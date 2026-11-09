from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core import security
from app.core.config import get_settings
from app.db.session import engine, get_db
from app.main import app
from app.models import (
    Activity,
    ActivityPhoto,
    AuditLog,
    ContentRevision,
    Course,
    Department,
    Enquiry,
    Faculty,
    GalleryItem,
    Media,
    News,
    NewsAttachment,
    Page,
    PageSection,
    Redirect,
    SiteSetting,
    User,
    UserSession,
)
from app.seed.loader import load_seed
from app.services import revalidate


@pytest.fixture(scope="session")
def client() -> Iterator[TestClient]:
    # "localhost" is an allowed host; the default "testserver" would be rejected.
    with TestClient(app, base_url="http://localhost") as test_client:
        yield test_client


@pytest.fixture
def db_session() -> Iterator[Session]:
    """A session whose changes are rolled back after the test, so tests never leave data behind."""
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    # Real accounts, logins and logs may exist in the development database. Every test starts
    # without them (removed inside the transaction, which is rolled back), so results never
    # depend on what was done by hand.
    for model in (UserSession, AuditLog, ContentRevision, Redirect, Enquiry, User):
        session.execute(delete(model))
    session.flush()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def api(db_session: Session) -> Iterator[TestClient]:
    """Test client that uses the rolled-back session instead of the real one."""
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        with TestClient(app, base_url="http://localhost") as test_client:
            yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def empty_content(db_session: Session) -> Session:
    """Removes all site content inside the test's transaction (rolled back afterwards), so a test
    starts from a known state whatever the development database contains."""
    for model in (
        ActivityPhoto,
        Activity,
        NewsAttachment,
        News,
        GalleryItem,
        PageSection,
        Page,
        Faculty,
        Course,
        Department,
        SiteSetting,
        Redirect,
        ContentRevision,
        Media,
    ):
        db_session.execute(delete(model))
    db_session.flush()
    return db_session


@pytest.fixture
def seeded(empty_content: Session, tmp_path) -> Session:
    """The starter content, loaded into the empty state (photo files go to a temporary folder)."""
    load_seed(empty_content, tmp_path, make_copies=False)  # (resizing every test would be slow)
    return empty_content


PASSWORD = "correct horse battery staple"


@pytest.fixture(autouse=True)
def _ignore_the_local_dev_account(monkeypatch: pytest.MonkeyPatch) -> None:
    """The local .env may hold DEV_ADMIN_* (a ready-made account for trying the site). Tests must
    not depend on it: with it set, a "prod" Settings object correctly refuses to load."""
    monkeypatch.setenv("DEV_ADMIN_EMAIL", "")
    monkeypatch.setenv("DEV_ADMIN_PASSWORD", "")


@pytest.fixture(autouse=True)
def _fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Argon2 is slow on purpose. Tests use the cheapest settings so the suite stays fast; the
    real settings are checked separately in test_security_core.py."""
    monkeypatch.setattr(
        security, "_hasher", PasswordHasher(time_cost=1, memory_cost=8, parallelism=1)
    )
    monkeypatch.setattr(security, "_DUMMY_HASH", security.hash_password("not-a-real-password"))


@pytest.fixture
def make_user(db_session: Session):
    """Creates a staff account (rolled back after the test)."""

    def create(
        email: str = "staff@example.org",
        *,
        role: str = "editor",
        password: str = PASSWORD,
        name: str = "Staff Person",
        **extra,
    ) -> User:
        user = User(
            email=email, name=name, password_hash=security.hash_password(password), role=role,
            **extra,
        )  # fmt: skip
        db_session.add(user)
        db_session.flush()
        return user

    return create


@pytest.fixture
def proxied(monkeypatch: pytest.MonkeyPatch):
    """One trusted proxy in front of the API, so a test can pretend to be different visitors with
    the X-Forwarded-For header."""
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "1")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def refreshes(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Records the "refresh these pages" messages instead of sending them."""
    sent: list[list[str]] = []
    monkeypatch.setattr(revalidate, "notify", lambda settings, tags, **_: sent.append(tags) or True)
    return sent


@dataclass
class Admin:
    """A signed-in member of staff: calls /api/v1/admin/... the way the admin page does."""

    api: TestClient
    csrf: str

    def _url(self, path: str) -> str:
        return f"/api/v1/admin{path}"

    def _headers(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.csrf, "Origin": "http://localhost"}

    def get(self, path: str, **params: Any):
        return self.api.get(self._url(path), params=params)

    def post(self, path: str, json: Any = None, **kwargs: Any):
        return self.api.post(self._url(path), json=json, headers=self._headers(), **kwargs)

    def put(self, path: str, json: Any = None):
        return self.api.put(self._url(path), json=json, headers=self._headers())

    def patch(self, path: str, json: Any = None):
        return self.api.patch(self._url(path), json=json, headers=self._headers())

    def delete(self, path: str):
        return self.api.delete(self._url(path), headers=self._headers())


@pytest.fixture
def editor(api: TestClient, make_user) -> Admin:
    from tests.helpers import signed_in

    make_user("editor@example.org", name="Edith Editor")
    return Admin(api, signed_in(api, email="editor@example.org"))


@pytest.fixture
def boss(api: TestClient, make_user) -> Admin:
    """A super admin (two-factor on), signed in on a separate browser: both can act at once."""
    from tests.helpers import code_for, signed_in

    secret = "JBSWY3DPEHPK3PXP"
    make_user(
        "boss@example.org", role="super_admin", name="Bo Boss", totp_enabled=True,
        totp_secret=security.encrypt_secret(get_settings(), secret),
    )  # fmt: skip
    browser = TestClient(app, base_url="http://localhost")  # (uses the same test database)
    csrf = signed_in(browser, email="boss@example.org", totpCode=code_for(secret))
    return Admin(browser, csrf)
