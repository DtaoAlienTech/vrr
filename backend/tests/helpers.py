import time
from typing import Any

import pyotp
from fastapi.testclient import TestClient

from app.core import security
from app.core.config import get_settings
from app.models import User

LOGIN = "/api/v1/auth/login"


def sign_in(api: TestClient, email: str = "staff@example.org", password: str | None = None,
            ip: str | None = None, **extra: Any):  # fmt: skip
    from tests.conftest import PASSWORD

    headers = {"X-Forwarded-For": ip} if ip else {}
    body = {"email": email, "password": password or PASSWORD, **extra}
    return api.post(LOGIN, json=body, headers=headers)


def changes(csrf: str) -> dict[str, str]:
    """Headers every state-changing request needs (what the admin page sends)."""
    return {"X-CSRF-Token": csrf, "Origin": "http://localhost"}


def signed_in(api: TestClient, **kwargs: Any) -> str:
    """Signs in and returns the CSRF token."""
    response = sign_in(api, **kwargs)
    assert response.status_code == 200, response.text
    return response.json()["csrfToken"]


def code_for(secret: str, offset: int = 0) -> str:
    """The authenticator app's code for the current 30-second step (+ offset steps)."""
    return pyotp.TOTP(secret).generate_otp(int(time.time()) // 30 + offset)


def secret_of(user: User) -> str:
    secret = security.decrypt_secret(get_settings(), user.totp_secret or "")
    assert secret
    return secret
