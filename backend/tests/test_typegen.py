"""The website's API types are generated from the backend schema and must never be stale."""

from app.main import app
from app.typegen import TARGET, _ts, generate, public_schema_names


def test_the_committed_types_match_the_api():
    """Fails when a public response model changed but ./scripts/generate-types.sh was not run."""
    assert TARGET.exists(), "run ./scripts/generate-types.sh"
    assert TARGET.read_text() == generate(app.openapi())


def test_every_public_answer_has_a_type():
    names = public_schema_names(app.openapi())
    for wanted in ["SettingsOut", "PageOut", "NewsOut", "CourseOut", "FacultyOut", "GalleryOut"]:
        assert wanted in names
    assert "PreviewOut" in names and "RedirectPublicOut" in names


def test_admin_and_error_shapes_are_not_in_the_website_types():
    names = public_schema_names(app.openapi())
    assert not any(name.endswith("AdminOut") for name in names)
    assert "HTTPValidationError" not in names


def test_an_empty_value_is_optional_and_never_null():
    text = generate(app.openapi())
    assert "cover?: MediaOut;" in text  # may be absent
    types_only = text.split("\n\n", 1)[1]  # without the comment at the top
    assert "null" not in types_only


def test_the_converter_handles_the_schema_features_the_api_uses():
    assert _ts({"type": "string"}, 0) == "string"
    assert _ts({"type": "integer"}, 0) == "number"
    assert _ts({"type": "array", "items": {"type": "string"}}, 0) == "string[]"
    assert _ts({"$ref": "#/components/schemas/MediaOut"}, 0) == "MediaOut"
    assert _ts({"enum": ["a", "b"]}, 0) == '"a" | "b"'
    assert _ts({"const": "x"}, 0) == '"x"'
    assert _ts({"type": "object", "additionalProperties": True}, 0) == "Record<string, unknown>"
    union = {"anyOf": [{"type": "string"}, {"type": "null"}]}
    assert _ts(union, 0) == "string | null"
    assert _ts(union, 0, absent_not_null=True) == "string"
    assert _ts({"type": "array", "items": union}, 0) == "(string | null)[]"
    shape = {
        "type": "object",
        "properties": {"a": {"type": "string"}, "b": union},
        "required": ["a"],
    }
    assert _ts(shape, 0) == "{\n  a: string;\n  b?: string;\n}"
