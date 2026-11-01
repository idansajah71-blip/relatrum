"""Finding endpoints: list, detail, evidence, history, status update."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import CurrentUser, require_workspace_member
from app.database import get_db
from app.models.case import Case
from app.models.finding import Finding
from app.models.user import User
from app.schemas.common import ok, page_meta
from app.services import findings as findings_service

router = APIRouter(tags=["findings"])


class FindingStatusPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(draft|pending_review|accepted|rejected|requires_more_evidence|resolved|superseded)$")
    review_notes: str | None = None
    decision: str | None = Field(default=None, pattern="^(accept|reject|insufficient_evidence|request_more_information|needs_reanalysis)$")


def _finding_data(f: Finding) -> dict:
    return {
        "id": f.id,
        "case_id": f.case_id,
        "finding_code": f.finding_code,
        "finding_type": f.finding_type,
        "title": f.title,
        "summary": f.summary,
        "detailed_explanation": f.detailed_explanation,
        "status": f.status,
        "priority": f.priority,
        "priority_factors": f.priority_factors,
        "impact_context": f.impact_context,
        "scope": f.scope,
        "quality_profile": f.quality_profile,
        "first_detected_at": f.first_detected_at.isoformat() if f.first_detected_at else None,
        "last_updated_at": f.last_updated_at.isoformat() if f.last_updated_at else None,
        "created_by_analysis_run": f.created_by_analysis_run,
        "last_confirmed_by_run": f.last_confirmed_by_run,
        "supersedes_finding_id": f.supersedes_finding_id,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "updated_at": f.updated_at.isoformat() if f.updated_at else None,
    }


@router.get("/cases/{case_id}/findings")
def list_findings(
    case_id: str,
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    rows, total = findings_service.list_findings(db, case_id=case.id, limit=limit, offset=offset, status=status)
    return ok(
        [_finding_data(f) for f in rows],
        meta=page_meta(total, min(max(limit, 1), 200), max(offset, 0)),
    )


@router.get("/findings/{finding_id}")
def get_finding(finding_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    f = findings_service.get_finding(db, finding_id)
    case = db.get(Case, f.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    return ok(_finding_data(f))


@router.get("/findings/{finding_id}/evidence")
def get_finding_evidence(finding_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    f = findings_service.get_finding(db, finding_id)
    case = db.get(Case, f.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    return ok(findings_service.get_finding_evidence(db, finding_id))


@router.get("/findings/{finding_id}/history")
def get_finding_history(finding_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    f = findings_service.get_finding(db, finding_id)
    case = db.get(Case, f.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    return ok(findings_service.get_finding_history(db, finding_id))


@router.patch("/findings/{finding_id}/status")
def patch_finding_status(
    finding_id: str,
    payload: FindingStatusPatch,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    f = findings_service.get_finding(db, finding_id)
    case = db.get(Case, f.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="reviewer")
    updated = findings_service.update_finding_status(
        db, finding_id=finding_id, user=user,
        new_status=payload.status, review_notes=payload.review_notes, decision=payload.decision,
    )
    return ok(_finding_data(updated), "Finding status updated.")
