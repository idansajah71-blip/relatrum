# RELATRUM — Phase 01 Repository Audit

**Document:** `docs/audit/PHASE_01_REPOSITORY_AUDIT.md`
**Phase:** 01 — Repository Reconnaissance & Technical Audit
**Date of audit:** 2026-10-31
**Auditor role:** Principal Software Architect / Senior Backend Engineer / Technical Auditor
**Audit method:** Static inspection of committed source + empirical execution tests (import, collection, engine init)

> This audit reports what was **observed and executed**, not what is assumed. Every
> "functional" / "broken" classification below is backed by either a file read or a
> command whose actual output is reproduced in §11.

---

## 1. Executive Summary

RELATRUM is currently a **backend-only, early-skeleton project with no version control**.
It contains a well-considered **domain model and infrastructure scaffold**, but the
application **cannot start**. A single missing import in `app/models/base.py` raises
`NameError` at import time, which cascades through `app.models` and therefore through
`create_all()`, the startup lifespan, `app.core.permissions`, and every model-dependent
module.

There is **no frontend, no tests, no Alembic migrations, no service/AI layer, no
authentication routes, and no business logic**. What exists is a high-quality
*chassis*: configuration, logging, error envelope, security primitives, database
configuration, enumerations, and a comprehensive ORM schema whose entities already
anticipate RELATRUM's four core mechanisms (BRA, TER, CEP, MRE).

**Headline verdict:** the schema and infrastructure direction are genuinely suitable for
RELATRUM and should be preserved. The immediate blocker is trivial to fix but currently
makes the entire product non-runnable. Phase 2 can proceed safely **after** that fix.

| Dimension | State | Note |
|---|---|---|
| Repository exists | Yes | Single `backend/` tree, no VCS |
| Application runs | **No** | Blocked by `NameError` in `models/base.py` |
| Backend framework | FastAPI | Skeleton only, 3 endpoints (2 health + 1 system) |
| Database schema | Substantial | 19 tables defined, not creatable due to blocker |
| Migrations | **None** | Alembic is a declared dependency but not configured |
| Frontend | **None** | Not started |
| Tests | **None** | `pytest` collects 0 tests |
| AI layer | **None** | Config keys only; no provider abstraction |
| Domain logic (BRA/TER/CEP/MRE) | **None** | Represented in schema/enums only |
| Documentation | None (before this phase) | No README, no ADRs |

---

## 2. Repository Structure

```
relatrum/
└── backend/
    ├── .env.example
    ├── requirements.txt
    └── app/
        ├── __init__.py
        ├── config.py                  # pydantic-settings Settings + validation
        ├── database.py                # engine, session, UTCDateTime, Base
        ├── main.py                    # FastAPI app, lifespan, CORS, health
        ├── api/
        │   └── v1/
        │       ├── router.py          # router aggregation
        │       └── system.py          # GET /api/v1/system/info
        ├── core/
        │   ├── exceptions.py          # ApiError hierarchy + envelope handlers
        │   ├── logging.py             # request-id structured logging
        │   ├── permissions.py         # auth dependency + workspace RBAC  [BROKEN IMPORT]
        │   └── security.py            # PBKDF2 hashing + JWT
        ├── domain/
        │   └── enums.py               # 25 domain enumerations
        ├── models/                    # 19 ORM tables  [BROKEN IMPORT CHAIN]
        │   ├── __init__.py            # registry (imports every model)
        │   ├── base.py                # UuidPkMixin, TimestampMixin  [CRITICAL]
        │   ├── user.py
        │   ├── workspace.py
        │   ├── case.py
        │   ├── source.py
        │   ├── evidence.py
        │   ├── statement.py
        │   ├── alignment.py
        │   ├── finding.py
        │   ├── verification.py
        │   ├── review.py
        │   ├── analysis_run.py
        │   └── audit.py
        └── schemas/
            └── common.py              # Envelope, PaginatedEnvelope, PaginationParams
```

### Absent (verified by enumeration)

