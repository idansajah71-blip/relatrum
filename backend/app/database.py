"""Database engine, session management, and shared column types.

SQLite is configured with foreign-key enforcement, WAL journaling and a busy
timeout. The UTCDateTime type stores timezone-aware UTC timestamps as ISO-8601
text, which keeps datetimes sortable and portable to PostgreSQL.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    """Timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class UTCDateTime(TypeDecorator):
    """ISO-8601 text storage of timezone-aware UTC datetimes (portable)."""

    cache_ok = True
    impl = type_engine = None  # set in __init__ via Text

    def __init__(self) -> None:
        from sqlalchemy.types import Text

        super().__init__(Text())

    def process_bind_param(self, value: datetime | None, dialect: Any) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def process_result_value(self, value: str | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt


class Base(DeclarativeBase):
    pass


def _sqlite_connect(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


def _set_sqlite_fk_on_all_connections(engine: Engine) -> None:
    if engine.url.get_backend_name() == "sqlite":
        event.listens_for(engine, "connect")(_sqlite_connect)


def create_engine_from_url(database_url: str) -> Engine:
    connect_args = {}
    if database_url.startswith("sqlite"):
        connect_args = {"check_same_thread": False}
    engine = create_engine(
        database_url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )
    _set_sqlite_fk_on_all_connections(engine)
    return engine


engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def init_engine(database_url: str | None = None) -> Engine:
    global engine, SessionLocal
    url = database_url or get_settings_url()
    engine = create_engine_from_url(url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)
    return engine


def get_settings_url() -> str:
    from app.config import get_settings

    return get_settings().database_url


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    if SessionLocal is None:
        init_engine()
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def create_all() -> None:
    """Create all tables (used for tests and quick-start; Alembic is authoritative)."""
    from app import models  # noqa: F401  (registers all tables on Base.metadata)

    if engine is None:
        init_engine()
    Base.metadata.create_all(engine)


def fk_integrity_check(db: Session) -> list[str]:
    """Run SQLite foreign_key_check; returns violating rows (empty = healthy)."""
    if engine is not None and engine.url.get_backend_name() == "sqlite":
        rows = db.execute(text("PRAGMA foreign_key_check")).fetchall()
        return [tuple(map(str, r)) for r in rows]
    return []
