"""Quiz models."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


QuizQuestionType = Literal["single_choice", "true_false", "short_answer"]


class QuizQuestion(BaseModel):
    id: str
    question_type: QuizQuestionType
    prompt: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str
    rubric: str | None = None
    points: float = 1.0


class QuizSession(BaseModel):
    id: str
    chat_session_id: str
    title: str
    topic: str
    source_material: str | None = None
    questions: list[QuizQuestion]
    created_at: datetime


class QuizAnswerSubmission(BaseModel):
    question_id: str
    answer: str


class QuizAttemptAnswerResult(BaseModel):
    question_id: str
    prompt: str
    question_type: QuizQuestionType
    submitted_answer: str
    correct_answer: str
    is_correct: bool | None = None
    score: float
    max_score: float
    feedback: str
    explanation: str


class QuizAttemptResult(BaseModel):
    attempt_id: str
    quiz_id: str
    score: float
    total_points: float
    submitted_at: datetime
    answers: list[QuizAttemptAnswerResult]
    summary: str


class QuizHistoryEntry(BaseModel):
    quiz_id: str
    attempt_id: str
    title: str
    topic: str
    score: float
    total_points: float
    submitted_at: datetime
    weak_areas: list[str] = Field(default_factory=list)


class QuizHistorySummary(BaseModel):
    attempts: list[QuizHistoryEntry]
    total_attempts: int
    average_score: float
    recent_topics: list[str]
    personalized_analysis: str


class QuizToolPayload(BaseModel):
    quiz_session: QuizSession


class QuizSubmissionRequest(BaseModel):
    answers: list[QuizAnswerSubmission]


class QuizHistoryToolPayload(BaseModel):
    history: QuizHistorySummary

