# Student Productivity Agent

Student Productivity Agent is a modular software engineering project for SUSTech students. The backend uses FastAPI, async SQLAlchemy, and pluggable providers for Blackboard, email, search, file automation, and memory. The frontend is a Vue 3 + Vite shell that consumes stable HTTP and SSE APIs.

## Current scope

- Backend-first architecture with stable domain models
- Mock-first Blackboard integration with cache fallback path
- Human-in-the-loop email draft and send flow
- Local file summary and batch rename workflow
- Local knowledge-base RAG with RAG-Anything-backed indexing
- Memory CRUD and task history persistence
- Minimal Vue frontend shell

## Quick start

### Backend

```bash
uv sync
uv run uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Tests

```bash
uv run pytest
```

## Project layout

```text
backend/
  agent/       Agent orchestration and tool wrappers
  api/         FastAPI routers and request models
  db/          Async database engine, ORM models, repositories
  models/      Shared Pydantic contracts
  services/    Domain services and provider adapters
frontend/      Vue 3 + Vite client
tests/         Backend test suite
```

## Notes

- Secrets are loaded from environment variables only.
- Blackboard V1 defaults to a mock provider behind a stable interface.
- Production migration to PostgreSQL is driven by `DATABASE_URL`.
- RAG setup and usage notes live in `docs/RAG_README.md`.
