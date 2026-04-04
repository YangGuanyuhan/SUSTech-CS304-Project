"""Database overview models for operational visibility."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TableCount(BaseModel):
    memories: int
    task_history: int
    quiz_sessions: int
    quiz_attempts: int
    email_drafts: int
    user_preferences: int


class MemoryCategoryStat(BaseModel):
    category: str
    count: int


class RecentHistoryItem(BaseModel):
    id: str
    session_id: str
    created_at: datetime
    user_input_preview: str
    tools_used: list[str]


class SessionActivityStat(BaseModel):
    session_id: str
    message_count: int


class LatestQuizAttempt(BaseModel):
    attempt_id: str
    quiz_session_id: str
    title: str
    topic: str
    score: float
    total_points: float
    submitted_at: datetime


class SchemaReadiness(BaseModel):
    conversation_storage_ready: bool
    memory_embedding_ready: bool
    email_approval_history_ready: bool
    quiz_relationships_ready: bool
    typed_json_ready: bool


class DatabaseOverview(BaseModel):
    counts: TableCount
    memory_categories: list[MemoryCategoryStat]
    recent_history: list[RecentHistoryItem]
    session_activity: list[SessionActivityStat]
    latest_quiz_attempt: LatestQuizAttempt | None = None
    schema_readiness: SchemaReadiness
