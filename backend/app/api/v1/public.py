from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from app.api.deps import DbSession
from app.core.config import get_settings
from app.models.enquiry import Enquiry
from app.schemas.enquiry import EnquiryIn
from app.services.enquiries import client_ip, hash_ip, origin_allowed, recent_enquiry_count
from app.services.mailer import send_enquiry_email
from app.services.turnstile import TurnstileUnavailable, verify_turnstile

router = APIRouter(prefix="/public", tags=["public"])


@router.post("/enquiries", status_code=status.HTTP_201_CREATED)
def create_enquiry(
    payload: EnquiryIn, request: Request, background: BackgroundTasks, db: DbSession
) -> dict[str, bool]:
    """Website enquiry form. Spam is handled in layers: origin, honeypot, Turnstile, rate limit."""
    settings = get_settings()

    if not origin_allowed(request, settings):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")

    # Honeypot: a bot filled the hidden field. Pretend it worked, but save nothing.
    if payload.website:
        return {"ok": True}

    ip = client_ip(request, settings)

    if settings.turnstile_enabled:
        if not payload.turnstile_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Spam check missing")
        try:
            passed = verify_turnstile(
                settings.turnstile_secret.get_secret_value(),  # type: ignore[union-attr]
                payload.turnstile_token,
                ip,
            )
        except TurnstileUnavailable:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE, "Spam check unavailable, try again later"
            ) from None
        if not passed:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Spam check failed")

    ip_hash = hash_ip(ip, settings.secret_key)
    if recent_enquiry_count(db, ip_hash) >= settings.enquiry_rate_limit_per_hour:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many enquiries. Please try again later.",
            headers={"Retry-After": "3600"},
        )

    db.add(
        Enquiry(
            name=payload.name,
            phone=payload.phone,
            course=payload.course,
            message=payload.message,
            source_page=payload.source_page,
            ip_hash=ip_hash,
        )
    )
    db.commit()

    background.add_task(
        send_enquiry_email,
        settings,
        name=payload.name,
        phone=payload.phone,
        course=payload.course,
        message=payload.message,
        source_page=payload.source_page,
    )
    return {"ok": True}
