"""What the staff endpoints accept (strict, camelCase, unknown fields refused) and return."""

import re
from datetime import datetime
from typing import Any, Literal

from pydantic import AwareDatetime, Field, model_validator

from app.models.enums import (
    ActivityGroup,
    EnquiryStatus,
    GalleryCategory,
    GalleryKind,
    NewsCategory,
    PublishStatus,
    Role,
)
from app.schemas.common import (
    CamelModel,
    DepartmentId,
    Email,
    Id,
    ImageId,
    Line,
    LongSummary,
    Para,
    PdfId,
    RichDoc,
    SeoDescription,
    SeoTitle,
    Short,
    Slug,
    Summary,
    check_href,
)
from app.schemas.public import Out


class AdminOut(Out):
    """Like the public output, but built from database rows."""


class MediaBrief(AdminOut):
    id: int
    kind: str
    url: str
    thumb_url: str
    alt_text: str
    width: int | None = None
    height: int | None = None
    original_filename: str


# ================= news =================


class NewsAttachmentIn(CamelModel):
    media_id: PdfId
    label: Short


class NewsIn(CamelModel):
    title: Line
    slug: Slug | None = Field(
        default=None,
        description="The last part of the web address. Leave empty to make it from the title.",
    )
    category: NewsCategory
    summary: Summary = Field(description="One or two sentences shown in the list and on Google.")
    body: RichDoc
    cover_media_id: ImageId | None = None
    published_at: AwareDatetime | None = Field(
        default=None, description="The date shown. Leave empty to use the moment of saving."
    )
    is_pinned: bool = Field(default=False, description="Keep it at the top of the list.")
    status: PublishStatus = PublishStatus.DRAFT
    seo_title: SeoTitle | None = None
    seo_description: SeoDescription | None = None
    attachments: list[NewsAttachmentIn] = Field(default_factory=list, max_length=10)


class NewsAttachmentOut(AdminOut):
    media: MediaBrief | None = None
    label: str


class NewsAdminOut(AdminOut):
    id: int
    title: str
    slug: str
    category: str
    summary: str
    body: dict[str, Any]
    cover_media: MediaBrief | None = None
    published_at: datetime
    is_pinned: bool
    status: str
    seo_title: str | None = None
    seo_description: str | None = None
    attachments: list[NewsAttachmentOut]
    created_at: datetime
    updated_at: datetime


# ================= activities =================


class ActivityPhotoIn(CamelModel):
    media_id: ImageId
    caption: Line | None = None


class ActivityIn(CamelModel):
    title: Line
    slug: Slug | None = None
    group: ActivityGroup
    year: int | None = Field(default=None, ge=1990, le=2100, strict=True)
    summary: LongSummary
    cover_media_id: ImageId | None = Field(
        default=None, description="Leave empty to use the first photo."
    )
    show_on_home: bool = Field(default=False, description="Also show it on the home page.")
    status: PublishStatus = PublishStatus.DRAFT
    sort_order: int = Field(default=0, ge=0, le=100000)
    photos: list[ActivityPhotoIn] = Field(default_factory=list, max_length=80)


class ActivityPhotoAdminOut(AdminOut):
    media: MediaBrief | None = None
    caption: str | None = None


class ActivityAdminOut(AdminOut):
    id: int
    title: str
    slug: str
    group: str
    year: int | None = None
    summary: str
    cover_media: MediaBrief | None = None
    show_on_home: bool
    status: str
    sort_order: int
    photos: list[ActivityPhotoAdminOut]
    created_at: datetime
    updated_at: datetime


# ================= gallery =================

_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{6,20}$")


class GalleryIn(CamelModel):
    kind: GalleryKind = GalleryKind.PHOTO
    media_id: ImageId | None = None
    youtube_id: str | None = Field(default=None, max_length=20, pattern=_YOUTUBE.pattern)
    category: GalleryCategory = GalleryCategory.CAMPUS
    caption: str = Field(default="", max_length=200)
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_published: bool = True

    @model_validator(mode="after")
    def _content_matches_kind(self) -> "GalleryIn":
        if self.kind == GalleryKind.PHOTO and (self.media_id is None or self.youtube_id):
            raise ValueError("a photo needs mediaId (and no youtubeId)")
        if self.kind == GalleryKind.VIDEO and (self.youtube_id is None or self.media_id):
            raise ValueError("a video needs youtubeId (and no mediaId)")
        return self


class GalleryAdminOut(AdminOut):
    id: int
    kind: str
    media: MediaBrief | None = None
    youtube_id: str | None = None
    category: str
    caption: str
    sort_order: int
    is_published: bool


# ================= departments, courses, faculty =================


class DepartmentIn(CamelModel):
    name: Line
    slug: Slug | None = None
    description: Para | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)


class DepartmentAdminOut(AdminOut):
    id: int
    name: str
    slug: str
    description: str | None = None
    sort_order: int


