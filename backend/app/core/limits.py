"""Refuses oversized request bodies before they are read into memory or onto disk."""

import json
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]


class _TooLarge(Exception):
    pass


class LimitRequestBody:
    """ASGI middleware: uploads may be up to `upload_bytes`, every other API request body up to
    `default_bytes`. The announced size (Content-Length) is checked first, and the bytes actually
    received are counted too, because a client can announce less than it sends."""

    def __init__(
        self,
        app: Callable[[Scope, Receive, Send], Awaitable[None]],
        *,
        api_prefix: str,
        upload_path: str,
        upload_bytes: int,
        default_bytes: int = 1024 * 1024,
    ) -> None:
        self.app = app
        self.api_prefix = api_prefix
        self.upload_path = upload_path
        self.upload_bytes = upload_bytes
        self.default_bytes = default_bytes

    def _limit(self, scope: Scope) -> int | None:
        path: str = scope["path"]
        if scope["method"] not in ("POST", "PUT", "PATCH"):
            return None
        if path == self.upload_path:
            return self.upload_bytes
        return self.default_bytes if path.startswith(self.api_prefix) else None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        limit = self._limit(scope) if scope["type"] == "http" else None
        if limit is None:
            await self.app(scope, receive, send)
            return

        started = False

        async def tracking_send(message: Message) -> None:
            nonlocal started
            started = started or message["type"] == "http.response.start"
            await send(message)

        announced = dict(scope["headers"]).get(b"content-length", b"")
        if announced.isdigit() and int(announced) > limit:
            await self._refuse(tracking_send)
            return

        received = 0

        async def counting_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _TooLarge
            return message

        try:
            await self.app(scope, counting_receive, tracking_send)
        except _TooLarge:
            if started:
                raise
            await self._refuse(tracking_send)

    @staticmethod
    async def _refuse(send: Send) -> None:
        body = json.dumps({"detail": "The upload is too large.", "code": "file_too_large"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(body)).encode()),
                    (b"connection", b"close"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
