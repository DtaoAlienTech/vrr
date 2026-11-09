from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.api.cookies import ACCESS_COOKIE
from app.core import security
from app.core.config import get_settings
from app.core.errors import ApiError
from app.db.session import get_db
from app.models.enums import Role
from app.services.auth import Auth, load_auth
from app.services.enquiries import origin_allowed

# Reusable dependency types: declare `db: DbSession` in any endpoint.
DbSession = Annotated[Session, Depends(get_db)]

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def same_origin(request: Request) -> None:
    """Refuses requests that a browser says came from another website."""
    if not origin_allowed(request, get_settings()):
        raise ApiError(403, "bad_origin", "This request is not allowed.")


def current_auth(request: Request, db: DbSession) -> Auth:
    """The signed-in person (any role). Every request that changes something must also come from
    our own website and carry the CSRF token, so no endpoint can forget these checks."""
    settings = get_settings()
    token = request.cookies.get(ACCESS_COOKIE)
    claims = security.read_access_token(settings, token) if token else None
    auth = None
    if claims is not None and str(claims["sub"]).isdigit():
        auth = load_auth(db, claims["sid"], int(claims["sub"]))
    if auth is None:
        raise ApiError(401, "not_authenticated", "Please sign in.")
    if request.method not in _SAFE_METHODS:
        same_origin(request)
        if not security.csrf_matches(
            settings, auth.session.id, request.headers.get("x-csrf-token")
        ):
            raise ApiError(
                403, "csrf_failed", "The security check failed. Reload the page and try again."
            )
    return auth


SignedIn = Annotated[Auth, Depends(current_auth)]


def require_staff(auth: SignedIn) -> Auth:
    """Any signed-in staff member. A super admin who has not turned on two-factor login yet can
    do nothing else until they have."""
    if auth.needs_totp_setup:
        raise ApiError(403, "totp_setup_required", "Turn on two-factor login to continue.")
    return auth


Staff = Annotated[Auth, Depends(require_staff)]


def require_super_admin(auth: Staff) -> Auth:
    if auth.user.role != Role.SUPER_ADMIN:
        raise ApiError(403, "forbidden", "Only a super admin can do this.")
    return auth


SuperAdmin = Annotated[Auth, Depends(require_super_admin)]
