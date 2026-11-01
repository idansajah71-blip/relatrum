"""Findings: structured evidence dossiers (never auto-proven violations)."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text, JSON
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
