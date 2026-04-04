# Database Refactor Summary

## 1. Background

This repository is a software engineering group project for a student productivity agent.  
The database layer previously worked, but it had several structural problems:

- Synchronous SQLAlchemy was wrapped in many `async def` CRUD functions
- Several fields were stored as manual JSON strings and decoded repeatedly in services
- Quiz-related tables had weak relational structure
- The persistence layer was difficult to extend toward future requirements described in the design docs
- There was no direct visualization entry for inspecting database state during demos

This refactor was completed on branch:

```bash
feat-db-refactor-foundation
```

Base branch at the time of work:

```bash
dev-pydanticAI
```

## 2. What Was Read Before Refactoring

The following project materials were reviewed before implementing changes:

- `README.md`
- `TECHNICAL_DESIGN.md`
- `proposal-26s-8.md`
- Existing backend database code in `backend/db/`
- Related services in `backend/services/`
- Existing backend tests in `tests/`

Important future-facing requirements extracted from the docs:

- Conversation storage should move from browser-only storage to backend tables
- Memory retrieval should later support embeddings / stronger retrieval
- Email workflow should later support approval history
- The system should remain compatible with future PostgreSQL migration
- The codebase should stay modular and easy to extend

## 3. Problems Found in the Original Database Layer

### 3.1 Persistence problems

- JSON fields were stored as raw text, for example:
  - memory values
  - memory tags
  - Blackboard cache payloads
  - task history tool lists
  - quiz options
- This forced repeated `json.dumps` / `json.loads` logic in services.

### 3.2 Structural problems

- Quiz tables had weak relational modeling
- Foreign keys and cascading behavior were missing
- Important uniqueness / indexing rules were not enforced

### 3.3 Code organization problems

- `backend/db/crud.py` had become a single large mixed helper file
- Services depended on low-level storage details instead of clearer repository abstractions
- Some tests mocked outdated method names and did not truly validate the intended fallback path

### 3.4 Demo / inspection problems

- There was no dedicated UI/API view for showing current database state
- That made it harder to explain the refactor during project review or group presentation

## 4. What Was Changed

### 4.1 ORM model upgrade

File:

- `backend/db/models.py`

Main changes:

- Added better indexes for frequent lookup paths
- Added uniqueness constraints where appropriate
- Added foreign keys for quiz-related tables
- Added cascade delete behavior for quiz relationships
- Converted JSON-like string columns into typed JSON-backed columns
- Changed quiz answer correctness from string storage to nullable boolean storage

Examples:

- `MemoryRecord.value` is now stored as structured JSON instead of `value_json`
- `MemoryRecord.tags` is now stored as structured JSON instead of `tags_json`
- `TaskHistoryRecord.tools_used` is now stored as structured JSON instead of `tools_used_json`
- `QuizQuestionRecord.options` is now stored as structured JSON instead of `options_json`

### 4.2 Reusable JSON column type

New file:

- `backend/db/types.py`

This introduces a custom SQLAlchemy type:

- `JSONText`

Purpose:

- Store Python data structures in text columns cleanly
- Avoid manual repetitive serialization logic in each service
- Keep SQLite-friendly behavior while remaining future-portable

### 4.3 Repository layer added

New file:

- `backend/db/repositories.py`

Repositories added:

- `MemoryRepository`
- `EmailDraftRepository`
- `BlackboardCacheRepository`
- `TaskHistoryRepository`
- `UserPreferenceRepository`
- `QuizRepository`
- `DatabaseAnalyticsRepository`

Purpose:

- Move storage logic closer to the database layer
- Reduce service-level coupling to SQL details
- Make future refactors easier

### 4.4 Backward compatibility kept

Updated file:

- `backend/db/crud.py`

Instead of deleting the old access surface entirely, `crud.py` now acts as a compatibility wrapper around the repository layer.  
This reduces breakage while still improving internal structure.

### 4.5 Service layer cleanup

Updated files:

- `backend/services/memory_service.py`
- `backend/services/email_service.py`
- `backend/services/quiz_service.py`
- `backend/services/settings_service.py`
- `backend/services/task_service.py`
- `backend/services/blackboard_service.py`

Main improvements:

- Removed unnecessary manual JSON decoding in service code
- Moved services toward repository-driven access
- Simplified several domain conversion paths
- Fixed quiz history handling to use real booleans instead of string `"false"`

### 4.6 Database overview API added

New file:

- `backend/services/database_insights_service.py`

New model file:

- `backend/models/database.py`

Updated route file:

- `backend/api/routes.py`

New endpoint:

```http
GET /api/database/overview
```

This endpoint exposes:

- table counts
- memory category distribution
- recent task history
- session activity
- latest quiz attempt summary
- schema readiness flags for future database goals

### 4.7 Frontend database visualization added

Updated files:

