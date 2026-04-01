"""Agent-facing Blackboard tools."""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.models.task import BlackboardResult, DownloadResult
from backend.services.blackboard_service import BlackboardService, MockBlackboardProvider


def _service(session: Session) -> BlackboardService:
    return BlackboardService(session, MockBlackboardProvider())


async def get_assignments(session: Session, course_id: str) -> BlackboardResult:
    """Fetch assignments for a course."""

    return await _service(session).get_assignments(course_id)


async def get_announcements(session: Session, course_id: str) -> BlackboardResult:
    """Fetch announcements for a course."""

    return await _service(session).get_announcements(course_id)


async def download_file(session: Session, file_id: str, save_path: str) -> DownloadResult:
    """Download a Blackboard file to a local path."""

    return await _service(session).download_file(file_id, save_path)


async def get_all_courses(session: Session) -> BlackboardResult:
    """Fetch all available courses."""

    return await _service(session).get_all_courses()
