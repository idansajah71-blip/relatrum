# Architecture

RELATRUM backend is a modular monolith (FastAPI + SQLAlchemy + SQLite/Postgres-portable).

## Modules
- `app/api/v1`: HTTP routers (auth, workspaces, cases, sources, statements, analysis, findings, verification, reports, graph, system).
- `app/core`: security, permissions, exceptions, logging.
- `app/models`: 19 normalized tables with FKs and indexes.
- `app/services`: ingestion, extraction, normalization, alignment, temporal, divergence, findings, verification, reporting, graph, orchestration, audit.
- `app/ai`: provider interface (Gemini, Groq, Mock) + prompts + usage tracking.
- `app/utils`: hashing, text, dates.

## Data flow
Upload source -> text extraction -> evidence spans -> statement extraction -> normalization -> alignment (candidate retrieval + classification + temporal) -> divergence detection -> findings -> MRE verification tasks -> reporting.

## Persistence
SQLite for dev (FK enforcement), portable to PostgreSQL. Alembic migrations authoritative. Append-only audit + review history.

## Provider architecture
Provider-independent interface; mock deterministic default; external providers optional via env.
