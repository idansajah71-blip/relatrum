<div align="center">

<img src="docs/assets/banner.svg" alt="RELATRUM: where expectations meet evidence" width="100%">

<br>

<img src="https://img.shields.io/badge/tests-100%20passed-2DD4BF?style=for-the-badge&labelColor=0A0F1E" alt="Tests: 100 passed">
<img src="https://img.shields.io/badge/backend-FastAPI-009688?style=for-the-badge&labelColor=0A0F1E&logo=fastapi&logoColor=white" alt="Backend: FastAPI">
<img src="https://img.shields.io/badge/frontend-Next.js%2016-FFFFFF?style=for-the-badge&labelColor=0A0F1E&logo=nextdotjs&logoColor=white" alt="Frontend: Next.js 16">
<img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=for-the-badge&labelColor=0A0F1E&logo=python&logoColor=white" alt="Python 3.11+">
<img src="https://img.shields.io/badge/license-Proprietary-A78BFA?style=for-the-badge&labelColor=0A0F1E" alt="License: Proprietary">

<br><br>

<a href="#overview"><b>Overview</b></a> &nbsp;&middot;&nbsp;
<a href="#how-it-works"><b>How It Works</b></a> &nbsp;&middot;&nbsp;
<a href="#architecture"><b>Architecture</b></a> &nbsp;&middot;&nbsp;
<a href="#quick-start"><b>Quick Start</b></a> &nbsp;&middot;&nbsp;
<a href="#documentation"><b>Documentation</b></a> &nbsp;&middot;&nbsp;
<a href="#responsible-ai"><b>Responsible AI</b></a>

</div>

<br>

<img src="docs/assets/stats.svg" alt="RELATRUM at a glance: 100 tests, 19 tables, 4 roles, 3 AI providers" width="100%">

<br>

## Overview

Organizations constantly say one thing on paper and live another in practice. Requirements sit in one place, observations in another, and finding where they diverge is slow, manual, and easy to get wrong.

**RELATRUM** is an evidence intelligence platform that closes that gap. It turns fragmented organizational information into a structured, traceable, time-aware evidence system, then:

- identifies possible divergence between official requirements and real-world observations,
- preserves uncertainty and counter-evidence instead of hiding it,
- proposes the **minimum evidence** needed to resolve each finding.

> RELATRUM never declares a violation on its own. Every finding is a candidate for human review.

<br>

## Highlights

<table>
  <tr>
    <td width="50%" valign="top">
      <b>Bidirectional alignment</b><br>
      Matches requirement to observation <i>and</i> observation to requirement, so gaps surface from both directions.
    </td>
    <td width="50%" valign="top">
      <b>Temporal reasoning</b><br>
      Effective dates, interval overlap, and supersession. Unknown-safe: no implicit infinity.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <b>Counter-evidence preservation</b><br>
      Conflicting evidence is never discarded. It stays attached to the finding it affects.
    </td>
    <td width="50%" valign="top">
      <b>Finding dossiers</b><br>
      Structured evidence with polarity, quality profile, and complete review history.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <b>Minimum Resolving Evidence (MRE)</b><br>
      Targeted verification tasks and responses that resolve a finding with the least effort.
    </td>
    <td width="50%" valign="top">
      <b>Reports and evidence graph</b><br>
      JSON and Markdown export, plus a graph view of how evidence connects.
    </td>
  </tr>
  <tr>
    <td width="50%" valign="top">
      <b>Responsible AI by design</b><br>
      Findings are candidates, not verdicts. Mock mode is deterministic and fully offline.
    </td>
    <td width="50%" valign="top">
      <b>Multi-tenant</b><br>
      Workspaces, role-based access (owner, editor, reviewer, viewer), and strict workspace isolation.
    </td>
  </tr>
</table>

<br>

## How It Works

<img src="docs/assets/pipeline.svg" alt="Analysis pipeline: ingest, extract, align, temporal, findings, MRE, review" width="100%">

Every analysis is **reproducible**: runs carry a manifest hash and run metadata, and every finding is grounded in evidence.

