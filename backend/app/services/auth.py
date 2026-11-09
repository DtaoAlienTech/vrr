"""Login, sessions and two-factor authentication. Every function that changes state saves it
(commit) before reporting a failure, so counters and the audit log survive the error response."""

import hashlib
import hmac
import logging
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import NoReturn

import pyotp
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import Settings
from app.core.errors import ApiError
from app.models import User, UserSession
from app.models.enums import Role
from app.services import audit

log = logging.getLogger("app.auth")

LOCKOUT_FAILURES = 5  # wrong passwords in a row ...
LOCKOUT_MINUTES = 15  # ... lock the account for this long
LOGIN_FAILURES_PER_MINUTE = 5  # per address, whoever the account is
REUSE_GRACE_SECONDS = 15  # two tabs may refresh at the same moment; that is not theft
RECOVERY_CODE_COUNT = 8
TOTP_STEP_SECONDS = 30

# One message for every kind of login failure, so it does not reveal which accounts exist.
LOGIN_FAILED = ApiError(
    401,
    "invalid_credentials",
    "Incorrect e-mail, password or code, or the account is temporarily locked.",
)


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass
class Auth:
    """The signed-in person and the login (session) they are using."""

    user: User
    session: UserSession

    @property
    def needs_totp_setup(self) -> bool:
        """Super admins must use two-factor login; until it is on, they can only set it up."""
        return self.user.role == Role.SUPER_ADMIN and not self.user.totp_enabled


# ---- sessions ----


def start_session(
    db: Session, settings: Settings, user: User, *, ip: str, user_agent: str | None
) -> tuple[UserSession, str]:
    """Creates a login. Returns it with the refresh token (shown once; only its hash is kept)."""
    token = security.new_refresh_token()
    row = UserSession(
        user_id=user.id,
        refresh_token_hash=security.hash_token(token),
        expires_at=_now() + timedelta(days=settings.refresh_token_days),
        user_agent=(user_agent or "")[:255] or None,
        ip=ip[:45],
    )
    db.add(row)
    db.flush()
    return row, token


def revoke_all_sessions(db: Session, user_id: int, *, except_session_id: int | None = None) -> None:
    stmt = (
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=_now())
    )
    if except_session_id is not None:
        stmt = stmt.where(UserSession.id != except_session_id)
    db.execute(stmt)


def load_auth(db: Session, session_id: int, user_id: int) -> Auth | None:
    """The person behind an access token, only if the login is still valid right now."""
    row = db.execute(
        select(UserSession, User)
        .join(User, User.id == UserSession.user_id)
        .where(UserSession.id == session_id, UserSession.user_id == user_id)
    ).first()
    if row is None:
        return None
    session, user = row
    if session.revoked_at is not None or session.expires_at <= _now() or not user.is_active:
        return None
    return Auth(user=user, session=session)


def refresh_session(
    db: Session, settings: Settings, refresh_token: str, *, ip: str, user_agent: str | None
) -> tuple[Auth, str]:
    """Replaces a refresh token with a new one. A token that was already replaced is a sign that
    it was copied: all of that person's logins are ended."""
    invalid = ApiError(401, "invalid_session", "Please sign in again.")
    old = db.scalar(
        select(UserSession)
        .where(UserSession.refresh_token_hash == security.hash_token(refresh_token))
        .with_for_update()
    )
    if old is None:
        raise invalid
    now = _now()
    if old.revoked_at is not None:
        if (now - old.revoked_at).total_seconds() > REUSE_GRACE_SECONDS:
            revoke_all_sessions(db, old.user_id)
            audit.record(db, "refresh_token_reuse", user_id=old.user_id, ip=ip)
            db.commit()
            log.warning("a replaced refresh token was used again; user %s logged out", old.user_id)
            raise invalid
        # Two tabs refreshed at the same moment. The other tab got the new token: do not touch it.
        raise ApiError(401, "session_replaced", "Please try again.")
    user = db.get(User, old.user_id)
    if old.expires_at <= now or user is None or not user.is_active:
        raise invalid
    old.revoked_at = now
    new, token = start_session(db, settings, user, ip=ip, user_agent=user_agent)
    db.commit()
    return Auth(user=user, session=new), token


def end_session(db: Session, refresh_token: str, *, ip: str) -> None:
    """Sign out the login that owns this refresh token (does nothing if it is unknown)."""
    session = db.scalar(
        select(UserSession).where(
            UserSession.refresh_token_hash == security.hash_token(refresh_token)
        )
    )
    if session is not None and session.revoked_at is None:
        session.revoked_at = _now()
        audit.record(db, "logout", user_id=session.user_id, ip=ip)
        db.commit()


# ---- passwords and lockout ----


def _fail(
    db: Session, ip: str, *, user: User | None = None, action: str = "login_failed"
) -> NoReturn:
    """Counts a failure (for the account lockout and the per-address limit), then reports it."""
    if user is not None:
        user.failed_logins += 1
        if user.failed_logins >= LOCKOUT_FAILURES:
            user.failed_logins = 0
            user.locked_until = _now() + timedelta(minutes=LOCKOUT_MINUTES)
            audit.record(db, "account_locked", user_id=user.id, ip=ip)
    audit.record(db, action, user_id=user.id if user else None, ip=ip)
    db.commit()
    raise LOGIN_FAILED


def _check_address_limit(db: Session, ip: str) -> None:
    if audit.recent_count(db, "login_failed", ip, seconds=60) >= LOGIN_FAILURES_PER_MINUTE:
        raise ApiError(
            429,
            "too_many_attempts",
            "Too many sign-in attempts. Please wait a minute and try again.",
            headers={"Retry-After": "60"},
        )