class CourseIn(CamelModel):
    department_id: DepartmentId
    name: Line
    tab: Short
    slug: Slug | None = None
    duration_years: int = Field(ge=1, le=6, strict=True)
    affiliation: Line | None = None
    summary: Summary
    description: RichDoc | None = None
    subjects: list[Line] = Field(default_factory=list, max_length=40)
    eligibility: Line | None = None
    seats: Short | None = None
    fees: Short | None = None
    syllabus_media_id: PdfId | None = None
    cover_media_id: ImageId | None = None
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_published: bool = True
    seo_title: SeoTitle | None = None
    seo_description: SeoDescription | None = None


class CourseAdminOut(AdminOut):
    id: int
    department_id: int
    department_name: str
    name: str
    tab: str
    slug: str
    duration_years: int
    affiliation: str | None = None
    summary: str
    description: dict[str, Any] | None = None
    subjects: list[str]
    eligibility: str | None = None
    seats: str | None = None
    fees: str | None = None
    syllabus: MediaBrief | None = None
    cover_media: MediaBrief | None = None
    sort_order: int
    is_published: bool
    seo_title: str | None = None
    seo_description: str | None = None


class FacultyIn(CamelModel):
    department_id: DepartmentId
    name: Line
    designation: Line
    qualification: Line
    photo_media_id: ImageId | None = None
    bio: Para | None = Field(default=None, max_length=1000)
    sort_order: int = Field(default=0, ge=0, le=100000)
    is_active: bool = True


class FacultyAdminOut(AdminOut):
    id: int
    department_id: int
    department_name: str
    name: str
    designation: str
    qualification: str
    photo: MediaBrief | None = None
    bio: str | None = None
    sort_order: int
    is_active: bool


class ReorderIn(CamelModel):
    ids: list[Id] = Field(min_length=1, max_length=500)


# ================= pages and their sections =================


class PageIn(CamelModel):
    title: Line
    slug: Slug | None = Field(
        default=None,
        description="The web address of the page. If you change it, the old address redirects.",
    )
    seo_title: SeoTitle | None = None
    seo_description: SeoDescription | None = None
    og_media_id: ImageId | None = Field(
        default=None, description="The picture shown when the page is shared."
    )
    robots_noindex: bool = Field(default=False, description="Ask search engines not to list it.")
    status: PublishStatus = PublishStatus.PUBLISHED


class SectionIn(CamelModel):
    type: str = Field(max_length=40)
    data: dict[str, Any]
    is_visible: bool = True
    position: int | None = Field(default=None, ge=0, le=500)  # left out: at the end


class SectionUpdateIn(CamelModel):
    data: dict[str, Any] | None = None
    is_visible: bool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> "SectionUpdateIn":
        if self.data is None and self.is_visible is None:
            raise ValueError("send data and/or isVisible")
        return self


class SectionAdminOut(AdminOut):
    id: int
    type: str
    position: int
    data: dict[str, Any]
    is_visible: bool


class PageListOut(AdminOut):
    id: int
    key: str
    title: str
    slug: str
    status: str
    robots_noindex: bool
    sections: int
    updated_at: datetime


class PageAdminOut(AdminOut):
    id: int
    key: str
    title: str
    slug: str
    seo_title: str | None = None
    seo_description: str | None = None
    og_media: MediaBrief | None = None
    robots_noindex: bool
    status: str
    published_at: datetime | None = None
    sections: list[SectionAdminOut]
    # every photo the sections point to, by id, so the editor can show them
    media: dict[str, MediaBrief]
    updated_at: datetime


# ================= redirects and history =================


class RedirectIn(CamelModel):
    from_path: str = Field(max_length=300)
    to_path: str = Field(max_length=300)
    status_code: Literal[301, 302, 307, 308] = 301

    @model_validator(mode="after")
    def _local_paths(self) -> "RedirectIn":
        for path in (self.from_path, self.to_path):
            check_href(path)
            if not path.startswith("/") or path.startswith("//"):
                raise ValueError("redirects use site addresses that start with a single /")
        if self.from_path == self.to_path:
            raise ValueError("the two addresses are the same")
        return self


class RedirectAdminOut(AdminOut):
    id: int
    from_path: str
    to_path: str
    status_code: int
    created_at: datetime


class RevisionOut(AdminOut):
    id: int
    entity: str
    entity_id: int
    action: str
    user_id: int | None = None
    user_name: str | None = None
    label: str | None = None  # the item's current title (none once it was deleted)
    created_at: datetime


class RevisionDetailOut(RevisionOut):
    data: dict[str, Any]


# ================= people and enquiries =================


class UserCreateIn(CamelModel):
    email: Email
    name: Short
    role: Role = Role.EDITOR
    password: str = Field(max_length=256)


class UserUpdateIn(CamelModel):
    name: Short | None = None
    role: Role | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _something_to_change(self) -> "UserUpdateIn":
        if self.name is None and self.role is None and self.is_active is None:
            raise ValueError("send name, role and/or isActive")
        return self


class PasswordResetIn(CamelModel):
    new_password: str = Field(max_length=256)


class EnquiryUpdateIn(CamelModel):
    status: EnquiryStatus


class EnquiryAdminOut(AdminOut):
    id: int
    name: str
    phone: str
    course: str | None = None
    message: str | None = None
    status: str
    source_page: str | None = None
    created_at: datetime
    handled_by: int | None = None
    handled_at: datetime | None = None
