import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.blocks import (
    EMBEDDED,
    SECTION_TYPES,
    TOP_LEVEL,
    block_schemas,
    collect_media_ids,
    replace_media,
    validate_section,
)
from app.schemas.common import check_href

LINK = {"label": "Enquire now", "href": "/admissions"}
PHOTO = {"mediaId": 7}
DOC = {
    "type": "doc",
    "content": [
        {"type": "heading", "attrs": {"level": 2}, "content": [{"type": "text", "text": "Hi"}]},
        {
            "type": "paragraph",
            "content": [
                {
                    "type": "text",
                    "text": "Visit us",
                    "marks": [{"type": "link", "attrs": {"href": "https://example.com/a"}}],
                }
            ],
        },
        {
            "type": "bulletList",
            "content": [
                {
                    "type": "listItem",
                    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x"}]}],
                }
            ],
        },
    ],
}

# One valid example of every top-level section type.
SAMPLES = {
    "hero": {
        "label": "Kallur",
        "headline": "Shape your future at",
        "highlight": "VRR Degree College",
        "text": "Three-year programs.",
        "primaryCta": LINK,
        "secondaryCta": {"label": "View courses", "href": "/courses"},
        "image": PHOTO,
    },
    "stats": {"items": [{"value": "2016", "label": "Established"}]},
    "notice_strip": {"label": "Notices", "items": ["Admissions open"]},
    "page_header": {"title": "About", "subtitle": "Our story", "crumbs": [LINK]},
    "card_grid": {
        "variant": "numbered",
        "heading": "Why VRR",
        "cards": [{"title": "Small classes", "text": "Personal attention"}],
    },
    "collection_list": {"collection": "courses", "layout": "cards", "limit": 3, "cta": LINK},
    "doc_list": {"docs": [{"title": "Affiliation letter", "href": "/uploads/a.pdf"}]},
    "rich_text": {"heading": "Welcome", "body": DOC},
    "quote": {"heading": "Principal", "text": "Welcome", "name": "A", "role": "Principal"},
    "media_gallery": {"heading": "Photos", "items": [{"media": PHOTO, "caption": "Day 1"}]},
    "enquiry_cta": {"heading": "Enquire", "text": "Call us"},
    "two_column": {
        "main": [
            {"type": "rich_text", "data": {"body": DOC}},
            {"type": "timeline", "data": {"items": [{"label": "2016", "text": "Started"}]}},
            {"type": "key_value", "data": {"rows": [{"label": "Seats", "value": "60"}]}},
            {"type": "faq", "data": {"items": [{"question": "Q?", "answer": "A."}]}},
            {"type": "doc_list", "data": {"docs": [{"title": "Form"}]}},
            {"type": "collection_list", "data": {"collection": "news"}},
        ],
        "aside": [
            {
                "type": "panel",
                "data": {"title": "Help", "list": ["a"], "items": [{"heading": "h", "text": "t"}]},
            },
            {"type": "image", "data": {"media": PHOTO}},
            {"type": "enquiry_form", "data": {"title": "Enquiry"}},
            {"type": "contact_info", "data": {}},
            {"type": "map", "data": {"title": "Find us"}},
        ],
    },
}


def test_every_section_type_has_a_valid_example():
    assert set(SAMPLES) == set(SECTION_TYPES)
    for name, data in SAMPLES.items():
        stored = validate_section(name, data)
        # storing the clean result again changes nothing (idempotent)
        assert validate_section(name, stored) == stored


def test_the_two_column_example_uses_every_embedded_type():
    used = {block["type"] for side in ("main", "aside") for block in SAMPLES["two_column"][side]}
    assert used == set(EMBEDDED)


def test_unknown_section_type_is_rejected():
    with pytest.raises(ValueError, match="unknown section type"):
        validate_section("script", {})


def test_unknown_fields_are_rejected():
    data = {**SAMPLES["enquiry_cta"], "html": "<script>alert(1)</script>"}
    with pytest.raises(ValidationError):
        validate_section("enquiry_cta", data)


