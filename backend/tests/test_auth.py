"""Login, lockout, sessions, CSRF, refresh tokens, logout and password change."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.api.cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.core import security
from app.core.config import get_settings
from app.models import AuditLog, UserSession
from app.services import auth as auth_service
from tests.conftest import PASSWORD
from tests.helpers import changes, sign_in, signed_in

ME = "/api/v1/auth/me"
REFRESH = "/api/v1/auth/refresh"
LOGOUT = "/api/v1/auth/logout"
CHANGE_PASSWORD = "/api/v1/auth/change-password"
SETUP = "/api/v1/auth/totp/setup"  # an ordinary state-changing endpoint, used to test CSRF
SAME_ORIGIN = {"Origin": "http://localhost"}


def actions(db, name: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == name)))


# ---- signing in ----


def test_sign_in_sets_protected_cookies_and_returns_the_person(api, make_user):
    user = make_user(name="Asha Reddy")
    response = sign_in(api)
    assert response.status_code == 200
    body = response.json()
    assert body["user"] == {
        "id": user.id, "email": "staff@example.org", "name": "Asha Reddy", "role": "editor",
        "totpEnabled": False, "needsTotpSetup": False,
    }  # fmt: skip
    assert body["csrfToken"] == security.csrf_token(get_settings(), _session_id(api))
    text = response.text
    assert "password" not in text.lower() and "hash" not in text.lower()
    assert response.headers["cache-control"] == "no-store"

    cookies = [c.lower() for c in response.headers.get_list("set-cookie")]
    access = next(c for c in cookies if c.startswith(ACCESS_COOKIE))
    refresh = next(c for c in cookies if c.startswith(REFRESH_COOKIE))
    assert "httponly" in access and "path=/api;" in access and "samesite=lax" in access
    assert "httponly" in refresh and "path=/api/v1/auth" in refresh and "samesite=strict" in refresh


def _session_id(api) -> int:
    claims = security.read_access_token(get_settings(), api.cookies[ACCESS_COOKIE])
    return claims["sid"]


def test_e_mail_is_not_case_or_space_sensitive(api, make_user):
    make_user()
    assert sign_in(api, email="  STAFF@Example.ORG ").status_code == 200


def test_tokens_are_not_stored_in_clear_text(api, make_user, db_session):
    make_user()
    sign_in(api)
    session = db_session.scalars(select(UserSession)).one()
    assert session.refresh_token_hash == security.hash_token(api.cookies[REFRESH_COOKIE])
    assert api.cookies[REFRESH_COOKIE] not in session.refresh_token_hash


def test_wrong_password_and_unknown_e_mail_look_identical(api, make_user, monkeypatch):
    make_user()
    burned = []
    monkeypatch.setattr(auth_service.security, "burn_password_time", burned.append)
    wrong = sign_in(api, password="not the password")
    unknown = sign_in(api, email="nobody@example.org")
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert set(wrong.json()) == {"detail", "code"} and wrong.json()["code"] == "invalid_credentials"
    assert len(burned) == 1  # an unknown e-mail still costs one password check: same response time
    assert ACCESS_COOKIE not in api.cookies


def test_failed_logins_are_counted_and_audited_without_personal_data(api, make_user, db_session):
    user = make_user()
    sign_in(api, password="wrong password!")
    db_session.refresh(user)
    assert user.failed_logins == 1
    entry = actions(db_session, "login_failed")[0]
    assert entry.user_id == user.id and entry.changes is None  # no e-mail, no password


def test_success_resets_the_counter_and_records_the_login(api, make_user, db_session):
    user = make_user()
    for _ in range(3):
        sign_in(api, password="wrong password!")
    assert sign_in(api).status_code == 200
    db_session.refresh(user)
    assert user.failed_logins == 0 and user.last_login_at is not None
    assert len(actions(db_session, "login")) == 1


def test_account_locks_after_five_failures_for_fifteen_minutes(api, make_user, db_session, proxied):
    user = make_user()
    for n in range(5):  # different visitors, so only the account lockout is being tested
        assert sign_in(api, password="wrong password!", ip=f"10.0.0.{n}").status_code == 401
    db_session.refresh(user)
    assert user.locked_until is not None
    assert timedelta(minutes=14) < user.locked_until - datetime.now(UTC) <= timedelta(minutes=15)
    assert len(actions(db_session, "account_locked")) == 1

    # even the right password is refused while locked, with the same message
    locked = sign_in(api, ip="10.0.0.99")
    assert locked.status_code == 401 and locked.json()["code"] == "invalid_credentials"
    assert len(actions(db_session, "login_refused")) == 1

    user.locked_until = datetime.now(UTC) - timedelta(seconds=1)  # fifteen minutes later
    db_session.flush()
    assert sign_in(api, ip="10.0.0.99").status_code == 200
    db_session.refresh(user)
    assert user.locked_until is None and user.failed_logins == 0


def test_one_address_is_limited_to_five_failures_a_minute(api, make_user, proxied):
    make_user()
    for n in range(5):
        assert sign_in(api, email=f"nobody{n}@example.org", ip="10.1.1.1").status_code == 401
    blocked = sign_in(api, ip="10.1.1.1")  # the right password does not help
    assert blocked.status_code == 429 and blocked.json()["code"] == "too_many_attempts"
    assert blocked.headers["retry-after"] == "60"
    assert sign_in(api, ip="10.1.1.2").status_code == 200  # someone else is not affected


def test_inactive_accounts_cannot_sign_in(api, make_user):
    make_user(is_active=False)
    assert sign_in(api).status_code == 401


def test_login_input_is_validated(api, make_user):
    make_user()
    url = "/api/v1/auth/login"
    assert api.post(url, json={"email": "a@b.co"}).status_code == 422
    assert api.post(url, json={"email": "a@b.co", "password": "x" * 300}).status_code == 422
    assert (
        api.post(url, json={"email": "a@b.co", "password": "x", "admin": True}).status_code == 422
    )
    assert api.post(url, content=b"not json").status_code == 422


def test_sign_in_from_another_website_is_refused(api, make_user):
    make_user()
    evil = api.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.org", "password": PASSWORD},
        headers={"Origin": "https://evil.example"},
    )
    assert evil.status_code == 403 and evil.json()["code"] == "bad_origin"
    assert ACCESS_COOKIE not in api.cookies
    own = api.post(
        "/api/v1/auth/login",
        json={"email": "staff@example.org", "password": PASSWORD},
        headers=SAME_ORIGIN,
    )
    assert own.status_code == 200


def test_old_weaker_hashes_are_upgraded_on_sign_in(api, make_user, db_session, monkeypatch):
    from argon2 import PasswordHasher

    user = make_user()
    old_hash = user.password_hash
    monkeypatch.setattr(
        security, "_hasher", PasswordHasher(time_cost=2, memory_cost=16, parallelism=1)
    )  # the "current" settings are now stronger than what this account was hashed with
    assert sign_in(api).status_code == 200
    db_session.refresh(user)
    assert user.password_hash != old_hash and security.verify_password(user.password_hash, PASSWORD)


# ---- who is signed in ----


def test_me_needs_a_session(api, make_user):
    make_user()
    missing = api.get(ME)
    assert missing.status_code == 401 and missing.json()["code"] == "not_authenticated"
    csrf = signed_in(api)
    me = api.get(ME)
    assert me.status_code == 200 and me.json()["csrfToken"] == csrf


@pytest.mark.parametrize("kind", ["garbage", "expired", "unsigned", "revoked", "other_user"])
def test_bad_access_tokens_are_refused(api, make_user, db_session, kind):
    import jwt

    user = make_user()
    signed_in(api)
    settings = get_settings()
    now = datetime.now(UTC)
    key = security.derive_key(settings, "access-token")
    claims = {
        "typ": "access", "sub": str(user.id), "sid": _session_id(api),
        "iat": now, "exp": now + timedelta(minutes=5),
    }  # fmt: skip
    if kind == "garbage":
        token = "x.y.z"
    elif kind == "expired":
        token = jwt.encode({**claims, "exp": now - timedelta(seconds=5)}, key, "HS256")
    elif kind == "unsigned":
        token = jwt.encode(claims, key="", algorithm="none")
    elif kind == "other_user":  # a valid token whose user does not own the session
        token = jwt.encode({**claims, "sub": str(user.id + 1000)}, key, "HS256")
    else:  # a perfectly good token, but the login was ended
        db_session.scalars(select(UserSession)).one().revoked_at = now
        db_session.flush()
        token = api.cookies[ACCESS_COOKIE]
    api.cookies.clear()
    assert api.get(ME, headers={"Cookie": f"{ACCESS_COOKIE}={token}"}).status_code == 401


def test_deactivating_an_account_ends_access_at_once(api, make_user, db_session):
    user = make_user()
    signed_in(api)
    assert api.get(ME).status_code == 200
    user.is_active = False
    db_session.flush()
    assert api.get(ME).status_code == 401


def test_expired_logins_are_refused(api, make_user, db_session):
    make_user()
    signed_in(api)
    db_session.scalars(select(UserSession)).one().expires_at = datetime.now(UTC) - timedelta(
        seconds=1
    )
    db_session.flush()
    assert api.get(ME).status_code == 401


# ---- CSRF and origin ----


def test_changes_need_the_csrf_token(api, make_user):
    make_user()
    csrf = signed_in(api)
    for headers in (
        {},
        {"X-CSRF-Token": "wrong"},
        {"X-CSRF-Token": csrf[::-1]},
        {"X-CSRF-Token": ""},
    ):
        response = api.post(SETUP, headers={**SAME_ORIGIN, **headers})
        assert response.status_code == 403 and response.json()["code"] == "csrf_failed"
    assert api.post(SETUP, headers=changes(csrf)).status_code == 200


def test_a_csrf_token_from_another_login_does_not_work(api, make_user):
    make_user()
    other = signed_in(api)
    api.cookies.clear()
    signed_in(api)
    assert api.post(SETUP, headers=changes(other)).status_code == 403


def test_changes_from_another_website_are_refused_even_with_the_token(api, make_user):
    make_user()
    csrf = signed_in(api)
    response = api.post(SETUP, headers={"X-CSRF-Token": csrf, "Origin": "https://evil.example"})
    assert response.status_code == 403 and response.json()["code"] == "bad_origin"


def test_reading_does_not_need_the_csrf_token(api, make_user):
    make_user()
    signed_in(api)
    assert api.get(ME).status_code == 200


# ---- refresh tokens ----


def test_refresh_replaces_the_token_and_the_old_one_stops_working(api, make_user, db_session):
    make_user()
    signed_in(api)
    old_refresh, old_access = api.cookies[REFRESH_COOKIE], api.cookies[ACCESS_COOKIE]

    response = api.post(REFRESH, headers=SAME_ORIGIN)
    assert response.status_code == 200
    assert api.cookies[REFRESH_COOKIE] != old_refresh and api.cookies[ACCESS_COOKIE] != old_access
    assert api.get(ME).status_code == 200
    assert response.json()["csrfToken"] == security.csrf_token(get_settings(), _session_id(api))

    # the replaced token cannot be used again (and the old access token died with its login)
    replay = api.post(REFRESH, headers={**SAME_ORIGIN, "Cookie": f"{REFRESH_COOKIE}={old_refresh}"})
    assert replay.status_code == 401
    assert api.get(ME, headers={"Cookie": f"{ACCESS_COOKIE}={old_access}"}).status_code == 401


def test_using_a_replaced_token_right_away_is_not_treated_as_theft(api, make_user, db_session):
    """Two browser tabs can refresh at the same moment: the slower one must not end the login."""
    make_user()
    signed_in(api)
    old_refresh = api.cookies[REFRESH_COOKIE]
    api.post(REFRESH, headers=SAME_ORIGIN)  # the first tab wins
    late = api.post(REFRESH, headers={**SAME_ORIGIN, "Cookie": f"{REFRESH_COOKIE}={old_refresh}"})
    assert late.status_code == 401 and late.json()["code"] == "session_replaced"
    assert not late.headers.get_list("set-cookie")  # the first tab's new cookies are left alone
    assert api.get(ME).status_code == 200  # the newest login is still valid
    assert actions(db_session, "refresh_token_reuse") == []


def test_a_replaced_token_used_later_signs_the_person_out_everywhere(api, make_user, db_session):
    user = make_user()
    signed_in(api)
    old_refresh = api.cookies[REFRESH_COOKIE]
    api.post(REFRESH, headers=SAME_ORIGIN)
    assert api.get(ME).status_code == 200  # the legitimate, newest login

    # the copied (old) token is used a minute later: someone stole it
    first = db_session.scalars(select(UserSession).order_by(UserSession.id)).first()
    first.revoked_at = datetime.now(UTC) - timedelta(minutes=1)
    db_session.flush()
    thief = api.post(REFRESH, headers={**SAME_ORIGIN, "Cookie": f"{REFRESH_COOKIE}={old_refresh}"})
    assert thief.status_code == 401 and thief.json()["code"] == "invalid_session"
    assert api.get(ME).status_code == 401  # the legitimate login is ended too
    rows = db_session.scalars(select(UserSession).where(UserSession.user_id == user.id))
    assert all(row.revoked_at for row in rows)
    assert len(actions(db_session, "refresh_token_reuse")) == 1


def test_refresh_without_or_with_a_bad_token_fails_and_clears_cookies(api, make_user):
    make_user()
    assert api.post(REFRESH, headers=SAME_ORIGIN).status_code == 401
    bad = api.post(REFRESH, headers={**SAME_ORIGIN, "Cookie": f"{REFRESH_COOKIE}=garbage"})
    assert bad.status_code == 401 and bad.json() == {
        "detail": "Please sign in again.", "code": "invalid_session"
    }  # fmt: skip
    cleared = " ".join(bad.headers.get_list("set-cookie")).lower()
    assert ACCESS_COOKIE in cleared and REFRESH_COOKIE in cleared and "max-age=0" in cleared


def test_refresh_from_another_website_is_refused(api, make_user):
    make_user()
    signed_in(api)
    response = api.post(REFRESH, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403


def test_refresh_ends_for_accounts_deactivated_meanwhile(api, make_user, db_session):
    user = make_user()
    signed_in(api)
    user.is_active = False
    db_session.flush()
    assert api.post(REFRESH, headers=SAME_ORIGIN).status_code == 401


# ---- sign out ----


def test_logout_ends_the_login_and_clears_the_cookies(api, make_user, db_session):
    make_user()
    signed_in(api)
    access = api.cookies[ACCESS_COOKIE]
    response = api.post(LOGOUT, headers=SAME_ORIGIN)
    assert response.status_code == 204
    cleared = " ".join(response.headers.get_list("set-cookie")).lower()
    assert ACCESS_COOKIE in cleared and REFRESH_COOKIE in cleared and "max-age=0" in cleared
    assert len(actions(db_session, "logout")) == 1
    # the access token, copied before logging out, no longer works
    assert api.get(ME, headers={"Cookie": f"{ACCESS_COOKIE}={access}"}).status_code == 401


def test_logout_always_succeeds_and_checks_the_origin(api, make_user):
    assert api.post(LOGOUT, headers=SAME_ORIGIN).status_code == 204  # nobody signed in
    make_user()
    signed_in(api)
    assert api.post(LOGOUT, headers={"Origin": "https://evil.example"}).status_code == 403
    assert api.get(ME).status_code == 200  # still signed in


# ---- change password ----

NEW_PASSWORD = "tulip granite orbit 4417"


def test_change_password(api, make_user, db_session):
    user = make_user()
    csrf = signed_in(api)
    other_device = sign_in(api)  # a second login for the same person
    assert other_device.status_code == 200
    csrf = signed_in(api)  # the current device
    response = api.post(
        CHANGE_PASSWORD,
        json={"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD},
        headers=changes(csrf),
    )
    assert response.status_code == 204
    assert api.get(ME).status_code == 200  # this device stays signed in
    live = [
        s
        for s in db_session.scalars(select(UserSession).where(UserSession.user_id == user.id))
        if not s.revoked_at
    ]
    assert len(live) == 1  # every other device was signed out
    assert len(actions(db_session, "password_changed")) == 1
    api.cookies.clear()
    assert sign_in(api, password=PASSWORD).status_code == 401
    assert sign_in(api, password=NEW_PASSWORD).status_code == 200


@pytest.mark.parametrize(
    ("new", "code"),
    [("short", "weak_password"), ("Password1234", "weak_password"), (PASSWORD, "weak_password")],
)
def test_weak_or_unchanged_new_passwords_are_refused(api, make_user, new, code):
    make_user()
    csrf = signed_in(api)
    response = api.post(
        CHANGE_PASSWORD,
        json={"currentPassword": PASSWORD, "newPassword": new},
        headers=changes(csrf),
    )
    assert response.status_code == 422 and response.json()["code"] == code


def test_wrong_current_password_counts_towards_the_lockout(api, make_user, db_session):
    user = make_user()
    csrf = signed_in(api)
    for _ in range(5):
        wrong = api.post(
            CHANGE_PASSWORD,
            json={"currentPassword": "not the password", "newPassword": NEW_PASSWORD},
            headers=changes(csrf),
        )
        assert wrong.status_code == 401
    db_session.refresh(user)
    assert user.locked_until is not None  # a stolen session cannot be used to guess the password


def test_change_password_needs_csrf_and_a_session(api, make_user):
    make_user()
    body = {"currentPassword": PASSWORD, "newPassword": NEW_PASSWORD}
    assert api.post(CHANGE_PASSWORD, json=body, headers=SAME_ORIGIN).status_code == 401
    signed_in(api)
    assert api.post(CHANGE_PASSWORD, json=body, headers=SAME_ORIGIN).status_code == 403


# ---- request ids and logs ----


def test_every_response_has_a_request_id(api):
    one, two = api.get("/api/v1/health"), api.get("/api/v1/health")
    assert one.headers["x-request-id"] != two.headers["x-request-id"]
    mine = api.get("/api/v1/health", headers={"X-Request-ID": "trace-1234-abcd"})
    assert mine.headers["x-request-id"] == "trace-1234-abcd"
    odd = api.get("/api/v1/health", headers={"X-Request-ID": "bad id\twith spaces"})
    assert odd.headers["x-request-id"] != "bad id\twith spaces"


def test_logs_contain_no_passwords_tokens_or_e_mail_addresses(api, make_user, db_session, caplog):
    import logging

    logging.getLogger("app").addHandler(caplog.handler)
    try:
        make_user()
        signed_in(api)
        stolen = api.cookies[REFRESH_COOKIE]
        api.post(REFRESH, headers=SAME_ORIGIN)
        first = db_session.scalars(select(UserSession).order_by(UserSession.id)).first()
        first.revoked_at = datetime.now(UTC) - timedelta(minutes=1)
        db_session.flush()
        api.post(REFRESH, headers={**SAME_ORIGIN, "Cookie": f"{REFRESH_COOKIE}={stolen}"})
        sign_in(api, password="wrong password!")
    finally:
        logging.getLogger("app").removeHandler(caplog.handler)
    logged = caplog.text
    assert "refresh token was used again" in logged  # the event itself is logged ...
    for secret in (PASSWORD, "wrong password!", stolen, "staff@example.org"):
        assert secret not in logged  # ... without anything sensitive
