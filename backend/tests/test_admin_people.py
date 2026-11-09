"""Staff accounts (super admin) and enquiries (all staff), including the CSV export."""

import csv
import io
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.models import AuditLog, Enquiry, User, UserSession
from tests.conftest import PASSWORD
from tests.helpers import sign_in

NEW_PASSWORD = "granite tulip orbit 2210"


def audit_actions(db, name: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == name)))


# ============================ accounts ============================


def test_only_super_admins_manage_accounts(editor, make_user):
    victim = make_user("victim@example.org")
    calls = [
        editor.get("/users"),
        editor.post("/users", {"email": "n@example.org", "name": "N", "password": NEW_PASSWORD}),
        editor.put(f"/users/{victim.id}", {"isActive": False}),
        editor.post(f"/users/{victim.id}/reset-password", {"newPassword": NEW_PASSWORD}),
        editor.post(f"/users/{victim.id}/reset-two-factor"),
    ]
    assert all(call.status_code == 403 and call.json()["code"] == "forbidden" for call in calls)


def test_a_super_admin_creates_an_account_that_can_sign_in(boss, api, db_session):
    made = boss.post(
        "/users",
        {"email": "  New.Editor@Example.org ", "name": "New Editor", "password": NEW_PASSWORD},
    )
    assert made.status_code == 201, made.text
    body = made.json()
    assert body["email"] == "new.editor@example.org" and body["role"] == "editor"
    assert body["isActive"] is True and body["totpEnabled"] is False
    assert "password" not in made.text.lower() and "hash" not in made.text.lower()
    user = db_session.get(User, body["id"])
    assert (
        security.verify_password(user.password_hash, NEW_PASSWORD)
        and NEW_PASSWORD not in user.password_hash
    )
    assert sign_in(api, email="new.editor@example.org", password=NEW_PASSWORD).status_code == 200
    assert [e.changes for e in audit_actions(db_session, "user_create")] == [{"role": "editor"}]


@pytest.mark.parametrize(
    ("changes", "status", "code"),
    [
        ({"password": "short"}, 422, "weak_password"),
        ({"password": "Password1234"}, 422, "weak_password"),
        ({"email": "taken@example.org"}, 409, "email_taken"),
        ({"email": "not-an-email"}, 422, "validation_error"),
        ({"role": "owner"}, 422, "validation_error"),
        ({"name": ""}, 422, "validation_error"),
    ],
)
def test_account_creation_is_checked(boss, make_user, changes, status, code):
    make_user("taken@example.org")
    body = {
        "email": "fresh@example.org",
        "name": "Fresh Person",
        "password": NEW_PASSWORD,
        **changes,
    }
    response = boss.post("/users", body)
    assert response.status_code == status and response.json()["code"] == code


def test_a_password_containing_the_persons_name_is_refused(boss):
    body = {
        "email": "asha.reddy@example.org",
        "name": "Asha Reddy",
        "password": "my-asha-is-great-1",
    }
    assert boss.post("/users", body).json()["code"] == "weak_password"


def test_accounts_can_be_renamed_promoted_and_switched_off(boss, make_user, db_session):
    user = make_user("staff2@example.org")
    done = boss.put(f"/users/{user.id}", {"name": "Renamed", "role": "super_admin"})
    assert (
        done.status_code == 200
        and done.json()["name"] == "Renamed"
        and done.json()["role"] == "super_admin"
    )
    assert audit_actions(db_session, "user_update")[0].changes == {"fields": ["name", "role"]}
    assert boss.put(f"/users/{user.id}", {}).status_code == 422
    assert boss.put(f"/users/{user.id}", {"role": "owner"}).status_code == 422
    assert boss.put("/users/999999999", {"name": "X"}).status_code == 404


def test_switching_an_account_off_signs_it_out_at_once(boss, api, make_user, db_session):
    user = make_user("leaving@example.org")
    assert sign_in(api, email="leaving@example.org").status_code == 200
    assert api.get("/api/v1/auth/me").status_code == 200
    boss.put(f"/users/{user.id}", {"isActive": False})
    assert api.get("/api/v1/auth/me").status_code == 401
    assert sign_in(api, email="leaving@example.org").status_code == 401
    assert all(
        s.revoked_at
        for s in db_session.scalars(select(UserSession).where(UserSession.user_id == user.id))
    )
    assert boss.put(f"/users/{user.id}", {"isActive": True}).json()["isActive"] is True
    assert sign_in(api, email="leaving@example.org").status_code == 200


def test_a_super_admin_cannot_change_their_own_role_or_switch_themselves_off(boss, db_session):
    me = db_session.scalars(select(User).where(User.email == "boss@example.org")).one()
    for change in ({"isActive": False}, {"role": "editor"}):
        response = boss.put(f"/users/{me.id}", change)
        assert response.status_code == 403 and response.json()["code"] == "cannot_change_self"
    assert (
        boss.put(f"/users/{me.id}", {"name": "Still Boss"}).status_code == 200
    )  # the name is fine


def test_another_super_admin_can_be_demoted_while_one_remains(boss, make_user):
    other = make_user("other.boss@example.org", role="super_admin")
    assert boss.put(f"/users/{other.id}", {"role": "editor"}).json()["role"] == "editor"


