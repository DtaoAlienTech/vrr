"""Public, read-only content for the website. Only published content is ever returned."""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select

from app.api.deps import DbSession
from app.core.config import get_settings
from app.db.base import SLUG_REGEX
from app.models import Redirect
from app.models.enums import ActivityGroup, GalleryCategory, NewsCategory, PageKey
from app.schemas.public import (
    ActivityOut,
    CourseOut,
    FacultyOut,
    GalleryOut,
    NewsOut,
    PageOut,
    PageSummaryOut,
    RedirectPublicOut,
    SettingsOut,
)
from app.services import public_content as content


def cacheable(response: Response) -> None:
    """Shared caches (a CDN) may keep these answers briefly. The website has its own cache that
    the admin refreshes on every save, so this is only a safety net."""
    response.headers["Cache-Control"] = "public, max-age=30, stale-while-revalidate=300"


router = APIRouter(prefix="/public", tags=["public content"], dependencies=[Depends(cacheable)])

_SLUG = re.compile(SLUG_REGEX)
_PAGE_KEYS = {key.value for key in PageKey}


def not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "Not found")


def valid_slug(slug: str) -> str:
    """An address that cannot be a real slug (odd characters, too long) is simply "not found" and
    never reaches the database."""
    if len(slug) > 120 or not _SLUG.fullmatch(slug):
        raise not_found()
    return slug


def valid_page_key(key: str) -> str:
    if key not in _PAGE_KEYS:
        raise not_found()
    return key


def media_lookup(db: DbSession) -> content.MediaLookup:
    return content.MediaLookup(db, get_settings().uploads_url)


PathSlug = Annotated[str, Depends(valid_slug)]
PathPageKey = Annotated[str, Depends(valid_page_key)]
SlugFilter = Annotated[str, Query(max_length=80, pattern=SLUG_REGEX)]
Media = Annotated[content.MediaLookup, Depends(media_lookup)]


@router.get("/settings", response_model=SettingsOut, response_model_exclude_none=True)
def read_settings(db: DbSession, media: Media):
    settings = content.get_site_settings(db, media)
    if settings is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Site settings are not set up")
    return settings


@router.get("/pages", response_model=list[PageSummaryOut], response_model_exclude_none=True)
def read_pages(db: DbSession):
    return content.list_pages(db)


@router.get("/pages/by-slug/{slug}", response_model=PageOut, response_model_exclude_none=True)
def read_page_by_slug(slug: PathSlug, db: DbSession, media: Media):
    page = content.get_page(db, media, slug=slug)
    if page is None:
        raise not_found()
    return page


@router.get("/pages/{key}", response_model=PageOut, response_model_exclude_none=True)
def read_page(key: PathPageKey, db: DbSession, media: Media):
    page = content.get_page(db, media, key=key)
    if page is None:
        raise not_found()
    return page


@router.get("/courses", response_model=list[CourseOut], response_model_exclude_none=True)
def read_courses(db: DbSession, media: Media):
    return content.list_courses(db, media)


@router.get("/courses/{slug}", response_model=CourseOut, response_model_exclude_none=True)
def read_course(slug: PathSlug, db: DbSession, media: Media):
    course = content.get_course(db, media, slug)
    if course is None:
        raise not_found()
    return course


@router.get("/faculty", response_model=list[FacultyOut], response_model_exclude_none=True)
def read_faculty(db: DbSession, media: Media, department: SlugFilter | None = None):
    return content.list_faculty(db, media, department)


@router.get("/news", response_model=list[NewsOut], response_model_exclude_none=True)
def read_news(
    db: DbSession,
    media: Media,
    category: NewsCategory | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
):
    return content.list_news(db, media, category=category.value if category else None, limit=limit)


@router.get("/news/{slug}", response_model=NewsOut, response_model_exclude_none=True)
def read_news_item(slug: PathSlug, db: DbSession, media: Media):
    item = content.get_news_item(db, media, slug)
    if item is None:
        raise not_found()
    return item


@router.get("/activities", response_model=list[ActivityOut], response_model_exclude_none=True)
def read_activities(
    db: DbSession,
    media: Media,
    group: ActivityGroup | None = None,
    home: bool | None = None,
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
):
    return content.list_activities(
        db, media, group=group.value if group else None, home=home, limit=limit
    )


@router.get("/gallery", response_model=list[GalleryOut], response_model_exclude_none=True)
def read_gallery(db: DbSession, media: Media, category: GalleryCategory | None = None):
    return content.list_gallery(db, media, category.value if category else None)


@router.get("/redirects", response_model=list[RedirectPublicOut])
def read_redirects(db: DbSession):
    """Old address -> new address (made when a page, course or news item changes its address)."""
    rows = db.scalars(select(Redirect).order_by(Redirect.id).limit(2000))
    return [
        {"from_path": r.from_path, "to_path": r.to_path, "status_code": r.status_code} for r in rows
    ]
