"""Integration tests: end-to-end vertical slice.

register -> create workspace -> create case -> upload source files -> prove
versions + evidence spans + duplicate detection + authorization enforcement.
"""
from __future__ import annotations

import pytest


@pytest.fixture()
def auth_headers(api_client):
    resp = api_client.post(
        "/api/v1/auth/register",
        json={"email": "e2e@example.org", "password": "correct-horse-99", "display_name": "E2E Tester"},
    )
    assert resp.status_code == 201, resp.text
    return {"Authorization": f"Bearer {resp.json()['data']['token']}"}


@pytest.fixture()
def workspace_id(api_client, auth_headers):
    resp = api_client.post(
        "/api/v1/workspaces",
        json={"name": "E2E Investigation Team", "description": "Synthetic workspace"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


@pytest.fixture()
def case_id(api_client, auth_headers, workspace_id):
    resp = api_client.post(
        f"/api/v1/workspaces/{workspace_id}/cases",
        json={
            "title": "Certificate processing investigation",
            "domain": "administrative_process",
            "observation_start": "2025-01-01",
            "observation_end": "2025-03-31",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]["id"]


# ---------------------------------------------------------------- happy paths


def test_register_login_roundtrip(api_client):
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.org", "password": "correct-horse-9", "display_name": "New User"},
    )
    assert reg.status_code == 201, reg.text
    body = reg.json()["data"]
    assert body["token"]
    assert body["user"]["is_active"] is True

    dup = api_client.post(
        "/api/v1/auth/register",
        json={"email": "new@example.org", "password": "another-pass-1", "display_name": "Dup"},
    )
    assert dup.status_code == 409

    login = api_client.post(
        "/api/v1/auth/login", json={"email": "new@example.org", "password": "correct-horse-9"}
    )
    assert login.status_code == 200
    assert login.json()["data"]["token"]


def test_workspace_create_and_list(api_client, auth_headers, workspace_id):
    listing = api_client.get("/api/v1/workspaces", headers=auth_headers)
    assert listing.status_code == 200
    data = listing.json()["data"]
    assert any(row["id"] == workspace_id and row["role"] == "owner" for row in data)


def test_case_crud_flow(api_client, auth_headers, workspace_id, case_id):
    detail = api_client.get(f"/api/v1/cases/{case_id}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["title"] == "Certificate processing investigation"
    assert detail.json()["data"]["status"] == "open"

    patched = api_client.patch(
        f"/api/v1/cases/{case_id}",
        json={"status": "in_progress", "scope_definition": "Administrative certificate processing"},
        headers=auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["status"] == "in_progress"

    listing = api_client.get(f"/api/v1/workspaces/{workspace_id}/cases", headers=auth_headers)
    assert listing.status_code == 200
    assert len(listing.json()["data"]) == 1


def test_txt_upload_produces_versions_and_spans(api_client, auth_headers, case_id):
    policy_text = (
        "Certificate Processing Policy v1\n\n"
        "Complete applications should be processed within two working days.\n\n"
        "Applications missing required documents will not be counted as valid submissions.\n"
    )
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("policy_v1.txt", policy_text.encode("utf-8"), "text/plain")},
        data={"source_type": "policy", "title": "Certificate Policy v1", "source_origin": "official_document"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["ingestion_status"] == "extracted"
    assert data["source_type"] == "policy"
    assert data["version_count"] == 1
    assert data["span_count"] == 3

    # versions endpoint
    versions = api_client.get(f"/api/v1/sources/{data['id']}/versions", headers=auth_headers)
    assert versions.status_code == 200
    versions_body = versions.json()["data"]
    assert len(versions_body) == 1
    assert versions_body[0]["extraction_method"] == "native_text:txt"

    # text endpoint returns exact extracted text
    detail = api_client.get(f"/api/v1/sources/{data['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["data"]["text"].startswith("Certificate Processing Policy v1")


def test_csv_upload_produces_row_spans(api_client, auth_headers, case_id):
    csv_content = "application_id,submitted,completed,complete_at_submission\nA-1,2025-02-20,2025-02-24,yes\nA-2,2025-02-25,2025-02-26,yes\n"
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("records.csv", csv_content.encode("utf-8"), "text/csv")},
        data={"source_type": "operational_record", "source_origin": "internal_record"},
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["ingestion_status"] == "extracted"
    assert data["span_count"] == 2


def test_duplicate_txt_upload_rejected(api_client, auth_headers, case_id):
    content = b"Duplicate me\n\nSecond paragraph\n"
    first = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("dup.txt", content, "text/plain")},
        headers=auth_headers,
    )
    assert first.status_code == 201
    second = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("dup_again.txt", content, "text/plain")},
        headers=auth_headers,
    )
    assert second.status_code == 409
    assert second.json()["error_code"] == "conflict"


