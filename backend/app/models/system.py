from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    desc,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, check_in
from app.models.enums import RevisionAction

_LOCAL_PATH = "left({col}, 1) = '/' AND left({col}, 2) <> '//' AND position(chr(92) in {col}) = 0"


class Redirect(IdMixin, TimestampMixin, Base):
    """Old address to new address. Created automatically when a page or item changes its slug."""

    __tablename__ = "redirects"
    __table_args__ = (
        CheckConstraint("status_code IN (301, 302, 307, 308)", name="status_code_valid"),
        # site paths only: start with one "/", never "//" or a backslash (open-redirect tricks)
        CheckConstraint(_LOCAL_PATH.format(col="from_path"), name="from_path_is_local"),
        CheckConstraint(_LOCAL_PATH.format(col="to_path"), name="to_path_is_local"),
        CheckConstraint("from_path <> to_path", name="not_a_loop"),
    )

    from_path: Mapped[str] = mapped_column(String(300), unique=True)
    to_path: Mapped[str] = mapped_column(String(300))
    status_code: Mapped[int] = mapped_column(server_default="301")
    created_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )


class ContentRevision(IdMixin, Base):
    """Before/after copy of every change to pages, settings, news and activities, for rollback."""

    __tablename__ = "content_revisions"
    __table_args__ = (
        check_in("action", RevisionAction),
        Index("ix_content_revisions_entity", "entity", "entity_id", desc("created_at")),
    )

    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[int] = mapped_column(BigInteger)
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    action: Mapped[str] = mapped_column(String(20))
    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(IdMixin, Base):
    """Who did what, when, from where. Append-only."""

    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_log_created_at", desc("created_at")),)

    user_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(BigInteger)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    ip: Mapped[str | None] = mapped_column(String(45))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
