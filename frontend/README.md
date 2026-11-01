# RELATRUM Frontend

Next.js 16 (App Router, TypeScript strict, Tailwind 4) client for the RELATRUM backend.

## Setup
```bash
cd frontend
npm install
copy .env.example .env.local
npm run dev
```
Open http://localhost:3000. Backend must run on http://localhost:8000.

## Scripts
- `npm run dev` — development server.
- `npm run build` — production build.
- `npm run lint` — ESLint.
- `npm run start` — production server.

## Pages
- `/login` — authentication.
- `/dashboard` — workspaces and cases.
- `/cases/[id]` — case workbench (ingest, extract, analyze, findings, MRE, report).

## Notes
- API base URL via `NEXT_PUBLIC_API_URL`.
- Token stored in localStorage; all API calls include Bearer token.
- Vertical slice; further polish (graph visualization, timeline, PDF export) planned.
