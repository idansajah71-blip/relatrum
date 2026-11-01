"""Workspace and membership services."""
from __future__ import annotations

import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.core.security import hash_password
from app.domain.enums import WorkspaceRole
from app.models.case import Case
from app.models.user import User
from app.models.workspace import Workspace, WorkspaceMember

_DEFENSIBLE_ROLE_RANK = {"viewer": 0, "reviewer": 1, "editor": 2, "owner": 3}


def slugify(name: str) -> str:
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    text = re.sub(r"-{2,}", "-", text)
    return text[:64] or "workspace"


def create_workspace(db: Session, user: User, name: str, description: str | None, slug: str | None) -> Workspace:
    final_slug = slug or slugify(name)
    exists = db.scalar(select(Workspace).where(Workspace.slug == final_slug))
    if exists is not None:
        raise ConflictError(f"Slug '{final_slug}' is already in use.")
    ws = Workspace(name=name, slug=final_slug, description=description)
    ws.members = [WorkspaceMember(user_id=user.id, role=WorkspaceRole.owner.value)]
    db.add(ws)
    db.commit()
    return ws


def get_membership(db: Session, workspace_id: str, user_id: str) -> WorkspaceMember | None:
    return db.scalar(
        select(WorkspaceMember).where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user_id,
        )
    )


def list_workspaces_for_user(db: Session, user: User) -> list[tuple[Workspace, WorkspaceMember, int]]:
    rows = db.execute(
        select(Workspace, WorkspaceMember, func.count(Case.id))
        .join(WorkspaceMember, WorkspaceMember.workspace_id == Workspace.id)
        .outerjoin(Case, Case.workspace_id == Workspace.id)
        .where(WorkspaceMember.user_id == user.id)
        .group_by(Workspace.id, WorkspaceMember.id)
        .order_by(Workspace.created_at.desc())
    ).all()
    return rows


def add_member_by_email(db: Session, workspace: Workspace, email: str, role: str, actor_role: str) -> WorkspaceMember:
    from app.core.exceptions import PermissionDeniedError
    from app.core.security import hash_password as _hp
    import secrets as _secrets

    def _rank(value: str) -> int:
        return {"viewer": 0, "reviewer": 1, "editor": 2, "owner": 3}.get(value, -1)

    if _rank(actor_role) < _rank("editor"):
        raise PermissionDeniedError("Requires role >= editor.")
    if _rank(actor_role) < _rank(role):
        raise PermissionDeniedError("Cannot grant a role above your own.")
    if role == WorkspaceRole.owner.value and actor_role != WorkspaceRole.owner.value:
        raise PermissionDeniedError("Only owners may invite owners.")
    lowered = email.lower().strip()
    user = db.scalar(select(User).where(User.email == lowered))
    if user is None:
        # Auto-provision an inactive placeholder so the invitation survives
        # until the invited person registers with this email. The password is
        # unguessable and the account is inactive, so nobody can log in yet.
        user = User(
            email=lowered,
            password_hash=_hp(_secrets.token_urlsafe(24)),
            display_name=lowered.split("@")[0],
            is_active=False,
        )
        db.add(user)
        db.flush()
    existing = get_membership(db, workspace.id, user.id)
    if existing is not None:
        raise ConflictError("User is already a member of this workspace.")
    member = WorkspaceMember(workspace_id=workspace.id, user_id=user.id, role=role)
    db.add(member)
    db.commit()
    return member


def list_members(db: Session, workspace_id: str) -> list[WorkspaceMember]:
    return list(
        db.scalars(select(WorkspaceMember).where(WorkspaceMember.workspace_id == workspace_id)).all()
    )


def ensure_workspace_of_id(db: Session, workspace_id: str) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None:
        raise NotFoundError(f"Workspace {workspace_id} not found.")
    return ws
