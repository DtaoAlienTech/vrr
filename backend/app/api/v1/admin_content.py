"""Staff endpoints for the content lists: news, activities, gallery, departments, courses and
faculty. Every change is checked by the strict schemas, recorded in the audit log, and the website
is told which cached pages to refresh. News and activities also keep a history for undo."""

from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from app.api.deps import DbSession, Staff, SuperAdmin
from app.core.errors import ApiError
from app.models import (
    Activity,
    ActivityPhoto,
    Course,
    Department,
    Faculty,
    GalleryItem,
    News,
    NewsAttachment,
)
from app.models.enums import MediaKind, PublishStatus, RevisionAction
from app.schemas.admin import (
    ActivityAdminOut,
    ActivityIn,
    CourseAdminOut,
    CourseIn,
    DepartmentAdminOut,
    DepartmentIn,
    FacultyAdminOut,
    FacultyIn,
    GalleryAdminOut,
    GalleryIn,
    NewsAdminOut,
    NewsIn,
    ReorderIn,
)
from app.services import admin_ops as ops
from app.services.admin_ops import MediaBriefs
from app.services.auth import Auth
from app.services.revisions import restorer

router = APIRouter(prefix="/admin", tags=["admin content"])

Limit = Annotated[int, Query(ge=1, le=200)]
Offset = Annotated[int, Query(ge=0, le=100000)]
Search = Annotated[str | None, Query(max_length=100)]
IMAGE, PDF = MediaKind.IMAGE, MediaKind.PDF


def _not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"That {what} does not exist.")


def _iso(moment: datetime) -> str:
    return moment.isoformat()


def _clean(data: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in data.items() if value is not None}


# =========================== news ===========================


def news_snapshot(row: News) -> dict[str, Any]:
    """The news item in the same shape the API accepts, so any saved version can be put back."""
    return _clean(
        {
            "title": row.title,
            "slug": row.slug,
            "category": row.category,
            "summary": row.summary,
            "body": row.body,
            "coverMediaId": row.cover_media_id,
            "publishedAt": _iso(row.published_at),
            "isPinned": row.is_pinned,
            "status": row.status,
            "seoTitle": row.seo_title,
            "seoDescription": row.seo_description,
            "attachments": [{"mediaId": a.media_id, "label": a.label} for a in row.attachments],
        }
    )


def _news_out(row: News, briefs: MediaBriefs) -> dict[str, Any]:
    return {
        "id": row.id, "title": row.title, "slug": row.slug, "category": row.category,
        "summary": row.summary, "body": row.body, "cover_media": briefs.get(row.cover_media_id),
        "published_at": row.published_at, "is_pinned": row.is_pinned, "status": row.status,
        "seo_title": row.seo_title, "seo_description": row.seo_description,
        "attachments": [
            {"media": briefs.get(a.media_id), "label": a.label} for a in row.attachments
        ],
        "created_at": row.created_at, "updated_at": row.updated_at,
    }  # fmt: skip


def _news_briefs(db: Session, rows: list[News]) -> MediaBriefs:
    ids = {r.cover_media_id for r in rows} | {a.media_id for r in rows for a in r.attachments}
    return MediaBriefs(db).load(ids)


def _save_news(db: Session, auth: Auth, row: News | None, data: NewsIn) -> News:
    ops.ensure_media(db, [data.cover_media_id], kind=IMAGE, what="The cover")
    ops.ensure_media(db, [a.media_id for a in data.attachments], kind=PDF, what="Attachments")
    creating = row is None
    item = row or News()
    old_slug, was_public = item.slug, item.status == PublishStatus.PUBLISHED.value
    item.slug = ops.choose_slug(
        db, News, wanted=data.slug, title=data.title, current=item.slug, row_id=item.id
    )
    item.title, item.category, item.summary, item.body = (
        data.title, data.category.value, data.summary, data.body,
    )  # fmt: skip
    item.cover_media_id = data.cover_media_id
    item.published_at = data.published_at or item.published_at or datetime.now(UTC)
    item.is_pinned, item.status = data.is_pinned, data.status.value
    item.seo_title, item.seo_description = data.seo_title, data.seo_description
    item.attachments = [
        NewsAttachment(media_id=a.media_id, label=a.label, sort_order=position)
        for position, a in enumerate(data.attachments)
    ]
    if creating:
        db.add(item)
    ops.flush_or_conflict(db)
    if not creating and was_public and old_slug != item.slug:
        ops.add_redirect(db, f"/news/{old_slug}", f"/news/{item.slug}", auth.user.id)
    return item