def test_blocks_match_the_website_types():
    """Drift guard: the website's TypeScript block list must equal the backend registry."""
    types_file = Path(__file__).resolve().parents[2] / "frontend/src/lib/content/types.ts"
    if not types_file.exists():
        pytest.skip("frontend types not available")
    in_ts = set(re.findall(r'Block<"([a-z_]+)"', types_file.read_text()))
    assert in_ts == set(TOP_LEVEL) | set(EMBEDDED)


# ---- text ----


def test_empty_text_counts_as_missing():
    data = {**SAMPLES["hero"], "label": "", "highlight": ""}
    stored = validate_section("hero", data)
    assert "label" not in stored and "highlight" not in stored
    with pytest.raises(ValidationError):  # but a required box cannot be empty
        validate_section("enquiry_cta", {"heading": "", "text": "x"})


@pytest.mark.parametrize(
    "bad",
    ["a\x00b", "a\tb", "a b", "a‮b", "a\x7fb", "line\nbreak"],
)
def test_hidden_and_control_characters_are_rejected_in_titles(bad):
    with pytest.raises(ValidationError):
        validate_section("enquiry_cta", {"heading": bad, "text": "ok"})


def test_paragraphs_may_contain_new_lines_but_not_hidden_characters():
    assert validate_section("enquiry_cta", {"heading": "h", "text": "a\nb"})["text"] == "a\nb"
    with pytest.raises(ValidationError):
        validate_section("enquiry_cta", {"heading": "h", "text": "a‮b"})


def test_length_limits():
    with pytest.raises(ValidationError):
        validate_section("enquiry_cta", {"heading": "x" * 201, "text": "ok"})
    cards = [{"title": f"c{i}"} for i in range(13)]
    with pytest.raises(ValidationError):
        validate_section("card_grid", {"variant": "tiles", "heading": "h", "cards": cards})


# ---- links ----


@pytest.mark.parametrize(
    "good",
    [
        "/",
        "/courses",
        "/news/open-day",
        "#apply",
        "https://example.com/a?b=1",
        "mailto:a@b.co",
        "tel:+919876543210",
        "HTTPS://example.com",
    ],
)
def test_safe_links_are_accepted(good):
    assert check_href(good) == good


@pytest.mark.parametrize(
    "bad",
    [
        "javascript:alert(1)",
        "JaVaScRiPt:alert(1)",
        "data:text/html,<script>1</script>",
        "vbscript:x",
        "//evil.com",
        "/\\evil.com",
        "/\t/evil.com",
        "/\n/evil.com",
        "http://insecure.example",
        "https://",
        "ftp://x.y",
        "evil.com",
        "",
    ],
)
def test_dangerous_links_are_rejected(bad):
    with pytest.raises(ValueError):
        check_href(bad)


def test_links_are_checked_inside_sections():
    bad = {**SAMPLES["hero"], "primaryCta": {"label": "Go", "href": "javascript:alert(1)"}}
    with pytest.raises(ValidationError):
        validate_section("hero", bad)


# ---- rich text ----


def _rich(*content):
    return {"heading": "h", "body": {"type": "doc", "content": list(content)}}


def _para(text="x", **extra):
    return {"type": "paragraph", "content": [{"type": "text", "text": text, **extra}]}