def test_the_last_super_admin_guard_counts_the_others(db_session, make_user):
    from app.api.v1.admin_people import _other_active_super_admins

    first = make_user("a@example.org", role="super_admin")
    assert _other_active_super_admins(db_session, first.id) == 0  # (no other super admin)
    second = make_user("b@example.org", role="super_admin")
    make_user("c@example.org", role="super_admin", is_active=False)  # switched off: not counted
    make_user("d@example.org", role="editor")  # not a super admin
    assert _other_active_super_admins(db_session, first.id) >= 1
    assert _other_active_super_admins(db_session, second.id) >= 1


def test_reset_password_unlocks_and_signs_out(boss, api, make_user, db_session):
    user = make_user(
        "forgot@example.org",
        failed_logins=4,
        locked_until=datetime.now(UTC) + timedelta(minutes=10),
    )
    done = boss.post(f"/users/{user.id}/reset-password", {"newPassword": NEW_PASSWORD})
    assert done.status_code == 204
    db_session.refresh(user)
    assert user.failed_logins == 0 and user.locked_until is None
    assert sign_in(api, email="forgot@example.org", password=PASSWORD).status_code == 401
    assert sign_in(api, email="forgot@example.org", password=NEW_PASSWORD).status_code == 200
    assert len(audit_actions(db_session, "user_password_reset")) == 1
    weak = boss.post(f"/users/{user.id}/reset-password", {"newPassword": "short"})
    assert weak.status_code == 422 and weak.json()["code"] == "weak_password"


def test_a_super_admin_uses_change_password_for_themselves(boss, db_session):
    me = db_session.scalars(select(User).where(User.email == "boss@example.org")).one()
    assert (
        boss.post(f"/users/{me.id}/reset-password", {"newPassword": NEW_PASSWORD}).status_code
        == 403
    )
    assert boss.post(f"/users/{me.id}/reset-two-factor").status_code == 403


def test_reset_two_factor_for_a_lost_phone(boss, api, make_user, db_session):
    user = make_user(
        "lostphone@example.org",
        totp_enabled=True,
        recovery_codes=["abc"],
        totp_secret=security.encrypt_secret(get_settings(), "JBSWY3DPEHPK3PXP"),
    )
    assert sign_in(api, email="lostphone@example.org").json()["code"] == "totp_required"
    assert boss.post(f"/users/{user.id}/reset-two-factor").status_code == 204
    db_session.refresh(user)
    assert user.totp_enabled is False and user.totp_secret is None and user.recovery_codes == []
    assert sign_in(api, email="lostphone@example.org").status_code == 200  # no code needed now
    assert len(audit_actions(db_session, "user_two_factor_reset")) == 1


def test_a_super_admin_whose_two_factor_was_reset_must_set_it_up_again(
    boss, api, make_user, db_session
):
    other = make_user("other.admin@example.org", role="super_admin")
    boss.post(f"/users/{other.id}/reset-two-factor")
    me = sign_in(api, email="other.admin@example.org").json()["user"]
    assert me["needsTotpSetup"] is True
    assert api.get("/api/v1/admin/blocks/schema").status_code == 403


# ============================ enquiries ============================


def enquiry(db, name="Asha Reddy", **fields) -> Enquiry:
    row = Enquiry(name=name, phone=fields.pop("phone", "9876543210"), ip_hash="x" * 64, **fields)
    db.add(row)
    db.flush()
    return row


@pytest.fixture(autouse=True)
def _blank_enquiries(db_session):
    from sqlalchemy import delete

    db_session.execute(delete(Enquiry))
    db_session.flush()


def test_enquiries_are_listed_newest_first_and_can_be_searched(editor, db_session):
    first = enquiry(db_session, "Asha Reddy", course="B.Sc Computer Science", message="Fees please")
    second = enquiry(
        db_session, "Ravi Kumar", phone="9123456780", course="B.Com", status="contacted"
    )
    third = enquiry(db_session, "Meena 100% Sure", message="call after 5")
    listed = editor.get("/enquiries").json()
    assert [e["id"] for e in listed] == [third.id, second.id, first.id]
    assert listed[0]["status"] == "new" and "ipHash" not in str(listed)  # the hash never leaves
    assert [e["id"] for e in editor.get("/enquiries", status="contacted").json()] == [second.id]
    assert [e["id"] for e in editor.get("/enquiries", q="ravi").json()] == [second.id]
    assert [e["id"] for e in editor.get("/enquiries", q="9123456780").json()] == [second.id]
    assert [e["id"] for e in editor.get("/enquiries", q="computer").json()] == [first.id]
    assert [e["id"] for e in editor.get("/enquiries", q="100%").json()] == [third.id]
    assert editor.get("/enquiries", q="R%vi").json() == []  # "%" means itself
    page = editor.get("/enquiries", limit=1).json()
    older = editor.get("/enquiries", limit=1, before_id=page[0]["id"]).json()
    assert [page[0]["id"], older[0]["id"]] == [third.id, second.id]
    for query in (
        {"limit": 0},
        {"limit": 201},
        {"before_id": 0},
        {"status": "spam"},
        {"q": "x" * 101},
    ):
        assert editor.get("/enquiries", **query).status_code == 422


