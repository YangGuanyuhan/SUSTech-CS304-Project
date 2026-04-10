"""Calendar application service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from backend.db.repositories import CalendarRepository
from backend.models.calendar import (
    CalendarEvent,
    CalendarEventCreate,
    CalendarEventList,
    CalendarEventMove,
    CalendarEventUpdate,
    CalendarSyncResult,
)
from backend.services.blackboard_service import DemoBlackboardProvider
from backend.services.runtime_settings import runtime_settings


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _default_status_for_window(start_at: datetime, end_at: datetime) -> str:
    now = datetime.now(timezone.utc)
    if end_at < now:
        return "completed"
    if start_at <= now <= end_at:
        return "pending"
    return "not_started"


class CalendarService:
    """Manage persisted calendar events and Blackboard sync."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = CalendarRepository(session)

    def _to_event(
        self,
        record: Any,
        *,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        occurrence_id: str | None = None,
    ) -> CalendarEvent:
        recurrence_rule = record.recurrence_rule or {}
        return CalendarEvent(
            id=occurrence_id or record.id,
            event_id=record.id,
            title=record.title,
            description=record.description,
            location=record.location,
            start_at=_ensure_aware(start_at or record.start_at),
            end_at=_ensure_aware(end_at or record.end_at),
            all_day=record.all_day,
            timezone=record.timezone or "UTC",
            source=record.source,
            status=record.status or "not_started",
            source_event_id=record.source_event_id,
            is_read_only=record.is_read_only,
            source_payload=record.source_payload if isinstance(record.source_payload, dict) else None,
        )

    def _validate_time_range(self, start_at: datetime, end_at: datetime) -> tuple[datetime, datetime]:
        normalized_start = _ensure_aware(start_at)
        normalized_end = _ensure_aware(end_at)
        if normalized_end < normalized_start:
            raise ValueError("Event end time must be after start time.")
        return normalized_start, normalized_end

    def _ensure_editable_event(self, event_id: str):
        record = self.repository.get(event_id)
        if record is None:
            raise ValueError("Calendar event not found.")
        return record

    def _expand_record(
        self,
        record: Any,
        *,
        range_start: datetime,
        range_end: datetime,
    ) -> list[CalendarEvent]:
        event_start = _ensure_aware(record.start_at)
        event_end = _ensure_aware(record.end_at)
        recurrence_rule = record.recurrence_rule or {}
        if not isinstance(recurrence_rule, dict) or recurrence_rule.get("freq") != "weekly":
            if event_start > range_end or event_end < range_start:
                return []
            return [self._to_event(record, start_at=event_start, end_at=event_end)]

        duration = event_end - event_start
        if duration < timedelta(0):
            return []
        week = timedelta(days=7)
        occurrence_start = event_start
        while occurrence_start + duration < range_start:
            occurrence_start += week

        events: list[CalendarEvent] = []
        while occurrence_start <= range_end:
            occurrence_end = occurrence_start + duration
            if occurrence_end >= range_start:
                occurrence_id = f"{record.id}::{occurrence_start.date().isoformat()}"
                events.append(
                    self._to_event(
                        record,
                        start_at=occurrence_start,
                        end_at=occurrence_end,
                        occurrence_id=occurrence_id,
                    )
                )
            occurrence_start += week
        return events

    def _parse_blackboard_datetime(self, raw_value: Any) -> datetime | None:
        if not isinstance(raw_value, str) or not raw_value.strip():
            return None
        normalized = raw_value.strip().replace("Z", "+00:00")
        try:
            return _ensure_aware(datetime.fromisoformat(normalized))
        except ValueError:
            return None

    def _blackboard_provider(self) -> DemoBlackboardProvider:
        bb_config = runtime_settings.get_blackboard_config()
        password = runtime_settings.get_secret_blackboard_password()
        return DemoBlackboardProvider(
            student_id=bb_config.student_id,
            password=password,
            base_url=bb_config.base_url,
        )

    async def list_events(
        self,
        *,
        start: datetime,
        end: datetime,
        include_blackboard: bool = True,
    ) -> CalendarEventList:
        range_start, range_end = self._validate_time_range(start, end)
        records = self.repository.list_candidates(
            range_start=range_start,
            range_end=range_end,
            include_blackboard=include_blackboard,
        )
        events: list[CalendarEvent] = []
        for record in records:
            events.extend(self._expand_record(record, range_start=range_start, range_end=range_end))
        events.sort(key=lambda item: (item.start_at, item.end_at, item.title.lower()))
        return CalendarEventList(start=range_start, end=range_end, events=events)

    async def create_event(self, payload: CalendarEventCreate) -> CalendarEvent:
        start_at, end_at = self._validate_time_range(payload.start_at, payload.end_at)
        record = self.repository.create(
            title=payload.title.strip(),
            description=payload.description,
            location=payload.location,
            start_at=start_at,
            end_at=end_at,
            all_day=payload.all_day,
            timezone=payload.timezone,
            status=payload.status,
            recurrence_rule=None,
        )
        return self._to_event(record)

    async def update_event(self, event_id: str, payload: CalendarEventUpdate) -> CalendarEvent:
        record = self._ensure_editable_event(event_id)
        mutable_fields = (
            payload.title is not None
            or payload.start_at is not None
            or payload.end_at is not None
            or payload.description is not None
            or payload.location is not None
            or payload.all_day is not None
            or payload.timezone is not None
        )
        if (record.source != "local" or record.is_read_only) and mutable_fields:
            raise ValueError("Only the status field can be modified for Blackboard events.")
        if payload.title is not None:
            record.title = payload.title.strip()
        if payload.description is not None:
            record.description = payload.description
        if payload.location is not None:
            record.location = payload.location
        if payload.all_day is not None:
            record.all_day = payload.all_day
        if payload.timezone is not None:
            record.timezone = payload.timezone
        start_at = payload.start_at or record.start_at
        end_at = payload.end_at or record.end_at
        record.start_at, record.end_at = self._validate_time_range(start_at, end_at)
        if payload.status is not None:
            record.status = payload.status
        updated = self.repository.update(record)
        return self._to_event(updated)

    async def move_event(self, event_id: str, payload: CalendarEventMove) -> CalendarEvent:
        record = self._ensure_editable_event(event_id)
        if record.source != "local" or record.is_read_only:
            raise ValueError("Only local calendar events can be moved.")
        record.start_at, record.end_at = self._validate_time_range(payload.start_at, payload.end_at)
        updated = self.repository.update(record)
        return self._to_event(updated)

    async def delete_event(self, event_id: str) -> bool:
        record = self._ensure_editable_event(event_id)
        if record.source != "local" or record.is_read_only:
            raise ValueError("Only local calendar events can be deleted.")
        self.repository.delete(record)
        return True

    async def clone_blackboard_event(self, event_id: str) -> CalendarEvent:
        record = self.repository.get(event_id)
        if record is None:
            raise ValueError("Calendar event not found.")
        if record.source != "blackboard":
            raise ValueError("Only Blackboard events can be copied into local calendar.")
        clone = self.repository.create(
            title=record.title,
            description=record.description,
            location=record.location,
            start_at=_ensure_aware(record.start_at),
            end_at=_ensure_aware(record.end_at),
            all_day=record.all_day,
            timezone=record.timezone,
            source="local",
            status=record.status or "not_started",
            source_payload=record.source_payload,
            is_read_only=False,
            recurrence_rule=record.recurrence_rule,
        )
        return self._to_event(clone)

    async def sync_blackboard(self) -> CalendarSyncResult:
        items = await self._blackboard_provider().get_calendar_items()
        result = CalendarSyncResult(synced=0, created=0, updated=0)
        for item in items:
            source_event_id = str(item.get("id") or "").strip()
            if not source_event_id:
                continue
            start_at = self._parse_blackboard_datetime(item.get("start"))
            if start_at is None:
                continue
            end_at = self._parse_blackboard_datetime(item.get("end")) or start_at
            title = str(item.get("title") or item.get("course_name") or "Blackboard Event").strip()
            description_bits = [
                bit
                for bit in [item.get("course_name"), item.get("event_type")]
                if isinstance(bit, str) and bit.strip()
            ]
            description = " · ".join(description_bits) or None
            status = _default_status_for_window(start_at, end_at)

            existing = self.repository.find_by_source_event(
                source="blackboard",
                source_event_id=source_event_id,
            )
            if existing is None:
                self.repository.create(
                    title=title,
                    description=description,
                    start_at=start_at,
                    end_at=end_at,
                    timezone="UTC",
                    source="blackboard",
                    status=status,
                    source_event_id=source_event_id,
                    source_payload=item,
                    is_read_only=True,
                )
                result.created += 1
            else:
                existing.title = title
                existing.description = description
                existing.start_at = start_at
                existing.end_at = end_at
                existing.source_payload = item
                existing.is_read_only = True
                existing.source = "blackboard"
                existing.status = status
                self.repository.update(existing)
                result.updated += 1
            result.synced += 1
        return result
