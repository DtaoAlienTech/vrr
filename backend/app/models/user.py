from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin, check_in
from app.models.enums import Role


class User(IdMixin, TimestampMixin, Base):
    """An admin-panel account. Passwords are stored only as Argon2id hashes."""

    __tablename__ = "users"
    __table_args__ = (
        check_in("role", Role),
        CheckConstraint("email = lower(email)", name="email_lowercase"),
        CheckConstraint("failed_logins >= 0", name="failed_logins_not_negative"),
    )

    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), server_default=Role.EDITOR.value)
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    failed_logins: Mapped[int] = mapped_column(server_default=text("0"))
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Two-factor secret, stored encrypted (never in clear text).
    totp_secret: Mapped[str | None] = mapped_column(String(255))
    totp_enabled: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))


class UserSession(IdMixin, TimestampMixin, Base):
    """One login. Only a hash of the refresh token is stored, so a leaked database cannot log in."""

    __tablename__ = "sessions"

    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(45))