<details>
<summary><b>Stage-by-stage breakdown</b> (click to expand)</summary>

<br>

| Stage | What happens |
|---|---|
| **01 Ingest** | Fragmented sources are brought into a single workspace. |
| **02 Extract** | Structured requirements and observations are extracted, each traceable to its source span. |
| **03 Align** | Both sides are matched in both directions to detect possible divergence. |
| **04 Temporal** | Effective dates, interval overlap, and supersession are applied, so a superseded requirement is never compared against the wrong observation. |
| **05 Findings** | Candidates are assembled into dossiers that keep supporting and conflicting evidence side by side. |
| **06 MRE** | For each finding, RELATRUM proposes the smallest verification that could resolve it. |
| **07 Review** | Human reviewers decide. Results export as JSON or Markdown reports, or are explored in the evidence graph. |

Full methodology: [`docs/ai-methodology.md`](docs/ai-methodology.md)

</details>

<details>
<summary><b>Core concepts</b> (click to expand)</summary>

<br>

| Concept | Meaning |
|---|---|
| **Requirement** | An official statement of what should be true (policy, contract clause, standard). |
| **Observation** | A real-world statement of what is actually true (report, log, field note). |
| **Finding** | A candidate divergence between a requirement and an observation. Never an automatic verdict. |
| **Polarity** | Whether a piece of evidence supports or conflicts with a finding. |
| **Dossier** | The complete record of a finding: evidence, counter-evidence, quality profile, and review history. |
| **MRE** | Minimum Resolving Evidence: the smallest verification needed to resolve a finding. |

</details>

<br>

## Architecture

<img src="docs/assets/architecture.svg" alt="Architecture: Next.js frontend, FastAPI API, service layer, database and AI provider" width="100%">

The backend is a **modular monolith**: routers, services, models, and AI providers are separated by responsibility, which keeps the codebase easy to test and reason about.

For module responsibilities, data flow, tenancy, and deployment, see [`docs/architecture.md`](docs/architecture.md).

<br>

## Quick Start

**Prerequisites:** Python 3.11+, Node.js (a version supported by Next.js 16), and Git.

```bash
git clone <your-repo-url> relatrum
cd relatrum
```

### 1. Start the backend

<details open>
<summary><b>Windows</b></summary>

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --port 8000
```

</details>

<details>
<summary><b>macOS / Linux</b></summary>

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --port 8000
```

</details>

### 2. Start the frontend

<details open>
<summary><b>Windows</b></summary>

```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```

</details>

<details>
<summary><b>macOS / Linux</b></summary>

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

</details>

### 3. Open it

| Service | URL |
|---|---|
| Frontend | http://localhost:3000 |
| Interactive API docs (OpenAPI) | http://localhost:8000/docs |
| Health and readiness | http://localhost:8000/health/ready |

> **No API keys required.** RELATRUM starts in deterministic mock mode, fully offline.

<br>

## AI Providers

RELATRUM talks to AI through a provider interface, so swapping engines never touches the rest of the system.

| Provider | Mode | Notes |
|---|---|---|
| **Mock** (default) | Deterministic heuristics, offline | Ideal for development, tests, and demos. Disclosed as mock in system info and reports. |
| **Gemini** | Hosted LLM | Configured through `.env`. |
| **Groq** | Hosted LLM | Configured through `.env`. |

Available settings are listed in `backend/.env.example`.

<br>

## Multi-Tenancy and Roles

Data is organized into **workspaces** with strict isolation between them. Access inside a workspace is role-based.

| Role | Intended use |
|---|---|
| `owner` | Full control of the workspace. |
| `editor` | Works with sources, analyses, and findings. |
| `reviewer` | Reviews findings and records decisions. |
| `viewer` | Read-only access. |

<br>

## Testing

| Area | Command | Result |
|---|---|---|
| Backend | `cd backend && python -m pytest` | 100 passed |
| Frontend build | `cd frontend && npm run build` | Production build succeeds |
| Frontend lint | `cd frontend && npm run lint` | 0 errors |

The backend suite covers ingestion, extraction, alignment, temporal logic, findings, MRE, reporting, graph, and RBAC.