| Expected area | Status |
|---|---|
| `frontend/` (Next.js) | Not present |
| `backend/tests/` | Not present |
| `backend/alembic/` + `alembic.ini` | Not present |
| `docs/` | Not present before this phase |
| `README.md`, `LICENSE`, `CONTRIBUTING.md` | Not present |
| `.gitignore` | Not present |
| `.git/` (version control) | **Not present** — `git status` → `fatal: not a git repository` |
| `pyproject.toml` / `setup.cfg` / lockfile | Not present |
| `scripts/` | Not present |
| `Dockerfile` / CI config | Not present |
| `storage/` runtime directory | Not present (referenced by config only) |
| Any `*.db` / `*.sqlite` file | Not present (no DB has ever been created) |

**Note:** Generated artifacts (e.g. `__pycache__`) are intentionally omitted. No virtual
environment exists inside the repository; all packages are installed into the machine's
global Python 3.12 site-packages.

---

## 3. Technology Inventory

| Technology | Version (installed) | Where used |
|---|---|---|
| Python | 3.12.4 | Entire backend |
| FastAPI | 0.141.1 | `app/main.py`, `app/api/v1/*` |
| Starlette (transitive) | 1.6.0 | Underlying ASGI framework |
| Uvicorn | 0.52.1 | ASGI server (declared, not scripted) |
| Pydantic | 2.13.4 | Schemas, settings, error body |
| pydantic-settings | 2.15.0 | `app/config.py` (12-factor config) |
| SQLAlchemy | 2.1.6 | `app/database.py`, all `app/models/*` |
| Alembic | 1.13.1 | **Declared in requirements only — not configured or used** |
| PyJWT | 2.13.0 | `app/core/security.py` JWT encode/decode |
| python-multipart | 0.0.32 | Declared for future file uploads (unused) |
| httpx | 0.28.1 | Declared for future AI HTTP calls (unused) |
| PyMuPDF (`pymupdf`) | 2.0 | Declared for future PDF extraction (unused) |
| python-docx | 1.2.0 | Declared for future DOCX extraction (unused) |
| scikit-learn | 1.9.0 | Declared for future TF-IDF/similarity (unused) |
| RapidFuzz | 3.14.6 | Declared for future fuzzy matching (unused) |
| pytest | 9.1.1 | Declared; **no tests exist** |
| pytest-asyncio | 1.4.0 | Declared; unused |
| SQLite | stdlib (3.12) | Target database via `sqlite:///./relatrum.db` |
| hashlib/hmac/secrets | stdlib | PBKDF2-HMAC-SHA256 password hashing |
| Node.js / npm | **Not used** | No `package.json`, no frontend |
| TypeScript / Next.js / Tailwind | **Not used** | Not present |

### Database technologies
- **SQLite** only, configured in `app/database.py` with `PRAGMA foreign_keys=ON`,
  `journal_mode=WAL`, `busy_timeout=5000`, `synchronous=NORMAL`.
- A custom `UTCDateTime` `TypeDecorator` stores timezone-aware UTC datetimes as ISO-8601
  **text**, explicitly to keep them sortable and portable to PostgreSQL later.

### API communication
- REST/JSON with a uniform response envelope (`app/schemas/common.py`,
  `app/core/exceptions.py`). No GraphQL, no RPC, no websockets. An `X-Request-ID`
  tracing header is echoed on every response.

### Authentication systems
- **JWT (HS256)** bearer tokens + **PBKDF2-HMAC-SHA256** password hashing
  (120,000 iterations, per-password random salt, `hmac.compare_digest`).
- Workspace RBAC scaffolding (`viewer < reviewer < editor < owner`) exists but is
  **not wired to any endpoint**, and the auth dependency is **defective** (see §9).

### AI integrations
- **None implemented.** `app/config.py` exposes `ai_provider` (`mock|gemini|groq`),
  `gemini_api_key`, `gemini_model`, `groq_api_key`, `groq_model`, timeouts, retry limits,
  and an `llm_max_calls_per_analysis` cap, but no provider code, no client, no prompt
  layer, and no `MockProvider` exist.

### ML / file-processing libraries
- Declared (`scikit-learn`, `PyMuPDF`, `python-docx`, `RapidFuzz`) but **not imported by
  any application module**. These are pre-provisioned for Phase 2+.

### Build tools / package managers
- **pip** only. `requirements.txt` with loose lower bounds. No lockfile, no `pyproject.toml`,
  no build system, no bundler/transpiler (no frontend).

