"""Alembic migration environment for RELATRUM.

The database URL comes from application settings (environment variables), never
from alembic.ini, so a single source of truth governs connections. All ORM
models are imported here for autogenerate support.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.config import get_settings
from app.database import Base
import app.models  # noqa: F401 - registers every table on Base.metadata


def _database_url() -> str:
    settings = get_settings()
    url = settings.database_url
    # Alembic runs synchronously; strip async drivers if ever introduced.
    if url.startswith("sqlite"):
        return url
    return url


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

config.set_main_option("sqlalchemy.url", _database_url())

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL, no DB connection)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connect and apply)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            # Required for SQLite ALTER TABLE limitations on later revisions.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
