"""Import every model module here so Alembic and the app see the full schema."""

from app.models.activity import Activity, ActivityPhoto
from app.models.catalog import Course, Department, Faculty
from app.models.enquiry import Enquiry
from app.models.gallery import GalleryItem
from app.models.media import Media
from app.models.news import News, NewsAttachment
from app.models.page import Page, PageSection
from app.models.site_setting import SiteSetting
from app.models.system import AuditLog, ContentRevision, Redirect
from app.models.user import User, UserSession

__all__ = [
    "Activity",
    "ActivityPhoto",
    "AuditLog",
    "ContentRevision",
    "Course",
    "Department",
    "Enquiry",
    "Faculty",
    "GalleryItem",
    "Media",
    "News",
    "NewsAttachment",
    "Page",
    "PageSection",
    "Redirect",
    "SiteSetting",
    "User",
    "UserSession",
]
