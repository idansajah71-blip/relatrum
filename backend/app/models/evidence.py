"""Evidence spans: the fundamental provenance unit."""
from __future__ import annotations

from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import UuidPkMixin


class EvidenceSpan(Base, UuidPkMixin):
    __tablename__ = "evidence_spans"
    __table_args__ = (
        CheckConstraint("start_char < end_char", name="ck_span_ordered"),
        Index("ix_spans_version", "source_version_id"),
    )

    source_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("source_versions.id", ondelete="CASCADE"), index=True, nullable=False
    )
    page_number: Mapped[int | None] = mapped_column(Integer)
    start_char: Mapped[int] = mapped_column(Integer, nullable=False)
    end_char: Mapped[int] = mapped_column(Integer, nullable=False)
    exact_quote: Mapped[str] = mapped_column(Text, nullable=False)
    paragraph_index: Mapped[int | None] = mapped_column(Integer)
    section_heading: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    source_version = relationship("SourceVersion", back_populates="spans")
