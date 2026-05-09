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
        deduplicate: bool = True,
    ) -> LongTermMemory:
        """Save a long-term memory.

        Deduplication:
          - If deduplicate is True (default), we check existing memories of the same
            memory_type for near-duplicate content. A duplicate is detected by:
              1) exact content match (case-insensitive), or
              2) high token-overlap (Jaccard >= 0.8) on word-level tokens, or
              3) cosine similarity >= 0.92 if both have real embeddings.
          - On match: we update the existing record (bump importance, refresh
            metadata) instead of inserting a new one.
        """
        clean_content = (content or "").strip()
        if not clean_content:
            raise ValueError("content is required")

        # Try to generate a real embedding (returns None if endpoint can't)
        embedding: list[float] | None = None
        if generate_embedding:
            embedding = await self.embedding_service.generate_embedding(clean_content)

        # Deduplication pass: scan same-type memories
        if deduplicate:
            existing = self.ltm_repository.list(memory_type=memory_type.value)
            duplicate = self._find_duplicate(clean_content, embedding, existing)
            if duplicate is not None:
                # Bump importance up to the new value if it's higher; refresh access
                new_imp = max(duplicate.importance_score, importance_score)
                self.ltm_repository.update_importance(duplicate.id, importance_score=new_imp)
                self.ltm_repository.update_access(duplicate.id)
                refreshed = self.ltm_repository.get(duplicate.id)
                return (
                    _to_long_term_memory(refreshed)
                    if refreshed
                    else _to_long_term_memory(duplicate)
                )

        record = self.ltm_repository.create(
            memory_type=memory_type.value,
            content=clean_content,
            embedding=embedding,
            meta_data=metadata or {},
            source_session_id=source_session_id,
            importance_score=importance_score,
        )
        return _to_long_term_memory(record)

    def _find_duplicate(
        self,
        content: str,
        embedding: list[float] | None,
        candidates: list[Any],
    ) -> Any | None:
        """Return an existing record that is a near-duplicate of `content`, else None."""
        content_lower = content.lower()
        content_tokens = set(self._tokenize(content_lower))
        if not content_tokens:
            return None

        for rec in candidates:
            existing = (rec.content or "").strip().lower()
            if not existing:
                continue
            # 1) exact match
            if existing == content_lower:
                return rec
            # 2) substring containment (one side fully covers the other)
            if content_lower in existing or existing in content_lower:
                return rec
            # 3) token overlap (Jaccard)
            existing_tokens = set(self._tokenize(existing))
            if existing_tokens:
                overlap = len(content_tokens & existing_tokens)
                union = len(content_tokens | existing_tokens)
                if union and (overlap / union) >= 0.8:
                    return rec
            # 4) embedding similarity (only if both sides have real vectors)
            if embedding and rec.embedding:
                try:
                    sim = self.embedding_service.cosine_similarity(embedding, rec.embedding)
                    if sim >= 0.92:
                        return rec
                except Exception:
                    pass
        return None

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """Word-level tokenizer that handles CJK by splitting per character.

        For ASCII we split on whitespace + strip punctuation. For CJK chars
        (no spaces between words) we treat each character as its own token,
        which gives reasonable Jaccard overlap for Chinese phrases.
        """
        import re

        tokens: list[str] = []
        # Pull ASCII words
        for m in re.finditer(r"[a-zA-Z0-9]+", text):
            tokens.append(m.group(0).lower())
        # Pull CJK characters individually
        for ch in text:
            if "一" <= ch <= "鿿":
                tokens.append(ch)
        return tokens

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

    # ----- Synonym table for keyword expansion (CJK + EN) -----
    # Used when real embeddings aren't available, so "我叫什么" can still match
    # "用户的名字叫张治安".
    _SYNONYMS: dict[str, list[str]] = {
        # English -> alternates
        "name": ["called", "named"],
        "my": ["i", "me", "user"],
        "prefer": ["like", "favorite", "favourite"],
        # Chinese: query token -> stored vocabulary it should match
        "我": ["用户", "咱"],
        "用": ["用户"],
        "户": ["用户"],
        "叫": ["名", "称", "姓"],
        "名": ["叫", "称", "姓"],
        "字": ["名", "姓"],
        "称": ["叫", "名"],
        "呼": ["称", "叫"],
        "姓": ["名", "叫"],
        "什": ["啥"],
        "么": ["啥"],
        "喜": ["爱", "好"],
        "欢": ["爱", "好"],
    }

    def _expand_query_tokens(self, query: str) -> set[str]:
        """Tokenize query and expand each token with its synonyms.

        Stripped of obvious stopwords ('the', 'is', 'of', etc.) so they don't
        dominate the match score.
        """
        stopwords = {
            "the",
            "a",
            "an",
            "is",
            "are",
            "was",
            "were",
            "of",
            "to",
            "in",
            "on",
            "at",
            "and",
            "or",
            "but",
            "do",
            "does",
            "did",
            "have",
            "has",
            "had",
            "what",
            "who",
            "how",
            "when",
            "where",
            "是",
            "的",
            "了",
            "吗",
            "呢",
            "啊",
            "哦",
        }
        base = set(self._tokenize(query.lower()))
        base = {t for t in base if t not in stopwords}
        expanded = set(base)
        for tok in base:
            for syn in self._SYNONYMS.get(tok, []):
                expanded.add(syn)
        return expanded

    async def search_long_term_memories(
        self,
        query: str,
        memory_types: list[MemoryType] | None = None,
        limit: int = 5,
        semantic_threshold: float = 0.7,
        use_hybrid: bool = True,
    ) -> list[LongTermMemory]:
        """Search long-term memories.

        Strategy:
          1. Try real embeddings via the configured endpoint.
             - If both query and record have real vectors -> cosine similarity.
             - If embeddings aren't available, this contribution is 0.
          2. Always run keyword overlap with synonym expansion (CJK-aware).
             This is the workhorse when embeddings aren't available, and a
             corrective signal when they are.
          3. Add small recency + importance multiplier so ties break sensibly.
        """
        # Get all memories (filtered by type if specified)
        all_memories: list[Any] = []
        if memory_types:
            for mem_type in memory_types:
                all_memories.extend(self.ltm_repository.list(memory_type=mem_type.value))
        else:
            all_memories = self.ltm_repository.list()

        if not all_memories:
            return []

        # Try to get a real query embedding (None if endpoint unsupported)
        query_embedding = await self.embedding_service.generate_embedding(query)
        embeddings_usable = query_embedding is not None

        # Tokenize+expand query for keyword scoring
        query_token_set = self._expand_query_tokens(query)

        import time

        scored: list[tuple[float, Any]] = []
        for record in all_memories:
            # --- Semantic component (only if both sides have real embeddings) ---
            semantic_score = 0.0
            if embeddings_usable and record.embedding:
                try:
                    semantic_score = self.embedding_service.cosine_similarity(
                        query_embedding, record.embedding
                    )
                except Exception:
                    semantic_score = 0.0

            # --- Keyword component (always) ---
            content_tokens = set(self._tokenize(record.content.lower()))
            if query_token_set and content_tokens:
                overlap = len(query_token_set & content_tokens)
                # Use overlap / |query_tokens| so a long memory doesn't get penalized
                keyword_score = overlap / max(len(query_token_set), 1)
            else:
                keyword_score = 0.0

            # --- Combine ---
            if embeddings_usable:
                combined = 0.6 * semantic_score + 0.4 * keyword_score
            else:
                # Keyword-only mode: don't pretend we have semantic info
                combined = keyword_score

            # Recency boost (decays over a year)
            age_days = (time.time() - record.created_at.timestamp()) / 86400
            recency_boost = max(0.0, 1.0 - (age_days / 365))
            combined += 0.05 * recency_boost

            # Importance multiplier (anchors strong signals)
            combined *= max(0.1, record.importance_score)

            # In keyword-only mode the threshold should be lower
            effective_threshold = (
                semantic_threshold if embeddings_usable else min(semantic_threshold, 0.15)
            )
            if semantic_threshold == 0.0 or combined >= effective_threshold:
                scored.append((combined, record))

        scored.sort(key=lambda x: x[0], reverse=True)

        results: list[LongTermMemory] = []
        for _, record in scored[:limit]:
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
