"""ORM models."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.db.types import JSONText


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(UTC)


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
    __table_args__ = (UniqueConstraint("owner_id", "key", name="uq_user_preferences_owner_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    key: Mapped[str] = mapped_column(String(128), index=True)
    value: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class CalendarEventRecord(Base):
    __tablename__ = "calendar_events"
    __table_args__ = (
        Index("ix_calendar_events_owner_start_end", "owner_id", "start_at", "end_at"),
        Index("ix_calendar_events_owner_source_start", "owner_id", "source", "start_at"),
        UniqueConstraint(
            "owner_id", "source", "source_event_id", name="uq_calendar_events_owner_source_event"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    source: Mapped[str] = mapped_column(String(32), default="local", index=True)
    status: Mapped[str] = mapped_column(String(32), default="not_started", index=True)
    source_event_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_payload: Mapped[Any | None] = mapped_column(JSONText, nullable=True)
    is_read_only: Mapped[bool] = mapped_column(Boolean, default=False)
    recurrence_rule: Mapped[Any | None] = mapped_column(JSONText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


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
    questions: Mapped[list[QuizQuestionRecord]] = relationship(
        back_populates="quiz_session",
        cascade="all, delete-orphan",
        order_by="QuizQuestionRecord.position",
    )
    attempts: Mapped[list[QuizAttemptRecord]] = relationship(
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
    quiz_session: Mapped[QuizSessionRecord] = relationship(back_populates="questions")
    answers: Mapped[list[QuizAnswerRecord]] = relationship(back_populates="quiz_question")


class QuizAttemptRecord(Base):
    __tablename__ = "quiz_attempts"
    __table_args__ = (Index("ix_quiz_attempts_owner_submitted", "owner_id", "submitted_at"),)

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
    quiz_session: Mapped[QuizSessionRecord] = relationship(back_populates="attempts")
    answers: Mapped[list[QuizAnswerRecord]] = relationship(
        back_populates="attempt",
        cascade="all, delete-orphan",
    )


class QuizAnswerRecord(TimestampMixin, Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (Index("ix_quiz_answers_attempt_created", "attempt_id", "created_at"),)

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
    attempt: Mapped[QuizAttemptRecord] = relationship(back_populates="answers")
    quiz_question: Mapped[QuizQuestionRecord] = relationship(back_populates="answers")


class RAGSourceRecord(Base):
    __tablename__ = "rag_sources"
    __table_args__ = (
        UniqueConstraint("owner_id", "file_path", name="uq_rag_sources_owner_file_path"),
        Index("ix_rag_sources_owner_status", "owner_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    file_path: Mapped[str] = mapped_column(Text)
    relative_path: Mapped[str] = mapped_column(Text)
    extension: Mapped[str] = mapped_column(String(16), index=True)
    file_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[str] = mapped_column(String(64), default="raganything")
    doc_id: Mapped[str] = mapped_column(String(128), index=True)
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )
    chunks: Mapped[list[RAGChunkRecord]] = relationship(
        back_populates="source",
        cascade="all, delete-orphan",
        order_by="RAGChunkRecord.position",
    )


class RAGChunkRecord(Base):
    __tablename__ = "rag_chunks"
    __table_args__ = (
        Index("ix_rag_chunks_source_position", "source_id", "position"),
        Index("ix_rag_chunks_owner_created", "owner_id", "created_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    owner_id: Mapped[str] = mapped_column(String(64), default="local-user", index=True)
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("rag_sources.id", ondelete="CASCADE"),
        index=True,
    )
    position: Mapped[int] = mapped_column(Integer, index=True)
    text: Mapped[str] = mapped_column(Text)
    page_idx: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict[str, Any]] = mapped_column(JSONText, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    source: Mapped[RAGSourceRecord] = relationship(back_populates="chunks")
