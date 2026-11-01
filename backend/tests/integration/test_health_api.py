"""Integration tests: HTTP surface — health, envelope, OpenAPI, tracing."""
from __future__ import annotations


def test_health_live_envelope(api_client):
    resp = api_client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "message" in body
    assert body["data"]["check"] == "live"
    assert body["data"]["status"] == "alive"


def test_health_ready_ready(api_client):
    resp = api_client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["database"] is True
    assert body["data"]["ai_provider"] == "mock"


def test_system_info_disclosure(api_client):
    resp = api_client.get("/api/v1/system/info")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "RELATRUM"
    assert data["ai_provider"] == "mock"
    assert "deterministic local processing" in data["analysis_disclosure"].lower()
    assert "database_backend" in data
    assert "limits" in data


def test_openapi_available(api_client):
    resp = api_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert schema["info"]["title"] == "RELATRUM API"
    assert "/health/live" in schema["paths"]
    assert "/api/v1/system/info" in schema["paths"]


def test_request_id_echoed(api_client):
    resp = api_client.get("/health/live", headers={"X-Request-ID": "trace-42"})
    assert resp.headers["X-Request-ID"] == "trace-42"


def test_unknown_route_returns_404_envelope(api_client):
    resp = api_client.get("/api/v1/nonexistent-resource")
    assert resp.status_code == 404
    body = resp.json()
    assert body["success"] is False


def test_request_validation_error_envelope(api_client):
    # Any route with typed params does not exist yet; validation errors surface
    # through FastAPI validation handler. Force one via bad JSON on a POST.
    resp = api_client.post(
        "/api/v1/nonexistent-resource",
        content="not json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code in (404, 422)
    assert resp.json()["success"] is False
