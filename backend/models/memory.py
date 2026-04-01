"""Memory models."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Memory(BaseModel):
    id: str
    key: str
    value: Any
    category: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)
