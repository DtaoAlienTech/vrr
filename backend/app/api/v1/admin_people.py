"""Staff endpoints for staff accounts (super admin) and for the enquiries people send in."""

import csv
import io
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query, Request, Response, status
from sqlalchemy import select

from app.api.deps import DbSession, Staff, SuperAdmin
from app.core import security
from app.core.errors import ApiError
from app.models import Enquiry, User
from app.models.enums import EnquiryStatus, Role
from app.schemas.admin import (
    EnquiryAdminOut,
    EnquiryUpdateIn,
    PasswordResetIn,
    UserCreateIn,
    UserUpdateIn,
)
from app.schemas.auth import AdminUserOut
from app.services import admin_ops as ops
from app.services.auth import revoke_all_sessions

router = APIRouter(prefix="/admin", tags=["admin people"])

_OUT: dict[str, Any] = {"response_model": AdminUserOut, "response_model_exclude_none": True}


def _get_user(db: DbSession, user_id: int) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise ApiError(404, "not_found", "That account does not exist.")
    return user


def _other_active_super_admins(db: DbSession, user_id: int) -> int:
    """How many active super admins there are besides this one. The rows are locked until the
    change is saved, so two super admins switching each other off at the same moment are handled
    one after the other (the second sees the first one's change) and cannot lock everyone out."""
    locked = db.scalars(
        select(User.id)
        .where(User.role == Role.SUPER_ADMIN.value, User.is_active.is_(True))
        .order_by(User.id)
        .with_for_update()
    )
    return sum(1 for other_id in locked if other_id != user_id)


def _not_yourself(auth_user_id: int, user_id: int, message: str) -> None:
    if auth_user_id == user_id:
        raise ApiError(403, "cannot_change_self", message)


# ============================ accounts ============================


@router.post("/users", status_code=status.HTTP_201_CREATED, **_OUT)
def create_user(
    data: UserCreateIn,
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
):
    problem = security.check_password_strength(data.password, email=data.email, name=data.name)
    if problem:
        raise ApiError(422, "weak_password", problem)
    if db.scalar(select(User.id).where(User.email == data.email)):
        raise ApiError(409, "email_taken", "An account with that e-mail already exists.")
    user = User(
        email=data.email, name=data.name, role=data.role.value,
        password_hash=security.hash_password(data.password),
    )  # fmt: skip
    db.add(user)
    ops.flush_or_conflict(db)
    ops.finish(db, request, auth, action="user_create", entity="user",
               entity_id=user.id, tags=[], changes={"role": user.role})  # fmt: skip
    return user


@router.put("/users/{user_id}", **_OUT)
def update_user(
    user_id: int,
    data: UserUpdateIn,
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
):
    user = _get_user(db, user_id)
    new_role = data.role.value if data.role else user.role
    new_active = user.is_active if data.is_active is None else data.is_active
    if new_role != user.role or new_active != user.is_active:
        _not_yourself(
            auth.user.id, user.id, "You cannot change your own role or switch yourself off."
        )
        stops_being_admin = (
            user.role == Role.SUPER_ADMIN.value
            and user.is_active
            and (new_role != Role.SUPER_ADMIN.value or not new_active)
        )
        if stops_being_admin and _other_active_super_admins(db, user.id) == 0:
            raise ApiError(409, "last_super_admin", "There must always be one active super admin.")
    changed = [
        field
        for field, new, old in (
            ("name", data.name or user.name, user.name),
            ("role", new_role, user.role),
            ("isActive", new_active, user.is_active),
        )
        if new != old
    ]
    user.name, user.role, user.is_active = data.name or user.name, new_role, new_active
    if not new_active:
        revoke_all_sessions(db, user.id)  # signed out at once
    ops.finish(db, request, auth, action="user_update", entity="user",
               entity_id=user.id, tags=[], changes={"fields": changed})  # fmt: skip
    return user


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    data: PasswordResetIn,
    request: Request,
    auth: SuperAdmin,
    db: DbSession,
):
    """Sets a new password (for example after one was forgotten), unlocks the account and signs
    it out everywhere."""
    user = _get_user(db, user_id)
    _not_yourself(auth.user.id, user.id, "Use “change password” for your own account.")
    problem = security.check_password_strength(data.new_password, email=user.email, name=user.name)
    if problem:
        raise ApiError(422, "weak_password", problem)
    user.password_hash = security.hash_password(data.new_password)
    user.failed_logins, user.locked_until = 0, None
    revoke_all_sessions(db, user.id)
    ops.finish(db, request, auth, action="user_password_reset", entity="user",
               entity_id=user.id, tags=[])  # fmt: skip


