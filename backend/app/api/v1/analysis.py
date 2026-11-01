"""Analysis endpoints: alignment analysis trigger, alignment listing, run detail."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.core.permissions import CurrentUser, require_workspace_member
from app.database import get_db
from app.models.alignment import Alignment
from app.models.analysis_run import AiInvocation, AnalysisRun
from app.models.case import Case
from app.models.user import User
from app.schemas.common import ok, page_meta
from app.services.orchestration import analysis_service as orchestration_service

router = APIRouter(tags=["analysis"])


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


@router.post("/cases/{case_id}/analyze", status_code=200)
async def analyze_case(
    case_id: str,
    payload: AnalyzeRequest | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    report = await orchestration_service.run_alignment_analysis(db, case_id, user.id)
    return ok(
        {
            "analysis_run_id": report.analysis_run_id,
            "status": report.status,
            "provider": report.provider,
            "input_manifest_hash": report.manifest_hash,
            "candidates_evaluated": report.candidates_evaluated,
            "alignment_type_counts": report.type_counts,
            "persisted_alignments": report.persisted_alignments,
            "missing_observation_ids": report.missing_observation_ids,
            "unexplained_practice_ids": report.unexplained_practice_ids,
            "superseded_requirement_ids": report.superseded_requirement_ids,
        },
        "Alignment analysis completed.",
    )


@router.get("/cases/{case_id}/alignments")
def list_alignments(
    case_id: str,
    limit: int = 100,
    offset: int = 0,
    analysis_run_id: str | None = None,
    alignment_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = CurrentUser,
):
    case = db.get(Case, case_id)
    if case is None:
        raise NotFoundError(f"Case {case_id} not found.")
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")

    q = db.query(Alignment).filter(Alignment.case_id == case.id)
    if analysis_run_id:
        q = q.filter(Alignment.analysis_run_id == analysis_run_id)
    if alignment_type:
        q = q.filter(Alignment.alignment_type == alignment_type)
    total = q.count()
    rows = (
        q.order_by(Alignment.created_at.asc(), Alignment.id.asc())
        .offset(max(offset, 0))
        .limit(min(max(limit, 1), 200))
        .all()
    )
    data = [_alignment_data(a) for a in rows]
    return ok(data, meta=page_meta(total, min(max(limit, 1), 200), max(offset, 0)))


@router.get("/analysis-runs/{run_id}")
def get_analysis_run(run_id: str, db: Session = Depends(get_db), user: User = CurrentUser):
    run = db.get(AnalysisRun, run_id)
    if run is None:
        raise NotFoundError(f"Analysis run {run_id} not found.")
    case = db.get(Case, run.case_id)
    require_workspace_member(case.workspace_id, user, db, min_role="viewer")

    counts = (
        db.query(Alignment.alignment_type, func.count(Alignment.id))
        .filter(Alignment.analysis_run_id == run.id)
        .group_by(Alignment.alignment_type)
        .all()
    )
    invocations = db.query(AiInvocation).filter(AiInvocation.analysis_run_id == run.id).all()
    return ok(
        {
            "id": run.id,
            "case_id": run.case_id,
            "status": run.status,
            "pipeline_version": run.pipeline_version,
            "prompt_version": run.prompt_version,
            "provider_name": run.provider_name,
            "model_name": run.model_name,
            "input_manifest_hash": run.input_manifest_hash,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "failure_reason": run.failure_reason,
            "execution_metadata": run.execution_metadata,
            "alignment_type_counts": {t: n for t, n in counts},
            "invocations": [
                {
                    "id": i.id,
                    "provider": i.provider,
                    "model": i.model,
                    "operation_type": i.operation_type,
                    "prompt_version": i.prompt_version,
                    "request_status": i.request_status,
                    "input_token_count": i.input_token_count,
                    "output_token_count": i.output_token_count,
                    "latency_ms": i.latency_ms,
                    "error_code": i.error_code,
                    "created_at": i.created_at.isoformat() if i.created_at else None,
                }
                for i in invocations
            ],
        },
        "Analysis run detail.",
    )


def _alignment_data(a: Alignment) -> dict:
    return {
        "id": a.id,
        "case_id": a.case_id,
        "requirement_statement_id": a.requirement_statement_id,
        "observation_statement_id": a.observation_statement_id,
        "alignment_type": a.alignment_type,
        "lexical_similarity": a.lexical_similarity,
        "semantic_similarity": a.semantic_similarity,
        "fuzzy_similarity": a.fuzzy_similarity,
        "temporal_compatibility": a.temporal_compatibility,
        "temporal_detail": a.temporal_detail,
        "explanation": a.explanation,
        "candidate_status": a.candidate_status,
        "analysis_run_id": a.analysis_run_id,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }
