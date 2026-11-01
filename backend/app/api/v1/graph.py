"""Evidence graph endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import CurrentUser, require_workspace_member
from app.database import get_db
from app.models.case import Case
from app.models.user import User
from app.schemas.common import ok
from app.services import graph as graph_service

router = APIRouter(tags=["graph"])


@router.get("/cases/{case_id}/graph")
def get_graph(case_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    return ok(graph_service.build_graph(db, case_id))
