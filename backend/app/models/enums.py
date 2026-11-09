"""Every fixed list of values, written once. The database CHECK constraints and the API validation
both use these, so they can never disagree."""

from enum import StrEnum


class Role(StrEnum):
    SUPER_ADMIN = "super_admin"
    EDITOR = "editor"


class PublishStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"


class MediaKind(StrEnum):
    IMAGE = "image"
    PDF = "pdf"


class NewsCategory(StrEnum):
    ADMISSION = "admission"
    NOTICE = "notice"
    EVENT = "event"
    EXAM = "exam"
    ACTIVITY = "activity"


class ActivityGroup(StrEnum):
    LEO = "leo"
    NSS = "nss"
    CULTURAL = "cultural"
    SPORTS = "sports"
    OTHER = "other"


class GalleryKind(StrEnum):
    PHOTO = "photo"
    VIDEO = "video"


class GalleryCategory(StrEnum):
    CAMPUS = "campus"
    LEO = "leo"
    NSS = "nss"
    OTHER = "other"


class PageKey(StrEnum):
    HOME = "home"
    ABOUT = "about"
    COURSES = "courses"
    FACULTY = "faculty"
    ADMISSIONS = "admissions"
    ACTIVITIES = "activities"
    GALLERY = "gallery"
    NEWS = "news"
    CONTACT = "contact"
    PRIVACY = "privacy"


class EnquiryStatus(StrEnum):
    NEW = "new"
    CONTACTED = "contacted"
    CLOSED = "closed"


class RevisionAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    RESTORE = "restore"


# Words shown on the website for each value above.
GROUP_LABELS = {
    ActivityGroup.LEO: "Leo Club",
    ActivityGroup.NSS: "NSS",
    ActivityGroup.CULTURAL: "Cultural",
    ActivityGroup.SPORTS: "Sports",
    ActivityGroup.OTHER: "Other",
}
CATEGORY_LABELS = {
    NewsCategory.ADMISSION: "Admission",
    NewsCategory.NOTICE: "Notice",
    NewsCategory.EVENT: "Event",
    NewsCategory.EXAM: "Exam",
    NewsCategory.ACTIVITY: "Activity",
}
GALLERY_LABELS = {
    GalleryCategory.CAMPUS: "Campus",
    GalleryCategory.LEO: "Leo Club",
    GalleryCategory.NSS: "NSS",
    GalleryCategory.OTHER: "Other",
}
