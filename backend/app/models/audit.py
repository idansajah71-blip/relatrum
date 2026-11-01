"""Append-only audit events."""
from __future__ import annotations

from sqlalchemy import ForeignKey, Index, String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, UTCDateTime, utcnow
from app.models.base import UuidPkMixin


class AuditEvent(Base, UuidPkMixin):
    __tablename__ = "audit_events"
    __table_args__ = (Index("ix_audit_workspace", "workspace_id", "created_at"),)

    workspace_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    actor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"))
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    action: Mapped[str] = mapped_column(String(40), nullable=False)
    before_hash: Mapped[str | None] = mapped_column(String(64))
    after_hash: Mapped[str | None] = mapped_column(String(64))
    event_metadata: Mapped[dict | None] = mapped_column(JSON, default=dict)
    created_at: Mapped[object] = mapped_column(UTCDateTime(), default=utcnow)
