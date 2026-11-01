"""Minimum Resolving Evidence (MRE) verification tasks and responses."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import TimestampMixin, UuidPkMixin


class VerificationTask(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "verification_tasks"
    __table_args__ = (Index("ix_verif_finding", "finding_id"),)

    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    unresolved_issue: Mapped[str | None] = mapped_column(Text)
    missing_information: Mapped[str | None] = mapped_column(Text)
    suggested_evidence_type: Mapped[str | None] = mapped_column(String(100))
    suggested_source: Mapped[str | None] = mapped_column(Text)
    expected_answer_structure: Mapped[dict | None] = mapped_column(JSON, default=dict)
    hypothesis_a: Mapped[str | None] = mapped_column(Text)
    hypothesis_b: Mapped[str | None] = mapped_column(Text)
    decision_relevance: Mapped[str | None] = mapped_column(Text)
    limitations: Mapped[str | None] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="proposed")
    assigned_to: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    due_at: Mapped[str | None] = mapped_column(String(64))
    created_by_run: Mapped[str | None] = mapped_column(String(36), ForeignKey("analysis_runs.id", ondelete="SET NULL"))

    finding = relationship("Finding", back_populates="verification_tasks")
    responses = relationship("VerificationResponse", back_populates="task", cascade="all, delete-orphan")


class VerificationResponse(Base, UuidPkMixin):
    __tablename__ = "verification_responses"

    verification_task_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("verification_tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    response_text: Mapped[str] = mapped_column(Text, nullable=False)
    response_source_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("sources.id", ondelete="SET NULL"))
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    submitted_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    submitted_at = mapped_column(UTCDateTime(), default=utcnow)

    task = relationship("VerificationTask", back_populates="responses")
