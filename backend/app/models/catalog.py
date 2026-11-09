from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    ForeignKey,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, TimestampMixin, slug_check


class Department(IdMixin, TimestampMixin, Base):
    __tablename__ = "departments"
    __table_args__ = (slug_check(),)

    name: Mapped[str] = mapped_column(String(120))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))


class Course(IdMixin, TimestampMixin, Base):
    __tablename__ = "courses"
    __table_args__ = (
        slug_check(),
        CheckConstraint("duration_years BETWEEN 1 AND 6", name="duration_range"),
    )

    # a department cannot be deleted while it still has courses
    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    # short label for the tab on the courses page
    tab: Mapped[str] = mapped_column(String(40))
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    duration_years: Mapped[int]
    affiliation: Mapped[str | None] = mapped_column(String(200))
    summary: Mapped[str] = mapped_column(String(400))
    # rich text (restricted editor JSON), never HTML
    description: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    subjects: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    eligibility: Mapped[str | None] = mapped_column(String(500))
    seats: Mapped[str | None] = mapped_column(String(40))
    fees: Mapped[str | None] = mapped_column(String(120))
    syllabus_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    cover_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    is_published: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    seo_title: Mapped[str | None] = mapped_column(String(120))
    seo_description: Mapped[str | None] = mapped_column(String(300))

    department: Mapped[Department] = relationship()


class Faculty(IdMixin, TimestampMixin, Base):
    """A teacher shown on the Faculty page. No phone or email is stored here on purpose."""

    __tablename__ = "faculty"

    department_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("departments.id", ondelete="RESTRICT"), index=True
    )
    name: Mapped[str] = mapped_column(String(120))
    designation: Mapped[str] = mapped_column(String(120))
    qualification: Mapped[str] = mapped_column(String(200))
    photo_media_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("media.id", ondelete="RESTRICT")
    )
    bio: Mapped[str | None] = mapped_column(String(1000))
    sort_order: Mapped[int] = mapped_column(server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))

    department: Mapped[Department] = relationship()
