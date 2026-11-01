"""Investigation case services."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError, ValidationFailedError
from app.domain.enums import FindingStatus
from app.models.case import Case
from app.models.finding import Finding
from app.models.source import Source
from app.models.statement import Statement
from app.models.user import User


def _validate_optional_date(value: str | None, field: str) -> str | None:
    if value is None or value == "":
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValidationFailedError(f"{field} must be an ISO-8601 date or datetime.") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.isoformat()


def create_case(db: Session, workspace_id: str, user: User, payload: dict) -> Case:
    case = Case(
        workspace_id=workspace_id,
        title=payload["title"],
        description=payload.get("description"),
        domain=payload.get("domain"),
        scope_definition=payload.get("scope_definition"),
        observation_start=_validate_optional_date(payload.get("observation_start"), "observation_start"),
        observation_end=_validate_optional_date(payload.get("observation_end"), "observation_end"),
        created_by=user.id,
    )
    db.add(case)
    db.commit()
    return case


def update_case(db: Session, case: Case, payload: dict) -> Case:
    for field in ("title", "description", "domain", "scope_definition"):
        if payload.get(field) is not None:
            setattr(case, field, payload[field])
    if payload.get("status") is not None:
        case.status = payload["status"]
    if "observation_start" in payload:
        case.observation_start = _validate_optional_date(payload["observation_start"], "observation_start")
    if "observation_end" in payload:
        case.observation_end = _validate_optional_date(payload["observation_end"], "observation_end")
    db.commit()
    return case


def get_case(db: Session, case_id: str) -> Case:
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    return case


def case_counts(db: Session, case: Case) -> dict:
    source_count = db.scalar(select(func.count(Source.id)).where(Source.case_id == case.id)) or 0
    statement_count = (
        db.scalar(select(func.count(Statement.id)).where(Statement.case_id == case.id)) or 0
    )
    finding_count = (
        db.scalar(
            select(func.count(Finding.id)).where(
                Finding.case_id == case.id, Finding.status.not_in([FindingStatus.superseded.value])
            )
        )
        or 0
    )
    return {
        "source_count": source_count,
        "statement_count": statement_count,
        "finding_count": finding_count,
    }


def list_cases(db: Session, workspace_id: str, limit: int, offset: int):
    total = db.scalar(select(func.count(Case.id)).where(Case.workspace_id == workspace_id)) or 0
    rows = db.scalars(
        select(Case)
        .where(Case.workspace_id == workspace_id)
        .order_by(Case.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return rows, total
