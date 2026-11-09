"""Two-factor login: setup, one-time codes, replay protection, recovery codes, turning it off."""

import re

import pytest
from sqlalchemy import select

from app.api.cookies import ACCESS_COOKIE
from app.core import security
from app.core.config import get_settings
from app.models import AuditLog
from tests.conftest import PASSWORD
from tests.helpers import changes, code_for, secret_of, sign_in, signed_in

SETUP = "/api/v1/auth/totp/setup"
ENABLE = "/api/v1/auth/totp/enable"
DISABLE = "/api/v1/auth/totp/disable"


def turn_on(api, user, csrf) -> list[str]:
    """Sets up and enables two-factor login; returns the recovery codes."""
    secret = api.post(SETUP, headers=changes(csrf)).json()["secret"]
    response = api.post(ENABLE, json={"code": code_for(secret)}, headers=changes(csrf))
    assert response.status_code == 200, response.text
    return response.json()["recoveryCodes"]


@pytest.fixture
def protected(api, make_user, db_session):
    """An editor with two-factor login switched on, signed out again."""
    user = make_user()
    csrf = signed_in(api)
    codes = turn_on(api, user, csrf)
    api.cookies.clear()
    return user, codes


def actions(db, name):
    return list(db.scalars(select(AuditLog).where(AuditLog.action == name)))


# ---- setup ----


def test_setup_gives_a_secret_and_a_qr_address_and_stores_the_secret_encrypted(
    api, make_user, db_session
):
    user = make_user()
    csrf = signed_in(api)
    response = api.post(SETUP, headers=changes(csrf))
    assert response.status_code == 200
    body = response.json()
    assert re.fullmatch(r"[A-Z2-7]{32}", body["secret"])
    assert body["otpauthUri"].startswith("otpauth://totp/")
    assert (
        "issuer=VRR+Degree+College" in body["otpauthUri"]
        or "issuer=VRR%20Degree%20College" in body["otpauthUri"]
    )  # noqa: E501
    assert f"secret={body['secret']}" in body["otpauthUri"]
    db_session.refresh(user)
    assert user.totp_secret and body["secret"] not in user.totp_secret  # never stored in clear
    assert secret_of(user) == body["secret"]
    assert user.totp_enabled is False
    assert sign_in(api).status_code == 200  # not active until the first code is confirmed


def test_enabling_needs_a_correct_code_and_gives_recovery_codes(api, make_user, db_session):
    user = make_user()
    csrf = signed_in(api)
    secret = api.post(SETUP, headers=changes(csrf)).json()["secret"]
    wrong = api.post(ENABLE, json={"code": "000000"}, headers=changes(csrf))
    assert wrong.status_code == 400 and wrong.json()["code"] == "invalid_code"
    db_session.refresh(user)
    assert user.totp_enabled is False

    right = api.post(ENABLE, json={"code": code_for(secret)}, headers=changes(csrf))
    assert right.status_code == 200
    codes = right.json()["recoveryCodes"]
    assert len(codes) == 8 and len(set(codes)) == 8
    assert all(re.fullmatch(r"[0-9a-f]{6}-[0-9a-f]{6}", code) for code in codes)
    db_session.refresh(user)
    assert user.totp_enabled is True and len(user.recovery_codes) == 8
    stored = " ".join(user.recovery_codes)
    assert not any(
        code.replace("-", "") in stored or code in stored for code in codes
    )  # hashes only
    assert len(actions(db_session, "totp_enabled")) == 1


def test_enable_without_setup_and_setup_twice_are_refused(api, make_user):
    user = make_user()
    csrf = signed_in(api)
    early = api.post(ENABLE, json={"code": "123456"}, headers=changes(csrf))
    assert early.status_code == 409 and early.json()["code"] == "totp_not_pending"
    turn_on(api, user, csrf)
    again = api.post(SETUP, headers=changes(csrf))
    assert again.status_code == 409 and again.json()["code"] == "totp_already_enabled"


def test_setup_needs_a_session_and_the_csrf_token(api, make_user):
    make_user()
    assert api.post(SETUP, headers={"Origin": "http://localhost"}).status_code == 401
    signed_in(api)
    assert api.post(SETUP, headers={"Origin": "http://localhost"}).status_code == 403


# ---- signing in with a code ----


def test_sign_in_asks_for_the_code_and_accepts_the_right_one(api, protected, db_session):
    user, _ = protected
    secret = secret_of(user)

    missing = sign_in(api)
    assert missing.status_code == 401 and missing.json()["code"] == "totp_required"
    assert ACCESS_COOKIE not in api.cookies
    db_session.refresh(user)
    assert user.failed_logins == 0  # asking for the code is not a failure

    wrong = sign_in(api, totpCode="000000")
    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"
    db_session.refresh(user)
    assert user.failed_logins == 1

    ok = sign_in(api, totpCode=code_for(secret, 1))  # the next step: later than the setup code
    assert ok.status_code == 200 and ok.json()["user"]["totpEnabled"] is True


def test_a_wrong_password_is_still_refused_with_a_correct_code(api, protected):
    user, _ = protected
    wrong = sign_in(api, password="wrong password!", totpCode=code_for(secret_of(user), 1))
    assert wrong.status_code == 401 and wrong.json()["code"] == "invalid_credentials"


@pytest.mark.parametrize("bad", ["12345", "1234567", "abcdef", "12 34", "١٢٣٤٥٦", "123456; DROP"])
def test_malformed_codes_are_refused(api, protected, bad):
    assert sign_in(api, totpCode=bad).status_code == 401


