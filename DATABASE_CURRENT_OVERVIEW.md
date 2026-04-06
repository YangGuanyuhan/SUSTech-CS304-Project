# Current Database Overview

> Initial draft for the database documentation. This is not the final version.

## 1. Purpose

This is a short current-state guide for the database on branch `dev-pydanticAI`. It is meant for teammates, reviews, and demos.

It focuses on:

- current tables
- how the backend connects to the database
- where Blackboard, quiz, memory, and settings data are stored
- how to inspect the database quickly

## 2. Database Connection

Main files:

- `backend/config.py`
- `backend/db/database.py`
- `backend/db/models.py`
- `backend/main.py`

Connection flow:

1. `backend/config.py` loads `DATABASE_URL` from `.env`
2. `backend/db/database.py` normalizes the SQLite URL and creates the SQLAlchemy engine
3. the same module ensures the database directory exists
4. `backend/main.py` runs `Base.metadata.create_all(bind=engine)` on startup

Default configuration:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/agent.db
```

Default database file:

```text
./data/agent.db
```

## 3. Current Tables

Defined in:

- `backend/db/models.py`

### `memories`

Stores reusable user memory.

Important fields:

- `key`
- `value`
- `category`
- `tags`
- `created_at`

### `email_drafts`

Stores email draft and send status data.

Important fields:

- `to_addr`
- `subject`
- `body`
- `status`
- `sent_at`

### `blackboard_cache`

Stores cached Blackboard data.

Important fields:

- `endpoint`
- `cache_key`
- `data`
- `cached_at`

### `task_history`

Stores recent task and chat history.

Important fields:

- `session_id`
- `user_input`
- `agent_response`
- `tools_used`
- `created_at`

### `user_preferences`

Stores saved preference-like records.

Current example:

- saved LLM profiles

### `quiz_sessions`

Stores one generated quiz session.

### `quiz_questions`

Stores questions belonging to one quiz session.

Important fields:

- `quiz_session_id`
- `position`
- `question_type`
- `prompt`
- `options`
- `correct_answer`

### `quiz_attempts`

Stores one submitted quiz attempt.

### `quiz_answers`

Stores grading results for each answered question in one attempt.

## 4. Current Relationships

The quiz subsystem currently has the clearest relational structure.

Relationships:

- `quiz_sessions` -> `quiz_questions`
- `quiz_sessions` -> `quiz_attempts`
- `quiz_attempts` -> `quiz_answers`
- `quiz_questions` -> `quiz_answers`

Notes:

- foreign keys are present
- quiz data uses cascade delete
- structured fields use typed JSON storage

## 5. Blackboard Integration

Main file:

- `backend/services/blackboard_service.py`

Current environment variables:

```env
BLACKBOARD_STUDENT_ID=replace-with-your-student-id
BLACKBOARD_CAS_PASSWORD=replace-with-your-cas-password
BLACKBOARD_BASE_URL=https://bb.sustech.edu.cn/learn/api/public/v1
BLACKBOARD_TOKEN=replace-me
```

Current database role:

- Blackboard responses can be cached in `blackboard_cache`
- if Blackboard is unavailable, cached data can be returned from the database

## 6. How To Inspect The Database

### Backend API

- `http://127.0.0.1:8000/api/database/overview`
- `http://127.0.0.1:8000/docs`

### Frontend Debug Entry

In the app:

1. click `Configure APIs`
2. open the `Developer / Debug` section
3. click `Open Database View`

Relevant files:

- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/components/DatabaseOverviewPanel.vue`

## 7. Quick Verification

Start backend:

```bash
uv run uvicorn backend.main:app --reload
```

Start frontend:

```bash
cd frontend
npm install
npm run dev
```

Useful test command:

```bash
uv run pytest tests\test_blackboard.py tests\test_database_insights.py tests\test_quiz_service.py
```

## 8. Collaboration Note

Branching and commit rules are documented separately in `CONTRIBUTING.md`.

---

# 当前数据库说明

> 数据库说明初稿，不代表最终版本。

## 1. 文档目的

这是一份面向 `dev-pydanticAI` 分支当前状态的简短数据库说明，适合队友协作、课程检查和演示时直接阅读。

重点包括：

- 当前有哪些表
- 后端怎么连接数据库
- Blackboard、Quiz、Memory、Settings 怎么落库
- 怎么快速查看数据库状态

## 2. 数据库连接方式

关键文件：

- `backend/config.py`
- `backend/db/database.py`
- `backend/db/models.py`
- `backend/main.py`

连接流程：

1. `backend/config.py` 从 `.env` 读取 `DATABASE_URL`
2. `backend/db/database.py` 规范化 SQLite URL，并创建 SQLAlchemy `engine`
3. 同一个模块会先确保数据库目录存在
4. `backend/main.py` 在启动时执行 `Base.metadata.create_all(bind=engine)`

默认配置：

```env
DATABASE_URL=sqlite+aiosqlite:///./data/agent.db
```

默认数据库文件：

```text
./data/agent.db
```

## 3. 当前数据表

定义位置：

- `backend/db/models.py`

### `memories`

存储可复用的用户记忆。

关键字段：

- `key`
- `value`
- `category`
- `tags`
- `created_at`

### `email_drafts`

存储邮件草稿和发送状态。

关键字段：

- `to_addr`
- `subject`
- `body`
- `status`
- `sent_at`

### `blackboard_cache`

存储 Blackboard 缓存数据。

关键字段：

- `endpoint`
- `cache_key`
- `data`
- `cached_at`

### `task_history`

存储最近的任务和聊天历史。

关键字段：

- `session_id`
- `user_input`
- `agent_response`
- `tools_used`
- `created_at`

### `user_preferences`

存储用户偏好类记录。

当前例子：

- 保存的 LLM profiles

### `quiz_sessions`

存储一次生成出来的 quiz 会话。

### `quiz_questions`

存储属于某个 quiz session 的题目。

关键字段：

- `quiz_session_id`
- `position`
- `question_type`
- `prompt`
- `options`
- `correct_answer`

### `quiz_attempts`

存储一次 quiz 提交记录。

### `quiz_answers`

存储某次提交里每道题的答案和评分结果。

## 4. 当前表关系

当前关系建模最完整的是 quiz 子系统。

关系：

- `quiz_sessions` -> `quiz_questions`
- `quiz_sessions` -> `quiz_attempts`
- `quiz_attempts` -> `quiz_answers`
- `quiz_questions` -> `quiz_answers`

说明：

- 已经有外键
- quiz 相关记录支持级联删除
- 结构化字段使用 typed JSON 存储

## 5. Blackboard 与数据库

主文件：

- `backend/services/blackboard_service.py`

当前环境变量：

```env
BLACKBOARD_STUDENT_ID=replace-with-your-student-id
BLACKBOARD_CAS_PASSWORD=replace-with-your-cas-password
BLACKBOARD_BASE_URL=https://bb.sustech.edu.cn/learn/api/public/v1
BLACKBOARD_TOKEN=replace-me
```

当前数据库作用：

- Blackboard 的返回结果可以缓存进 `blackboard_cache`
- 如果 Blackboard 不可用，可以从数据库缓存回退读取

## 6. 如何查看数据库

### 后端接口

- `http://127.0.0.1:8000/api/database/overview`
- `http://127.0.0.1:8000/docs`

### 前端调试入口

在前端里：

1. 点击 `Configure APIs`
2. 打开 `Developer / Debug` 区域
3. 点击 `Open Database View`

相关文件：

- `frontend/src/components/SettingsPanel.vue`
- `frontend/src/components/DatabaseOverviewPanel.vue`

## 7. 快速验证

启动后端：

```bash
uv run uvicorn backend.main:app --reload
```

启动前端：

```bash
cd frontend
npm install
npm run dev
```

推荐测试命令：

```bash
uv run pytest tests\test_blackboard.py tests\test_database_insights.py tests\test_quiz_service.py
```

## 8. 协作说明

分支命名、提交粒度和同步要求已经单独写在 `CONTRIBUTING.md` 里，不放进这份数据库说明文档中。
