"""Staff endpoints for news and activities, and the history (undo) that goes with them."""

import pytest
from sqlalchemy import select

from app.models import AuditLog, ContentRevision, Media, News, Redirect

POST_NEWS = "/news"


def doc(text: str = "Welcome to the open day.") -> dict:
    return {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
    }


def news(**changes) -> dict:
    return {
        "title": "Open day 2026",
        "category": "event",
        "summary": "Come and see the college.",
        "body": doc(),
        "status": "published",
        **changes,
    }


@pytest.fixture
def photos(seeded) -> list[int]:
    """Ids of the starter photos (the library entries of the seeded site)."""
    return [
        m.id for m in seeded.scalars(select(Media).where(Media.kind == "image").order_by(Media.id))
    ]


@pytest.fixture
def pdf(seeded) -> int:
    row = Media(
        kind="pdf",
        original_filename="circular.pdf",
        stored_name="circular.pdf",
        mime="application/pdf",
        size_bytes=10,
    )
    seeded.add(row)
    seeded.flush()
    return row.id


def revisions(db, entity: str, entity_id: int) -> list[ContentRevision]:
    query = select(ContentRevision).where(
        ContentRevision.entity == entity, ContentRevision.entity_id == entity_id
    )
    return list(db.scalars(query.order_by(ContentRevision.id)))


def audit_actions(db, name: str) -> list[AuditLog]:
    return list(db.scalars(select(AuditLog).where(AuditLog.action == name)))


# ============================ news: create ============================


