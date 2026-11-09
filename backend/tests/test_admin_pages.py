"""Staff endpoints for pages and their sections, the site settings, redirects and page history."""

import pytest
from sqlalchemy import select

from app.models import ContentRevision, Media, Page, PageSection, Redirect, SiteSetting
from app.services.revalidate import ALL_TAGS


@pytest.fixture
def pages(seeded) -> dict[str, int]:
    return {p.key: p.id for p in seeded.scalars(select(Page))}


@pytest.fixture
def photos(seeded) -> list[int]:
    return [
        m.id for m in seeded.scalars(select(Media).where(Media.kind == "image").order_by(Media.id))
    ]


def hero(photo_id: int, **changes) -> dict:
    data = {
        "headline": "A new headline",
        "text": "A short welcome text.",
        "primaryCta": {"label": "Enquire", "href": "/admissions"},
        "image": {"mediaId": photo_id},
    }
    return {"type": "hero", "data": {**data, **changes}}


def section_types(admin, page_id: int) -> list[str]:
    return [s["type"] for s in admin.get(f"/pages/{page_id}").json()["sections"]]


def public_types(admin, key: str) -> list[str]:
    return [s["type"] for s in admin.api.get(f"/api/v1/public/pages/{key}").json()["sections"]]


# ============================ pages ============================


def test_the_page_list_shows_every_page(editor, pages):
    listed = {p["key"]: p for p in editor.get("/pages").json()}
    assert set(listed) == set(pages) and len(listed) == 10
    assert listed["home"]["sections"] == 9 and listed["home"]["slug"] == ""
    assert listed["privacy"]["robotsNoindex"] is True


def test_a_page_comes_with_its_sections_and_the_photos_they_use(editor, pages):
    page = editor.get(f"/pages/{pages['home']}").json()
    assert page["key"] == "home" and [s["position"] for s in page["sections"]] == list(range(9))
    hero_section = page["sections"][0]
    media_id = hero_section["data"]["image"]["mediaId"]  # stored form: just the id ...
    assert page["media"][str(media_id)]["url"].startswith("/uploads/")  # ... plus what to show
    assert page["ogMedia"] is not None
    assert editor.get("/pages/999999999").status_code == 404


