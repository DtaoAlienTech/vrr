"""The public content API: shapes match the website's types, and only published content leaves."""

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select, update

from app.models import (
    Activity,
    Course,
    Faculty,
    GalleryItem,
    News,
    Page,
    PageSection,
    SiteSetting,
)


def get(api, path: str, *, status: int = 200, **params):
    response = api.get(f"/api/v1/public{path}", params=params)
    assert response.status_code == status, response.text
    return response.json()


def walk(value: Any):
    """Every value in a JSON document."""
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def test_responses_contain_no_nulls_and_no_unresolved_photos(api, seeded):
    for path in (
        "/settings",
        "/pages/home",
        "/pages/by-slug/about",
        "/courses",
        "/faculty",
        "/news",
        "/activities",
        "/gallery",
    ):
        for value in walk(get(api, path)):
            assert value is not None, path
            assert not (isinstance(value, dict) and "mediaId" in value), path


# ---- settings ----


def test_settings(api, seeded):
    settings = get(api, "/settings")
    assert settings["name"] == "VRR Degree College"
    assert settings["established"] == 2016
    assert settings["logo"] == {
        "url": "/uploads/seed-logo.png",
        "alt": "VRR Degree College logo",
        "width": 439,
        "height": 512,
    }
    assert settings["seo"]["ogImage"]["url"].startswith("/uploads/seed-")
    assert [link["label"] for link in settings["menu"]][:3] == ["Home", "About", "Courses"]
    assert len(settings["menu"]) == 9 and len(settings["footerCourses"]) == 3
    assert settings["contact"]["address"] == "Piler Road, Kallur"
    assert (
        settings["contact"]["phone"] == ""
    )  # not provided yet: empty text, as the website expects


def test_settings_missing_gives_503(api, seeded):
    seeded.execute(update(SiteSetting).where(SiteSetting.key == "menu").values(key="menu-old"))
    seeded.flush()
    get(api, "/settings", status=503)


# ---- pages ----


def test_page_list(api, seeded):
    pages = {page["key"]: page for page in get(api, "/pages")}
    assert set(pages) == {
        "home",
        "about",
        "courses",
        "faculty",
        "admissions",
        "activities",
        "gallery",
        "news",
        "contact",
        "privacy",
    }
    assert pages["home"]["slug"] == "" and pages["about"]["slug"] == "about"
    assert pages["privacy"]["noindex"] is True and "noindex" not in pages["home"]


def test_home_page_is_resolved_for_the_website(api, seeded):
    page = get(api, "/pages/home")
    assert [s["type"] for s in page["sections"]] == [
        "hero",
        "stats",
        "notice_strip",
        "collection_list",
        "collection_list",
        "quote",
        "card_grid",
        "media_gallery",
        "enquiry_cta",
    ]
    assert all(isinstance(s["id"], int) for s in page["sections"])
    hero = page["sections"][0]["data"]
    assert set(hero["image"]) <= {"url", "alt", "width", "height", "variants", "cropBottom"}
    assert hero["image"]["url"].startswith("/uploads/seed-campus-") and hero["image"]["alt"]
    assert page["seo"]["title"] and page["seo"]["description"]
    assert page["seo"]["ogImage"]["url"].startswith("/uploads/")


def test_embedded_blocks_get_ids_and_nss_photos_hide_the_date_stamp(api, seeded):
    about = get(api, "/pages/by-slug/about")
    two_column = next(s for s in about["sections"] if s["type"] == "two_column")["data"]
    blocks = two_column["main"] + two_column["aside"]
    assert blocks and all(isinstance(b["id"], int) and b["type"] for b in blocks)
    gallery = get(api, "/gallery", category="nss")
    assert gallery and all(item["media"]["cropBottom"] is True for item in gallery)


