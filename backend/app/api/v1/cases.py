"""Case endpoints: create, list, detail, update, archive."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.permissions import CurrentUser, require_workspace_member, resolve_case
from app.database import get_db
from app.domain.schemas import CaseCreate, CaseRead, CaseUpdate
from app.models.user import User
from app.schemas.common import ok, page_meta
from app.services import audit, case as case_service
from app.services import workspace as workspace_service

router = APIRouter(tags=["cases"])


@router.post("/workspaces/{workspace_id}/cases", status_code=201)
def create_case(
    workspace_id: str,
    payload: CaseCreate,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    require_workspace_member(workspace_id, user, db, min_role="editor")
    case = case_service.create_case(db, workspace_id, user, payload.model_dump())
    audit.record_event(
        db,
        workspace_id=workspace_id,
        actor_id=user.id,
        entity_type="case",
        entity_id=case.id,
        action="created",
        after_state={"title": case.title},
    )
    return ok(_read(db, case).model_dump(mode="json"), "Case created.", status_code=201)


@router.get("/workspaces/{workspace_id}/cases")
def list_cases(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    require_workspace_member(workspace_id, user, db, min_role="viewer")
    rows, total = case_service.list_cases(db, workspace_id, _page(limit), max(offset, 0))
    return ok(
        [_read(db, c).model_dump(mode="json") for c in rows],
        meta=page_meta(total, _page(limit), max(offset, 0)),
    )


@router.get("/cases/{case_id}")
def get_case(case_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    case = resolve_case(db, user, case_id)
    return ok(_read(db, case).model_dump(mode="json"))


@router.patch("/cases/{case_id}")
def update_case(
    case_id: str,
    payload: CaseUpdate,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = resolve_case(db, user, case_id, min_role="editor")
    updated = case_service.update_case(db, case, payload.model_dump(exclude_unset=True))
    audit.record_event(
        db,
        workspace_id=updated.workspace_id,
        actor_id=user.id,
        entity_type="case",
        entity_id=updated.id,
        action="updated",
        after_state={"status": updated.status},
    )
    return ok(_read(db, updated).model_dump(mode="json"), "Case updated.")


def _page(limit: int) -> int:
    return min(max(limit, 1), 200)


def _read(db: Session, case) -> CaseRead:
    counts = case_service.case_counts(db, case)
    return CaseRead(
        id=case.id,
        workspace_id=case.workspace_id,
        title=case.title,
        description=case.description,
        domain=case.domain,
        scope_definition=case.scope_definition,
        status=case.status,  # type: ignore[arg-type]
        observation_start=case.observation_start,
        observation_end=case.observation_end,
        created_at=case.created_at,
        updated_at=case.updated_at,
        **counts,
    )
