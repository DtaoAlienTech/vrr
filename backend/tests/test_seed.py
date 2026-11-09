import pytest
from sqlalchemy import func, select

from app.models import Media, Page
from app.seed.loader import is_empty, load_seed


def test_seed_loads_into_an_empty_database_and_copies_the_photos(empty_content, tmp_path):
    assert is_empty(empty_content)
    counts = load_seed(empty_content, tmp_path)
    assert counts == {
        "photos": 14,
        "pages": 10,
        "courses": 3,
        "faculty": 8,
        "activities": 2,
        "news": 5,
        "gallery": 13,
    }
    assert not is_empty(empty_content)
    # every library entry has its file, with the right size, under a name that matches the row
    for media in empty_content.scalars(select(Media)):
        assert (tmp_path / media.stored_name).stat().st_size == media.size_bytes
    assert empty_content.scalar(select(func.count()).select_from(Media)) == 14
    # every starter photo also has its resized WebP copies; the original file stays as the fallback
    for media in empty_content.scalars(select(Media)):
        assert media.stored_name.startswith("seed-") and media.variants
        widths = [v["width"] for v in media.variants]
        assert widths == sorted(widths) and widths[-1] == min(media.width, 1600)
        assert all((tmp_path / v["name"]).is_file() for v in media.variants)


def test_the_website_receives_the_resized_copies(api, empty_content, tmp_path):
    load_seed(empty_content, tmp_path)  # with the resized copies
    hero = api.get("/api/v1/public/pages/home").json()["sections"][0]["data"]["image"]
    assert [v["width"] for v in hero["variants"]] == [400, 800, 1156]
    assert all(v["url"].startswith("/uploads/seed-campus-") and v["url"].endswith(".webp")
               for v in hero["variants"])  # fmt: skip
    assert hero["url"].endswith(".jpg")  # the original stays as the fallback address


def test_seed_refuses_to_run_twice(empty_content, tmp_path):
    load_seed(empty_content, tmp_path)
    with pytest.raises(RuntimeError, match="already has pages"):
        load_seed(empty_content, tmp_path)


def test_all_system_pages_are_published_and_privacy_is_not_indexed(seeded):
    pages = {p.key: p for p in seeded.scalars(select(Page))}
    assert {p.status for p in pages.values()} == {"published"}
    assert pages["privacy"].robots_noindex and not pages["home"].robots_noindex
