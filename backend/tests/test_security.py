from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app


def test_security_headers_are_present(client: TestClient) -> None:
    headers = client.get("/api/v1/health").headers
    assert headers["x-content-type-options"] == "nosniff"
    assert headers["x-frame-options"] == "DENY"
    assert headers["referrer-policy"] == "no-referrer"
    assert headers["cache-control"] == "no-store"


def test_unknown_host_is_rejected(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Host": "evil.example"})
    assert response.status_code == 400


def test_docs_available_in_dev(client: TestClient) -> None:
    assert client.get("/api/docs").status_code == 200


def test_docs_disabled_in_production(monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("ENV", "prod")
    get_settings.cache_clear()
    try:
        with TestClient(create_app(), base_url="http://localhost") as prod_client:
            assert prod_client.get("/api/docs").status_code == 404
            assert prod_client.get("/api/openapi.json").status_code == 404
    finally:
        get_settings.cache_clear()
