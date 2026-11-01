"""Minimum Resolving Evidence (MRE) generation and verification workflow."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.core.exceptions import NotFoundError, ValidationFailedError
from app.core.permissions import require_workspace_member
from app.database import utcnow
from app.models.case import Case
from app.models.finding import Finding
from app.models.user import User
from app.models.verification import VerificationResponse, VerificationTask
from app.models.finding import Finding
from app.services import audit

TEMPLATES = {
    "possible_requirement_deviation": {
        "question": "For a defined sample of affected applications, what were the submission date, completion date, and document-completeness status at submission?",
        "unresolved_issue": "It is unclear whether processing is routinely delayed or delays concentrate in incomplete submissions.",
        "missing_information": "Per-item submission dates, completion dates, and document-completeness status.",
        "suggested_evidence_type": "operational_record",
        "suggested_source": "Administrative processing records or equivalent official log",
        "expected_answer_structure": {
            "fields": ["application_id", "submission_date", "completion_date", "complete_at_submission", "processing_category"],
        },
        "hypothesis_a": "Processing is routinely delayed across applications.",
        "hypothesis_b": "Delays occur mainly when submissions are incomplete.",
        "decision_relevance": "Timestamps plus completeness status separate systematic delays from case-mix explanations.",
        "limitations": "A single sample may not represent all periods; results are preliminary evidence, not proof.",
    },
    "temporal_divergence": {
        "question": "Which requirement version was in force on the date of each observed event, and what was its effective date?",
        "unresolved_issue": "The observation may relate to an outdated or newer requirement version.",
        "missing_information": "Requirement version identifiers and effective dates for the observation period.",
        "suggested_evidence_type": "policy_version",
        "suggested_source": "Versioned policy or procedure document with effective dates",
        "expected_answer_structure": {"fields": ["requirement_version", "effective_from", "effective_until", "observation_date"]},
        "hypothesis_a": "The observation reflects an older requirement version.",
        "hypothesis_b": "The observation reflects a data or date error.",
        "decision_relevance": "Version resolution determines whether the observation is actually a deviation.",
        "limitations": "Effective dates may be implicit or undocumented.",
    },
    "missing_observation": {
        "question": "Where are the operational records that would show whether this requirement is met in practice?",
        "unresolved_issue": "No observational evidence maps to this requirement.",
        "missing_information": "Operational records, reports, or logs covering the requirement's scope.",
        "suggested_evidence_type": "operational_record",
        "suggested_source": "Operational logs, case files, or monitoring records",
        "expected_answer_structure": {"fields": ["record_id", "date", "outcome", "source"]},
        "hypothesis_a": "The process is unmonitored and no records exist.",
        "hypothesis_b": "Records exist but have not been ingested.",
        "decision_relevance": "Establishes whether the gap is in practice or in evidence.",
        "limitations": "Absence of ingested records is not proof of absence of activity.",
    },
    "unexplained_practice": {
        "question": "Which policy or procedure authorises this observed practice?",
        "unresolved_issue": "An observed practice cannot be mapped to an available requirement.",
        "missing_information": "The authorising policy, procedure, or approval record.",
        "suggested_evidence_type": "policy_document",
        "suggested_source": "Policy or procedure manual, or approval record",
        "expected_answer_structure": {"fields": ["policy_reference", "effective_date", "scope"]},
        "hypothesis_a": "The practice is an undocumented but authorised procedure.",
        "hypothesis_b": "The practice reflects a policy gap or extraction error.",
        "decision_relevance": "Determines whether to update policy or correct the record.",
        "limitations": "Authorisation may be implicit or verbal.",
    },
    "contradictory_reports": {
        "question": "For both reports, what are the case identifiers and dates involved?",
        "unresolved_issue": "Two reports describe incompatible operational conditions.",
        "missing_information": "Case identifiers, timestamps, and contextual conditions for each report.",
        "suggested_evidence_type": "case_record",
        "suggested_source": "Case files or operational logs",
        "expected_answer_structure": {"fields": ["report_id", "case_id", "date", "condition"]},
        "hypothesis_a": "The reports concern different time periods or case mixes.",
        "hypothesis_b": "The reports reflect genuinely inconsistent practice.",
        "decision_relevance": "Distinguishes reporting artefacts from real inconsistency.",
        "limitations": "Records may be incomplete or inconsistently recorded.",
    },
    "repeated_operational_friction": {
        "question": "For a sample of affected cases, what are the submission dates, completion dates, and submission completeness?",
        "unresolved_issue": "Multiple observations suggest a recurring operational difficulty.",
        "missing_information": "Per-case timestamps and completeness status.",
        "suggested_evidence_type": "operational_record",
        "suggested_source": "Processing logs or case files",
        "expected_answer_structure": {"fields": ["case_id", "submission_date", "completion_date", "complete_at_submission"]},
        "hypothesis_a": "A systematic delay affects many cases.",
        "hypothesis_b": "Delays concentrate in specific conditions or periods.",
        "decision_relevance": "Separates systemic from case-mix explanations.",
        "limitations": "Sample may not be representative.",
    },
    "insufficient_evidence": {
        "question": "What additional sources would establish whether this requirement is met in practice?",
        "unresolved_issue": "Available sources cannot support a reliable finding.",
        "missing_information": "Additional reports, records, or policy documents.",
        "suggested_evidence_type": "document",
        "suggested_source": "Additional reports or operational records",
        "expected_answer_structure": {"fields": ["source_type", "description", "date_range"]},
        "hypothesis_a": "Evidence exists but has not been ingested.",
        "hypothesis_b": "No evidence exists because the process is unmonitored.",
        "decision_relevance": "Determines the next evidence to collect.",
        "limitations": "Cannot distinguish absence of evidence from absence of activity.",
    },
}

DEFAULT_TEMPLATE = TEMPLATES["insufficient_evidence"]


def _template_for(finding_type: str) -> dict:
    return TEMPLATES.get(finding_type, DEFAULT_TEMPLATE)


def generate_verification_tasks(
    db: Session, *, finding_id: str, user_id: str, force: bool = False
) -> list[VerificationTask]:
    finding = db.get(Finding, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding {finding_id} not found.")

    existing = db.query(VerificationTask).filter(VerificationTask.finding_id == finding.id).all()
    if existing and not force:
        return existing

    if force:
        for t in existing:
            db.delete(t)
        db.flush()

    # Optional provider refinement
    template = _template_for(finding.finding_type)
    tasks_to_create = [template]

    created: list[VerificationTask] = []
    for tpl in tasks_to_create:
        task = VerificationTask(
            finding_id=finding.id,
            question=tpl["question"],
            unresolved_issue=tpl["unresolved_issue"],
            missing_information=tpl["missing_information"],
            suggested_evidence_type=tpl["suggested_evidence_type"],
            suggested_source=tpl["suggested_source"],
            expected_answer_structure=tpl["expected_answer_structure"],
            hypothesis_a=tpl["hypothesis_a"],
            hypothesis_b=tpl["hypothesis_b"],
            decision_relevance=tpl["decision_relevance"],
            limitations=tpl["limitations"],
            priority=finding.priority,
            status="proposed",
            created_by_run=finding.created_by_analysis_run,
        )
        db.add(task)
        db.flush()
        created.append(task)

    # audit
    from app.models.case import Case

    case = db.get(Case, finding.case_id)
    audit.record_event(
        db,
        workspace_id=case.workspace_id,
        actor_id=user_id,
        entity_type="verification_task",
        entity_id=finding.id,
        action="generated",
        after_state={"count": len(created), "finding_id": finding.id},
    )
    db.commit()
    return created if created else existing


def list_tasks(db: Session, finding_id: str) -> list[VerificationTask]:
    return db.query(VerificationTask).filter(VerificationTask.finding_id == finding_id).order_by(VerificationTask.created_at.asc()).all()


def get_task(db: Session, task_id: str) -> VerificationTask:
    t = db.get(VerificationTask, task_id)
    if t is None:
        raise NotFoundError(f"Verification task {task_id} not found.")
    return t


def update_task(db: Session, *, task_id: str, user: User, payload: dict) -> VerificationTask:
    task = get_task(db, task_id)
    finding = db.get(Finding, task.finding_id)
    case = db.get(Case, finding.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="reviewer")
    if payload.get("status") is not None:
        task.status = payload["status"]
    if payload.get("assigned_to") is not None:
        task.assigned_to = payload["assigned_to"]
    if payload.get("due_at") is not None:
        task.due_at = payload["due_at"]
    if payload.get("priority") is not None:
        task.priority = payload["priority"]
    db.commit()
    return task


def add_response(db: Session, *, task_id: str, user: User, response_text: str, response_source_id: str | None, reviewer_notes: str | None) -> VerificationResponse:
    task = get_task(db, task_id)
    finding = db.get(Finding, task.finding_id)
    case = db.get(Case, finding.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="editor")
    resp = VerificationResponse(
        verification_task_id=task.id,
        response_text=response_text,
        response_source_id=response_source_id,
        reviewer_notes=reviewer_notes,
        submitted_by=user.id,
    )
    db.add(resp)
    db.flush()
    task.status = "evidence_received"
    db.commit()
    return resp


def verification_queue(db: Session, *, case_id: str) -> list[dict]:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    findings = db.query(Finding).filter(Finding.case_id == case.id).all()
    finding_ids = [f.id for f in findings]
    tasks = db.query(VerificationTask).filter(VerificationTask.finding_id.in_(finding_ids)).order_by(VerificationTask.created_at.desc()).all() if finding_ids else []
    finding_map = {f.id: f for f in findings}
    out = []
    for t in tasks:
        f = finding_map.get(t.finding_id)
        out.append({
            "task_id": t.id,
            "finding_id": t.finding_id,
            "finding_title": f.title if f else None,
            "finding_type": f.finding_type if f else None,
            "finding_status": f.status if f else None,
            "question": t.question,
            "status": t.status,
            "priority": t.priority,
            "suggested_evidence_type": t.suggested_evidence_type,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        })
    return out


def task_to_dict(t: VerificationTask) -> dict:
    return {
        "id": t.id,
        "finding_id": t.finding_id,
        "question": t.question,
        "unresolved_issue": t.unresolved_issue,
        "missing_information": t.missing_information,
        "suggested_evidence_type": t.suggested_evidence_type,
        "suggested_source": t.suggested_source,
        "expected_answer_structure": t.expected_answer_structure,
        "hypothesis_a": t.hypothesis_a,
        "hypothesis_b": t.hypothesis_b,
        "decision_relevance": t.decision_relevance,
        "limitations": t.limitations,
        "priority": t.priority,
        "status": t.status,
        "assigned_to": t.assigned_to,
        "due_at": t.due_at,
        "created_by_run": t.created_by_run,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "updated_at": t.updated_at.isoformat() if t.updated_at else None,
        "responses": [
            {
                "id": r.id,
                "response_text": r.response_text,
                "response_source_id": r.response_source_id,
                "reviewer_notes": r.reviewer_notes,
                "submitted_by": r.submitted_by,
                "submitted_at": r.submitted_at.isoformat() if r.submitted_at else None,
            }
            for r in t.responses
        ],
    }
