"""In-memory storage for pending tool approvals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from backend.models.tooling import BatchApprovalRequest, ToolApprovalRequest, ToolTrace


@dataclass
class PendingApproval:
    """Stores pending approval requests for a batch of tool calls."""

    id: str
    session_id: str
    user_input: str
    tool_calls: list[dict[str, Any]]  # List of {tool_call_id, tool_name, tool_arguments, summary}
    workspace_root: str | None
    messages: list[Any]
    tools_used: list[str]
    tool_events: list[ToolTrace]
    deferred_metadata: dict[str, dict[str, Any]] | None = None


class ApprovalService:
    """Keep pending approvals in process memory."""

    def __init__(self) -> None:
        self._pending: dict[str, PendingApproval] = {}

    def create_batch(
        self,
        *,
        session_id: str,
        user_input: str,
        tool_calls: list[dict[str, Any]],
        workspace_root: str | None,
        messages: list[Any],
        tools_used: list[str],
        tool_events: list[ToolTrace],
        deferred_metadata: dict[str, dict[str, Any]] | None = None,
    ) -> BatchApprovalRequest:
        """Create a batch approval request for multiple tool calls."""
        batch_id = str(uuid4())
        pending = PendingApproval(
            id=batch_id,
            session_id=session_id,
            user_input=user_input,
            tool_calls=tool_calls,
            workspace_root=workspace_root,
            messages=messages,
            tools_used=tools_used,
            tool_events=tool_events,
            deferred_metadata=deferred_metadata,
        )
        self._pending[batch_id] = pending

        # Build individual approval requests
        approvals = [
            ToolApprovalRequest(
                id=str(uuid4()),
                session_id=session_id,
                tool_name=tc["tool_name"],
                arguments=tc["tool_arguments"],
                summary=tc["summary"],
                workspace_root=workspace_root,
            )
            for tc in tool_calls
        ]

        # Combined summary for the batch
        combined_summary = f"{len(tool_calls)} tool(s) require approval: " + ", ".join(
            tc["tool_name"] for tc in tool_calls
        )

        return BatchApprovalRequest(
            id=batch_id,
            session_id=session_id,
            approvals=approvals,
            combined_summary=combined_summary,
            workspace_root=workspace_root,
        )

    def get(self, approval_id: str) -> PendingApproval | None:
        return self._pending.get(approval_id)

    def pop(self, approval_id: str) -> PendingApproval | None:
        return self._pending.pop(approval_id, None)


approval_service = ApprovalService()
