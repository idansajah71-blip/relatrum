"""Atomic statements, their evidence links, and cross-statement relations."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, Integer, String, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import TimestampMixin, UuidPkMixin


class Statement(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "statements"
    __table_args__ = (
        Index("ix_statements_case_type", "case_id", "statement_type"),
    )

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    source_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    statement_type: Mapped[str] = mapped_column(String(30), nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_text: Mapped[str | None] = mapped_column(Text)

    subject: Mapped[str | None] = mapped_column(String(200))
    actor: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str | None] = mapped_column(String(200))
    object: Mapped[str | None] = mapped_column(String(200))
    condition: Mapped[str | None] = mapped_column(Text)
    modality: Mapped[str | None] = mapped_column(String(20))
    frequency: Mapped[str | None] = mapped_column(String(50))

    temporal_valid_from: Mapped[str | None] = mapped_column(String(64))
    temporal_valid_until: Mapped[str | None] = mapped_column(String(64))
    observed_at: Mapped[str | None] = mapped_column(String(64))
    reported_at: Mapped[str | None] = mapped_column(String(64))

    extraction_confidence: Mapped[float | None] = mapped_column(Float)
    review_status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    creator_analysis_run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    extraction_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)

    case = relationship("Case", back_populates="statements")
    source_version = relationship("SourceVersion", back_populates="statements")
    evidence_links = relationship("StatementEvidence", back_populates="statement", cascade="all, delete-orphan")

    def evidence_spans(self, db):
        from sqlalchemy import select
        from app.models.evidence import EvidenceSpan
        from app.models.statement import StatementEvidence
        links = db.scalars(select(StatementEvidence).where(StatementEvidence.statement_id == self.id)).all()
        return [db.get(EvidenceSpan, l.evidence_span_id) for l in links]


class StatementEvidence(Base, UuidPkMixin):
    __tablename__ = "statement_evidence"
    __table_args__ = (
        Index("ix_st_ev_statement", "statement_id"),
    )

    statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("statements.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_span_id: Mapped[str] = mapped_column(String(36), ForeignKey("evidence_spans.id", ondelete="CASCADE"), index=True, nullable=False)
    evidence_role: Mapped[str] = mapped_column(String(30), nullable=False, default="direct_support")
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    statement = relationship("Statement", back_populates="evidence_links")
    evidence_span = relationship("EvidenceSpan")


class StatementRelation(Base, UuidPkMixin):
    __tablename__ = "statement_relations"
    __table_args__ = (
        Index("ix_stmt_rel_source", "source_statement_id"),
        Index("ix_stmt_rel_target", "target_statement_id"),
    )

    source_statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("statements.id", ondelete="CASCADE"), index=True, nullable=False)
    target_statement_id: Mapped[str] = mapped_column(String(36), ForeignKey("statements.id", ondelete="CASCADE"), index=True, nullable=False)
    relation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    relationship_explanation: Mapped[str | None] = mapped_column(Text)
    created_by_analysis_run: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)
