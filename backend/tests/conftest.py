"""Test configuration and shared fixtures for RELATRUM backend tests.

Runs entirely offline: no external AI calls, no real network. Environment is
pinned to `testing` before application modules are imported.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path

# Pin the environment BEFORE app modules import (env vars beat .env file).
BACKEND_DIR = Path(__file__).resolve().parents[1]
os.environ["APP_ENV"] = "testing"
os.environ["JWT_SECRET"] = secrets.token_urlsafe(32)
os.environ.setdefault("AI_PROVIDER", "mock")
_TEST_DB = BACKEND_DIR / "_test_rel.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB}"

import pytest
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.database import Base, create_engine_from_url, utcnow
import app.models  # noqa: F401 - registers all tables


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    """Each test sees a freshly-read Settings object."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def memory_engine():
    engine = create_engine_from_url("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db(memory_engine):
    session_factory = sessionmaker(bind=memory_engine, expire_on_commit=False, future=True)
    session = session_factory()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def api_client():
    """TestClient with lifespan (engine init + schema pre-created)."""
    from fastapi.testclient import TestClient

    from app.database import create_all, init_engine

    if _TEST_DB.exists():
        _TEST_DB.unlink()
    engine = init_engine(f"sqlite:///{_TEST_DB}")
    create_all()

    from app.main import app

    with TestClient(app) as client:  # context manager triggers lifespan
        yield client
    engine.dispose()
    if _TEST_DB.exists():
        _TEST_DB.unlink()
    for suffix in ("-wal", "-shm"):
        p = Path(str(_TEST_DB) + suffix)
        if p.exists():
            p.unlink()


# ---------------------------------------------------------------------------
# Entity builders (used across model/service tests)


@pytest.fixture()
def user_factory(db):
    from app.core.security import hash_password
    from app.models.user import User

    def make(email="alice@example.org", display_name="Alice"):
        user = User(email=email, password_hash=hash_password("correct-horse"), display_name=display_name)
        db.add(user)
        db.commit()
        return user

    return make


@pytest.fixture()
def workspace_factory(db):
    from app.models.workspace import Workspace

    def make(user=None, name="Test Workspace", member_role="owner"):
        ws = Workspace(name=name, slug=f"test-{secrets.token_hex(4)}")
        db.add(ws)
        db.flush()
        if user is not None:
            from app.models.workspace import WorkspaceMember

            db.add(WorkspaceMember(workspace_id=ws.id, user_id=user.id, role=member_role))
        db.commit()
        return ws

    return make


@pytest.fixture()
def case_factory(db):
    from app.models.case import Case

    def make(workspace):
        case = Case(
            workspace_id=workspace.id,
            title="Certificate processing investigation",
            domain="administrative_process",
        )
        db.add(case)
        db.commit()
        return case

    return make


@pytest.fixture()
def source_chain_factory(db):
    """workspace -> case -> source -> source_version -> evidence span."""
    from app.models.evidence import EvidenceSpan
    from app.models.source import Source, SourceVersion

    def make(case, text="Complete applications must be processed within two working days."):
        source = Source(
            workspace_id=case.workspace_id,
            case_id=case.id,
            source_type="policy",
            title="Certificate Processing Policy v1",
            source_origin="official_document",
            ingestion_status="extracted",
        )
        db.add(source)
        db.flush()
        version = SourceVersion(
            source_id=source.id,
            version_number=1,
            content_sha256=secrets.token_hex(32),
            extracted_text=text,
            extraction_method="native_text",
            extraction_status="success",
        )
        db.add(version)
        db.flush()
        span = EvidenceSpan(
            source_version_id=version.id,
            start_char=0,
            end_char=len(text),
            exact_quote=text,
        )
        db.add(span)
        db.commit()
        return source, version, span

    return make


@pytest.fixture()
def timestamp_now():
    return utcnow()
