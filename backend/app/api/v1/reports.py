"""Reporting endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import CurrentUser, require_workspace_member
from app.database import get_db
from app.models.case import Case
from app.models.user import User
from app.schemas.common import ok
from app.services import reporting as reporting_service

router = APIRouter(tags=["reports"])


@router.get("/cases/{case_id}/reports")
def get_report(
    case_id: str,
    format: str = Query(default="json", pattern="^(json|markdown)$"),
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    report = reporting_service.build_report(db, case_id)
    if format == "markdown":
        return ok({"format": "markdown", "content": report["markdown"]}, "Report generated.")
    # json: omit markdown duplicate? keep summary
    report.pop("markdown", None)
    return ok(report, "Report generated.")
