"""Findings persistence, dossier assembly, and review transitions."""
from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.permissions import require_workspace_member
from app.database import utcnow
from app.domain.enums import EvidencePolarity, FindingPriority, FindingStatus
from app.models.alignment import Alignment
from app.models.analysis_run import AnalysisRun
from app.models.case import Case
from app.models.evidence import EvidenceSpan
from app.models.finding import Finding, FindingEvidence
from app.models.review import Review
from app.models.statement import Statement, StatementEvidence
from app.models.user import User
from app.services import audit
from app.services.divergence.detector import detect_findings

PRIORITY_BY_TYPE = {
    "possible_requirement_deviation": FindingPriority.high.value,
    "contradictory_reports": FindingPriority.high.value,
    "temporal_divergence": FindingPriority.high.value,
    "missing_observation": FindingPriority.medium.value,
    "unexplained_practice": FindingPriority.medium.value,
    "repeated_operational_friction": FindingPriority.medium.value,
    "insufficient_evidence": FindingPriority.low.value,
    "underspecified_requirement": FindingPriority.medium.value,
}

STATUS_DECISION_MAP = {
    FindingStatus.accepted.value: "accept",
    FindingStatus.rejected.value: "reject",
    FindingStatus.requires_more_evidence.value: "request_more_information",
    FindingStatus.resolved.value: "accept",
    FindingStatus.pending_review.value: "needs_reanalysis",
}


def _finding_code(finding_type: str, statement_ids: list[str]) -> str:
    basis = finding_type + "|" + ",".join(sorted(statement_ids))
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12]
    return f"FND-{digest}"


def _quality_profile(db: Session, statements_by_id: dict[str, Statement], candidate, alignments: list) -> dict[str, Any]:
    involved = [statements_by_id[sid] for sid in candidate.involved_statement_ids if sid in statements_by_id]
    confs = [s.extraction_confidence for s in involved if s.extraction_confidence is not None]
    extraction_quality = round(sum(confs) / len(confs), 3) if confs else None

    span_ids: set[str] = set()
    for s in involved:
        links = db.scalars(select(StatementEvidence).where(StatementEvidence.statement_id == s.id)).all()
        for l in links:
            span_ids.add(l.evidence_span_id)
    evidence_coverage = round(len(span_ids) / max(len(involved), 1), 3) if involved else None

    cand_aligns = [a for a in alignments if a.id in set(candidate.involved_alignment_ids)]
    if cand_aligns:
        compatible = sum(1 for a in cand_aligns if a.temporal_compatibility == "compatible")
        temporal_q = round(compatible / len(cand_aligns), 3)
        sims = [a.lexical_similarity for a in cand_aligns if a.lexical_similarity is not None]
        semantic_q = round(sum(sims) / len(sims), 3) if sims else None
    else:
        temporal_q = None
        semantic_q = None

    source_versions = {s.source_version_id for s in involved}
    counter_presence = any(p == "contradicts" for p in (candidate.polarity_map or {}).values())

    return {
        "extraction_quality": extraction_quality,
        "evidence_coverage": evidence_coverage,
        "temporal_alignment_quality": temporal_q,
        "semantic_alignment_quality": semantic_q,
        "source_diversity": len(source_versions),
        "counter_evidence_presence": counter_presence,
        "reviewer_validation_status": None,
    }


def generate_findings(db: Session, *, case_id: str, analysis_run_id: str, user_id: str) -> list[Finding]:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    run = db.get(AnalysisRun, analysis_run_id)
    if run is None or run.case_id != case_id:
        raise NotFoundError(f"Analysis run {analysis_run_id} not found.")

    statements = db.query(Statement).filter(Statement.case_id == case.id).all()
    alignments = db.query(Alignment).filter(Alignment.analysis_run_id == run.id).all()
    statements_by_id = {s.id: s for s in statements}
    has_observations = any(s.statement_type != "requirement" for s in statements)
    superseded_ids = set((run.execution_metadata or {}).get("superseded_requirement_ids", []))

    candidates = detect_findings(
        case_id=case.id,
        statements=statements,
        alignments=alignments,
        superseded_ids=superseded_ids,
        has_observations=has_observations,
    )

    created: list[Finding] = []
    for cand in candidates:
        code = _finding_code(cand.finding_type, cand.involved_statement_ids)
        previous = db.scalar(
            select(Finding).where(Finding.case_id == case.id, Finding.finding_code == code)
            .order_by(Finding.created_at.desc())
        )
        if previous is not None and previous.status != FindingStatus.superseded.value:
            previous.status = FindingStatus.superseded.value
            previous.last_updated_at = utcnow()
            db.flush()

        finding = Finding(
            case_id=case.id,
            finding_code=code,
            finding_type=cand.finding_type,
            title=cand.title,
            summary=cand.summary,
            detailed_explanation=cand.detailed_explanation,
            status=FindingStatus.pending_review.value,
            priority=PRIORITY_BY_TYPE.get(cand.finding_type, FindingPriority.medium.value),
            priority_factors={
                "rule": "finding_type",
                "finding_type": cand.finding_type,
                "involved_statements": len(cand.involved_statement_ids),
                "counter_evidence": any(p == "contradicts" for p in (cand.polarity_map or {}).values()),
            },
            impact_context=None,
            scope=None,
            quality_profile=_quality_profile(db, statements_by_id, cand, alignments),
            first_detected_at=utcnow(),
            last_updated_at=utcnow(),
            created_by_analysis_run=run.id,
            last_confirmed_by_run=run.id,
            supersedes_finding_id=previous.id if previous is not None else None,
        )
        db.add(finding)
        db.flush()

        # link evidence
        for sid in cand.involved_statement_ids:
            stmt = statements_by_id.get(sid)
            if stmt is None:
                continue
            polarity = (cand.polarity_map or {}).get(sid, EvidencePolarity.unresolved.value)
            links = db.scalars(select(StatementEvidence).where(StatementEvidence.statement_id == sid)).all()
            if links:
                for l in links:
                    db.add(FindingEvidence(
                        finding_id=finding.id,
                        evidence_span_id=l.evidence_span_id,
                        statement_id=sid,
                        evidence_polarity=polarity,
                        relevance_explanation=cand.summary,
                        relationship_type=cand.finding_type,
                    ))
            else:
                db.add(FindingEvidence(
                    finding_id=finding.id,
                    evidence_span_id=None,
                    statement_id=sid,
                    evidence_polarity=polarity,
                    relevance_explanation=cand.summary,
                    relationship_type=cand.finding_type,
                ))
        db.flush()
        created.append(finding)

    audit.record_event(
        db,
        workspace_id=case.workspace_id,
        actor_id=user_id,
        entity_type="finding",
        entity_id=run.id,
        action="generated",
        after_state={"count": len(created), "analysis_run_id": run.id},
    )
    db.commit()
    return created


