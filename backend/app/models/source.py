"""Sources and immutable source versions."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, UTCDateTime, utcnow
from app.models.base import TimestampMixin, UuidPkMixin


class Source(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "sources"
    __table_args__ = (Index("ix_sources_case", "case_id", "source_type"),)

    workspace_id: Mapped[str] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.id", ondelete="CASCADE"), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(500))
    mime_type: Mapped[str | None] = mapped_column(String(150))
    file_size: Mapped[int | None] = mapped_column(Integer)
    storage_key: Mapped[str | None] = mapped_column(String(500))
    sha256: Mapped[str | None] = mapped_column(String(64), index=True)

    source_origin: Mapped[str] = mapped_column(String(40), nullable=False, default="unknown")
    source_author: Mapped[str | None] = mapped_column(String(200))
    authority_label: Mapped[str | None] = mapped_column(String(50))
    sensitivity_level: Mapped[str] = mapped_column(String(30), nullable=False, default="internal")
    source_date: Mapped[str | None] = mapped_column(String(64))
    captured_at: Mapped[str | None] = mapped_column(String(64))
    ingestion_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    created_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))

    case = relationship("Case", back_populates="sources")
    versions = relationship("SourceVersion", back_populates="source", cascade="all, delete-orphan", order_by="SourceVersion.version_number")


class SourceVersion(Base, UuidPkMixin):
    __tablename__ = "source_versions"
    __table_args__ = (UniqueConstraint("source_id", "version_number", name="uq_source_version"),)

    source_id: Mapped[str] = mapped_column(String(36), ForeignKey("sources.id", ondelete="CASCADE"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_sha256: Mapped[str | None] = mapped_column(String(64), index=True)
    extracted_text: Mapped[str | None] = mapped_column(Text)
    extraction_method: Mapped[str | None] = mapped_column(String(60))
    extraction_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    extraction_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)

    source = relationship("Source", back_populates="versions")
    spans = relationship("EvidenceSpan", back_populates="source_version", cascade="all, delete-orphan")
    statements = relationship("Statement", back_populates="source_version")
