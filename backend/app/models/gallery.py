from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, check_in
from app.models.enums import GalleryCategory, GalleryKind


class GalleryItem(IdMixin, TimestampMixin, Base):
    """A photo (from the media library) or a YouTube video in the gallery."""

    __tablename__ = "gallery_items"
    __table_args__ = (
        check_in("kind", GalleryKind),
        check_in("category", GalleryCategory),
        # a photo needs an uploaded image; a video needs a YouTube id
        CheckConstraint(
            "(kind = 'photo' AND media_id IS NOT NULL)"
            " OR (kind = 'video' AND youtube_id IS NOT NULL)",
            name="has_content",
        ),
        CheckConstraint(
            "youtube_id IS NULL OR youtube_id ~ '^[A-Za-z0-9_-]{6,20}$'", name="youtube_id_format"
        ),
        Index("ix_gallery_items_category_sort_order", "category", "sort_order"),
    )

    kind: Mapped[str] = mapped_column(String(10), server_default=GalleryKind.PHOTO.value)
    media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    youtube_id: Mapped[str | None] = mapped_column(String(20))
    category: Mapped[str] = mapped_column(String(20), server_default=GalleryCategory.CAMPUS.value)
    caption: Mapped[str] = mapped_column(String(200), server_default="")
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
