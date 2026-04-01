"""Blackboard provider interface and mock implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.db import crud
from backend.models.task import Announcement, Assignment, BlackboardResult, Course, DownloadResult


class BlackboardProvider(ABC):
    """Provider contract for Blackboard integrations."""

    @abstractmethod
    async def get_all_courses(self) -> list[Course]:
        """Return all courses."""

    @abstractmethod
    async def get_assignments(self, course_id: str) -> list[Assignment]:
        """Return assignments for one course."""

    @abstractmethod
    async def get_announcements(self, course_id: str) -> list[Announcement]:
        """Return announcements for one course."""

    @abstractmethod
    async def download_file(self, file_id: str, save_path: str) -> DownloadResult:
        """Download one Blackboard file."""


class MockBlackboardProvider(BlackboardProvider):
    """Mock Blackboard provider used for V1 development."""

    async def get_all_courses(self) -> list[Course]:
        return [
            Course(id="cs305", name="Software Engineering", code="CS305"),
            Course(id="cs310", name="Operating Systems", code="CS310"),
        ]

    async def get_assignments(self, course_id: str) -> list[Assignment]:
        due_at = datetime.now(timezone.utc) + timedelta(days=7)
        return [Assignment(id=f"{course_id}-a1", course_id=course_id, title="Sprint report", due_at=due_at)]

    async def get_announcements(self, course_id: str) -> list[Announcement]:
        now = datetime.now(timezone.utc)
        return [
            Announcement(
                id=f"{course_id}-n1",
                course_id=course_id,
                title="Project checkpoint",
                content="Submit your checkpoint slides before Friday.",
                published_at=now,
            )
        ]

    async def download_file(self, file_id: str, save_path: str) -> DownloadResult:
        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"Mock Blackboard content for {file_id}", encoding="utf-8")
        return DownloadResult(file_id=file_id, save_path=save_path, success=True, message="Downloaded mock file.")


class BlackboardService:
    """Service wrapper that adds cache fallback to a provider."""

    def __init__(self, session: Session, provider: BlackboardProvider):
        self.session = session
        self.provider = provider

    async def _fetch_with_cache(self, endpoint: str, cache_key: str, fetcher) -> BlackboardResult:
        try:
            items = await fetcher()
            await crud.save_blackboard_cache(
                self.session,
                endpoint=endpoint,
                cache_key=cache_key,
                data=[item.model_dump(mode="json") for item in items],
            )
            return BlackboardResult(data=items, is_cached=False)
        except Exception as exc:
            cached = await crud.load_blackboard_cache(
                self.session,
                endpoint=endpoint,
                cache_key=cache_key,
            )
            if not cached:
                raise exc
            return BlackboardResult(
                data=[
                    Course.model_validate(item)
                    if endpoint == "courses"
                    else Assignment.model_validate(item)
                    if endpoint == "assignments"
                    else Announcement.model_validate(item)
                    for item in json.loads(cached.data_json)
                ],
                is_cached=True,
                cached_at=cached.cached_at,
                warning="Blackboard is unavailable. Showing cached data.",
            )

    async def get_all_courses(self) -> BlackboardResult:
        return await self._fetch_with_cache("courses", "all", self.provider.get_all_courses)

    async def get_assignments(self, course_id: str) -> BlackboardResult:
        return await self._fetch_with_cache(
            "assignments",
            course_id,
            lambda: self.provider.get_assignments(course_id),
        )

    async def get_announcements(self, course_id: str) -> BlackboardResult:
        return await self._fetch_with_cache(
            "announcements",
            course_id,
            lambda: self.provider.get_announcements(course_id),
        )

    async def download_file(self, file_id: str, save_path: str) -> DownloadResult:
        return await self.provider.download_file(file_id, save_path)
