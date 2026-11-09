"""Building blocks shared by every content schema: a strict base model, safe text, safe links,
media pointers and rich text. Everything an editor can type goes through these checks."""

import re
from typing import Annotated, Any
from urllib.parse import urlsplit

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    WithJsonSchema,
    model_validator,
)
from pydantic.alias_generators import to_camel

from app.db.base import SLUG_REGEX


class CamelModel(BaseModel):
    """JSON uses camelCase (like the website code); Python uses snake_case. Unknown fields are
    rejected, so nothing unexpected can be stored."""

    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _empty_text_means_missing(cls, data: Any) -> Any:
        # An admin form sends "" for a box left empty: treat that as "not provided".
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value != ""}
        return data


# ---- Text ----

# Characters that can hide or reorder text: line/paragraph separators and bidi overrides.
_HIDDEN_CHARS = {0x2028, 0x2029, *range(0x202A, 0x202F), *range(0x2066, 0x206A)}


def _check_text(value: str, *, multiline: bool) -> str:
    for char in value:
        code = ord(char)
        allowed_newline = multiline and char == "\n"
        if (code < 32 and not allowed_newline) or code == 127 or code in _HIDDEN_CHARS:
            raise ValueError("text contains characters that are not allowed")
    return value


def _one_line(value: str) -> str:
    return _check_text(value, multiline=False)


def _many_lines(value: str) -> str:
    return _check_text(value, multiline=True)


def _line(max_length: int) -> Any:
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(_one_line),
    ]


Short = _line(80)  # labels, button text, names
Line = _line(200)  # titles, headlines
Para = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=1500),
    AfterValidator(_many_lines),
]


# ---- Links ----

_SAFE_START = re.compile(r"^(/(?![/\\])|#|https://|mailto:|tel:)", re.IGNORECASE)


def check_href(value: str) -> str:
    """Site path, #anchor, https, mailto or tel only. Mirrors the website's safeHref rule: control
    characters and backslashes are refused because browsers turn "/\\t/evil.com" and "/\\evil.com"
    into the address "//evil.com"."""
    if any(ord(char) < 32 or ord(char) == 127 or char == "\\" for char in value):
        raise ValueError("link contains characters that are not allowed")
    if not _SAFE_START.match(value):
        raise ValueError("link must start with /, #, https://, mailto: or tel:")
    if value.lower().startswith("https://") and not urlsplit(value).hostname:
        raise ValueError("link has no website address")
    return value


Href = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=500),
    AfterValidator(check_href),
    WithJsonSchema({"type": "string", "minLength": 1, "maxLength": 500, "x-widget": "link"}),
]


# ---- Media ----


class MediaPick(CamelModel):
    """A pointer to a library photo. Pages store only the id; the public API adds the address,
    size and alt text. Anything else in the object is rejected."""

    model_config = ConfigDict(json_schema_extra={"x-widget": "media"})
    media_id: int = Field(gt=0, strict=True)  # a real number: no "7", no true


# ---- Rich text (restricted editor JSON; the website draws it with React, never as HTML) ----

MAX_RICH_DEPTH = 6  # same limit as the website's renderer
MAX_RICH_NODES = 2000
MAX_RICH_CHARS = 20000

_CHILDREN: dict[str, set[str]] = {
    "doc": {"paragraph", "heading", "bulletList", "orderedList", "blockquote"},
    "paragraph": {"text", "hardBreak"},
    "heading": {"text", "hardBreak"},
    "bulletList": {"listItem"},
    "orderedList": {"listItem"},
    "listItem": {"paragraph", "bulletList", "orderedList"},
    "blockquote": {"paragraph"},
    "text": set(),
    "hardBreak": set(),
}
_NODE_KEYS = {"type", "text", "attrs", "marks", "content"}
_MARKS = {"bold", "italic", "underline", "link"}


class _Budget:
    def __init__(self) -> None:
        self.nodes = 0
        self.chars = 0


