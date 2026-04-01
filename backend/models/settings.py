"""Settings-related models."""

from __future__ import annotations

from pydantic import BaseModel


class LLMProfile(BaseModel):
    name: str
    provider: str
    model: str
    base_url: str | None = None
    api_key_configured: bool = False
