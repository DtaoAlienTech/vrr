"""Draft preview. An editor asks for a link (staff only); the link holds a signed, 30-minute token
that opens exactly one page or news item, for reading, on the real website layout."""

from typing import Literal

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, Staff
from app.api.v1.content import Media, not_found
from app.core.config import get_settings
from app.core.security import create_preview_token, read_preview_token
from app.models import News, Page
from app.schemas.common import CamelModel, Id
from app.schemas.public import NewsOut, Out, PageOut
from app.services import public_content as content

router = APIRouter(tags=["preview"])


def never_cached(response: Response) -> None:
    """A draft must not be stored by browsers, CDNs or search engines."""
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    response.headers["Referrer-Policy"] = "no-referrer"


class PreviewLinkIn(CamelModel):
    kind: Literal["page", "news"]
    id: Id


class PreviewLinkOut(Out):
    path: str
    expires_at: str


class PreviewOut(Out):
    kind: Literal["page", "news"]
    page: PageOut | None = None
    news: NewsOut | None = None


@router.post(
    "/admin/preview-links",
    status_code=status.HTTP_201_CREATED,
    response_model=PreviewLinkOut,
    dependencies=[Depends(never_cached)],
)
def create_preview_link(data: PreviewLinkIn, _: Staff, db: DbSession):
    model = Page if data.kind == "page" else News
    if db.scalar(select(model.id).where(model.id == data.id)) is None:
        raise not_found()
    token, expires = create_preview_token(get_settings(), kind=data.kind, entity_id=data.id)
    return {"path": f"/preview/{token}", "expires_at": expires.isoformat()}


@router.get(
    "/preview/{token}",
    response_model=PreviewOut,
    response_model_exclude_none=True,
    dependencies=[Depends(never_cached)],
)
def read_preview(token: str, db: DbSession, media: Media):
    target = read_preview_token(get_settings(), token) if len(token) <= 200 else None
    if target is None:
        raise not_found()
    result = content.get_preview(db, media, *target)
    if result is None:
        raise not_found()
    return result
