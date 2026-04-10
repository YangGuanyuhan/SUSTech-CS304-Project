"""Calendar models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


CalendarEventSource = Literal["local", "blackboard"]
CalendarEventStatus = Literal["not_started", "pending", "completed"]


class CalendarEvent(BaseModel):
    id: str
    event_id: str
    title: str
    description: str | None = None
    location: str | None = None
    start_at: datetime
    end_at: datetime
    all_day: bool = False
    timezone: str = "UTC"
    source: CalendarEventSource = "local"
    status: CalendarEventStatus = "not_started"
    source_event_id: str | None = None
    is_read_only: bool = False
    source_payload: dict[str, Any] | None = None


class CalendarEventCreate(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    description: str | None = None
    location: str | None = None
    all_day: bool = False
    timezone: str = "UTC"
    status: CalendarEventStatus = "not_started"


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    description: str | None = None
    location: str | None = None
    all_day: bool | None = None
    timezone: str | None = None
    status: CalendarEventStatus | None = None

class CalendarEventMove(BaseModel):
    start_at: datetime
    end_at: datetime


class CalendarEventList(BaseModel):
    start: datetime
    end: datetime
    events: list[CalendarEvent] = Field(default_factory=list)


class CalendarSyncResult(BaseModel):
    synced: int = 0
    created: int = 0
    updated: int = 0
