"""Backward-compatible CRUD wrappers around repositories."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.db.models import Base
from backend.db.repositories import (
    BlackboardCacheRepository,
    EmailDraftRepository,
    MemoryRepository,
    QuizRepository,
    TaskHistoryRepository,
    UserPreferenceRepository,
)


async def init_db(session: Session) -> None:
    """Placeholder init function kept for compatibility."""

    _ = session


async def create_memory(
    session: Session,
    *,
    key: str,
    value: Any,
    category: str,
    tags: list[str],
    owner_id: str = "local-user",
):
    return MemoryRepository(session).create(
        key=key,
        value=value,
        category=category,
        tags=tags,
        owner_id=owner_id,
    )


async def list_memories(
    session: Session, *, category: str | None = None, owner_id: str = "local-user"
):
    return MemoryRepository(session).list(category=category, owner_id=owner_id)


async def delete_memory(session: Session, memory_id: str, *, owner_id: str = "local-user") -> bool:
    return MemoryRepository(session).delete(memory_id, owner_id=owner_id)


async def create_email_draft(
    session: Session,
    *,
    to_addr: str,
    subject: str,
    body: str,
    owner_id: str = "local-user",
):
    return EmailDraftRepository(session).create(
        to_addr=to_addr, subject=subject, body=body, owner_id=owner_id
    )


async def get_email_draft(session: Session, draft_id: str, *, owner_id: str = "local-user"):
    return EmailDraftRepository(session).get(draft_id, owner_id=owner_id)


async def update_email_draft_status(
    session: Session,
    draft_id: str,
    *,
    status: str,
    sent_at: datetime | None = None,
    owner_id: str = "local-user",
):
    return EmailDraftRepository(session).update_status(
        draft_id,
        status=status,
        sent_at=sent_at,
        owner_id=owner_id,
    )


async def save_blackboard_cache(
    session: Session,
    *,
    endpoint: str,
    cache_key: str,
    data: Any,
    owner_id: str = "local-user",
):
    return BlackboardCacheRepository(session).save(
        endpoint=endpoint,
        cache_key=cache_key,
        data=data,
        owner_id=owner_id,
    )


async def load_blackboard_cache(
    session: Session,
    *,
    endpoint: str,
    cache_key: str,
    owner_id: str = "local-user",
):
    return BlackboardCacheRepository(session).load(
        endpoint=endpoint,
        cache_key=cache_key,
        owner_id=owner_id,
    )


async def add_task_history(
    session: Session,
    *,
    session_id: str,
    user_input: str,
    agent_response: str,
    tools_used: list[str],
    owner_id: str = "local-user",
):
    return TaskHistoryRepository(session).create(
        session_id=session_id,
        user_input=user_input,
        agent_response=agent_response,
        tools_used=tools_used,
        owner_id=owner_id,
    )


async def list_recent_history(
    session: Session,
    *,
    session_id: str,
    limit: int = 20,
    owner_id: str = "local-user",
):
    return TaskHistoryRepository(session).list_recent(
        session_id=session_id, limit=limit, owner_id=owner_id
    )


async def upsert_user_preference(
    session: Session, *, key: str, value: str, owner_id: str = "local-user"
):
    return UserPreferenceRepository(session).upsert(key=key, value=value, owner_id=owner_id)


async def list_user_preferences(
    session: Session, *, key_prefix: str | None = None, owner_id: str = "local-user"
):
    return UserPreferenceRepository(session).list(key_prefix=key_prefix, owner_id=owner_id)


async def delete_user_preference(
    session: Session, *, key: str, owner_id: str = "local-user"
) -> bool:
    return UserPreferenceRepository(session).delete(key=key, owner_id=owner_id)


async def create_quiz_session(
    session: Session,
    *,
    chat_session_id: str,
    title: str,
    topic: str,
    source_material: str | None,
    owner_id: str = "local-user",
):
    return QuizRepository(session).create_session(
        chat_session_id=chat_session_id,
        title=title,
        topic=topic,
        source_material=source_material,
        owner_id=owner_id,
    )


async def create_quiz_questions(
    session: Session, *, quiz_session_id: str, questions: list[dict[str, Any]]
):
    return QuizRepository(session).create_questions(
        quiz_session_id=quiz_session_id, questions=questions
    )


async def get_quiz_session(session: Session, quiz_id: str, *, owner_id: str = "local-user"):
    return QuizRepository(session).get_session(quiz_id, owner_id=owner_id)


async def list_quiz_questions(session: Session, quiz_id: str):
    session_record = QuizRepository(session).get_session(quiz_id)
    return [] if session_record is None else list(session_record.questions)


async def list_recent_quiz_sessions(
    session: Session, *, limit: int = 10, owner_id: str = "local-user"
):
    return QuizRepository(session).list_recent_sessions(limit=limit, owner_id=owner_id)


async def create_quiz_attempt(
    session: Session,
    *,
    quiz_session_id: str,
    score: float,
    total_points: float,
    summary: str,
    owner_id: str = "local-user",
):
    return QuizRepository(session).create_attempt(
        quiz_session_id=quiz_session_id,
        score=score,
        total_points=total_points,
        summary=summary,
        owner_id=owner_id,
    )


async def create_quiz_answers(session: Session, *, attempt_id: str, answers: list[dict[str, Any]]):
    return QuizRepository(session).create_answers(attempt_id=attempt_id, answers=answers)


async def list_recent_quiz_attempts(
    session: Session, *, limit: int = 10, owner_id: str = "local-user"
):
    return QuizRepository(session).list_recent_attempts(limit=limit, owner_id=owner_id)


async def list_quiz_answers_for_attempt(session: Session, attempt_id: str):
    return QuizRepository(session).list_answers_for_attempt(attempt_id)


__all__ = ["Base"]
