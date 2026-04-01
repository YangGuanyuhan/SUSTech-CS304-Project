"""Memory management helpers."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.services.memory_service import MemoryService


async def delete_memories_by_query(session: Session, natural_language_query: str) -> int:
    """Delete memories using simple token matching for V1."""

    return await MemoryService(session).delete_memories_by_query(natural_language_query)
