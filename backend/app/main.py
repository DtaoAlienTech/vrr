from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import get_settings

# Safe defaults on every response. Endpoints may override (for example public GET caching).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
}


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VRR College API",
        version="0.1.0",
        # API docs only in development
        docs_url=None if settings.is_prod else "/api/docs",
        openapi_url=None if settings.is_prod else "/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_host_list)

    @app.middleware("http")
    async def security_headers(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        return response

    app.include_router(api_router, prefix=settings.api_prefix)
    # Development convenience. In Docker, Caddy answers /uploads itself from the shared volume.
    app.mount(
        settings.uploads_url,
        StaticFiles(directory=settings.upload_dir, check_dir=False),
        name="uploads",
    )
    return app


app = create_app()
