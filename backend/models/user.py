"""User profile models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    avatar_url: str | None = None
    created_at: datetime
    updated_at: datetime


class LoginResult(BaseModel):
    token: str
    profile: UserProfile
