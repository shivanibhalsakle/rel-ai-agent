# Relocation & Routine Copilot

An AI relocation and routine copilot that helps people who've recently moved rebuild their daily
routines — fitness, focused work, and outdoor activity — by combining place, route, and weather
data behind a single agent, with deterministic (non-hallucinated) ranking and explicit data
confidence labeling.

Full product and architecture design: see `docs/relocation-copilot-design.md` (or the copy shared
in project chat).

## Monorepo layout

- `frontend/` — Next.js (App Router) + TypeScript + Tailwind. Chat UI, recommendation cards, map,
  onboarding.
- `backend/` — FastAPI. Agent orchestration (LangGraph), provider integrations, deterministic
  scoring, Firestore data access.
- `infrastructure/` — Cloud Run service config, Firestore security rules/indexes.
- `docs/` — architecture notes and decision records (ADRs).
- `.github/workflows/` — CI (lint/test) and deploy pipelines.

## Status

Milestone 0 in progress: repo skeleton, local dev skeletons for frontend/backend, Firebase Auth,
first deploy to `app.<domain>` (Vercel) and Cloud Run.

## Local development

See `frontend/README.md` and `backend/README.md` (added as each skeleton is built) for
run/test instructions.