def _get_news(db: Session, news_id: int) -> News:
    row = db.scalar(select(News).where(News.id == news_id).options(selectinload(News.attachments)))
    if row is None:
        raise _not_found("news item")
    return row


@router.get("/news", response_model=list[NewsAdminOut])
def list_news(
    _: Staff,
    db: DbSession,
    status_filter: Annotated[PublishStatus | None, Query(alias="status")] = None,
    q: Search = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    query = select(News).options(selectinload(News.attachments))
    if status_filter:
        query = query.where(News.status == status_filter.value)
    if q and q.strip():
        query = query.where(News.title.ilike(ops.like_pattern(q), escape="\\"))
    rows = list(
        db.scalars(
            query.order_by(News.is_pinned.desc(), News.published_at.desc(), News.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    briefs = _news_briefs(db, rows)
    return [_news_out(row, briefs) for row in rows]


@router.get("/news/{news_id}", response_model=NewsAdminOut)
def read_news(news_id: int, _: Staff, db: DbSession):
    row = _get_news(db, news_id)
    return _news_out(row, _news_briefs(db, [row]))


@router.post("/news", status_code=status.HTTP_201_CREATED, response_model=NewsAdminOut)
def create_news(data: NewsIn, request: Request, auth: Staff, db: DbSession):
    row = _save_news(db, auth, None, data)
    ops.save_revision(
        db, entity="news", entity_id=row.id, data=news_snapshot(row),
        action=RevisionAction.CREATE, user_id=auth.user.id,
    )  # fmt: skip
    ops.finish(db, request, auth, action="news_create", entity="news",
               entity_id=row.id, tags=["news"])  # fmt: skip
    return _news_out(row, _news_briefs(db, [row]))


@router.put("/news/{news_id}", response_model=NewsAdminOut)
def update_news(
    news_id: int,
    data: NewsIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _get_news(db, news_id)
    before = news_snapshot(row)
    row = _save_news(db, auth, row, data)
    after = news_snapshot(row)
    ops.save_revision(
        db, entity="news", entity_id=row.id, data=after, action=RevisionAction.UPDATE,
        user_id=auth.user.id, baseline=before,
    )  # fmt: skip
    fields = sorted(
        key for key in after.keys() | before.keys() if after.get(key) != before.get(key)
    )
    ops.finish(db, request, auth, action="news_update", entity="news",
               entity_id=row.id, tags=["news"], changes={"fields": fields})  # fmt: skip
    return _news_out(row, _news_briefs(db, [row]))


@router.delete("/news/{news_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_news(news_id: int, request: Request, auth: Staff, db: DbSession):
    row = _get_news(db, news_id)
    ops.save_revision(
        db, entity="news", entity_id=row.id, data=news_snapshot(row),
        action=RevisionAction.DELETE, user_id=auth.user.id,
    )  # fmt: skip
    db.delete(row)
    ops.finish(db, request, auth, action="news_delete", entity="news",
               entity_id=news_id, tags=["news"])  # fmt: skip


@restorer("news")
def restore_news(db: Session, auth: Auth, entity_id: int, data: dict[str, Any]) -> int:
    row = db.scalar(
        select(News).where(News.id == entity_id).options(selectinload(News.attachments))
    )
    item = _save_news(db, auth, row, NewsIn.model_validate(data))
    return item.id


# ========================= activities =========================


def activity_snapshot(row: Activity) -> dict[str, Any]:
    return _clean(
        {
            "title": row.title,
            "slug": row.slug,
            "group": row.group,
            "year": row.year,
            "summary": row.summary,
            "coverMediaId": row.cover_media_id,
            "showOnHome": row.show_on_home,
            "status": row.status,
            "sortOrder": row.sort_order,
            "photos": [_clean({"mediaId": p.media_id, "caption": p.caption}) for p in row.photos],
        }
    )


def _activity_out(row: Activity, briefs: MediaBriefs) -> dict[str, Any]:
    return {
        "id": row.id, "title": row.title, "slug": row.slug, "group": row.group, "year": row.year,
        "summary": row.summary, "cover_media": briefs.get(row.cover_media_id),
        "show_on_home": row.show_on_home, "status": row.status, "sort_order": row.sort_order,
        "photos": [{"media": briefs.get(p.media_id), "caption": p.caption} for p in row.photos],
        "created_at": row.created_at, "updated_at": row.updated_at,
    }  # fmt: skip


def _activity_briefs(db: Session, rows: list[Activity]) -> MediaBriefs:
    ids = {r.cover_media_id for r in rows} | {p.media_id for r in rows for p in r.photos}
    return MediaBriefs(db).load(ids)


def _save_activity(db: Session, row: Activity | None, data: ActivityIn) -> Activity:
    ops.ensure_media(
        db, [data.cover_media_id, *(p.media_id for p in data.photos)], kind=IMAGE, what="Photos"
    )
    creating = row is None
    item = row or Activity()
    item.slug = ops.choose_slug(
        db, Activity, wanted=data.slug, title=data.title, current=item.slug, row_id=item.id
    )
    item.title, item.group, item.year = data.title, data.group.value, data.year
    item.summary, item.cover_media_id = data.summary, data.cover_media_id
    item.show_on_home, item.status, item.sort_order = (
        data.show_on_home, data.status.value, data.sort_order,
    )  # fmt: skip
    item.photos = [
        ActivityPhoto(media_id=p.media_id, caption=p.caption, sort_order=position)
        for position, p in enumerate(data.photos)
    ]
    if creating:
        db.add(item)
    ops.flush_or_conflict(db)
    return item


def _get_activity(db: Session, activity_id: int) -> Activity:
    row = db.scalar(
        select(Activity).where(Activity.id == activity_id).options(selectinload(Activity.photos))
    )
    if row is None:
        raise _not_found("activity")
    return row


@router.get("/activities", response_model=list[ActivityAdminOut])
def list_activities(
    _: Staff,
    db: DbSession,
    status_filter: Annotated[PublishStatus | None, Query(alias="status")] = None,
    limit: Limit = 100,
    offset: Offset = 0,
):
    query = select(Activity).options(selectinload(Activity.photos))
    if status_filter:
        query = query.where(Activity.status == status_filter.value)
    rows = list(
        db.scalars(query.order_by(Activity.sort_order, Activity.id).limit(limit).offset(offset))
    )
    briefs = _activity_briefs(db, rows)
    return [_activity_out(row, briefs) for row in rows]


@router.post("/activities/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_activities(data: ReorderIn, request: Request, auth: Staff, db: DbSession):
    ops.reorder(db, Activity, data.ids)
    ops.finish(db, request, auth, action="activity_reorder", entity="activity",
               entity_id=None, tags=["activities"])  # fmt: skip


@router.get("/activities/{activity_id}", response_model=ActivityAdminOut)
def read_activity(activity_id: int, _: Staff, db: DbSession):
    row = _get_activity(db, activity_id)
    return _activity_out(row, _activity_briefs(db, [row]))


@router.post("/activities", status_code=status.HTTP_201_CREATED, response_model=ActivityAdminOut)
def create_activity(data: ActivityIn, request: Request, auth: Staff, db: DbSession):
    row = _save_activity(db, None, data)
    ops.save_revision(
        db, entity="activity", entity_id=row.id, data=activity_snapshot(row),
        action=RevisionAction.CREATE, user_id=auth.user.id,
    )  # fmt: skip
    ops.finish(db, request, auth, action="activity_create", entity="activity",
               entity_id=row.id, tags=["activities"])  # fmt: skip
    return _activity_out(row, _activity_briefs(db, [row]))


@router.put("/activities/{activity_id}", response_model=ActivityAdminOut)
def update_activity(
    activity_id: int,
    data: ActivityIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _get_activity(db, activity_id)
    before = activity_snapshot(row)
    row = _save_activity(db, row, data)
    after = activity_snapshot(row)
    ops.save_revision(
        db, entity="activity", entity_id=row.id, data=after, action=RevisionAction.UPDATE,
        user_id=auth.user.id, baseline=before,
    )  # fmt: skip
    fields = sorted(
        key for key in after.keys() | before.keys() if after.get(key) != before.get(key)
    )
    ops.finish(db, request, auth, action="activity_update", entity="activity",
               entity_id=row.id, tags=["activities"], changes={"fields": fields})  # fmt: skip
    return _activity_out(row, _activity_briefs(db, [row]))


@router.delete("/activities/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_activity(activity_id: int, request: Request, auth: Staff, db: DbSession):
    row = _get_activity(db, activity_id)
    ops.save_revision(
        db, entity="activity", entity_id=row.id, data=activity_snapshot(row),
        action=RevisionAction.DELETE, user_id=auth.user.id,
    )  # fmt: skip
    db.delete(row)
    ops.finish(db, request, auth, action="activity_delete", entity="activity",
               entity_id=activity_id, tags=["activities"])  # fmt: skip


@restorer("activity")
def restore_activity(db: Session, auth: Auth, entity_id: int, data: dict[str, Any]) -> int:
    row = db.scalar(
        select(Activity).where(Activity.id == entity_id).options(selectinload(Activity.photos))
    )
    return _save_activity(db, row, ActivityIn.model_validate(data)).id


# ============================ gallery ============================


def _gallery_out(row: GalleryItem, briefs: MediaBriefs) -> dict[str, Any]:
    return {
        "id": row.id, "kind": row.kind, "media": briefs.get(row.media_id),
        "youtube_id": row.youtube_id, "category": row.category, "caption": row.caption,
        "sort_order": row.sort_order, "is_published": row.is_published,
    }  # fmt: skip


def _save_gallery(db: Session, row: GalleryItem | None, data: GalleryIn) -> GalleryItem:
    ops.ensure_media(db, [data.media_id], kind=IMAGE, what="The photo")
    item = row or GalleryItem()
    item.kind, item.media_id, item.youtube_id = data.kind.value, data.media_id, data.youtube_id
    item.category, item.caption = data.category.value, data.caption
    item.sort_order, item.is_published = data.sort_order, data.is_published
    if row is None:
        db.add(item)
    ops.flush_or_conflict(db)
    return item


def _get_gallery(db: Session, item_id: int) -> GalleryItem:
    row = db.get(GalleryItem, item_id)
    if row is None:
        raise _not_found("gallery item")
    return row


@router.get("/gallery", response_model=list[GalleryAdminOut])
def list_gallery(
    _: Staff,
    db: DbSession,
    category: str | None = Query(default=None, max_length=20),
    limit: Limit = 200,
    offset: Offset = 0,
):
    query = select(GalleryItem)
    if category:
        query = query.where(GalleryItem.category == category)
    rows = list(
        db.scalars(
            query.order_by(GalleryItem.sort_order, GalleryItem.id).limit(limit).offset(offset)
        )
    )
    briefs = MediaBriefs(db).load(r.media_id for r in rows)
    return [_gallery_out(row, briefs) for row in rows]


@router.post("/gallery/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_gallery(data: ReorderIn, request: Request, auth: Staff, db: DbSession):
    ops.reorder(db, GalleryItem, data.ids)
    ops.finish(db, request, auth, action="gallery_reorder", entity="gallery_item",
               entity_id=None, tags=["gallery"])  # fmt: skip


@router.get("/gallery/{item_id}", response_model=GalleryAdminOut)
def read_gallery_item(item_id: int, _: Staff, db: DbSession):
    row = _get_gallery(db, item_id)
    return _gallery_out(row, MediaBriefs(db).load([row.media_id]))


@router.post("/gallery", status_code=status.HTTP_201_CREATED, response_model=GalleryAdminOut)
def create_gallery_item(data: GalleryIn, request: Request, auth: Staff, db: DbSession):
    row = _save_gallery(db, None, data)
    ops.finish(db, request, auth, action="gallery_create", entity="gallery_item",
               entity_id=row.id, tags=["gallery"])  # fmt: skip
    return _gallery_out(row, MediaBriefs(db).load([row.media_id]))


@router.put("/gallery/{item_id}", response_model=GalleryAdminOut)
def update_gallery_item(
    item_id: int,
    data: GalleryIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _save_gallery(db, _get_gallery(db, item_id), data)
    ops.finish(db, request, auth, action="gallery_update", entity="gallery_item",
               entity_id=row.id, tags=["gallery"])  # fmt: skip
    return _gallery_out(row, MediaBriefs(db).load([row.media_id]))


@router.delete("/gallery/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gallery_item(item_id: int, request: Request, auth: Staff, db: DbSession):
    db.delete(_get_gallery(db, item_id))  # (the photo itself stays in the media library)
    ops.finish(db, request, auth, action="gallery_delete", entity="gallery_item",
               entity_id=item_id, tags=["gallery"])  # fmt: skip


# ========================== departments ==========================

DEPARTMENT_TAGS = ["courses", "faculty"]  # both show the department's name


def _department_out(row: Department) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "slug": row.slug,
            "description": row.description, "sort_order": row.sort_order}  # fmt: skip


def _get_department(db: Session, department_id: int) -> Department:
    row = db.get(Department, department_id)
    if row is None:
        raise _not_found("department")
    return row


def _save_department(db: Session, row: Department | None, data: DepartmentIn) -> Department:
    item = row or Department()
    item.slug = ops.choose_slug(
        db, Department, wanted=data.slug, title=data.name, current=item.slug, row_id=item.id
    )
    item.name, item.description, item.sort_order = data.name, data.description, data.sort_order
    if row is None:
        db.add(item)
    ops.flush_or_conflict(db)
    return item


@router.get("/departments", response_model=list[DepartmentAdminOut])
def list_departments(_: Staff, db: DbSession):
    rows = db.scalars(select(Department).order_by(Department.sort_order, Department.id))
    return [_department_out(row) for row in rows]


@router.post("/departments/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_departments(data: ReorderIn, request: Request, auth: Staff, db: DbSession):
    ops.reorder(db, Department, data.ids)
    ops.finish(db, request, auth, action="department_reorder", entity="department",
               entity_id=None, tags=DEPARTMENT_TAGS)  # fmt: skip


@router.get("/departments/{department_id}", response_model=DepartmentAdminOut)
def read_department(department_id: int, _: Staff, db: DbSession):
    return _department_out(_get_department(db, department_id))


@router.post("/departments", status_code=status.HTTP_201_CREATED, response_model=DepartmentAdminOut)
def create_department(
    data: DepartmentIn,
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
):
    row = _save_department(db, None, data)
    ops.finish(db, request, auth, action="department_create", entity="department",
               entity_id=row.id, tags=DEPARTMENT_TAGS)  # fmt: skip
    return _department_out(row)


@router.put("/departments/{department_id}", response_model=DepartmentAdminOut)
def update_department(
    department_id: int,
    data: DepartmentIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _save_department(db, _get_department(db, department_id), data)
    ops.finish(db, request, auth, action="department_update", entity="department",
               entity_id=row.id, tags=DEPARTMENT_TAGS)  # fmt: skip
    return _department_out(row)


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(
    department_id: int,
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
):
    row = _get_department(db, department_id)
    courses = db.scalar(select(func.count()).where(Course.department_id == row.id)) or 0
    people = db.scalar(select(func.count()).where(Faculty.department_id == row.id)) or 0
    if courses or people:
        raise ApiError(
            409, "department_in_use",
            f"This department still has {courses} course(s) and {people} faculty member(s).",
        )  # fmt: skip
    db.delete(row)
    ops.finish(db, request, auth, action="department_delete", entity="department",
               entity_id=department_id, tags=DEPARTMENT_TAGS)  # fmt: skip


# ============================ courses ============================


def _course_out(row: Course, briefs: MediaBriefs) -> dict[str, Any]:
    return {
        "id": row.id, "department_id": row.department_id, "department_name": row.department.name,
        "name": row.name, "tab": row.tab, "slug": row.slug, "duration_years": row.duration_years,
        "affiliation": row.affiliation, "summary": row.summary, "description": row.description,
        "subjects": row.subjects, "eligibility": row.eligibility, "seats": row.seats,
        "fees": row.fees, "syllabus": briefs.get(row.syllabus_media_id),
        "cover_media": briefs.get(row.cover_media_id), "sort_order": row.sort_order,
        "is_published": row.is_published, "seo_title": row.seo_title,
        "seo_description": row.seo_description,
    }  # fmt: skip


def _course_briefs(db: Session, rows: list[Course]) -> MediaBriefs:
    return MediaBriefs(db).load(
        {r.syllabus_media_id for r in rows} | {r.cover_media_id for r in rows}
    )


def _get_course(db: Session, course_id: int) -> Course:
    row = db.scalar(
        select(Course).where(Course.id == course_id).options(joinedload(Course.department))
    )
    if row is None:
        raise _not_found("course")
    return row


def _save_course(db: Session, auth: Auth, row: Course | None, data: CourseIn) -> Course:
    _get_department(db, data.department_id)
    ops.ensure_media(db, [data.syllabus_media_id], kind=PDF, what="The syllabus")
    ops.ensure_media(db, [data.cover_media_id], kind=IMAGE, what="The cover")
    item = row or Course()
    old_slug, was_public = item.slug, bool(item.is_published)
    item.slug = ops.choose_slug(
        db, Course, wanted=data.slug, title=data.name, current=item.slug, row_id=item.id
    )
    item.department_id, item.name, item.tab = data.department_id, data.name, data.tab
    item.duration_years, item.affiliation, item.summary = (
        data.duration_years, data.affiliation, data.summary,
    )  # fmt: skip
    item.description, item.subjects = data.description, data.subjects
    item.eligibility, item.seats, item.fees = data.eligibility, data.seats, data.fees
    item.syllabus_media_id, item.cover_media_id = data.syllabus_media_id, data.cover_media_id
    item.sort_order, item.is_published = data.sort_order, data.is_published
    item.seo_title, item.seo_description = data.seo_title, data.seo_description
    if row is None:
        db.add(item)
    ops.flush_or_conflict(db)
    db.refresh(item, ["department"])
    if row is not None and was_public and old_slug != item.slug:
        ops.add_redirect(db, f"/courses/{old_slug}", f"/courses/{item.slug}", auth.user.id)
    return item


@router.get("/courses", response_model=list[CourseAdminOut])
def list_courses(_: Staff, db: DbSession):
    rows = list(
        db.scalars(
            select(Course)
            .options(joinedload(Course.department))
            .order_by(Course.sort_order, Course.id)
        )
    )
    briefs = _course_briefs(db, rows)
    return [_course_out(row, briefs) for row in rows]


@router.post("/courses/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_courses(data: ReorderIn, request: Request, auth: Staff, db: DbSession):
    ops.reorder(db, Course, data.ids)
    ops.finish(db, request, auth, action="course_reorder", entity="course",
               entity_id=None, tags=["courses"])  # fmt: skip


@router.get("/courses/{course_id}", response_model=CourseAdminOut)
def read_course(course_id: int, _: Staff, db: DbSession):
    row = _get_course(db, course_id)
    return _course_out(row, _course_briefs(db, [row]))


@router.post("/courses", status_code=status.HTTP_201_CREATED, response_model=CourseAdminOut)
def create_course(data: CourseIn, request: Request, auth: SuperAdmin, db: DbSession):
    row = _save_course(db, auth, None, data)
    ops.finish(db, request, auth, action="course_create", entity="course",
               entity_id=row.id, tags=["courses"])  # fmt: skip
    return _course_out(row, _course_briefs(db, [row]))


@router.put("/courses/{course_id}", response_model=CourseAdminOut)
def update_course(
    course_id: int,
    data: CourseIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _save_course(db, auth, _get_course(db, course_id), data)
    ops.finish(db, request, auth, action="course_update", entity="course",
               entity_id=row.id, tags=["courses"])  # fmt: skip
    return _course_out(row, _course_briefs(db, [row]))


@router.delete("/courses/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_course(course_id: int, request: Request, auth: SuperAdmin, db: DbSession):
    db.delete(_get_course(db, course_id))
    ops.finish(db, request, auth, action="course_delete", entity="course",
               entity_id=course_id, tags=["courses"])  # fmt: skip


# ============================ faculty ============================


def _faculty_out(row: Faculty, briefs: MediaBriefs) -> dict[str, Any]:
    return {
        "id": row.id, "department_id": row.department_id, "department_name": row.department.name,
        "name": row.name, "designation": row.designation, "qualification": row.qualification,
        "photo": briefs.get(row.photo_media_id), "bio": row.bio, "sort_order": row.sort_order,
        "is_active": row.is_active,
    }  # fmt: skip


def _get_faculty(db: Session, member_id: int) -> Faculty:
    row = db.scalar(
        select(Faculty).where(Faculty.id == member_id).options(joinedload(Faculty.department))
    )
    if row is None:
        raise _not_found("faculty member")
    return row


def _save_faculty(db: Session, row: Faculty | None, data: FacultyIn) -> Faculty:
    _get_department(db, data.department_id)
    ops.ensure_media(db, [data.photo_media_id], kind=IMAGE, what="The photo")
    item = row or Faculty()
    item.department_id, item.name = data.department_id, data.name
    item.designation, item.qualification = data.designation, data.qualification
    item.photo_media_id, item.bio = data.photo_media_id, data.bio
    item.sort_order, item.is_active = data.sort_order, data.is_active
    if row is None:
        db.add(item)
    ops.flush_or_conflict(db)
    db.refresh(item, ["department"])
    return item


@router.get("/faculty", response_model=list[FacultyAdminOut])
def list_faculty(_: Staff, db: DbSession, limit: Limit = 200, offset: Offset = 0):
    rows = list(
        db.scalars(
            select(Faculty)
            .options(joinedload(Faculty.department))
            .order_by(Faculty.sort_order, Faculty.id)
            .limit(limit)
            .offset(offset)
        )
    )
    briefs = MediaBriefs(db).load(r.photo_media_id for r in rows)
    return [_faculty_out(row, briefs) for row in rows]


@router.post("/faculty/reorder", status_code=status.HTTP_204_NO_CONTENT)
def reorder_faculty(data: ReorderIn, request: Request, auth: Staff, db: DbSession):
    ops.reorder(db, Faculty, data.ids)
    ops.finish(db, request, auth, action="faculty_reorder", entity="faculty",
               entity_id=None, tags=["faculty"])  # fmt: skip


@router.get("/faculty/{member_id}", response_model=FacultyAdminOut)
def read_faculty_member(member_id: int, _: Staff, db: DbSession):
    row = _get_faculty(db, member_id)
    return _faculty_out(row, MediaBriefs(db).load([row.photo_media_id]))


@router.post("/faculty", status_code=status.HTTP_201_CREATED, response_model=FacultyAdminOut)
def create_faculty_member(data: FacultyIn, request: Request, auth: Staff, db: DbSession):
    row = _save_faculty(db, None, data)
    ops.finish(db, request, auth, action="faculty_create", entity="faculty",
               entity_id=row.id, tags=["faculty"])  # fmt: skip
    return _faculty_out(row, MediaBriefs(db).load([row.photo_media_id]))


@router.put("/faculty/{member_id}", response_model=FacultyAdminOut)
def update_faculty_member(
    member_id: int,
    data: FacultyIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = _save_faculty(db, _get_faculty(db, member_id), data)
    ops.finish(db, request, auth, action="faculty_update", entity="faculty",
               entity_id=row.id, tags=["faculty"])  # fmt: skip
    return _faculty_out(row, MediaBriefs(db).load([row.photo_media_id]))


@router.delete("/faculty/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_faculty_member(member_id: int, request: Request, auth: Staff, db: DbSession):
    db.delete(_get_faculty(db, member_id))
    ops.finish(db, request, auth, action="faculty_delete", entity="faculty",
               entity_id=member_id, tags=["faculty"])  # fmt: skip
