"""Statement endpoints: extraction trigger, case statements, detail, correction."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import CurrentUser, require_workspace_member
from app.database import get_db
from app.models.evidence import EvidenceSpan
from app.models.source import Source, SourceVersion
from app.models.statement import Statement, StatementEvidence
from app.models.user import User
from app.schemas.common import ok, page_meta
from app.services import audit
from app.services import extraction as extraction_service

router = APIRouter(tags=["statements"])


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StatementRead(BaseModel):
    id: str
    case_id: str
    source_version_id: str
    source_id: str | None = None
    statement_type: str
    original_text: str
    normalized_text: str | None
    subject: str | None
    actor: str | None
    action: str | None
    object: str | None
    condition: str | None
    modality: str | None
    frequency: str | None
    temporal_valid_from: str | None
    temporal_valid_until: str | None
    observed_at: str | None
    reported_at: str | None
    extraction_confidence: float | None
    review_status: str
    creator_analysis_run_id: str | None
    created_at: str | None = None
    span_ids: list[str] = []


class StatementPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement_type: str | None = Field(
        default=None,
        pattern="^(requirement|observation|contextual_claim|operational_practice|hypothesis|unknown)$",
    )
    normalized_text: str | None = None
    subject: str | None = None
    actor: str | None = None
    action: str | None = None
    object: str | None = None
    condition: str | None = None
    modality: str | None = Field(
        default=None, pattern="^(mandatory|recommended|conditional|permissive|unknown)$"
    )
    frequency: str | None = None
    temporal_valid_from: str | None = Field(default=None, max_length=64)
    temporal_valid_until: str | None = Field(default=None, max_length=64)
    observed_at: str | None = Field(default=None, max_length=64)
    reported_at: str | None = Field(default=None, max_length=64)
    review_status: str | None = Field(
        default=None, pattern="^(draft|confirmed|corrected|rejected)$"
    )


@router.post("/sources/{source_id}/extract", status_code=200)
async def extract_statements(
    source_id: str, db: Session = Depends(get_db), user: User = CurrentUser
):
    report = await extraction_service.extract_statements_for_source(
        db, source_id=source_id, user_id=user.id
    )
    return ok(
        {
            "analysis_run_id": report.analysis_run_id,
            "provider": report.provider,
            "model": report.model,
            "statements_created": report.created,
            "statements_rejected_fabricated": report.rejected_fabricated,
            "span_ids": report.span_ids,
        },
        "Extraction completed.",
    )


@router.get("/cases/{case_id}/statements")
def list_statements(
    case_id: str,
    limit: int = 100,
    offset: int = 0,
    statement_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    from app.models.case import Case

    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")
    q = db.query(Statement).filter(Statement.case_id == case.id)
    if statement_type:
        q = q.filter(Statement.statement_type == statement_type)
    total = q.count()
    rows = q.order_by(Statement.created_at.asc()).offset(max(offset, 0)).limit(min(max(limit, 1), 200)).all()
    data = [_statement_data(db, s).model_dump(mode="json") for s in rows]
    return ok(data, meta=page_meta(total, min(max(limit, 1), 200), max(offset, 0)))


@router.get("/statements/{statement_id}")
def get_statement(statement_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    statement = _authorized_statement(db, user, statement_id)
    data = _statement_data(db, statement)
    return ok(data.model_dump(mode="json"))


@router.patch("/statements/{statement_id}")
def patch_statement(
    statement_id: str,
    payload: StatementPatch,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    statement = _authorized_statement(db, user, statement_id, min_role="editor")
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)
    for field, value in changes.items():
        setattr(statement, field, value)
    from app.services.normalization.normalize import normalize_statement_text

    if "normalized_text" not in changes:
        statement.normalized_text = normalize_statement_text(statement.original_text)
    db.commit()
    audit.record_event(
        db,
        workspace_id=statement.case.workspace_id,
        actor_id=user.id,
        entity_type="statement",
        entity_id=statement.id,
        action="updated",
        after_state={"fields": sorted(changes.keys())},
    )
    return ok(_statement_data(db, statement).model_dump(mode="json"), "Statement updated.")


def _authorized_statement(db: Session, user: User, statement_id: str, min_role: str = "viewer") -> Statement:
    statement = db.get(Statement, statement_id)
    if statement is None:
        raise NotFoundError(f"Statement {statement_id} not found.")
    from app.models.case import Case

    case = db.get(Case, statement.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role=min_role)
    return statement


def _statement_data(db: Session, statement: Statement) -> StatementRead:
    source_version = db.get(SourceVersion, statement.source_version_id)
    links = (
        db.scalars(select(StatementEvidence).where(StatementEvidence.statement_id == statement.id)).all()
    )
    span_ids = [l.evidence_span_id for l in links]
    return StatementRead(
        id=statement.id,
        case_id=statement.case_id,
        source_version_id=statement.source_version_id,
        source_id=source_version.source_id if source_version else None,
        statement_type=statement.statement_type,
        original_text=statement.original_text,
        normalized_text=statement.normalized_text,
        subject=statement.subject,
        actor=statement.actor,
        action=statement.action,
        object=statement.object,
        condition=statement.condition,
        modality=statement.modality,
        frequency=statement.frequency,
        temporal_valid_from=statement.temporal_valid_from,
        temporal_valid_until=statement.temporal_valid_until,
        observed_at=statement.observed_at,
        reported_at=statement.reported_at,
        extraction_confidence=statement.extraction_confidence,
        review_status=statement.review_status,
        creator_analysis_run_id=statement.creator_analysis_run_id,
        created_at=statement.created_at.isoformat() if statement.created_at else None,
        span_ids=span_ids,
    )
