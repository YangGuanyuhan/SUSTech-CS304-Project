"""Blackboard provider interface and demo implementation."""

from __future__ import annotations
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

    def __init__(self, student_id: str | None = None, password: str | None = None, base_url: str | None = None):
        self._cas_session = None
        self._student_id = student_id
        self._password = password
        self._base_url = base_url

    def _get_credentials(self):
        """Get credentials from runtime settings or fall back to config."""
        import logging
        logger = logging.getLogger(__name__)

        from backend.services.runtime_settings import runtime_settings

        # Try runtime settings first (from UI configuration)
        runtime_bb_config = runtime_settings.get_blackboard_config()
        runtime_password = runtime_settings.get_secret_blackboard_password()

        student_id = self._student_id or runtime_bb_config.student_id
        password = self._password or runtime_password

        # Fall back to config settings if not in runtime
        if not student_id or not password:
            settings = get_settings()
            student_id = student_id or settings.blackboard_student_id
            password = password or settings.blackboard_cas_password

        base_url = self._base_url or runtime_bb_config.base_url
        if not base_url:
            settings = get_settings()
            base_url = self._base_url or settings.blackboard_base_url

        logger.info(f"_get_credentials: student_id={student_id}, base_url={base_url}, password_set={bool(password)}")
        return student_id, password, base_url

    async def bypass_cas_login(self) -> bool:
        # Perform CAS login and cache the authenticated session for later API calls.
        username, password, base_url = self._get_credentials()

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
            # Always use root URL for CAS login, not the API URL
            login_url = "https://bb.sustech.edu.cn/"
            response = session.get(login_url, timeout=60)

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
        _, _, base_url = self._get_credentials()
        api_url = f"{base_url.rstrip('/')}/users/me"

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
        _, _, base_url = self._get_credentials()
        api_url = f"{base_url.rstrip('/')}/calendars/items"

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
                    for item in cached.data
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

    @staticmethod
    async def test_connection(student_id: str, password: str, base_url: str = "https://bb.sustech.edu.cn/") -> bool:
        """Test Blackboard connection with provided credentials."""
        import aiohttp
        import logging

        logger = logging.getLogger(__name__)
        logger.info(f"Testing Blackboard connection for student: {student_id}, base_url: {base_url}")

        session = aiohttp.ClientSession(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }
        )
        try:
            async with session.get(base_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                logger.info(f"Initial response URL: {response.url}, status: {response.status}")
                if "cas.sustech.edu.cn" in str(response.url):
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(await response.text(), "html.parser")
                    execution_input = soup.find("input", {"name": "execution"})
                    if execution_input is None:
                        logger.warning("No execution input found in CAS form")
                        return False

                    execution = execution_input.get("value")
                    login_data = {
                        "username": student_id,
                        "password": password,
                        "execution": execution,
                        "_eventId": "submit",
                        "geolocation": "",
                    }

                    async with session.post(str(response.url), data=login_data, timeout=aiohttp.ClientTimeout(total=60)) as login_response:
                        logger.info(f"Login response URL: {login_response.url}, status: {login_response.status}")
                        success = "cas.sustech.edu.cn" not in str(login_response.url)
                        return success
                return True
        except Exception as e:
            logger.error(f"Blackboard connection test failed: {e}")
            return False
        finally:
            await session.close()
