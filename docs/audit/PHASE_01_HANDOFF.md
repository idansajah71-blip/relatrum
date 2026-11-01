# RELATRUM — Phase 01 Handoff

**Document:** `docs/audit/PHASE_01_HANDOFF.md`
**Phase completed:** 01 — Repository Reconnaissance & Technical Audit
**Date:** 2026-10-31
**Audience:** The next development session (Phase 2). Written to be self-sufficient —
you should not need any prior conversation history to understand the project state.

---

## 0. Read this first

RELATRUM today is a **backend-only skeleton that does not run**. There is no frontend, no
tests, no migrations, and no version control. The database schema and infrastructure
chassis are **good and must be preserved**. One missing import currently prevents the
application from starting. Phase 2 must begin by restoring a runnable baseline, then build
feature-by-feature on the existing schema.

Do **not** rewrite the models, the config, the error envelope, or the logging. They are the
project's best assets.

---

## 1. Current Repository State

- **Root:** `c:\Users\User\Desktop\relatrum` (Windows). Working dir for the backend is
  `c:\Users\User\Desktop\relatrum\backend`.
- **Version control:** **NONE.** `git status` → `fatal: not a git repository`. There is no
  `.git` and no `.gitignore`. Nothing is committed anywhere. Treat the working tree as the
  only copy.
- **Contents:** one `backend/` tree only. 27 Python files + `requirements.txt` +
  `.env.example`.
- **Runtime status:** `python -c "import app.main"` **succeeds**, but the app **crashes at
  startup** because the lifespan calls `create_all()`, which imports `app.models`, which
  raises `NameError` (see §4, P0-1).
- **Database:** no `*.db`/`*.sqlite` file exists anywhere. `create_all()` has never
  succeeded, so no schema has ever been materialised.
- **Environment:** Python 3.12.4 with all `requirements.txt` packages installed **globally**
  (no project venv). No lockfile. Global site-packages also contain unrelated packages.
- **Docs:** none existed before Phase 1; the three `docs/audit/*` files are the first.
- **Secrets:** no `.env` file exists; only `.env.example` with placeholders. No real
  credentials were found. Effective JWT secret is the insecure built-in default (see SEC-03).

---

## 2. Existing Technology Decisions (preserve these)

| Decision | Rationale (as implemented) |
|---|---|
| **FastAPI** as the API framework | Async-capable, Pydantic-native, OpenAPI built in |
| **Pydantic v2 + pydantic-settings** for config | Typed, validated, 12-factor; fail-fast `model_validator` |
| **SQLAlchemy 2.x** declarative with `Mapped[...]` | Modern typed ORM |
| **SQLite** as the development database | Zero-cost, file-based, no server, matches constraints |
| **Custom `UTCDateTime`** storing tz-aware UTC as ISO-8601 text | Sortable, portable to PostgreSQL, avoids SQLite naive-datetime bugs |
| **UUID string primary keys** (`new_uuid`) | Non-guessable, merge-friendly, portable across DBs |
| **Envelope response contract** (`success`/`message`/`data`/`meta`) | One consistent client contract; central error rendering |
| **`ApiError` hierarchy + global handlers** | No stack leakage in production; typed error codes |
| **Request-ID `ContextVar` + structured logs** | End-to-end traceability |
| **PBKDF2-HMAC-SHA256** password hashing (stdlib) | No extra dependency; salted; constant-time compare |
| **JWT HS256** access tokens via PyJWT | Simple, stateless; `jwt_expire_days` configurable |
| **Enum-as-string domain vocabulary** (`domain/enums.py`) | Serialises directly to API + DB; refactor-safe |
| **Alembic declared as the migration authority** | `create_all()` is explicitly a dev/test convenience only |
| **AI provider selected by config with `mock` default** | Product must work with zero API keys |
| **`AI_PROVIDER` may be `mock\|gemini\|groq`** | Free-tier-friendly (Gemini, Groq) |

These are deliberate. Only change them with a stated technical reason.

---

## 3. Existing Modules Worth Preserving

Preserve **as-is** (they are correct and reusable):

- `backend/app/database.py` — engine factory, PRAGMA setup (`foreign_keys=ON`,
  `journal_mode=WAL`, `busy_timeout`, `synchronous=NORMAL`), `UTCDateTime`, `Base`,
  `get_db`, `create_all`, `fk_integrity_check`.
