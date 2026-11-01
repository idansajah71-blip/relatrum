"""Investigation cases."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.base import TimestampMixin, UuidPkMixin


class Case(Base, UuidPkMixin, TimestampMixin):
    __tablename__ = "cases"
    __table_args__ = (Index("ix_cases_workspace_status", "workspace_id", "status"),)

    workspace_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    domain: Mapped[str | None] = mapped_column(String(120))
    scope_definition: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    observation_start: Mapped[str | None] = mapped_column(String(64))  # ISO date/datetime text
    observation_end: Mapped[str | None] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    workspace = relationship("Workspace", back_populates="cases")
    sources = relationship("Source", back_populates="case")
    statements = relationship("Statement", back_populates="case")
    alignments = relationship("Alignment", back_populates="case")
    findings = relationship("Finding", back_populates="case")
    analysis_runs = relationship("AnalysisRun", back_populates="case")