@router.post("/users/{user_id}/reset-two-factor", status_code=status.HTTP_204_NO_CONTENT)
def reset_two_factor(user_id: int, request: Request, auth: SuperAdmin, db: DbSession):
    """For a lost phone: turns two-factor login off. A super admin must set it up again at the
    next sign-in; the person is signed out everywhere."""
    user = _get_user(db, user_id)
    _not_yourself(auth.user.id, user.id, "You cannot reset your own two-factor login.")
    user.totp_enabled, user.totp_secret, user.totp_last_step = False, None, None
    user.recovery_codes = []
    revoke_all_sessions(db, user.id)
    ops.finish(db, request, auth, action="user_two_factor_reset", entity="user",
               entity_id=user.id, tags=[])  # fmt: skip


# ============================ enquiries ============================


def _enquiry_filter(query: Any, status_filter: EnquiryStatus | None, q: str | None) -> Any:
    if status_filter:
        query = query.where(Enquiry.status == status_filter.value)
    if q and q.strip():
        pattern = ops.like_pattern(q)
        query = query.where(
            Enquiry.name.ilike(pattern, escape="\\")
            | Enquiry.phone.ilike(pattern, escape="\\")
            | Enquiry.course.ilike(pattern, escape="\\")
            | Enquiry.message.ilike(pattern, escape="\\")
        )
    return query


def _enquiry_out(row: Enquiry) -> dict[str, Any]:
    return {
        "id": row.id, "name": row.name, "phone": row.phone, "course": row.course,
        "message": row.message, "status": row.status, "source_page": row.source_page,
        "created_at": row.created_at, "handled_by": row.handled_by, "handled_at": row.handled_at,
    }  # fmt: skip


StatusFilter = Annotated[EnquiryStatus | None, Query(alias="status")]
Search = Annotated[str | None, Query(max_length=100)]


@router.get("/enquiries", response_model=list[EnquiryAdminOut], response_model_exclude_none=True)
def list_enquiries(
    _: Staff,
    db: DbSession,
    status_filter: StatusFilter = None,
    q: Search = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    before_id: Annotated[int | None, Query(ge=1)] = None,
):
    """Newest first. `before_id` continues after the last item of the previous page."""
    query = _enquiry_filter(select(Enquiry), status_filter, q)
    if before_id:
        query = query.where(Enquiry.id < before_id)
    return [_enquiry_out(r) for r in db.scalars(query.order_by(Enquiry.id.desc()).limit(limit))]


def _spreadsheet_safe(value: object) -> str:
    """A cell that starts with = + - @ is run as a formula by Excel: a visitor could type one into
    the enquiry form. A leading apostrophe makes it plain text."""
    text = "" if value is None else str(value)
    return f"'{text}" if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _stamp(moment: datetime | None) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC") if moment else ""


@router.get("/enquiries/export.csv")
def export_enquiries(
    request: Request,
    auth: Staff,
    db: DbSession,
    status_filter: StatusFilter = None,
    q: Search = None,
) -> Response:
    rows = list(
        db.scalars(
            _enquiry_filter(select(Enquiry), status_filter, q)
            .order_by(Enquiry.id.desc())
            .limit(10000)
        )
    )
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Received", "Name", "Phone", "Course", "Message", "Status", "Page", "Handled"])
    for row in rows:
        cells = (
            _stamp(row.created_at), row.name, row.phone, row.course, row.message, row.status,
            row.source_page, _stamp(row.handled_at),
        )  # fmt: skip
        writer.writerow([_spreadsheet_safe(cell) for cell in cells])
    # a personal-data export: always recorded
    ops.finish(db, request, auth, action="enquiries_export", entity="enquiry",
               entity_id=None, tags=[], changes={"count": len(rows)})  # fmt: skip
    filename = f"enquiries-{datetime.now(UTC):%Y-%m-%d}.csv"
    return Response(
        content="﻿" + out.getvalue(),  # the marker makes Excel read names in any language
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch(
    "/enquiries/{enquiry_id}", response_model=EnquiryAdminOut, response_model_exclude_none=True
)
def update_enquiry(
    enquiry_id: int,
    data: EnquiryUpdateIn,
    request: Request,
    auth: Staff,
    db: DbSession,
):
    row = db.get(Enquiry, enquiry_id)
    if row is None:
        raise ApiError(404, "not_found", "That enquiry does not exist.")
    row.status = data.status.value
    row.handled_by = None if data.status == EnquiryStatus.NEW else auth.user.id
    row.handled_at = None if data.status == EnquiryStatus.NEW else datetime.now(UTC)
    ops.finish(db, request, auth, action="enquiry_update", entity="enquiry",
               entity_id=row.id, tags=[], changes={"status": row.status})  # fmt: skip
    return _enquiry_out(row)
