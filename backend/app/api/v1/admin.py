"""Staff-only endpoints. Every route here needs a signed-in staff member (see deps.py)."""

from typing import Annotated, Any

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.api.deps import DbSession, Staff, SuperAdmin
from app.models import AuditLog, User
from app.schemas.auth import AdminUserOut, AuditEntryOut
from app.schemas.blocks import block_schemas

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/blocks/schema")
def blocks_schema(_: Staff) -> dict[str, dict[str, Any]]:
    """The section types and their JSON Schemas: the admin builds its edit forms from these."""
    return block_schemas()


@router.get("/users", response_model=list[AdminUserOut], response_model_exclude_none=True)
def list_users(_: SuperAdmin, db: DbSession):
    return db.scalars(select(User).order_by(User.id)).all()


@router.get("/audit-log", response_model=list[AuditEntryOut], response_model_exclude_none=True)
def audit_log(
    _: SuperAdmin,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1)] = None,
):
    query = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if before_id is not None:
        query = query.where(AuditLog.id < before_id)
    return db.scalars(query).all()
