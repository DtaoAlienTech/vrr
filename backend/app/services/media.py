"""Uploaded photos and PDFs: saving them (files and database entry together), finding where they
are used, deleting them safely and cleaning up leftovers. Picture processing itself lives in
images.py; the rules for what may be uploaded are decided there."""

import logging
import os
import re
import secrets
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import cast, func, literal, or_, select
from sqlalchemy.dialects.postgresql import JSONB, JSONPATH
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.models import (
    Activity,
    ActivityPhoto,
    Course,
    Faculty,
    GalleryItem,
    Media,
    News,
    NewsAttachment,
    Page,
    PageSection,
    SiteSetting,
)
from app.models.enums import MediaKind
from app.services.images import FileRejected, Variant, check_pdf, detect_kind, process_image

log = logging.getLogger("app.media")

MAX_UPLOADS_PER_HOUR = 300  # per person: a bulk gallery upload is fine, a runaway script is not


@dataclass(frozen=True)
class Storage:
    upload_dir: Path  # served to visitors at /uploads
    originals_dir: Path | None  # the photos exactly as uploaded (private); None = not kept

    @classmethod
    def from_settings(cls, settings: Settings) -> "Storage":
        return cls(settings.upload_dir, settings.originals_dir)


# ---- file names ----

_TOKEN_NAME = re.compile(r"^(?P<base>[0-9a-f]{24})-\d+\.webp$")


def base_of(stored_name: str) -> str:
    """The shared part of a photo's file names: "ab12...-1600.webp" and "ab12...-800.webp" share
    "ab12...". (Photos from the starter content keep their own name, e.g. "seed-campus-1".)"""
    match = _TOKEN_NAME.match(stored_name)
    return match["base"] if match else Path(stored_name).stem


def _plain_name(name: str) -> bool:
    """A single file name: no folders, no tricks. (Names are made by us, but they come back from
    the database, so they are checked again before a file is touched.)"""
    return bool(name) and name == Path(name).name and name not in (".", "..")


def clean_filename(name: str | None) -> str:
    """The uploaded file's own name, made harmless. It is only ever shown in the admin panel."""
    base = re.split(r"[\\/]", name or "")[-1]
    base = "".join(c if c.isprintable() and ord(c) >= 32 else "_" for c in base)
    base = re.sub(r"[  ‪-‮⁦-⁩]", "_", base).strip(" .")
    return base[:255] or "upload"