<br>

## Documentation

| Document | Description |
|---|---|
| [Architecture](docs/architecture.md) | Modules, data flow, tenancy, providers |
| [Data Dictionary](docs/data-dictionary.md) | All 19 tables and fields |
| [AI Methodology](docs/ai-methodology.md) | Extraction, alignment, temporal, MRE, quality |
| [Evaluation](docs/evaluation.md) | Synthetic dataset and test results |
| [Privacy](docs/privacy.md) | Data handling and security |
| [Backend README](backend/README.md) | Backend-specific setup and API |
| [Frontend README](frontend/README.md) | Frontend setup and pages |

<br>

## Tech Stack

<div align="center">

<img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
<img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
<img src="https://img.shields.io/badge/Pydantic-E92063?style=flat-square&logo=pydantic&logoColor=white" alt="Pydantic">
<img src="https://img.shields.io/badge/SQLAlchemy-D71F00?style=flat-square&logo=sqlalchemy&logoColor=white" alt="SQLAlchemy">
<img src="https://img.shields.io/badge/Alembic-555555?style=flat-square" alt="Alembic">
<img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
<img src="https://img.shields.io/badge/SQLite-003B57?style=flat-square&logo=sqlite&logoColor=white" alt="SQLite">
<img src="https://img.shields.io/badge/scikit--learn-F7931E?style=flat-square&logo=scikitlearn&logoColor=white" alt="scikit-learn">
<img src="https://img.shields.io/badge/RapidFuzz-555555?style=flat-square" alt="RapidFuzz">
<br>
<img src="https://img.shields.io/badge/Next.js%2016-000000?style=flat-square&logo=nextdotjs&logoColor=white" alt="Next.js 16">
<img src="https://img.shields.io/badge/React%2019-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React 19">
<img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
<img src="https://img.shields.io/badge/Tailwind%20CSS%204-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white" alt="Tailwind CSS 4">
<img src="https://img.shields.io/badge/Gemini-8E75B2?style=flat-square" alt="Gemini">
<img src="https://img.shields.io/badge/Groq-F55036?style=flat-square" alt="Groq">

</div>

<br>

## Project Structure

```text
relatrum/
├── backend/     # FastAPI backend: routers, services, models, AI providers
├── frontend/    # Next.js frontend
├── docs/        # Architecture, data dictionary, methodology, evaluation, privacy
│   └── assets/  # README visuals (banner, stats, pipeline, architecture)
└── README.md
```

<br>

## Responsible AI

RELATRUM is built to assist human judgment, never to replace it.

| Principle | What it means here |
|---|---|
| **Human review first** | Findings are candidates requiring human review, never auto-proven violations. |
| **Honest about absence** | Absence of evidence is not evidence of non-compliance. |
| **Transparent mock mode** | Mock mode is deterministic heuristics, and is disclosed as such in system info and reports. |
| **No unsupported causality** | No causal claims are made without explicit evidence. |
| **Full traceability** | All outputs are traceable to source spans. |

<br>

## FAQ

<details>
<summary><b>Do I need an API key to try RELATRUM?</b></summary>

<br>

No. The default Mock provider is deterministic and runs fully offline. Gemini and Groq are optional and configured through `.env`.

</details>

<details>
<summary><b>Does RELATRUM decide whether something is compliant?</b></summary>

<br>

No. It surfaces candidate divergences with their supporting evidence, counter-evidence, and uncertainty. A human reviewer makes the call.

</details>

<details>
<summary><b>What happens when evidence conflicts?</b></summary>

<br>

Nothing is discarded. Conflicting evidence stays in the finding dossier with its polarity, so reviewers see both sides.

</details>

<details>
<summary><b>Which databases are supported?</b></summary>

<br>

SQLite and PostgreSQL, through SQLAlchemy 2.x with Alembic migrations.

</details>

<br>

## License

Proprietary / internal project. All rights reserved.

<br>

<div align="center">

**RELATRUM** &nbsp;&middot;&nbsp; Where expectations meet evidence.

<a href="#">Back to top</a>

</div>
