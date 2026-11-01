<div align="center">

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0f172a,100:0d9488&height=200&section=header&text=RELATRUM&fontSize=60&fontColor=ffffff&animation=fadeIn&fontAlignY=38&desc=Where%20expectations%20meet%20evidence.&descAlignY=58&descSize=18" alt="RELATRUM header" width="100%">

<br>

[![Build](https://img.shields.io/github/actions/workflow/status/idansajah71-blip/relatrum/ci.yml?style=for-the-badge&labelColor=0A0F1E&label=build)](https://github.com/idansajah71-blip/relatrum/actions)
[![Release](https://img.shields.io/github/v/release/idansajah71-blip/relatrum?style=for-the-badge&labelColor=0A0F1E&color=0d9488)](https://github.com/idansajah71-blip/relatrum/releases)
[![Stars](https://img.shields.io/github/stars/idansajah71-blip/relatrum?style=for-the-badge&labelColor=0A0F1E&color=fbbf24)](https://github.com/idansajah71-blip/relatrum/stargazers)
[![License](https://img.shields.io/badge/license-Proprietary-A78BFA?style=for-the-badge&labelColor=0A0F1E)](#license)
[![Tests](https://img.shields.io/badge/tests-100%20passed-2DD4BF?style=for-the-badge&labelColor=0A0F1E)](#testing)

<br>

<img src="https://readme-typing-svg.demolab.com?font=Segoe+UI&weight=600&size=20&duration=3000&pause=1000&color=38BDF8&center=true&vCenter=true&width=700&lines=Where+expectations+meet+evidence.;Turn+fragmented+information+into+structured+evidence.;Preserve+uncertainty.+Preserve+counter-evidence." alt="Typing tagline" width="700">

<br>

<img src="docs/assets/stats.svg" alt="RELATRUM at a glance" width="100%">

</div>

<br>

## Overview

Organizations constantly say one thing on paper and live another in practice. Requirements sit in one place, observations in another, and finding where they diverge is slow, manual, and easy to get wrong.

RELATRUM is an evidence intelligence platform that closes that gap. It turns fragmented organizational information into a structured, traceable, time-aware evidence system, then:

- identifies possible divergence between official requirements and real-world observations,
- preserves uncertainty and counter-evidence instead of hiding it,
- proposes the minimum evidence needed to resolve each finding.

> RELATRUM never declares a violation on its own. Every finding is a candidate for human review.

<br>

## Demo

> Placeholder for demo GIF / video. Record a walkthrough of: create case, upload source, extract statements, analyze, review finding, generate MRE, export report.

![Demo placeholder](docs/assets/pipeline.svg)

Short explanation: the animation above shows the end-to-end evidence pipeline from source ingestion to report generation. A recorded demo video can be dropped into this section later.

<br>

## Highlights

<table>
  <tr>
    <td width="50%" valign="top">
      <b>Bidirectional alignment</b><br>
      Matches requirement to observation and observation to requirement, so gaps surface from both directions.
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
      <b>Minimum Resolving Evidence</b><br>
      Targeted verification tasks with competing hypotheses and expected answer structure.
    </td>
  </tr>
</table>

<br>

## Architecture

<img src="docs/assets/animated-architecture.svg" alt="Animated architecture" width="100%">

```mermaid
flowchart LR
    U[User] --> FE[Next.js Frontend]
    FE --> API[FastAPI /api/v1]
    API --> SVC[Service Layer]
    SVC --> DB[(SQLite / PostgreSQL)]
    SVC --> AI[AI Provider Adapter]
    AI --> MOCK[Mock (default)]
    AI --> GEMINI[Gemini (optional)]
    AI --> GROQ[Groq (optional)]
```

The backend is a modular monolith: routers, services, models, and AI providers are separated by responsibility. Every analysis is reproducible (manifest hash, run metadata) and all findings are evidence-grounded.

See the full [Architecture document](docs/architecture.md).

<br>

## Tech stack

<p align="center">
  <img src="https://skillicons.dev/icons?i=python,fastapi,postgres,sqlite,nextjs,react,ts,tailwind,docker,git,github" alt="Tech stack icons" />
</p>

Backend: Python 3.11+, FastAPI, Pydantic v2, SQLAlchemy 2.x, Alembic, SQLite/PostgreSQL, scikit-learn, RapidFuzz.

Frontend: Next.js 16, React 19, TypeScript (strict), Tailwind CSS 4.

AI: Mock (default, deterministic, offline), Gemini, Groq via provider interface.

<br>

## Quick start

<details>
<summary><b>Windows (PowerShell)</b></summary>

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --port 8000

cd ..\frontend
npm install
copy .env.example .env.local
npm run dev
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

cd ../frontend
npm install
cp .env.example .env.local
npm run dev
```

</details>

- OpenAPI: http://localhost:8000/docs
- Frontend: http://localhost:3000

<br>

## Testing

```bash
cd backend
python -m pytest        # 100 passed
```

```bash
cd frontend
npm run build            # production build
npm run lint              # 0 errors
```

<br>

## Documentation

| Document | Description |
|----------|-------------|
| [Architecture](docs/architecture.md) | Modules, data flow, tenancy, providers |
| [Data Dictionary](docs/data-dictionary.md) | All 19 tables and fields |
| [AI Methodology](docs/ai-methodology.md) | Extraction, alignment, temporal, MRE, quality |
| [Evaluation](docs/evaluation.md) | Synthetic dataset and test results |
| [Privacy](docs/privacy.md) | Data handling and security |
| [Backend README](backend/README.md) | Backend-specific setup and API |
| [Frontend README](frontend/README.md) | Frontend setup and pages |

<br>

## FAQ

<details>
<summary><b>Does RELATRUM require an API key?</b></summary>

No. Default mode is `AI_PROVIDER=mock`, which runs fully offline with deterministic rule-based processing. Gemini and Groq are optional enhancements.

</details>

<details>
<summary><b>Are findings proof of non-compliance?</b></summary>

No. Findings are candidates requiring human review. Absence of evidence is not evidence of non-compliance. RELATRUM is decision support, not an accusation engine.

</details>

<details>
<summary><b>How is reproducibility ensured?</b></summary>

Each analysis creates an analysis run with pipeline, prompt, provider, and model versions plus an input manifest hash (SHA-256). Findings carry the originating run and supersession links. Review and audit trails are append-only.

</details>

<details>
<summary><b>Can I use PostgreSQL instead of SQLite?</b></summary>

Yes. Models are Postgres-portable. Set `DATABASE_URL` to a PostgreSQL connection string and run Alembic migrations.

</details>

<br>

## Responsible AI

- Findings are candidates requiring human review, never auto-proven violations.
- Absence of evidence is not evidence of non-compliance.
- Mock mode is deterministic heuristics, disclosed as such in system info and reports.
- No causal claims without explicit evidence.
- All outputs traceable to source spans.

<br>

## License

Proprietary / internal project.

<div align="center">
<br>
<img src="https://capsule-render.vercel.app/api?type=waving&color=0:0d9488,100:0f172a&height=120&section=footer" alt="footer" width="100%">
</div>
