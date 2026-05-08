"""Task history service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import TaskHistoryRepository
from backend.services.context_manager import TokenCounter


class TaskHistoryService:
    """Task history accessors."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = TaskHistoryRepository(session)
        self.token_counter = TokenCounter()

    async def add_history(
        self,
        session_id: str,
        user_input: str,
        agent_response: str,
        tools_used: list[str],
        importance_score: float = 1.0,
    ) -> None:
        # Calculate token count for this exchange
        token_count = self.token_counter.count_tokens(user_input) + self.token_counter.count_tokens(
            agent_response
        )

        self.repository.create(
            session_id=session_id,
            user_input=user_input,
            agent_response=agent_response,
            tools_used=tools_used,
            token_count=token_count,
            importance_score=importance_score,
        )

    async def get_recent_messages(
        self, session_id: str, limit: int = 20, max_tokens: int | None = None
    ) -> list[dict[str, str]]:
        """
        Get recent messages, optionally respecting a token budget.

        Args:
            session_id: Session identifier
            limit: Maximum number of message pairs to retrieve
            max_tokens: Optional token budget - will return fewer messages if needed

        Returns:
            List of message dicts with role and content
        """
        records = self.repository.list_recent(session_id=session_id, limit=limit)
        messages = []

        cumulative_tokens = 0
        for record in reversed(records):
            user_msg = {"role": "user", "content": record.user_input}
            assistant_msg = {"role": "assistant", "content": record.agent_response}

            # Check token budget if specified
            if max_tokens is not None:
                msg_tokens = record.token_count
                if cumulative_tokens + msg_tokens > max_tokens:
                    # Would exceed budget, stop here
                    break
                cumulative_tokens += msg_tokens

            messages.append(user_msg)
            messages.append(assistant_msg)

        return messages