---

## 4. Existing Functionality

### 4.1 Component classification

| # | Component | File | Classification |
|---|---|---|---|
| 1 | Settings & validation | `app/config.py` | **Implemented and functional** (imports & validates) |
| 2 | Structured logging + request-id | `app/core/logging.py` | **Implemented and functional** |
| 3 | Error hierarchy + envelope | `app/core/exceptions.py` | **Implemented and functional** (1 deprecation warning) |
| 4 | Password hashing + JWT | `app/core/security.py` | **Implemented and functional** (not wired to routes) |
| 5 | DB engine/session/UTC type | `app/database.py` | **Implemented and functional** (engine builds) |
| 6 | ORM models (19 tables) | `app/models/*` | **Present but broken** — `NameError` blocks import |
| 7 | Domain enumerations | `app/domain/enums.py` | **Implemented and functional** |
| 8 | RBAC / auth dependencies | `app/core/permissions.py` | **Present but broken** (import fails) + logic defect |
| 9 | Response schemas | `app/schemas/common.py` | Implemented and functional |
| 10 | App factory / lifespan | `app/main.py` | **Implemented but incomplete** — import OK, startup crashes |
| 11 | Health endpoints | `app/main.py` | Implemented but unreachable (startup fails) |
| 12 | `GET /api/v1/system/info` | `app/api/v1/system.py` | Implemented but unreachable |
| 13 | Auth routes (register/login/refresh) | — | **Not present** |
| 14 | Workspace/Case/Source CRUD routes | — | **Not present** |
| 15 | Statement / Alignment / Finding routes | — | **Not present** |
| 16 | Review & Verification workflows | — | **Not present** |
| 17 | Audit-event writer | — | **Not present** (model only) |
| 18 | File upload & extraction pipeline | — | **Not present** |
| 19 | AI provider abstraction (mock/gemini/groq) | — | **Not present** |
| 20 | Analysis pipeline (BRA/TER/CEP/MRE) | — | **Not present** |
| 21 | Alembic migrations | — | **Planned but not implemented** |
| 22 | Tests | — | **Not present** |
| 23 | Frontend | — | **Not present** |
| 24 | Seed/demo data scripts | — | **Not present** |

### 4.2 Existing API routes (complete inventory)

| Method | Path | Handler | Reachable? |
|---|---|---|---|
| GET | `/health/live` | `app/main.py::health_live` | No — app startup fails |
| GET | `/health/ready` | `app/main.py::health_ready` | No — app startup fails |
| GET | `/api/v1/system/info` | `app/api/v1/system.py::system_info` | No — app startup fails |
| GET | `/docs`, `/redoc`, `/openapi.json` | FastAPI built-ins | No — app startup fails |

That is the entire route surface. No authentication, no resource, and no analysis
endpoints exist.

### 4.3 Existing database models (19 tables)

| Table | Model file | Purpose |
|---|---|---|
| `users` | `user.py` | Accounts (email, PBKDF2 hash, `is_active`) |
| `workspaces` | `workspace.py` | Multi-tenant container |
| `workspace_members` | `workspace.py` | Membership + role (unique on workspace+user) |
| `cases` | `case.py` | Investigation case, observation window, status |
| `sources` | `source.py` | Provenance metadata, sha256, sensitivity, ingestion status |
| `source_versions` | `source.py` | Immutable extracted text versions (history preservation) |
| `evidence_spans` | `evidence.py` | Char-offset quotes; `CHECK(start_char < end_char)` |
| `statements` | `statement.py` | Atomic statements + subject/actor/action/object/modality/temporal |
| `statement_evidence` | `statement.py` | M:N statement ↔ span with `evidence_role` |
| `statement_relations` | `statement.py` | Typed relations between statements (supports/contradicts/...) |
| `alignments` | `alignment.py` | Requirement↔observation candidates + similarity scores |
| `findings` | `finding.py` | Evidence dossiers, quality profile, supersession chain |
| `finding_evidence` | `finding.py` | M:N finding ↔ span |
| `verification_tasks` | `verification.py` | MRE questions, hypotheses A/B, status |
| `verification_responses` | `verification.py` | Human answers to verification tasks |
| `reviews` | `review.py` | Append-only human review decisions |
| `analysis_runs` | `analysis_run.py` | Reproducibility: pipeline/prompt/provider versions, manifest hash |
| `ai_invocations` | `analysis_run.py` | Token/cost/latency/error accounting per AI call |
| `audit_events` | `audit.py` | Append-only audit trail |

