from collections.abc import Iterator

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
    ContentRevision,
    Course,
    Department,
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
)
from app.seed.loader import load_seed


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
