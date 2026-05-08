"""Memory models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MemoryType(str, Enum):
    """Types of long-term memories."""

    USER_PREFERENCE = "user_preference"  # User habits, preferences
    FACTUAL = "factual"  # Facts about courses, assignments
    PROCEDURAL = "procedural"  # How to do things
    EPISODIC = "episodic"  # Past interactions, events
    TOOL_USAGE = "tool_usage"  # Successful tool usage patterns


class Memory(BaseModel):
    """Legacy memory model for backward compatibility."""

    id: str
    key: str
    value: Any
    category: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)


class LongTermMemory(BaseModel):
    """Enhanced long-term memory with semantic search support."""

    id: str
    memory_type: MemoryType
    content: str
    embedding: list[float] | None = None  # For semantic search
    metadata: dict[str, Any] = Field(default_factory=dict)  # Type-specific metadata
    source_session_id: str | None = None
    access_count: int = 0
    last_accessed: datetime
    created_at: datetime
    importance_score: float = 1.0


class ConversationMessage(BaseModel):
    """Enhanced conversation message with token tracking."""

    id: str
    session_id: str
    role: str  # "user", "assistant", "system"
    content: str
    token_count: int = 0  # Estimated token count
    tools_used: list[str] = Field(default_factory=list)
    created_at: datetime
    importance_score: float = 1.0  # For selective retention