This schema is the strongest asset in the repository. It anticipates all four RELATRUM
mechanisms:

- **BRA** → `alignments` (requirement ↔ observation candidates with similarity + type).
- **TER** → temporal columns across `statements`, `cases`, `sources`, `alignments`
  (`temporal_compatibility`, `temporal_detail`).
- **CEP** → `SourceType.counter_evidence`, `EvidenceRole.counter_context`,
  `EvidencePolarity`, `StatementRelation.contradicts`.
- **MRE** → `verification_tasks` / `verification_responses` with hypotheses and
  decision relevance.

### 4.4 Existing business logic
None. There is no service layer, no repository layer, and no domain logic beyond enum
definitions. Persistence is exposed only through the `get_db` dependency.

---

## 5. Dependency Assessment

### 5.1 Manifest vs environment

`requirements.txt`:

```
fastapi>=0.115,<1.0            pydantic>=2.7          sqlalchemy>=2.0.30,<3.0
uvicorn[standard]>=0.30        pydantic-settings>=2.2 alembic>=1.13
python-multipart>=0.0.9        httpx>=0.27            PyJWT>=2.8
PyMuPDF>=1.24                  python-docx>=1.1       scikit-learn>=1.4
rapidfuzz>=3.6                 pytest>=8.0            pytest-asyncio>=0.23
```

All declared dependencies are **installed and satisfied**. No version conflicts were
observed at import time.

### 5.2 Findings

| Finding | Severity | Detail | Recommendation (report only — do not apply this phase) |
|---|---|---|---|
| **Unused-but-declared dependencies** | Low | `alembic`, `python-multipart`, `httpx`, `PyMuPDF`, `python-docx`, `scikit-learn`, `rapidfuzz` are installed but imported by **no** module. | Keep for Phase 2, but they inflate install size now. `alembic` is the most urgent to *actually wire up*. |
| **No lockfile / no pinning** | Medium | Only lower bounds, `>=`. A future `pip install` may resolve to untested versions. Reproducibility risk. | Add a `requirements.lock` (e.g. `pip freeze`) or a `constraints.txt`; or migrate to `pyproject.toml` + `uv`/`pip-tools` in Phase 2. |
| **No virtual environment in repo** | Medium | Packages live in the machine's global site-packages. | Create `backend/.venv` and document activation. |
| **Environment pollution** | Low | Global env contains unrelated packages (`Flask-SQLAlchemy`, `sse-starlette`, `openapi-pydantic`, `pymupdf4llm`, `pymupdf_layout`). | Isolate RELATRUM in its own venv; do not treat global package set as project truth. |
| **`fitz` import deprecated** | Low | Installed PyMuPDF is `2.0`; `import fitz` emits `FutureWarning`. | In Phase 2 use `import pymupdf`. |
| **Starlette deprecation** | Low | `HTTP_422_UNPROCESSABLE_ENTITY` deprecated in Starlette 1.6.0. | Migrate to `HTTP_422_UNPROCESSABLE_CONTENT` (see §11 evidence). |
| **Heavy ML dependency installed early** | Low | `scikit-learn` + `scipy` + `numpy` + `joblib` add significant install weight before any ML code exists. | Acceptable, but consider lazy/deferred adoption if disk-constrained. |
| **`pytest-asyncio` v1.4.0** | Low | Major-version bump changes default loop/`asyncio_mode` behaviour; requirements only demand `>=0.23`, which spans incompatible majors. | Pin explicitly and set `asyncio_mode` in Phase 2's pytest config. |
| **Missing essentials for Phase 2** | Low | No `email-validator` (needed if `EmailStr` is used), no formatting/linting toolchain (`ruff`/`black`/`mypy`). | Add when auth/schemas are implemented. |

No conflicting or duplicate libraries were detected in the resolution. `Flask-SQLAlchemy`
is unrelated to this project and is **not** a project dependency.

