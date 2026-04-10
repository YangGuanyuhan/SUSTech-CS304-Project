"""Request and response schemas for API routes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from backend.models.quiz import QuizAnswerSubmission


class ChatRequest(BaseModel):
    message: str
    session_id: str = Field(default="default")
    workspace_root: str | None = None


class ChatApprovalRequest(BaseModel):
    session_id: str
    approval_id: str
    approved: bool


class EmailDraftRequest(BaseModel):
    to: str
    subject: str
    body_instruction: str


class EmailConfirmRequest(BaseModel):
    confirmed: bool


class MemoryDeleteByQueryRequest(BaseModel):
    query: str


class LLMSettingsRequest(BaseModel):
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


class LLMConnectionTestRequest(BaseModel):
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class LLMProfileRequest(BaseModel):
    name: str
    provider: str
    model: str
    base_url: str | None = None
    api_key: str | None = None


class BlackboardProfileRequest(BaseModel):
    name: str
    student_id: str
    base_url: str | None = None
    password: str | None = None


class QuizAttemptRequest(BaseModel):
    answers: list[QuizAnswerSubmission]


class BlackboardSettingsRequest(BaseModel):
    student_id: str | None = None
    password: str | None = None
    base_url: str | None = None
    replace_password: bool = False


class CalendarEventCreateRequest(BaseModel):
    title: str
    start_at: datetime
    end_at: datetime
    description: str | None = None
    location: str | None = None
    all_day: bool = False
    timezone: str = "UTC"
    status: str = "not_started"


class CalendarEventUpdateRequest(BaseModel):
    title: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    description: str | None = None
    location: str | None = None
    all_day: bool | None = None
    timezone: str | None = None
    status: str | None = None


class CalendarEventMoveRequest(BaseModel):
    start_at: datetime
    end_at: datetime