def test_unknown_or_draft_pages_are_not_found(api, seeded):
    get(api, "/pages/by-slug/nothing-here", status=404)
    get(api, "/pages/nothing", status=404)
    seeded.execute(update(Page).where(Page.key == "about").values(status="draft"))
    seeded.flush()
    get(api, "/pages/about", status=404)
    get(api, "/pages/by-slug/about", status=404)
    assert "about" not in {p["key"] for p in get(api, "/pages")}


def test_hidden_sections_are_not_sent(api, seeded):
    seeded.execute(update(PageSection).where(PageSection.type == "stats").values(is_visible=False))
    seeded.flush()
    types = [s["type"] for s in get(api, "/pages/home")["sections"]]
    assert "stats" not in types and "hero" in types


def test_a_section_with_a_deleted_photo_is_skipped_not_fatal(api, seeded):
    seeded.execute(
        update(PageSection)
        .where(PageSection.type == "quote")
        .values(
            data={
                "heading": "h",
                "text": "t",
                "name": "n",
                "role": "r",
                "image": {"mediaId": 987654321},
            }
        )
    )
    seeded.flush()
    types = [s["type"] for s in get(api, "/pages/home")["sections"]]
    assert "quote" not in types and "hero" in types and "enquiry_cta" in types


# ---- courses and faculty ----


def test_courses(api, seeded):
    courses = get(api, "/courses")
    assert [c["slug"] for c in courses] == [
        "bsc-computer-science",
        "bsc-zoology",
        "bcom-computer-science",
    ]
    cs = courses[0]
    assert cs["duration"] == "3 years" and cs["department"] == "Department of Computer Science"
    assert cs["description"]["type"] == "doc" and cs["subjects"]
    assert get(api, "/courses/bsc-zoology")["tab"] == "Zoology"
    get(api, "/courses/unknown", status=404)


def test_unpublished_course_is_hidden(api, seeded):
    seeded.execute(update(Course).where(Course.slug == "bsc-zoology").values(is_published=False))
    seeded.flush()
    assert len(get(api, "/courses")) == 2
    get(api, "/courses/bsc-zoology", status=404)


def test_faculty(api, seeded):
    everyone = get(api, "/faculty")
    assert len(everyone) == 8
    assert {m["departmentKey"] for m in everyone} == {"computer-science", "zoology", "commerce"}
    assert [m["name"] for m in get(api, "/faculty", department="zoology")] == [
        m["name"] for m in everyone if m["departmentKey"] == "zoology"
    ]
    seeded.execute(update(Faculty).where(Faculty.id == everyone[0]["id"]).values(is_active=False))
    seeded.flush()
    assert len(get(api, "/faculty")) == 7


# ---- news ----


def test_news_order_labels_and_dates(api, seeded):
    news = get(api, "/news")
    assert len(news) == 5
    assert news[0]["pinned"] is True and news[0]["category"] == "Admission"
    rest = [n["publishedAt"] for n in news[1:]]
    assert rest == sorted(rest, reverse=True)
    assert news[0]["publishedAt"] == "2026-10-28" and news[0]["attachments"] == []
    assert all("pinned" not in n for n in news[1:])  # false is left out
    assert {n["category"] for n in news} == {"Admission", "Notice", "Event", "Activity"}


def test_news_filters_limit_and_detail(api, seeded):
    assert {n["category"] for n in get(api, "/news", category="notice")} == {"Notice"}
    assert len(get(api, "/news", limit=2)) == 2
    get(api, "/news", category="gossip", status=422)
    get(api, "/news", limit=0, status=422)
    item = get(api, "/news/sample-admissions-open")
    assert item["body"]["type"] == "doc"
    get(api, "/news/unknown", status=404)


def test_drafts_and_future_news_are_hidden(api, seeded):
    first = seeded.scalars(select(News).order_by(News.id)).first()
    other = seeded.scalars(select(News).order_by(News.id).offset(1)).first()
    first.status = "draft"
    other.published_at = datetime.now(UTC) + timedelta(days=2)
    seeded.flush()
    slugs = {n["slug"] for n in get(api, "/news")}
    assert first.slug not in slugs and other.slug not in slugs and len(slugs) == 3
    get(api, f"/news/{first.slug}", status=404)
    get(api, f"/news/{other.slug}", status=404)


