from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    String,
    desc,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Enquiry(TimestampMixin, Base):
    """A message sent through the website enquiry form. Only what the college needs is stored."""

    __tablename__ = "enquiries"
    __table_args__ = (
        CheckConstraint("status IN ('new', 'contacted', 'closed')", name="status_valid"),
        Index("ix_enquiries_status_created_at", "status", desc("created_at")),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    name: Mapped[str] = mapped_column(String(80))
    phone: Mapped[str] = mapped_column(String(10))
    course: Mapped[str | None] = mapped_column(String(120))
    message: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(20), server_default="new")
    source_page: Mapped[str | None] = mapped_column(String(200))
    # Keyed hash of the visitor's IP address (never the address itself), used for rate limiting.
    ip_hash: Mapped[str] = mapped_column(String(64), index=True)
    # Who last changed the status, and when.
    handled_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
