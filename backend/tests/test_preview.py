"""Draft preview links: signed, short-lived, read-only, never cached."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core import security
from app.core.config import get_settings
from app.models import Page

SETTINGS = get_settings()


def make_token(kind="page", entity_id=1, now=None) -> str:
    return security.create_preview_token(SETTINGS, kind=kind, entity_id=entity_id, now=now)[0]


# ============================ the token ============================


def test_a_token_opens_exactly_what_it_was_made_for():
    assert security.read_preview_token(SETTINGS, make_token("news", 42)) == ("news", 42)
    assert security.read_preview_token(SETTINGS, make_token("page", 7)) == ("page", 7)


def test_a_token_expires_after_thirty_minutes():
    start = datetime.now(UTC)
    token, expires = security.create_preview_token(SETTINGS, kind="page", entity_id=1, now=start)
    assert expires - start == timedelta(minutes=30)
    inside = start + timedelta(minutes=29)
    after = start + timedelta(minutes=31)
    assert security.read_preview_token(SETTINGS, token, now=inside) == ("page", 1)
    assert security.read_preview_token(SETTINGS, token, now=after) is None


def test_a_changed_token_is_refused():
    token = make_token("page", 5)
    version, kind, entity_id, expires, signature = token.split(".")
    forged = [
        ".".join([version, kind, "6", expires, signature]),  # another item
        ".".join([version, "news", entity_id, expires, signature]),  # another kind
        ".".join([version, kind, entity_id, str(int(expires) + 99999), signature]),  # longer life
        ".".join([version, kind, entity_id, expires, "0" * len(signature)]),
        ".".join([version, kind, entity_id, expires, signature[:-1]]),
        ".".join(["v2", kind, entity_id, expires, signature]),
    ]
    for value in forged:
        assert security.read_preview_token(SETTINGS, value) is None, value


@pytest.mark.parametrize(
    "junk",
    [
        "",
        "v1",
        "a.b.c.d.e",
        "v1.page.1.2.3.4",
        "v1.page..99999999999.abc",
        "v1.page.-1.99999999999.abc",
        "v1.page.١٢.99999999999.abc",  # non-ASCII digits
        "v1.page." + "9" * 40 + ".99999999999.abc",
        "v1.course.1.99999999999.abc",
        "\x00",
        "%00",
    ],
)
def test_garbage_is_refused_without_an_error(junk):
    assert security.read_preview_token(SETTINGS, junk) is None


def test_a_token_from_another_secret_is_refused():
    other = SETTINGS.model_copy(update={"secret_key": "x" * 64})
    token, _ = security.create_preview_token(other, kind="page", entity_id=1)
    assert security.read_preview_token(SETTINGS, token) is None


def test_a_token_cannot_be_made_for_an_unknown_target():
    with pytest.raises(ValueError):
        security.create_preview_token(SETTINGS, kind="course", entity_id=1)
    with pytest.raises(ValueError):
        security.create_preview_token(SETTINGS, kind="page", entity_id=0)


# ============================ asking for a link ============================


def page_id(db, key: str) -> int:
    return db.scalar(select(Page.id).where(Page.key == key))


def news_body(**changes) -> dict:
    doc = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hello."}]}],
    }
    return {
        "title": "Secret draft",
        "category": "event",
        "summary": "Not public yet.",
        "body": doc,
        "status": "draft",
        **changes,
    }


def test_a_link_needs_a_signed_in_member_of_staff(api, seeded):
    response = api.post("/api/v1/admin/preview-links", json={"kind": "page", "id": 1})
    assert response.status_code == 401


def test_a_link_needs_the_csrf_token(editor, seeded):
    response = editor.api.post(
        "/api/v1/admin/preview-links",
        json={"kind": "page", "id": page_id(seeded, "about")},
        headers={"Origin": "http://localhost"},
    )
    assert response.status_code == 403


def test_staff_gets_a_link_for_a_page_and_for_news(editor, seeded):
    about = page_id(seeded, "about")
    made = editor.post("/preview-links", {"kind": "page", "id": about})
    assert made.status_code == 201
    assert made.headers["cache-control"] == "no-store"
    body = made.json()
    assert body["path"].startswith("/preview/v1.page.")
    assert datetime.fromisoformat(body["expiresAt"]) > datetime.now(UTC) + timedelta(minutes=25)

    item = editor.post("/news", news_body()).json()
    link = editor.post("/preview-links", {"kind": "news", "id": item["id"]})
    assert link.status_code == 201 and "/preview/v1.news." in link.json()["path"]


@pytest.mark.parametrize(
    "payload",
    [
        {"kind": "course", "id": 1},
        {"kind": "page", "id": 0},
        {"kind": "page", "id": "1"},
        {"kind": "page", "id": True},
        {"kind": "page"},
        {"id": 1},
        {"kind": "page", "id": 1, "extra": 1},
    ],
)
def test_a_bad_request_for_a_link_is_refused(editor, seeded, payload):
    assert editor.post("/preview-links", payload).status_code == 422


def test_no_link_for_something_that_does_not_exist(editor, seeded):
    assert editor.post("/preview-links", {"kind": "page", "id": 999999}).status_code == 404
    assert editor.post("/preview-links", {"kind": "news", "id": 999999}).status_code == 404


# ============================ opening a link ============================


def open_link(editor, kind: str, entity_id: int):
    path = editor.post("/preview-links", {"kind": kind, "id": entity_id}).json()["path"]
    # opened by anyone holding the link: no sign-in, no cookies
    from fastapi.testclient import TestClient

    from app.main import app

    visitor = TestClient(app, base_url="http://localhost")
    return visitor.get(f"/api/v1{path}")


def test_a_draft_page_can_be_previewed_but_is_not_public(editor, seeded):
    about = seeded.scalar(select(Page).where(Page.key == "about"))
    about.status = "draft"
    seeded.flush()
    assert editor.api.get("/api/v1/public/pages/about").status_code == 404

    response = open_link(editor, "page", about.id)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "page" and body["page"]["key"] == "about"
    assert body["page"]["sections"], "the page content is shown"
    assert "news" not in body


def test_a_hidden_section_stays_hidden_in_the_preview(editor, seeded):
    about = seeded.scalar(select(Page).where(Page.key == "about"))
    shown = len(about.sections)
    about.sections[0].is_visible = False
    seeded.flush()
    body = open_link(editor, "page", about.id).json()
    assert len(body["page"]["sections"]) == shown - 1


def test_the_preview_shows_the_latest_saved_text(editor, seeded):
    about = seeded.scalar(select(Page).where(Page.key == "about"))
    about.title = "About us, version two"
    seeded.flush()
    assert open_link(editor, "page", about.id).json()["page"]["title"] == "About us, version two"


def test_a_draft_news_item_can_be_previewed_but_is_not_public(editor, seeded):
    item = editor.post("/news", news_body(slug="secret-draft")).json()
    assert editor.api.get("/api/v1/public/news/secret-draft").status_code == 404

    response = open_link(editor, "news", item["id"])
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "news" and body["news"]["title"] == "Secret draft"
    assert body["news"]["slug"] == "secret-draft"
    assert "page" not in body


def test_a_news_item_dated_in_the_future_can_be_previewed(editor, seeded):
    later = (datetime.now(UTC) + timedelta(days=30)).isoformat()
    item = editor.post("/news", news_body(status="published", publishedAt=later)).json()
    assert open_link(editor, "news", item["id"]).status_code == 200


def test_a_preview_is_never_cached_or_indexed(editor, seeded):
    response = open_link(editor, "page", page_id(seeded, "about"))
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-robots-tag"] == "noindex, nofollow"
    assert response.headers["referrer-policy"] == "no-referrer"


def test_an_expired_link_stops_working(editor, seeded):
    old = datetime.now(UTC) - timedelta(hours=2)
    token = make_token("page", page_id(seeded, "about"), now=old)
    assert editor.api.get(f"/api/v1/preview/{token}").status_code == 404


def test_a_changed_link_does_not_work(editor, seeded):
    token = make_token("page", page_id(seeded, "about"))
    assert editor.api.get(f"/api/v1/preview/{token[:-2]}00").status_code == 404
    assert editor.api.get("/api/v1/preview/nonsense").status_code == 404
    assert editor.api.get("/api/v1/preview/" + "a" * 500).status_code == 404
    assert editor.api.get("/api/v1/preview/%00").status_code == 404


def test_a_link_stops_working_when_the_item_is_deleted(editor, seeded):
    item = editor.post("/news", news_body()).json()
    path = editor.post("/preview-links", {"kind": "news", "id": item["id"]}).json()["path"]
    assert editor.api.get(f"/api/v1{path}").status_code == 200
    assert editor.delete(f"/news/{item['id']}").status_code == 204
    assert editor.api.get(f"/api/v1{path}").status_code == 404


def test_the_kind_in_the_link_decides_what_opens(editor, seeded):
    about = page_id(seeded, "about")
    item = editor.post("/news", news_body()).json()
    page_view = open_link(editor, "page", about).json()
    news_view = open_link(editor, "news", item["id"]).json()
    assert page_view["kind"] == "page" and "news" not in page_view
    assert news_view["kind"] == "news" and "page" not in news_view
