from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.models.calendar import CalendarEventCreate, CalendarEventMove, CalendarEventUpdate
from backend.services.calendar_service import CalendarService


def utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


async def test_calendar_service_creates_and_lists_event(db_session):
    service = CalendarService(db_session)
    created = await service.create_event(
        CalendarEventCreate(
            title="Team sync",
            start_at=utc("2026-04-08T01:00:00Z"),
            end_at=utc("2026-04-08T02:00:00Z"),
            description="Sprint planning",
            location="Room 301",
        )
    )

    result = await service.list_events(
        start=utc("2026-04-08T00:00:00Z"),
        end=utc("2026-04-08T23:59:59Z"),
    )

    assert created.source == "local"
    assert result.events[0].title == "Team sync"
    assert result.events[0].event_id == created.event_id
    assert result.events[0].status == "not_started"


async def test_calendar_service_expands_weekly_events(db_session):
    service = CalendarService(db_session)
    created = await service.create_event(
        CalendarEventCreate(
            title="Weekly Lab",
            start_at=utc("2026-04-06T02:00:00Z"),
            end_at=utc("2026-04-06T04:00:00Z"),
            weekly_repeat=True,
        )
    )

    result = await service.list_events(
        start=utc("2026-04-06T00:00:00Z"),
        end=utc("2026-04-20T23:59:59Z"),
    )

    weekly_events = [event for event in result.events if event.event_id == created.event_id]
    assert len(weekly_events) == 3
    assert all(event.weekly_repeat for event in weekly_events)


async def test_calendar_service_moves_series_anchor(db_session):
    service = CalendarService(db_session)
    created = await service.create_event(
        CalendarEventCreate(
            title="Research block",
            start_at=utc("2026-04-10T03:00:00Z"),
            end_at=utc("2026-04-10T05:00:00Z"),
            weekly_repeat=True,
        )
    )

    moved = await service.move_event(
        created.event_id,
        CalendarEventMove(
            start_at=utc("2026-04-11T06:00:00Z"),
            end_at=utc("2026-04-11T08:00:00Z"),
        ),
    )

    result = await service.list_events(
        start=utc("2026-04-11T00:00:00Z"),
        end=utc("2026-04-25T23:59:59Z"),
    )

    assert moved.start_at == utc("2026-04-11T06:00:00Z")
    assert result.events[0].start_at == utc("2026-04-11T06:00:00Z")


async def test_blackboard_sync_and_clone(db_session, monkeypatch):
    service = CalendarService(db_session)

    class FakeProvider:
        async def get_calendar_items(self):
            return [
                {
                    "id": "bb-1",
                    "title": "SE Deadline",
                    "course_name": "CS305",
                    "event_type": "assignment",
                    "start": "2026-04-12T08:00:00Z",
                    "end": "2026-04-12T09:00:00Z",
                }
            ]

    monkeypatch.setattr(service, "_blackboard_provider", lambda: FakeProvider())

    sync_result = await service.sync_blackboard()
    blackboard_events = await service.list_events(
        start=utc("2026-04-12T00:00:00Z"),
        end=utc("2026-04-12T23:59:59Z"),
    )

    cloned = await service.clone_blackboard_event(blackboard_events.events[0].event_id)

    assert sync_result.created == 1
    assert blackboard_events.events[0].is_read_only is True
    assert cloned.source == "local"
    assert cloned.is_read_only is False


async def test_calendar_service_updates_local_status(db_session):
    service = CalendarService(db_session)
    created = await service.create_event(
        CalendarEventCreate(
            title="Write report",
            start_at=utc("2026-04-09T02:00:00Z"),
            end_at=utc("2026-04-09T03:00:00Z"),
        )
    )

    updated = await service.update_event(created.event_id, CalendarEventUpdate(status="completed"))

    assert updated.status == "completed"


async def test_blackboard_events_allow_status_only_updates(db_session, monkeypatch):
    service = CalendarService(db_session)

    class FakeProvider:
        async def get_calendar_items(self):
            return [
                {
                    "id": "bb-2",
                    "title": "OS Quiz",
                    "course_name": "CS310",
                    "event_type": "assessment",
                    "start": "2026-04-16T08:00:00Z",
                    "end": "2026-04-16T09:00:00Z",
                }
            ]

    monkeypatch.setattr(service, "_blackboard_provider", lambda: FakeProvider())
    await service.sync_blackboard()
    result = await service.list_events(
        start=utc("2026-04-16T00:00:00Z"),
        end=utc("2026-04-16T23:59:59Z"),
    )
    blackboard_event = result.events[0]

    updated = await service.update_event(
        blackboard_event.event_id,
        CalendarEventUpdate(status="completed"),
    )

    assert updated.status == "completed"

    with pytest.raises(ValueError):
        await service.update_event(
            blackboard_event.event_id,
            CalendarEventUpdate(title="Illegal edit"),
        )
