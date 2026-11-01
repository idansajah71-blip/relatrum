"""Workspace membership authorization and auth dependencies."""
from __future__ import annotations

from typing import Callable

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, PermissionDeniedError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

ROLE_RANK = {"viewer": 0, "reviewer": 1, "editor": 2, "owner": 3}


def auth_dependency(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise UnauthorizedError("Missing bearer token.")
    token = authorization.split(" ", 1)[1]
    try:
        payload = decode_token(token)
    except Exception:
        raise UnauthorizedError("Invalid or expired token.")
    user_id = payload.get("sub")
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive.")
    return user


CurrentUser: Callable = Depends(auth_dependency)


def require_workspace_member(
    workspace_id: str,
    user: User,
    db: Session,
    min_role: str = "viewer",
) -> WorkspaceMember:
    """Enforce workspace membership.

    Policy: a non-member sees a 404 identical to a missing workspace, so the
    existence of other workspaces is not leaked. A member with an insufficient
    role gets an explicit 403.
    """
    workspace = db.get(Workspace, workspace_id)
    if workspace is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    membership = db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    if membership is None:
        # Non-membership is indistinguishable from an unknown workspace (404):
        # avoids leaking the existence of the workspace to outsiders.
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    if ROLE_RANK.get(membership.role, -1) < ROLE_RANK.get(min_role, 99):
        raise PermissionDeniedError(f"Requires role >= {min_role}.")
    return membership


def resolve_case(db: Session, user: User, case_id: str, min_role: str = "viewer"):
    from app.models.case import Case

    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role)
    return case
