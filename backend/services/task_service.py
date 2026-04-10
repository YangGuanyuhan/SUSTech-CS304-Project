"""Task history service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.db.repositories import TaskHistoryRepository


class TaskHistoryService:
    """Task history accessors."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = TaskHistoryRepository(session)

    async def add_history(
        self, session_id: str, user_input: str, agent_response: str, tools_used: list[str]
    ) -> None:
        self.repository.create(
            session_id=session_id,
            user_input=user_input,
            agent_response=agent_response,
            tools_used=tools_used,
        )

    async def get_recent_messages(self, session_id: str, limit: int = 20) -> list[dict[str, str]]:
        records = self.repository.list_recent(session_id=session_id, limit=limit)
        messages = []
        for record in reversed(records):
            messages.append({"role": "user", "content": record.user_input})
            messages.append({"role": "assistant", "content": record.agent_response})
        return messages
