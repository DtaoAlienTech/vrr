from datetime import date

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, check_in, slug_check
from app.models.enums import ActivityGroup, PublishStatus


class Activity(IdMixin, TimestampMixin, Base):
    """A Leo Club, NSS, cultural or sports activity with its photos."""

    __tablename__ = "activities"
    __table_args__ = (
        # the column is named "group" (a reserved word in SQL), so the check is written out
        check_in('"group"', ActivityGroup, name="group_valid"),
        check_in("status", PublishStatus),
        slug_check(),
        Index("ix_activities_status_show_on_home", "status", "show_on_home"),
    )

    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    group: Mapped[str] = mapped_column(String(20))
    activity_date: Mapped[date | None] = mapped_column(Date)
    summary: Mapped[str] = mapped_column(String(500))
    cover_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    show_on_home: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    status: Mapped[str] = mapped_column(String(20), server_default=PublishStatus.DRAFT.value)
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))

    photos: Mapped[list["ActivityPhoto"]] = relationship(
        order_by="ActivityPhoto.sort_order", cascade="all, delete-orphan"
    )


class ActivityPhoto(IdMixin, Base):
    __tablename__ = "activity_photos"

    activity_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("activities.id", ondelete="CASCADE"), index=True
    )
    media_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("media.id", ondelete="RESTRICT"))
    caption: Mapped[str | None] = mapped_column(String(200))
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
