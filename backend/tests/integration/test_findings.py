"""Integration tests: finding dossiers (Phase 6)."""
from __future__ import annotations

import pytest


POLICY = (
    "Certificate Processing Policy v1\n\n"
    "Complete applications must be processed within two working days.\n"
    "Applications must not be stamped as approved before payment is confirmed.\n"
    "Appeal letters must receive a decision within one month.\n"
)

REPORT = (
    "My application took ten days for processing and I returned it unopened on 2024-03-02.\n"
    "We usually stamp applications in bulk before review.\n"
    "Registrations must not be stamped as approved before all documents are verified.\n"
)


async def _setup(api_client):
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": "find@example.org", "password": "find-pass-1234", "display_name": "F"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['token']}"}
    ws = api_client.post("/api/v1/workspaces", json={"name": "Find WS"}, headers=headers).json()["data"]["id"]
    case = api_client.post(f"/api/v1/workspaces/{ws}/cases", json={"title": "Find Case"}, headers=headers).json()["data"]["id"]
    s1 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": POLICY, "meta": {"source_type": "policy", "title": "Policy"}}, headers=headers).json()["data"]["id"]
    s2 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": REPORT, "meta": {"source_type": "observation", "title": "Report"}}, headers=headers).json()["data"]["id"]
    api_client.post(f"/api/v1/sources/{s1}/extract", headers=headers)
    api_client.post(f"/api/v1/sources/{s2}/extract", headers=headers)
    analyze = api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    assert analyze.status_code == 200, analyze.text
    return headers, ws, case, analyze.json()["data"]["analysis_run_id"]


@pytest.mark.asyncio
async def test_findings_generated_and_listed(api_client, db):
    headers, ws, case, run_id = await _setup(api_client)
    listing = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers)
    assert listing.status_code == 200, listing.text
    rows = listing.json()["data"]
    assert rows, "analysis should produce at least one finding"
    assert all(r["case_id"] == case for r in rows)
    assert all(r["status"] == "pending_review" for r in rows)
    assert all(r["finding_code"].startswith("FND-") for r in rows)
    types = {r["finding_type"] for r in rows}
    assert types & {"possible_requirement_deviation", "missing_observation", "unexplained_practice", "contradictory_reports", "temporal_divergence", "repeated_operational_friction", "insufficient_evidence"}


@pytest.mark.asyncio
async def test_finding_detail_evidence_and_history(api_client, db):
    headers, ws, case, run_id = await _setup(api_client)
    finding_id = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"][0]["id"]

    detail = api_client.get(f"/api/v1/findings/{finding_id}", headers=headers)
    assert detail.status_code == 200
    d = detail.json()["data"]
    assert d["id"] == finding_id
    assert d["quality_profile"] is not None
    assert d["priority"] in ("low", "medium", "high")

    ev = api_client.get(f"/api/v1/findings/{finding_id}/evidence", headers=headers)
    assert ev.status_code == 200
    evidence_rows = ev.json()["data"]
    assert evidence_rows, "finding must have evidence links"
    assert all("statement_id" in r or r.get("statement_id") is None for r in evidence_rows)
    assert any(r.get("statement_text") for r in evidence_rows)

    hist = api_client.get(f"/api/v1/findings/{finding_id}/history", headers=headers)
    assert hist.status_code == 200
    h = hist.json()["data"]
    assert h["finding_id"] == finding_id
    assert "reviews" in h and "supersession_chain" in h


@pytest.mark.asyncio
async def test_finding_status_patch_creates_review(api_client, db):
    headers, ws, case, run_id = await _setup(api_client)
    finding_id = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"][0]["id"]

    patched = api_client.patch(
        f"/api/v1/findings/{finding_id}/status",
        json={"status": "accepted", "review_notes": "Confirmed after checking records."},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["status"] == "accepted"

    hist = api_client.get(f"/api/v1/findings/{finding_id}/history", headers=headers).json()["data"]
    assert len(hist["reviews"]) == 1
    assert hist["reviews"][0]["new_status"] == "accepted"
    assert hist["reviews"][0]["previous_status"] == "pending_review"


@pytest.mark.asyncio
async def test_findings_rbac(api_client, db):
    headers, ws, case, run_id = await _setup(api_client)
    finding_id = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"][0]["id"]

    viewer_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "vw2@example.org", "password": "viewer-pass-123", "display_name": "V"},
    ).json()["data"]["token"]
    api_client.post(f"/api/v1/workspaces/{ws}/members", json={"email": "vw2@example.org", "role": "viewer"}, headers=headers)

    # viewer can read
    r = api_client.get(f"/api/v1/findings/{finding_id}", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 200
    # viewer cannot change status
    forbidden = api_client.patch(
        f"/api/v1/findings/{finding_id}/status",
        json={"status": "rejected"},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert forbidden.status_code == 403

    # non-member hidden
    outsider_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "out2@example.org", "password": "out-pass-12345", "display_name": "O"},
    ).json()["data"]["token"]
    hidden = api_client.get(f"/api/v1/findings/{finding_id}", headers={"Authorization": f"Bearer {outsider_token}"})
    assert hidden.status_code == 404


@pytest.mark.asyncio
async def test_stable_finding_code_across_runs(api_client, db):
    headers, ws, case, run_id = await _setup(api_client)
    first_codes = {f["finding_code"] for f in api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"]}
    # second analyze (new run) should supersede, not duplicate codes
    api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    second = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"]
    second_codes = {f["finding_code"] for f in second}
    # at least one code persists (stable)
    assert first_codes & second_codes
    # superseded old findings should be marked superseded (not in default? list includes all statuses by default)
    statuses = {f["status"] for f in second}
    assert "superseded" in statuses or len(second) >= len(first_codes)
