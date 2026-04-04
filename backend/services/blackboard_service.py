"""Blackboard provider interface and demo implementation."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db import crud
from backend.models.task import Announcement, Assignment, BlackboardResult, Course, DownloadResult


class BlackboardProvider(ABC):
    """Provider contract for Blackboard integrations."""

    @abstractmethod
    async def bypass_cas_login(self) -> bool:
        """Bypass CAS login flow and prepare Blackboard access session."""

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

    @abstractmethod
    async def get_calendar_items(self) -> list[dict[str, object]]:
        """Return key calendar items from Blackboard."""


class DemoBlackboardProvider(BlackboardProvider):
    """Demo Blackboard provider used for V1 development."""

    def __init__(self):
        self._cas_session = None
    
    async def bypass_cas_login(self) -> bool:
        # Perform CAS login and cache the authenticated session for later API calls.
        settings = get_settings()
        username = settings.blackboard_student_id
        password = settings.blackboard_cas_password

        if not username or not password:
            return False

        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )

        try:
            base_url = "https://bb.sustech.edu.cn/"
            response = session.get(base_url, timeout=60)

            if "cas.sustech.edu.cn" in response.url:
                soup = BeautifulSoup(response.text, "html.parser")
                execution_input = soup.find("input", {"name": "execution"})
                if execution_input is None:
                    return False

                execution = execution_input.get("value")
                if not execution:
                    return False

                login_data = {
                    "username": username,
                    "password": password,
                    "execution": execution,
                    "_eventId": "submit",
                    "geolocation": "",
                }

                response = session.post(response.url, data=login_data, timeout=60)
        except requests.Timeout:
            return False

        success = "cas.sustech.edu.cn" not in response.url
        if success:
            self._cas_session = session
        return success

    async def test_api_available(self) -> bool:
        # Probe Blackboard users/me endpoint and return availability as a boolean.
        settings = get_settings()
        api_url = f"{settings.blackboard_base_url.rstrip('/')}/users/me"

        if self._cas_session is None:
            logged_in = await self.bypass_cas_login()
            if not logged_in:
                return False

        try:
            response = self._cas_session.get(api_url, timeout=60)
        except requests.Timeout:
            return False

        if response.status_code == 401:
            return False

        return response.ok

    async def get_calendar_items(self) -> list[dict[str, object]]:
        settings = get_settings()
        api_url = f"{settings.blackboard_base_url.rstrip('/')}/calendars/items"

        if self._cas_session is None:
            logged_in = await self.bypass_cas_login()
            if not logged_in:
                return []

        try:
            response = self._cas_session.get(api_url, timeout=60)
        except requests.Timeout:
            return []

        if response.status_code == 401 or not response.ok:
            return []

        try:
            payload = response.json()
        except ValueError:
            return []

        items = payload.get("results", [])
        if not isinstance(items, list):
            return []

        extracted: list[dict[str, object]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            dynamic_props = item.get("dynamicCalendarItemProps")
            event_type = dynamic_props.get("eventType") if isinstance(dynamic_props, dict) else None
            extracted.append(
                {
                    "id": item.get("id"),
                    "course_name": item.get("calendarName"),
                    "title": item.get("title"),
                    "start": item.get("start"),
                    "end": item.get("end"),
                    "event_type": event_type,
                }
            )

        return extracted

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