---

## 6. Architecture Assessment

### 6.1 Backend architecture

| Concern | Current state | Assessment |
|---|---|---|
| Route/handler separation | One router module aggregated in `api/v1/router.py` | Adequate start, but only one feature module exists |
| Service layer | **Absent** | Must be introduced in Phase 2 |
| Repository layer | **Absent** | Raw `Session` via `get_db` only |
| Domain entities | Enums only (`domain/enums.py`) | No domain services / value objects yet |
| Dependency injection | `Depends(get_db)` | Present and idiomatic |
| Error handling | `ApiError` hierarchy + global handlers + envelope | **Good** — consistent, no stack leakage in production |
| Logging | Root handler with request-id `ContextVar` filter | **Good** — correlatable, third-party noise suppressed |
| Configuration | `pydantic-settings` with `model_validator` fail-fast rules | **Good** — validates provider config, JWT secret in prod, positive limits |

Overall the backend skeleton follows sound conventions (12-factor config, single
error-envelope contract, tracing). The missing pieces are the **service and repository
layers** and any **feature routers**.

### 6.2 Database architecture

| Concern | Assessment |
|---|---|
| Data model quality | **High.** Normalised, explicit FKs, `UniqueConstraint`s, `CheckConstraint` on spans, typed enums mirrored as strings. |
| Relationship integrity | Good: `ondelete="CASCADE"` on parent-owned children, `SET NULL` for actor references, SQLite FK enforcement actually enabled via PRAGMA. |
| Foreign-key usage | Consistent and deliberate. |
| Indexing | Mostly good, but **duplicate indexes** exist where a column is both `index=True` and repeated in `__table_args__` (e.g. `evidence_spans.source_version_id`, `statement_evidence.statement_id`, both columns of `statement_relations`). Wasted writes/space. |
| Migration strategy | **Absent.** Alembic declared but no `alembic.ini`, no `env.py`, no versions. `create_all()` is used as a dev convenience. This must be fixed **before** the schema evolves. |
| Transaction handling | `get_db` commits on success / rolls back on exception / always closes. Correct for request scope. |
| Historical preservation | Strong: `SourceVersion` immutable versions + `source_versions` content hashes + `reviews`/`audit_events` append-only + `findings.supersedes_finding_id`. |
| Multi-workspace isolation | Schema supports it (`workspace_id` on `sources`, `cases`→workspace, `audit_events`). Enforcement is only scaffolded in `permissions.py` and is **not applied to any route**. |

### 6.3 AI architecture readiness

| Requirement | Supported today? | Evidence |
|---|---|---|
| Multiple providers | Config-only | `ai_provider ∈ {mock,gemini,groq}` |
| Structured outputs | No | No schema/prompt layer |
| Pydantic validation of AI output | No | Not implemented |
| Provider fallbacks | No | Not implemented |
| Mock inference | No | `mock` is a config value, not a class |
| Request limits | Config-only | `llm_max_calls_per_analysis` |
| Token tracking | **Schema-ready** | `ai_invocations.input/output_token_count`, `estimated_cost` |
| AI error handling | Partial | `AiProviderError` exists; no provider raises it |
| Reproducible runs | **Schema-ready** | `analysis_runs.pipeline_version`, `prompt_version`, `input_manifest_hash`, `provider_name`, `model_name` |

Verdict: the *accounting and reproducibility schema* is excellent; the *provider
abstraction itself* does not exist yet.

### 6.4 Scalability and maintainability risks

1. **SQLite write contention.** WAL helps readers, but a single writer plus CPU-bound
   analysis (scikit-learn) can block. Analysis must run outside the request/event loop
   (threadpool or background worker).
2. **Duplicate indexes** raise write cost as `statements`/`evidence_spans` grow.
3. **No duplicate-prevention on `alignments`.** Re-running analysis may insert duplicate
   candidate rows; a uniqueness/“supersede” strategy is required.
4. **JSON columns** (`extraction_metadata`, `quality_profile`, `temporal_detail`, etc.) are
   convenient but unqueryable without care under SQLite. Acceptable for v1.
5. **Missing route/service layers** mean there is no established pattern yet — this is
   the right moment to fix module boundaries before code volume grows.
