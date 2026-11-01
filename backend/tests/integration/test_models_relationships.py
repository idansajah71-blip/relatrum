"""Integration tests: 19-table schema, relationships, constraints, FK enforcement."""
from __future__ import annotations

import secrets

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.database import utcnow
from app.models.case import Case
from app.models.evidence import EvidenceSpan
from app.models.source import Source, SourceVersion
from app.models.statement import Statement, StatementEvidence, StatementRelation
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember
from app.models.finding import Finding, FindingEvidence


def test_full_table_registry(db):
    from app.database import Base

    expected = {
        "users", "workspaces", "workspace_members", "cases", "sources",
        "source_versions", "evidence_spans", "statements", "statement_evidence",
        "statement_relations", "alignments", "findings", "finding_evidence",
        "verification_tasks", "verification_responses", "reviews",
        "analysis_runs", "ai_invocations", "audit_events",
    }
    assert set(Base.metadata.tables) == expected


def test_user_membership_workspace_chain(db, user_factory, workspace_factory):
    user = user_factory()
    ws = workspace_factory(user=user, member_role="owner")
    member = db.query(WorkspaceMember).filter_by(workspace_id=ws.id, user_id=user.id).one()
    assert member.role == "owner"
    assert user.memberships[0].workspace.slug.startswith("test-")


def test_membership_unique_constraint(db, user_factory, workspace_factory):
    user = user_factory()
    ws = workspace_factory(user=user)
    db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="editor"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_membership_default_is_least_privilege(db, user_factory, workspace_factory):
    from app.models.workspace import WorkspaceMember

    user = user_factory()
    ws = workspace_factory()  # no explicit member
    m = WorkspaceMember(workspace_id=ws.id, user_id=user.id)
    db.add(m)
    db.commit()
    # Schema default enforces least privilege (viewer), never owner.
    assert m.role == "viewer"


def test_case_belongs_to_workspace(db, workspace_factory):
    ws = workspace_factory()
    case = Case(workspace_id=ws.id, title="T", domain="d")
    db.add(case)
    db.commit()
    assert case.workspace.slug.startswith("test-")


def test_source_version_chain(db, case_factory, source_chain_factory):
    ws = db.query(Workspace).first()
    if ws is None:
        ws = Workspace(name="W", slug="w")
        db.add(ws)
        db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    assert version.source_id == source.id
    assert span.source_version_id == version.id
    assert span.exact_quote in version.extracted_text


def test_span_ordered_check_violation_rejected(db, case_factory, source_chain_factory):
    ws = Workspace(name="W2", slug="w2")
    db.add(ws)
    db.commit()
    case = case_factory(ws)
    source, version, _ = source_chain_factory(case)
    bad = EvidenceSpan(
        source_version_id=version.id,
        start_char=10,
        end_char=5,
        exact_quote="reversed",
    )
    db.add(bad)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_statement_with_evidence_and_relation(db, case_factory, source_chain_factory):
    ws = Workspace(name="W3", slug="w3")
    db.add(ws)
    db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)

    s1 = Statement(
        case_id=case.id,
        source_version_id=version.id,
        statement_type="requirement",
        original_text="Applications must be processed within two working days.",
        modality="mandatory",
    )
    s2 = Statement(
        case_id=case.id,
        source_version_id=version.id,
        statement_type="observation",
        original_text="My application took four days in February.",
        observed_at="2026-02-24",
    )
    db.add_all([s1, s2])
    db.flush()

    link = StatementEvidence(statement_id=s1.id, evidence_span_id=span.id, evidence_role="direct_support")
    db.add(link)
    rel = StatementRelation(
        source_statement_id=s2.id,
        target_statement_id=s1.id,
        relation_type="contradicts",
        relationship_explanation="Reported processing time exceeds documented standard.",
    )
    db.add(rel)
    db.commit()

    assert s1.evidence_links[0].evidence_span.exact_quote == span.exact_quote
    assert s2.evidence_links == []


def test_evidence_span_with_statement_relation(db, case_factory, source_chain_factory):
    ws = Workspace(name="W3", slug="w3")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    stmt = Statement(
        case_id=case.id,
        source_version_id=version.id,
        statement_type="requirement",
        original_text=span.exact_quote,
    )
    db.add(stmt); db.flush()
    db.add(StatementEvidence(statement_id=stmt.id, evidence_span_id=span.id))
    db.commit()
    assert stmt.evidence_links[0].statement_id == stmt.id


