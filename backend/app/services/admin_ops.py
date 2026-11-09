"""The steps every staff change shares, so each resource stays short and behaves the same way:
check that referenced files exist, make URL-safe unique addresses, keep revisions for undo,
create redirects when an address changes, record the change and tell the website to refresh."""

import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from fastapi import Request
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ApiError
from app.models import ContentRevision, Media, Redirect
from app.models.enums import MediaKind, RevisionAction
from app.schemas.media import media_admin_dict
from app.services import audit, revalidate
from app.services.auth import Auth
from app.services.enquiries import client_ip

MAX_REVISIONS_PER_ITEM = 50


def like_pattern(text: str) -> str:
    """A search text for ILIKE where %, _ and \\ mean themselves (use with escape="\\")."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


# ---- referenced photos and PDFs ----


def ensure_media(db: Session, ids: Iterable[int | None], *, kind: MediaKind, what: str) -> None:
    """Every id must be a file in the library, of the right kind (a photo or a PDF)."""
    wanted = {i for i in ids if i is not None}
    if not wanted:
        return
    found = dict(db.execute(select(Media.id, Media.kind).where(Media.id.in_(wanted))).all())
    missing = sorted(wanted - found.keys())
    if missing:
        raise ApiError(
            422, "unknown_media", f"{what}: file {missing[0]} is not in the media library."
        )
    if any(found[i] != kind.value for i in wanted):
        article = "a photo" if kind == MediaKind.IMAGE else "a PDF document"
        raise ApiError(422, "wrong_media_type", f"{what} must be {article}.")


class MediaBriefs:
    """The few facts about a file that an edit form needs to show it."""

    def __init__(self, db: Session) -> None:
        self._db = db
        self._prefix = get_settings().uploads_url
        self._rows: dict[int, Media] = {}

    def load(self, ids: Iterable[int | None]) -> "MediaBriefs":
        missing = {i for i in ids if i is not None} - self._rows.keys()
        if missing:
            for row in self._db.scalars(select(Media).where(Media.id.in_(missing))):
                self._rows[row.id] = row
        return self

    def get(self, media_id: int | None) -> dict[str, Any] | None:
        if media_id is None:
            return None
        if media_id not in self._rows:
            self.load([media_id])
        row = self._rows.get(media_id)
        if row is None:
            return None
        full = media_admin_dict(row, self._prefix)
        keys = (
            "id",
            "kind",
            "url",
            "thumb_url",
            "alt_text",
            "width",
            "height",
            "original_filename",
        )
        return {key: full[key] for key in keys}


# ---- addresses (slugs) ----


def slugify(text: str, *, fallback: str = "item") -> str:
    """ "Admissions Open 2026!" -> "admissions-open-2026". Letters of other scripts (for example
    Telugu) cannot be written in a URL-safe way, so such titles use the fallback word."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", plain.lower()).strip("-")[:80].strip("-")
    return slug or fallback


def slug_taken(db: Session, model: Any, slug: str, exclude_id: int | None = None) -> bool:
    query = select(model.id).where(model.slug == slug)
    if exclude_id is not None:
        query = query.where(model.id != exclude_id)
    return db.scalar(query.limit(1)) is not None


def unique_slug(db: Session, model: Any, base: str) -> str:
    candidate, number = base, 2
    while slug_taken(db, model, candidate):
        candidate = f"{base[:70]}-{number}"
        number += 1
    return candidate


def choose_slug(
    db: Session,
    model: Any,
    *,
    wanted: str | None,
    title: str,
    current: str | None,
    row_id: int | None,
) -> str:
    """The address to use: the one asked for (it must be free), else the current one, else made
    from the title."""
    if wanted is not None:
        if slug_taken(db, model, wanted, row_id):
            raise ApiError(409, "slug_taken", "That address is already used by something else.")
        return wanted
    return current if current is not None else unique_slug(db, model, slugify(title))


def flush_or_conflict(db: Session) -> None:
    """Writes pending changes; a clash with an existing item becomes a clean 409."""
    try:
        with db.begin_nested():
            db.flush()
    except IntegrityError:
        raise ApiError(
            409, "conflict", "That clashes with an existing item (for example the address)."
        ) from None


# ---- redirects ----


def add_redirect(db: Session, old_path: str, new_path: str, user_id: int | None) -> None:
    """Old address -> new address, so existing links and search results keep working."""
    if old_path == new_path:
        return
    # the new address may once have been redirected away: it is live again
    db.execute(delete(Redirect).where(Redirect.from_path == new_path))
    # keep chains short: whatever pointed to the old address now points to the new one
    db.execute(update(Redirect).where(Redirect.to_path == old_path).values(to_path=new_path))
    existing = db.scalar(select(Redirect).where(Redirect.from_path == old_path))
    if existing is None:
        db.add(Redirect(from_path=old_path, to_path=new_path, status_code=301, created_by=user_id))
    else:
        existing.to_path = new_path
    db.flush()


# ---- revisions (undo) ----


def save_revision(
    db: Session,
    *,
    entity: str,
    entity_id: int,
    data: dict[str, Any],
    action: RevisionAction,
    user_id: int | None,
    baseline: dict[str, Any] | None = None,
) -> None:
    """Keeps the state after a change. `baseline` (the state before it) is saved too when this
    item has no history yet, so even the very first edit can be undone."""
    has_history = db.scalar(
        select(func.count())
        .select_from(ContentRevision)
        .where(ContentRevision.entity == entity, ContentRevision.entity_id == entity_id)
    )
    if baseline is not None and not has_history:
        db.add(
            ContentRevision(
                entity=entity, entity_id=entity_id, data=baseline,
                action=RevisionAction.CREATE.value, user_id=None,
            )
        )  # fmt: skip
    db.add(
        ContentRevision(
            entity=entity, entity_id=entity_id, data=data, action=action.value, user_id=user_id
        )
    )
    db.flush()
    old = (
        select(ContentRevision.id)
        .where(ContentRevision.entity == entity, ContentRevision.entity_id == entity_id)
        .order_by(ContentRevision.id.desc())
        .offset(MAX_REVISIONS_PER_ITEM)
    )
    db.execute(delete(ContentRevision).where(ContentRevision.id.in_(old)))


# ---- finishing a change ----


def finish(
    db: Session,
    request: Request,
    auth: Auth,
    *,
    action: str,
    entity: str,
    entity_id: int | None,
    tags: list[str],
    changes: dict[str, Any] | None = None,
) -> None:
    """Records who did it, saves everything, then tells the website which cached pages are out of
    date. This happens BEFORE the answer is sent, so an editor who looks at the site straight after
    saving always sees the change. It never fails the save: if the website does not answer (it
    is capped at a few seconds) the page refreshes itself within the hour."""
    settings = get_settings()
    audit.record(
        db,
        action,
        user_id=auth.user.id,
        entity=entity,
        entity_id=entity_id,
        changes=changes,
        ip=client_ip(request, settings),
    )
    db.commit()
    if tags:
        revalidate.notify(settings, tags)


# ---- order ----


def reorder(db: Session, model: Any, ids: list[int]) -> None:
    """Puts the items in the given order (their sort_order becomes their position in the list)."""
    if len(set(ids)) != len(ids):
        raise ApiError(422, "invalid_order", "The list contains the same item twice.")
    found = set(db.scalars(select(model.id).where(model.id.in_(ids))))
    if found != set(ids):
        raise ApiError(422, "invalid_order", "The list contains an item that does not exist.")
    for position, item_id in enumerate(ids):
        db.execute(update(model).where(model.id == item_id).values(sort_order=position))
