# RELATRUM — Evidence Intelligence Platform

> Where expectations meet evidence.

RELATRUM is an evidence intelligence platform that turns fragmented organizational information into a structured, traceable, time-aware evidence system. It identifies possible divergence between official requirements and real-world observations, preserves uncertainty and counter-evidence, and proposes the minimum evidence needed to resolve each finding.

## Status

- Backend: complete (Phases 0–8), 100 tests passing.
- Frontend: vertical slice (Phases 9–12), production build passing.
- Default mode runs fully offline with `AI_PROVIDER=mock` (no API key).

## Quick start

### Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --port 8000
```
OpenAPI: http://localhost:8000/docs

### Frontend
```bash
cd frontend
npm install
npm run dev
```
Open http://localhost:3000

### Tests
```bash
cd backend
python -m pytest
```

## Documentation
- [Architecture](docs/architecture.md)
- [Data Dictionary](docs/data-dictionary.md)
- [AI Methodology](docs/ai-methodology.md)
- [Evaluation](docs/evaluation.md)
- [Privacy](docs/privacy.md)
- [Backend README](backend/README.md)

## Core capabilities
- Secure multi-tenant workspaces and cases.
- Source ingestion (TXT, PDF, DOCX, CSV, manual text) with provenance spans.
- Atomic statement extraction with verbatim quote verification.
- Bidirectional alignment (requirement ↔ observation) with temporal reasoning.
- Finding dossiers with supporting/counter/context/unresolved evidence.
- Minimum Resolving Evidence (MRE) verification tasks and responses.
- Evidence graph and Markdown/JSON reports.

## Responsible AI
Findings are candidates requiring human review, never auto-proven violations. Absence of evidence is not evidence of non-compliance. Mock mode is deterministic heuristics, disclosed as such.

## License
Proprietary / internal project.