def test_manual_text_report(api_client, auth_headers, case_id):
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources/text",
        json={
            "text": "Report: My application took four days to complete in February.",
            "meta": {"source_type": "observation", "source_origin": "first_hand_report", "source_date": "2025-02-24"},
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["source_type"] == "observation"
    assert data["ingestion_status"] == "extracted"


# ------------------------------------------------------------------ rejections


def test_bad_extension_rejected(api_client, auth_headers, case_id):
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("evil.exe", b"MZ\x90\x00", "application/octet-stream")},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert resp.json()["success"] is False


def test_fake_pdf_rejected(api_client, auth_headers, case_id):
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "magic bytes" in resp.json()["message"]


def test_oversized_upload_rejected(api_client, auth_headers, case_id):
    from app.config import get_settings

    get_settings.cache_clear()
    too_big = b"A" * (11 * 1024 * 1024)  # default MAX_UPLOAD_MB=10
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("big.txt", too_big, "text/plain")},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_upload_requires_auth(api_client, case_id):
    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("x.txt", b"hello\n", "text/plain")},
    )
    assert resp.status_code == 401


def test_outsider_cannot_see_case(api_client, auth_headers, workspace_id, case_id):
    outsider = api_client.post(
        "/api/v1/auth/register",
        json={"email": "outsider@example.org", "password": "outsider-pass-1", "display_name": "Out"},
    )
    assert outsider.status_code == 201
    outsider_headers = {"Authorization": f"Bearer {outsider.json()['data']['token']}"}

    detail = api_client.get(f"/api/v1/cases/{case_id}", headers=outsider_headers)
    assert detail.status_code == 404

    listing = api_client.get(f"/api/v1/workspaces/{workspace_id}/cases", headers=outsider_headers)
    assert listing.status_code == 404


def test_viewer_cannot_upload(api_client, auth_headers, workspace_id, case_id, db):
    from app.models.workspace import WorkspaceMember

    viewer = api_client.post(
        "/api/v1/auth/register",
        json={"email": "viewer@example.org", "password": "viewer-pass-99", "display_name": "Viewer"},
    )
    viewer_token = viewer.json()["data"]["token"]
    # add as viewer via owner membership endpoint
    add = api_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "viewer@example.org", "role": "viewer"},
        headers=auth_headers,
    )
    assert add.status_code == 201, add.text

    resp = api_client.post(
        f"/api/v1/cases/{case_id}/sources",
        files={"file": ("v.txt", b"viewer upload\n", "text/plain")},
        headers={"Authorization": f"Bearer {viewer_token}"},
    )
    assert resp.status_code == 403


def test_member_add_endpoint(api_client, auth_headers, workspace_id):
    resp = api_client.post(
        f"/api/v1/workspaces/{workspace_id}/members",
        json={"email": "future-member@example.org", "role": "reviewer"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["role"] == "reviewer"
    members = api_client.get(f"/api/v1/workspaces/{workspace_id}/members", headers=auth_headers)
    emails = {m["user_email"] for m in members.json()["data"]}
    assert "future-member@example.org" in emails