6. **No VCS** is a process-level maintainability risk larger than any code issue.
7. **Blocking I/O in async handlers.** If analysis/HTTP calls are mounted in `async def`
   routes without offloading, the event loop stalls. Design rule for Phase 2.

---

## 7. Database Assessment

Covered in §4.3 and §6.2. Additional notes:

- **No database file exists** on disk (`*.db` / `*.sqlite` search returned nothing), so
  `create_all()` has never successfully run — consistent with the import blocker.
- `UTCDateTime` text-storage of ISO-8601 UTC is a deliberate, portable choice; it keeps
  datetimes lexicographically sortable and avoids SQLite's naive-datetime pitfalls.
  Trade-off: no native DB-level date arithmetic/indexes. Acceptable at this scale.
- `fk_integrity_check()` helper exists (`PRAGMA foreign_key_check`) but is unused.
- A few `mapped_column(...)` attributes omit `Mapped[...]` annotations
  (`reviews.created_at`, `verification_responses.submitted_at`, several `created_at`
  fields) and instead use `Mapped[object]`. Functionally tolerable in SQLAlchemy 2.x,
  but inconsistent typing. Cosmetic/tech-debt only.
- `Case.created_by` is annotated `Mapped[str]` while declared `nullable=True` — the
  annotation should be `str | None`. Type-accuracy debt.

---

## 8. AI Integration Assessment

- **Provider abstraction:** absent. No `providers/` package, no base protocol, no
  `MockProvider`, no Gemini/Groq clients.
- **Prompt management:** absent. `prompt_version` config exists but no prompt registry.
- **Structured output & validation:** absent. No response models for extraction,
  alignment classification, or verification generation.
- **Fallback & retry:** only `ai_retry_limit` / `ai_timeout_seconds` config; no logic.
- **Cost/token tracking:** schema present (`ai_invocations`); no writer.
- **Graceful operation without API keys:** partially enforced by `Settings.validate_settings`
  (refuses `gemini`/`groq` without a key, and defaults to `mock`). The `MockProvider`
  that would make "no key" genuinely useful **does not exist yet**.

Conclusion: RELATRUM's AI posture is currently *declarative*. Phase 2 must build the
provider protocol, the `MockProvider` (deterministic, offline), and the structured-output
validation layer before any LLM call is made.

---

## 9. Security Assessment

No real secrets were found. `.env.example` contains placeholders only, and **no `.env`
file exists**. Values are never reproduced in this report.

