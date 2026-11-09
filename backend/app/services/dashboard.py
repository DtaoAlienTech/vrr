"""The numbers and recent activity shown on the admin dashboard."""

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Activity, ContentRevision, Enquiry, Media, News, Page, SiteSetting, User
from app.models.enums import EnquiryStatus, PublishStatus

RECENT = 6


def _count(db: Session, model: Any, *conditions: Any) -> int:
    return db.scalar(select(func.count()).select_from(model).where(*conditions)) or 0


def titles(db: Session, entity: str, ids: set[int]) -> dict[int, str]:
    """A readable name for each changed item (a deleted item has none)."""
    if not ids:
        return {}
    if entity == "news":
        rows = db.execute(select(News.id, News.title).where(News.id.in_(ids)))
    elif entity == "activity":
        rows = db.execute(select(Activity.id, Activity.title).where(Activity.id.in_(ids)))
    elif entity == "page":
        rows = db.execute(select(Page.id, Page.title).where(Page.id.in_(ids)))
    elif entity == "settings":
        rows = db.execute(select(SiteSetting.id, SiteSetting.key).where(SiteSetting.id.in_(ids)))
    else:
        return {}
    return dict(rows.all())


def dashboard(db: Session) -> dict[str, Any]:
    published = PublishStatus.PUBLISHED.value
    draft = PublishStatus.DRAFT.value
    enquiries = db.scalars(select(Enquiry).order_by(Enquiry.id.desc()).limit(RECENT)).all()
    changes = db.execute(
        select(ContentRevision, User.name)
        .outerjoin(User, User.id == ContentRevision.user_id)
        .order_by(ContentRevision.id.desc())
        .limit(RECENT)
    ).all()
    wanted: dict[str, set[int]] = {}
    for revision, _ in changes:
        wanted.setdefault(revision.entity, set()).add(revision.entity_id)
    names = {entity: titles(db, entity, ids) for entity, ids in wanted.items()}
    return {
        "counts": {
            "newEnquiries": _count(db, Enquiry, Enquiry.status == EnquiryStatus.NEW.value),
            "publishedNews": _count(db, News, News.status == published),
            "draftNews": _count(db, News, News.status == draft),
            "publishedActivities": _count(db, Activity, Activity.status == published),
            "draftActivities": _count(db, Activity, Activity.status == draft),
            "media": _count(db, Media),
        },
        "recentEnquiries": [
            {
                "id": e.id,
                "name": e.name,
                "phone": e.phone,
                "course": e.course,
                "status": e.status,
                "createdAt": e.created_at,
            }
            for e in enquiries
        ],
        "recentChanges": [
            {
                "id": revision.id,
                "entity": revision.entity,
                "entityId": revision.entity_id,
                "action": revision.action,
                "label": names.get(revision.entity, {}).get(revision.entity_id),
                "userName": name,
                "createdAt": revision.created_at,
            }
            for revision, name in changes
        ],
    }