def clean_code(value: str | None) -> str:
    return re.sub(r"[\s-]", "", value or "").lower()


def login(
    db: Session,
    settings: Settings,
    *,
    email: str,
    password: str,
    totp_code: str | None,
    recovery_code: str | None,
    ip: str,
    user_agent: str | None,
) -> tuple[Auth, str]:
    _check_address_limit(db, ip)
    user = db.scalar(select(User).where(User.email == email.strip().lower()))

    if user is None:
        security.burn_password_time(password)  # same time as a real check
        _fail(db, ip)

    locked = user.locked_until is not None and user.locked_until > _now()
    if locked or not user.is_active:
        security.burn_password_time(password)
        audit.record(db, "login_refused", user_id=user.id, ip=ip)
        db.commit()
        raise LOGIN_FAILED

    if not security.verify_password(user.password_hash, password):
        _fail(db, ip, user=user)
    if security.password_needs_rehash(user.password_hash):
        user.password_hash = security.hash_password(password)

    if user.totp_enabled:
        if not totp_code and not recovery_code:
            raise ApiError(
                401, "totp_required", "Enter the 6-digit code from your authenticator app."
            )
        ok = (
            verify_totp(db, settings, user, totp_code)
            if totp_code
            else use_recovery_code(user, recovery_code)
        )
        if not ok:
            _fail(db, ip, user=user)

    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = _now()
    session, token = start_session(db, settings, user, ip=ip, user_agent=user_agent)
    audit.record(db, "login", user_id=user.id, ip=ip)
    db.commit()
    return Auth(user=user, session=session), token


def change_password(db: Session, auth: Auth, *, current: str, new: str, ip: str) -> None:
    user = auth.user
    if not security.verify_password(user.password_hash, current):
        _fail(db, ip, user=user, action="password_change_failed")
    problem = security.check_password_strength(new, email=user.email, name=user.name)
    if problem:
        raise ApiError(422, "weak_password", problem)
    if security.verify_password(user.password_hash, new):
        raise ApiError(422, "weak_password", "Choose a password you have not used before.")
    user.password_hash = security.hash_password(new)
    revoke_all_sessions(db, user.id, except_session_id=auth.session.id)  # other devices sign out
    audit.record(db, "password_changed", user_id=user.id, ip=ip)
    db.commit()


# ---- two-factor (TOTP) ----


def begin_totp_setup(db: Session, settings: Settings, user: User) -> tuple[str, str]:
    """A new secret (stored encrypted, not active yet) and the address for the QR code."""
    if user.totp_enabled:
        raise ApiError(409, "totp_already_enabled", "Two-factor login is already on.")
    secret = pyotp.random_base32()
    user.totp_secret = security.encrypt_secret(settings, secret)
    db.commit()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=settings.totp_issuer)
    return secret, uri


def verify_totp(db: Session, settings: Settings, user: User, code: str | None) -> bool:
    """True for the current code (or one step either side, for clock drift). A code that was
    already used is refused, so a code seen over someone's shoulder cannot be replayed."""
    secret = security.decrypt_secret(settings, user.totp_secret) if user.totp_secret else None
    digits = clean_code(code)
    # Plain 0-9 only: "\d" would also accept digits of other scripts, which cannot be compared.
    if secret is None or not re.fullmatch(r"[0-9]{6}", digits):
        return False
    totp = pyotp.TOTP(secret)
    current_step = int(_now().timestamp()) // TOTP_STEP_SECONDS
    for step in (current_step - 1, current_step, current_step + 1):
        if hmac.compare_digest(totp.generate_otp(step), digits):
            if user.totp_last_step is not None and step <= user.totp_last_step:
                return False
            user.totp_last_step = step
            return True
    return False


def _new_recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(3)}-{secrets.token_hex(3)}" for _ in range(RECOVERY_CODE_COUNT)]


def _hash_recovery_code(code: str) -> str:
    return hashlib.sha256(clean_code(code).encode()).hexdigest()


def use_recovery_code(user: User, code: str | None) -> bool:
    """One-time codes for a lost phone. Each works once."""
    hashed = _hash_recovery_code(code or "")
    if not any(hmac.compare_digest(hashed, stored) for stored in user.recovery_codes):
        return False
    user.recovery_codes = [c for c in user.recovery_codes if not hmac.compare_digest(c, hashed)]
    return True


def enable_totp(db: Session, settings: Settings, auth: Auth, code: str, *, ip: str) -> list[str]:
    user = auth.user
    if user.totp_enabled or not user.totp_secret:
        raise ApiError(409, "totp_not_pending", "Start the two-factor setup first.")
    if not verify_totp(db, settings, user, code):
        raise ApiError(400, "invalid_code", "That code is not correct. Please try again.")
    codes = _new_recovery_codes()
    user.recovery_codes = [_hash_recovery_code(c) for c in codes]
    user.totp_enabled = True
    audit.record(db, "totp_enabled", user_id=user.id, ip=ip)
    db.commit()
    return codes


def disable_totp(
    db: Session, settings: Settings, user: User, *, password: str, code: str, ip: str
) -> None:
    if user.role == Role.SUPER_ADMIN:
        raise ApiError(403, "totp_required_for_role", "Super admins must keep two-factor login on.")
    if not user.totp_enabled:
        raise ApiError(409, "totp_not_enabled", "Two-factor login is not on.")
    if not security.verify_password(user.password_hash, password) or not verify_totp(
        db, settings, user, code
    ):
        _fail(db, ip, user=user, action="totp_disable_failed")
    user.totp_enabled = False
    user.totp_secret = None
    user.totp_last_step = None
    user.recovery_codes = []
    audit.record(db, "totp_disabled", user_id=user.id, ip=ip)
    db.commit()