@pytest.mark.parametrize(
    "node",
    [
        {"type": "script", "content": []},
        {"type": "paragraph", "attrs": {"onclick": "x()"}, "content": []},
        {"type": "heading", "attrs": {"level": 1}, "content": [{"type": "text", "text": "x"}]},
        {"type": "heading", "attrs": {"level": 4}, "content": [{"type": "text", "text": "x"}]},
        {"type": "text", "text": "loose text cannot sit at the top"},
        {"type": "listItem", "content": []},
        {"type": "paragraph", "content": [{"type": "image", "attrs": {"src": "x"}}]},
        {"type": "paragraph", "html": "<b>x</b>", "content": []},
        _para("x", marks=[{"type": "link", "attrs": {"href": "javascript:alert(1)"}}]),
        _para("x", marks=[{"type": "link", "attrs": {"href": "https://a.b", "onclick": "x"}}]),
        _para("x", marks=[{"type": "color", "attrs": {"color": "red"}}]),
        _para("x", marks=[{"type": "bold", "attrs": {"x": 1}}]),
        _para("‮"),
        {"type": "paragraph", "content": [{"type": "text", "text": ""}]},
        {"type": "paragraph", "content": [{"type": "text", "text": "x", "content": []}]},
    ],
)
def test_rich_text_attacks_are_rejected(node):
    with pytest.raises(ValidationError):
        validate_section("rich_text", _rich(node))


def test_rich_text_must_be_a_document():
    for body in ({}, {"type": "doc"}, {"type": "doc", "content": []}, {"type": "html"}):
        with pytest.raises(ValidationError):
            validate_section("rich_text", {"body": body})


def test_rich_text_depth_and_size_limits():
    # lists nested deeper than the website draws (it silently drops what is too deep)
    inner = _para()
    for _ in range(5):
        inner = {"type": "bulletList", "content": [{"type": "listItem", "content": [inner]}]}
    with pytest.raises(ValidationError):
        validate_section("rich_text", _rich(inner))
    with pytest.raises(ValidationError):  # too many nodes
        validate_section("rich_text", _rich(*[_para() for _ in range(1100)]))
    with pytest.raises(ValidationError):  # too much text
        validate_section("rich_text", _rich(*[_para("x" * 5000) for _ in range(5)]))


# ---- photos ----


def test_media_pointer_accepts_only_an_id():
    for bad in (
        {"mediaId": 0},
        {"mediaId": "7"},
        {"mediaId": True},
        {"mediaId": 7, "url": "https://evil"},
        {},
    ):
        with pytest.raises(ValidationError):
            validate_section("hero", {**SAMPLES["hero"], "image": bad})


def test_all_photos_in_a_section_are_found_and_replaced():
    data = {
        "main": [{"type": "image", "data": {"media": {"mediaId": 11}}}],
        "aside": [{"type": "image", "data": {"media": {"mediaId": 12}}}],
    }
    stored = validate_section("two_column", data)
    assert collect_media_ids(stored) == {11, 12}
    assert collect_media_ids(validate_section("hero", SAMPLES["hero"])) == {7}
    assert collect_media_ids(validate_section("enquiry_cta", SAMPLES["enquiry_cta"])) == set()

    shown = replace_media(stored, lambda media_id: {"url": f"/uploads/{media_id}.webp"})
    assert shown["main"][0]["data"]["media"] == {"url": "/uploads/11.webp"}
    assert shown["aside"][0]["data"]["media"] == {"url": "/uploads/12.webp"}
    assert stored["main"][0]["data"]["media"] == {"mediaId": 11}  # the stored copy is untouched


# ---- embedded blocks ----


def test_embedded_blocks_are_limited_to_the_allowed_types():
    for bad in ("hero", "two_column", "page_header", "script"):
        data = {"main": [{"type": bad, "data": {}}]}
        with pytest.raises(ValidationError):
            validate_section("two_column", data)
    with pytest.raises(ValidationError):  # a column cannot be empty
        validate_section("two_column", {"main": []})


# ---- admin form schema ----


def test_admin_form_schemas_are_generated_for_every_type():
    schemas = block_schemas()
    assert set(schemas) == set(SECTION_TYPES)
    hero = schemas["hero"]["schema"]
    assert hero["required"] == ["headline", "text", "primaryCta", "image"]
    assert hero["additionalProperties"] is False
    assert hero["$defs"]["MediaPick"]["x-widget"] == "media"
    assert hero["$defs"]["Link"]["properties"]["href"]["x-widget"] == "link"
    rich = schemas["rich_text"]["schema"]["properties"]["body"]
    assert rich["x-widget"] == "richtext"
