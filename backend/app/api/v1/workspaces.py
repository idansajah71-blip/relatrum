"""Workspace endpoints: create, list, detail, member management."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.core.permissions import CurrentUser
from app.database import get_db
from app.domain.schemas import (
    WorkspaceCreate,
    WorkspaceMemberAdd,
    WorkspaceMemberRead,
    WorkspaceRead,
)
from app.models.user import User
from app.schemas.common import ok
from app.services import audit, workspace as workspace_service

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", status_code=201)
def create_workspace(payload: WorkspaceCreate, db: Session = Depends(get_db), user: User = CurrentUser):
    ws = workspace_service.create_workspace(
        db, user=user, name=payload.name, description=payload.description, slug=payload.slug
    )
    audit.record_event(
        db,
        workspace_id=ws.id,
        actor_id=user.id,
        entity_type="workspace",
        entity_id=ws.id,
        action="created",
        after_state={"slug": ws.slug},
    )
    return ok(_read(ws, role="owner").model_dump(mode="json"), "Workspace created.", status_code=201)


@router.get("")
def list_workspaces(db: Session = Depends(get_db), user: User = CurrentUser):
    rows = workspace_service.list_workspaces_for_user(db, user)
    return ok(
        [_read(ws, role=member.role, case_count=count).model_dump(mode="json") for ws, member, count in rows]
    )


@router.get("/{workspace_id}")
def get_workspace(workspace_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    ws = workspace_service.ensure_workspace_of_id(db, workspace_id)
    member = workspace_service.get_membership(db, ws.id, user.id)
    if member is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    return ok(_read(ws, role=member.role).model_dump(mode="json"))


@router.get("/{workspace_id}/members")
def list_members(workspace_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    ws = workspace_service.ensure_workspace_of_id(db, workspace_id)
    member = workspace_service.get_membership(db, ws.id, user.id)
    if member is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    data = []
    for m in workspace_service.list_members(db, ws.id):
        user_row = m.user
        data.append(
            WorkspaceMemberRead(
                id=m.id,
                user_id=m.user_id,
                user_email=user_row.email if user_row else None,
                user_display_name=user_row.display_name if user_row else None,
                role=m.role,  # type: ignore[arg-type]
                joined_at=m.joined_at,
            ).model_dump(mode="json")
        )
    return ok(data)


@router.post("/{workspace_id}/members", status_code=201)
def add_member(
    workspace_id: str,
    payload: WorkspaceMemberAdd,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    ws = workspace_service.ensure_workspace_of_id(db, workspace_id)
    actor = workspace_service.get_membership(db, ws.id, user.id)
    if actor is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    try:
        member = workspace_service.add_member_by_email(
            db, ws, email=payload.email, role=payload.role, actor_role=actor.role
        )
    except PermissionError as exc:
        raise PermissionDeniedError(str(exc)) from exc
    audit.record_event(
        db,
        workspace_id=ws.id,
        actor_id=user.id,
        entity_type="workspace_member",
        entity_id=member.id,
        action="created",
        after_state={"role": member.role},
    )
    user_row = member.user
    data = WorkspaceMemberRead(
        id=member.id,
        user_id=member.user_id,
        user_email=user_row.email if user_row else None,
        user_display_name=user_row.display_name if user_row else None,
        role=member.role,  # type: ignore[arg-type]
        joined_at=member.joined_at,
    ).model_dump(mode="json")
    return ok(data, "Member added.", status_code=201)


def _read(ws, *, role, case_count: int | None = None) -> WorkspaceRead:
    return WorkspaceRead(
        id=ws.id,
        name=ws.name,
        slug=ws.slug,
        description=ws.description,
        role=role,  # type: ignore[arg-type]
        case_count=case_count,
        created_at=ws.created_at,
        updated_at=ws.updated_at,
    )