def _write(path: Path, data: bytes, mode: int) -> None:
    """Write to a temporary name first, so a half-written file is never visible."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_bytes(data)
    os.chmod(temporary, mode)
    os.replace(temporary, path)


def _remove(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except OSError as error:
        log.warning("could not remove %s (%s)", path.name, type(error).__name__)


# ---- saving ----


def _write_variants(storage: Storage, base: str, variants: list[Variant]) -> list[dict[str, Any]]:
    entries = []
    for variant in variants:
        name = f"{base}-{variant.width}.webp"
        _write(storage.upload_dir / name, variant.data, 0o644)  # Caddy must be able to read it
        entries.append({"width": variant.width, "name": name})
    return entries


def save_upload(
    db: Session,
    storage: Storage,
    *,
    raw: bytes,
    filename: str | None,
    alt_text: str,
    crop_bottom: bool,
    user_id: int | None,
) -> Media:
    """Checks the file and stores it. Raises ApiError (415 wrong type, 422 not acceptable)."""
    kind = detect_kind(raw)
    if kind is None:
        raise ApiError(
            415, "unsupported_type", "Upload a JPEG, PNG or WebP photo, or a PDF document."
        )
    token = secrets.token_hex(12)
    written: list[Path] = []
    try:
        if kind == "image":
            variants = process_image(raw)
            entries = _write_variants(storage, token, variants)
            written += [storage.upload_dir / e["name"] for e in entries]
            if storage.originals_dir is not None:
                _write(storage.originals_dir / token, raw, 0o600)  # private: never served
                written.append(storage.originals_dir / token)
            largest = variants[-1]
            row = Media(
                kind=MediaKind.IMAGE.value,
                stored_name=entries[-1]["name"],
                mime="image/webp",
                size_bytes=len(largest.data),
                width=largest.width,
                height=largest.height,
                variants=entries,
            )
        else:
            check_pdf(raw)
            name = f"{token}.pdf"
            _write(storage.upload_dir / name, raw, 0o644)
            written.append(storage.upload_dir / name)
            row = Media(
                kind=MediaKind.PDF.value,
                stored_name=name,
                mime="application/pdf",
                size_bytes=len(raw),
            )
        row.original_filename = clean_filename(filename)
        row.alt_text = alt_text
        row.crop_bottom = crop_bottom
        row.uploaded_by = user_id
        db.add(row)
        db.flush()
    except FileRejected as error:
        _discard(written)
        raise ApiError(422, "invalid_file", str(error)) from error
    except Exception:
        _discard(written)  # never leave files behind for an entry that was not saved
        raise
    return row


def _discard(paths: list[Path]) -> None:
    for path in paths:
        _remove(path)


# ---- where is a file used? ----


def find_usages(db: Session, media_id: int) -> list[dict[str, Any]]:
    """Every place that points to this file. Photos inside page sections and settings are stored
    as {"mediaId": n} in JSON, so the database is asked exactly that (not a text search)."""
    usages: list[dict[str, Any]] = []

    def add(entity: str, entity_id: int, label: str) -> None:
        usages.append({"entity": entity, "id": entity_id, "label": label})

    pointer = literal({"id": media_id}, type_=JSONB)  # a JSON object, as Postgres requires
    path = cast("$.** ? (@.mediaId == $id)", JSONPATH)

    for page in db.scalars(select(Page).where(Page.og_media_id == media_id)):
        add("page", page.id, f"Share image of the page “{page.title}”")
    rows = db.execute(
        select(PageSection, Page)
        .join(Page, Page.id == PageSection.page_id)
        .where(func.jsonb_path_exists(PageSection.data, path, pointer))
    )
    for section, page in rows:
        add("page_section", section.id, f"Page “{page.title}” ({section.type} section)")
    for setting in db.scalars(
        select(SiteSetting).where(func.jsonb_path_exists(SiteSetting.value, path, pointer))
    ):
        add("settings", setting.id, f"Site settings ({setting.key})")
    for course in db.scalars(
        select(Course).where(
            or_(Course.syllabus_media_id == media_id, Course.cover_media_id == media_id)
        )
    ):
        add("course", course.id, f"Course “{course.name}”")
    for member in db.scalars(select(Faculty).where(Faculty.photo_media_id == media_id)):
        add("faculty", member.id, f"Faculty member “{member.name}”")
    for item in db.scalars(select(News).where(News.cover_media_id == media_id)):
        add("news", item.id, f"News “{item.title}”")
    for _attachment, item in db.execute(
        select(NewsAttachment, News)
        .join(News, News.id == NewsAttachment.news_id)
        .where(NewsAttachment.media_id == media_id)
    ):
        add("news", item.id, f"News “{item.title}” (attachment)")
    for activity in db.scalars(select(Activity).where(Activity.cover_media_id == media_id)):
        add("activity", activity.id, f"Activity “{activity.title}” (cover)")
    for _photo, activity in db.execute(
        select(ActivityPhoto, Activity)
        .join(Activity, Activity.id == ActivityPhoto.activity_id)
        .where(ActivityPhoto.media_id == media_id)
    ):
        add("activity", activity.id, f"Activity “{activity.title}” (photo)")
    for gallery in db.scalars(select(GalleryItem).where(GalleryItem.media_id == media_id)):
        add("gallery_item", gallery.id, "Gallery")
    return usages


# ---- deleting ----


def files_of(storage: Storage, row: Media) -> list[Path]:
    names = {row.stored_name, *(v["name"] for v in row.variants)}
    paths = [storage.upload_dir / n for n in sorted(names) if _plain_name(n)]
    if row.kind == MediaKind.IMAGE.value and storage.originals_dir is not None:
        base = base_of(row.stored_name)
        if _plain_name(base):
            paths.append(storage.originals_dir / base)
    return paths


def delete_media(db: Session, storage: Storage, row: Media) -> None:
    """Deletes the entry and its files, unless something still uses it."""
    usages = find_usages(db, row.id)
    if usages:
        raise ApiError(
            409,
            "media_in_use",
            "This file is still used. Remove it from those places first.",
            extra={"usages": usages},
        )
    paths = files_of(storage, row)
    db.delete(row)
    db.flush()  # the database refuses too (RESTRICT) if a link was missed above
    db.commit()
    _discard(paths)  # after the commit: a rolled-back delete must not lose its files


# ---- maintenance ----


def reprocess_media(row: Media, storage: Storage) -> bool:
    """(Re)makes the resized copies of a photo from its original (or, for the starter photos,
    from the served file). Returns False for PDFs and when the source file is missing."""
    if row.kind != MediaKind.IMAGE.value:
        return False
    base = base_of(row.stored_name)
    source = None
    if storage.originals_dir is not None and (storage.originals_dir / base).is_file():
        source = storage.originals_dir / base
    elif _plain_name(row.stored_name) and (storage.upload_dir / row.stored_name).is_file():
        source = storage.upload_dir / row.stored_name
    if source is None:
        log.warning("media %s: source file not found", row.id)
        return False
    variants = process_image(source.read_bytes())
    row.variants = _write_variants(storage, base, variants)
    return True


def cleanup_orphans(
    db: Session, storage: Storage, *, min_age_seconds: int = 3600, dry_run: bool = False
) -> list[Path]:
    """Removes files that no database entry refers to (left over from failed uploads or crashes).
    Files younger than `min_age_seconds` are kept: an upload may be in progress."""
    rows = list(db.scalars(select(Media)))
    served = {r.stored_name for r in rows} | {v["name"] for r in rows for v in r.variants}
    originals = {base_of(r.stored_name) for r in rows if r.kind == MediaKind.IMAGE.value}
    cutoff = time.time() - min_age_seconds
    removed: list[Path] = []
    for folder, keep in ((storage.upload_dir, served), (storage.originals_dir, originals)):
        if folder is None or not folder.is_dir():
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file() and path.name not in keep and path.stat().st_mtime < cutoff:
                removed.append(path)
                if not dry_run:
                    _remove(path)
    return removed
