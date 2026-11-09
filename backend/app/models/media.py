from typing import Any

from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, check_in
from app.models.enums import MediaKind


class Media(IdMixin, TimestampMixin, Base):
    """An uploaded photo or PDF. Content refers to it by id, so one upload is reused anywhere."""

    __tablename__ = "media"
    __table_args__ = (
        check_in("kind", MediaKind),
        CheckConstraint("size_bytes > 0", name="size_positive"),
        # NULL would slip past "width > 0", so the size must be present and positive
        CheckConstraint(
            "kind = 'pdf' OR"
            " (width IS NOT NULL AND height IS NOT NULL AND width > 0 AND height > 0)",
            name="image_has_size",
        ),
    )

    kind: Mapped[str] = mapped_column(String(10))
    original_filename: Mapped[str] = mapped_column(String(255))
    # Random name on disk (the visitor never sees the original name in a URL).
    stored_name: Mapped[str] = mapped_column(String(80), unique=True)
    mime: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    width: Mapped[int | None]
    height: Mapped[int | None]
    alt_text: Mapped[str] = mapped_column(String(300), server_default="")
    # Resized copies, for example [{"width": 800, "name": "ab12-800.webp"}].
    variants: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb")
    )
    # Hide a camera date stamp burned into the bottom edge of a photo.
    crop_bottom: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    uploaded_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