- `frontend/src/App.vue`
- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/api/client.js`

New file:

- `frontend/src/components/DatabaseOverviewPanel.vue`

What this adds:

- a `Database View` entry inside the settings panel's `Developer / Debug` area
- a panel that displays database summary information from the backend
- a practical demo surface for presenting database improvements

### 4.8 Tests updated and extended

Updated file:

- `tests/test_quiz_service.py`

New file:

- `tests/test_database_insights.py`

What was done:

- fixed outdated LLM mock usage in quiz tests
- added a test for the new database overview service
- verified that the main refactored database paths still work

## 4.9 What The Database Is For In This Project

The database is what makes this project stateful instead of disposable.

It is used to:

- persist task history so the assistant can recover recent context
- persist saved memories so useful user facts and prior results can be reused
- persist quiz sessions and quiz attempts so learning history can be analyzed
- persist email draft state and saved non-secret settings profiles
- support future features such as backend conversation storage and stronger memory retrieval

Without the database, the system behaves more like a one-shot chat demo. With it, the app has continuity, history, and inspectable behavior.

## 5. Why This Refactor Is Better

### Better maintainability

- Data serialization is centralized instead of duplicated
- Repositories isolate SQL behavior from domain services
- Relationships are now more explicit and safer

### Better extensibility

The new structure is much more suitable for adding:

- backend conversation storage
- memory embedding retrieval
- email approval history
- richer analytics or admin-style inspection endpoints

### Better demo value

The new database overview panel gives the team something visible to show in a review, instead of only claiming that the backend is “cleaner”.

## 6. Future Directions Suggested During the Refactor

These are the next best database-facing tasks based on project docs and current structure.

### 6.1 Add conversation tables

Recommended future tables:

- `conversations`
- `conversation_messages`

Reason:

- The docs explicitly mention moving browser-only chat persistence into backend storage
- Current `task_history` is usable, but not ideal as the long-term source of truth

### 6.2 Add memory retrieval upgrades

Recommended future additions:

- embedding field or embedding side-table
- hybrid retrieval support
- ranking metadata

Reason:

- The design document explicitly calls for stronger memory retrieval than keyword matching

### 6.3 Add email approval history

Recommended future additions:

- email approval decision table
- reviewer / timestamp / decision tracking

Reason:

- The proposal and design emphasize human-in-the-loop mail safety

### 6.4 Add migration tooling

Recommended future work:

- Alembic or equivalent migration setup

Reason:

- The schema is now more serious
- Future evolution should not rely only on `create_all`

### 6.5 Improve operational insight

Possible future additions:

- cache freshness metrics
- per-session tool usage stats
- memory growth trends
- quiz performance trend charts

## 7. Files Added or Changed

### New files

- `backend/db/types.py`
- `backend/db/repositories.py`
- `backend/models/database.py`
- `backend/services/database_insights_service.py`
- `frontend/src/components/DatabaseOverviewPanel.vue`
- `tests/test_database_insights.py`
- `DATABASE_REFACTOR_SUMMARY.md`

### Updated files

- `backend/api/routes.py`
- `backend/db/crud.py`
- `backend/db/models.py`
- `backend/services/blackboard_service.py`
- `backend/services/email_service.py`
- `backend/services/memory_service.py`
- `backend/services/quiz_service.py`
- `backend/services/settings_service.py`
- `backend/services/task_service.py`
- `frontend/src/App.vue`
- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/api/client.js`
- `tests/test_quiz_service.py`

## 8. How to Inspect the Changes

### 8.1 Confirm current branch

```bash
git branch --show-current
```

Expected:

```bash
feat-db-refactor-foundation
```

### 8.2 See changed files

```bash
git status
```

### 8.3 View all code changes

```bash
git diff
```

### 8.4 View only database model changes

```bash
git diff -- backend/db/models.py
```

### 8.5 View the new repository layer

```bash
git diff -- backend/db/repositories.py
```

### 8.6 View the new database overview API

```bash
git diff -- backend/api/routes.py backend/services/database_insights_service.py backend/models/database.py
```

### 8.7 View the new frontend database panel

```bash
git diff -- frontend/src/App.vue frontend/src/api/client.js frontend/src/components/DatabaseOverviewPanel.vue
```

## 9. How to Run the Project and See the New Database Work

### 9.1 Start backend

From the repository root:

```bash
uv run uvicorn backend.main:app --reload
```

### 9.2 Start frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

### 9.3 Open the app

Open the frontend URL shown by Vite, usually:

```text
http://127.0.0.1:5173
```

### 9.4 Open the database visualization

In the app:

1. Launch the frontend
2. Make sure backend is running
3. Click `Configure APIs`
4. In the `Developer / Debug` section, click `Open Database View`
4. Inspect:
   - table counts
   - memory categories
   - recent task history
   - session activity
   - latest quiz attempt
   - schema readiness

### 9.5 Direct backend inspection without the frontend

Useful URLs:

- `http://127.0.0.1:8000/api/database/overview`
- `http://127.0.0.1:8000/docs`

The `/docs` page is often enough for debugging or demos, even if the database panel is hidden from normal users.

### 9.6 Generate some data first if needed

If the panel is mostly empty, create data through the app first:

- use the chat window
- save some memory via tools or memory features
- create a quiz
- submit a quiz attempt
- save LLM profiles in settings

Then reopen `Database View`.

## 10. How to Query the New Database Overview Directly

You can call the API directly after starting the backend.

### Browser

Open:

```text
http://127.0.0.1:8000/api/database/overview
```

### FastAPI docs

Open:

```text
http://127.0.0.1:8000/docs
```

### PowerShell

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/database/overview
```

### curl

```bash
curl http://127.0.0.1:8000/api/database/overview
```

## 11. How to Run the Relevant Tests

Recommended command:

```bash
uv run pytest tests\test_memory.py tests\test_quiz_service.py tests\test_settings_service.py tests\test_database_insights.py
```

The refactor was verified with this targeted test run and it passed.

## 12. Important Notes

### Existing unrelated worktree changes

There were unrelated pre-existing local changes in the repository at the time of this refactor, including:

- `frontend/package-lock.json`
- `package-lock.json`

These were not part of the database refactor itself.

### Current schema evolution limitation

The project still initializes schema through `Base.metadata.create_all(...)`.  
That is acceptable for this course project stage, but proper migration tooling should be added if the schema keeps evolving.

## 13. Short Summary

This refactor changed the database layer from a fragile, mixed-style implementation into a cleaner foundation with:

- better relational modeling
- safer typed JSON handling
- repository-based organization
- improved service integration
- a developer/debug database overview surface
- test coverage for the new overview logic

It also leaves the project in a much better position for the future requirements already described in the project documentation.
