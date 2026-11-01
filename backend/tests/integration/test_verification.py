"""Integration tests: Minimum Resolving Evidence verification (Phase 7)."""
from __future__ import annotations

import pytest


POLICY = (
    "Certificate Processing Policy v1\n\n"
    "Complete applications must be processed within two working days.\n"
    "Applications must not be stamped as approved before payment is confirmed.\n"
)

REPORT = (
    "My application took ten days for processing.\n"
    "We usually stamp applications in bulk before review.\n"
)


async def _setup(api_client):
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": "ver@example.org", "password": "ver-pass-12345", "display_name": "V"},
    )
    headers = {"Authorization": f"Bearer {reg.json()['data']['token']}"}
    ws = api_client.post("/api/v1/workspaces", json={"name": "Ver WS"}, headers=headers).json()["data"]["id"]
    case = api_client.post(f"/api/v1/workspaces/{ws}/cases", json={"title": "Ver Case"}, headers=headers).json()["data"]["id"]
    s1 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": POLICY, "meta": {"source_type": "policy", "title": "Policy"}}, headers=headers).json()["data"]["id"]
    s2 = api_client.post(f"/api/v1/cases/{case}/sources/text", json={"text": REPORT, "meta": {"source_type": "observation", "title": "Report"}}, headers=headers).json()["data"]["id"]
    api_client.post(f"/api/v1/sources/{s1}/extract", headers=headers)
    api_client.post(f"/api/v1/sources/{s2}/extract", headers=headers)
    api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    finding_id = api_client.get(f"/api/v1/cases/{case}/findings", headers=headers).json()["data"][0]["id"]
    return headers, ws, case, finding_id


@pytest.mark.asyncio
async def test_generate_and_list_verification(api_client, db):
    headers, ws, case, finding_id = await _setup(api_client)
    gen = api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers=headers)
    assert gen.status_code in (200, 201), gen.text
    tasks = gen.json()["data"]
    assert tasks, "should generate at least one task"
    t = tasks[0]
    assert t["question"] and t["unresolved_issue"] and t["missing_information"]
    assert t["hypothesis_a"] and t["hypothesis_b"]
    assert t["expected_answer_structure"]
    assert t["status"] == "proposed"

    listed = api_client.get(f"/api/v1/findings/{finding_id}/verification", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()["data"]) == len(tasks)

    # idempotent: re-generate without force returns existing
    gen2 = api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers=headers)
    assert gen2.status_code in (200, 201)
    assert len(gen2.json()["data"]) == len(tasks)


@pytest.mark.asyncio
async def test_verification_task_patch_and_response(api_client, db):
    headers, ws, case, finding_id = await _setup(api_client)
    task_id = api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers=headers).json()["data"][0]["id"]

    patched = api_client.patch(
        f"/api/v1/verification/{task_id}",
        json={"status": "approved", "priority": "high"},
        headers=headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["data"]["status"] == "approved"
    assert patched.json()["data"]["priority"] == "high"

    resp = api_client.post(
        f"/api/v1/verification/{task_id}/responses",
        json={"response_text": "Sample of 20 applications shows 18 within two days.", "reviewer_notes": "preliminary"},
        headers=headers,
    )
    assert resp.status_code in (200, 201), resp.text
    task = api_client.get(f"/api/v1/findings/{finding_id}/verification", headers=headers).json()["data"][0]
    assert task["status"] == "evidence_received"
    assert len(task["responses"]) == 1
    assert task["responses"][0]["response_text"].startswith("Sample")


@pytest.mark.asyncio
async def test_verification_queue(api_client, db):
    headers, ws, case, finding_id = await _setup(api_client)
    api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers=headers)
    queue = api_client.get(f"/api/v1/cases/{case}/verification-queue", headers=headers)
    assert queue.status_code == 200, queue.text
    rows = queue.json()["data"]
    assert rows and rows[0]["finding_id"] == finding_id
    assert "question" in rows[0] and "status" in rows[0]


@pytest.mark.asyncio
async def test_verification_rbac(api_client, db):
    headers, ws, case, finding_id = await _setup(api_client)
    api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers=headers)
    task_id = api_client.get(f"/api/v1/findings/{finding_id}/verification", headers=headers).json()["data"][0]["id"]

    viewer_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "vw3@example.org", "password": "viewer-pass-123", "display_name": "V"},
    ).json()["data"]["token"]
    api_client.post(f"/api/v1/workspaces/{ws}/members", json={"email": "vw3@example.org", "role": "viewer"}, headers=headers)

    # viewer can read queue and tasks
    assert api_client.get(f"/api/v1/findings/{finding_id}/verification", headers={"Authorization": f"Bearer {viewer_token}"}).status_code == 200
    # viewer cannot generate (editor) 
    forbidden_gen = api_client.post(f"/api/v1/findings/{finding_id}/verification", json={}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert forbidden_gen.status_code == 403
    # viewer cannot patch task
    forbidden_patch = api_client.patch(f"/api/v1/verification/{task_id}", json={"status": "completed"}, headers={"Authorization": f"Bearer {viewer_token}"})
    assert forbidden_patch.status_code == 403

    # non-member hidden
    outsider_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "out3@example.org", "password": "out-pass-12345", "display_name": "O"},
    ).json()["data"]["token"]
    assert api_client.get(f"/api/v1/findings/{finding_id}/verification", headers={"Authorization": f"Bearer {outsider_token}"}).status_code == 404
    assert api_client.get(f"/api/v1/cases/{case}/verification-queue", headers={"Authorization": f"Bearer {outsider_token}"}).status_code == 404
