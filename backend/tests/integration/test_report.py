"""Integration tests: reporting and graph (Phase 8)."""
from __future__ import annotations

import pytest


POLICY = (
    "Certificate Processing Policy v1\n\n"
    "Complete applications must be processed within two working days.\n"
)

REPORT = "My application took ten days for processing.\n"


async def _setup(api_client):
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": "rep@example.org", "password": "rep-pass-12345", "display_name": "R"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['token']}"}
    ws = api_client.post("/api/v1/workspaces", json={"name": "Rep WS"}, headers=headers).json()["data"]["id"]
    case = api_client.post(f"/api/v1/workspaces/{ws}/cases", json={"title": "Rep Case"}, headers=headers).json()["data"]["id"]
    s1 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": POLICY, "meta": {"source_type": "policy", "title": "Policy"}}, headers=headers).json()["data"]["id"]
    s2 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": REPORT, "meta": {"source_type": "observation", "title": "Report"}}, headers=headers).json()["data"]["id"]
    api_client.post(f"/api/v1/sources/{s1}/extract", headers=headers)
    api_client.post(f"/api/v1/sources/{s2}/extract", headers=headers)
    api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    return headers, ws, case


@pytest.mark.asyncio
async def test_report_json_and_markdown(api_client, db):
    headers, ws, case = await _setup(api_client)
    jr = api_client.get(f"/api/v1/cases/{case}/reports?format=json", headers=headers)
    assert jr.status_code == 200, jr.text
    data = jr.json()["data"]
    assert data["overview"]["case_id"] == case
    assert "requirements_summary" in data
    assert "evidence_dossiers" in data
    assert "methodology_and_limitations" in data

    mr = api_client.get(f"/api/v1/cases/{case}/reports?format=markdown", headers=headers)
    assert mr.status_code == 200
    content = mr.json()["data"]["content"]
    assert "RELATRUM Evidence Report" in content
    assert "Methodology and Limitations" in content


@pytest.mark.asyncio
async def test_graph_endpoint(api_client, db):
    headers, ws, case = await _setup(api_client)
    g = api_client.get(f"/api/v1/cases/{case}/graph", headers=headers)
    assert g.status_code == 200, g.text
    data = g.json()["data"]
    assert "nodes" in data and "edges" in data
    assert any(n["type"] == "statement" for n in data["nodes"])
    assert any(n["type"] == "finding" for n in data["nodes"])


@pytest.mark.asyncio
async def test_provider_health(api_client, db):
    r = api_client.get("/api/v1/system/providers")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["provider"] == "mock"
    assert data["mock_available"] is True
    assert data["configured"] is True


@pytest.mark.asyncio
async def test_report_rbac(api_client, db):
    headers, ws, case = await _setup(api_client)
    outsider_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "out4@example.org", "password": "out-pass-12345", "display_name": "O"},
    ).json()["data"]["token"]
    assert api_client.get(f"/api/v1/cases/{case}/reports", headers={"Authorization": f"Bearer {outsider_token}"}).status_code == 404
    assert api_client.get(f"/api/v1/cases/{case}/graph", headers={"Authorization": f"Bearer {outsider_token}"}).status_code == 404
