# Relocation & Routine Copilot — project context

AI relocation/routine copilot: helps people who've recently moved rebuild routines (fitness,
focused work, outdoor activity) via place + route + weather data, deterministic (non-hallucinated)
ranking, and explicit data-confidence labeling.

Full design doc: [docs/relocation-copilot-design.md](docs/relocation-copilot-design.md). Scoring
weight rationale: [docs/decisions/0001-scoring-weights.md](docs/decisions/0001-scoring-weights.md).

This file is shared context for any Claude session (Claude Code or the Claude.ai app) working in
this repo — both start cold each session, so treat this as the brief that carries state between
them. Keep it current as milestones land; don't let it drift from the code.

## Monorepo layout

- `frontend/` — Next.js (App Router) + TypeScript + Tailwind. Chat UI, recommendation cards, map,
  onboarding, settings.
- `backend/` — FastAPI. LangGraph agent orchestration, provider integrations (weather/route/places/
  geocoding/calendar/LLM), deterministic scoring, Firestore data access.
- `infrastructure/` — Cloud Run service config, Firestore security rules/indexes.
- `docs/` — architecture notes and ADRs.
- `.github/workflows/` — CI (lint/test) and deploy pipelines.

## Local development

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env        # fill in FIREBASE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS
uvicorn app.main:app --http h11
```

`--http h11` is required — auto-detected `httptools` crashes on Python 3.12/Windows. Don't use
`--reload` on Windows either: its subprocess reloader can fail to inherit the venv and leaves a
zombie process squatting on port 8000 (symptom: requests hang with no log line). If that happens:
`netstat -ano | findstr :8000` then `taskkill /PID <pid> /F`, restart manually.

Health check: http://localhost:8000/v1/health. Docs: http://localhost:8000/docs.
Test: `pytest`. Lint: `ruff check app tests`.

Frontend:

```bash
cd frontend
npm install
npm run dev   # http://localhost:3000
```

Lint/typecheck: `npm run lint`, `npm run typecheck`. Test: `npx vitest run` (Vitest + RTL).

## Architecture notes

- Agent orchestration is a LangGraph graph (`backend/app/agent/graph.py`, nodes in
  `backend/app/agent/nodes/`) — not a freeform agent loop. Ranking is deterministic scoring
  (`backend/app/scoring/`), not LLM-judged, by design (see design doc for why).
- Side-effecting actions (e.g. creating a calendar event) go through an explicit
  `request_user_approval` interrupt — no code path should create a calendar event without a
  confirmed user approval. Preserve this invariant when touching `backend/app/agent/` or
  `backend/app/api/calendar.py`.
- Calendar tokens are encrypted at rest (`backend/app/core/`); OAuth state is CSRF-protected via
  `oauth_state.py`.
- Frontend talks to the backend through `frontend/lib/api-client.ts`; Firebase auth context in
  `frontend/lib/auth-context.tsx`.

## Conventions

- Commit messages are milestone-tagged (`M<major>.<minor>: ...` or `fix: ...`) — match this style;
  it doubles as the changelog across milestones.
- Prefer editing existing files over new ones; no speculative abstractions ahead of the milestone
  that needs them.

## Working across two Claude sessions

This repo is being worked on from both a local Claude Code session and the Claude.ai app. The
Claude.ai app only sees this repo via GitHub (it doesn't share this machine's working directory or
uncommitted state), so:

- Push before switching tools, pull before starting — origin/master is the handoff point, not the
  local working tree.
- Avoid both sides committing to `master` at the same time; prefer a feature branch + PR when work
  might overlap.
- If you (either Claude) make an architectural decision or discover a non-obvious constraint,
  record it here or as an ADR in `docs/decisions/` — don't leave it only in chat history the other
  session can't see.
