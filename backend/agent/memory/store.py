"""Memory store interface backed by MemoryService."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.models.memory import Memory
from backend.services.memory_service import MemoryService


async def save_memory(
    session: Session,
    key: str,
    value: Any,
    category: str,
    tags: list[str] | None = None,
) -> Memory:
    """Save one memory entry."""

    return await MemoryService(session).save_memory(key, value, category, tags)


async def get_relevant_memories(session: Session, query: str, limit: int = 5) -> list[Memory]:
    """Return relevant memories using keyword matching."""

    return await MemoryService(session).get_relevant_memories(query, limit)


async def delete_memory(session: Session, memory_id: str) -> bool:
    """Delete one memory by id."""

    return await MemoryService(session).delete_memory(memory_id)
