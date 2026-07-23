# Backend — Relocation & Routine Copilot API

FastAPI. `/v1/health` (unauthenticated) and `/v1/me` (Firebase-token-protected) as of
Milestone 0 — agent/provider code lands in later milestones.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
```

Then fill in `.env`:
- `FIREBASE_PROJECT_ID` — from Firebase console > Project settings > General.
- `GOOGLE_APPLICATION_CREDENTIALS` — full path to the service account JSON you downloaded from
  Project settings > Service accounts > Generate new private key. Keep this file outside the repo.

```bash
uvicorn app.main:app --http h11
```

`--http h11` forces the pure-Python HTTP protocol implementation. Without it, uvicorn tries to
auto-detect and use `httptools` if present, which has a known incompatibility with Python 3.12 on
Windows (crashes with `TypeError: Metaclasses with custom tp_new are not supported`). We're not
using the `uvicorn[standard]` extra for this reason — plain `uvicorn` is enough for MVP local dev
and Cloud Run.

**Deliberately not using `--reload` on Windows.** Its subprocess reloader has been observed
failing to inherit the active venv (crashing with `ModuleNotFoundError` for packages that are
definitely installed), and — worse — leaving a dead process squatting on port 8000 afterward, so
every subsequent request silently hangs against that zombie process instead of a working server or
a clear connection error. If you hit a request that hangs forever with no log line in the uvicorn
terminal, check for a stale process first: `netstat -ano | findstr :8000`, then
`taskkill /PID <pid> /F`. Just restart uvicorn manually after each code change instead — one extra
command, but predictable.

Open http://localhost:8000/v1/health — expect `{"status": "ok"}`.
`/v1/me` requires a real Firebase ID token as a Bearer header — easiest way to test it end to end
is through the frontend's "Verify backend sees my token" button once you're signed in there.
Interactive API docs: http://localhost:8000/docs

## Test

```bash
pytest
```

## Lint

```bash
ruff check app tests
```
