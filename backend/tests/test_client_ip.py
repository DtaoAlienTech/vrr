import pytest
from starlette.requests import Request

from app.core.config import Settings, get_settings
from app.services.enquiries import client_ip


def make_request(forwarded_for: str | None, socket_ip: str = "10.0.0.5") -> Request:
    headers = [(b"x-forwarded-for", forwarded_for.encode())] if forwarded_for is not None else []
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "query_string": b"",
            "scheme": "http",
            "server": ("localhost", 8000),
            "client": (socket_ip, 4000),
            "headers": headers,
        }
    )


def settings_with(hops: int) -> Settings:
    return get_settings().model_copy(update={"trusted_proxy_hops": hops})


def test_header_is_ignored_when_no_proxy_is_trusted() -> None:
    request = make_request("6.6.6.6")
    assert client_ip(request, settings_with(0)) == "10.0.0.5"


def test_one_proxy_uses_the_last_entry() -> None:
    assert client_ip(make_request("203.0.113.7"), settings_with(1)) == "203.0.113.7"


def test_a_faked_leading_address_is_ignored() -> None:
    # The visitor wrote "6.6.6.6"; our proxy appended the real address after it.
    request = make_request("6.6.6.6, 203.0.113.7")
    assert client_ip(request, settings_with(1)) == "203.0.113.7"


def test_two_proxies_use_the_second_entry_from_the_right() -> None:
    request = make_request("6.6.6.6, 203.0.113.7, 172.18.0.3")
    assert client_ip(request, settings_with(2)) == "203.0.113.7"


@pytest.mark.parametrize("header", [None, "", "  "])
def test_missing_header_falls_back_to_the_socket_address(header: str | None) -> None:
    assert client_ip(make_request(header), settings_with(1)) == "10.0.0.5"


def test_header_with_too_few_entries_falls_back_to_the_socket_address() -> None:
    assert client_ip(make_request("203.0.113.7"), settings_with(2)) == "10.0.0.5"
