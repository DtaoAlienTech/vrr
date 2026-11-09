from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import CamelModel
from app.schemas.public import Out


class LoginIn(CamelModel):
    email: str = Field(max_length=254)
    password: str = Field(max_length=256)
    totp_code: str | None = Field(default=None, max_length=16)
    recovery_code: str | None = Field(default=None, max_length=32)


class ChangePasswordIn(CamelModel):
    current_password: str = Field(max_length=256)
    new_password: str = Field(max_length=256)


class TotpCodeIn(CamelModel):
    code: str = Field(max_length=16)


class TotpDisableIn(CamelModel):
    password: str = Field(max_length=256)
    code: str = Field(max_length=16)


class UserOut(Out):
    id: int
    email: str
    name: str
    role: str
    totp_enabled: bool
    needs_totp_setup: bool


class SessionOut(Out):
    user: UserOut
    # Sent back in the X-CSRF-Token header on every change (POST, PUT, PATCH, DELETE).
    csrf_token: str


class TotpSetupOut(Out):
    secret: str
    otpauth_uri: str


class RecoveryCodesOut(Out):
    recovery_codes: list[str]


class AdminUserOut(Out):
    id: int
    email: str
    name: str
    role: str
    is_active: bool
    totp_enabled: bool
    last_login_at: datetime | None = None
    locked_until: datetime | None = None


class AuditEntryOut(Out):
    id: int
    user_id: int | None = None
    action: str
    entity: str | None = None
    entity_id: int | None = None
    changes: dict[str, Any] | None = None
    ip: str | None = None
    created_at: datetime
