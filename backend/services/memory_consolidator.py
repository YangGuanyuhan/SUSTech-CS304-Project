"""Memory lifecycle management - consolidation, pruning, and automatic creation."""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from backend.models.memory import LongTermMemory, MemoryType
from backend.services.embedding_service import EmbeddingService
from backend.services.memory_service import MemoryService


class MemoryConsolidator:
    """Manage memory lifecycle: consolidation, pruning, and automatic creation."""

    def __init__(self, session: Session):
        self.session = session
        self.memory_service = MemoryService(session)
        self.embedding_service = EmbeddingService()

    async def consolidate_similar_memories(
        self, similarity_threshold: float = 0.95, max_age_days: int = 30
    ) -> int:
        """
        Consolidate very similar memories to reduce duplication.

        Args:
            similarity_threshold: Minimum similarity to consider consolidation
            max_age_days: Only consolidate memories newer than this

        Returns:
            Number of memories consolidated
        """
        # Get recent memories
        cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)
        all_memories = await self.memory_service.list_long_term_memories(limit=1000)

        # Filter by age (handle both timezone-aware and naive datetimes)
        recent_memories = []
        for m in all_memories:
            mem_created = m.created_at
            if mem_created.tzinfo is None:
                # Make naive datetime timezone-aware
                mem_created = mem_created.replace(tzinfo=UTC)
            if mem_created >= cutoff_date:
                recent_memories.append(m)

        if len(recent_memories) < 2:
            return 0

        consolidated_count = 0

        # Compare memories pairwise
        for i, mem1 in enumerate(recent_memories):
            if not mem1.embedding:
                continue

            for mem2 in recent_memories[i + 1 :]:
                if not mem2.embedding:
                    continue

                # Calculate similarity
                similarity = self.embedding_service.cosine_similarity(
                    mem1.embedding, mem2.embedding
                )

                if similarity >= similarity_threshold:
                    # Merge memories - keep the one with higher importance
                    if mem1.importance_score >= mem2.importance_score:
                        # Update mem1 with combined access count
                        # Delete mem2
                        await self.memory_service.delete_long_term_memory(mem2.id)
                        consolidated_count += 1
                    else:
                        await self.memory_service.delete_long_term_memory(mem1.id)
                        consolidated_count += 1
                        break  # mem1 is deleted, move to next

        return consolidated_count

    async def prune_old_memories(
        self, max_age_days: int = 365, min_access_count: int = 0, max_memories: int = 5000
    ) -> int:
        """
        Prune old, rarely accessed memories.

        Args:
            max_age_days: Delete memories older than this
            min_access_count: Only delete if access count is below this
            max_memories: Keep at most this many memories

        Returns:
            Number of memories pruned
        """
        all_memories = await self.memory_service.list_long_term_memories(limit=None)

        if len(all_memories) <= max_memories:
            # Under budget, only prune very old ones
            cutoff_date = datetime.now(UTC) - timedelta(days=max_age_days)
            to_delete = [
                m
                for m in all_memories
                if m.created_at < cutoff_date and m.access_count <= min_access_count
            ]
        else:
            # Over budget, need to prune more aggressively
            # Sort by score: (access_count * importance_score) / age_days
            scored_memories = []
            now = time.time()

            for mem in all_memories:
                age_days = (now - mem.created_at.timestamp()) / 86400
                score = (mem.access_count * mem.importance_score) / max(age_days, 1)
                scored_memories.append((score, mem))

            # Sort by score (ascending) and delete lowest scoring
            scored_memories.sort(key=lambda x: x[0])
            to_delete = [mem for _, mem in scored_memories[: len(all_memories) - max_memories]]

        # Delete selected memories
        deleted_count = 0
        for mem in to_delete:
            if await self.memory_service.delete_long_term_memory(mem.id):
                deleted_count += 1

        return deleted_count

    async def extract_memory_from_conversation(
        self, user_input: str, agent_response: str, session_id: str
    ) -> list[LongTermMemory]:
        """
        Automatically extract important information from conversation and create memories.

        Args:
            user_input: User's message
            agent_response: Agent's response
            session_id: Session ID

        Returns:
            List of created memories
        """
        created_memories = []

        # Extract user preferences
        preference_keywords = ["prefer", "like", "favorite", "always", "never", "usually"]
        if any(keyword in user_input.lower() for keyword in preference_keywords):
            # This might be a preference
            memory = await self.memory_service.save_long_term_memory(
                content=f"User stated: {user_input}",
                memory_type=MemoryType.USER_PREFERENCE,
                metadata={"extracted_from": "conversation", "agent_response": agent_response[:200]},
                source_session_id=session_id,
                importance_score=0.8,
                generate_embedding=True,
            )
            created_memories.append(memory)

        # Extract procedural knowledge (how-to)
        procedural_keywords = ["how to", "how do i", "steps to", "process for", "way to"]
        if any(keyword in user_input.lower() for keyword in procedural_keywords):
            # This is a how-to question, save the answer
            memory = await self.memory_service.save_long_term_memory(
                content=f"Q: {user_input}\nA: {agent_response[:500]}",
                memory_type=MemoryType.PROCEDURAL,
                metadata={"question": user_input, "extracted_from": "conversation"},
                source_session_id=session_id,
                importance_score=0.7,
                generate_embedding=True,
            )
            created_memories.append(memory)

        # Extract important facts
        fact_keywords = ["remember that", "important", "deadline", "due date", "meeting"]
        if any(keyword in user_input.lower() for keyword in fact_keywords):
            memory = await self.memory_service.save_long_term_memory(
                content=user_input,
                memory_type=MemoryType.FACTUAL,
                metadata={"extracted_from": "conversation", "context": agent_response[:200]},
                source_session_id=session_id,
                importance_score=0.9,
                generate_embedding=True,
            )
            created_memories.append(memory)

        return created_memories

    async def update_memory_importance(self) -> int:
        """
        Update importance scores based on access patterns.

        Frequently accessed memories get higher importance.

        Returns:
            Number of memories updated
        """
        all_memories = await self.memory_service.list_long_term_memories(limit=None)

        updated_count = 0
        for mem in all_memories:
            # Calculate new importance based on access count
            # More accesses = higher importance
            if mem.access_count > 10:
                new_importance = min(1.0, 0.5 + (mem.access_count / 100))
            elif mem.access_count > 5:
                new_importance = 0.8
            elif mem.access_count > 2:
                new_importance = 0.7
            else:
                new_importance = mem.importance_score  # Keep original

            # Persist if changed by a meaningful margin
            if abs(new_importance - mem.importance_score) > 0.05:
                if self.memory_service.ltm_repository.update_importance(
                    mem.id, importance_score=new_importance
                ):
                    updated_count += 1

        return updated_count

    async def run_maintenance(
        self,
        consolidate: bool = True,
        prune: bool = True,
        update_importance: bool = True,
    ) -> dict[str, int]:
        """
        Run all maintenance tasks.

        Args:
            consolidate: Whether to consolidate similar memories
            prune: Whether to prune old memories
            update_importance: Whether to update importance scores

        Returns:
            Dict with counts of operations performed
        """
        results = {
            "consolidated": 0,
            "pruned": 0,
            "importance_updated": 0,
        }

        if consolidate:
            results["consolidated"] = await self.consolidate_similar_memories()

        if prune:
            results["pruned"] = await self.prune_old_memories()

        if update_importance:
            results["importance_updated"] = await self.update_memory_importance()

        return results
