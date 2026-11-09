from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, check_in, slug_check
from app.models.enums import PageKey, PublishStatus


class Page(IdMixin, TimestampMixin, Base):
    """A page of the site: its address and SEO, plus an ordered list of sections."""

    __tablename__ = "pages"
    __table_args__ = (
        check_in("key", PageKey),
        check_in("status", PublishStatus),
        # "" is the home page; everything else is one lower-case word group
        slug_check(allow_empty=True),
    )

    key: Mapped[str] = mapped_column(String(30), unique=True)
    title: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    seo_title: Mapped[str | None] = mapped_column(String(120))
    seo_description: Mapped[str | None] = mapped_column(String(300))
    og_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    robots_noindex: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), server_default=PublishStatus.PUBLISHED.value)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sections: Mapped[list["PageSection"]] = relationship(
        back_populates="page", order_by="PageSection.position", cascade="all, delete-orphan"
    )


class PageSection(IdMixin, TimestampMixin, Base):
    """One block on a page. `data` is validated against the block's schema before every save."""

    __tablename__ = "page_sections"
    __table_args__ = (Index("ix_page_sections_page_id_position", "page_id", "position"),)

    page_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("pages.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(40))
    position: Mapped[int]
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    is_visible: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    page: Mapped[Page] = relationship(back_populates="sections")