| ID | Severity | Location | Component | Explanation | Remediation |
|---|---|---|---|---|---|
| SEC-01 | **High** | `backend/app/core/permissions.py:19` | `auth_dependency` | `authorization: str \| None = None` is **not** declared as a header/`Depends`, so FastAPI treats it as a **query parameter**. The `Authorization` header is ignored; a caller can supply `?authorization=Bearer <token>`. Tokens then land in URLs, access logs, proxies, and browser history. | Declare `authorization: str \| None = Header(default=None)` (import `Header` from `fastapi`); read only the header. |
| SEC-02 | **High** | `backend/app/models/base.py:11` | `UuidPkMixin` | Missing `Mapped`/`mapped_column` imports raise `NameError`, so the app **cannot start**. Not a vulnerability per se, but it blocks every security control from being exercised and forces improvised run paths. | Add `from sqlalchemy.orm import Mapped, mapped_column`. |
| SEC-03 | **Medium** | `backend/app/config.py:21` + `backend/.env.example:6` | `Settings.jwt_secret` | Insecure default `dev-insecure-secret-change-me`; the production guard only triggers when `app_env == "production"`. With no `.env` present, this default **is** the effective signing key. | Fail fast unless `APP_ENV=testing`, or generate/require a secret on first run. Never ship a usable default. |
| SEC-04 | **Medium** | `backend/app/models/workspace.py:30` | `WorkspaceMember.role` | Defaults to `"owner"` — the **highest** privilege. Any code path that creates a membership without an explicit role grants owner rights. | Require an explicit role; default to least privilege (`viewer`). |
| SEC-05 | **Medium** | `backend/app/core/permissions.py:49-53` | `require_workspace_member` | Both the "not a member" and "workspace missing" branches raise the identical `NotFoundError`; the commented intent to distinguish 403 vs 404 is dead code. The hide-existence approach is defensible, but the current implementation is unintentional and untested. | Decide the policy explicitly (recommend: 404 for non-members to avoid existence leakage), delete the dead branch, and test it. |
| SEC-06 | **Low** | `backend/app/core/exceptions.py:102` | `unhandled_error_handler` | Returns the raw exception string when `app_env != "production"`. Safe in dev; risky if a non-production env is ever exposed. | Keep, but ensure deployments always set `APP_ENV=production`. |
| SEC-07 | **Low** | `backend/app/main.py:52-56` | CORS | `allow_credentials=True` with `allow_methods=["*"]`/`allow_headers=["*"]`. Origins are env-restricted (default localhost), so currently low risk. | Keep origins explicit; never widen to `*` while credentials are allowed. |
| SEC-08 | **Low (future)** | `app/config.py` (`max_upload_mb`, `storage_dir`) | Upload pipeline (not built) | No upload code exists, so path-traversal / unsafe-file risks are **unmitigated but not yet exposed**. | When building ingestion: sanitise/ignoring user filenames, store under server-generated UUID keys, validate MIME + magic bytes, enforce size/page caps, never concatenate user input into filesystem paths. |
| SEC-09 | **Low (future)** | `app/api/v1/*` | Cross-workspace access | Isolation depends on service-layer checks that no route currently applies. | Every resource route must resolve through `resolve_case` / `require_workspace_member`; add tests that assert cross-workspace access is denied. |
| SEC-10 | **Info** | `app/core/exceptions.py:51-53` | `RateLimitedError` | Defined but no rate limiting anywhere. | Add throttling for auth and AI endpoints in Phase 2. |
| SEC-11 | **Info** | `app/core/security.py:16-30` | Password hashing | PBKDF2-HMAC-SHA256, 120k iterations, per-password salt, constant-time compare — **reasonable**. | Consider a higher iteration count or Argon2id once an auth flow exists. |

**Positive security observations:** SQLAlchemy ORM usage (no raw string-built SQL in
application code beyond two parameter-free `PRAGMA`/`SELECT COUNT(*)` statements) removes
the classic SQL-injection surface; the error envelope avoids leaking traces in production;
`AuditEvent` is designed for traceability.

**Actions taken this phase:** none. No security-sensitive component was modified. Every
finding above is documented only, per the Phase 1 restriction.

---

## 10. Testing Assessment

| Test category | Present? |
|---|---|
| Unit tests | **No** |
| Integration tests | **No** |
| API tests | **No** |
| Database tests | **No** |
| AI tests | **No** |
| Evaluation datasets | **No** |
| Fixtures / conftest | **No** |
| Test configuration (pytest.ini / pyproject) | **No** |

**How tests are meant to run:** `pytest` from `backend/` (dependencies installed).
**Actual result:** `python -m pytest --collect-only -q` → `no tests collected` (exit code 5).
There is no test suite to pass or fail.

**Untested critical workflows (all of them):** config validation, JWT issue/verify,
password hashing round-trip, RBAC, workspace isolation, model creation, health readiness,
and (future) ingestion, alignment, finding, verification, and AI-provider behaviour.

No coverage percentage is reported because none can be truthfully computed.

---

## 11. Technical Debt (ranked)

1. **T-01 (Blocker):** `models/base.py` missing `Mapped`/`mapped_column` imports → whole app fails.
2. **T-02 (High):** No version control (`git` absent) and no `.gitignore`.
3. **T-03 (High):** No Alembic configuration despite being a declared dependency; schema
   changes will be unmanaged.
4. **T-04 (High):** No test infrastructure at all.
5. **T-05 (Medium):** No service or repository layer; no route layer for any domain resource.
6. **T-06 (Medium):** `auth_dependency` reads the token from a query parameter (SEC-01).
7. **T-07 (Medium):** No lockfile / venv; environment not reproducible.
8. **T-08 (Low):** Duplicate indexes across several tables.
9. **T-09 (Low):** `WorkspaceMember.role` defaults to `owner` (SEC-04).
10. **T-10 (Low):** Deprecated `HTTP_422_UNPROCESSABLE_ENTITY`; deprecated `fitz` import usage pending.
11. **T-11 (Low):** Inconsistent `Mapped[...]` typing (`Mapped[object]`, non-optional
    annotations on nullable columns); `Any` imported but unused in `base.py`;
    `UTCDateTime.impl = type_engine = None` is a confusing construct.
