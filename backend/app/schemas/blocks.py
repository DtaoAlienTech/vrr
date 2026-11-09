"""The shape of every page section, written once.

Each section type is one model here. It checks every save, produces the JSON Schema that builds
the admin form, and mirrors the website's TypeScript types (frontend/src/lib/content/types.ts).
Adding a field is one line. Photos are stored as {"mediaId": 12}; the public API swaps that for
the real picture address.
"""

from collections.abc import Callable
from typing import Annotated, Any, Literal, Union

from pydantic import Field, create_model

from app.schemas.common import CamelModel, Href, Line, MediaPick, Para, RichDoc, Short

Tone = Literal["default", "alt"]
CollectionName = Literal["courses", "activities", "news", "faculty", "gallery"]


class Link(CamelModel):
    label: Short
    href: Href


class DocItem(CamelModel):
    title: Line
    note: Line | None = None
    href: Href | None = None


# ---- Embedded blocks (they can sit inside a two-column section) ----


class RichTextData(CamelModel):
    tone: Tone = "default"
    heading: Line | None = None
    body: RichDoc


class TimelineItem(CamelModel):
    label: Short
    text: Para


class TimelineData(CamelModel):
    items: list[TimelineItem] = Field(min_length=1, max_length=30)


class KeyValueRow(CamelModel):
    label: Short
    value: Line


class KeyValueData(CamelModel):
    rows: list[KeyValueRow] = Field(min_length=1, max_length=30)


class FaqItem(CamelModel):
    question: Line
    answer: Para


class FaqData(CamelModel):
    items: list[FaqItem] = Field(min_length=1, max_length=30)


class PanelItem(CamelModel):
    heading: Short
    text: Para


class PanelData(CamelModel):
    title: Line | None = None
    items: list[PanelItem] | None = Field(default=None, max_length=12)
    # the JSON key is "list" (as on the website); the Python name avoids hiding the built-in type
    bullets: list[Line] | None = Field(default=None, alias="list", max_length=20)


class ImageData(CamelModel):
    media: MediaPick


class EnquiryFormData(CamelModel):
    title: Line


class ContactInfoData(CamelModel):
    heading: Line | None = None


class MapData(CamelModel):
    title: Line | None = None


class DocListData(CamelModel):
    tone: Tone = "default"
    heading: Line | None = None
    intro: Para | None = None
    docs: list[DocItem] = Field(min_length=1, max_length=30)


class CollectionListData(CamelModel):
    collection: CollectionName
    layout: Literal["cards", "detailed", "albums", "list", "grid", "mosaic"] | None = None
    tone: Tone = "default"
    heading: Line | None = None
    intro: Para | None = None
    limit: int | None = Field(default=None, ge=1, le=50)
    cta: Link | None = None


# type name -> data model, for blocks allowed inside two_column
EMBEDDED: dict[str, type[CamelModel]] = {
    "rich_text": RichTextData,
    "timeline": TimelineData,
    "key_value": KeyValueData,
    "faq": FaqData,
    "panel": PanelData,
    "image": ImageData,
    "enquiry_form": EnquiryFormData,
    "contact_info": ContactInfoData,
    "map": MapData,
    "doc_list": DocListData,
    "collection_list": CollectionListData,
}


def _embedded_section(type_name: str, data_model: type[CamelModel]) -> type[CamelModel]:
    """{type, data, isVisible} wrapper for one embedded block (the `type` picks the data model)."""
    return create_model(
        f"Embedded{type_name.title().replace('_', '')}",
        __base__=CamelModel,
        type=(Literal[type_name], ...),
        data=(data_model, ...),
        is_visible=(bool, True),
    )


EmbeddedSection = Annotated[
    Union[tuple(_embedded_section(name, model) for name, model in EMBEDDED.items())],  # noqa: UP007
    Field(discriminator="type"),
]


# ---- Top-level sections ----


class HeroData(CamelModel):
    label: Short | None = None
    headline: Line
    highlight: Short | None = None
    text: Para
    primary_cta: Link
    secondary_cta: Link | None = None
    image: MediaPick


