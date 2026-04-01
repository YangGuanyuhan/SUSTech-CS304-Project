"""Email models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class EmailDraft(BaseModel):
    id: str
    to: str
    subject: str
    body: str
    created_at: datetime
    status: Literal["draft", "sent", "cancelled"]


class EmailSummary(BaseModel):
    subject: str
    from_addr: str
    snippet: str
    received_at: datetime


class SendResult(BaseModel):
    draft_id: str
    status: Literal["sent", "blocked"]
    detail: str
