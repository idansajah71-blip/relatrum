# RELATRUM Backend

Evidence Intelligence Platform — backend (FastAPI).

## Features (implemented)
- Workspaces, cases, source ingestion (TXT/PDF/DOCX/CSV/manual text) with provenance and evidence spans.
- Atomic statement extraction (mock provider deterministic; Gemini/Groq optional).
- Alignment engine (TF-IDF + fuzzy + temporal reasoning) with bidirectional absence detection.
- Finding dossiers with evidence polarity and review history.
- Minimum Resolving Evidence (MRE) verification tasks and responses.
- Reporting (JSON/Markdown) and evidence graph.
- Mock mode works with no API key (`AI_PROVIDER=mock`).

## Prerequisites
- Python 3.11+
- PostgreSQL not required for dev (SQLite default).

## Setup
```
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Run
```
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```
OpenAPI: http://localhost:8000/docs

## Tests
```
python -m pytest
```
Current: 100 passed.

## AI providers
- `AI_PROVIDER=mock` (default, deterministic, offline).
- Gemini/Groq optional via env keys; never exposed to frontend.

## Known limitations
- MRE uses rule-based templates, not statistically optimized.
- Embeddings (sentence-transformers) disabled by default.
- No frontend yet (backend-first).
