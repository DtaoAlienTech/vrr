"""Site-wide settings, stored as one JSON document per group in `site_settings`.
The admin edits one group at a time; every group is validated by the model below."""

from typing import Annotated, Any

from pydantic import AfterValidator, Field, StringConstraints

from app.schemas.blocks import Link
from app.schemas.common import CamelModel, Href, Line, MediaPick, Short

# Only Google Maps "embed" addresses may be framed (the page security policy allows just these).
_MAP_EMBED_PREFIX = "https://www.google.com/maps/embed"


def _check_map_embed(value: str) -> str:
    if not value.startswith(_MAP_EMBED_PREFIX) or any(ord(c) < 33 or c == "\\" for c in value):
        raise ValueError(f"must be a Google Maps embed address ({_MAP_EMBED_PREFIX}...)")
    return value


Phone = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^[+0-9 ()-]{6,20}$")]
Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, max_length=254, pattern=r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$"
    ),
]
MapEmbed = Annotated[str, StringConstraints(max_length=1000), AfterValidator(_check_map_embed)]


class Brand(CamelModel):
    name: Short
    short_name: Short
    tagline: Short
    established: int = Field(ge=1800, le=2100, strict=True)
    top_bar: Line
    affiliation_text: Line
    copyright: Line
    logo: MediaPick


class Contact(CamelModel):
    address: Line
    phone: Phone | None = None
    whatsapp: Phone | None = None
    email: Email | None = None
    hours: Line | None = None
    map_link: Href | None = None
    map_embed_url: MapEmbed | None = None


class LinkList(CamelModel):
    items: list[Link] = Field(max_length=20)


class Seo(CamelModel):
    default_title: Line
    title_template: Annotated[str, StringConstraints(max_length=120, pattern=r".*%s.*")]
    description: Annotated[str, StringConstraints(max_length=300)]
    og_image: MediaPick


# key in site_settings -> model. `menu` and `footer_courses` are the header and footer link lists.
SETTINGS_GROUPS: dict[str, type[CamelModel]] = {
    "brand": Brand,
    "contact": Contact,
    "social": LinkList,
    "menu": LinkList,
    "footer_courses": LinkList,
    "seo": Seo,
}


def validate_settings(group: str, data: Any) -> dict[str, Any]:
    model = SETTINGS_GROUPS.get(group)
    if model is None:
        raise ValueError("unknown settings group")
    return model.model_validate(data).model_dump(mode="json", by_alias=True, exclude_none=True)
