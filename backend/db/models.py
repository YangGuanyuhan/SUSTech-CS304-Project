"""ORM models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.db.types import JSONText


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base ORM model."""


class TimestampMixin:
    """Shared created/updated timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class MemoryRecord(TimestampMixin, Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_owner_category_created", "owner_id", "category", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    key: Mapped[str] = mapped_column(String(255), index=True)
    value: Mapped[Any] = mapped_column(JSONText)
    category: Mapped[str] = mapped_column(String(100), index=True)
    tags: Mapped[list[str]] = mapped_column(JSONText, default=list)


class EmailDraftRecord(TimestampMixin, Base):
    __tablename__ = "email_drafts"
    __table_args__ = (
        Index("ix_email_drafts_owner_status_created", "owner_id", "status", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    to_addr: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class BlackboardCacheRecord(Base):
    __tablename__ = "blackboard_cache"
    __table_args__ = (
        Index("ix_blackboard_cache_lookup", "owner_id", "endpoint", "cache_key", "cached_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    endpoint: Mapped[str] = mapped_column(String(128), index=True)
    cache_key: Mapped[str] = mapped_column(String(255), index=True)
    data: Mapped[Any] = mapped_column(JSONText)
    cached_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TaskHistoryRecord(TimestampMixin, Base):
    __tablename__ = "task_history"
    __table_args__ = (
        Index("ix_task_history_owner_session_created", "owner_id", "session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    session_id: Mapped[str] = mapped_column(String(128), index=True)
    user_input: Mapped[str] = mapped_column(Text)
    agent_response: Mapped[str] = mapped_column(Text)
    tools_used: Mapped[list[str]] = mapped_column(JSONText, default=list)


class UserPreferenceRecord(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        UniqueConstraint("owner_id", "key", name="uq_user_preferences_owner_key"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class QuizSessionRecord(TimestampMixin, Base):
    __tablename__ = "quiz_sessions"
    __table_args__ = (
        Index("ix_quiz_sessions_owner_chat_created", "owner_id", "chat_session_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    chat_session_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str] = mapped_column(String(255))
    topic: Mapped[str] = mapped_column(Text)
    source_material: Mapped[str | None] = mapped_column(Text, nullable=True)
    questions: Mapped[list["QuizQuestionRecord"]] = relationship(
        back_populates="quiz_session",
        cascade="all, delete-orphan",
        order_by="QuizQuestionRecord.position",
    )
    attempts: Mapped[list["QuizAttemptRecord"]] = relationship(
        back_populates="quiz_session",
        cascade="all, delete-orphan",
        order_by="QuizAttemptRecord.submitted_at.desc()",
    )


class QuizQuestionRecord(Base):
    __tablename__ = "quiz_questions"
    __table_args__ = (
        UniqueConstraint("quiz_session_id", "position", name="uq_quiz_questions_session_position"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    quiz_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(index=True)
    question_type: Mapped[str] = mapped_column(String(32))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list[str]] = mapped_column(JSONText, default=list)
    correct_answer: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text)
    rubric: Mapped[str | None] = mapped_column(Text, nullable=True)
    points: Mapped[float] = mapped_column(Float, default=1.0)
    quiz_session: Mapped["QuizSessionRecord"] = relationship(back_populates="questions")
    answers: Mapped[list["QuizAnswerRecord"]] = relationship(back_populates="quiz_question")


class QuizAttemptRecord(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (
        Index("ix_quiz_attempts_owner_submitted", "owner_id", "submitted_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    quiz_session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quiz_sessions.id", ondelete="CASCADE"),
        index=True,
    )
    score: Mapped[float] = mapped_column(Float, default=0.0)
    total_points: Mapped[float] = mapped_column(Float, default=0.0)
    summary: Mapped[str] = mapped_column(Text, default="")
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    quiz_session: Mapped["QuizSessionRecord"] = relationship(back_populates="attempts")
    answers: Mapped[list["QuizAnswerRecord"]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class QuizAnswerRecord(TimestampMixin, Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (
        Index("ix_quiz_answers_attempt_created", "attempt_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    attempt_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quiz_attempts.id", ondelete="CASCADE"),
        index=True,
    )
    quiz_question_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("quiz_questions.id", ondelete="CASCADE"),
        index=True,
    )
    submitted_answer: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    score: Mapped[float] = mapped_column(Float, default=0.0)
    feedback: Mapped[str] = mapped_column(Text, default="")
    attempt: Mapped["QuizAttemptRecord"] = relationship(back_populates="answers")
    quiz_question: Mapped["QuizQuestionRecord"] = relationship(back_populates="answers")
