from fastapi import Response

from app.core.config import Settings

ACCESS_COOKIE = "vrr_access"
REFRESH_COOKIE = "vrr_refresh"


def _paths(settings: Settings) -> tuple[str, str]:
    # The access cookie goes to every API call; the refresh cookie only to the sign-in endpoints.
    return settings.api_prefix.rsplit("/", 1)[0] or "/", f"{settings.api_prefix}/auth"


def set_auth_cookies(response: Response, settings: Settings, access: str, refresh: str) -> None:
    access_path, refresh_path = _paths(settings)
    common = {"httponly": True, "secure": settings.cookies_secure, "domain": settings.cookie_domain}
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_token_minutes * 60,
        path=access_path,
        samesite="lax",
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_days * 86400,
        path=refresh_path,
        samesite="strict",
        **common,
    )


def clear_auth_cookies(response: Response, settings: Settings) -> None:
    access_path, refresh_path = _paths(settings)
    for name, path in ((ACCESS_COOKIE, access_path), (REFRESH_COOKIE, refresh_path)):
        response.delete_cookie(
            name, path=path, domain=settings.cookie_domain, secure=settings.cookies_secure,
            httponly=True,
        )  # fmt: skip
