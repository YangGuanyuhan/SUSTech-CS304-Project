# Student Productivity Agent

Student Productivity Agent is a modular software engineering project for SUSTech students. The backend uses FastAPI, async SQLAlchemy, and pluggable providers for Blackboard, email, search, file automation, and memory. The frontend is a Vue 3 + Vite shell that consumes stable HTTP and SSE APIs.

## Current scope

- Backend-first architecture with stable domain models
- Mock-first Blackboard integration with cache fallback path
- Human-in-the-loop email send flow with inbox reading and reusable profiles
- Local file summary and batch rename workflow
- Local knowledge-base RAG with RAG-Anything-backed indexing
- **Intelligent memory system with semantic search and context management**
- **Tool learning and pattern recognition**
- Memory CRUD and task history persistence
- Minimal Vue frontend shell

## Quick start

### One-command start (Recommended)

```bash
./start-dev.sh
```

This starts both backend (port 8000) and frontend (port 5173).

### Manual start

#### Backend

```bash
uv sync
uv run uvicorn backend.main:app --reload
```

#### Frontend

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
  db/          Database engine, ORM models, repositories, migrations
  models/      Shared Pydantic contracts
  services/    Domain services and provider adapters
frontend/      Vue 3 + Vite client
tests/         Backend test suite
docs/          Documentation
  architecture/  System design and architecture docs
  development/   Development guides and refactoring notes
  features/      Feature implementation documentation
```

## Documentation

### Architecture
- [Technical Design](docs/architecture/TECHNICAL_DESIGN.md) - Overall system architecture
- [Design Document](docs/architecture/design-26s-8.md) - Detailed design with UI mockups
- [Database Overview](docs/architecture/DATABASE_CURRENT_OVERVIEW.md) - Current database schema
- [Project Proposal](docs/architecture/proposal-26s-8.md) - Original project proposal

### Features
- [Email Feature](docs/features/EMAIL_FEATURE.md) - End-to-end email workflow with configuration, inbox reading, and approval-based sending
- [Memory System](docs/features/MEMORY_SYSTEM_IMPLEMENTATION.md) - Intelligent memory with semantic search
- [RAG System](docs/RAG_README.md) - Knowledge base and RAG setup

### Development
- [Database Refactoring](docs/development/DATABASE_REFACTOR_SUMMARY.md) - Database migration history
- [Contributing Guide](CONTRIBUTING.md) - How to contribute

## Key Features

### 🧠 Intelligent Memory System
- **Semantic Search**: Hybrid search combining embeddings + keywords + recency
- **Context Management**: Token-aware compression with LLM summarization
- **Tool Learning**: Automatically learns from successful tool usage patterns
- **Lifecycle Management**: Auto-extraction, consolidation, and pruning

### 📚 Knowledge Base (RAG)
- Local document indexing with RAG-Anything
- Support for PDF, DOCX, PPTX, Markdown, and text files
- Semantic search across indexed materials

### 📅 Calendar & Tasks
- Unified calendar with Blackboard integration
- Task history and conversation persistence
- Event management and reminders

## Notes

- Secrets are loaded from environment variables only.
- Blackboard V1 defaults to a mock provider behind a stable interface.
- Production migration to PostgreSQL is driven by `DATABASE_URL`.
- First-time setup may take 10-20 minutes to download ML dependencies (PyTorch, CUDA libraries for RAG).
- Docker Compose mounts host `./shared` to backend `/app/shared`; place files there for local file tools and RAG indexing.