def test_spaces_in_a_code_are_ignored(api, protected):
    user, _ = protected
    code = code_for(secret_of(user), 1)
    assert sign_in(api, totpCode=f"{code[:3]} {code[3:]}").status_code == 200


def test_a_code_cannot_be_used_twice(api, protected, db_session):
    user, _ = protected
    code = code_for(secret_of(user), 1)
    assert sign_in(api, totpCode=code).status_code == 200
    api.cookies.clear()
    replay = sign_in(api, totpCode=code)
    assert replay.status_code == 401 and replay.json()["code"] == "invalid_credentials"
    assert ACCESS_COOKIE not in api.cookies


def test_the_code_from_the_setup_cannot_be_reused_to_sign_in(api, protected):
    user, _ = protected
    assert sign_in(api, totpCode=code_for(secret_of(user), 0)).status_code == 401


@pytest.mark.parametrize(
    ("offset", "accepted"), [(-2, False), (-1, True), (0, True), (1, True), (2, False)]
)
def test_codes_are_accepted_one_step_either_side_for_clock_drift(
    api, protected, db_session, offset, accepted
):
    user, _ = protected
    user.totp_last_step = None  # (forget the setup code, to test the time window on its own)
    db_session.flush()
    response = sign_in(api, totpCode=code_for(secret_of(user), offset))
    assert (response.status_code == 200) is accepted


def test_five_wrong_codes_lock_the_account(api, protected, db_session, proxied):
    user, _ = protected
    for n in range(5):
        assert sign_in(api, totpCode="000000", ip=f"10.2.0.{n}").status_code == 401
    db_session.refresh(user)
    assert user.locked_until is not None
    right = sign_in(api, totpCode=code_for(secret_of(user), 1), ip="10.2.0.99")
    assert right.status_code == 401  # locked, even with a correct code


# ---- recovery codes ----


def test_a_recovery_code_works_once(api, protected, db_session):
    user, codes = protected
    ok = sign_in(api, recoveryCode=codes[0])
    assert ok.status_code == 200
    db_session.refresh(user)
    assert len(user.recovery_codes) == 7
    api.cookies.clear()
    again = sign_in(api, recoveryCode=codes[0])
    assert again.status_code == 401 and again.json()["code"] == "invalid_credentials"
    assert sign_in(api, recoveryCode=codes[1]).status_code == 200  # the others still work


def test_recovery_codes_ignore_case_and_hyphens_and_wrong_ones_are_counted(
    api, protected, db_session
):
    user, codes = protected
    assert sign_in(api, recoveryCode="ffffff-ffffff").status_code == 401
    db_session.refresh(user)
    assert user.failed_logins == 1
    messy = codes[2].replace("-", "").upper()
    assert sign_in(api, recoveryCode=f" {messy} ").status_code == 200


# ---- turning it off ----


def test_an_editor_can_turn_two_factor_off_with_password_and_code(api, protected, db_session):
    user, _ = protected
    secret = secret_of(user)
    csrf = signed_in(api, totpCode=code_for(secret, 1))
    user.totp_last_step = None  # (so the next code can be taken from the current time window)
    db_session.flush()

    wrong_password = api.post(
        DISABLE,
        json={"password": "wrong password!", "code": code_for(secret)},
        headers=changes(csrf),
    )
    assert wrong_password.status_code == 401
    wrong_code = api.post(
        DISABLE, json={"password": PASSWORD, "code": "000000"}, headers=changes(csrf)
    )
    assert wrong_code.status_code == 401
    db_session.refresh(user)
    assert user.totp_enabled is True and user.failed_logins == 2

    done = api.post(
        DISABLE, json={"password": PASSWORD, "code": code_for(secret)}, headers=changes(csrf)
    )
    assert done.status_code == 204
    db_session.refresh(user)
    assert user.totp_enabled is False and user.totp_secret is None and user.recovery_codes == []
    assert len(actions(db_session, "totp_disabled")) == 1
    api.cookies.clear()
    assert sign_in(api).status_code == 200  # no code needed any more


def test_a_super_admin_cannot_turn_two_factor_off(api, make_user):
    make_user(role="super_admin")
    csrf = signed_in(api)
    secret = api.post(SETUP, headers=changes(csrf)).json()["secret"]
    api.post(ENABLE, json={"code": code_for(secret)}, headers=changes(csrf))
    response = api.post(
        DISABLE, json={"password": PASSWORD, "code": code_for(secret, 1)}, headers=changes(csrf)
    )
    assert response.status_code == 403 and response.json()["code"] == "totp_required_for_role"


def test_disable_when_it_is_not_on(api, make_user):
    make_user()
    csrf = signed_in(api)
    response = api.post(
        DISABLE, json={"password": PASSWORD, "code": "123456"}, headers=changes(csrf)
    )
    assert response.status_code == 409 and response.json()["code"] == "totp_not_enabled"


# ---- secrets never leave the server ----


def test_the_secret_is_never_returned_after_setup(api, protected):
    user, _ = protected
    secret = secret_of(user)
    signed_in(api, totpCode=code_for(secret, 1))
    me = api.get("/api/v1/auth/me")
    assert secret not in me.text and "recovery" not in me.text.lower()
    assert security.encrypt_secret(get_settings(), "x")  # (the encryption key is configured)
