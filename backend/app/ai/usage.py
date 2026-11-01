"""AI invocation accounting: write one row per provider call into ai_invocations."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.ai.base import TokenUsage
from app.models.analysis_run import AiInvocation


async def record_invocation(
    db: Session,
    *,
    analysis_run_id: str,
    provider: str,
    model: str,
    operation_type: str,
    prompt_version: str,
    input_hash: str | None,
    request_status: str,
    token_usage: TokenUsage | None = None,
    latency_ms: int | None = None,
    error_code: str | None = None,
) -> None:
    invocation = AiInvocation(
        analysis_run_id=analysis_run_id,
        provider=provider,
        model=model,
        operation_type=operation_type,
        prompt_version=prompt_version,
        input_hash=input_hash,
        request_status=request_status,
        input_token_count=token_usage.input_token_count if token_usage else None,
        output_token_count=token_usage.output_token_count if token_usage else None,
        estimated_cost=token_usage.estimated_cost if token_usage else None,
        latency_ms=latency_ms,
        error_code=error_code,
    )
    db.add(invocation)
    db.commit()
