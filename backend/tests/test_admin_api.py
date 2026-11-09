"""Who may reach the staff endpoints: nobody signed out, editors and super admins, and the rule
that a super admin must have two-factor login on."""

import pytest
from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.models import AuditLog
from app.schemas.blocks import SECTION_TYPES
from tests.helpers import changes, code_for, sign_in, signed_in

SCHEMA = "/api/v1/admin/blocks/schema"
USERS = "/api/v1/admin/users"
AUDIT = "/api/v1/admin/audit-log"
ADMIN_PATHS = [SCHEMA, USERS, AUDIT]
SECRET = "JBSWY3DPEHPK3PXP"


@pytest.fixture
def super_admin(make_user):
    """A super admin with two-factor login already on (secret known to the test)."""
    return make_user(
        "boss@example.org", role="super_admin", name="Boss Person",
        totp_enabled=True, totp_secret=security.encrypt_secret(get_settings(), SECRET),
    )  # fmt: skip


def sign_in_super_admin(api) -> str:
    return signed_in(api, email="boss@example.org", totpCode=code_for(SECRET))


@pytest.mark.parametrize("path", ADMIN_PATHS)
def test_nothing_is_available_when_signed_out(api, path):
    response = api.get(path)
    assert response.status_code == 401 and response.json()["code"] == "not_authenticated"


# ---- editors ----


def test_an_editor_gets_the_section_schemas(api, make_user):
    make_user()
    signed_in(api)
    response = api.get(SCHEMA)
    assert response.status_code == 200
    schemas = response.json()
    assert tuple(schemas) == SECTION_TYPES
    hero = schemas["hero"]
    assert hero["label"] and hero["schema"]["required"] == [
        "headline",
        "text",
        "primaryCta",
        "image",
    ]
    assert hero["schema"]["$defs"]["MediaPick"]["x-widget"] == "media"


@pytest.mark.parametrize("path", [USERS, AUDIT])
def test_an_editor_cannot_reach_super_admin_endpoints(api, make_user, path):
    make_user()
    signed_in(api)
    response = api.get(path)
    assert response.status_code == 403 and response.json()["code"] == "forbidden"


def test_demoting_a_super_admin_takes_effect_at_once(api, super_admin, db_session):
    sign_in_super_admin(api)
    assert api.get(USERS).status_code == 200
    super_admin.role = "editor"  # the role is read from the database on every request
    db_session.flush()
    assert api.get(USERS).status_code == 403


# ---- super admins must use two-factor login ----


def test_a_super_admin_without_two_factor_can_only_set_it_up(api, make_user, db_session):
    user = make_user("boss@example.org", role="super_admin")
    csrf = signed_in(api, email="boss@example.org")
    me = api.get("/api/v1/auth/me").json()["user"]
    assert me["needsTotpSetup"] is True and me["totpEnabled"] is False

    for path in ADMIN_PATHS:
        response = api.get(path)
        assert response.status_code == 403 and response.json()["code"] == "totp_setup_required"

    secret = api.post("/api/v1/auth/totp/setup", headers=changes(csrf)).json()["secret"]
    enabled = api.post(
        "/api/v1/auth/totp/enable", json={"code": code_for(secret)}, headers=changes(csrf)
    )
    assert enabled.status_code == 200
    assert api.get(SCHEMA).status_code == 200  # unlocked at once
    assert api.get("/api/v1/auth/me").json()["user"]["needsTotpSetup"] is False
    db_session.refresh(user)
    assert user.totp_enabled


def test_editors_do_not_need_two_factor(api, make_user):
    make_user()
    signed_in(api)
    assert api.get("/api/v1/auth/me").json()["user"]["needsTotpSetup"] is False


# ---- super admin: users and audit log ----


def test_the_user_list_shows_only_safe_fields(api, super_admin, make_user):
    make_user("colleague@example.org", name="Colleague")
    sign_in_super_admin(api)
    response = api.get(USERS)
    assert response.status_code == 200
    users = {u["email"]: u for u in response.json()}
    assert {"boss@example.org", "colleague@example.org"} <= set(users)
    assert users["boss@example.org"]["role"] == "super_admin"
    assert users["colleague@example.org"]["totpEnabled"] is False
    allowed = {
        "id",
        "email",
        "name",
        "role",
        "isActive",
        "totpEnabled",
        "lastLoginAt",
        "lockedUntil",
    }
    for user in users.values():
        assert set(user) <= allowed
    text = response.text.lower()
    for secret in ("hash", "argon", "totpsecret", "recovery", "failed"):
        assert secret not in text