class StatItem(CamelModel):
    value: Short
    label: Short


class StatsData(CamelModel):
    items: list[StatItem] = Field(min_length=1, max_length=6)


class NoticeStripData(CamelModel):
    label: Short
    items: list[Line] = Field(min_length=1, max_length=12)


class PageHeaderData(CamelModel):
    title: Line
    subtitle: Para | None = None
    crumbs: list[Link] | None = Field(default=None, max_length=4)


class Card(CamelModel):
    title: Line
    text: Para | None = None


class CardGridData(CamelModel):
    variant: Literal["numbered", "tiles", "steps"]
    tone: Tone = "default"
    heading: Line
    intro: Para | None = None
    cards: list[Card] = Field(min_length=1, max_length=12)


class QuoteData(CamelModel):
    heading: Line
    text: Para
    name: Short
    role: Short
    image: MediaPick | None = None


class GalleryEntry(CamelModel):
    media: MediaPick
    caption: str = Field(default="", max_length=200)


class MediaGalleryData(CamelModel):
    heading: Line
    intro: Para | None = None
    cta: Link | None = None
    items: list[GalleryEntry] = Field(min_length=1, max_length=24)


class EnquiryCtaData(CamelModel):
    heading: Line
    text: Para


class TwoColumnData(CamelModel):
    tone: Tone = "default"
    heading: Line | None = None
    intro: Para | None = None
    main: list[EmbeddedSection] = Field(min_length=1, max_length=8)
    aside: list[EmbeddedSection] = Field(default_factory=list, max_length=8)


# type name -> (label shown in the admin, data model)
TOP_LEVEL: dict[str, tuple[str, type[CamelModel]]] = {
    "hero": ("Hero (home banner)", HeroData),
    "stats": ("Numbers strip", StatsData),
    "notice_strip": ("Notice strip", NoticeStripData),
    "page_header": ("Page title", PageHeaderData),
    "card_grid": ("Cards", CardGridData),
    "collection_list": ("List (courses, news, ...)", CollectionListData),
    "doc_list": ("Documents", DocListData),
    "rich_text": ("Text", RichTextData),
    "quote": ("Message with name", QuoteData),
    "media_gallery": ("Photo gallery", MediaGalleryData),
    "enquiry_cta": ("Enquiry band", EnquiryCtaData),
    "two_column": ("Two columns", TwoColumnData),
}
SECTION_TYPES = tuple(TOP_LEVEL)


def validate_section(type_name: str, data: Any) -> dict[str, Any]:
    """Checks a section's data and returns the clean JSON to store. Raises ValueError (pydantic's
    ValidationError is one) when the type is unknown or the data is invalid."""
    entry = TOP_LEVEL.get(type_name)
    if entry is None:
        raise ValueError("unknown section type")
    return entry[1].model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=True)


def block_schemas() -> dict[str, dict[str, Any]]:
    """What the admin needs to build a form for each section type."""
    return {
        name: {
            "label": label,
            "schema": model.model_json_schema(by_alias=True, mode="validation"),
        }
        for name, (label, model) in TOP_LEVEL.items()
    }


# ---- Media pointers inside stored data ----


def _is_media_pointer(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == {"mediaId"}


def collect_media_ids(data: Any) -> set[int]:
    """Every library photo a section points to (to check they exist and to know what is in use)."""
    if _is_media_pointer(data):
        return {data["mediaId"]}
    if isinstance(data, dict):
        return set().union(*(collect_media_ids(v) for v in data.values())) if data else set()
    if isinstance(data, list):
        return set().union(*(collect_media_ids(v) for v in data)) if data else set()
    return set()


def replace_media(data: Any, resolve: Callable[[int], Any]) -> Any:
    """Copy of `data` with each {"mediaId": n} replaced by resolve(n) (the public picture info)."""
    if _is_media_pointer(data):
        return resolve(data["mediaId"])
    if isinstance(data, dict):
        return {key: replace_media(value, resolve) for key, value in data.items()}
    if isinstance(data, list):
        return [replace_media(value, resolve) for value in data]
    return data
