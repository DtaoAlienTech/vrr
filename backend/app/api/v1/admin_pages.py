"""Staff endpoints for pages and their sections, site settings, redirects and the history
(undo). Every change to a page or to the settings keeps a version that can be put back."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import DbSession, Staff, SuperAdmin
from app.core.errors import ApiError, field_errors
from app.models import ContentRevision, Page, PageSection, Redirect, SiteSetting
from app.models.enums import MediaKind, PublishStatus, RevisionAction
from app.schemas.admin import (
    PageAdminOut,
    PageIn,
    PageListOut,
    RedirectAdminOut,
    RedirectIn,
    ReorderIn,
    RevisionDetailOut,
    RevisionOut,
    SectionIn,
    SectionUpdateIn,
)
from app.schemas.blocks import collect_media_ids, validate_section
from app.schemas.settings import SETTINGS_GROUPS, validate_settings
from app.services import admin_ops as ops
from app.services.admin_ops import MediaBriefs
from app.services.auth import Auth
from app.services.revalidate import ALL_TAGS
from app.services.revisions import RESTORERS, restorer

router = APIRouter(prefix="/admin", tags=["admin pages"])

IMAGE = MediaKind.IMAGE
# Addresses the website itself uses: a page must never take them over.
RESERVED_SLUGS = {
    "admin",
    "api",
    "uploads",
    "internal",
    "_next",
    "icon",
    "robots",
    "sitemap",
    "static",
}


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


# ============================ pages ============================


def page_snapshot(page: Page) -> dict[str, Any]:
    """The page and all its sections, in the shape the API accepts."""
    return {
        "page": _clean(
            {
                "title": page.title,
                "slug": page.slug,
                "seoTitle": page.seo_title,
                "seoDescription": page.seo_description,
                "ogMediaId": page.og_media_id,
                "robotsNoindex": page.robots_noindex,
                "status": page.status,
            }
        ),  # fmt: skip
        "sections": [
            {"type": s.type, "data": s.data, "isVisible": s.is_visible} for s in page.sections
        ],
    }


def _get_page(db: Session, page_id: int) -> Page:
    page = db.scalar(select(Page).where(Page.id == page_id).options(selectinload(Page.sections)))
    if page is None:
        raise ApiError(404, "not_found", "That page does not exist.")
    return page


def _page_out(db: Session, page: Page) -> dict[str, Any]:
    ids: set[int] = {page.og_media_id} if page.og_media_id else set()
    for section in page.sections:
        ids |= collect_media_ids(section.data)
    briefs = MediaBriefs(db).load(ids)
    return {
        "id": page.id, "key": page.key, "title": page.title, "slug": page.slug,
        "seo_title": page.seo_title, "seo_description": page.seo_description,
        "og_media": briefs.get(page.og_media_id), "robots_noindex": page.robots_noindex,
        "status": page.status, "published_at": page.published_at,
        "sections": [
            {"id": s.id, "type": s.type, "position": s.position, "data": s.data,
             "is_visible": s.is_visible}
            for s in page.sections
        ],
        "media": {str(i): briefs.get(i) for i in sorted(ids) if briefs.get(i)},
        "updated_at": page.updated_at,
    }  # fmt: skip


def _apply_page_fields(db: Session, auth: Auth, page: Page, data: PageIn) -> None:
    if page.key == "home":
        if data.slug is not None:
            raise ApiError(422, "home_address_fixed", "The home page always lives at /.")
        if data.status != PublishStatus.PUBLISHED:
            raise ApiError(422, "home_must_be_published", "The home page cannot be a draft.")
    if data.slug in RESERVED_SLUGS:
        raise ApiError(422, "reserved_slug", "That address is used by the website itself.")
    ops.ensure_media(db, [data.og_media_id], kind=IMAGE, what="The share image")
    old_slug, was_public = page.slug, page.status == PublishStatus.PUBLISHED.value
    if page.key != "home":
        page.slug = ops.choose_slug(
            db, Page, wanted=data.slug, title=data.title, current=page.slug, row_id=page.id
        )
    page.title, page.seo_title, page.seo_description = (
        data.title,
        data.seo_title,
        data.seo_description,
    )
    page.og_media_id, page.robots_noindex = data.og_media_id, data.robots_noindex
    page.status = data.status.value
    if data.status == PublishStatus.PUBLISHED and page.published_at is None:
        page.published_at = datetime.now(UTC)
    ops.flush_or_conflict(db)
    if page.key != "home" and was_public and old_slug != page.slug:
        ops.add_redirect(db, f"/{old_slug}", f"/{page.slug}", auth.user.id)


def _check_section(db: Session, section_type: str, data: dict[str, Any]) -> dict[str, Any]:
    """The clean data to store, or a 422 that says which field is wrong."""
    try:
        clean = validate_section(section_type, data)
    except ValidationError as error:
        raise ApiError(
            422, "invalid_section", "Please check the fields marked below.",
            extra={"errors": field_errors(error)},
        ) from None  # fmt: skip
    except ValueError:
        raise ApiError(
            422, "unknown_section_type", "That kind of section does not exist."
        ) from None
    ops.ensure_media(db, collect_media_ids(clean), kind=IMAGE, what="A photo in this section")
    return clean


def _renumber(sections: list[PageSection]) -> None:
    for position, section in enumerate(sections):
        section.position = position


def _commit_page(
    db: Session,
    request: Request,
    auth: Auth,
    page: Page,
    before: dict[str, Any],
    action: str,
    changes: dict[str, Any] | None = None,
) -> None:
    db.flush()
    db.refresh(page, ["sections"])
    ops.save_revision(
        db, entity="page", entity_id=page.id, data=page_snapshot(page),
        action=RevisionAction.UPDATE, user_id=auth.user.id, baseline=before,
    )  # fmt: skip
    ops.finish(db, request, auth, action=action, entity="page", entity_id=page.id,
               tags=["pages"], changes=changes)  # fmt: skip


@router.get("/pages", response_model=list[PageListOut])
def list_pages(_: Staff, db: DbSession):
    counts = dict(
        db.execute(select(PageSection.page_id, func.count()).group_by(PageSection.page_id)).all()
    )
    return [
        {
            "id": p.id, "key": p.key, "title": p.title, "slug": p.slug, "status": p.status,
            "robots_noindex": p.robots_noindex, "sections": counts.get(p.id, 0),
            "updated_at": p.updated_at,
        }
        for p in db.scalars(select(Page).order_by(Page.id))
    ]  # fmt: skip


@router.get("/pages/{page_id}", response_model=PageAdminOut)
def read_page(page_id: int, _: Staff, db: DbSession):
    return _page_out(db, _get_page(db, page_id))


@router.put("/pages/{page_id}", response_model=PageAdminOut)
def update_page(
    page_id: int,
    data: PageIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    _apply_page_fields(db, auth, page, data)
    _commit_page(db, request, auth, page, before, "page_update",
                 {"fields": sorted(k for k, v in page_snapshot(page)["page"].items()
                                   if before["page"].get(k) != v)})  # fmt: skip
    return _page_out(db, page)


# ---- sections ----


@router.post("/pages/{page_id}/sections", status_code=status.HTTP_201_CREATED,
             response_model=PageAdminOut)  # fmt: skip
def add_section(
    page_id: int,
    data: SectionIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    clean = _check_section(db, data.type, data.data)
    section = PageSection(page_id=page.id, type=data.type, data=clean, is_visible=data.is_visible,
                          position=0)  # fmt: skip
    sections = list(page.sections)
    sections.insert(
        min(data.position if data.position is not None else len(sections), len(sections)), section
    )
    db.add(section)
    _renumber(sections)
    _commit_page(db, request, auth, page, before, "section_add",
                 {"type": data.type})  # fmt: skip
    return _page_out(db, page)


def _find_section(page: Page, section_id: int) -> PageSection:
    for section in page.sections:
        if section.id == section_id:
            return section
    raise ApiError(404, "not_found", "That section does not exist on this page.")


@router.put("/pages/{page_id}/sections/{section_id}", response_model=PageAdminOut)
def update_section(
    page_id: int,
    section_id: int,
    data: SectionUpdateIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    section = _find_section(page, section_id)
    if data.data is not None:
        section.data = _check_section(db, section.type, data.data)
    if data.is_visible is not None:
        section.is_visible = data.is_visible
    _commit_page(db, request, auth, page, before, "section_update",
                 {"type": section.type})  # fmt: skip
    return _page_out(db, page)


@router.post("/pages/{page_id}/sections/reorder", response_model=PageAdminOut)
def reorder_sections(
    page_id: int,
    data: ReorderIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    by_id = {s.id: s for s in page.sections}
    if sorted(data.ids) != sorted(by_id):
        raise ApiError(
            422, "invalid_order", "The list must contain every section of the page once."
        )
    _renumber([by_id[i] for i in data.ids])
    _commit_page(db, request, auth, page, before, "section_reorder")
    return _page_out(db, page)


@router.post("/pages/{page_id}/sections/{section_id}/duplicate",
             status_code=status.HTTP_201_CREATED, response_model=PageAdminOut)  # fmt: skip
def duplicate_section(
    page_id: int,
    section_id: int,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    original = _find_section(page, section_id)
    copy = PageSection(page_id=page.id, type=original.type, data=original.data,
                       is_visible=original.is_visible, position=0)  # fmt: skip
    sections = list(page.sections)
    sections.insert(sections.index(original) + 1, copy)
    db.add(copy)
    _renumber(sections)
    _commit_page(db, request, auth, page, before, "section_duplicate",
                 {"type": original.type})  # fmt: skip
    return _page_out(db, page)


@router.delete("/pages/{page_id}/sections/{section_id}", response_model=PageAdminOut)
def delete_section(
    page_id: int,
    section_id: int,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    page = _get_page(db, page_id)
    before = page_snapshot(page)
    section = _find_section(page, section_id)
    remaining = [s for s in page.sections if s.id != section_id]
    page.sections.remove(section)  # (delete-orphan removes it)
    _renumber(remaining)
    _commit_page(db, request, auth, page, before, "section_delete",
                 {"type": section.type})  # fmt: skip
    return _page_out(db, page)


@restorer("page")
def restore_page(db: Session, auth: Auth, entity_id: int, data: dict[str, Any]) -> int:
    page = _get_page(db, entity_id)  # (pages are never deleted, so this always exists)
    _apply_page_fields(db, auth, page, PageIn.model_validate(data["page"]))
    sections = [
        PageSection(
            page_id=page.id, type=item["type"], position=position,
            data=_check_section(db, item["type"], item["data"]),
            is_visible=item.get("isVisible", True),
        )
        for position, item in enumerate(data["sections"])
    ]  # fmt: skip
    page.sections = sections
    ops.flush_or_conflict(db)
    return page.id


# ========================= site settings =========================

SETTINGS_LABELS = {
    "brand": "Name, logo and footer text",
    "contact": "Contact details",
    "social": "Social media links",
    "menu": "Header menu",
    "footer_courses": "Footer course links",
    "seo": "Search engines and sharing",
}


def _group(name: str) -> str:
    if name not in SETTINGS_GROUPS:
        raise ApiError(404, "not_found", "That settings group does not exist.")
    return name


def settings_snapshot(row: SiteSetting) -> dict[str, Any]:
    return {"group": row.key, "value": row.value}


@router.get("/settings/schema")
def settings_schema(_: SuperAdmin) -> dict[str, dict[str, Any]]:
    """The settings groups and their JSON Schemas: the admin builds its forms from these."""
    return {
        name: {
            "label": SETTINGS_LABELS[name],
            "schema": model.model_json_schema(by_alias=True, mode="validation"),
        }
        for name, model in SETTINGS_GROUPS.items()
    }


@router.get("/settings")
def read_settings(_: SuperAdmin, db: DbSession) -> dict[str, Any]:
    rows = {row.key: row.value for row in db.scalars(select(SiteSetting))}
    ids: set[int] = set()
    for value in rows.values():
        ids |= collect_media_ids(value)
    briefs = MediaBriefs(db).load(ids)
    return {
        "groups": {name: rows.get(name) for name in SETTINGS_GROUPS},
        "media": {str(i): briefs.get(i) for i in sorted(ids) if briefs.get(i)},
    }


@router.put("/settings/{group}")
def update_settings(
    group: str,
    data: dict[str, Any],
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
) -> dict[str, Any]:
    name = _group(group)
    try:
        clean = validate_settings(name, data)
    except ValidationError as error:
        raise ApiError(
            422, "invalid_settings", "Please check the fields marked below.",
            extra={"errors": field_errors(error)},
        ) from None  # fmt: skip
    ops.ensure_media(db, collect_media_ids(clean), kind=IMAGE, what="A photo in the settings")
    row = db.scalar(select(SiteSetting).where(SiteSetting.key == name))
    before = settings_snapshot(row) if row else None
    if row is None:
        row = SiteSetting(key=name, value=clean)
        db.add(row)
    else:
        row.value = clean
    row.updated_by = auth.user.id
    ops.flush_or_conflict(db)
    ops.save_revision(
        db, entity="settings", entity_id=row.id, data=settings_snapshot(row),
        action=RevisionAction.UPDATE, user_id=auth.user.id, baseline=before,
    )  # fmt: skip
    ops.finish(db, request, auth, action="settings_update", entity="settings",
               entity_id=row.id, tags=ALL_TAGS, changes={"group": name})  # fmt: skip
    return clean


@restorer("settings")
def restore_settings(db: Session, auth: Auth, entity_id: int, data: dict[str, Any]) -> int:
    row = db.get(SiteSetting, entity_id)
    if row is None or row.key != data.get("group"):
        raise ApiError(404, "not_found", "That settings group does not exist any more.")
    clean = validate_settings(row.key, data["value"])
    ops.ensure_media(db, collect_media_ids(clean), kind=IMAGE, what="A photo in the settings")
    row.value, row.updated_by = clean, auth.user.id
    ops.flush_or_conflict(db)
    return row.id


# ============================ redirects ============================


@router.get("/redirects", response_model=list[RedirectAdminOut])
def list_redirects(
    _: Staff,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    query = select(Redirect).order_by(Redirect.id.desc()).limit(limit).offset(offset)
    return [
        {"id": r.id, "from_path": r.from_path, "to_path": r.to_path,
         "status_code": r.status_code, "created_at": r.created_at}
        for r in db.scalars(query)
    ]  # fmt: skip


@router.post("/redirects", status_code=status.HTTP_201_CREATED, response_model=RedirectAdminOut)
def create_redirect(data: RedirectIn, request: Request, auth: Staff, db: DbSession):
    if db.scalar(select(Redirect.id).where(Redirect.from_path == data.from_path)):
        raise ApiError(409, "redirect_exists", "That address already redirects somewhere.")
    if db.scalar(select(Redirect.id).where(Redirect.from_path == data.to_path)):
        raise ApiError(
            422, "redirect_chain", "The target address redirects somewhere else; use that one."
        )
    row = Redirect(from_path=data.from_path, to_path=data.to_path, status_code=data.status_code,
                   created_by=auth.user.id)  # fmt: skip
    db.add(row)
    ops.flush_or_conflict(db)
    ops.finish(db, request, auth, action="redirect_create", entity="redirect",
               entity_id=row.id, tags=["redirects"])  # fmt: skip
    return {"id": row.id, "from_path": row.from_path, "to_path": row.to_path,
            "status_code": row.status_code, "created_at": row.created_at}  # fmt: skip


@router.delete("/redirects/{redirect_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_redirect(redirect_id: int, request: Request, auth: Staff, db: DbSession):
    row = db.get(Redirect, redirect_id)
    if row is None:
        raise ApiError(404, "not_found", "That redirect does not exist.")
    db.delete(row)
    ops.finish(db, request, auth, action="redirect_delete", entity="redirect",
               entity_id=redirect_id, tags=["redirects"])  # fmt: skip


# ============================ history ============================

RESTORE_TAGS = {
    "news": ["news"],
    "activity": ["activities"],
    "page": ["pages"],
    "settings": ALL_TAGS,
}


@router.get("/revisions", response_model=list[RevisionOut])
def list_revisions(
    _: Staff,
    db: DbSession,
    entity: Annotated[str | None, Query(max_length=40)] = None,
    entity_id: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1)] = None,
):
    """Saved versions, newest first (the data of each version is read one at a time)."""
    query = select(ContentRevision).order_by(ContentRevision.id.desc()).limit(limit)
    if entity:
        query = query.where(ContentRevision.entity == entity)
    if entity_id:
        query = query.where(ContentRevision.entity_id == entity_id)
    if before_id:
        query = query.where(ContentRevision.id < before_id)
    return [
        {"id": r.id, "entity": r.entity, "entity_id": r.entity_id, "action": r.action,
         "user_id": r.user_id, "created_at": r.created_at}
        for r in db.scalars(query)
    ]  # fmt: skip


def _get_revision(db: Session, revision_id: int) -> ContentRevision:
    row = db.get(ContentRevision, revision_id)
    if row is None:
        raise ApiError(404, "not_found", "That version does not exist.")
    return row


@router.get("/revisions/{revision_id}", response_model=RevisionDetailOut)
def read_revision(revision_id: int, _: Staff, db: DbSession):
    r = _get_revision(db, revision_id)
    return {"id": r.id, "entity": r.entity, "entity_id": r.entity_id, "action": r.action,
            "user_id": r.user_id, "created_at": r.created_at, "data": r.data}  # fmt: skip


@router.post("/revisions/{revision_id}/restore")
def restore_revision(
    revision_id: int, request: Request, auth: Staff, db: DbSession
) -> dict[str, Any]:
    """Puts an old version back. (The current state is kept in the history too, so this can be
    undone again.)"""
    revision = _get_revision(db, revision_id)
    if revision.entity == "settings" and auth.user.role != "super_admin":
        raise ApiError(403, "forbidden", "Only a super admin can change the settings.")
    restore = RESTORERS.get(revision.entity)
    if restore is None:
        raise ApiError(422, "not_restorable", "This kind of change cannot be restored.")
    try:
        new_id = restore(db, auth, revision.entity_id, revision.data)
    except ValidationError as error:
        raise ApiError(
            422, "invalid_version", "That version no longer fits the rules.",
            extra={"errors": field_errors(error)},
        ) from None  # fmt: skip
    ops.save_revision(
        db, entity=revision.entity, entity_id=new_id, data=revision.data,
        action=RevisionAction.RESTORE, user_id=auth.user.id,
    )  # fmt: skip
    ops.finish(db, request, auth, action="revision_restore", entity=revision.entity,
               entity_id=new_id, tags=RESTORE_TAGS[revision.entity],
               changes={"revision": revision_id})  # fmt: skip
    return {"entity": revision.entity, "entityId": new_id}
