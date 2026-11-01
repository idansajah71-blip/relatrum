# RELATRUM Backend

Evidence Intelligence Platform — FastAPI backend.

## Overview
RELATRUM turns fragmented organizational information into a structured, traceable, time-aware evidence system. The backend exposes a REST API for workspaces, cases, source ingestion, statement extraction, alignment, findings, verification, reporting, and graph.

## Tech stack
- Python 3.11+, FastAPI, Pydantic v2
- SQLAlchemy 2.x, Alembic, SQLite (Postgres-portable)
- scikit-learn, RapidFuzz for candidate retrieval
- Providers: Mock (default), Gemini, Groq

## Setup
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- OpenAPI: http://localhost:8000/docs
- Health: http://localhost:8000/health/ready

## Configuration (.env)
```
APP_ENV=development
DATABASE_URL=sqlite:///./relatrum.db
AI_PROVIDER=mock
GEMINI_API_KEY=
GROQ_API_KEY=
MAX_UPLOAD_MB=10
```

## Tests
```bash
python -m pytest
```
Current result: 100 passed.

## API surface
- `/api/v1/workspaces`, `/cases`
- `/api/v1/cases/{id}/sources`, `/sources/{id}/extract`
- `/api/v1/cases/{id}/statements`
- `/api/v1/cases/{id}/analyze`, `/alignments`, `/analysis-runs/{id}`
- `/api/v1/cases/{id}/findings`, `/findings/{id}/...`
- `/api/v1/findings/{id}/verification`, `/verification/{id}/...`
- `/api/v1/cases/{id}/reports`, `/graph`, `/verification-queue`
- `/api/v1/system/info`, `/system/providers`

## Database
- 19 normalized tables, UUID PKs, FK enforcement, Alembic migrations.
- See [data dictionary](../docs/data-dictionary.md).

## Known limitations
- MRE uses rule-based templates (not statistically optimized).
- Local embeddings disabled by default.
- Frontend is a vertical slice.
