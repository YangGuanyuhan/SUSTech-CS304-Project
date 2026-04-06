"""Datetime service."""

from __future__ import annotations

from datetime import datetime, timezone
import time

from backend.models.task import DateTimeInfo


class DateTimeService:
    """Provide current datetime information in a structured format."""

    def get_current_datetime(self) -> DateTimeInfo:
        now = datetime.now(timezone.utc).astimezone()
        utc_offset = now.utcoffset()
        utc_offset_hours = utc_offset.total_seconds() / 3600 if utc_offset else 0.0

        return DateTimeInfo(
            timestamp=time.time(),
            iso_format=now.isoformat(),
            year=now.year,
            month=now.month,
            day=now.day,
            hour=now.hour,
            minute=now.minute,
            second=now.second,
            microsecond=now.microsecond,
            tzname=now.tzname() or "UTC",
            utc_offset_hours=utc_offset_hours,
        )
