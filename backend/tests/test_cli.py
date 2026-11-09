"""The administrator's command-line tools."""

import sys
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app import cli
from app.core import security
from app.models import AuditLog, User, UserSession
from app.services.auth import start_session
from tests.conftest import PASSWORD


class _Same:
    """Makes `with SessionLocal() as db` hand out the test's own (rolled-back) session."""

    def __init__(self, db):
        self.db = db

    def __call__(self):
        return self

    def __enter__(self):
        return self.db

    def __exit__(self, *_):
        return False


@pytest.fixture(autouse=True)
def _use_test_session(monkeypatch, db_session):
    monkeypatch.setattr(cli, "SessionLocal", _Same(db_session))
    monkeypatch.setenv("ADMIN_PASSWORD", PASSWORD)


def user_by_email(db, email):
    return db.scalar(select(User).where(User.email == email))


def test_create_admin(db_session, capsys):
    assert (
        cli.create_admin(email=" New.Boss@Example.org ", name="New Boss", role="super_admin") == 0
    )
    user = user_by_email(db_session, "new.boss@example.org")
    assert user.role == "super_admin" and user.name == "New Boss" and user.is_active
    assert (
        security.verify_password(user.password_hash, PASSWORD)
        and PASSWORD not in user.password_hash
    )
    assert user.totp_enabled is False
    assert "turn on two-factor" in capsys.readouterr().out
    entry = db_session.scalars(select(AuditLog).where(AuditLog.action == "user_created_cli")).one()
    assert entry.user_id == user.id


def test_an_editor_can_be_created(db_session, capsys):
    assert cli.create_admin(email="ed@example.org", name="Ed", role="editor") == 0
    assert user_by_email(db_session, "ed@example.org").role == "editor"
    assert "two-factor" not in capsys.readouterr().out


@pytest.mark.parametrize(
    "email", ["", "no-at-sign", "a@b", "a b@c.de", "<x>@y.zz", "x@" + "y" * 260 + ".com"]
)
def test_invalid_e_mail_is_refused(email, capsys):
    assert cli.create_admin(email=email, name="Name", role="editor") == 1
    assert "not valid" in capsys.readouterr().err


@pytest.mark.parametrize("name", ["", "   ", "x" * 81])
def test_invalid_name_is_refused(name, capsys):
    assert cli.create_admin(email="a@example.org", name=name, role="editor") == 1
    assert "name" in capsys.readouterr().err


def test_duplicate_account_is_refused(make_user, capsys):
    make_user("taken@example.org")
    assert cli.create_admin(email="TAKEN@example.org", name="Other", role="editor") == 1
    assert "already exists" in capsys.readouterr().err


def test_weak_password_is_refused(monkeypatch, db_session, capsys):
    monkeypatch.setenv("ADMIN_PASSWORD", "short")
    assert cli.create_admin(email="weak@example.org", name="Weak", role="editor") == 1
    assert "at least 12" in capsys.readouterr().err
    assert user_by_email(db_session, "weak@example.org") is None


def test_typed_passwords_must_match(monkeypatch, db_session, capsys):
    monkeypatch.delenv("ADMIN_PASSWORD")
    answers = iter([PASSWORD, PASSWORD + "x"])
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: next(answers))
    assert cli.create_admin(email="typo@example.org", name="Typo", role="editor") == 1
    assert "different" in capsys.readouterr().err
    assert user_by_email(db_session, "typo@example.org") is None


def test_typed_password_is_used_when_no_variable_is_set(monkeypatch, db_session):
    monkeypatch.delenv("ADMIN_PASSWORD")
    monkeypatch.setattr(cli.getpass, "getpass", lambda _prompt: "another long password 77")
    assert cli.create_admin(email="typed@example.org", name="Typed", role="editor") == 0
    user = user_by_email(db_session, "typed@example.org")
    assert security.verify_password(user.password_hash, "another long password 77")


def test_reset_password_unlocks_and_signs_out_everywhere(
    make_user, db_session, monkeypatch, capsys
):
    user = make_user(failed_logins=3, locked_until=datetime.now(UTC) + timedelta(minutes=10))
    from app.core.config import get_settings

    session, _ = start_session(db_session, get_settings(), user, ip="1.2.3.4", user_agent="test")
    monkeypatch.setenv("ADMIN_PASSWORD", "a brand new password 55")
    assert cli.reset_password(email="STAFF@example.org") == 0
    db_session.refresh(user)
    db_session.refresh(session)
    assert security.verify_password(user.password_hash, "a brand new password 55")
    assert user.failed_logins == 0 and user.locked_until is None
    assert session.revoked_at is not None
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "password_reset_cli")).one()
    assert "signed out everywhere" in capsys.readouterr().out
    assert db_session.scalars(select(UserSession)).first().revoked_at is not None