def list_findings(db: Session, *, case_id: str, limit: int = 50, offset: int = 0, status: str | None = None):
    q = db.query(Finding).filter(Finding.case_id == case_id)
    if status:
        q = q.filter(Finding.status == status)
    total = q.count()
    rows = q.order_by(Finding.created_at.desc()).offset(max(offset, 0)).limit(min(max(limit, 1), 200)).all()
    return rows, total


def get_finding(db: Session, finding_id: str) -> Finding:
    f = db.get(Finding, finding_id)
    if f is None:
        raise NotFoundError(f"Finding {finding_id} not found.")
    return f


def get_finding_evidence(db: Session, finding_id: str) -> list[dict]:
    f = get_finding(db, finding_id)
    rows = db.query(FindingEvidence).filter(FindingEvidence.finding_id == f.id).all()
    out = []
    for r in rows:
        span = db.get(EvidenceSpan, r.evidence_span_id) if r.evidence_span_id else None
        stmt = db.get(Statement, r.statement_id) if r.statement_id else None
        out.append({
            "id": r.id,
            "finding_id": r.finding_id,
            "evidence_span_id": r.evidence_span_id,
            "statement_id": r.statement_id,
            "evidence_polarity": r.evidence_polarity,
            "relevance_explanation": r.relevance_explanation,
            "relationship_type": r.relationship_type,
            "statement_text": stmt.original_text if stmt else None,
            "statement_type": stmt.statement_type if stmt else None,
            "exact_quote": span.exact_quote if span else None,
            "source_version_id": span.source_version_id if span else None,
            "start_char": span.start_char if span else None,
            "end_char": span.end_char if span else None,
            "page_number": span.page_number if span else None,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        })
    return out


def get_finding_history(db: Session, finding_id: str) -> dict:
    f = get_finding(db, finding_id)
    reviews = db.query(Review).filter(Review.finding_id == f.id).order_by(Review.created_at.asc()).all()
    # supersession chain
    chain = []
    cur = f
    seen: set[str] = set()
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        chain.append({
            "id": cur.id,
            "finding_code": cur.finding_code,
            "status": cur.status,
            "created_by_analysis_run": cur.created_by_analysis_run,
            "first_detected_at": cur.first_detected_at.isoformat() if cur.first_detected_at else None,
            "supersedes_finding_id": cur.supersedes_finding_id,
        })
        if cur.supersedes_finding_id:
            cur = db.get(Finding, cur.supersedes_finding_id)
        else:
            cur = None
    return {
        "finding_id": f.id,
        "reviews": [
            {
                "id": r.id,
                "reviewer_id": r.reviewer_id,
                "decision": r.decision,
                "review_notes": r.review_notes,
                "decision_rationale": r.decision_rationale,
                "previous_status": r.previous_status,
                "new_status": r.new_status,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in reviews
        ],
        "supersession_chain": chain,
    }


def update_finding_status(db: Session, *, finding_id: str, user: User, new_status: str, review_notes: str | None = None, decision: str | None = None) -> Finding:
    f = get_finding(db, finding_id)
    case = db.get(Case, f.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="reviewer")
    if new_status not in {s.value for s in FindingStatus}:
        raise ValidationFailedError(f"Unknown finding status: {new_status}")
    prev = f.status
    f.status = new_status
    f.last_updated_at = utcnow()
    if decision is None:
        decision = STATUS_DECISION_MAP.get(new_status, "needs_reanalysis")
    review = Review(
        finding_id=f.id,
        reviewer_id=user.id,
        decision=decision,
        review_notes=review_notes,
        decision_rationale=review_notes,
        previous_status=prev,
        new_status=new_status,
    )
    db.add(review)
    audit.record_event(
        db,
        workspace_id=case.workspace_id,
        actor_id=user.id,
        entity_type="finding",
        entity_id=f.id,
        action="status_changed",
        after_state={"from": prev, "to": new_status},
    )
    db.commit()
    return f
