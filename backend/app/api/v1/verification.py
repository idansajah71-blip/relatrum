"""Verification (MRE) endpoints."""
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
from app.services import verification as verification_service

router = APIRouter(tags=["verification"])


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    force: bool = False


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str | None = Field(default=None, pattern="^(proposed|approved|in_progress|evidence_received|completed|dismissed)$")
    assigned_to: str | None = None
    due_at: str | None = None
    priority: str | None = Field(default=None, pattern="^(low|medium|high)$")


class ResponseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response_text: str
    response_source_id: str | None = None
    reviewer_notes: str | None = None


@router.get("/findings/{finding_id}/verification")
def list_verification(finding_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    from app.models.finding import Finding as F

    finding = db.get(F, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding {finding_id} not found.")
    case = db.get(Case, finding.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    tasks = verification_service.list_tasks(db, finding_id)
    return ok([verification_service.task_to_dict(t) for t in tasks])


@router.post("/findings/{finding_id}/verification", status_code=201)
def generate_verification(
    finding_id: str,
    payload: GenerateRequest | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    from app.models.finding import Finding as F
    finding = db.get(F, finding_id)
    if finding is None:
        raise NotFoundError(f"Finding {finding_id} not found.")
    case = db.get(Case, finding.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="editor")
    force = (payload.force if payload else False)
    tasks = verification_service.generate_verification_tasks(db, finding_id=finding_id, user_id=user.id, force=force)
    return ok([verification_service.task_to_dict(t) for t in tasks], "Verification tasks generated.", status_code=201)


@router.patch("/verification/{task_id}")
def patch_verification(task_id: str, payload: TaskPatch, db: Session = Depends(get_db), user: User = CurrentUser):
    updated = verification_service.update_task(db, task_id=task_id, user=user, payload=payload.model_dump(exclude_unset=True))
    return ok(verification_service.task_to_dict(updated), "Verification task updated.")


@router.post("/verification/{task_id}/responses", status_code=201)
def add_verification_response(task_id: str, payload: ResponseCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    resp = verification_service.add_response(
        db, task_id=task_id, user=user,
        response_text=payload.response_text,
        response_source_id=payload.response_source_id,
        reviewer_notes=payload.reviewer_notes,
    )
    task = verification_service.get_task(db, task_id)
    return ok(verification_service.task_to_dict(task), "Response recorded.", status_code=201)


@router.get("/cases/{case_id}/verification-queue")
def verification_queue(case_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    return ok(verification_service.verification_queue(db, case_id=case_id))
