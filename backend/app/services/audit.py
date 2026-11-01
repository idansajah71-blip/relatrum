"""Append-only audit event writer for important operations."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.audit import AuditEvent


def record_event(
    db: Session,
    *,
    workspace_id: str,
    actor_id: str | None,
    entity_type: str,
    entity_id: str | None,
    action: str,
    after_state: dict | None = None,
) -> None:
    """Write one audit event in the same transaction as or after the mutation.

    Only small reference states are embedded (id-level metadata); document
    bodies never land in the audit trail.
    """
    event = AuditEvent(
        workspace_id=workspace_id,
        actor_id=actor_id,
        entity_type=entity_type,
        entity_id=entity_id or "n/a",
        action=action,
        event_metadata=after_state or {},
    )
    db.add(event)
    db.commit()