- `backend/app/config.py` — `Settings` with provider/JWT/limit validation.
- `backend/app/core/logging.py` — request-id logging, third-party noise suppression.
- `backend/app/core/exceptions.py` — `ApiError` family, `envelope`, handlers.
- `backend/app/core/security.py` — `hash_password`, `verify_password`,
  `create_access_token`, `decode_token`.
- `backend/app/schemas/common.py` — `Envelope`, `PaginatedEnvelope`, `PaginationParams`.
- `backend/app/domain/enums.py` — all 25 enums; this is the product vocabulary.
- `backend/app/models/*` — the 19-table schema (fix the one import bug in `base.py`, then
  treat as the authoritative data model).
- `backend/app/main.py` — app factory, lifespan, CORS, request-id middleware, health
  endpoints (fix nothing except what §4 requires).
- `backend/app/api/v1/router.py` — router aggregation pattern.

Reusable **patterns** (not code) to continue:
- response envelope for every endpoint;
- typed `ApiError` subclasses instead of ad-hoc HTTP exceptions;
- traceability columns on every AI-generated row;
- append-only tables for history (`reviews`, `audit_events`).

---

## 4. Important Discovered Problems

### P0 — blockers (must fix before any feature work)

**P0-1 — Application cannot start (CRITICAL).**
`backend/app/models/base.py` uses `Mapped` and `mapped_column` but never imports them.
The class body is evaluated at import time, so importing anything that pulls in
`app.models` raises `NameError: name 'mapped_column' is not defined`.
Blast radius: `app.models`, `create_all()`, the app lifespan, `app.core.permissions`, and
every future model-dependent module.

Empirical evidence (executed 2026-10-31):

```
$ python -c "from app import models"
  File ".../app/models/base.py", line 11, in UuidPkMixin
    id: Mapped[str] = mapped_column(primary_key=True, default=new_uuid)
                      ^^^^^^^^^^^^^
NameError: name 'mapped_column' is not defined

$ python -c "from app.database import create_all; create_all()"
  → same NameError  (therefore: app startup fails)

$ python -c "import app.main"          → OK (models are imported lazily)
$ python -c "import app.core.permissions" → same NameError
```

Required fix (exact): add to `backend/app/models/base.py`

```python
from sqlalchemy.orm import Mapped, mapped_column
```

and remove the unused `from typing import Any` import. **This fix was deliberately NOT
applied in Phase 1** (audit phase: no application-code changes). It is the first action of
Phase 2.

**P0-2 — No version control.** Initialise git and add `.gitignore` before writing new code,
or the first refactor can destroy unrecoverable work.

**P0-3 — No Alembic configuration.** `alembic` is installed and declared, but there is no
`alembic.ini`, no `alembic/env.py`, and no revision history. The schema cannot be evolved
safely until this exists and an initial revision is generated from the current models.

### P1 — correctness & security

**P1-1 — Auth token read from a query parameter (SEC-01, High).**
`backend/app/core/permissions.py:19` declares `authorization: str | None = None`. Because
this is not a `Header(...)`/`Depends` parameter, FastAPI treats it as a **query parameter**;
the `Authorization` header is never read. Fix: `authorization: str | None = Header(default=None)`.

**P1-2 — Insecure default JWT secret (SEC-03, Medium).**
`config.py` default `dev-insecure-secret-change-me` is the *effective* signing key because
no `.env` exists. The guard only fires when `app_env == "production"`.

**P1-3 — Membership defaults to `owner` (SEC-04, Medium).**
`models/workspace.py:30` — `role` default is the highest privilege. Should be least privilege.

**P1-4 — RBAC policy is dead code (SEC-05, Medium).**
`permissions.py:49-53`: both branches raise the identical `NotFoundError`. The 403-vs-404
intent is unimplemented. Decide the policy explicitly and test it.

### P2 — hygiene

- **P2-1** Duplicate indexes: a column declared `index=True` *and* repeated in
  `__table_args__` (e.g. `evidence_spans.source_version_id`,
  `statement_evidence.statement_id`, both columns of `statement_relations`).
- **P2-2** Deprecated `HTTP_422_UNPROCESSABLE_ENTITY` (Starlette 1.6.0 warns) →
  `HTTP_422_UNPROCESSABLE_CONTENT`.
- **P2-3** Deprecated `fitz` alias (PyMuPDF 2.0 installed) → use `import pymupdf`.
- **P2-4** Inconsistent ORM typing: `Mapped[object]` for datetime columns; `Case.created_by`
  annotated `Mapped[str]` but `nullable=True`.