# ---- activities and gallery ----


def test_activities(api, seeded):
    activities = get(api, "/activities")
    nss = next(a for a in activities if a["groupKey"] == "nss")
    leo = next(a for a in activities if a["groupKey"] == "leo")
    assert nss["group"] == "NSS" and nss["year"] == "2022" and len(nss["photos"]) == 7
    assert leo["group"] == "Leo Club" and "year" not in leo
    assert nss["cover"]["url"].startswith("/uploads/") and nss["photos"][0]["media"]["cropBottom"]
    assert [a["groupKey"] for a in get(api, "/activities", group="leo")] == ["leo"]
    assert len(get(api, "/activities", home=True)) == 2
    assert len(get(api, "/activities", limit=1)) == 1
    get(api, "/activities", group="politics", status=422)


def test_draft_activity_is_hidden_and_missing_cover_falls_back_to_a_photo(api, seeded):
    nss = seeded.scalars(select(Activity).where(Activity.group == "nss")).one()
    leo = seeded.scalars(select(Activity).where(Activity.group == "leo")).one()
    leo.status = "draft"
    nss.cover_media_id = None
    seeded.flush()
    seeded.refresh(nss)
    activities = get(api, "/activities")
    assert [a["groupKey"] for a in activities] == ["nss"]
    assert activities[0]["cover"] == activities[0]["photos"][0]["media"]


def test_gallery(api, seeded):
    items = get(api, "/gallery")
    assert len(items) == 13
    assert {i["categoryLabel"] for i in items} == {"Campus", "NSS", "Leo Club"}
    assert len(get(api, "/gallery", category="nss")) == 7
    first = seeded.scalars(select(GalleryItem).order_by(GalleryItem.id)).first()
    first.is_published = False
    seeded.add(GalleryItem(kind="video", youtube_id="dQw4w9WgXcQ", category="campus"))
    seeded.flush()
    assert len(get(api, "/gallery")) == 12  # unpublished and video items are not sent (yet)


# ---- headers ----


def test_headers(api, seeded):
    ok = api.get("/api/v1/public/courses")
    assert ok.headers["cache-control"] == "public, max-age=30, stale-while-revalidate=300"
    assert ok.headers["x-content-type-options"] == "nosniff"
    missing = api.get("/api/v1/public/courses/unknown")
    assert missing.status_code == 404 and missing.headers["cache-control"] == "no-store"


def test_nothing_leaks_from_an_empty_site(api, empty_content):
    assert get(api, "/pages") == [] and get(api, "/courses") == [] and get(api, "/news") == []
    assert (
        get(api, "/activities") == [] and get(api, "/gallery") == [] and get(api, "/faculty") == []
    )
    get(api, "/pages/home", status=404)
    get(api, "/settings", status=503)


@pytest.mark.parametrize(
    "path",
    [
        "/pages/by-slug/" + "x" * 500,
        "/pages/by-slug/About",
        "/pages/by-slug/%00",
        "/pages/..%2f..%2fetc",
        "/pages/bogus",
        "/courses/" + "y" * 500,
        "/courses/%00",
        "/courses/a'; drop table news;--",
        "/news/%00",
        "/news/Open%20Day",
    ],
)
def test_odd_addresses_are_a_clean_404(api, seeded, path):
    assert api.get(f"/api/v1/public{path}").status_code == 404


@pytest.mark.parametrize(
    "path",
    [
        "/gallery?category=%00",
        "/gallery?category=x' OR '1'='1",
        "/faculty?department=%00",
        "/faculty?department=A B",
        "/news?category=%00",
        "/activities?group=%00",
    ],
)
def test_odd_filters_are_refused_before_the_database(api, seeded, path):
    assert api.get(f"/api/v1/public{path}").status_code == 422
