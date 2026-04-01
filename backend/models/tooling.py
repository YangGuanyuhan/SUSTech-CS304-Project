"""Tooling and approval models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class ToolApprovalRequest(BaseModel):
    id: str
    session_id: str
    tool_name: str
    arguments: dict[str, Any]
    summary: str
    workspace_root: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentTurnResult(BaseModel):
    response: str = ""
    tools_used: list[str] = Field(default_factory=list)
    approval_request: ToolApprovalRequest | None = None
