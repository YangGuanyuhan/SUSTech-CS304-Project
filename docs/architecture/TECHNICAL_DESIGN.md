# Student Productivity Agent Technical Design

## 1. Overview

This project is a backend-first implementation of a modular student productivity assistant for SUSTech coursework. It currently provides:

- A FastAPI backend with SSE chat streaming
- Runtime-configurable OpenAI-compatible LLM access
- Blackboard mock integration with a provider/service boundary
- Local conversation persistence in the browser
- Config profile management for multiple API endpoints
- A Vue 3 frontend for chat, configuration, and session management

The current implementation is intentionally structured for extensibility. The short-term goal was to make the framework runnable and inspectable on the local machine before expanding into full Blackboard, mail, and memory-driven workflows.

## 2. Current Architecture

### 2.1 High-level structure

```text
backend/
  agent/        Chat orchestration, context assembly, tool prefetching
  api/          FastAPI routes and request schemas
  db/           SQLAlchemy models and CRUD helpers
  models/       Shared Pydantic models
  services/     LLM, Blackboard, email, memory, settings, runtime config

frontend/
  src/
    components/ Chat UI and settings UI
    api/        Frontend API wrapper
```

### 2.2 Main execution flow

```text
Browser UI
  -> POST /api/chat
  -> StudentProductivityAgent
  -> gather conversation history + memory + optional tool context
  -> LLMService (OpenAI-compatible)
  -> stream chunks back through SSE
  -> frontend renders markdown response into current conversation
```

### 2.3 Main files

- Backend entrypoint: [backend/main.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/main.py)
- API routes: [backend/api/routes.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/api/routes.py)
- Agent orchestration: [backend/agent/core.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/agent/core.py)
- LLM integration: [backend/services/llm_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/llm_service.py)
- Runtime settings: [backend/services/runtime_settings.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/runtime_settings.py)
- Persisted profile management: [backend/services/settings_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/settings_service.py)
- Frontend chat UI: [frontend/src/components/ChatWindow.vue](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/frontend/src/components/ChatWindow.vue)
- Frontend API settings UI: [frontend/src/components/SettingsPanel.vue](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/frontend/src/components/SettingsPanel.vue)

## 3. Core Code Framework

### 3.1 Backend framework

- Framework: FastAPI
- Config: `pydantic-settings`
- ORM: SQLAlchemy
- Response streaming: SSE via `sse-starlette`
- LLM client: OpenAI Python SDK in OpenAI-compatible mode

The backend is divided into three practical layers:

1. API layer
   Receives requests, validates input, returns typed responses.

2. Orchestration layer
   Builds prompt context, decides which helper services to call before the LLM call, stores task history.

3. Service layer
   Encapsulates external dependencies and domain-specific workflows such as Blackboard, LLM runtime settings, secret handling, and saved LLM profiles.

### 3.2 Frontend framework

- Framework: Vue 3 + Vite
- State style: component-local reactive state plus `localStorage`
- Markdown rendering: `markdown-it`

The frontend is currently organized around two user-facing surfaces:

- Chat workspace
- Settings overlay

The chat workspace includes:

- Conversation list
- New conversation
- Rename conversation
- Delete conversation
- Continue previous conversation
- Local persistence after refresh

## 4. Core Logic Implementation

### 4.1 Chat request pipeline

Implemented in [backend/agent/core.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/agent/core.py).

Core steps:

1. Load recent conversation history from `task_history`
2. Load relevant memories using keyword matching
3. Conditionally prefetch Blackboard/search context
4. Build a prompt message list for the current OpenAI-compatible backend
5. Send the request through `LLMService`
6. Stream SSE chunks back to the frontend
7. Persist final response and used tools into history

Important implementation choice:

- Tools are not yet exposed as native LLM tool-calling definitions
- Instead, the server prefetches useful context before the model call
- This keeps the current system stable while the tool boundary remains modular enough for a later migration to native function calling

### 4.2 Runtime LLM configuration

Implemented in [backend/services/runtime_settings.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/runtime_settings.py).

Behavior:

- The currently active LLM provider/model/base URL are stored in process memory
- The active API key is also kept in process memory
- The API key is never returned to the browser

This layer powers:

- `GET /api/settings/llm`
- `PUT /api/settings/llm`
- `POST /api/settings/llm/test`

### 4.3 Saved API profiles

Implemented in:

- [backend/services/settings_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/settings_service.py)
- [backend/services/secret_store.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/secret_store.py)

Behavior:

- Non-secret profile fields are persisted through `user_preferences`
- API keys can also be stored locally in encrypted form
- Applying a profile pushes its values into the active runtime config

This supports:

- Creating multiple endpoint profiles
- Reusing them without retyping the endpoint
- Switching between providers or model endpoints

### 4.4 Blackboard integration

Implemented in [backend/services/blackboard_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/blackboard_service.py).

Current design:

- `BlackboardProvider` defines the provider contract
- `MockBlackboardProvider` provides the current implementation
- `BlackboardService` wraps the provider and handles cache fallback

This is the core plug-in point for replacing mock Blackboard with a real adapter later.

### 4.5 Frontend conversation model

Implemented in [frontend/src/components/ChatWindow.vue](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/frontend/src/components/ChatWindow.vue).

Each conversation stores:

- `id`
- `title`
- `createdAt`
- `updatedAt`
- `messages[]`

Messages store:

- `id`
- `role`
- `content`
- `elapsedLabel`

Current persistence behavior:

- Conversations are saved into browser `localStorage`
- Active conversation ID is also persisted
- Refresh keeps the visible session state locally

## 5. Database Design

Current SQLAlchemy models in [backend/db/models.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/db/models.py):

- `memories`
- `email_drafts`
- `blackboard_cache`
- `task_history`
- `user_preferences`

Important notes:

- The current implementation uses synchronous SQLite through SQLAlchemy because `aiosqlite` blocked in the local Python 3.13 environment
- This was a pragmatic compatibility fix, not a long-term architectural preference
- The schema still supports future migration to PostgreSQL

## 6. Extensibility Plan

This section describes how future capabilities should be added without rewriting the current system.

### 6.1 Replace mock Blackboard with real Blackboard

Current insertion point:

- [backend/services/blackboard_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/blackboard_service.py)

How to extend:

1. Implement `RealBlackboardProvider`
2. Keep the same method signatures:
   - `get_all_courses`
   - `get_assignments`
   - `get_announcements`
   - `download_file`
3. Preserve return types using existing Pydantic models
4. Replace provider selection with configuration-based provider wiring
5. Keep cache fallback in `BlackboardService`, not in the provider itself

Reason:

- Providers should only fetch data
- Service layer should own reliability policy and fallback

### 6.2 Upgrade to native LLM tool calling

Current status:

- Server-side prefetch only

How to extend:

1. Define OpenAI-compatible tool schemas for Blackboard, search, memory, and email draft creation
2. Add a tool execution loop in `StudentProductivityAgent`
3. On `tool_calls`, execute mapped Python functions
4. Send tool results back to the LLM
5. Repeat until final assistant text is produced

Recommended insertion point:

- [backend/agent/core.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/agent/core.py)

Reason:

- This keeps orchestration centralized
- Service interfaces are already modular enough for this step

### 6.3 Replace local browser conversation storage with backend conversation storage

Current status:

- Frontend-only `localStorage`

How to extend:

1. Add `conversations` and `conversation_messages` tables, or a conversation grouping model on top of `task_history`
2. Create backend CRUD APIs for:
   - list conversations
   - rename conversation
   - delete conversation
   - load conversation messages
3. Move current local persistence logic into API-backed state loading
4. Keep a browser cache only as a convenience, not as source of truth

Reason:

- Current refresh continuity works only in the same browser
- It does not support multi-device or shared state

### 6.4 Add robust memory retrieval

Current status:

- Keyword matching only

How to extend:

1. Add embedding generation for memory records
2. Add vector similarity retrieval
3. Keep the `MemoryService` interface stable
4. Optionally allow hybrid retrieval: keyword + embedding

Recommended place:

- [backend/services/memory_service.py](https://github.com/sustech-cs304/team-project-26spring-26s-8/blob/main/backend/services/memory_service.py)

### 6.5 Email workflow expansion

Current status:

- Draft/save/send path exists
- Mail reading is still minimal

How to extend:

1. Add IMAP-backed inbox reading
2. Add draft approval history
3. Add UI for draft review and send confirmation
4. Keep human-in-the-loop enforcement in backend service logic

### 6.6 Multi-provider support

Current status:

- Only `provider=openai` is accepted, though `base_url` may target any OpenAI-compatible endpoint

How to extend:

1. Expand provider normalization to accept aliases like:
   - `dashscope`
   - `qwen`
   - `deepseek`
   - `openai-compatible`
2. Map these aliases internally to the same OpenAI-compatible transport layer
3. Add per-provider defaults for recommended models and URLs

## 7. Current Gaps vs. Original Project Goals

The current implementation is functional, but it is still not the full target system described in the original project prompt.

### 7.1 What is already done

- Modular backend structure
- FastAPI application
- Configuration UI for LLM backends
- Blackboard mock provider
- Conversation management UI
- Markdown rendering in chat
- SSE-based streaming path
- Local multi-session conversation support

### 7.2 What is still missing

- Real Blackboard integration
- Stable native LLM tool calling
- True PydanticAI-driven agent loop
- Full email workflow UI
- Rich memory management UI
- Search provider configuration UI
- Backend-persisted conversations
- User authentication or multi-user isolation
- Docker packaging and production deployment setup
- CI coverage quality gates and broader test cases

## 8. TODO List

### Near-term TODO

1. Finish browser-side SSE debug tooling so stream failures can be diagnosed visually
2. Add conversation rename/delete APIs on backend if conversations move out of local storage
3. Improve LLM connection test error messaging for provider-specific failures
4. Add per-profile test/apply status in the settings panel
5. Add frontend controls to clear one conversation or clear all local conversations

### Medium-term TODO

1. Implement real Blackboard provider
2. Add native OpenAI-compatible tool calling loop
3. Add backend-persisted conversations and conversation summaries
4. Add proper mail inbox reading and draft review UI
5. Expand memory retrieval beyond keyword matching
6. Revisit async DB implementation once local Python/driver compatibility is stable

### Longer-term TODO

1. Multi-user authentication and isolation
2. PostgreSQL production migration
3. Docker and deployment manifests
4. Fine-grained RBAC or secure local secret management policy
5. Formal observability and structured logging

## 9. Recommended Next Steps

If the team wants the biggest product improvement with the least rework, the recommended order is:

1. Stabilize the live LLM chat experience completely
2. Move conversation state from browser-only storage to backend persistence
3. Replace mock Blackboard with a real provider
4. Upgrade from prefetch-style orchestration to true tool-calling orchestration
5. Finish email and memory management UI

This ordering keeps current user-visible value while moving steadily toward the original system design.
