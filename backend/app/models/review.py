"""Append-only human review history for findings."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import UuidPkMixin


class Review(Base, UuidPkMixin):
    """Append-only: review rows must never be updated or deleted."""
    __tablename__ = "reviews"
    __table_args__ = (Index("ix_reviews_finding", "finding_id"),)

    finding_id: Mapped[str] = mapped_column(String(36), ForeignKey("findings.id", ondelete="CASCADE"), index=True, nullable=False)
    reviewer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    decision: Mapped[str] = mapped_column(String(40), nullable=False)
    review_notes: Mapped[str | None] = mapped_column(Text)
    decision_rationale: Mapped[str | None] = mapped_column(Text)
    previous_status: Mapped[str | None] = mapped_column(String(30))
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    finding = relationship("Finding", back_populates="reviews")
