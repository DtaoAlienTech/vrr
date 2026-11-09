"""What the public API sends to the website. The shapes mirror frontend/src/lib/content/types.ts
(camelCase). Empty optional values are left out of the JSON."""

from typing import Any

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from app.schemas.blocks import DocItem, Link


class Out(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class MediaVariantOut(Out):
    url: str
    width: int


class MediaOut(Out):
    url: str
    alt: str
    width: int
    height: int
    variants: list[MediaVariantOut] | None = None
    crop_bottom: bool | None = None  # only present (true) when a camera date stamp must be hidden


class ContactOut(Out):
    address: str = ""
    phone: str = ""
    whatsapp: str = ""
    email: str = ""
    hours: str = ""
    map_link: str = ""
    map_embed_url: str = ""


class RedirectPublicOut(Out):
    from_path: str
    to_path: str
    status_code: int


class SeoSettingsOut(Out):
    default_title: str
    title_template: str
    description: str
    og_image: MediaOut


class SettingsOut(Out):
    name: str
    short_name: str
    tagline: str
    established: int
    top_bar: str
    logo: MediaOut
    contact: ContactOut
    social: list[Link]
    menu: list[Link]
    footer_courses: list[Link]
    affiliation_text: str
    copyright: str
    seo: SeoSettingsOut


class PageSeoOut(Out):
    title: str
    description: str
    og_image: MediaOut | None = None
    noindex: bool | None = None


class SectionOut(Out):
    id: int
    type: str
    data: dict[str, Any]


class PageSummaryOut(Out):
    key: str
    slug: str
    title: str
    noindex: bool | None = None


class PageOut(Out):
    key: str
    slug: str
    title: str
    seo: PageSeoOut
    sections: list[SectionOut]


class CourseOut(Out):
    slug: str
    tab: str
    name: str
    department: str
    duration: str
    affiliation: str | None = None
    summary: str
    description: dict[str, Any] | None = None
    subjects: list[str] | None = None
    eligibility: str | None = None
    seats: str | None = None
    fees: str | None = None
    syllabus: DocItem | None = None


class ActivityPhotoOut(Out):
    media: MediaOut
    caption: str | None = None


class ActivityOut(Out):
    slug: str
    group: str
    group_key: str
    year: str | None = None
    title: str
    summary: str
    cover: MediaOut
    photos: list[ActivityPhotoOut]


class NewsOut(Out):
    slug: str
    title: str
    category: str
    published_at: str  # YYYY-MM-DD, India time
    summary: str
    body: dict[str, Any]
    pinned: bool | None = None
    attachments: list[DocItem]
    cover: MediaOut | None = None


class FacultyOut(Out):
    id: int
    name: str
    designation: str
    qualification: str
    department: str
    department_key: str
    photo: MediaOut | None = None


class GalleryOut(Out):
    id: int
    media: MediaOut
    caption: str
    category: str
    category_label: str
