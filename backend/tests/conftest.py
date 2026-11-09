from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.session import engine, get_db
from app.main import app


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