def test_staff_record_who_followed_up(editor, db_session):
    row = enquiry(db_session)
    done = editor.patch(f"/enquiries/{row.id}", {"status": "contacted"})
    assert done.status_code == 200 and done.json()["status"] == "contacted"
    assert done.json()["handledBy"] and done.json()["handledAt"]
    reopened = editor.patch(f"/enquiries/{row.id}", {"status": "new"})
    assert reopened.json()["status"] == "new" and "handledBy" not in reopened.json()
    assert editor.patch(f"/enquiries/{row.id}", {"status": "spam"}).status_code == 422
    assert editor.patch("/enquiries/999999999", {"status": "closed"}).status_code == 404
    assert [e.changes for e in audit_actions(db_session, "enquiry_update")] == [
        {"status": "contacted"},
        {"status": "new"},
    ]


def test_enquiries_need_staff(api, db_session):
    assert api.get("/api/v1/admin/enquiries").status_code == 401
    assert api.get("/api/v1/admin/enquiries/export.csv").status_code == 401


def read_csv(response) -> list[list[str]]:
    assert response.text.startswith("﻿")  # so Excel reads names in any language correctly
    return list(csv.reader(io.StringIO(response.text.lstrip("﻿"))))


def test_the_csv_export(editor, db_session):
    enquiry(
        db_session,
        "Asha Reddy",
        course="B.Sc Computer Science",
        message="Fees, please\nthanks",
        source_page="/admissions",
    )
    enquiry(db_session, "Ravi Kumar", status="closed")
    response = editor.api.get("/api/v1/admin/enquiries/export.csv")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"].startswith('attachment; filename="enquiries-')
    assert response.headers["content-disposition"].endswith('.csv"')
    rows = read_csv(response)
    assert rows[0] == [
        "Received",
        "Name",
        "Phone",
        "Course",
        "Message",
        "Status",
        "Page",
        "Handled",
    ]
    assert [r[1] for r in rows[1:]] == ["Ravi Kumar", "Asha Reddy"]  # newest first
    assert (
        rows[2][4] == "Fees, please\nthanks" and rows[2][6] == "/admissions"
    )  # commas and new lines survive
    assert "ipHash" not in response.text and "xxxxxxxx" not in response.text
    filtered = read_csv(
        editor.api.get("/api/v1/admin/enquiries/export.csv", params={"status": "closed"})
    )
    assert [r[1] for r in filtered[1:]] == ["Ravi Kumar"]


@pytest.mark.parametrize(
    "dangerous", ['=HYPERLINK("http://evil","x")', "+1+1", "-2+3", "@SUM(A1)", "\tcmd", "\rcmd"]
)
def test_the_csv_cannot_run_formulas_in_a_spreadsheet(editor, db_session, dangerous):
    enquiry(db_session, name=dangerous, message=dangerous, course=dangerous)
    rows = read_csv(editor.api.get("/api/v1/admin/enquiries/export.csv"))
    for cell in rows[1][1:5]:
        if cell and cell != "9876543210":
            assert cell.startswith("'") and cell[1] == dangerous[0]  # plain text, not a formula


def test_every_export_is_recorded(editor, boss, db_session):
    enquiry(db_session)
    editor.api.get("/api/v1/admin/enquiries/export.csv")
    entry = audit_actions(db_session, "enquiries_export")[0]
    assert entry.changes == {"count": 1} and entry.user_id
    assert "Asha" not in str(entry.changes)


def test_old_enquiries_are_deleted_by_the_privacy_command(db_session, monkeypatch, capsys):
    from app import cli
    from tests.test_cli import _Same

    monkeypatch.setattr(cli, "SessionLocal", _Same(db_session))
    old = enquiry(db_session, "Old Enquiry")
    old.created_at = datetime.now(UTC) - timedelta(days=400)
    recent = enquiry(db_session, "Recent Enquiry")
    db_session.flush()
    assert cli.purge_enquiries(days=365, dry_run=True) == 0
    assert "Would delete 1" in capsys.readouterr().out and db_session.get(Enquiry, old.id)
    assert cli.purge_enquiries(days=365, dry_run=False) == 0
    assert "Deleted 1" in capsys.readouterr().out
    assert db_session.get(Enquiry, old.id) is None and db_session.get(Enquiry, recent.id)
    assert audit_actions(db_session, "enquiries_purged")[0].changes == {"count": 1, "days": 365}


def test_reset_two_factor_command(db_session, make_user, monkeypatch, capsys):
    from app import cli
    from tests.test_cli import _Same

    monkeypatch.setattr(cli, "SessionLocal", _Same(db_session))
    user = make_user("phone@example.org", totp_enabled=True, totp_secret="x", recovery_codes=["a"])
    assert cli.reset_two_factor(email=" PHONE@example.org ") == 0
    db_session.refresh(user)
    assert user.totp_enabled is False and user.totp_secret is None and user.recovery_codes == []
    assert cli.reset_two_factor(email="nobody@example.org") == 1
