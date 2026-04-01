"""Request and response schemas for API routes."""

from __future__ import annotations

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


class QuizAttemptRequest(BaseModel):
    answers: list[QuizAnswerSubmission]