- **P2-5** `UTCDateTime.impl = type_engine = None` is a confusing construct (harmless).
- **P2-6** `RateLimitedError` defined but no rate limiting exists.
- **P2-7** No venv/lockfile; global environment includes unrelated packages.

---

## 5. Approved Architectural Recommendations

Full detail in `PHASE_01_ARCHITECTURE_RECOMMENDATION.md`. Summary of what Phase 2 should
follow:

1. **Modular monolith** — one FastAPI backend, one Next.js frontend later. No microservices.
2. **Add `services/`** — all business logic lives here; routers stay thin. Add
   `repositories/` only if a query genuinely needs sharing.
3. **Add `ai/`** with an `AiProvider` protocol, `MockProvider` (default, offline,
   deterministic), `GeminiProvider`, `GroqProvider`, structured Pydantic outputs, a
   provider chain with visible degradation, central limit enforcement, and per-call
   `ai_invocations` accounting.
4. **Add `ingestion/`** — validate (size/MIME/magic bytes) → hash → store under
   server-generated UUID keys → extract (PDF/DOCX/CSV/TXT) → version → generate
   `evidence_spans`. Immutable versions only.
5. **Add `analysis/`** — pure, deterministic engines for BRA (alignment), TER (temporal),
   CEP (counter-evidence), MRE (verification tasks). No I/O, no network.
6. **Alembic becomes authoritative**; `create_all()` only in tests.
7. **Tests from day one** — `tests/conftest.py` with in-memory SQLite; unit + service + API
   + mock-AI layers; mandatory isolation/RBAC negative tests; no network in tests.
8. **Preserve schema and chassis** — extend, do not replace.

---

## 6. Decisions That Must Not Be Changed Casually

