"""Errors that the website can act on: a readable message plus a stable `code` (for example
"totp_required" tells the login form to ask for the six-digit code)."""

from typing import Any

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        detail: str,
        headers: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.code = code
        self.detail = detail
        self.headers = headers
        self.extra = extra or {}


async def api_error_handler(_: Request, error: ApiError) -> JSONResponse:
    return JSONResponse(
        {"detail": error.detail, "code": error.code, **error.extra},
        status_code=error.status_code,
        headers=error.headers,
    )


def field_errors(error: ValidationError | RequestValidationError) -> list[dict[str, str]]:
    """One entry per problem: which field and what is wrong (the value itself is never echoed)."""
    problems = []
    for item in error.errors():
        location = list(item["loc"])
        if isinstance(error, RequestValidationError):
            location = location[1:]  # drop "body" / "query" / "path": where the field was sent
        field = ".".join(str(part) for part in location)
        problems.append({"field": field, "message": str(item["msg"])})
    return problems


async def validation_error_handler(_: Request, error: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        {
            "detail": "Please check the fields marked below.",
            "code": "validation_error",
            "errors": field_errors(error),
        },
        status_code=422,
    )
