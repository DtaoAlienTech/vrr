"""Tells the website that some cached pages are out of date (see the website's
/internal/revalidate route). Best effort: if the website does not answer, the change is still
saved and the website refreshes itself within the hour."""

import logging

import httpx

from app.core.config import Settings

log = logging.getLogger("app.revalidate")

# The tags the website's data layer uses (frontend/src/lib/content/api.ts).
ALL_TAGS = ["settings", "pages", "courses", "activities", "news", "faculty", "gallery"]


def notify(
    settings: Settings, tags: list[str], *, transport: httpx.BaseTransport | None = None
) -> bool:
    """True when the website accepted the request."""
    if not settings.revalidate_url or settings.revalidate_secret is None:
        return False
    try:
        with httpx.Client(transport=transport, timeout=5) as client:
            response = client.post(
                settings.revalidate_url,
                json={"tags": tags},
                headers={"x-revalidate-secret": settings.revalidate_secret.get_secret_value()},
            )
        response.raise_for_status()
    except httpx.HTTPError as error:
        # only the kind of problem is logged: the address and secret stay out of the logs
        log.warning("the website could not be told to refresh (%s)", type(error).__name__)
        return False
    return True
