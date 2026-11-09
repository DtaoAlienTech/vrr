"""Sign in, sign out and two-factor login for the admin panel."""

from typing import Any

from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.api.deps import DbSession, SignedIn, same_origin
from app.core import security
from app.core.config import get_settings
from app.core.errors import ApiError
from app.schemas.auth import (
    ChangePasswordIn,
    LoginIn,
    RecoveryCodesOut,
    SessionOut,
    TotpCodeIn,
    TotpDisableIn,
    TotpSetupOut,
    UserOut,
)
from app.services import auth as auth_service
from app.services.auth import Auth
from app.services.enquiries import client_ip

router = APIRouter(prefix="/auth", tags=["auth"])


def _session_out(auth: Auth) -> SessionOut:
    settings = get_settings()
    user = auth.user
    return SessionOut(
        user=UserOut(
            id=user.id,
            email=user.email,
            name=user.name,
            role=user.role,
            totp_enabled=user.totp_enabled,
            needs_totp_setup=auth.needs_totp_setup,
        ),
        csrf_token=security.csrf_token(settings, auth.session.id),
    )


def _start(response: Response, auth: Auth, refresh_token: str) -> SessionOut:
    settings = get_settings()
    access = security.create_access_token(
        settings, user_id=auth.user.id, session_id=auth.session.id
    )
    set_auth_cookies(response, settings, access, refresh_token)
    return _session_out(auth)


@router.post("/login", dependencies=[Depends(same_origin)])
def login(payload: LoginIn, request: Request, response: Response, db: DbSession) -> SessionOut:
    settings = get_settings()
    auth, refresh_token = auth_service.login(
        db,
        settings,
        email=payload.email,
        password=payload.password,
        totp_code=payload.totp_code,
        recovery_code=payload.recovery_code,
        ip=client_ip(request, settings),
        user_agent=request.headers.get("user-agent"),
    )
    return _start(response, auth, refresh_token)


@router.post("/refresh", dependencies=[Depends(same_origin)], response_model=SessionOut)
def refresh(request: Request, response: Response, db: DbSession) -> Any:
    settings = get_settings()
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise ApiError(401, "invalid_session", "Please sign in again.")
    try:
        auth, new_token = auth_service.refresh_session(
            db,
            settings,
            token,
            ip=client_ip(request, settings),
            user_agent=request.headers.get("user-agent"),
        )
    except ApiError as error:
        if error.code == "session_replaced":
            raise  # a harmless race with another tab: keep the cookies the other tab just set
        # Not valid any more: tell the browser to stop sending it. (A raised error would drop the
        # cookie instructions, so the error response is built here.)
        failed = JSONResponse(
            {"detail": error.detail, "code": error.code}, status_code=error.status_code
        )
        clear_auth_cookies(failed, settings)
        return failed
    return _start(response, auth, new_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(same_origin)])
def logout(request: Request, response: Response, db: DbSession) -> None:
    """Ends this login. Works even when the access token has already expired."""
    settings = get_settings()
    token = request.cookies.get(REFRESH_COOKIE)
    if token:
        auth_service.end_session(db, token, ip=client_ip(request, settings))
    clear_auth_cookies(response, settings)


@router.get("/me")
def me(auth: SignedIn) -> SessionOut:
    return _session_out(auth)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: ChangePasswordIn, request: Request, auth: SignedIn, db: DbSession
) -> None:
    auth_service.change_password(
        db,
        auth,
        current=payload.current_password,
        new=payload.new_password,
        ip=client_ip(request, get_settings()),
    )


@router.post("/totp/setup")
def totp_setup(auth: SignedIn, db: DbSession) -> TotpSetupOut:
    secret, uri = auth_service.begin_totp_setup(db, get_settings(), auth.user)
    return TotpSetupOut(secret=secret, otpauth_uri=uri)


@router.post("/totp/enable")
def totp_enable(
    payload: TotpCodeIn, request: Request, auth: SignedIn, db: DbSession
) -> RecoveryCodesOut:
    settings = get_settings()
    codes = auth_service.enable_totp(
        db, settings, auth, payload.code, ip=client_ip(request, settings)
    )
    return RecoveryCodesOut(recovery_codes=codes)


@router.post("/totp/disable", status_code=status.HTTP_204_NO_CONTENT)
def totp_disable(payload: TotpDisableIn, request: Request, auth: SignedIn, db: DbSession) -> None:
    settings = get_settings()
    auth_service.disable_totp(
        db,
        settings,
        auth.user,
        password=payload.password,
        code=payload.code,
        ip=client_ip(request, settings),
    )
