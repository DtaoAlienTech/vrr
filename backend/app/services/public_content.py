"""Reads published content from the database and shapes it for the website (see schemas/public.py).
Only published, visible content leaves this module; drafts and hidden sections never do."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models import (
    Activity,
    Course,
    Faculty,
    GalleryItem,
    Media,
    News,
    Page,
    SiteSetting,
)
from app.models.enums import CATEGORY_LABELS, GALLERY_LABELS, GROUP_LABELS, PublishStatus
from app.schemas.blocks import collect_media_ids, replace_media

log = logging.getLogger("app.content")
INDIA = timezone(timedelta(hours=5, minutes=30))  # no daylight saving, so a fixed offset is exact


class MissingMedia(LookupError):
    """A section points to a photo that is not in the library (it was deleted)."""


class MediaLookup:
    """Loads the photos a response needs in few queries and builds their addresses."""

    def __init__(self, db: Session, uploads_url: str) -> None:
        self._db = db
        self._prefix = uploads_url.rstrip("/")
        self._rows: dict[int, Media] = {}

    def load(self, ids: set[int]) -> None:
        missing = ids - self._rows.keys()
        if missing:
            for row in self._db.scalars(select(Media).where(Media.id.in_(missing))):
                self._rows[row.id] = row

    def url(self, media_id: int) -> str:
        return f"{self._prefix}/{self._row(media_id).stored_name}"

    def ref(self, media_id: int) -> dict[str, Any]:
        """The picture as the website needs it: address, alt text, size and resized copies."""
        row = self._row(media_id)
        if row.width is None or row.height is None:
            raise MissingMedia(f"media {media_id} is not an image")
        ref: dict[str, Any] = {
            "url": f"{self._prefix}/{row.stored_name}",
            "alt": row.alt_text,
            "width": row.width,
            "height": row.height,
        }
        if row.variants:
            ref["variants"] = [
                {"url": f"{self._prefix}/{v['name']}", "width": v["width"]} for v in row.variants
            ]
        if row.crop_bottom:
            ref["cropBottom"] = True
        return ref

    def _row(self, media_id: int) -> Media:
        if media_id not in self._rows:
            self.load({media_id})
        try:
            return self._rows[media_id]
        except KeyError:
            raise MissingMedia(f"media {media_id} does not exist") from None


def _day(moment: datetime) -> str:
    return moment.astimezone(INDIA).date().isoformat()


# ---- settings ----


def get_site_settings(db: Session, media: MediaLookup) -> dict[str, Any] | None:
    groups = {row.key: row.value for row in db.scalars(select(SiteSetting))}
    needed = ("brand", "contact", "social", "menu", "footer_courses", "seo")
    if any(key not in groups for key in needed):
        return None
    media.load(collect_media_ids(groups))
    brand, seo = groups["brand"], groups["seo"]
    return {
        "name": brand["name"],
        "shortName": brand["shortName"],
        "tagline": brand["tagline"],
        "established": brand["established"],
        "topBar": brand["topBar"],
        "logo": media.ref(brand["logo"]["mediaId"]),
        "contact": groups["contact"],
        "social": groups["social"]["items"],
        "menu": groups["menu"]["items"],
        "footerCourses": groups["footer_courses"]["items"],
        "affiliationText": brand["affiliationText"],
        "copyright": brand["copyright"],
        "seo": {
            "defaultTitle": seo["defaultTitle"],
            "titleTemplate": seo["titleTemplate"],
            "description": seo["description"],
            "ogImage": media.ref(seo["ogImage"]["mediaId"]),
        },
    }


# ---- pages ----


def _published_pages():
    return select(Page).where(Page.status == PublishStatus.PUBLISHED.value)


def list_pages(db: Session) -> list[dict[str, Any]]:
    pages = db.scalars(_published_pages().order_by(Page.id))
    return [
        {"key": p.key, "slug": p.slug, "title": p.title, "noindex": p.robots_noindex or None}
        for p in pages
    ]


def _embedded_with_ids(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"id": index + 1, **block} for index, block in enumerate(blocks)]


def page_response(db: Session, page: Page, media: MediaLookup) -> dict[str, Any]:
    visible = [section for section in page.sections if section.is_visible]
    ids: set[int] = {page.og_media_id} if page.og_media_id else set()
    for section in visible:
        ids |= collect_media_ids(section.data)
    media.load(ids)

    sections: list[dict[str, Any]] = []
    for section in visible:
        try:
            data = replace_media(section.data, media.ref)
        except MissingMedia as error:
            # Never break the whole page because one section lost a photo.
            log.warning("page %s: section %s skipped (%s)", page.key, section.id, error)
            continue
        if section.type == "two_column":
            data["main"] = _embedded_with_ids(data["main"])
            data["aside"] = _embedded_with_ids(data["aside"])
        sections.append({"id": section.id, "type": section.type, "data": data})

    default_description = ""
    seo_row = db.scalar(select(SiteSetting).where(SiteSetting.key == "seo"))
    if seo_row:
        default_description = seo_row.value.get("description", "")
    seo: dict[str, Any] = {
        "title": page.seo_title or page.title,
        "description": page.seo_description or default_description,
        "noindex": page.robots_noindex or None,
    }
    if page.og_media_id:
        try:
            seo["ogImage"] = media.ref(page.og_media_id)
        except MissingMedia as error:
            log.warning("page %s: share image skipped (%s)", page.key, error)
    return {
        "key": page.key,
        "slug": page.slug,
        "title": page.title,
        "seo": seo,
        "sections": sections,
    }


def get_page(db: Session, media: MediaLookup, *, key: str | None = None, slug: str | None = None):
    query = _published_pages().options(selectinload(Page.sections))
    query = query.where(Page.key == key) if key is not None else query.where(Page.slug == slug)
    page = db.scalar(query)
    return page_response(db, page, media) if page else None


# ---- courses and faculty ----


def _course(course: Course, media: MediaLookup) -> dict[str, Any]:
    out: dict[str, Any] = {
        "slug": course.slug,
        "tab": course.tab,
        "name": course.name,
        "department": f"Department of {course.department.name}",
        "duration": f"{course.duration_years} year{'s' if course.duration_years != 1 else ''}",
        "affiliation": course.affiliation,
        "summary": course.summary,
        "description": course.description,
        "subjects": course.subjects or None,
        "eligibility": course.eligibility,
        "seats": course.seats,
        "fees": course.fees,
    }
    if course.syllabus_media_id:
        try:
            out["syllabus"] = {"title": "Syllabus", "href": media.url(course.syllabus_media_id)}
        except MissingMedia as error:
            log.warning("course %s: syllabus skipped (%s)", course.slug, error)
    return out


def _published_courses():
    return (
        select(Course)
        .where(Course.is_published.is_(True))
        .options(joinedload(Course.department))
        .order_by(Course.sort_order, Course.id)
    )


def list_courses(db: Session, media: MediaLookup) -> list[dict[str, Any]]:
    rows = list(db.scalars(_published_courses()))
    media.load({c.syllabus_media_id for c in rows if c.syllabus_media_id})
    return [_course(c, media) for c in rows]


def get_course(db: Session, media: MediaLookup, slug: str) -> dict[str, Any] | None:
    course = db.scalar(_published_courses().where(Course.slug == slug))
    return _course(course, media) if course else None


def list_faculty(db: Session, media: MediaLookup, department: str | None) -> list[dict[str, Any]]:
    query = (
        select(Faculty)
        .where(Faculty.is_active.is_(True))
        .options(joinedload(Faculty.department))
        .order_by(Faculty.sort_order, Faculty.id)
    )
    rows = list(db.scalars(query))
    media.load({m.photo_media_id for m in rows if m.photo_media_id})
    out = []
    for member in rows:
        if department and member.department.slug != department:
            continue
        item: dict[str, Any] = {
            "id": member.id,
            "name": member.name,
            "designation": member.designation,
            "qualification": member.qualification,
            "department": member.department.name,
            "departmentKey": member.department.slug,
        }
        if member.photo_media_id:
            try:
                item["photo"] = media.ref(member.photo_media_id)
            except MissingMedia as error:
                log.warning("faculty %s: photo skipped (%s)", member.id, error)
        out.append(item)
    return out


# ---- news ----


def _published_news():
    return (
        select(News)
        .where(News.status == PublishStatus.PUBLISHED.value, News.published_at <= func.now())
        .options(selectinload(News.attachments))
        .order_by(News.is_pinned.desc(), News.published_at.desc(), News.id.desc())
    )


def _news(item: News, media: MediaLookup) -> dict[str, Any]:
    attachments = []
    for attachment in item.attachments:
        try:
            attachments.append({"title": attachment.label, "href": media.url(attachment.media_id)})
        except MissingMedia as error:
            log.warning("news %s: attachment skipped (%s)", item.slug, error)
    out: dict[str, Any] = {
        "slug": item.slug,
        "title": item.title,
        "category": CATEGORY_LABELS[item.category],  # type: ignore[index]
        "publishedAt": _day(item.published_at),
        "summary": item.summary,
        "body": item.body,
        "pinned": item.is_pinned or None,
        "attachments": attachments,
    }
    if item.cover_media_id:
        try:
            out["cover"] = media.ref(item.cover_media_id)
        except MissingMedia as error:
            log.warning("news %s: cover skipped (%s)", item.slug, error)
    return out


def _load_news_media(rows: list[News], media: MediaLookup) -> None:
    ids = {n.cover_media_id for n in rows if n.cover_media_id}
    ids |= {a.media_id for n in rows for a in n.attachments}
    media.load(ids)


def list_news(
    db: Session, media: MediaLookup, *, category: str | None, limit: int
) -> list[dict[str, Any]]:
    query = _published_news()
    if category:
        query = query.where(News.category == category)
    rows = list(db.scalars(query.limit(limit)))
    _load_news_media(rows, media)
    return [_news(n, media) for n in rows]


def get_news_item(db: Session, media: MediaLookup, slug: str) -> dict[str, Any] | None:
    item = db.scalar(_published_news().where(News.slug == slug))
    if not item:
        return None
    _load_news_media([item], media)
    return _news(item, media)


# ---- activities and gallery ----


def list_activities(
    db: Session, media: MediaLookup, *, group: str | None, home: bool | None, limit: int | None
) -> list[dict[str, Any]]:
    query = (
        select(Activity)
        .where(Activity.status == PublishStatus.PUBLISHED.value)
        .options(selectinload(Activity.photos))
        .order_by(Activity.sort_order, Activity.id)
    )
    if group:
        query = query.where(Activity.group == group)
    if home:
        query = query.where(Activity.show_on_home.is_(True))
    if limit:
        query = query.limit(limit)
    rows = list(db.scalars(query))
    ids = {a.cover_media_id for a in rows if a.cover_media_id}
    ids |= {p.media_id for a in rows for p in a.photos}
    media.load(ids)

    out = []
    for activity in rows:
        try:
            photos = [
                {"media": media.ref(p.media_id), "caption": p.caption} for p in activity.photos
            ]
            cover_id = activity.cover_media_id or (activity.photos[0].media_id if photos else None)
            if cover_id is None:
                raise MissingMedia("no cover photo")
            cover = media.ref(cover_id)
        except MissingMedia as error:
            log.warning("activity %s skipped (%s)", activity.slug, error)
            continue
        out.append(
            {
                "slug": activity.slug,
                "group": GROUP_LABELS[activity.group],  # type: ignore[index]
                "groupKey": activity.group,
                "year": str(activity.year) if activity.year else None,
                "title": activity.title,
                "summary": activity.summary,
                "cover": cover,
                "photos": photos,
            }
        )
    return out


def list_gallery(db: Session, media: MediaLookup, category: str | None) -> list[dict[str, Any]]:
    query = (
        select(GalleryItem)
        .where(GalleryItem.is_published.is_(True), GalleryItem.kind == "photo")
        .order_by(GalleryItem.sort_order, GalleryItem.id)
    )
    if category:
        query = query.where(GalleryItem.category == category)
    rows = list(db.scalars(query))
    media.load({g.media_id for g in rows if g.media_id})
    out = []
    for item in rows:
        try:
            out.append(
                {
                    "id": item.id,
                    "media": media.ref(item.media_id),  # type: ignore[arg-type]
                    "caption": item.caption,
                    "category": item.category,
                    "categoryLabel": GALLERY_LABELS[item.category],  # type: ignore[index]
                }
            )
        except MissingMedia as error:
            log.warning("gallery item %s skipped (%s)", item.id, error)
    return out
