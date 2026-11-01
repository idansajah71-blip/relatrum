"""Alignment candidates between requirements and observations."""
from __future__ import annotations

from sqlalchemy import Float, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import UuidPkMixin


class Alignment(Base, UuidPkMixin):
    __tablename__ = "alignments"
    __table_args__ = (
        Index("ix_alignments_case", "case_id"),
        Index("ix_alignments_run", "analysis_run_id"),
    )

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    requirement_statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("statements.id", ondelete="CASCADE"), index=True, nullable=False)
    observation_statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("statements.id", ondelete="CASCADE"), index=True, nullable=False)

    lexical_similarity: Mapped[float | None] = mapped_column(Float)
    semantic_similarity: Mapped[float | None] = mapped_column(Float)
    fuzzy_similarity: Mapped[float | None] = mapped_column(Float)
    temporal_compatibility: Mapped[str | None] = mapped_column(String(40))
    temporal_detail: Mapped[dict | None] = mapped_column(JSON, default=dict)
    alignment_type: Mapped[str] = mapped_column(String(40), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text)
    candidate_status: Mapped[str] = mapped_column(String(30), nullable=False, default="candidate")
    analysis_run_id: Mapped[str] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="CASCADE"), index=True, nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    case = relationship("Case", back_populates="alignments")
    analysis_run = relationship("AnalysisRun", back_populates="alignments")
