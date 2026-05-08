"""Memory application service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.db.repositories import LongTermMemoryRepository, MemoryRepository
from backend.models.memory import LongTermMemory, Memory, MemoryType
from backend.services.embedding_service import EmbeddingService


def _to_memory(record: Any) -> Memory:
    return Memory(
        id=record.id,
        key=record.key,
        value=record.value,
        category=record.category,
        created_at=record.created_at,
        tags=record.tags or [],
    )


def _to_long_term_memory(record: Any) -> LongTermMemory:
    return LongTermMemory(
        id=record.id,
        memory_type=MemoryType(record.memory_type),
        content=record.content,
        embedding=record.embedding,
        metadata=record.meta_data or {},
        source_session_id=record.source_session_id,
        access_count=record.access_count,
        last_accessed=record.last_accessed,
        created_at=record.created_at,
        importance_score=record.importance_score,
    )


class MemoryService:
    """High-level memory operations."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = MemoryRepository(session)
        self.ltm_repository = LongTermMemoryRepository(session)
        self.embedding_service = EmbeddingService()

    async def save_memory(
        self, key: str, value: Any, category: str, tags: list[str] | None = None
    ) -> Memory:
        """Save a legacy memory (backward compatibility)."""
        record = self.repository.create(
            key=key,
            value=value,
            category=category,
            tags=tags or [],
        )
        return _to_memory(record)

    async def save_long_term_memory(
        self,
        content: str,
        memory_type: MemoryType,
        metadata: dict[str, Any] | None = None,
        source_session_id: str | None = None,
        importance_score: float = 1.0,
        generate_embedding: bool = True,
    ) -> LongTermMemory:
        """
        Save a long-term memory with optional embedding generation.

        Args:
            content: Memory content
            memory_type: Type of memory
            metadata: Additional metadata
            source_session_id: Source session ID
            importance_score: Importance score (0-1)
            generate_embedding: Whether to generate embedding

        Returns:
            Created LongTermMemory
        """
        embedding = None
        if generate_embedding:
            try:
                embedding = await self.embedding_service.generate_embedding(content)
            except Exception as e:
                # Log but don't fail if embedding generation fails
                print(f"Warning: Failed to generate embedding: {e}")

        record = self.ltm_repository.create(
            memory_type=memory_type.value,
            content=content,
            embedding=embedding,
            meta_data=metadata or {},
            source_session_id=source_session_id,
            importance_score=importance_score,
        )
        return _to_long_term_memory(record)

    async def list_memories(self, category: str | None = None) -> list[Memory]:
        """List legacy memories."""
        records = self.repository.list(category=category)
        return [_to_memory(record) for record in records]

    async def list_long_term_memories(
        self, memory_type: MemoryType | None = None, limit: int | None = None
    ) -> list[LongTermMemory]:
        """List long-term memories."""
        records = self.ltm_repository.list(
            memory_type=memory_type.value if memory_type else None, limit=limit
        )
        return [_to_long_term_memory(record) for record in records]

    async def get_relevant_memories(self, query: str, limit: int = 5) -> list[Memory]:
        """Get relevant legacy memories using keyword matching."""
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

    async def search_long_term_memories(
        self,
        query: str,
        memory_types: list[MemoryType] | None = None,
        limit: int = 5,
        semantic_threshold: float = 0.7,
        use_hybrid: bool = True,
    ) -> list[LongTermMemory]:
        """
        Search long-term memories using hybrid semantic + keyword search.

        Args:
            query: Search query
            memory_types: Filter by memory types
            limit: Maximum results to return
            semantic_threshold: Minimum similarity score for semantic search
            use_hybrid: Whether to combine semantic and keyword search

        Returns:
            List of relevant memories, sorted by relevance
        """
        # Get all memories (filtered by type if specified)
        all_memories = []
        if memory_types:
            for mem_type in memory_types:
                records = self.ltm_repository.list(memory_type=mem_type.value)
                all_memories.extend(records)
        else:
            all_memories = self.ltm_repository.list()

        if not all_memories:
            return []

        # Generate query embedding
        try:
            query_embedding = await self.embedding_service.generate_embedding(query)
        except Exception as e:
            # Fall back to keyword search only
            return await self._keyword_search_ltm(query, all_memories, limit)

        # Calculate semantic similarity scores
        scored_memories = []
        query_terms = query.lower().split()

        for record in all_memories:
            # Semantic similarity
            semantic_score = 0.0
            if record.embedding:
                try:
                    semantic_score = self.embedding_service.cosine_similarity(
                        query_embedding, record.embedding
                    )
                except Exception:
                    semantic_score = 0.0

            # Keyword matching score
            keyword_score = 0.0
            if use_hybrid:
                content_lower = record.content.lower()
                keyword_score = sum(1 for term in query_terms if term in content_lower) / max(
                    len(query_terms), 1
                )

            # Combined score (weighted average)
            if use_hybrid:
                combined_score = 0.7 * semantic_score + 0.3 * keyword_score
            else:
                combined_score = semantic_score

            # Apply recency boost (newer memories get slight boost)
            import time

            age_seconds = time.time() - record.created_at.timestamp()
            age_days = age_seconds / 86400
            recency_boost = max(0, 1.0 - (age_days / 365))  # Decay over a year
            combined_score += 0.1 * recency_boost

            # Apply importance score
            combined_score *= record.importance_score

            # For testing/debugging: always include if threshold is 0
            if semantic_threshold == 0.0 or combined_score >= semantic_threshold:
                scored_memories.append((combined_score, record))

        # Sort by score and return top results
        scored_memories.sort(key=lambda x: x[0], reverse=True)

        # Update access counts for returned memories
        results = []
        for score, record in scored_memories[:limit]:
            self.ltm_repository.update_access(record.id)
            results.append(_to_long_term_memory(record))

        return results

    async def _keyword_search_ltm(
        self, query: str, memories: list[Any], limit: int
    ) -> list[LongTermMemory]:
        """Fallback keyword search for long-term memories."""
        query_terms = query.lower().split()
        scored = []

        for record in memories:
            content_lower = record.content.lower()
            score = sum(1 for term in query_terms if term in content_lower)
            if score > 0:
                scored.append((score, record))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [_to_long_term_memory(record) for _, record in scored[:limit]]

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a legacy memory."""
        return self.repository.delete(memory_id)

    async def delete_long_term_memory(self, memory_id: str) -> bool:
        """Delete a long-term memory."""
        return self.ltm_repository.delete(memory_id)

    async def delete_memories_by_query(self, natural_language_query: str) -> int:
        """Delete legacy memories matching a query."""
        memories = await self.list_memories()
        lowered = natural_language_query.lower()
        deleted = 0
        for memory in memories:
            text = f"{memory.key} {memory.category} {' '.join(memory.tags)} {memory.value}".lower()
            if any(token in text for token in lowered.split()):
                if await self.delete_memory(memory.id):
                    deleted += 1
        return deleted
