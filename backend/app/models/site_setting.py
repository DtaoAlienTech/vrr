from typing import Any

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class SiteSetting(IdMixin, TimestampMixin, Base):
    """Site-wide settings, one row per group: brand, contact, social, menu, footer, seo."""

    __tablename__ = "site_settings"

    key: Mapped[str] = mapped_column(String(60), unique=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB)
    updated_by: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL")
    )
