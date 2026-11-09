import hashlib
import hmac
from urllib.parse import urlparse

from fastapi import Request
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.models.enquiry import Enquiry


def client_ip(request: Request, settings: Settings) -> str:
    """The visitor's IP. X-Forwarded-For is trusted only when we run behind our own proxy."""
    if settings.trust_proxy:
        first = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        if first:
            return first
    return request.client.host if request.client else "unknown"


def hash_ip(ip: str, secret_key: str) -> str:
    """Keyed hash, so the stored value cannot be turned back into an IP address."""
    return hmac.new(secret_key.encode(), ip.encode(), hashlib.sha256).hexdigest()


def origin_allowed(request: Request, settings: Settings) -> bool:
    """Browsers send Origin on form posts. Reject posts that come from another website."""
    origin = request.headers.get("origin")
    if not origin:
        return True
    return urlparse(origin).hostname in settings.allowed_host_list


def recent_enquiry_count(db: Session, ip_hash: str) -> int:
    since = func.now() - text("interval '1 hour'")
    stmt = (
        select(func.count())
        .select_from(Enquiry)
        .where(Enquiry.ip_hash == ip_hash, Enquiry.created_at >= since)
    )
    return db.scalar(stmt) or 0
