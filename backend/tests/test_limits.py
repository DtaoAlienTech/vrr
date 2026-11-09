"""The request size limiter, tested directly with fake web requests."""

import asyncio
import json

import pytest

from app.core.limits import LimitRequestBody

UPLOAD = "/api/v1/admin/media"


def run(path, *, method="POST", announce=None, chunks=(b"x" * 10,), inner=None):
    """Sends one fake request through the limiter. Returns (status, body, bytes the app read)."""
    state = {"read": 0, "called": False}

    async def default_app(scope, receive, send):
        state["called"] = True
        while True:
            message = await receive()
            state["read"] += len(message.get("body", b""))
            if not message.get("more_body"):
                break
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    limiter = LimitRequestBody(
        inner or default_app,
        api_prefix="/api/v1",
        upload_path=UPLOAD,
        upload_bytes=1000,
        default_bytes=100,
    )
    headers = [] if announce is None else [(b"content-length", str(announce).encode())]
    scope = {"type": "http", "method": method, "path": path, "headers": headers}
    queue = list(chunks)

    async def receive():
        body = queue.pop(0) if queue else b""
        return {"type": "http.request", "body": body, "more_body": bool(queue)}

    sent = []

    async def send(message):
        sent.append(message)

    asyncio.run(limiter(scope, receive, send))
    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    body = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, body, state


def test_requests_within_the_limit_pass():
    status, body, state = run(UPLOAD, announce=900, chunks=(b"x" * 500, b"x" * 400))
    assert status == 200 and body == b"ok" and state["read"] == 900


def test_uploads_may_be_larger_than_other_requests():
    assert run("/api/v1/auth/login", chunks=(b"x" * 101,))[0] == 413  # 100 bytes for ordinary calls
    assert run(UPLOAD, chunks=(b"x" * 900,))[0] == 200  # 1000 for uploads
    assert run(UPLOAD, chunks=(b"x" * 1001,))[0] == 413


def test_an_announced_size_that_is_too_big_is_refused_before_anything_is_read():
    status, body, state = run(UPLOAD, announce=5_000_000, chunks=(b"x",))
    assert status == 413 and state["called"] is False
    assert json.loads(body) == {"detail": "The upload is too large.", "code": "file_too_large"}


def test_a_client_that_announces_less_than_it_sends_is_stopped():
    status, _, state = run(UPLOAD, announce=10, chunks=(b"x" * 600, b"x" * 600))
    assert status == 413 and state["read"] < 1200  # stopped partway, not read to the end


def test_a_body_without_a_size_is_counted_too():
    assert run(UPLOAD, chunks=tuple(b"x" * 300 for _ in range(5)))[0] == 413


@pytest.mark.parametrize("method", ["GET", "HEAD", "DELETE", "OPTIONS"])
def test_requests_that_carry_no_body_are_left_alone(method):
    assert run(UPLOAD, method=method, chunks=(b"x" * 5000,))[0] == 200


def test_paths_outside_the_api_are_left_alone():
    assert run("/uploads/x.jpg", chunks=(b"x" * 5000,))[0] == 200
    assert run("/something-else", chunks=(b"x" * 5000,))[0] == 200


def test_other_kinds_of_connections_pass_through():
    called = []

    async def app(scope, receive, send):
        called.append(scope["type"])

    limiter = LimitRequestBody(app, api_prefix="/api/v1", upload_path=UPLOAD, upload_bytes=1)
    asyncio.run(limiter({"type": "lifespan"}, None, None))
    assert called == ["lifespan"]


def test_if_the_answer_already_started_the_problem_is_not_hidden():
    async def late_reader(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        while (await receive()).get("more_body"):
            pass

    with pytest.raises(Exception):  # noqa: B017, PT011  (the limiter's private "too large" signal)
        run(UPLOAD, chunks=(b"x" * 600, b"x" * 600), inner=late_reader)


def test_the_real_application_has_the_limiter_in_place(api):
    big = api.post("/api/v1/auth/login", content=b"x" * (2 * 1024 * 1024))
    assert big.status_code == 413 and big.json()["code"] == "file_too_large"