def _check_marks(marks: Any) -> None:
    if not isinstance(marks, list) or len(marks) > 4:
        raise ValueError("rich text marks are invalid")
    for mark in marks:
        if not isinstance(mark, dict) or not set(mark) <= {"type", "attrs"}:
            raise ValueError("rich text mark is invalid")
        kind = mark.get("type")
        if kind not in _MARKS:
            raise ValueError("rich text mark type is not allowed")
        attrs = mark.get("attrs")
        if kind == "link":
            if (
                not isinstance(attrs, dict)
                or set(attrs) != {"href"}
                or not isinstance(attrs["href"], str)
            ):
                raise ValueError("rich text link needs an href")
            check_href(attrs["href"].strip())
        elif attrs not in (None, {}):
            raise ValueError("rich text mark has unexpected attributes")


def _check_node(node: Any, parent: str, depth: int, budget: _Budget) -> None:
    if not isinstance(node, dict) or not set(node) <= _NODE_KEYS:
        raise ValueError("rich text node is invalid")
    kind = node.get("type")
    if not isinstance(kind, str) or kind not in _CHILDREN:
        raise ValueError("rich text node type is not allowed")
    if kind not in _CHILDREN[parent]:
        raise ValueError(f"rich text: {kind} is not allowed inside {parent}")
    if depth > MAX_RICH_DEPTH:
        raise ValueError("rich text is nested too deeply")
    budget.nodes += 1
    if budget.nodes > MAX_RICH_NODES:
        raise ValueError("rich text is too long")

    if kind == "text":
        text = node.get("text")
        if not isinstance(text, str) or not text or "content" in node or "attrs" in node:
            raise ValueError("rich text text node is invalid")
        budget.chars += len(text)
        if budget.chars > MAX_RICH_CHARS:
            raise ValueError("rich text is too long")
        _many_lines(text)
        if "marks" in node:
            _check_marks(node["marks"])
        return

    if "text" in node or "marks" in node:
        raise ValueError("rich text: only text nodes carry text or marks")
    attrs = node.get("attrs")
    if kind == "heading":
        if not isinstance(attrs, dict) or set(attrs) != {"level"} or attrs["level"] not in (2, 3):
            raise ValueError("rich text headings must be level 2 or 3")
    elif attrs not in (None, {}):
        raise ValueError("rich text node has unexpected attributes")
    children = node.get("content", [])
    if not isinstance(children, list):
        raise ValueError("rich text content must be a list")
    for child in children:
        _check_node(child, kind, depth + 1, budget)


def check_rich_doc(value: dict[str, Any]) -> dict[str, Any]:
    if set(value) - {"type", "content"} or value.get("type") != "doc":
        raise ValueError("rich text must be a document")
    content = value.get("content")
    if not isinstance(content, list) or not content:
        raise ValueError("rich text must not be empty")
    budget = _Budget()
    for node in content:
        _check_node(node, "doc", 0, budget)
    return value


RichDoc = Annotated[
    dict[str, Any],
    AfterValidator(check_rich_doc),
    WithJsonSchema({"type": "object", "x-widget": "richtext"}),
]


AltText = _line(300)  # what a picture shows, for people who cannot see it (and for search engines)


def _paragraph(max_length: int) -> Any:
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=max_length),
        AfterValidator(_many_lines),
    ]


Summary = _paragraph(400)  # the short text of a news item or a course
LongSummary = _paragraph(500)
SeoTitle = _line(120)
SeoDescription = _line(300)
Slug = Annotated[str, StringConstraints(min_length=1, max_length=120, pattern=SLUG_REGEX)]
EMAIL_REGEX = r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$"
Email = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_lower=True, max_length=254, pattern=EMAIL_REGEX),
]
Id = Annotated[int, Field(gt=0, strict=True)]  # a database id: a real number, never "7" or true
# the same, but the admin form shows a photo picker / PDF picker (see x-widget in the JSON Schema)
ImageId = Annotated[
    int,
    Field(gt=0, strict=True),
    WithJsonSchema({"type": "integer", "minimum": 1, "x-widget": "media-image"}),
]
DepartmentId = Annotated[
    int,
    Field(gt=0, strict=True),
    WithJsonSchema({"type": "integer", "minimum": 1, "x-widget": "department"}),
]
PdfId = Annotated[
    int,
    Field(gt=0, strict=True),
    WithJsonSchema({"type": "integer", "minimum": 1, "x-widget": "media-pdf"}),
]
