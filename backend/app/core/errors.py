"""Errors that the website can act on: a readable message plus a stable `code` (for example
"totp_required" tells the login form to ask for the six-digit code)."""

from fastapi import Request
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers


async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        {"detail": error.detail, "code": error.code},
        status_code=error.status_code,
        headers=error.headers,
    )
