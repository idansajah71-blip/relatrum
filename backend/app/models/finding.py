"""Findings: structured evidence dossiers (never auto-proven violations)."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import TimestampMixin, UuidPkMixin


class Finding(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "findings"
    __table_args__ = (
        Index("ix_findings_case_status", "case_id", "status"),
    )

    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    finding_code: Mapped[str] = mapped_column(String(60), nullable=False)
    finding_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    detailed_explanation: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    priority_factors: Mapped[dict | None] = mapped_column(JSON, default=dict)
    impact_context: Mapped[str | None] = mapped_column(Text)
    scope: Mapped[str | None] = mapped_column(Text)
    quality_profile: Mapped[dict | None] = mapped_column(JSON, default=dict)
    first_detected_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)
    last_updated_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)
    created_by_analysis_run: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    last_confirmed_by_run: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"))
    supersedes_finding_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("findings.id", ondelete="SET NULL"))

    case = relationship("Case", back_populates="findings")
    evidence = relationship("FindingEvidence", back_populates="finding", cascade="all, delete-orphan")
    reviews = relationship("Review", back_populates="finding", cascade="all, delete-orphan")
    verification_tasks = relationship("VerificationTask", back_populates="finding", cascade="all, delete-orphan")


class FindingEvidence(Base, UuidPkMixin):
    """Link between a finding dossier and the evidence that constitutes it.

    Polarity is epistemically explicit: 'unresolved' is the conservative default,
    never claim support unless the analysis asserts it. At least one of the two
    references (a source span or a statement) must be present.
    """
    __tablename__ = "finding_evidence"
    __table_args__ = (
        CheckConstraint(
            "evidence_span_id IS NOT NULL OR statement_id IS NOT NULL",
            name="ck_finding_evidence_has_reference",
        ),
        Index("ix_finding_evidence_finding", "finding_id"),
        Index("ix_finding_evidence_statement", "statement_id"),
    )

    finding_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False
    )
    evidence_span_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evidence_spans.id", ondelete="CASCADE")
    )
    statement_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("statements.id", ondelete="SET NULL")
    )
    evidence_polarity: Mapped[str] = mapped_column(String(20), nullable=False, default="unresolved")
    relevance_explanation: Mapped[str | None] = mapped_column(Text)
    relationship_type: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    finding = relationship("Finding", back_populates="evidence")
    evidence_span = relationship("EvidenceSpan")
    statement = relationship("Statement")