| Decision | Why it is load-bearing |
|---|---|
| `mock` must be the default and fully functional offline | Core product constraint: zero-budget, no mandatory paid AI. |
| AI outputs must never be presented as proven violations | Findings are evidence dossiers; vocabulary is candidate-oriented. |
| Traceability columns on every AI-generated row (`provider_name`, `model_name`, `pipeline_version`, `prompt_version`, `*_analysis_run_id`) | Required for reproducibility and auditability (RELATRUM's premise). |
| Envelope response contract (`success`/`message`/`data`/`meta`) | Frontend contract; changing it invalidates all clients. |
| `UTCDateTime` ISO-8601 text storage | Sorting/portability guarantees; changing it requires a migration + data rewrite. |
| UUID string primary keys | Non-guessable IDs; changing key strategy is a breaking migration. |
| Append-only `reviews` / `audit_events`; immutable `source_versions` | Historical preservation is a product requirement. |
| `CHECK(start_char < end_char)` on spans | Provenance integrity invariant. |
| Enums in `domain/enums.py` are plain `str, Enum` | Serialise directly to API + DB; do not convert to ints. |
| SQLite for development | Constraint-driven; Postgres is a later, optional deployment choice. |
| Alembic is the migration authority | Prevents schema drift once multiple sessions work on the repo. |

---

## 7. Relevant Files For Phase 2 (in the intended order of work)

**Fix first (blockers):**
1. `backend/app/models/base.py` — add the two ORM imports (P0-1).
2. `backend/app/core/permissions.py` — header-based auth (P1-1) and RBAC policy (P1-4).
3. `backend/app/config.py` — JWT secret hardening (P1-2).
4. `backend/app/models/workspace.py` — least-privilege default (P1-3).
5. new: `.gitignore`, `backend/alembic.ini`, `backend/alembic/env.py`, initial revision.

**Then build (new modules):**
6. `backend/app/api/v1/auth.py` + `backend/app/services/auth_service.py` — first real feature.
7. `backend/app/services/` — one service per bounded context (§3 of the recommendation doc).
8. `backend/app/api/v1/*` — feature routers registered in `backend/app/api/v1/router.py`.
9. `backend/app/ai/` — provider protocol + `MockProvider` first.
10. `backend/app/ingestion/` — after models are proven to create cleanly.
11. `backend/app/analysis/` — BRA → TER → CEP → MRE, in that order.
12. `backend/tests/` — `conftest.py` + the first tests alongside the first feature.

**Read before coding:** `backend/app/models/__init__.py` (table registry),
`backend/app/domain/enums.py` (vocabulary), `backend/app/database.py` (engine/session
contract), `backend/app/core/exceptions.py` (error/envelope contract).

---

## 8. Commands For Running The Current Project

> All commands run from `c:\Users\User\Desktop\relatrum\backend` unless stated otherwise.
> Note: **the app will NOT start until P0-1 is fixed.**

```powershell
# Working directory
cd c:\Users\User\Desktop\relatrum\backend

# Verify dependencies are importable
python -c "import fastapi, sqlalchemy, pydantic, jwt; print('deps OK')"

# Reproduce the current blocker (expected to fail with NameError today)
python -c "from app import models; print('models import OK')"

# App import (succeeds today; startup still fails via create_all)
python -c "import app.main; print('app.main import OK')"

# Run the server (fails today at startup; works after P0-1)
uvicorn app.main:app --reload --port 8000
#   → docs:     http://localhost:8000/docs
#   → health:   http://localhost:8000/health/live
#   → ready:    http://localhost:8000/health/ready
#   → system:   http://localhost:8000/api/v1/system/info

# Tests (currently collects nothing)
python -m pytest -q

# Environment variables (create backend/.env from .env.example)
#   APP_ENV=development  LOG_LEVEL=INFO  DATABASE_URL=sqlite:///./relatrum.db
#   AI_PROVIDER=mock     JWT_SECRET=<generate a strong value>
```

**Health endpoint contract (already implemented):**
- `GET /health/live` → always `200`, `{success, message, data:{check,status}}`.
- `GET /health/ready` → `200` when DB engine exists and AI provider is configured or
  `mock`; otherwise `503` with `data.ai_provider = "misconfigured"`.

---

## 9. Known Blockers

| # | Blocker | Status | Impact if unresolved |
|---|---|---|---|
| B-1 | `NameError` in `models/base.py` | Open (documented, not fixed — audit phase) | App cannot start; no endpoint reachable; no schema creatable |
| B-2 | No version control | Open | Any work is unrecoverable; no diff/review history |
| B-3 | No Alembic config / initial revision | Open | Schema cannot evolve safely |
| B-4 | No test suite | Open | Regressions invisible; fixes unverifiable |
| B-5 | Auth dependency reads query param, not header | Open | Insecure/incorrect auth once routes exist |
| B-6 | No service/route layer for any domain resource | Open | No product functionality beyond health/system |
| B-7 | No `.env` file; insecure default JWT secret in effect | Open | Unsafe signing key if deployed as-is |
| B-8 | No frontend | Open (expected) | No user interface |

None of these are ambiguous or externally blocked — each has a defined fix.

---

## 10. Phase Acceptance & Confirmation

- **Phase 1 objective achieved:** the repository was inspected exhaustively; structure,
  technologies, implementation, dependencies, configuration, architecture, database, AI
  posture, security, and testing were assessed using both static inspection and executed
  commands. Findings are evidence-backed and non-fabricated.
- **Phase 1 acceptance criteria met:** YES.
  - Repository structure documented (§2 of the audit).
  - Technology inventory documented (§3).
  - Existing functionality classified (§4).
  - Dependency assessment documented (§5).
  - Architecture, database, and AI assessments documented (§6–§8).
  - Security assessment with severity/location/explanation/remediation documented (§9).
  - Testing audit with actual execution results documented (§10 — `no tests collected`).
  - Technical debt, missing capabilities, recommendations, and risks documented (§11–§14).
  - All three required deliverables created.
- **Implementation restrictions honoured:** no frontend, no dashboards, no AI workflows, no
  complete schema, no backend replacement, no dependency upgrades, no model downloads, no
  infrastructure additions, no deletion of existing code, no rewrite of working files. The
  only files created are the three audit documents in `docs/audit/`.
- **Unresolved blockers:** B-1 … B-8 above. B-1 is a one-line import fix; B-2/B-3/B-4 are
  setup actions; B-5 is a small code fix; B-6/B-8 are the intended Phase 2 build scope.
- **Can Phase 2 begin safely?** **YES — provided Phase 2 starts by clearing B-1 … B-3**
  (make it run, put it under version control, wire Alembic). After those, the existing
  chassis and schema are a sound foundation for building features.

---

**Explicit confirmation: PHASE 1 IS COMPLETE.**
No work has been carried into Phase 2, and Phase 2 has not been started.

*End of handoff.*