def test_page_details_can_be_edited(editor, pages, photos, refreshes):
    response = editor.put(
        f"/pages/{pages['about']}",
        {
            "title": "About us",
            "seoTitle": "About VRR",
            "seoDescription": "Who we are.",
            "ogMediaId": photos[1],
            "robotsNoindex": False,
            "status": "published",
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert (
        body["title"] == "About us"
        and body["slug"] == "about"
        and body["ogMedia"]["id"] == photos[1]
    )
    assert refreshes == [["pages"]]
    public = editor.api.get("/api/v1/public/pages/about").json()
    assert public["seo"]["title"] == "About VRR"


def test_changing_a_page_address_leaves_a_redirect(editor, pages, db_session):
    done = editor.put(f"/pages/{pages['about']}", {"title": "About", "slug": "about-us"})
    assert done.status_code == 200 and done.json()["slug"] == "about-us"
    redirect = db_session.scalars(select(Redirect)).one()
    assert (redirect.from_path, redirect.to_path, redirect.status_code) == (
        "/about",
        "/about-us",
        301,
    )
    assert editor.api.get("/api/v1/public/pages/by-slug/about-us").status_code == 200
    assert editor.api.get("/api/v1/public/pages/by-slug/about").status_code == 404


def test_page_rules(editor, pages):
    home = pages["home"]
    assert (
        editor.put(f"/pages/{home}", {"title": "Home", "slug": "start"}).json()["code"]
        == "home_address_fixed"
    )
    assert (
        editor.put(f"/pages/{home}", {"title": "Home", "status": "draft"}).json()["code"]
        == "home_must_be_published"
    )
    for reserved in ("admin", "api", "uploads", "internal"):
        response = editor.put(f"/pages/{pages['about']}", {"title": "About", "slug": reserved})
        assert response.status_code == 422 and response.json()["code"] == "reserved_slug"
    assert (
        editor.put(f"/pages/{pages['about']}", {"title": "About", "slug": "courses"}).status_code
        == 409
    )
    assert (
        editor.put(f"/pages/{pages['about']}", {"title": "About", "slug": "Bad Slug"}).status_code
        == 422
    )
    assert editor.put(f"/pages/{pages['about']}", {"title": ""}).status_code == 422
    assert (
        editor.put(
            f"/pages/{pages['about']}", {"title": "About", "ogMediaId": 987654321}
        ).status_code
        == 422
    )


def test_a_draft_page_disappears_from_the_website(editor, pages):
    editor.put(f"/pages/{pages['privacy']}", {"title": "Privacy", "status": "draft"})
    assert editor.api.get("/api/v1/public/pages/privacy").status_code == 404


# ============================ sections ============================


def test_add_a_section_at_a_position(editor, pages, photos, refreshes):
    before = section_types(editor, pages["about"])
    response = editor.post(f"/pages/{pages['about']}/sections", hero(photos[0]) | {"position": 1})
    assert response.status_code == 201, response.text
    types = [s["type"] for s in response.json()["sections"]]
    assert types == [*before[:1], "hero", *before[1:]]
    assert [s["position"] for s in response.json()["sections"]] == list(range(len(types)))
    assert refreshes == [["pages"]]
    assert public_types(editor, "about") == types  # visible on the website at once
    end = editor.post(f"/pages/{pages['about']}/sections", hero(photos[0], headline="Last"))
    assert [s["type"] for s in end.json()["sections"]][-1] == "hero"  # no position: at the end


def test_a_bad_section_says_which_field_is_wrong(editor, pages, photos):
    bad = hero(photos[0], primaryCta={"label": "Go", "href": "javascript:alert(1)"})
    response = editor.post(f"/pages/{pages['about']}/sections", bad)
    assert response.status_code == 422 and response.json()["code"] == "invalid_section"
    fields = [e["field"] for e in response.json()["errors"]]
    assert "primaryCta.href" in fields
    assert "javascript" not in response.text.lower().replace(
        "javascript:", ""
    )  # the value is not echoed
    missing = editor.post(f"/pages/{pages['about']}/sections", {"type": "hero", "data": {}})
    assert missing.status_code == 422 and len(missing.json()["errors"]) >= 4


def test_unknown_types_and_missing_photos_are_refused(editor, pages, photos):
    unknown = editor.post(f"/pages/{pages['about']}/sections", {"type": "script", "data": {}})
    assert unknown.status_code == 422 and unknown.json()["code"] == "unknown_section_type"
    gone = editor.post(f"/pages/{pages['about']}/sections", hero(987654321))
    assert gone.status_code == 422 and gone.json()["code"] == "unknown_media"
    assert editor.post("/pages/999999999/sections", hero(photos[0])).status_code == 404
    assert editor.post(f"/pages/{pages['about']}/sections", {"type": "hero"}).status_code == 422


def test_a_section_can_be_edited_hidden_and_shown(editor, pages, photos):
    page = pages["home"]
    stats = next(s for s in editor.get(f"/pages/{page}").json()["sections"] if s["type"] == "stats")
    new_data = {"items": [{"value": "9", "label": "Awards"}]}
    updated = editor.put(f"/pages/{page}/sections/{stats['id']}", {"data": new_data})
    assert updated.status_code == 200
    shown = next(s for s in updated.json()["sections"] if s["id"] == stats["id"])
    assert shown["data"] == new_data and shown["isVisible"] is True

    editor.put(f"/pages/{page}/sections/{stats['id']}", {"isVisible": False})
    assert "stats" not in public_types(
        editor, "home"
    )  # hidden: still in the admin, not on the site
    assert "stats" in section_types(editor, page)
    editor.put(f"/pages/{page}/sections/{stats['id']}", {"isVisible": True})
    assert "stats" in public_types(editor, "home")

    assert editor.put(f"/pages/{page}/sections/{stats['id']}", {}).status_code == 422
    bad = editor.put(f"/pages/{page}/sections/{stats['id']}", {"data": {"items": []}})
    assert bad.status_code == 422 and bad.json()["code"] == "invalid_section"
    assert editor.put(f"/pages/{page}/sections/999999999", {"isVisible": False}).status_code == 404
    other_page = pages["about"]  # a section id of another page is not found here
    assert (
        editor.put(f"/pages/{other_page}/sections/{stats['id']}", {"isVisible": False}).status_code
        == 404
    )


def test_sections_can_be_reordered(editor, pages):
    page = pages["home"]
    ids = [s["id"] for s in editor.get(f"/pages/{page}").json()["sections"]]
    reordered = editor.post(f"/pages/{page}/sections/reorder", {"ids": ids[::-1]})
    assert reordered.status_code == 200
    assert [s["id"] for s in reordered.json()["sections"]] == ids[::-1]
    assert [s["position"] for s in reordered.json()["sections"]] == list(range(len(ids)))
    for bad in (ids[:-1], [*ids, 987654321], [ids[0]] * len(ids)):
        assert editor.post(f"/pages/{page}/sections/reorder", {"ids": bad}).status_code == 422


def test_a_section_can_be_duplicated_and_deleted(editor, pages):
    page = pages["home"]
    sections = editor.get(f"/pages/{page}").json()["sections"]
    stats = next(s for s in sections if s["type"] == "stats")
    copy = editor.post(f"/pages/{page}/sections/{stats['id']}/duplicate")
    assert copy.status_code == 201
    types = [s["type"] for s in copy.json()["sections"]]
    index = types.index("stats")
    assert (
        types[index + 1] == "stats" and len(types) == len(sections) + 1
    )  # right after the original
    duplicate = copy.json()["sections"][index + 1]
    assert duplicate["id"] != stats["id"] and duplicate["data"] == stats["data"]

    gone = editor.delete(f"/pages/{page}/sections/{duplicate['id']}")
    assert gone.status_code == 200 and len(gone.json()["sections"]) == len(sections)
    assert [s["position"] for s in gone.json()["sections"]] == list(range(len(sections)))
    assert editor.delete(f"/pages/{page}/sections/{duplicate['id']}").status_code == 404


def test_a_page_keeps_a_history_and_a_mistake_can_be_undone(editor, pages, db_session, refreshes):
    page = pages["home"]
    before = editor.get(f"/pages/{page}").json()
    stats = next(s for s in before["sections"] if s["type"] == "stats")
    editor.delete(f"/pages/{page}/sections/{stats['id']}")  # "oops"
    assert "stats" not in section_types(editor, page)

    history = editor.get("/revisions", entity="page", entity_id=page).json()
    assert [r["action"] for r in history] == ["update", "create"]  # the state before was kept too
    refreshes.clear()
    restored = editor.post(f"/revisions/{history[-1]['id']}/restore")
    assert restored.status_code == 200 and refreshes == [["pages"]]
    after = editor.get(f"/pages/{page}").json()
    assert [(s["type"], s["data"], s["isVisible"]) for s in after["sections"]] == [
        (s["type"], s["data"], s["isVisible"]) for s in before["sections"]
    ]
    assert editor.get("/revisions", entity="page", entity_id=page).json()[0]["action"] == "restore"


def test_the_stored_history_has_the_whole_page(editor, pages, db_session):
    page = pages["about"]
    editor.put(f"/pages/{page}", {"title": "About", "seoTitle": "Changed"})
    revision = db_session.scalars(
        select(ContentRevision)
        .where(ContentRevision.entity == "page")
        .order_by(ContentRevision.id.desc())
    ).first()
    assert revision.data["page"]["seoTitle"] == "Changed" and revision.data["sections"]


def test_a_page_version_with_a_deleted_photo_is_not_restored(editor, pages, db_session):
    photo = Media(
        kind="image",
        original_filename="p.jpg",
        stored_name="page-photo.webp",
        mime="image/webp",
        size_bytes=1,
        width=10,
        height=10,
    )
    db_session.add(photo)
    db_session.flush()
    page = pages["about"]
    editor.post(f"/pages/{page}/sections", hero(photo.id))
    marked = editor.get("/revisions", entity="page", entity_id=page).json()[0]
    section = next(
        s for s in editor.get(f"/pages/{page}").json()["sections"] if s["type"] == "hero"
    )
    editor.delete(f"/pages/{page}/sections/{section['id']}")
    db_session.execute(
        PageSection.__table__.delete().where(PageSection.page_id == page)
    )  # (no pointers left)
    db_session.execute(Media.__table__.delete().where(Media.id == photo.id))
    db_session.flush()
    gone = editor.post(f"/revisions/{marked['id']}/restore")
    assert gone.status_code == 422 and gone.json()["code"] == "unknown_media"


# ============================ site settings ============================


def test_only_super_admins_touch_the_settings(editor, boss):
    for call in (
        editor.get("/settings"),
        editor.get("/settings/schema"),
        editor.put("/settings/contact", {"address": "Somewhere"}),
    ):
        assert call.status_code == 403 and call.json()["code"] == "forbidden"
    assert boss.get("/settings").status_code == 200


def test_settings_can_be_read_with_their_photos_and_form_schemas(boss, seeded):
    body = boss.get("/settings").json()
    assert set(body["groups"]) == {"brand", "contact", "social", "menu", "footer_courses", "seo"}
    logo = body["groups"]["brand"]["logo"]["mediaId"]
    assert body["media"][str(logo)]["url"].startswith("/uploads/")
    schema = boss.get("/settings/schema").json()
    assert schema["contact"]["schema"]["additionalProperties"] is False
    assert schema["brand"]["schema"]["$defs"]["MediaPick"]["x-widget"] == "media"
    assert all(group["label"] for group in schema.values())


def test_changing_the_settings_updates_the_website_and_refreshes_everything(
    boss, seeded, refreshes
):
    brand = boss.get("/settings").json()["groups"]["brand"]
    response = boss.put("/settings/brand", {**brand, "topBar": "Affiliated to SVU · NAAC applied"})
    assert response.status_code == 200 and response.json()["topBar"].endswith("NAAC applied")
    assert refreshes == [ALL_TAGS]
    assert boss.api.get("/api/v1/public/settings").json()["topBar"].endswith("NAAC applied")

    contact = boss.put(
        "/settings/contact",
        {
            "address": "Piler Road, Kallur",
            "phone": "+91 98765 43210",
            "email": "Info@Example.org",
            "mapLink": "https://maps.app.goo.gl/abc",
        },
    )
    assert contact.status_code == 200
    public = boss.api.get("/api/v1/public/settings").json()["contact"]
    assert public["phone"] == "+91 98765 43210" and public["address"] == "Piler Road, Kallur"


@pytest.mark.parametrize(
    ("group", "bad", "field"),
    [
        ("contact", {"address": "A", "phone": "call me"}, "phone"),
        ("contact", {"address": "A", "email": "not-an-email"}, "email"),
        ("contact", {"address": "A", "mapEmbedUrl": "https://evil.example/x"}, "mapEmbedUrl"),
        ("contact", {"address": "A", "mapLink": "javascript:alert(1)"}, "mapLink"),
        ("contact", {"address": "A", "extra": 1}, "extra"),
        ("menu", {"items": [{"label": "X", "href": "//evil.example"}]}, "items.0.href"),
        ("menu", {"items": [{"label": "X", "href": "/a"}] * 21}, "items"),
        (
            "seo",
            {
                "defaultTitle": "T",
                "titleTemplate": "no placeholder",
                "description": "d",
                "ogImage": {"mediaId": 1},
            },
            "titleTemplate",
        ),
    ],
)
def test_invalid_settings_say_which_field_is_wrong(boss, seeded, group, bad, field):
    response = boss.put(f"/settings/{group}", bad)
    assert response.status_code == 422 and response.json()["code"] == "invalid_settings"
    assert field in [e["field"] for e in response.json()["errors"]]


def test_the_settings_logo_must_be_a_photo_in_the_library(boss, seeded, db_session):
    brand = boss.get("/settings").json()["groups"]["brand"]
    assert (
        boss.put("/settings/brand", {**brand, "logo": {"mediaId": 987654321}}).json()["code"]
        == "unknown_media"
    )
    pdf = Media(
        kind="pdf",
        original_filename="a.pdf",
        stored_name="settings-test.pdf",
        mime="application/pdf",
        size_bytes=1,
    )
    db_session.add(pdf)
    db_session.flush()
    assert (
        boss.put("/settings/brand", {**brand, "logo": {"mediaId": pdf.id}}).json()["code"]
        == "wrong_media_type"
    )
    assert boss.put("/settings/unknown", {}).status_code == 404


def test_settings_history_and_undo(boss, seeded, db_session, refreshes):
    contact = boss.get("/settings").json()["groups"]["contact"]
    boss.put("/settings/contact", {**contact, "address": "Changed address"})
    row = db_session.scalars(select(SiteSetting).where(SiteSetting.key == "contact")).one()
    history = boss.get("/revisions", entity="settings", entity_id=row.id).json()
    assert [r["action"] for r in history] == ["update", "create"]
    refreshes.clear()
    assert boss.post(f"/revisions/{history[-1]['id']}/restore").status_code == 200
    assert boss.get("/settings").json()["groups"]["contact"]["address"] == contact["address"]
    assert refreshes == [ALL_TAGS]


def test_an_editor_cannot_restore_a_settings_version(editor, boss, seeded, db_session):
    contact = boss.get("/settings").json()["groups"]["contact"]
    boss.put("/settings/contact", {**contact, "address": "Changed address"})
    row = db_session.scalars(select(SiteSetting).where(SiteSetting.key == "contact")).one()
    version = boss.get("/revisions", entity="settings", entity_id=row.id).json()[-1]
    assert editor.post(f"/revisions/{version['id']}/restore").status_code == 403
    assert boss.get("/settings").json()["groups"]["contact"]["address"] == "Changed address"


# ============================ redirects ============================


def test_redirects_can_be_listed_added_and_removed(editor, seeded, refreshes):
    made = editor.post("/redirects", {"fromPath": "/old-page", "toPath": "/about"})
    assert made.status_code == 201 and made.json()["statusCode"] == 301
    assert (
        editor.post(
            "/redirects", {"fromPath": "/temp", "toPath": "/news", "statusCode": 302}
        ).status_code
        == 201
    )
    assert {r["fromPath"] for r in editor.get("/redirects").json()} >= {"/old-page", "/temp"}
    assert {"fromPath": "/old-page", "toPath": "/about", "statusCode": 301} in (
        editor.api.get("/api/v1/public/redirects").json()
    )
    assert editor.delete(f"/redirects/{made.json()['id']}").status_code == 204
    assert editor.delete(f"/redirects/{made.json()['id']}").status_code == 404
    assert "/old-page" not in [r["fromPath"] for r in editor.get("/redirects").json()]
    assert refreshes[-1] == ["redirects"]


@pytest.mark.parametrize(
    "bad",
    [
        {"fromPath": "/a", "toPath": "//evil.example"},
        {"fromPath": "/a", "toPath": "https://evil.example"},
        {"fromPath": "/a", "toPath": "javascript:alert(1)"},
        {"fromPath": "a", "toPath": "/b"},
        {"fromPath": "/a\\b", "toPath": "/b"},
        {"fromPath": "/same", "toPath": "/same"},
        {"fromPath": "/a", "toPath": "/b", "statusCode": 200},
        {"fromPath": "/" + "x" * 300, "toPath": "/b"},
    ],
)
def test_unsafe_redirects_are_refused(editor, seeded, bad):
    assert editor.post("/redirects", bad).status_code == 422


def test_redirect_clashes_are_refused(editor, seeded):
    editor.post("/redirects", {"fromPath": "/one", "toPath": "/two"})
    assert editor.post("/redirects", {"fromPath": "/one", "toPath": "/three"}).status_code == 409
    chain = editor.post("/redirects", {"fromPath": "/zero", "toPath": "/one"})
    assert chain.status_code == 422 and chain.json()["code"] == "redirect_chain"
