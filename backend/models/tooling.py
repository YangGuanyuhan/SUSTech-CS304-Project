"""Tooling and approval models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class ToolApprovalRequest(BaseModel):
    id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    workspace_root: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchApprovalRequest(BaseModel):
    """Batch of pending tool approvals for the same user request."""

    id: str
    session_id: str
    approvals: list[ToolApprovalRequest]
    combined_summary: str
    workspace_root: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolTrace(BaseModel):
    tool_name: str
    arguments: dict[str, Any]
    status: str
    output: str | None = None


class AgentTurnResult(BaseModel):
    response: str = ""
    thinking: str | None = None
    tools_used: list[str] = Field(default_factory=list)
    tool_events: list[ToolTrace] = Field(default_factory=list)
    approval_request: BatchApprovalRequest | None = None
