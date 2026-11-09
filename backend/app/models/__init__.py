"""Import every model module here so Alembic and the app see the full schema.

Next models (Phase 1): users, site_settings, media, pages, page_sections, courses, faculty, news,
activities, gallery_items, redirects, content_revisions, audit_log.
"""

from app.models.enquiry import Enquiry

__all__ = ["Enquiry"]