12. **T-12 (Low):** No `README`, no ADRs, no run scripts.

---

## 12. Missing Capabilities

- Frontend (Next.js / TypeScript / Tailwind / React / `@xyflow/react` / Recharts / Lucide).
- Authentication routes (register, login, token refresh, current-user).
- CRUD + workflow routes for workspaces, cases, sources, statements, alignments,
  findings, reviews, verification tasks, and analysis runs.
- Ingestion pipeline (upload → validate → store → extract for PDF/DOCX/CSV/TXT → spans).
- Statement extraction, normalisation, and temporal parsing.
- Alignment engine (TF-IDF / cosine, RapidFuzz, temporal compatibility).
- Finding synthesis and prioritisation; counter-evidence preservation logic.
- MRE verification-task generation.
- AI provider abstraction with `MockProvider`, Gemini, and Groq implementations,
  structured outputs, retries, fallbacks, and call caps.
- Reproducible analysis-run orchestration and `ai_invocations` accounting writer.
- Audit-event emission.
- Pagination/filtering/search conventions (only `PaginationParams` exists).
- Offline/dev seeding and demo dataset.
- CI, linting, type-checking, packaging, deployment config.

---

## 13. Recommended Improvements (Phase 2+, prioritised)

**P0 — restore a runnable baseline**
1. Add the two missing imports in `models/base.py` (fixes T-01 / SEC-02).
2. Initialise the database via Alembic (`alembic init`, autogenerate initial revision)
   and stop relying on `create_all()` outside tests.
3. Initialise version control and add `.gitignore` (`__pycache__/`, `*.db`, `.env`,
   `.venv/`, `storage/`).
4. Add a project virtualenv and a lockfile; adopt `pyproject.toml`.

**P1 — make the skeleton trustworthy**
5. Add a `tests/` suite with `conftest.py` (in-memory SQLite), covering config
   validation, JWT round-trip, password round-trip, model creation, health endpoints,
   and RBAC/isolation negative cases.
6. Fix `auth_dependency` to read the `Authorization` header (SEC-01).
7. Harden defaults: no usable `jwt_secret` default (SEC-03); least-privilege membership
   default (SEC-04); make the RBAC 403/404 policy explicit and tested (SEC-05).
8. Introduce a `services/` (and optional `repositories/`) layer and per-domain routers so
   business logic never lives in handlers.

**P2 — domain capability**
9. Build the AI provider protocol + `MockProvider` first; then Gemini/Groq behind the
   same interface, with structured Pydantic outputs and `ai_invocations` accounting.
10. Build ingestion (validation, hashing, storage, extraction) with the SEC-08 controls.
11. Build alignment → finding → verification pipelines as pure, testable functions that
    are fully deterministic in `mock` mode.

**P3 — hygiene**
12. Remove duplicate indexes (T-08); normalise `Mapped[...]` typing (T-11); replace
    deprecated constants; switch to `import pymupdf`.
13. Add `ruff`/`black`/`mypy`, then CI.

---

## 14. Known Risks

| Risk | Likelihood | Impact | Note |
|---|---|---|---|
| Work lost due to no version control | High | High | T-02; nothing is committed anywhere |
| App remains unrunnable if the import fix is skipped | Certain today | High | T-01 |
| Schema drift because Alembic is unconfigured | High | Medium | T-03 |
| Regressions invisible without tests | High | Medium/High | T-04 |
| Token leakage via query-string auth | Medium | High | SEC-01 |
| Reproducibility failure on another machine | Medium | Medium | T-07 (no venv/lockfile) |
| SQLite write contention / blocked event loop at scale | Medium | Medium | §6.4 |
| Silent cross-workspace access once routes exist | Medium | High | SEC-09 — must be tested |
| Insecure JWT signing key in any real deployment | Medium | High | SEC-03 |
| Duplicate alignments on re-analysis | Medium | Low/Medium | §6.4 |

---

*End of repository audit.*