def test_create_news(editor, seeded, photos, pdf, refreshes):
    response = editor.post(
        POST_NEWS,
        news(
            coverMediaId=photos[0],
            attachments=[{"mediaId": pdf, "label": "Circular"}],
            isPinned=True,
            seoTitle="Open day",
            seoDescription="Visit us.",
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert (
        body["slug"] == "open-day-2026"
        and body["status"] == "published"
        and body["isPinned"] is True
    )
    assert body["coverMedia"]["id"] == photos[0] and body["coverMedia"]["url"].startswith(
        "/uploads/"
    )
    assert body["attachments"] == [
        {"media": {**body["attachments"][0]["media"]}, "label": "Circular"}
    ]
    assert body["attachments"][0]["media"]["kind"] == "pdf" and body["publishedAt"]
    assert refreshes == [["news"]]
    public = [n["slug"] for n in editor.api.get("/api/v1/public/news").json()]
    assert "open-day-2026" in public  # published at once


def test_news_is_a_draft_unless_published(editor, seeded):
    body = editor.post(POST_NEWS, news(status=None) | {"status": "draft"}).json()
    assert body["status"] == "draft"
    payload = news()
    del payload["status"]
    assert editor.post(POST_NEWS, payload).json()["status"] == "draft"  # the default
    assert "open-day-2026" not in [n["slug"] for n in editor.api.get("/api/v1/public/news").json()]


def test_addresses_are_made_unique_and_can_be_chosen(editor, seeded):
    assert editor.post(POST_NEWS, news()).json()["slug"] == "open-day-2026"
    assert editor.post(POST_NEWS, news()).json()["slug"] == "open-day-2026-2"
    assert editor.post(POST_NEWS, news(slug="my-own-address")).json()["slug"] == "my-own-address"
    taken = editor.post(POST_NEWS, news(slug="my-own-address"))
    assert taken.status_code == 409 and taken.json()["code"] == "slug_taken"
    telugu = editor.post(POST_NEWS, news(title="ప్రవేశాలు ప్రారంభం")).json()
    assert telugu["slug"].startswith("item")  # a title in another script still gets a safe address


def test_invalid_news_is_refused_with_the_field_names(editor, seeded, photos, pdf):
    cases = {
        "title": news(title=""),
        "category": news(category="gossip"),
        "summary": news(summary="x" * 401),
        "slug": news(slug="Bad Slug!"),
        "body": news(body={"type": "doc", "content": [{"type": "script"}]}),
        "publishedAt": news(publishedAt="2026-10-28T09:00:00"),  # no time zone
        "attachments": news(attachments=[{"mediaId": pdf, "label": "x"}] * 11),
        "coverMediaId": news(coverMediaId="7"),
    }
    for field, payload in cases.items():
        response = editor.post(POST_NEWS, payload)
        assert response.status_code == 422, field
        body = response.json()
        assert body["code"] == "validation_error" and set(body) == {"detail", "code", "errors"}
        assert any(e["field"].startswith(field) for e in body["errors"]), (field, body["errors"])
    assert editor.post(POST_NEWS, news(headline="extra field")).status_code == 422


def test_photos_and_pdfs_must_exist_and_be_the_right_kind(editor, seeded, photos, pdf):
    missing = editor.post(POST_NEWS, news(coverMediaId=987654321))
    assert missing.status_code == 422 and missing.json()["code"] == "unknown_media"
    cover_is_pdf = editor.post(POST_NEWS, news(coverMediaId=pdf))
    assert cover_is_pdf.status_code == 422 and cover_is_pdf.json()["code"] == "wrong_media_type"
    attachment_is_photo = editor.post(
        POST_NEWS, news(attachments=[{"mediaId": photos[0], "label": "x"}])
    )
    assert (
        attachment_is_photo.status_code == 422
        and attachment_is_photo.json()["code"] == "wrong_media_type"
    )


def test_news_needs_a_signed_in_member_of_staff(api, seeded):
    assert api.post("/api/v1/admin/news", json=news()).status_code in (401, 403)
    assert api.get("/api/v1/admin/news").status_code == 401


def test_news_changes_need_the_csrf_token(editor, seeded):
    response = editor.api.post(
        "/api/v1/admin/news", json=news(), headers={"Origin": "http://localhost"}
    )
    assert response.status_code == 403 and response.json()["code"] == "csrf_failed"


# ============================ news: read, update, delete ============================


def test_list_filter_search_and_paging(editor, seeded):
    first = editor.post(POST_NEWS, news(title="Alpha notice", category="notice")).json()
    second = editor.post(POST_NEWS, news(title="Beta 100% event", status="draft")).json()
    everything = editor.get("/news").json()
    assert {first["id"], second["id"]} <= {n["id"] for n in everything}
    assert [n["id"] for n in editor.get("/news", status="draft").json()] == [second["id"]]
    assert [n["id"] for n in editor.get("/news", q="alpha").json()] == [first["id"]]
    assert [n["id"] for n in editor.get("/news", q="100%").json()] == [second["id"]]
    assert editor.get("/news", q="B%ta").json() == []  # "%" means itself
    assert len(editor.get("/news", limit=2).json()) == 2
    assert editor.get(f"/news/{first['id']}").json()["title"] == "Alpha notice"
    assert editor.get("/news/999999999").status_code == 404
    for query in ({"limit": 0}, {"limit": 201}, {"offset": -1}, {"status": "archived"}):
        assert editor.get("/news", **query).status_code == 422


def test_update_replaces_the_item_and_refreshes_the_website(editor, seeded, db_session, refreshes):
    made = editor.post(POST_NEWS, news(title="Old title")).json()
    refreshes.clear()
    response = editor.put(
        f"/news/{made['id']}", news(title="New title", summary="Changed", status="draft")
    )
    assert response.status_code == 200
    body = response.json()
    assert (body["title"], body["summary"], body["status"]) == ("New title", "Changed", "draft")
    assert body["slug"] == made["slug"]  # no address in the request: it stays
    assert refreshes == [["news"]]
    entry = audit_actions(db_session, "news_update")[0]
    assert entry.changes == {"fields": ["status", "summary", "title"]}  # names only, never the text
    assert editor.put("/news/999999999", news()).status_code == 404


def test_changing_the_address_of_a_published_item_leaves_a_redirect(editor, seeded, db_session):
    made = editor.post(POST_NEWS, news(slug="first-address")).json()
    editor.put(f"/news/{made['id']}", news(slug="second-address"))
    editor.put(f"/news/{made['id']}", news(slug="third-address"))
    redirects = {r.from_path: r.to_path for r in db_session.scalars(select(Redirect))}
    assert redirects == {
        "/news/first-address": "/news/third-address",  # chains are kept short
        "/news/second-address": "/news/third-address",
    }
    editor.put(f"/news/{made['id']}", news(slug="first-address"))  # back to the first address
    redirects = {r.from_path: r.to_path for r in db_session.scalars(select(Redirect))}
    assert "/news/first-address" not in redirects  # it is live again: no loop
    assert redirects["/news/third-address"] == "/news/first-address"


def test_a_new_redirect_is_announced_to_the_website_but_a_plain_edit_is_not(
    editor, seeded, refreshes
):
    made = editor.post(POST_NEWS, news(slug="first-address")).json()
    refreshes.clear()
    editor.put(f"/news/{made['id']}", news(slug="second-address"))
    assert refreshes == [["news", "redirects"]]  # the website keeps its own list of redirects
    refreshes.clear()
    editor.put(f"/news/{made['id']}", news(slug="second-address", title="Another title"))
    assert refreshes == [["news"]]
    draft = editor.post(POST_NEWS, news(slug="draft-a", status="draft")).json()
    refreshes.clear()
    editor.put(f"/news/{draft['id']}", news(slug="draft-b", status="draft"))
    assert refreshes == [["news"]]  # a draft leaves no redirect


def test_drafts_leave_no_redirect(editor, seeded, db_session):
    made = editor.post(POST_NEWS, news(slug="draft-a", status="draft")).json()
    editor.put(f"/news/{made['id']}", news(slug="draft-b", status="draft"))
    assert db_session.scalars(select(Redirect)).all() == []


def test_an_address_cannot_be_taken_from_another_item(editor, seeded):
    editor.post(POST_NEWS, news(slug="taken"))
    other = editor.post(POST_NEWS, news(slug="free")).json()
    response = editor.put(f"/news/{other['id']}", news(slug="taken"))
    assert response.status_code == 409
    assert editor.put(f"/news/{other['id']}", news(slug="free")).status_code == 200  # its own


def test_delete_news(editor, seeded, db_session, refreshes):
    made = editor.post(POST_NEWS, news()).json()
    refreshes.clear()
    assert editor.delete(f"/news/{made['id']}").status_code == 204
    assert editor.get(f"/news/{made['id']}").status_code == 404
    assert editor.delete(f"/news/{made['id']}").status_code == 404
    assert refreshes == [["news"]]
    assert [r.action for r in revisions(db_session, "news", made["id"])] == ["create", "delete"]
    assert db_session.scalars(select(News).where(News.id == made["id"])).first() is None


# ============================ history ============================


def test_every_edit_keeps_a_version_and_can_be_undone(editor, seeded, db_session, refreshes):
    made = editor.post(POST_NEWS, news(title="Version one", summary="First")).json()
    editor.put(f"/news/{made['id']}", news(title="Version two", summary="Second"))
    editor.put(f"/news/{made['id']}", news(title="Version three", summary="Third"))

    listed = editor.get("/revisions", entity="news", entity_id=made["id"]).json()
    assert [r["action"] for r in listed] == ["update", "update", "create"]  # newest first
    assert all(r["entityId"] == made["id"] for r in listed)
    assert all(r["userName"] == "Edith Editor" for r in listed[:2])  # who made each version
    assert all(
        r["label"] == "Version three" for r in listed
    )  # which item it is (its current title)
    oldest = listed[-1]
    assert editor.get(f"/revisions/{oldest['id']}").json()["data"]["title"] == "Version one"

    refreshes.clear()
    restored = editor.post(f"/revisions/{oldest['id']}/restore")
    assert restored.status_code == 200 and restored.json() == {
        "entity": "news",
        "entityId": made["id"],
    }
    now = editor.get(f"/news/{made['id']}").json()
    assert (now["title"], now["summary"]) == ("Version one", "First")
    assert refreshes == [["news"]]
    actions = [
        r["action"] for r in editor.get("/revisions", entity="news", entity_id=made["id"]).json()
    ]
    assert actions[0] == "restore"  # the undo itself is in the history, so it can be undone too
    assert len(audit_actions(db_session, "revision_restore")) == 1


def test_the_very_first_edit_of_an_old_item_can_be_undone(editor, seeded, db_session):
    existing = db_session.scalars(
        select(News).order_by(News.id)
    ).first()  # made by the seed: no history
    original_title = existing.title
    editor.put(f"/news/{existing.id}", news(title="Edited once", slug=existing.slug))
    history = editor.get("/revisions", entity="news", entity_id=existing.id).json()
    assert [r["action"] for r in history] == ["update", "create"]  # the "before" state was saved
    editor.post(f"/revisions/{history[-1]['id']}/restore")
    assert editor.get(f"/news/{existing.id}").json()["title"] == original_title


def test_a_deleted_item_can_be_brought_back(editor, seeded):
    made = editor.post(POST_NEWS, news(title="Short-lived", slug="short-lived")).json()
    editor.delete(f"/news/{made['id']}")
    deleted = editor.get("/revisions", entity="news", entity_id=made["id"]).json()[0]
    assert deleted["action"] == "delete"
    back = editor.post(f"/revisions/{deleted['id']}/restore")
    assert back.status_code == 200
    new_id = back.json()["entityId"]
    item = editor.get(f"/news/{new_id}").json()
    assert item["title"] == "Short-lived" and item["slug"] == "short-lived"


def test_restoring_refuses_a_version_that_clashes_with_something_now(editor, seeded):
    made = editor.post(POST_NEWS, news(slug="original-address")).json()
    editor.delete(f"/news/{made['id']}")
    editor.post(POST_NEWS, news(slug="original-address"))  # someone else uses the address now
    deleted = editor.get("/revisions", entity="news", entity_id=made["id"]).json()[0]
    assert editor.post(f"/revisions/{deleted['id']}/restore").status_code == 409


def test_a_version_whose_photo_was_deleted_cannot_be_restored(editor, seeded, photos, db_session):
    lonely = Media(
        kind="image",
        original_filename="x.jpg",
        stored_name="lonely-photo.webp",
        mime="image/webp",
        size_bytes=1,
        width=10,
        height=10,
    )
    db_session.add(lonely)
    db_session.flush()
    made = editor.post(POST_NEWS, news(coverMediaId=lonely.id)).json()
    editor.put(f"/news/{made['id']}", news(title="Without cover"))
    old = editor.get("/revisions", entity="news", entity_id=made["id"]).json()[-1]
    editor.put(f"/news/{made['id']}", news(title="Still without"))
    db_session.execute(Media.__table__.delete().where(Media.id == lonely.id))  # (now unused)
    db_session.flush()
    gone = editor.post(f"/revisions/{old['id']}/restore")
    assert gone.status_code == 422 and gone.json()["code"] == "unknown_media"


def test_history_only_keeps_the_latest_fifty_versions(editor, seeded, db_session):
    made = editor.post(POST_NEWS, news(title="Counting")).json()
    for number in range(55):
        editor.put(f"/news/{made['id']}", news(title=f"Edit {number}"))
    assert len(revisions(db_session, "news", made["id"])) == 50
    assert editor.get(f"/news/{made['id']}").json()["title"] == "Edit 54"


def test_history_endpoints_validate_and_hide_unknown_versions(editor, seeded):
    assert editor.get("/revisions/999999999").status_code == 404
    assert editor.post("/revisions/999999999/restore").status_code == 404
    for query in ({"limit": 0}, {"limit": 201}, {"before_id": 0}, {"entity_id": 0}):
        assert editor.get("/revisions", **query).status_code == 422
    assert editor.get("/revisions", entity="news", entity_id=999999999).json() == []


# ============================ activities ============================


def activity(**changes) -> dict:
    return {
        "title": "Blood donation camp",
        "group": "nss",
        "summary": "Volunteers organised a camp.",
        "status": "published",
        **changes,
    }


def test_create_and_update_an_activity_with_photos(editor, seeded, photos, refreshes):
    response = editor.post(
        "/activities",
        activity(
            year=2026,
            coverMediaId=photos[0],
            showOnHome=True,
            photos=[{"mediaId": photos[1], "caption": "Registration"}, {"mediaId": photos[2]}],
        ),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["slug"] == "blood-donation-camp" and body["year"] == 2026 and body["showOnHome"]
    assert [p["media"]["id"] for p in body["photos"]] == [photos[1], photos[2]]
    assert (
        body["photos"][0]["caption"] == "Registration" and body["photos"][1].get("caption") is None
    )
    assert refreshes == [["activities"]]
    public = editor.api.get("/api/v1/public/activities").json()
    assert "blood-donation-camp" in [a["slug"] for a in public]

    changed = editor.put(
        f"/activities/{body['id']}", activity(photos=[{"mediaId": photos[3]}], status="draft")
    )
    assert [p["media"]["id"] for p in changed.json()["photos"]] == [photos[3]]
    assert "blood-donation-camp" not in [
        a["slug"] for a in editor.api.get("/api/v1/public/activities").json()
    ]


@pytest.mark.parametrize(
    "bad",
    [
        {"year": 1800},
        {"year": "2026"},
        {"group": "politics"},
        {"coverMediaId": 987654321},
        {"photos": [{"mediaId": 987654321}]},
    ],
)
def test_invalid_activities_are_refused(editor, seeded, bad):
    assert editor.post("/activities", activity(**bad)).status_code == 422


def test_activities_can_be_reordered(editor, seeded):
    ids = [editor.post("/activities", activity(title=f"Event {n}")).json()["id"] for n in range(3)]
    assert editor.post("/activities/reorder", {"ids": [ids[2], ids[0], ids[1]]}).status_code == 204
    listed = [a["id"] for a in editor.get("/activities").json() if a["id"] in ids]
    assert listed == [ids[2], ids[0], ids[1]]
    assert editor.post("/activities/reorder", {"ids": [ids[0], ids[0]]}).status_code == 422
    assert editor.post("/activities/reorder", {"ids": [ids[0], 987654321]}).status_code == 422
    assert editor.post("/activities/reorder", {"ids": []}).status_code == 422


def test_activity_history_and_delete(editor, seeded, photos):
    made = editor.post("/activities", activity(photos=[{"mediaId": photos[0]}])).json()
    editor.put(f"/activities/{made['id']}", activity(title="Renamed camp", photos=[]))
    oldest = editor.get("/revisions", entity="activity", entity_id=made["id"]).json()[-1]
    editor.post(f"/revisions/{oldest['id']}/restore")
    back = editor.get(f"/activities/{made['id']}").json()
    assert back["title"] == "Blood donation camp" and len(back["photos"]) == 1
    assert editor.delete(f"/activities/{made['id']}").status_code == 204
    assert editor.get(f"/activities/{made['id']}").status_code == 404
