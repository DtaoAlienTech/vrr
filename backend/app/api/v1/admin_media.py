"""The media library: upload, list, rename (alt text), delete. Staff only."""

from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, Request, UploadFile, status
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import select

from app.api.deps import DbSession, Staff
from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import Media
from app.models.enums import MediaKind
from app.schemas.common import AltText
from app.schemas.media import (
    MediaAdminOut,
    MediaUpdateIn,
    MediaUsageListOut,
    media_admin_dict,
)
from app.services import audit, revalidate
from app.services import media as media_service
from app.services.enquiries import client_ip

router = APIRouter(prefix="/admin/media", tags=["admin media"])

_ALT = TypeAdapter(AltText)
_NOT_FOUND = ("not_found", "That file does not exist.")


def _get(db: DbSession, media_id: int) -> Media:
    row = db.get(Media, media_id)
    if row is None:
        raise ApiError(404, *_NOT_FOUND)
    return row


def _out(row: Media) -> dict:
    return media_admin_dict(row, get_settings().uploads_url)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=MediaAdminOut)
def upload(
    request: Request,
    auth: Staff,
    db: DbSession,
    file: Annotated[UploadFile, File()],
    alt_text: Annotated[str | None, Form(alias="altText")] = None,
    crop_bottom: Annotated[bool, Form(alias="cropBottom")] = False,
):
    settings = get_settings()
    if audit.recent_user_count(db, "media_upload", auth.user.id, seconds=3600) >= (
        media_service.MAX_UPLOADS_PER_HOUR
    ):
        raise ApiError(429, "too_many_uploads", "Too many uploads this hour. Please wait a while.")

    raw = file.file.read(settings.max_upload_bytes + 1)
    if len(raw) > settings.max_upload_bytes:
        raise ApiError(
            413, "file_too_large", f"The file is larger than {settings.max_upload_mb} MB."
        )
    is_pdf = raw.startswith(b"%PDF-")
    try:
        alt = _ALT.validate_python(alt_text) if alt_text else ""
    except ValidationError:
        raise ApiError(
            422, "invalid_alt_text", "Describe the file in a few words (up to 300 characters)."
        ) from None
    if not alt and not is_pdf:
        raise ApiError(
            422,
            "invalid_alt_text",
            "Describe the photo in a few words (for people who cannot see it).",
        )

    row = media_service.save_upload(
        db,
        media_service.Storage.from_settings(settings),
        raw=raw,
        filename=file.filename,
        alt_text=alt,
        crop_bottom=crop_bottom,
        user_id=auth.user.id,
    )
    audit.record(
        db,
        "media_upload",
        user_id=auth.user.id,
        entity="media",
        entity_id=row.id,
        changes={"kind": row.kind, "sizeBytes": row.size_bytes},
        ip=client_ip(request, settings),
    )
    db.commit()
    return _out(row)


@router.get("", response_model=list[MediaAdminOut])
def list_media(
    _: Staff,
    db: DbSession,
    kind: MediaKind | None = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 40,
    before_id: Annotated[int | None, Query(ge=1)] = None,
):
    """Newest first. `before_id` continues after the last item of the previous page."""
    query = select(Media).order_by(Media.id.desc()).limit(limit)
    if kind:
        query = query.where(Media.kind == kind.value)
    if before_id:
        query = query.where(Media.id < before_id)
    if q and q.strip():
        escaped = q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        pattern = f"%{escaped}%"
        query = query.where(
            Media.original_filename.ilike(pattern, escape="\\")
            | Media.alt_text.ilike(pattern, escape="\\")
        )
    return [_out(row) for row in db.scalars(query)]


@router.get("/{media_id}", response_model=MediaAdminOut)
def read_media(media_id: int, _: Staff, db: DbSession):
    return _out(_get(db, media_id))


@router.get("/{media_id}/usage", response_model=MediaUsageListOut)
def media_usage(media_id: int, _: Staff, db: DbSession):
    """Where this file is used (shown before deleting)."""
    row = _get(db, media_id)
    return {"usages": media_service.find_usages(db, row.id)}


@router.patch("/{media_id}", response_model=MediaAdminOut)
def update_media(
    media_id: int,
    payload: MediaUpdateIn,
    request: Request,
    background: BackgroundTasks,
    auth: Staff,
    db: DbSession,
):
    settings = get_settings()
    row = _get(db, media_id)
    changed = []
    if payload.alt_text is not None:
        row.alt_text = payload.alt_text
        changed.append("altText")
    if payload.crop_bottom is not None:
        row.crop_bottom = payload.crop_bottom
        changed.append("cropBottom")
    audit.record(
        db,
        "media_update",
        user_id=auth.user.id,
        entity="media",
        entity_id=row.id,
        changes={"fields": changed},
        ip=client_ip(request, settings),
    )
    db.commit()
    # pages show the alt text and the date-stamp crop, so they must be refreshed
    background.add_task(revalidate.notify, settings, revalidate.ALL_TAGS)
    return _out(row)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(media_id: int, request: Request, auth: Staff, db: DbSession):
    settings = get_settings()
    row = _get(db, media_id)
    entry = {"kind": row.kind}
    media_service.delete_media(db, media_service.Storage.from_settings(settings), row)
    audit.record(
        db,
        "media_delete",
        user_id=auth.user.id,
        entity="media",
        entity_id=media_id,
        changes=entry,
        ip=client_ip(request, settings),
    )
    db.commit()
