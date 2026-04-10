"""Memory application service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.db.repositories import MemoryRepository
from backend.models.memory import Memory


def _to_memory(record: Any) -> Memory:
    return Memory(
        id=record.id,
        key=record.key,
        value=record.value,
        category=record.category,
        created_at=record.created_at,
        tags=record.tags or [],
    )


class MemoryService:
    """High-level memory operations."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = MemoryRepository(session)

    async def save_memory(
        self, key: str, value: Any, category: str, tags: list[str] | None = None
    ) -> Memory:
        record = self.repository.create(
            key=key,
            value=value,
            category=category,
            tags=tags or [],
        )
        return _to_memory(record)

    async def list_memories(self, category: str | None = None) -> list[Memory]:
        records = self.repository.list(category=category)
        return [_to_memory(record) for record in records]

    async def get_relevant_memories(self, query: str, limit: int = 5) -> list[Memory]:
        records = self.repository.list()
        lowered_terms = [term for term in query.lower().split() if term]
        ranked = []
        for record in records:
            haystack = f"{record.key} {record.category} {record.value} {' '.join(record.tags or [])}".lower()
            score = sum(1 for term in lowered_terms if term in haystack)
            if score:
                ranked.append((score, record))
        ranked.sort(key=lambda item: (-item[0], item[1].created_at), reverse=False)
        return [_to_memory(record) for _, record in ranked[:limit]]

    async def delete_memory(self, memory_id: str) -> bool:
        return self.repository.delete(memory_id)

    async def delete_memories_by_query(self, natural_language_query: str) -> int:
        memories = await self.list_memories()
        lowered = natural_language_query.lower()
        deleted = 0
        for memory in memories:
            text = f"{memory.key} {memory.category} {' '.join(memory.tags)} {memory.value}".lower()
            if any(token in text for token in lowered.split()):
                if await self.delete_memory(memory.id):
                    deleted += 1
        return deleted
