# Architecture

RELATRUM backend is a modular monolith: FastAPI + SQLAlchemy + SQLite (Postgres-portable).

## Layers
- `app/api/v1`: HTTP routers, request validation, RBAC, envelope responses.
- `app/core`: security (JWT), permissions, exceptions, logging, config.
- `app/models`: 19 normalized tables with FKs, indexes, mixins.
- `app/services`: domain logic (ingestion, extraction, normalization, alignment, temporal, divergence, findings, verification, reporting, graph, orchestration, audit, case, workspace).
- `app/ai`: provider interface (Gemini, Groq, Mock), prompts, usage accounting.
- `app/utils`: hashing, text folding, dates.
- `app/database`: engine, UTCDateTime TypeDecorator, session.

## Data flow
1. Source ingestion → text extraction → evidence spans (with char offsets).
2. Statement extraction → atomic statements linked to spans.
3. Normalization.
4. Alignment: candidate retrieval (TF-IDF + fuzzy) → classification + temporal reasoning → supersession.
5. Divergence detection → finding dossiers with evidence polarity.
6. MRE: verification tasks + responses.
7. Reporting (JSON/Markdown) + evidence graph.

## Reproducibility
Each analysis creates an `analysis_run` with pipeline/prompt/provider/model versions, input manifest hash, execution metadata. Findings carry `created_by_analysis_run` and supersession links; review history is append-only.

## Tenancy
Every workspace-owned resource is scoped by `workspace_id`; `require_workspace_member` enforces RBAC (viewer/editor/reviewer/owner). Non-members receive 404 to hide existence.

## Provider architecture
`AIProvider` interface with `extract_statements`, `classify_alignment`, `generate_verification_requests`. Mock is deterministic and fully offline; external providers optional via env. All outputs remain traceable to source spans.

## Performance
CPU-friendly: chunked extraction, hash-based dedup, candidate filtering, configurable limits, no large local models.
