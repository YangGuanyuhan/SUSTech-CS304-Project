"""Low-level CRUD helpers."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from backend.db.models import (
    Base,
    BlackboardCacheRecord,
    EmailDraftRecord,
    MemoryRecord,
    TaskHistoryRecord,
    UserPreferenceRecord,
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
) -> MemoryRecord:
    """Persist a memory record."""

    record = MemoryRecord(
        owner_id=owner_id,
        key=key,
        value_json=json.dumps(value, ensure_ascii=False),
        category=category,
        tags_json=json.dumps(tags, ensure_ascii=False),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def list_memories(
    session: Session,
    *,
    category: str | None = None,
    owner_id: str = "local-user",
) -> list[MemoryRecord]:
    """List memories, optionally filtered by category."""

    stmt = select(MemoryRecord).where(MemoryRecord.owner_id == owner_id)
    if category:
        stmt = stmt.where(MemoryRecord.category == category)
    stmt = stmt.order_by(MemoryRecord.created_at.desc())
    result = session.execute(stmt)
    return list(result.scalars())


async def delete_memory(session: Session, memory_id: str, *, owner_id: str = "local-user") -> bool:
    """Delete a memory by id."""

    stmt = delete(MemoryRecord).where(MemoryRecord.id == memory_id, MemoryRecord.owner_id == owner_id)
    result = session.execute(stmt)
    session.commit()
    return result.rowcount > 0


async def create_email_draft(
    session: Session,
    *,
    to_addr: str,
    subject: str,
    body: str,
    owner_id: str = "local-user",
) -> EmailDraftRecord:
    """Persist an email draft."""

    record = EmailDraftRecord(owner_id=owner_id, to_addr=to_addr, subject=subject, body=body)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def get_email_draft(
    session: Session,
    draft_id: str,
    *,
    owner_id: str = "local-user",
) -> EmailDraftRecord | None:
    """Fetch a draft by id."""

    stmt = select(EmailDraftRecord).where(
        EmailDraftRecord.id == draft_id,
        EmailDraftRecord.owner_id == owner_id,
    )
    result = session.execute(stmt)
    return result.scalar_one_or_none()


async def update_email_draft_status(
    session: Session,
    draft_id: str,
    *,
    status: str,
    sent_at: datetime | None = None,
    owner_id: str = "local-user",
) -> EmailDraftRecord | None:
    """Update draft status and sent time."""

    draft = await get_email_draft(session, draft_id, owner_id=owner_id)
    if not draft:
        return None
    draft.status = status
    draft.sent_at = sent_at
    session.commit()
    session.refresh(draft)
    return draft


async def save_blackboard_cache(
    session: Session,
    *,
    endpoint: str,
    cache_key: str,
    data: Any,
    owner_id: str = "local-user",
) -> BlackboardCacheRecord:
    """Write a cache entry for Blackboard data."""

    record = BlackboardCacheRecord(
        owner_id=owner_id,
        endpoint=endpoint,
        cache_key=cache_key,
        data_json=json.dumps(data, ensure_ascii=False),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def load_blackboard_cache(
    session: Session,
    *,
    endpoint: str,
    cache_key: str,
    owner_id: str = "local-user",
) -> BlackboardCacheRecord | None:
    """Load the newest cache entry for an endpoint/key pair."""

    stmt = (
        select(BlackboardCacheRecord)
        .where(
            BlackboardCacheRecord.owner_id == owner_id,
            BlackboardCacheRecord.endpoint == endpoint,
            BlackboardCacheRecord.cache_key == cache_key,
        )
        .order_by(BlackboardCacheRecord.cached_at.desc())
    )
    result = session.execute(stmt)
    return result.scalars().first()


async def add_task_history(
    session: Session,
    *,
    session_id: str,
    user_input: str,
    agent_response: str,
    tools_used: list[str],
    owner_id: str = "local-user",
) -> TaskHistoryRecord:
    """Store a task history item."""

    record = TaskHistoryRecord(
        owner_id=owner_id,
        session_id=session_id,
        user_input=user_input,
        agent_response=agent_response,
        tools_used_json=json.dumps(tools_used, ensure_ascii=False),
    )
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def list_recent_history(
    session: Session,
    *,
    session_id: str,
    limit: int = 20,
    owner_id: str = "local-user",
) -> list[TaskHistoryRecord]:
    """Load recent task history for one chat session."""

    stmt = (
        select(TaskHistoryRecord)
        .where(TaskHistoryRecord.owner_id == owner_id, TaskHistoryRecord.session_id == session_id)
        .order_by(TaskHistoryRecord.created_at.desc())
        .limit(limit)
    )
    result = session.execute(stmt)
    return list(result.scalars())


async def upsert_user_preference(
    session: Session,
    *,
    key: str,
    value: str,
    owner_id: str = "local-user",
) -> UserPreferenceRecord:
    """Create or update a user preference entry."""

    stmt = select(UserPreferenceRecord).where(
        UserPreferenceRecord.owner_id == owner_id,
        UserPreferenceRecord.key == key,
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing:
        existing.value = value
        session.commit()
        session.refresh(existing)
        return existing

    record = UserPreferenceRecord(owner_id=owner_id, key=key, value=value)
    session.add(record)
    session.commit()
    session.refresh(record)
    return record


async def list_user_preferences(
    session: Session,
    *,
    key_prefix: str | None = None,
    owner_id: str = "local-user",
) -> list[UserPreferenceRecord]:
    """List preferences, optionally filtered by key prefix."""

    stmt = select(UserPreferenceRecord).where(UserPreferenceRecord.owner_id == owner_id)
    if key_prefix:
        stmt = stmt.where(UserPreferenceRecord.key.like(f"{key_prefix}%"))
    stmt = stmt.order_by(UserPreferenceRecord.updated_at.desc())
    result = session.execute(stmt)
    return list(result.scalars())


async def delete_user_preference(session: Session, *, key: str, owner_id: str = "local-user") -> bool:
    """Delete one user preference by exact key."""

    stmt = delete(UserPreferenceRecord).where(
        UserPreferenceRecord.owner_id == owner_id,
        UserPreferenceRecord.key == key,
    )
    result = session.execute(stmt)
    session.commit()
    return result.rowcount > 0


__all__ = ["Base"]
