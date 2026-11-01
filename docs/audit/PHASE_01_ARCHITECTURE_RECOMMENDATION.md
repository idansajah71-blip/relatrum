# RELATRUM — Phase 01 Architecture Recommendation

**Document:** `docs/audit/PHASE_01_ARCHITECTURE_RECOMMENDATION.md`
**Phase:** 01 — Repository Reconnaissance & Technical Audit
**Date:** 2026-10-31
**Status:** Recommendation only — **nothing in this document is implemented during Phase 1**

This recommendation is derived from the *actual* repository state documented in
`PHASE_01_REPOSITORY_AUDIT.md`. It preserves the existing backend chassis and extends it.
It does **not** propose replacing working technology.

---

## 1. Recommended Architecture

**Shape: modular monolith.** A single deployable FastAPI backend with strict internal
module boundaries, plus a separately-built Next.js frontend. No microservices, no message
broker, no container orchestration, no paid infrastructure. This matches the zero-budget,
low-spec-laptop, CPU-first constraint.

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend (Next.js + TypeScript strict + Tailwind)               │
│  later phase — consumes /api/v1 only                             │
└───────────────────────────────┬──────────────────────────────────┘
                                │ REST/JSON (envelope contract)
┌───────────────────────────────▼──────────────────────────────────┐
│  Backend — RELATRUM modular monolith (FastAPI)                   │
│                                                                  │
│  api/v1/*        routers: transport only (parse → service → env) │
│  services/*      use-cases / orchestration (the real logic)      │
│  domain/*        enums, value objects, pure rules                │
│  ai/*            provider protocol + mock/gemini/groq + prompts  │
│  ingestion/*     validate → store → extract → span               │
│  analysis/*      BRA, TER, CEP, MRE engines (pure, deterministic)│
│  models/*        SQLAlchemy ORM (persistence only)               │
│  schemas/*       Pydantic v2 request/response contracts          │
│  core/*          config, security, errors, logging, permissions  │
│  repositories/*  optional thin data-access, only if needed       │
└───────────────────────────────┬──────────────────────────────────┘
                                │
                     SQLite (WAL) + local filesystem storage
                                │
                     optional outbound: Gemini / Groq (key-gated)
```

**Dependency rule (one-way):** `api → services → domain` and `services → models/ai/ingestion/analysis`.
`models` and `domain` never import `services` or `api`. `ai` and `analysis` never import
`api`. This keeps the analysis engines unit-testable in isolation and keeps `mock` mode
fully offline.

**Deviation from the proposed target stack:** none required. The existing backend already
uses Python + FastAPI + Pydantic v2 + SQLAlchemy 2.x + SQLite, so the target stack is
**adopted as-is**. The only additions are *structural* (`services/`, `ai/`, `ingestion/`,
`analysis/`) and *operational* (Alembic wiring, tests, venv/lockfile).

---

## 2. Proposed Backend Module Boundaries

| Module | Responsibility | Must NOT do |
|---|---|---|
| `app/api/v1/<feature>.py` | HTTP shape, status codes, dependency wiring, envelope construction | Contain business rules; touch the DB directly beyond service calls |
| `app/services/<feature>_service.py` | Use-cases, transaction boundaries, authorization calls, orchestration | Build HTTP responses; import FastAPI types |
| `app/domain/` | Enums (exists), value objects, pure predicates (e.g. modality rules, temporal overlap) | Import SQLAlchemy or FastAPI |
| `app/repositories/` (optional) | Reusable queries too complex for the service | Add behaviour beyond data access |
| `app/ai/` | `AiProvider` protocol, `MockProvider`, `GeminiProvider`, `GroqProvider`, prompt registry, structured-output validation, call-cap enforcement, `ai_invocations` accounting | Decide domain outcomes; be imported by API layer |
| `app/ingestion/` | Type/size validation, hashing, storage write, text extraction (PDF/DOCX/CSV/TXT), span generation | Interpret meaning (that is `analysis/`) |
| `app/analysis/` | BRA alignment, TER temporal reasoning, CEP counter-evidence preservation, MRE verification generation | Perform I/O; make network calls (receive data, return data) |
| `app/models/` | ORM tables only | Contain business logic or queries beyond relationships |
| `app/schemas/` | Pydantic request/response models | Contain persistence logic |
| `app/core/` | Config, security, errors, logging, permissions (exists) | Contain feature logic |

**Service-layer contract sketch (illustrative, not to be implemented this phase):**

```python
# app/services/alignment_service.py  (Phase 2 sketch)
def run_alignment(db: Session, *, case_id: str, actor: User, provider_name: str) -> AnalysisRun:
    case = resolve_case(db, actor, case_id, min_role="editor")   # existing helper
    run = _start_run(db, case, provider_name)                    # AnalysisRun + versions
    candidates = analysis.bra.candidates(...)                    # pure, deterministic
    _persist_alignments(db, run, candidates)
    _finalize_run(db, run)
    return run
```

**Design rules to keep the platform honest:**
- Every AI-generated artifact is stored with `provider_name`, `model_name`,
  `pipeline_version`, `prompt_version`, and a `creator_analysis_run_id` so it is traceable.
- `mock` mode must produce a complete, deterministic result set with **no network access**,
  so the product is fully usable with zero API keys.
- Analysis engines are pure functions over already-loaded data; this makes them fast to
  test and safe to re-run.

---

## 3. Proposed Domain Boundaries

Bounded contexts, each owning its tables and service:

| Context | Owns | Core mechanisms |
|---|---|---|
| **Identity & Tenancy** | `users`, `workspaces`, `workspace_members` | auth, RBAC, workspace isolation |
| **Case Management** | `cases` | scope, observation window, lifecycle |
| **Ingestion & Provenance** | `sources`, `source_versions`, `evidence_spans` | hashing, immutability, span provenance |
| **Statement Layer** | `statements`, `statement_evidence`, `statement_relations` | normalisation, modality, **TER** temporal fields |
| **Alignment** | `alignments` | **BRA** requirement↔observation candidates |
| **Finding & Counter-Evidence** | `findings`, `finding_evidence` | **CEP** preservation, supersession, quality profile |
| **Verification (MRE)** | `verification_tasks`, `verification_responses` | minimal resolving evidence |
| **Review & Governance** | `reviews`, `audit_events` | append-only human decisions + audit trail |
| **Analysis Execution** | `analysis_runs`, `ai_invocations` | reproducibility, cost/token accounting |

These boundaries map 1:1 onto the existing model files, confirming the schema was designed
with the right decomposition. The recommendation is to **add service modules per context**,
not to restructure the schema.

**Invariant to make explicit:** a `Finding` is a *dossier of evidence*, never a proven
violation (as the model docstring already states). Services must never emit
"violation"/"guilty" semantics; the vocabulary stays candidate-oriented
(`possible_requirement_deviation`, `insufficient_information`, …).

---

## 4. Database Architecture Direction

- **Engine:** SQLite with the already-configured PRAGMAs (FK on, WAL, busy timeout).
  Keep the `UTCDateTime` portable text storage. The schema remains PostgreSQL-portable by
  design; do **not** adopt Postgres in Phase 2.
- **Migrations:** make **Alembic authoritative** immediately.
  - Add `backend/alembic.ini` + `backend/alembic/env.py` bound to `Base.metadata` and
    importing `app.models` for full table registration.
  - Autogenerate an `initial` revision from the existing schema.
  - Restrict `create_all()` to tests only (it already exists in `database.py`).
  - Never edit a migration after it has been shared; always add a new revision.
- **Schema hardening (document, apply in Phase 2):**
  - Remove duplicate indexes (column `index=True` + matching `Index(...)`).
  - Add a uniqueness/replacement strategy for `alignments` so re-analysis does not
    accumulate duplicates (e.g. unique on
    `(case_id, requirement_statement_id, observation_statement_id, pipeline_version)`
    plus an explicit supersede on re-run).
  - Add `CHECK` constraints mirroring the enum domains once enums stabilise.
- **Historical preservation:** already strong (`source_versions`, append-only `reviews`/
  `audit_events`, `findings.supersedes_finding_id`). Continue the pattern: never mutate
  extracted content in place; add a new `SourceVersion`.
- **Multi-workspace isolation:** every root entity carries or inherits `workspace_id`.
  Enforce it in the service layer via the existing `require_workspace_member` /
  `resolve_case` helpers — and back it with negative tests. Consider a default-scoped query
  helper so isolation is hard to forget.
- **Concurrency:** keep one `SessionLocal` per request; run analysis off the request path.

---

## 5. AI Provider Architecture Direction

Build the abstraction **before** any real LLM call:

```python
# app/ai/base.py  (Phase 2 sketch)
class AiOperation(str, Enum): ...          # already in domain.enums.AiOperationType

class AiProvider(Protocol):
    name: str
    def invoke(self, request: AiRequest) -> AiResult: ...

@dataclass
class AiRequest:
    operation: AiOperationType
    prompt_version: str
    payload: dict
    response_model: type[BaseModel]

@dataclass
class AiResult:
    output: BaseModel
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
```

- **Providers:** `MockProvider` (deterministic, offline, no key — the default),
  `GeminiProvider`, `GroqProvider`. Selected by `Settings.ai_provider`.
- **Structured outputs:** every operation declares a Pydantic `response_model`; provider
  output is validated before it reaches the domain. Validation failure is a typed error,
  never a silent fallback.
- **Fallbacks:** `ProviderChain` that tries the configured provider, then degrades to
  `MockProvider` for non-critical operations — recorded in `ai_invocations.request_status`
  so degradation is always visible, never hidden.
- **Limits:** enforce `llm_max_calls_per_analysis`, `ai_timeout_seconds`,
  `ai_retry_limit` centrally in the provider layer, not per call site.
- **Accounting:** write one `ai_invocations` row per call (tokens, cost, latency, error
  code). This is the raw material for REPRODUCIBLE analysis runs.
- **Reproducibility:** `analysis_runs.input_manifest_hash` = stable hash over the ordered
  input statement/span IDs; same inputs + same `pipeline_version` + `prompt_version` must
  yield the same result, especially in mock mode.
- **Error handling:** providers raise `AiProviderError` (already defined); the service layer
  decides whether to degrade, retry, or fail the run.
- **Graceful offline operation:** with `AI_PROVIDER=mock` and no keys, every feature must
  remain fully functional. This is a hard requirement, not a nicety.

---

## 6. Document Ingestion Direction

Pipeline: **validate → hash → store → extract → version → span**.

- **Accepted types (v1):** PDF (`pymupdf` — use the non-deprecated import), DOCX
  (`python-docx`), CSV (stdlib `csv`), TXT (stdlib). Reject everything else.
- **Validation (addresses SEC-08):** enforce `MAX_UPLOAD_MB` and `MAX_DOCUMENT_PAGES`;
  verify magic bytes, not just the client-declared MIME; ignore the client filename for
  storage.
- **Storage:** server-generated UUID keys under `settings.storage_dir` (never a path
  derived from user input); record `sha256` and `file_size` on `sources`.
- **Deduplication:** detect duplicate content via `sources.sha256` /
  `source_versions.content_sha256`; mark `IngestionStatus.duplicate` rather than
  re-ingesting.
- **Extraction:** persist text to `source_versions.extracted_text` with
  `extraction_method`, `extraction_status` (`success|partial|failed`), and
  `extraction_metadata`.
- **Spans:** produce `evidence_spans` with `start_char`/`end_char`/`exact_quote`/
  `page_number`/`section_heading` so every downstream statement is traceable to source
  text. Keep the existing `CHECK(start_char < end_char)`.
- **Immutability:** never overwrite extracted content; a re-ingest creates a new
  `SourceVersion`.
- **Cost awareness:** extraction is local and CPU-only; no AI is used for ingestion.

---

## 7. Testing Strategy

Adopt a pyramid that is cheap to run on a low-spec laptop:

| Layer | Scope | Tooling |
|---|---|---|
| Unit | Analysis engines, domain rules, temporal logic, prompt/response validation | `pytest` (pure functions, no DB) |
| Service | Use-cases against in-memory SQLite | `pytest` + fixture `Session` |
| API | Routers via `TestClient` (envelope, status codes, auth, isolation) | `pytest` + `httpx` |
| AI | `MockProvider` determinism; provider fallback; call-cap enforcement | `pytest` (no network) |
| Golden/eval | Fixed input → expected alignment/finding output for regression | JSON fixtures under `tests/datasets/` |

**Conventions:**
- `backend/tests/conftest.py` with an in-memory SQLite engine
  (`sqlite:///:memory:` or a temp file), `Base.metadata.create_all`, and a `db` + `client`
  fixture. Tests never touch the developer's real `relatrum.db`.
- Pin `pytest-asyncio` and set `asyncio_mode = "auto"` explicitly (installed 1.4.0 changed
  defaults).
- All tests run with `APP_ENV=testing` and `AI_PROVIDER=mock`; **no test may require a
  network or an API key**.
- Mandatory negative tests: cross-workspace access denied; expired/invalid JWT rejected;
  RBAC rank enforcement; upload type/size rejection.
- CI (GitHub Actions, free tier) runs `pytest` on push once the suite exists.

No coverage percentage is claimed; coverage tooling (`pytest-cov`) is installed but there
is nothing to measure yet.

---

## 8. Infrastructure Strategy

- **Local-first.** Single machine, single process, SQLite file + local `storage/` directory.
- **Version control:** initialise git, add `.gitignore` (`__pycache__/`, `*.py[cod]`,
  `.venv/`, `.env`, `*.db`, `*.sqlite*`, `storage/`), commit the existing scaffold as the
  baseline **before** implementing Phase 2. (Not done in Phase 1 — no VCS action was taken.)
- **Environment:** create `backend/.venv`; add `requirements.lock` (or `constraints.txt`)
  for reproducible installs; set `APP_ENV`/`AI_PROVIDER` via `.env` (never committed).
- **Configuration:** keep `pydantic-settings` + `.env.example` as the source of truth;
  keep the fail-fast validation in `Settings.validate_settings`.
- **Run (development):** `uvicorn app.main:app --reload --port 8000` from `backend/`.
  A `Makefile`/`tasks.ps1` with `dev`, `test`, `migrate`, `seed` targets is a nice-to-have.
- **Deployment (later):** a single container or a bare process behind a reverse proxy; still
  one SQLite file (or a managed Postgres only if a real deployment demands it). No cloud
  services are required for development or for the initial product.
- **Secrets:** `.env` only; no secrets in code or in git. Provide `.env.example` with
  placeholders (already done).

---

## 9. Low-Resource Development Strategy

Explicitly optimising for "low-spec laptop, no GPU, zero budget, no mandatory paid API":

1. **CPU-only by default.** No GPU requirement anywhere. `scikit-learn` TF-IDF + cosine
   similarity and `RapidFuzz` are CPU-light and need no model downloads.
2. **No mandatory large models.** `MockProvider` is the default; Gemini/Groq are strictly
   optional and key-gated. Never download a local LLM as a prerequisite.
3. **Incremental processing.** Process per case/source; persist spans and statements so
   re-runs reuse stored extraction rather than recomputing everything.
4. **Bounded work per request.** Keep ingestion and analysis off the event loop
   (threadpool/background task) so the API stays responsive on modest hardware; cap pages,
   upload size, statements per run, and LLM calls per analysis.
5. **Deterministic-first.** Do the maximum possible with local deterministic processing
   (lexical/fuzzy/temporal) and use AI only for ambiguity that heuristics cannot resolve.
6. **Lightweight dependency discipline.** Every new dependency must justify itself against
   install size and CPU/RAM cost; avoid heavy frameworks and model-serving stacks.
7. **Graceful degradation.** Missing API keys must degrade to `mock` behaviour with a clear,
   recorded status — never a hard failure of the product.
8. **Storage hygiene.** SQLite + filesystem keeps RAM and setup cost near zero; WAL keeps
   reads non-blocking during writes.

---

*End of architecture recommendation.*
