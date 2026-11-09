"""Password hashing, tokens, CSRF tokens, encryption and settings: the building blocks of login."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from argon2 import PasswordHasher
from pydantic import ValidationError

from app.api.cookies import ACCESS_COOKIE, REFRESH_COOKIE, set_auth_cookies
from app.core import security
from app.core.config import Settings, get_settings
from app.core.logging import new_request_id

SETTINGS = get_settings()


def other_settings(**changes) -> Settings:
    return SETTINGS.model_copy(update=changes)


# ---- keys ----


def test_derived_keys_are_stable_separate_and_depend_on_the_secret():
    key = security.derive_key(SETTINGS, "access-token")
    assert key == security.derive_key(SETTINGS, "access-token") and len(key) == 32
    assert key != security.derive_key(SETTINGS, "csrf")
    assert key != security.derive_key(
        other_settings(secret_key="another-secret-key-0123456789"), "access-token"
    )
    assert SETTINGS.secret_key.encode() != key


# ---- passwords ----


@pytest.mark.parametrize(
    ("password", "problem"),
    [
        ("short", "at least 12"),
        ("x" * 129, "at most 128"),
        ("Password1234", "too easy"),
        ("aaaaaaaaaaaaaaaa", "too easy"),
        ("ababababababab", "too easy"),
    ],
)
def test_weak_passwords_are_refused(password, problem):
    assert problem in (security.check_password_strength(password) or "")


def test_password_must_not_contain_the_persons_name_or_email():
    message = security.check_password_strength(
        "my-asha-is-great-1", email="asha.reddy@vrr.in", name="Asha Reddy"
    )
    assert message and "name or email" in message
    assert (
        security.check_password_strength(
            "tulip-granite-orbit-91", email="asha.reddy@vrr.in", name="Asha Reddy"
        )
        is None
    )


def test_long_passphrases_are_accepted():
    assert security.check_password_strength("a long passphrase with several words in it") is None


def test_real_password_hashing_uses_argon2id_and_notices_weaker_settings(monkeypatch):
    monkeypatch.undo()  # drop the fast test hasher: use the real settings
    monkeypatch.setattr(security, "_hasher", PasswordHasher())
    hashed = security.hash_password("a very long password")
    assert hashed.startswith("$argon2id$")
    assert security.verify_password(hashed, "a very long password")
    assert not security.password_needs_rehash(hashed)
    weak = PasswordHasher(time_cost=1, memory_cost=8, parallelism=1).hash("a very long password")
    assert security.password_needs_rehash(weak)  # upgraded on the person's next login


def test_password_verification_never_raises_and_hashes_are_salted():
    one, two = security.hash_password("same password!"), security.hash_password("same password!")
    assert one != two
    assert security.verify_password(one, "same password!") and not security.verify_password(
        one, "other"
    )
    for garbage in ("", "not a hash", "$argon2id$broken"):
        assert security.verify_password(garbage, "same password!") is False


# ---- access tokens ----


def make_token(**claims) -> str:
    now = datetime.now(UTC)
    payload = {"typ": "access", "sub": "5", "sid": 9, "iat": now, "exp": now + timedelta(minutes=5)}
    payload.update(claims)
    payload = {k: v for k, v in payload.items() if v is not None}
    return jwt.encode(payload, security.derive_key(SETTINGS, "access-token"), algorithm="HS256")


def test_access_token_round_trip():
    token = security.create_access_token(SETTINGS, user_id=5, session_id=9)
    claims = security.read_access_token(SETTINGS, token)
    assert claims and claims["sub"] == "5" and claims["sid"] == 9 and claims["typ"] == "access"
    assert claims["exp"] - claims["iat"] == SETTINGS.access_token_minutes * 60


def test_forged_expired_and_malformed_tokens_are_refused():
    good = make_token()
    assert security.read_access_token(SETTINGS, good)
    now = datetime.now(UTC)
    unsigned = jwt.encode(
        {"typ": "access", "sub": "1", "sid": 1, "iat": now, "exp": now + timedelta(hours=1)},
        key="",
        algorithm="none",
    )  # noqa: E501
    foreign_key = jwt.encode(
        {"typ": "access", "sub": "1", "sid": 1, "iat": now, "exp": now + timedelta(hours=1)},
        "x" * 32,
        algorithm="HS256",
    )  # noqa: E501
    other_algorithm = jwt.encode(
        {"typ": "access", "sub": "1", "sid": 1, "iat": now, "exp": now + timedelta(hours=1)},
        security.derive_key(SETTINGS, "access-token") * 2,
        algorithm="HS512",
    )  # noqa: E501
    bad = [
        good + "x",  # signature broken
        good[:-4] + ("AAAA" if not good.endswith("AAAA") else "BBBB"),
        good.split(".")[0] + "." + good.split(".")[1],  # signature removed
        unsigned,  # "alg: none"
        foreign_key,  # signed with another key
        other_algorithm,  # another algorithm
        make_token(exp=now - timedelta(seconds=1)),  # expired
        make_token(typ="refresh"),  # wrong kind
        make_token(typ=None),  # missing claims
        make_token(sub=None),
        make_token(sid="9"),  # session id must be a number
        "",
        "a.b.c",
        "not a token",
    ]
    for token in bad:
        assert security.read_access_token(SETTINGS, token) is None, token[:40]


def test_a_token_from_another_installation_is_refused():
    token = security.create_access_token(
        other_settings(secret_key="another-secret-key-0123456789"), user_id=1, session_id=1
    )
    assert security.read_access_token(SETTINGS, token) is None


# ---- refresh tokens ----


def test_refresh_tokens_are_random_and_only_hashes_are_stored():
    one, two = security.new_refresh_token(), security.new_refresh_token()
    assert one != two and len(one) >= 40
    assert security.hash_token(one) == security.hash_token(one) != one
    assert len(security.hash_token(one)) == 64


# ---- CSRF ----


def test_csrf_token_belongs_to_one_session():
    token = security.csrf_token(SETTINGS, 7)
    assert security.csrf_matches(SETTINGS, 7, token)
    assert not security.csrf_matches(SETTINGS, 8, token)
    assert not security.csrf_matches(SETTINGS, 7, token[:-1] + ("0" if token[-1] != "0" else "1"))
    assert not security.csrf_matches(SETTINGS, 7, None)
    assert not security.csrf_matches(SETTINGS, 7, "")
    other = other_settings(secret_key="another-secret-key-0123456789")
    assert not security.csrf_matches(other, 7, token)


# ---- encryption of 2FA secrets ----


def test_two_factor_secrets_are_encrypted():
    encrypted = security.encrypt_secret(SETTINGS, "JBSWY3DPEHPK3PXP")
    assert "JBSWY3DPEHPK3PXP" not in encrypted
    assert security.decrypt_secret(SETTINGS, encrypted) == "JBSWY3DPEHPK3PXP"
    assert encrypted != security.encrypt_secret(SETTINGS, "JBSWY3DPEHPK3PXP")  # fresh each time
    assert security.decrypt_secret(SETTINGS, encrypted[:-3] + "xyz") is None  # tampered
    other = other_settings(secret_key="another-secret-key-0123456789")
    assert security.decrypt_secret(other, encrypted) is None  # wrong key
    assert security.decrypt_secret(SETTINGS, "garbage") is None


# ---- settings ----


def test_production_needs_a_long_secret_key():
    with pytest.raises(ValidationError, match="at least 32"):
        Settings(env="prod", secret_key="x" * 20, database_url="postgresql+psycopg://x")
    assert Settings(env="prod", secret_key="x" * 32, database_url="postgresql+psycopg://x")
    assert Settings(env="dev", secret_key="x" * 20, database_url="postgresql+psycopg://x")


def test_cookies_are_secure_in_production_unless_overridden():
    url = "postgresql+psycopg://x"
    assert Settings(env="prod", secret_key="x" * 32, database_url=url).cookies_secure is True
    assert Settings(env="dev", secret_key="x" * 32, database_url=url).cookies_secure is False
    forced = Settings(env="dev", secret_key="x" * 32, database_url=url, cookie_secure=True)
    assert forced.cookies_secure is True


def test_auth_cookies_are_httponly_secure_and_scoped():
    from fastapi import Response

    response = Response()
    prod = Settings(env="prod", secret_key="x" * 32, database_url="postgresql+psycopg://x")
    set_auth_cookies(response, prod, "access-value", "refresh-value")
    cookies = {h.split("=")[0]: h for k, h in response.headers.items() if k == "set-cookie"}
    access, refresh = cookies[ACCESS_COOKIE].lower(), cookies[REFRESH_COOKIE].lower()
    for cookie in (access, refresh):
        assert "httponly" in cookie and "secure" in cookie
    assert "path=/api;" in access and "samesite=lax" in access and "max-age=900" in access
    assert "path=/api/v1/auth" in refresh and "samesite=strict" in refresh
    assert "max-age=604800" in refresh


# ---- request ids ----


def test_request_ids_are_kept_only_when_they_look_safe():
    assert new_request_id("abcd1234-ef56") == "abcd1234-ef56"
    for bad in (
        None,
        "",
        "short",
        "a" * 65,
        "has space in it",
        "../../etc/passwd",
        "id\r\nX-Evil: 1",
    ):
        generated = new_request_id(bad)
        assert generated != bad and len(generated) == 32
