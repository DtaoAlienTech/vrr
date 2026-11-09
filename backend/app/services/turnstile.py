import httpx

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


class TurnstileUnavailable(Exception):
    """Cloudflare could not be reached, so the check could not be done."""


def verify_turnstile(secret: str, token: str, remote_ip: str | None = None) -> bool:
    """Ask Cloudflare whether the visitor passed the spam check."""
    data = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip
    try:
        response = httpx.post(VERIFY_URL, data=data, timeout=5.0)
        response.raise_for_status()
        return bool(response.json().get("success"))
    except (httpx.HTTPError, ValueError) as exc:
        raise TurnstileUnavailable from exc
