"""Security building blocks: password hashing, signed access tokens, refresh tokens, CSRF tokens
and encryption of two-factor secrets. No database access here, so everything is easy to test."""

import base64
import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import Settings

# ---- keys: one secret in the environment, a separate derived key for every purpose ----


def derive_key(settings: Settings, purpose: str) -> bytes:
    """A key that only works for `purpose`. A leak of one derived key (for example the one that
    signs tokens) does not reveal the others, or the secret itself."""
    return hmac.new(
        settings.secret_key.encode(), f"vrr:{purpose}".encode(), hashlib.sha256
    ).digest()


# ---- passwords ----

_hasher = PasswordHasher()  # Argon2id with the library's current recommended cost

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 128  # long enough for passphrases, short enough to stop hashing-cost abuse
_COMMON_PASSWORDS = {
    "password1234", "passwordpassword", "123456789012", "qwertyuiopas", "administrator",
    "welcome12345", "letmein12345", "iloveyou1234", "college12345", "vrrcollege123",
}  # fmt: skip


def check_password_strength(password: str, *, email: str = "", name: str = "") -> str | None:
    """A message describing the problem, or None when the password is acceptable."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Use at most {MAX_PASSWORD_LENGTH} characters."
    lowered = password.lower()
    if lowered in _COMMON_PASSWORDS or len(set(password)) < 5:
        return "That password is too easy to guess."
    for personal in (email.split("@")[0], *name.split()):
        if len(personal) >= 4 and personal.lower() in lowered:
            return "The password must not contain your name or email."
    return None


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def password_needs_rehash(stored_hash: str) -> bool:
    return _hasher.check_needs_rehash(stored_hash)


# A real hash of a random value. Checking a password against it when the e-mail is unknown makes
# "no such user" take as long as "wrong password", so response time reveals nothing.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_password_time(password: str) -> None:
    verify_password(_DUMMY_HASH, password)


# ---- access token (JWT) ----

_ALGORITHM = "HS256"


def create_access_token(settings: Settings, *, user_id: int, session_id: int) -> str:
    now = datetime.now(UTC)
    claims = {
        "typ": "access",
        "sub": str(user_id),
        "sid": session_id,
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(claims, derive_key(settings, "access-token"), algorithm=_ALGORITHM)


def read_access_token(settings: Settings, token: str) -> dict[str, Any] | None:
    """The token's claims, or None when it is invalid, expired or not an access token. The
    algorithm is fixed, so tokens that claim "alg: none" or another algorithm are refused."""
    try:
        claims = jwt.decode(
            token,
            derive_key(settings, "access-token"),
            algorithms=[_ALGORITHM],
            options={"require": ["exp", "iat", "sub", "sid", "typ"]},
        )
    except jwt.PyJWTError:
        return None
    if claims.get("typ") != "access" or not isinstance(claims.get("sid"), int):
        return None
    return claims


# ---- refresh token: random, only its hash is stored ----


def new_refresh_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# ---- CSRF: a token that only a page of our own site can know ----


def csrf_token(settings: Settings, session_id: int) -> str:
    """Derived from the session, so nothing is stored. The page learns it from /auth/me (which other
    websites cannot read) and sends it back in the X-CSRF-Token header on every change."""
    return hmac.new(
        derive_key(settings, "csrf"), f"session:{session_id}".encode(), hashlib.sha256
    ).hexdigest()


def csrf_matches(settings: Settings, session_id: int, given: str | None) -> bool:
    return bool(given) and hmac.compare_digest(csrf_token(settings, session_id), given or "")


# ---- preview links: a signed, short-lived address that shows one draft to whoever has it ----

PREVIEW_KINDS = ("page", "news")
PREVIEW_LIFETIME = timedelta(minutes=30)
_PREVIEW_ID_MAX_DIGITS = 18


def _preview_signature(settings: Settings, text: str) -> str:
    return hmac.new(derive_key(settings, "preview"), text.encode(), hashlib.sha256).hexdigest()


def create_preview_token(
    settings: Settings, *, kind: str, entity_id: int, now: datetime | None = None
) -> tuple[str, datetime]:
    """`v1.<kind>.<id>.<expires unix time>.<signature>`. The token only ever opens one item for
    reading, so an editor can share it with a colleague without sharing an account."""
    if kind not in PREVIEW_KINDS or entity_id < 1:
        raise ValueError("unknown preview target")
    expires = (now or datetime.now(UTC)) + PREVIEW_LIFETIME
    body = f"v1.{kind}.{entity_id}.{int(expires.timestamp())}"
    return f"{body}.{_preview_signature(settings, body)}", expires


def read_preview_token(
    settings: Settings, token: str, now: datetime | None = None
) -> tuple[str, int] | None:
    """(kind, id) of a genuine, unexpired token; None for anything else (never an error detail)."""
    parts = token.split(".")
    if len(parts) != 5 or parts[0] != "v1":
        return None
    version, kind, raw_id, raw_expires, signature = parts
    if kind not in PREVIEW_KINDS:
        return None
    for number in (raw_id, raw_expires):
        if not (number.isascii() and number.isdigit()) or len(number) > _PREVIEW_ID_MAX_DIGITS:
            return None
    expected = _preview_signature(settings, f"{version}.{kind}.{raw_id}.{raw_expires}")
    if not hmac.compare_digest(expected, signature):
        return None
    if int(raw_expires) < int((now or datetime.now(UTC)).timestamp()):
        return None
    return kind, int(raw_id)


# ---- encryption of two-factor secrets (a leaked database must not leak them) ----


def _fernet(settings: Settings) -> Fernet:
    return Fernet(base64.urlsafe_b64encode(derive_key(settings, "totp-secret")))


def encrypt_secret(settings: Settings, plain: str) -> str:
    return _fernet(settings).encrypt(plain.encode()).decode()


def decrypt_secret(settings: Settings, encrypted: str) -> str | None:
    try:
        return _fernet(settings).decrypt(encrypted.encode()).decode()
    except InvalidToken:
        return None
