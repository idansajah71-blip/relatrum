"""Reproducible analysis runs and AI invocation accounting."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import UuidPkMixin


class AnalysisRun(Base, UuidPkMixin):
    __tablename__ = "analysis_runs"
    __table_args__ = (Index("ix_runs_case", "case_id", "status"),)

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    pipeline_version: Mapped[str] = mapped_column(String(30), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False, default="none")
    provider_name: Mapped[str] = mapped_column(String(30), nullable=False, default="mock")
    model_name: Mapped[str] = mapped_column(String(120), nullable=False, default="deterministic-heuristics")
    input_manifest_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    started_at: Mapped[str | None] = mapped_column(String(64))
    completed_at: Mapped[str | None] = mapped_column(String(64))
    execution_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)
    failure_reason: Mapped[str | None] = mapped_column(Text)

    case = relationship("Case", back_populates="analysis_runs")
    alignments = relationship("Alignment", back_populates="analysis_run", cascade="all, delete-orphan")
    invocations = relationship("AiInvocation", back_populates="analysis_run", cascade="all, delete-orphan")


class AiInvocation(Base, UuidPkMixin):
    __tablename__ = "ai_invocations"

    analysis_run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True, nullable=False
    )
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(50), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(30), nullable=False)
    input_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    request_status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_token_count: Mapped[int | None] = mapped_column(Integer)
    output_token_count: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float | None] = mapped_column(Float)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    analysis_run = relationship("AnalysisRun", back_populates="invocations")
