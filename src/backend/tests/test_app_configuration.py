"""Application startup and browser-access regression tests."""
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_health_endpoint_reports_service_metadata() -> None:
    """Verify the unauthenticated readiness endpoint has the documented shape.

    @returns: None.
    """
    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["version"] == "0.1.0"
    assert body["generated_at"]


def test_cors_allows_the_local_vite_origin_only() -> None:
    """Verify browser preflight permits the local Vite UI without a wildcard.

    @returns: None.
    """
    allowed_origin = "http://127.0.0.1:5173"
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": allowed_origin,
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == allowed_origin
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers
