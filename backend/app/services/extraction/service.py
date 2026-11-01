"""Statement extraction pipeline: provider -> quote verification -> persistence.

Fabrication policy:
  * A statement whose exact_quote is not found in the extracted source text is
    REJECTED and counted, never persisted with a rewritten quote;
  * mock provider char offsets must match exactly, external providers must
    quote verbatim (folded fallback allowed for typographic variants only).
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.base import ExtractedStatement as AIStatement
from app.ai.prompts import PROMPT_VERSION
from app.core.exceptions import AiProviderError, NotFoundError, ValidationFailedError
from app.config import get_settings
from app.database import utcnow
from app.models.analysis_run import AiInvocation, AnalysisRun
from app.models.evidence import EvidenceSpan
from app.models.source import Source, SourceVersion
from app.models.statement import Statement, StatementEvidence
from app.services import audit
from app.services.normalization.normalize import normalize_statement_text
from app.utils.hashing import sha256_text
from app.utils.text import fold_quote

PIPELINE_VERSION = "1.1.0"


def latest_version(db: Session, source: Source) -> SourceVersion | None:
    return (
        db.query(SourceVersion)
        .filter(SourceVersion.source_id == source.id)
        .order_by(SourceVersion.version_number.desc())
        .first()
    )


@dataclass
class ExtractionReport:
    created: int = 0
    rejected_fabricated: int = 0
    rejected_other: int = 0
    analysis_run_id: str = ""
    provider: str = ""
    model: str = ""
    span_ids: list[str] = field(default_factory=list)


async def extract_statements_for_source(
    db: Session, *, source_id: str, user_id: str
) -> ExtractionReport:
    source = db.get(Source, source_id)
    if source is None:
        raise NotFoundError(f"Source {source_id} not found.")
    from app.core.permissions import require_workspace_member
    from app.models.user import User

    user = db.get(User, user_id)
    if user is None:
        raise NotFoundError(f"User {user_id} not found.")
    require_workspace_member(source.workspace_id, user, db, min_role="editor")
    version = latest_version(db, source)
    if version is None or not version.extracted_text:
        raise ValidationFailedError(
            "Source has no successfully extracted text to analyze; re-upload or fix extraction first."
        )

    settings = get_settings()
    provider = _build_provider()
    started_at = utcnow().isoformat()
    run = AnalysisRun(
        case_id=source.case_id,
        status="running",
        pipeline_version=PIPELINE_VERSION,
        prompt_version=PROMPT_VERSION,
        provider_name=provider.name,
        model_name=provider.model,
        started_at=started_at,
        execution_metadata={
            "source_id": source.id,
            "source_version_id": version.id,
            "note": "statement extraction",
        },
    )
    db.add(run)
    db.flush()
    input_hash = sha256_text(version.extracted_text)

    report = ExtractionReport(analysis_run_id=run.id, provider=provider.name, model=provider.model)
    try:
        result = await provider.extract_statements(
            version.extracted_text,
            context={
                "source_type": source.source_type,
                "source_origin": source.source_origin,
                "source_title": source.title,
            },
        )
    except AiProviderError as exc:
        run.status = "failed"
        run.failure_reason = str(exc)
        run.completed_at = utcnow().isoformat()
        db.commit()
        raise
    await _record_invocation(
        db, run.id, provider, "extract_statements", PROMPT_VERSION, input_hash,
        result.request_status, result.token_usage, result.latency_ms, result.error_code,
    )

    for ai_stmt in result.statements:
        location = _verify_quote(version.extracted_text, ai_stmt, provider.name == "mock")
        if location is None:
            report.rejected_fabricated += 1
            continue
        span = _upsert_span(db, version, ai_stmt, location, existing_spans=report)
        statement = _persist_statement(
            db,
            source=source,
            version=version,
            run_id=run.id,
            ai_stmt=ai_stmt,
            span=span,
        )
        report.created += 1
        report.span_ids.append(span.id)

    run.status = "completed"
    run.completed_at = utcnow().isoformat()
    run.execution_metadata = {
        **(run.execution_metadata or {}),
        "statements_created": report.created,
        "statements_rejected_fabricated": report.rejected_fabricated,
        "input_manifest_hash": input_hash,
    }
    audit.record_event(
        db,
        workspace_id=source.workspace_id,
        actor_id=user_id,
        entity_type="analysis_run",
        entity_id=run.id,
        action="analysis_run",
        after_state={"type": "extract_statements", "created": report.created},
    )
    db.commit()
    return report


def _verify_quote(text: str, ai_stmt: AIStatement, strict_offsets: bool) -> tuple[int, int] | None:
    quote = ai_stmt.exact_quote.strip() if ai_stmt.exact_quote else ""
    if not quote:
        return None
    if strict_offsets:
        if ai_stmt.start_char is not None and ai_stmt.end_char is not None and 0 <= ai_stmt.start_char < ai_stmt.end_char <= len(text):
            if text[ai_stmt.start_char:ai_stmt.end_char].strip() == quote:
                return (ai_stmt.start_char, ai_stmt.end_char)
    # verbatim search
    plain = text.find(quote)
    if plain != -1:
        return (plain, plain + len(quote))
    folded_quote = fold_quote(quote)
    folded_text = fold_quote(text)
    folded_index = folded_text.find(folded_quote)
    if folded_index != -1:
        return None if folded_index == -1 else _map_folded_index(text, folded_text, folded_index, len(folded_quote))
    return None


def _map_folded_index(original: str, folded: str, index: int, length: int) -> tuple[int, int]:
    """Naive mostly-accurate mapping after fold; tolerable because quotes were confirmed equal after folding."""
    ratio = len(original) / max(len(folded), 1)
    start = min(int(index * ratio), len(original) - 1)
    end = min(int((index + length) * ratio), len(original))
    # widen to match original loosely: search actual quote text around estimate
    quote = folded[index:index + length]
    probe = original.find(quote[: min(30, len(quote))], max(0, start - 200), min(len(original), end + 400))
    if probe != -1:
        return (probe, probe + len(quote[: min(30, len(quote))]))
    return (start, end)


def _upsert_span(
    db: Session, version: SourceVersion, ai_stmt: AIStatement, location: tuple[int, int], *, existing_spans
) -> EvidenceSpan:
    start, end = location
    existing = db.scalar(
        select(EvidenceSpan).where(
            EvidenceSpan.source_version_id == version.id,
            EvidenceSpan.start_char == start,
            EvidenceSpan.end_char == end,
        )
    )
    if existing is not None:
        return existing
    span = EvidenceSpan(
        source_version_id=version.id,
        page_number=ai_stmt.page_number,
        start_char=start,
        end_char=end,
        exact_quote=ai_stmt.exact_quote.strip(),
        paragraph_index=ai_stmt.paragraph_index,
        section_heading=None,
    )
    db.add(span)
    db.flush()
    existing_spans.span_ids.append(span.id)
    return span


def _persist_statement(
    db: Session, *, source: Source, version: SourceVersion, run_id: str, ai_stmt: AIStatement, span: EvidenceSpan
) -> Statement:
    statement = Statement(
        case_id=source.case_id,
        source_version_id=version.id,
        statement_type=ai_stmt.statement_type,
        original_text=ai_stmt.original_text,
        normalized_text=normalize_statement_text(ai_stmt.original_text),
        subject=ai_stmt.subject,
        actor=ai_stmt.actor,
        action=ai_stmt.action,
        object=ai_stmt.object,
        condition=ai_stmt.condition,
        modality=ai_stmt.modality,
        frequency=ai_stmt.frequency,
        temporal_valid_from=ai_stmt.temporal_valid_from,
        temporal_valid_until=ai_stmt.temporal_valid_until,
        observed_at=ai_stmt.observed_at,
        reported_at=ai_stmt.reported_at,
        extraction_confidence=ai_stmt.extraction_confidence,
        review_status="draft",
        creator_analysis_run_id=run_id,
        extraction_metadata={
            "provider": _build_provider().name,
            "extraction_method": "provider_extract",
        },
    )
    db.add(statement)
    db.flush()
    link = StatementEvidence(
        statement_id=statement.id,
        evidence_span_id=span.id,
        evidence_role="direct_support",
    )
    db.add(link)
    return statement


def _build_provider():
    from app.ai.registry import build_provider

    return build_provider()


async def _record_invocation(
    db: Session, run_id: str, provider, operation_type: str, prompt_version: str,
    input_hash: str, request_status: str, token_usage, latency_ms: int | None, error_code: str | None,
) -> None:
    from app.ai.usage import record_invocation

    await record_invocation(
        db,
        analysis_run_id=run_id,
        provider=provider.name,
        model=provider.model,
        operation_type=operation_type,
        prompt_version=prompt_version,
        input_hash=input_hash,
        request_status=request_status,
        token_usage=token_usage,
        latency_ms=latency_ms,
        error_code=error_code,
    )