def test_sqlalchemy_statement_relation_cascade(db, case_factory, source_chain_factory):
    ws = Workspace(name="W3", slug="w3")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    stmt = Statement(
        case_id=case.id, source_version_id=version.id,
        statement_type="requirement", original_text="x",
    )
    db.add(stmt); db.flush()
    db.add(StatementEvidence(statement_id=stmt.id, evidence_span_id=span.id))
    db.commit()
    db.delete(stmt)
    db.commit()
    assert db.query(StatementEvidence).count() == 0


def test_finding_requires_at_least_one_reference(db, case_factory, source_chain_factory):
    ws = Workspace(name="W4", slug="w4")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    finding = Finding(
        case_id=case.id,
        finding_code="F-TEST-001",
        finding_type="possible_requirement_deviation",
        title="Possible processing delay",
        status="draft",
    )
    db.add(finding)
    db.flush()
    # No span and no statement -> violates CHECK
    db.add(FindingEvidence(finding_id=finding.id, evidence_polarity="supports"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_finding_with_statement_reference_ok(db, case_factory, source_chain_factory):
    ws = Workspace(name="W5", slug="w5")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    stmt = Statement(
        case_id=case.id,
        source_version_id=version.id,
        statement_type="observation",
        original_text="Report: took four days.",
        observed_at="2025-02-24",
    )
    db.add(stmt)
    db.commit()
    finding = Finding(
        case_id=case.id,
        finding_code="F-TEST-002",
        finding_type="possible_requirement_deviation",
        title="Possible processing delay",
        status="draft",
    )
    db.add(finding)
    db.flush()
    db.add(FindingEvidence(finding_id=finding.id, statement_id=stmt.id, evidence_polarity="supports"))
    db.commit()
    assert len(finding.evidence) == 1


def test_creating_statement_with_invalid_case_rejected(db):
    fake_case_id = secrets.token_hex(16)
    stmt = Statement(
        case_id=fake_case_id,
        source_version_id=secrets.token_hex(16),
        statement_type="requirement",
        original_text="x",
    )
    db.add(stmt)
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_analysis_run_and_ai_invocation_chain(db, case_factory):
    from app.models.analysis_run import AnalysisRun, AiInvocation

    ws = Workspace(name="W6", slug="w6")
    db.add(ws); db.commit()
    case = case_factory(ws)
    run = AnalysisRun(
        case_id=case.id,
        status="completed",
        pipeline_version="1.0.0",
        prompt_version="1.0.0",
        provider_name="mock",
        model_name="deterministic",
    )
    db.add(run)
    db.flush()
    inv = AiInvocation(
        analysis_run_id=run.id,
        provider="mock",
        model="deterministic",
        operation_type="extract_statements",
        prompt_version="1.0.0",
        request_status="success",
        input_token_count=0,
        output_token_count=0,
    )
    db.add(inv)
    db.commit()
    assert run.invocations[0].operation_type == "extract_statements"


def test_review_is_expressible_and_reversible(db, case_factory, source_chain_factory, user_factory):
    from app.models.review import Review
    from app.models.verification import VerificationTask, VerificationResponse

    user = user_factory()
    ws = Workspace(name="W7", slug="w7")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    finding = Finding(
        case_id=case.id,
        finding_code="F-TEST-003",
        finding_type="missing_observation",
        title="Insufficient observation evidence",
    )
    db.add(finding)
    db.flush()
    review = Review(
        finding_id=finding.id,
        reviewer_id=user.id,
        decision="accept",
        previous_status="pending_review",
        new_status="accepted",
    )
    db.add(review)
    task = VerificationTask(
        finding_id=finding.id,
        question="Provide timestamps for sample applications.",
        suggested_evidence_type="operational_record",
        hypothesis_a="Processing routinely delayed.",
        hypothesis_b="Delays were volume-related.",
        status="proposed",
    )
    db.add(task)
    db.commit()
    resp = VerificationResponse(
        verification_task_id=task.id,
        response_text="Sample: 12 apps, submission/completion timestamps attached.",
        response_source_id=source.id,
        submitted_by=user.id,
    )
    db.add(resp)
    db.commit()
    assert finding.reviews[0].decision == "accept"
    assert finding.verification_tasks[0].responses[0].submitted_by == user.id


def test_timestamps_are_utc_aware(db, case_factory, source_chain_factory):
    ws = Workspace(name="W8", slug="w8")
    db.add(ws); db.commit()
    case = case_factory(ws)
    source, version, span = source_chain_factory(case)
    stmt = Statement(
        case_id=case.id,
        source_version_id=version.id,
        statement_type="requirement",
        original_text="x",
    )
    db.add(stmt)
    db.commit()
    assert stmt.created_at.tzinfo is not None
    assert stmt.created_at.utcoffset().total_seconds() == 0
