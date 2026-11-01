"""Integration tests: alignment engine (Phase 5).

Covers: deterministic classification rules for all decision types, retrieval,
supersession relations, case-level absence categories (missing_observation,
unexplained_practice), manifest-hash reproducibility, and the analyze /
alignments / run API flow incl. RBAC (404 hidden for non-members).
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.services.alignment import Candidate, classify_candidate, retrieve_candidates
from app.services.orchestration.analysis_service import run_alignment_analysis
from app.services.temporal.reasoning import supersession_pairs


def _stmt(
    sid: str,
    text: str,
    *,
    statement_type: str = "requirement",
    valid_from: str | None = None,
    valid_until: str | None = None,
    observed_at: str | None = None,
    reported_at: str | None = None,
    subject: str | None = None,
    case_id: str = "case-x",
):
    return SimpleNamespace(
        id=sid,
        case_id=case_id,
        statement_type=statement_type,
        original_text=text,
        normalized_text=text,
        temporal_valid_from=valid_from,
        temporal_valid_until=valid_until,
        observed_at=observed_at,
        reported_at=reported_at,
        subject=subject,
        modality="mandatory" if statement_type == "requirement" else "unknown",
    )


def _pair(req, obs, combined: float):
    return Candidate(
        requirement=req, observation=obs,
        lexical_similarity=round(combined - 0.05, 4),
        fuzzy_similarity=round(combined - 0.02, 4),
        combined_similarity=combined,
    )


# -------------------------------------------------------------- classification


def test_full_match_candidate_rule():
    req = _stmt("r1", "Applications must be processed within two working days.")
    obs = _stmt("o1", "Applications were processed within two working days.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.92))
    assert d.alignment_type == "full_match_candidate"
    assert "0.92" in d.explanation


def test_partial_match_candidate_rule():
    req = _stmt("r1", "Fees must be submitted together with the application form.")
    obs = _stmt("o1", "Fees were submitted with the form only after the deadline passed.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.55))
    assert d.alignment_type == "partial_match_candidate"


def test_duration_breach_is_possible_contradiction():
    req = _stmt("r1", "Applications must be completed within two working days of arrival.")
    obs = _stmt("o1", "Applications took ten working days after arrival.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.85))
    assert d.alignment_type == "possible_contradiction"
    assert "duration" in d.explanation.lower()
    assert d.temporal_detail["duration_observed_days"] == 10.0


def test_negation_conflict_is_possible_contradiction():
    req = _stmt("r1", "Registrations must not be stamped as approved before all documents are verified.")
    obs = _stmt("o1", "Registrations were stamped as approved before all documents.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.72))
    assert d.alignment_type == "possible_contradiction"


def test_temporal_window_miss_is_mismatch():
    req = _stmt(
        "r1", "Renewal notifications must be issued during the defined circular window.",
        valid_from="2023-01-01", valid_until="2023-12-31",
    )
    obs = _stmt(
        "o1", "Renewal notifications were issued during the defined circular window.",
        statement_type="observation", observed_at="2024-06-15", reported_at="2024-06-15",
    )
    d = classify_candidate(_pair(req, obs, 0.88))
    assert d.alignment_type == "temporal_mismatch"
    assert d.temporal_compatibility == "incompatible"


def test_thin_statements_are_insufficient_information():
    req = _stmt("r1", "Fees apply.")
    obs = _stmt("o1", "Fees applied.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.20))
    assert d.alignment_type == "insufficient_information"


def test_weak_shared_topic_is_uncertain():
    req = _stmt("r1", "Certificates must be stamped within three days.")
    obs = _stmt("o1", "Certificates are sometimes stamped late without a clear reason.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.25))
    assert d.alignment_type == "uncertain"


def test_weak_but_contentful_is_unrelated():
    req = _stmt("r1", "Scholarship committees must publish the accepted candidate ranking list each quarter.")
    obs = _stmt("o1", "The bakery once sold out of baguettes during the winter harvest festival.", statement_type="observation")
    d = classify_candidate(_pair(req, obs, 0.12))
    assert d.alignment_type == "unrelated"


def test_identical_texts_score_high():
    """Retrieval sanity: near-duplicate sentences must land far above PARTIAL."""
    req = _stmt("r1", "Applications must be processed within two working days of receipt.")
    obs = _stmt("o1", "Applications were processed within two working days of receipt.", statement_type="observation")
    cands = retrieve_candidates([req], [obs])
    assert cands and cands[0].combined_similarity >= 0.4


# ------------------------------------------------------------------ retrieval


def test_retrieval_finds_relevant_but_noise_is_classified_harmlessly():
    req = _stmt("r1", "Applications must be processed within two working days.")
    obs = _stmt("o1", "The application took five days for processing.", statement_type="observation")
    noise = _stmt("o2", "A bakery once sold out of baguettes during the winter festival.", statement_type="observation")
    candidates = retrieve_candidates([req], [obs, noise])
    pair_ids = {(c.requirement.id, c.observation.id) for c in candidates}
    assert ("r1", "o1") in pair_ids
    # The retrieval floor is deliberately low: noise may enter, but the engine
    # must rule it out as unrelated rather than fabricate alignment.
    noise_candidate = next(c for c in candidates if c.observation.id == "o2")
    decision = classify_candidate(noise_candidate)
    assert decision.alignment_type == "unrelated"
    assert all(c.combined_similarity > 0 for c in candidates)


def test_retrieval_empty_sides():
    assert retrieve_candidates([], []) == []


# --------------------------------------------------------------- supersession


def test_supersession_pairs_detected():
    older = _stmt("a", "Certificates must be stamped within three days.",
                  valid_from="2023-01-01", valid_until="2023-06-30", subject="certificates")
    newer = _stmt("b", "Certificates must be stamped within five days.",
                  valid_from="2023-07-01", valid_until="2024-06-30", subject="certificates")
    fines = _stmt("c", "Bakery fines must be paid within one week.",
                  valid_from="2020-01-01", valid_until="2020-12-31", subject="fines")
    pairs = supersession_pairs([older, newer, fines])
    assert [(p[0], p[1]) for p in pairs] == [(0, 1)]


# ----------------------------------------------------------- service over db


async def _seed_case(db, workspace_factory, case_factory, user, requirements, counterparts):
    from app.models.evidence import EvidenceSpan
    from app.models.source import Source, SourceVersion
    from app.models.statement import Statement, StatementEvidence

    ws = workspace_factory(user)
    case = case_factory(ws)
    source = Source(
        workspace_id=ws.id, case_id=case.id, source_type="policy",
        title="t", source_origin="official_document", ingestion_status="extracted",
    )
    db.add(source)
    db.flush()
    version = SourceVersion(
        source_id=source.id, version_number=1,
        content_sha256="seed" * 8, extracted_text="seed text",
        extraction_method="native_text", extraction_status="success",
    )
    db.add(version)
    db.flush()
    span = EvidenceSpan(source_version_id=version.id, start_char=0, end_char=9, exact_quote="seed text")
    db.add(span)
    db.flush()

    def persist(spec):
        stmt = Statement(
            case_id=case.id, source_version_id=version.id, statement_type=spec.statement_type,
            original_text=spec.original_text, normalized_text=spec.normalized_text,
            temporal_valid_from=spec.temporal_valid_from, temporal_valid_until=spec.temporal_valid_until,
            observed_at=spec.observed_at, reported_at=spec.reported_at,
            review_status="confirmed",
        )
        db.add(stmt)
        db.flush()
        db.add(StatementEvidence(
            statement_id=stmt.id, evidence_span_id=span.id, evidence_role="direct_support"
        ))
        db.flush()
        return stmt

    created = [persist(s) for s in requirements] + [persist(s) for s in counterparts]
    db.commit()
    return ws, case, created


@pytest.mark.asyncio
async def test_analysis_service_classifies_and_reports(db, workspace_factory, case_factory, user_factory):
    user = user_factory()
    req_hit = _stmt("x1", "Applications must be processed within two working days.")
    obs_hit = _stmt("x2", "The application took five days for processing.", statement_type="observation")
    req_missing = _stmt("x3", "Appeal letters must receive a decision within one month.")
    req_superseded = _stmt("x5", "Certificates must be stamped within one day.",
                           valid_from="2022-01-01", valid_until="2022-06-30", subject="certificates")
    req_newer = _stmt("x4", "Certificates must be stamped within three days.",
                      valid_from="2023-01-01", valid_until="2023-06-30", subject="certificates")

    _ws, case, created = await _seed_case(
        db, workspace_factory, case_factory, user,
        requirements=[req_hit, req_missing, req_superseded, req_newer],
        counterparts=[obs_hit],
    )
    req_hit_db, req_missing_db, req_superseded_db, req_newer_db = created[:4]
    report = await run_alignment_analysis(db, case.id, user.id)

    assert report.status == "completed"
    assert report.type_counts.get("possible_contradiction", 0) >= 1
    assert report.type_counts.get("unrelated", 0) >= 1
    assert req_hit_db.id not in report.missing_observation_ids
    assert req_missing_db.id in report.missing_observation_ids
    assert report.superseded_requirement_ids == [req_superseded_db.id]
    assert report.persisted_alignments == report.candidates_evaluated

    from app.models.alignment import Alignment
    from app.models.statement import StatementRelation

    rows = db.scalars(select(Alignment).where(Alignment.analysis_run_id == report.analysis_run_id)).all()
    assert len(rows) == report.persisted_alignments > 0
    assert all(a.case_id == case.id for a in rows)
    assert all(r.analysis_run_id == report.analysis_run_id for r in rows)

    rel = db.scalars(
        select(StatementRelation).where(StatementRelation.created_by_analysis_run == report.analysis_run_id)
    ).all()
    assert len(rel) == 1
    assert rel[0].relation_type == "supersedes"
    assert rel[0].source_statement_id == req_newer_db.id   # newer statement does the superseding
    assert rel[0].target_statement_id == req_superseded_db.id


@pytest.mark.asyncio
async def test_unexplained_practice_detected(db, workspace_factory, case_factory, user_factory):
    user = user_factory()
    req = _stmt("p-req", "Applications must be processed within two working days.")
    practice = _stmt("p-practice", "We usually stamp applications in bulk before review.",
                     statement_type="operational_practice")
    _ws, case, created = await _seed_case(
        db, workspace_factory, case_factory, user, requirements=[req], counterparts=[practice],
    )
    practice_db = created[1]
    report = await run_alignment_analysis(db, case.id, user.id)
    assert practice_db.id in report.unexplained_practice_ids


@pytest.mark.asyncio
async def test_deterministic_reproducibility(db, workspace_factory, case_factory, user_factory):
    user = user_factory()
    req = _stmt("d1", "Applications must be processed within two working days.")
    obs = _stmt("d2", "The application took five days for processing.", statement_type="observation")
    _ws, case, created = await _seed_case(
        db, workspace_factory, case_factory, user, requirements=[req], counterparts=[obs],
    )
    r1 = await run_alignment_analysis(db, case.id, user.id)
    r2 = await run_alignment_analysis(db, case.id, user.id)
    assert r1.type_counts == r2.type_counts
    assert r1.manifest_hash == r2.manifest_hash
    assert r1.missing_observation_ids == r2.missing_observation_ids
    assert r1.candidates_evaluated == r2.candidates_evaluated
    assert r1.candidates_evaluated > 0
    assert r1.persisted_alignments == r2.persisted_alignments > 0

    from app.models.alignment import Alignment

    sig1 = sorted(
        (a.requirement_statement_id, a.observation_statement_id, a.alignment_type)
        for a in db.scalars(select(Alignment).where(Alignment.analysis_run_id == r1.analysis_run_id)).all()
    )
    sig2 = sorted(
        (a.requirement_statement_id, a.observation_statement_id, a.alignment_type)
        for a in db.scalars(select(Alignment).where(Alignment.analysis_run_id == r2.analysis_run_id)).all()
    )
    assert sig1 == sig2


@pytest.mark.asyncio
async def test_requires_requirement_statements(db, workspace_factory, case_factory, user_factory):
    user = user_factory()
    obs = _stmt("z1", "Buses ran late throughout the strike months.", statement_type="observation")
    _ws, case, created = await _seed_case(
        db, workspace_factory, case_factory, user, requirements=[], counterparts=[obs],
    )
    from app.core.exceptions import ValidationFailedError

    with pytest.raises(ValidationFailedError):
        await run_alignment_analysis(db, case.id, user.id)


# ----------------------------------------------------------------- API flow


@pytest.mark.asyncio
async def test_api_alignment_flow_and_rbac(api_client, db):
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": "align@example.org", "password": "align-pass-123", "display_name": "A"},
    )
    assert register.status_code in (200, 201), register.text
    headers = {"Authorization": f"Bearer {register.json()['data']['token']}"}
    ws = api_client.post("/api/v1/workspaces", json={"name": "Align WS"}, headers=headers).json()["data"]["id"]
    case = api_client.post(
        f"/api/v1/workspaces/{ws}/cases", json={"title": "Align Case"}, headers=headers
    ).json()["data"]["id"]

    no_requirements = api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    assert no_requirements.status_code in (400, 422), no_requirements.text

    policy = (
        "Certificate Processing Policy v1\n\n"
        "Complete applications must be processed within two working days.\n"
        "Applications must not be stamped as approved before payment is confirmed.\n"
        "Appeal letters must receive a decision within one month.\n"
    )
    report_text = (
        "My application took ten days for processing and I returned it unopened on 2024-03-02.\n"
        "We usually stamp applications in bulk before review.\n"
    )
    upload_1 = api_client.post(
        f"/api/v1/cases/{case}/sources/text",
        json={"text": policy, "meta": {"source_type": "policy", "title": "Policy v1"}},
        headers=headers,
    )
    assert upload_1.status_code == 201, upload_1.text
    source_1 = upload_1.json()["data"]["id"]
    upload_2 = api_client.post(
        f"/api/v1/cases/{case}/sources/text",
        json={"text": report_text, "meta": {"source_type": "observation", "title": "Field notes"}},
        headers=headers,
    )
    assert upload_2.status_code == 201, upload_2.text
    source_2 = upload_2.json()["data"]["id"]

    extract_1 = api_client.post(f"/api/v1/sources/{source_1}/extract", headers=headers)
    assert extract_1.status_code == 200, extract_1.text
    extract_2 = api_client.post(f"/api/v1/sources/{source_2}/extract", headers=headers)
    assert extract_2.status_code == 200, extract_2.text

    analyze = api_client.post(f"/api/v1/cases/{case}/analyze", json={}, headers=headers)
    assert analyze.status_code == 200, analyze.text
    data = analyze.json()["data"]
    run_id = data["analysis_run_id"]
    assert data["provider"] == "mock"
    assert isinstance(data["alignment_type_counts"], dict)
    assert "missing_observation_ids" in data and "unexplained_practice_ids" in data
    assert data["input_manifest_hash"]

    listing = api_client.get(f"/api/v1/cases/{case}/alignments", headers=headers)
    assert listing.status_code == 200, listing.text
    body = listing.json()
    assert body["success"] is True
    rows = body["data"]
    assert rows and all(r["analysis_run_id"] == run_id for r in rows)
    assert all({"alignment_type", "lexical_similarity", "explanation", "temporal_compatibility"} <= set(r) for r in rows)

    run_detail = api_client.get(f"/api/v1/analysis-runs/{run_id}", headers=headers)
    assert run_detail.status_code == 200, run_detail.text
    rd = run_detail.json()["data"]
    assert rd["id"] == run_id
    assert rd["alignment_type_counts"]
    assert rd["execution_metadata"].get("missing_observation_ids") is not None
    assert rd["input_manifest_hash"] == data["input_manifest_hash"]

    # viewer cannot analyze but may read alignments
    viewer_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "viewer@example.org", "password": "viewer-pass-123", "display_name": "V"},
    ).json()["data"]["token"]
    api_client.post(
        f"/api/v1/workspaces/{ws}/members",
        json={"email": "viewer@example.org", "role": "viewer"},
        headers=headers,
    )
    forbidden_analyze = api_client.post(
        f"/api/v1/cases/{case}/analyze", json={}, headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert forbidden_analyze.status_code == 403, forbidden_analyze.text
    readable = api_client.get(
        f"/api/v1/cases/{case}/alignments", headers={"Authorization": f"Bearer {viewer_token}"}
    )
    assert readable.status_code == 200

    # non-member: existence is hidden
    outsider_token = api_client.post(
        "/api/v1/auth/register",
        json={"email": "outsider@example.org", "password": "out-pass-12345", "display_name": "O"},
    ).json()["data"]["token"]
    hidden_list = api_client.get(
        f"/api/v1/cases/{case}/alignments", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert hidden_list.status_code == 404
    hidden_run = api_client.get(
        f"/api/v1/analysis-runs/{run_id}", headers={"Authorization": f"Bearer {outsider_token}"}
    )
    assert hidden_run.status_code == 404
