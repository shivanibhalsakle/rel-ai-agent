# Backend — Relocation & Routine Copilot API

FastAPI. Health check only in Milestone 0 — agent/provider code lands in later milestones.

## Run locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Open http://localhost:8000/v1/health — expect `{"status": "ok"}`.
Interactive API docs: http://localhost:8000/docs

## Test

```bash
pytest
```

## Lint

```bash
ruff check app tests
```
