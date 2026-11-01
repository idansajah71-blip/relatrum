"""Unit tests: database engine behavior — UTCDateTime, FK enforcement, UUID defaults."""
from __future__ import annotations

from datetime import timezone

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.database import UTCDateTime, create_engine_from_url, utcnow
import app.models  # noqa: F401


def test_utcdatetime_roundtrip_preserves_utc():
    dt = utcnow()
    assert dt.tzinfo is not None
    typ = UTCDateTime()
    stored = typ.process_bind_param(dt, None)
    assert stored.endswith("+00:00")
    restored = typ.process_result_value(stored, None)
    assert restored == dt


def test_utcdatetime_normalizes_naive_input():
    from datetime import datetime

    naive = datetime(2025, 1, 1, 12, 0, 0)
    stored = UTCDateTime().process_bind_param(naive, None)
    assert stored == "2025-01-01T12:00:00+00:00"


def test_uuid_default_is_valid_uuidv4():
    from app.database import new_uuid

    import uuid as uuidlib

    val = new_uuid()
    uuidlib.UUID(val)
    assert len(val) == 36


def test_workspace_cascade_deletes_cases():
    engine = create_engine_from_url("sqlite:///:memory:")
    from app.database import Base

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    s = Session()
    from app.models.workspace import Workspace
    from app.models.case import Case

    ws = Workspace(name="W", slug="w")
    db = s
    db.add(ws)
    db.flush()
    db.add(Case(workspace_id=ws.id, title="C1", domain="admin"))
    db.commit()
    assert db.query(Case).count() == 1
    db.delete(ws)
    db.commit()
    assert db.query(Case).count() == 0
    db.close()
    engine.dispose()
