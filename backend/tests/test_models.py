"""The database enforces its own rules, even if the application code has a bug."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Activity,
    ContentRevision,
    Course,
    Department,
    GalleryItem,
    Media,
    News,
    NewsAttachment,
    Page,
    PageSection,
    Redirect,
    User,
)

NOW = datetime(2026, 11, 9, tzinfo=UTC)


def rejected(db: Session, *objects):
    """Assert that the database refuses these rows (and undo only that attempt)."""
    with pytest.raises(IntegrityError), db.begin_nested():
        db.add_all(objects)
        db.flush()


def saved(db: Session, obj):
    db.add(obj)
    db.flush()
    return obj


def photo(db: Session, name="a") -> Media:
    return saved(
        db,
        Media(
            kind="image",
            original_filename=f"{name}.jpg",
            stored_name=f"{name}-x1",
            mime="image/webp",
            size_bytes=10,
            width=800,
            height=600,
        ),
    )


def department(db: Session, slug="cs") -> Department:
    return saved(db, Department(name="Computer Science", slug=slug))


def news(**overrides) -> News:
    values = {
        "title": "T",
        "slug": "open-day",
        "category": "event",
        "summary": "s",
        "body": {"type": "doc", "content": []},
        "published_at": NOW,
    }
    return News(**{**values, **overrides})


# ---- users ----


def test_user_email_must_be_lower_case_and_unique(db_session):
    rejected(db_session, User(email="Admin@College.IN", name="A", password_hash="x"))
    saved(db_session, User(email="admin@college.in", name="A", password_hash="x"))
    rejected(db_session, User(email="admin@college.in", name="B", password_hash="x"))


def test_user_role_must_be_known(db_session):
    rejected(db_session, User(email="a@b.co", name="A", password_hash="x", role="owner"))
    user = saved(db_session, User(email="ok@b.co", name="A", password_hash="x"))
    db_session.refresh(user)
    assert user.role == "editor" and user.is_active and user.failed_logins == 0
    assert not user.totp_enabled


# ---- slugs and enums ----


@pytest.mark.parametrize("slug", ["Open Day", "open_day", "-open", "open-", "open--day", "", "a/b"])
def test_news_slug_must_be_url_safe(db_session, slug):
    rejected(db_session, news(slug=slug))


def test_news_category_and_status_must_be_known(db_session):
    rejected(db_session, news(category="gossip"))
    rejected(db_session, news(status="archived"))
    item = saved(db_session, news())
    db_session.refresh(item)
    assert item.status == "draft"  # nothing is public until someone publishes it


def test_activity_group_must_be_known(db_session):
    rejected(db_session, Activity(title="T", slug="t", group="politics", summary="s"))
    saved(db_session, Activity(title="Blood camp", slug="blood-camp", group="nss", summary="s"))


def test_page_slug_may_be_empty_only_for_a_plain_word(db_session):
    saved(db_session, Page(key="home", title="Home", slug=""))
    rejected(db_session, Page(key="about", title="About", slug="About Us"))
    rejected(db_session, Page(key="blog", title="Blog", slug="blog"))  # not a system page
    rejected(db_session, Page(key="home", title="Home 2", slug="home-2"))  # key is unique


# ---- media: in-use files are protected ----


def test_media_in_use_cannot_be_deleted(db_session):
    media = photo(db_session)
    saved(db_session, Page(key="about", title="About", slug="about", og_media_id=media.id))
    with pytest.raises(IntegrityError), db_session.begin_nested():
        db_session.delete(media)
        db_session.flush()


def test_media_rules(db_session):
    rejected(
        db_session,
        Media(kind="image", original_filename="a", stored_name="n1", mime="m", size_bytes=10),
    )  # an image needs a size
    rejected(
        db_session,
        Media(kind="video", original_filename="a", stored_name="n2", mime="m", size_bytes=10),
    )
    rejected(
        db_session,
        Media(kind="pdf", original_filename="a", stored_name="n3", mime="m", size_bytes=0),
    )
    saved(
        db_session,
        Media(kind="pdf", original_filename="a", stored_name="n4", mime="m", size_bytes=10),
    )
    media = photo(db_session, "b")
    db_session.refresh(media)
    assert media.variants == [] and media.alt_text == "" and media.crop_bottom is False


# ---- gallery ----


def test_gallery_item_needs_its_content(db_session):
    rejected(db_session, GalleryItem(kind="photo"))  # a photo needs an image
    rejected(db_session, GalleryItem(kind="video"))  # a video needs a YouTube id
    rejected(db_session, GalleryItem(kind="video", youtube_id="a b<script>"))
    rejected(db_session, GalleryItem(kind="photo", media_id=photo(db_session).id, category="x"))
    saved(db_session, GalleryItem(kind="photo", media_id=photo(db_session, "c").id))
    saved(db_session, GalleryItem(kind="video", youtube_id="dQw4w9WgXcQ"))


# ---- courses and departments ----


def test_course_rules(db_session):
    dept = department(db_session)

    def course(**overrides):
        values = {
            "department_id": dept.id,
            "name": "B.Sc CS",
            "tab": "B.Sc CS",
            "slug": "bsc-cs",
            "duration_years": 3,
            "summary": "s",
        }
        return Course(**{**values, **overrides})

    rejected(db_session, course(duration_years=0))
    rejected(db_session, course(duration_years=9))
    rejected(db_session, course(slug="BSc CS"))
    saved(db_session, course())
    with pytest.raises(IntegrityError), db_session.begin_nested():  # a department in use stays
        db_session.delete(dept)
        db_session.flush()


# ---- redirects ----


@pytest.mark.parametrize(
    ("from_path", "to_path"),
    [
        ("/old", "//evil.com"),
        ("/old", "/\\evil.com"),
        ("/old", "https://evil.com"),
        ("//old", "/new"),
        ("old", "/new"),
        ("/same", "/same"),
    ],
)
def test_redirects_must_stay_on_the_site(db_session, from_path, to_path):
    rejected(db_session, Redirect(from_path=from_path, to_path=to_path))


def test_redirect_defaults_and_status_codes(db_session):
    redirect = saved(db_session, Redirect(from_path="/old", to_path="/new"))
    db_session.refresh(redirect)
    assert redirect.status_code == 301
    rejected(db_session, Redirect(from_path="/a", to_path="/b", status_code=200))
    rejected(db_session, Redirect(from_path="/old", to_path="/other"))  # from_path is unique


# ---- cascades ----


def test_deleting_a_page_deletes_its_sections(db_session):
    page = saved(db_session, Page(key="home", title="Home", slug=""))
    page.sections.append(PageSection(type="stats", position=0, data={"items": []}))
    page.sections.append(PageSection(type="hero", position=1, data={}, is_visible=False))
    db_session.flush()
    assert [s.position for s in page.sections] == [0, 1]
    db_session.delete(page)
    db_session.flush()
    assert db_session.scalars(select(PageSection)).all() == []


def test_deleting_news_deletes_its_attachments_but_not_the_file(db_session):
    media = photo(db_session)
    item = saved(db_session, news())
    item.attachments.append(NewsAttachment(media_id=media.id, label="Circular"))
    db_session.flush()
    db_session.delete(item)
    db_session.flush()
    assert db_session.scalars(select(NewsAttachment)).all() == []
    assert db_session.get(Media, media.id) is not None


def test_revisions_must_name_a_known_action(db_session):
    rejected(db_session, ContentRevision(entity="page", entity_id=1, data={}, action="hack"))
    saved(db_session, ContentRevision(entity="page", entity_id=1, data={}, action="update"))
