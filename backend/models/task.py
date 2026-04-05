"""Task and Blackboard related models."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class Course(BaseModel):
    course_id: str
    name: str
    blackboard_course_id: str | None = None


class Assignment(BaseModel):
    id: str
    course_id: str
    title: str
    due_at: datetime
    status: str = "open"


class Announcement(BaseModel):
    id: str
    course_id: str
    title: str
    content: str
    published_at: datetime


class DownloadResult(BaseModel):
    file_id: str
    save_path: str
    success: bool
    message: str


class BlackboardResult(BaseModel):
    data: list[Course] | list[Assignment] | list[Announcement]
    is_cached: bool = False
    cached_at: datetime | None = None
    warning: str | None = None


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str
    published_date: datetime | None = None


class RenameOperation(BaseModel):
    original_name: str
    new_name: str
    conflict: bool = False
    reason: str | None = None


class RenamePreview(BaseModel):
    directory: str
    operations: list[RenameOperation]
    valid: bool


class RenameResult(BaseModel):
    directory: str
    renamed_count: int
    operations: list[RenameOperation]


class FileSummary(BaseModel):
    file_path: str
    summary: str
    key_points: list[str] = Field(default_factory=list)


class QuizQuestion(BaseModel):
    question: str
    options: list[str]
    answer: str
    explanation: str


class Quiz(BaseModel):
    source_file: str
    questions: list[QuizQuestion]
    generated_at: datetime


class DateTimeInfo(BaseModel):
    """Structured datetime information."""

    timestamp: float
    iso_format: str
    year: int
    month: int
    day: int
    hour: int
    minute: int
    second: int
    microsecond: int
    tzname: str
    utc_offset_hours: float
