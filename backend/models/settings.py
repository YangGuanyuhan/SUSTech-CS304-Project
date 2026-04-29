"""Settings-related models."""

from __future__ import annotations

from pydantic import BaseModel


class LLMProfile(BaseModel):
    name: str
    provider: str
    model: str
    base_url: str | None = None
    api_key_configured: bool = False
    enable_reasoning: bool = False


class BlackboardProfile(BaseModel):
    name: str
    student_id: str
    base_url: str | None = None
    password_configured: bool = False
