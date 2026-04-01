"""In-memory storage for pending tool approvals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from backend.models.tooling import ToolApprovalRequest, ToolTrace


@dataclass
class PendingApproval:
    id: str
    session_id: str
    user_input: str
    tool_call_id: str
    tool_name: str
    tool_arguments: dict[str, Any]
    summary: str
    workspace_root: str | None
    messages: list[dict[str, Any]]
    tools_used: list[str]
    tool_events: list[ToolTrace]


class ApprovalService:
    """Keep pending approvals in process memory."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def create(
        self,
        *,
        session_id: str,
        user_input: str,
        tool_call_id: str,
        tool_name: str,
        tool_arguments: dict[str, Any],
        summary: str,
        workspace_root: str | None,
        messages: list[dict[str, Any]],
        tools_used: list[str],
        tool_events: list[ToolTrace],
    ) -> ToolApprovalRequest:
        approval_id = str(uuid4())
        pending = PendingApproval(
            id=approval_id,
            session_id=session_id,
            user_input=user_input,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            summary=summary,
            workspace_root=workspace_root,
            messages=messages,
            tools_used=tools_used,
            tool_events=tool_events,
        )
        self._pending[approval_id] = pending
        return ToolApprovalRequest(
            id=approval_id,
            session_id=session_id,
            tool_name=tool_name,
            arguments=tool_arguments,
            summary=summary,
            workspace_root=workspace_root,
        )

    def get(self, approval_id: str) -> PendingApproval | None:
        return self._pending.get(approval_id)

    def pop(self, approval_id: str) -> PendingApproval | None:
        return self._pending.pop(approval_id, None)


approval_service = ApprovalService()
