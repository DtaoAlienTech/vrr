from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, desc, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, check_in, slug_check
from app.models.enums import NewsCategory, PublishStatus


class News(IdMixin, TimestampMixin, Base):
    """A notice, announcement or news item."""

    __tablename__ = "news"
    __table_args__ = (
        check_in("category", NewsCategory),
        check_in("status", PublishStatus),
        slug_check(),
        Index("ix_news_status_published_at", "status", desc("published_at")),
    )

    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    category: Mapped[str] = mapped_column(String(20))
    summary: Mapped[str] = mapped_column(String(400))
    # rich text (restricted editor JSON), never HTML
    body: Mapped[dict[str, Any]] = mapped_column(JSONB)
    cover_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_pinned: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), server_default=PublishStatus.DRAFT.value)
    seo_title: Mapped[str | None] = mapped_column(String(120))
    seo_description: Mapped[str | None] = mapped_column(String(300))

    attachments: Mapped[list["NewsAttachment"]] = relationship(
        order_by="NewsAttachment.sort_order", cascade="all, delete-orphan"
    )


class NewsAttachment(IdMixin, Base):
    """A PDF attached to a news item (a circular, a timetable)."""

    __tablename__ = "news_attachments"

    news_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("news.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("media.id", ondelete="RESTRICT"))
    label: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
