from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.enquiry import Enquiry

URL = "/api/v1/public/enquiries"
VALID: dict[str, Any] = {
    "name": "Asha Reddy",
    "phone": "9876543210",
    "course": "B.Sc Computer Science",
    "message": "Please call me about admission.",
    "source_page": "/",
}


def count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Enquiry)) or 0


def test_valid_enquiry_is_saved(api: TestClient, db_session: Session) -> None:
    response = api.post(URL, json=VALID)
    assert response.status_code == 201
    assert response.json() == {"ok": True}
    row = db_session.scalars(select(Enquiry)).one()
    assert (row.name, row.phone, row.course, row.status) == (
        "Asha Reddy",
        "9876543210",
        "B.Sc Computer Science",
        "new",
    )
    assert len(row.ip_hash) == 64 and "testclient" not in row.ip_hash  # keyed hash, not the IP


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("98765 43210", "9876543210"),
        ("+91 98765-43210", "9876543210"),
        ("09876543210", "9876543210"),
    ],
)
def test_phone_formats_are_normalised(
    api: TestClient, db_session: Session, raw: str, expected: str
) -> None:
    assert api.post(URL, json={**VALID, "phone": raw}).status_code == 201
    assert db_session.scalars(select(Enquiry)).one().phone == expected


@pytest.mark.parametrize("phone", ["12345", "5123456789", "98765432101", "abcdefghij", ""])
def test_invalid_phone_is_rejected(api: TestClient, db_session: Session, phone: str) -> None:
    assert api.post(URL, json={**VALID, "phone": phone}).status_code == 422
    assert count(db_session) == 0


@pytest.mark.parametrize(
    "bad",
    [
        {"name": "A"},
        {"name": "<script>alert(1)</script>"},
        {"name": "Asha\x00Reddy"},
        {"message": "x" * 501},
        {"unexpected": "field"},
    ],
)
def test_invalid_input_is_rejected(
    api: TestClient, db_session: Session, bad: dict[str, Any]
) -> None:
    assert api.post(URL, json={**VALID, **bad}).status_code == 422
    assert count(db_session) == 0


def test_honeypot_hides_the_failure_and_saves_nothing(api: TestClient, db_session: Session) -> None:
    response = api.post(URL, json={**VALID, "website": "http://spam.example"})
    assert response.status_code == 201
    assert count(db_session) == 0


def test_rate_limit_blocks_the_sixth_enquiry(api: TestClient, db_session: Session) -> None:
    for _ in range(5):
        assert api.post(URL, json=VALID).status_code == 201
    blocked = api.post(URL, json=VALID)
    assert blocked.status_code == 429
    assert blocked.headers["retry-after"] == "3600"
    assert count(db_session) == 5


def test_post_from_another_website_is_rejected(api: TestClient, db_session: Session) -> None:
    response = api.post(URL, json=VALID, headers={"Origin": "https://evil.example"})
    assert response.status_code == 403
    assert count(db_session) == 0


def test_post_from_own_website_is_accepted(api: TestClient) -> None:
    assert api.post(URL, json=VALID, headers={"Origin": "http://localhost:3000"}).status_code == 201


def _with_turnstile(monkeypatch: pytest.MonkeyPatch, passes: bool) -> None:
    settings = get_settings().model_copy(update={"turnstile_secret": SecretStr("test-secret")})
    monkeypatch.setattr("app.api.v1.public.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.v1.public.verify_turnstile", lambda *args, **kwargs: passes)


def test_turnstile_token_is_required_when_enabled(
    api: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_turnstile(monkeypatch, passes=True)
    assert api.post(URL, json=VALID).status_code == 400
    assert count(db_session) == 0


def test_turnstile_failure_is_rejected(
    api: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_turnstile(monkeypatch, passes=False)
    assert api.post(URL, json={**VALID, "turnstile_token": "bad"}).status_code == 400
    assert count(db_session) == 0


def test_turnstile_success_is_accepted(
    api: TestClient, db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _with_turnstile(monkeypatch, passes=True)
    assert api.post(URL, json={**VALID, "turnstile_token": "good"}).status_code == 201
    assert count(db_session) == 1


def test_email_is_sent_after_saving(api: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict[str, Any]] = []
    monkeypatch.setattr(
        "app.api.v1.public.send_enquiry_email", lambda settings, **kw: sent.append(kw)
    )
    assert api.post(URL, json=VALID).status_code == 201
    assert sent and sent[0]["phone"] == "9876543210"
