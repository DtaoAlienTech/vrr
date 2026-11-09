from datetime import datetime
from enum import StrEnum

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Identity, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# Stable constraint names make Alembic migrations predictable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    """created_at / updated_at (UTC) for every table that needs them."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class IdMixin:
    """Bigint identity primary key."""

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)


def check_in(column: str, values: type[StrEnum], name: str | None = None) -> CheckConstraint:
    """CHECK constraint limiting a text column to the values of an enum (see enums.py)."""
    allowed = ", ".join(f"'{value.value}'" for value in values)
    return CheckConstraint(f"{column} IN ({allowed})", name=name or f"{column}_valid")


# lower-case words joined by single hyphens: safe to use in a URL
SLUG_REGEX = "^[a-z0-9]+(-[a-z0-9]+)*$"


def slug_check(column: str = "slug", *, allow_empty: bool = False) -> CheckConstraint:
    rule = f"{column} ~ '{SLUG_REGEX}'"
    if allow_empty:
        rule = f"{column} = '' OR {rule}"
    return CheckConstraint(rule, name=f"{column}_format")