def test_reset_password_for_an_unknown_account(capsys):
    assert cli.reset_password(email="nobody@example.org") == 1
    assert "No account" in capsys.readouterr().err


def test_command_line_parsing(monkeypatch, db_session):
    monkeypatch.setattr(
        sys,
        "argv",
        ["cli", "create-admin", "--email", "arg@example.org", "--name", "Arg", "--role", "editor"],
    )
    assert cli.main() == 0 and user_by_email(db_session, "arg@example.org").role == "editor"
    monkeypatch.setattr(
        sys, "argv", ["cli", "create-admin", "--email", "x@y.zz", "--name", "X", "--role", "owner"]
    )
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 2  # an unknown role is rejected by the parser


def test_the_default_role_is_super_admin(monkeypatch, db_session):
    monkeypatch.setattr(
        sys, "argv", ["cli", "create-admin", "--email", "def@example.org", "--name", "Def"]
    )
    assert cli.main() == 0 and user_by_email(db_session, "def@example.org").role == "super_admin"


# ---- the ready-made development account ----


def dev_settings(monkeypatch, **changes):
    from app.core.config import Settings

    values = {"env": "dev", "dev_admin_email": "Admin@Gmail.com", "dev_admin_password": "vrr@123"}
    monkeypatch.setattr(cli, "get_settings", lambda: Settings(**{**values, **changes}))


def test_the_dev_account_is_created_with_its_short_password(monkeypatch, db_session, capsys):
    dev_settings(monkeypatch)
    assert cli.ensure_dev_admin() == 0
    user = user_by_email(db_session, "admin@gmail.com")
    assert user.role == "super_admin" and user.is_active and user.totp_enabled is False
    assert security.verify_password(user.password_hash, "vrr@123")
    assert "vrr@123" not in user.password_hash and "vrr@123" not in capsys.readouterr().out
    assert db_session.scalars(select(AuditLog).where(AuditLog.action == "user_created_dev")).one()


def test_the_dev_account_can_sign_in_but_must_set_up_two_factor_first(api, monkeypatch):
    from tests.helpers import sign_in

    dev_settings(monkeypatch)
    cli.ensure_dev_admin()
    response = sign_in(api, email="admin@gmail.com", password="vrr@123")
    assert response.status_code == 200 and response.json()["user"]["needsTotpSetup"] is True
    assert sign_in(api, email="admin@gmail.com", password="vrr@1234").status_code == 401


def test_the_dev_account_is_never_changed_once_it_exists(monkeypatch, db_session, capsys):
    dev_settings(monkeypatch)
    cli.ensure_dev_admin()
    user = user_by_email(db_session, "admin@gmail.com")
    user.name, user.password_hash = "Renamed", security.hash_password(PASSWORD)
    db_session.flush()
    assert cli.ensure_dev_admin() == 0 and "already exists" in capsys.readouterr().out
    again = user_by_email(db_session, "admin@gmail.com")
    assert again.name == "Renamed" and security.verify_password(again.password_hash, PASSWORD)
    assert len(db_session.scalars(select(User).where(User.email == "admin@gmail.com")).all()) == 1


@pytest.mark.parametrize(
    "changes", [{"dev_admin_email": ""}, {"dev_admin_password": None}, {"dev_admin_password": ""}]
)
def test_nothing_is_created_unless_both_are_set(monkeypatch, db_session, changes):
    dev_settings(monkeypatch, **changes)
    assert cli.ensure_dev_admin() == 0
    assert db_session.scalars(select(User)).all() == []


def test_a_wrong_dev_email_is_refused(monkeypatch, db_session, capsys):
    dev_settings(monkeypatch, dev_admin_email="not-an-email")
    assert cli.ensure_dev_admin() == 1 and db_session.scalars(select(User)).all() == []
    assert "skipped" in capsys.readouterr().out


def test_production_refuses_to_start_with_a_dev_account_set():
    from pydantic import ValidationError

    from app.core.config import Settings

    long_key = "k" * 40
    with pytest.raises(ValidationError, match="must be empty when ENV=prod"):
        Settings(env="prod", secret_key=long_key, dev_admin_email="admin@gmail.com")
    with pytest.raises(ValidationError, match="must be empty when ENV=prod"):
        Settings(env="prod", secret_key=long_key, dev_admin_password="vrr@123")
    # fine without them (the values in the local .env file are set aside here on purpose)
    Settings(env="prod", secret_key=long_key, dev_admin_email="", dev_admin_password=None)


def test_the_normal_way_still_refuses_a_short_password(monkeypatch, capsys):
    monkeypatch.setenv("ADMIN_PASSWORD", "vrr@123")
    assert cli.create_admin(email="x@example.org", name="X", role="editor") == 1
    assert "at least 12" in capsys.readouterr().err