def test_the_audit_log_lists_newest_first_with_paging(api, super_admin, make_user, db_session):
    make_user()
    sign_in(api, password="wrong password!")  # an entry from another person
    sign_in_super_admin(api)
    entries = api.get(AUDIT).json()
    assert entries[0]["action"] == "login" and entries[0]["userId"] == super_admin.id
    ids = [e["id"] for e in entries]
    assert ids == sorted(ids, reverse=True)
    assert any(e["action"] == "login_failed" for e in entries)
    assert all("ip" in e and "createdAt" in e for e in entries[:2])

    page = api.get(AUDIT, params={"limit": 1}).json()
    assert len(page) == 1 and page[0]["id"] == ids[0]
    older = api.get(AUDIT, params={"limit": 1, "before_id": ids[0]}).json()
    assert older[0]["id"] < ids[0]


@pytest.mark.parametrize("query", ["limit=0", "limit=201", "limit=abc", "before_id=0"])
def test_audit_log_paging_is_validated(api, super_admin, query):
    sign_in_super_admin(api)
    assert api.get(f"{AUDIT}?{query}").status_code == 422


def test_audit_entries_never_hold_passwords_or_tokens(api, super_admin, make_user, db_session):
    make_user()
    sign_in(api, password="wrong password!")
    sign_in_super_admin(api)
    rows = list(db_session.scalars(select(AuditLog)))
    assert rows  # something was recorded
    for row in rows:
        assert row.changes is None or not any(
            word in str(row.changes).lower() for word in ("password", "token", "secret", "hash")
        )


# ---- what the admin screens are built from ----


def test_the_edit_forms_are_described_by_json_schemas(editor):
    response = editor.get("/forms/schema")
    assert response.status_code == 200
    forms = response.json()
    assert set(forms) == {"news", "activity", "gallery", "department", "course", "faculty", "page"}
    assert all(form["label"] and form["schema"]["type"] == "object" for form in forms.values())

    news = forms["news"]["schema"]["properties"]
    assert news["body"]["x-widget"] == "richtext"
    cover = next(item for item in news["coverMediaId"]["anyOf"] if item.get("type") == "integer")
    assert cover["x-widget"] == "media-image"
    assert "description" in news["slug"] and news["category"]["$ref"].endswith("NewsCategory")
    defs = forms["news"]["schema"]["$defs"]
    assert defs["NewsAttachmentIn"]["properties"]["mediaId"]["x-widget"] == "media-pdf"
    assert defs["NewsCategory"]["enum"] == ["admission", "notice", "event", "exam", "activity"]
    assert forms["course"]["schema"]["properties"]["departmentId"]["x-widget"] == "department"
    assert forms["course"]["schema"]["additionalProperties"] is False


def test_the_dashboard_summarises_the_site(editor, seeded, db_session):
    from sqlalchemy import select

    from app.models import Enquiry, News

    db_session.add(Enquiry(name="Asha", phone="9876543210", ip_hash="x" * 64))
    db_session.flush()
    first_news = db_session.scalars(select(News).order_by(News.id)).first()
    edited = {
        "title": "Edited by the editor",
        "category": "notice",
        "summary": "s",
        "body": {"type": "doc", "content": [{"type": "paragraph"}]},
        "status": "published",
    }
    assert editor.put(f"/news/{first_news.id}", edited).status_code == 200

    body = editor.get("/dashboard").json()
    assert body["counts"]["newEnquiries"] == 1 and body["counts"]["media"] == 14
    assert body["counts"]["publishedNews"] == 5 and body["counts"]["draftNews"] == 0
    assert body["recentEnquiries"][0]["name"] == "Asha" and "ipHash" not in str(body)
    change = body["recentChanges"][0]
    assert change["entity"] == "news" and change["action"] == "update"
    assert change["label"] == "Edited by the editor" and change["userName"] == "Edith Editor"
