"""Domain repositories for database access."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from backend.db.models import (
    BlackboardCacheRecord,
    EmailDraftRecord,
    MemoryRecord,
    QuizAnswerRecord,
    QuizAttemptRecord,
    QuizQuestionRecord,
    QuizSessionRecord,
    TaskHistoryRecord,
    UserPreferenceRecord,
)


class Repository:
    """Small base class shared by repository implementations."""

    def __init__(self, session: Session):
        self.session = session

    def _persist(self, record: Any) -> Any:
        self.session.add(record)
        self.session.commit()
        self.session.refresh(record)
        return record


class MemoryRepository(Repository):
    def create(
        self,
        *,
        key: str,
        value: Any,
        category: str,
        tags: list[str] | None = None,
        owner_id: str = "local-user",
    ) -> MemoryRecord:
        return self._persist(
            MemoryRecord(
                owner_id=owner_id,
                key=key,
                value=value,
                category=category,
                tags=tags or [],
            )
        )

    def list(self, *, category: str | None = None, owner_id: str = "local-user") -> list[MemoryRecord]:
        stmt = select(MemoryRecord).where(MemoryRecord.owner_id == owner_id)
        if category:
            stmt = stmt.where(MemoryRecord.category == category)
        stmt = stmt.order_by(MemoryRecord.created_at.desc())
        return list(self.session.execute(stmt).scalars())

    def delete(self, memory_id: str, *, owner_id: str = "local-user") -> bool:
        stmt = delete(MemoryRecord).where(MemoryRecord.id == memory_id, MemoryRecord.owner_id == owner_id)
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0


class EmailDraftRepository(Repository):
    def create(self, *, to_addr: str, subject: str, body: str, owner_id: str = "local-user") -> EmailDraftRecord:
        return self._persist(EmailDraftRecord(owner_id=owner_id, to_addr=to_addr, subject=subject, body=body))

    def get(self, draft_id: str, *, owner_id: str = "local-user") -> EmailDraftRecord | None:
        stmt = select(EmailDraftRecord).where(
            EmailDraftRecord.id == draft_id,
            EmailDraftRecord.owner_id == owner_id,
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list(self, *, owner_id: str = "local-user") -> list[EmailDraftRecord]:
        stmt = (
            select(EmailDraftRecord)
            .where(EmailDraftRecord.owner_id == owner_id)
            .order_by(EmailDraftRecord.created_at.desc())
        )
        return list(self.session.execute(stmt).scalars())

    def update_status(
        self,
        draft_id: str,
        *,
        status: str,
        sent_at: datetime | None = None,
        owner_id: str = "local-user",
    ) -> EmailDraftRecord | None:
        draft = self.get(draft_id, owner_id=owner_id)
        if draft is None:
            return None
        draft.status = status
        draft.sent_at = sent_at
        self.session.commit()
        self.session.refresh(draft)
        return draft


class BlackboardCacheRepository(Repository):
    def save(self, *, endpoint: str, cache_key: str, data: Any, owner_id: str = "local-user") -> BlackboardCacheRecord:
        return self._persist(
            BlackboardCacheRecord(
                owner_id=owner_id,
                endpoint=endpoint,
                cache_key=cache_key,
                data=data,
            )
        )

    def load(self, *, endpoint: str, cache_key: str, owner_id: str = "local-user") -> BlackboardCacheRecord | None:
        stmt = (
            select(BlackboardCacheRecord)
            .where(
                BlackboardCacheRecord.owner_id == owner_id,
                BlackboardCacheRecord.endpoint == endpoint,
                BlackboardCacheRecord.cache_key == cache_key,
            )
            .order_by(BlackboardCacheRecord.cached_at.desc())
        )
        return self.session.execute(stmt).scalars().first()


class TaskHistoryRepository(Repository):
    def create(
        self,
        *,
        session_id: str,
        user_input: str,
        agent_response: str,
        tools_used: list[str] | None = None,
        owner_id: str = "local-user",
    ) -> TaskHistoryRecord:
        return self._persist(
            TaskHistoryRecord(
                owner_id=owner_id,
                session_id=session_id,
                user_input=user_input,
                agent_response=agent_response,
                tools_used=tools_used or [],
            )
        )

    def list_recent(
        self,
        *,
        session_id: str,
        limit: int = 20,
        owner_id: str = "local-user",
    ) -> list[TaskHistoryRecord]:
        stmt = (
            select(TaskHistoryRecord)
            .where(TaskHistoryRecord.owner_id == owner_id, TaskHistoryRecord.session_id == session_id)
            .order_by(TaskHistoryRecord.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())


class UserPreferenceRepository(Repository):
    def upsert(self, *, key: str, value: str, owner_id: str = "local-user") -> UserPreferenceRecord:
        stmt = select(UserPreferenceRecord).where(
            UserPreferenceRecord.owner_id == owner_id,
            UserPreferenceRecord.key == key,
        )
        record = self.session.execute(stmt).scalar_one_or_none()
        if record is None:
            return self._persist(UserPreferenceRecord(owner_id=owner_id, key=key, value=value))

        record.value = value
        record.updated_at = datetime.now(timezone.utc)
        self.session.commit()
        self.session.refresh(record)
        return record

    def list(self, *, key_prefix: str | None = None, owner_id: str = "local-user") -> list[UserPreferenceRecord]:
        stmt = select(UserPreferenceRecord).where(UserPreferenceRecord.owner_id == owner_id)
        if key_prefix:
            stmt = stmt.where(UserPreferenceRecord.key.like(f"{key_prefix}%"))
        stmt = stmt.order_by(UserPreferenceRecord.updated_at.desc())
        return list(self.session.execute(stmt).scalars())

    def delete(self, *, key: str, owner_id: str = "local-user") -> bool:
        stmt = delete(UserPreferenceRecord).where(
            UserPreferenceRecord.owner_id == owner_id,
            UserPreferenceRecord.key == key,
        )
        result = self.session.execute(stmt)
        self.session.commit()
        return result.rowcount > 0


class QuizRepository(Repository):
    def create_session(
        self,
        *,
        chat_session_id: str,
        title: str,
        topic: str,
        source_material: str | None,
        owner_id: str = "local-user",
    ) -> QuizSessionRecord:
        return self._persist(
            QuizSessionRecord(
                owner_id=owner_id,
                chat_session_id=chat_session_id,
                title=title,
                topic=topic,
                source_material=source_material,
            )
        )

    def create_questions(self, *, quiz_session_id: str, questions: list[dict[str, Any]]) -> list[QuizQuestionRecord]:
        records: list[QuizQuestionRecord] = []
        for index, question in enumerate(questions, start=1):
            record = QuizQuestionRecord(
                id=question["id"],
                quiz_session_id=quiz_session_id,
                position=index,
                question_type=question["question_type"],
                prompt=question["prompt"],
                options=question.get("options", []),
                correct_answer=question["correct_answer"],
                explanation=question["explanation"],
                rubric=question.get("rubric"),
                points=float(question.get("points", 1.0)),
            )
            self.session.add(record)
            records.append(record)
        self.session.commit()
        for record in records:
            self.session.refresh(record)
        return records

    def get_session(self, quiz_id: str, *, owner_id: str = "local-user") -> QuizSessionRecord | None:
        stmt = (
            select(QuizSessionRecord)
            .options(selectinload(QuizSessionRecord.questions))
            .where(QuizSessionRecord.id == quiz_id, QuizSessionRecord.owner_id == owner_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()

    def list_recent_sessions(self, *, limit: int = 10, owner_id: str = "local-user") -> list[QuizSessionRecord]:
        stmt = (
            select(QuizSessionRecord)
            .where(QuizSessionRecord.owner_id == owner_id)
            .order_by(QuizSessionRecord.created_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def create_attempt(
        self,
        *,
        quiz_session_id: str,
        score: float,
        total_points: float,
        summary: str,
        owner_id: str = "local-user",
    ) -> QuizAttemptRecord:
        return self._persist(
            QuizAttemptRecord(
                owner_id=owner_id,
                quiz_session_id=quiz_session_id,
                score=score,
                total_points=total_points,
                summary=summary,
            )
        )

    def create_answers(self, *, attempt_id: str, answers: list[dict[str, Any]]) -> list[QuizAnswerRecord]:
        records: list[QuizAnswerRecord] = []
        for answer in answers:
            record = QuizAnswerRecord(
                attempt_id=attempt_id,
                quiz_question_id=answer["quiz_question_id"],
                submitted_answer=answer["submitted_answer"],
                is_correct=answer.get("is_correct"),
                score=float(answer["score"]),
                feedback=answer["feedback"],
            )
            self.session.add(record)
            records.append(record)
        self.session.commit()
        for record in records:
            self.session.refresh(record)
        return records

    def list_recent_attempts(self, *, limit: int = 10, owner_id: str = "local-user") -> list[QuizAttemptRecord]:
        stmt = (
            select(QuizAttemptRecord)
            .where(QuizAttemptRecord.owner_id == owner_id)
            .order_by(QuizAttemptRecord.submitted_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())

    def list_answers_for_attempt(self, attempt_id: str) -> list[QuizAnswerRecord]:
        stmt = select(QuizAnswerRecord).where(QuizAnswerRecord.attempt_id == attempt_id)
        return list(self.session.execute(stmt).scalars())


class DatabaseAnalyticsRepository(Repository):
    """Read-only aggregate queries for operational visibility."""

    def overview(self, *, owner_id: str = "local-user", recent_limit: int = 8) -> dict[str, Any]:
        memory_count = self.session.scalar(
            select(func.count()).select_from(MemoryRecord).where(MemoryRecord.owner_id == owner_id)
        ) or 0
        task_count = self.session.scalar(
            select(func.count()).select_from(TaskHistoryRecord).where(TaskHistoryRecord.owner_id == owner_id)
        ) or 0
        quiz_count = self.session.scalar(
            select(func.count()).select_from(QuizSessionRecord).where(QuizSessionRecord.owner_id == owner_id)
        ) or 0
        attempt_count = self.session.scalar(
            select(func.count()).select_from(QuizAttemptRecord).where(QuizAttemptRecord.owner_id == owner_id)
        ) or 0
        draft_count = self.session.scalar(
            select(func.count()).select_from(EmailDraftRecord).where(EmailDraftRecord.owner_id == owner_id)
        ) or 0
        preference_count = self.session.scalar(
            select(func.count()).select_from(UserPreferenceRecord).where(UserPreferenceRecord.owner_id == owner_id)
        ) or 0

        memory_records = self.session.execute(
            select(MemoryRecord).where(MemoryRecord.owner_id == owner_id).order_by(MemoryRecord.created_at.desc())
        ).scalars()
        memory_category_counts = Counter(record.category for record in memory_records)

        history_records = self.session.execute(
            select(TaskHistoryRecord)
            .where(TaskHistoryRecord.owner_id == owner_id)
            .order_by(TaskHistoryRecord.created_at.desc())
            .limit(recent_limit)
        ).scalars()
        recent_history = [
            {
                "id": record.id,
                "session_id": record.session_id,
                "created_at": record.created_at,
                "user_input_preview": record.user_input[:80],
                "tools_used": record.tools_used,
            }
            for record in history_records
        ]

        session_activity_rows = self.session.execute(
            select(TaskHistoryRecord.session_id, func.count(TaskHistoryRecord.id))
            .where(TaskHistoryRecord.owner_id == owner_id)
            .group_by(TaskHistoryRecord.session_id)
            .order_by(func.count(TaskHistoryRecord.id).desc(), TaskHistoryRecord.session_id.asc())
            .limit(5)
        ).all()
        session_activity = [
            {"session_id": session_id, "message_count": message_count}
            for session_id, message_count in session_activity_rows
        ]

        latest_attempt = self.session.execute(
            select(QuizAttemptRecord, QuizSessionRecord.title, QuizSessionRecord.topic)
            .join(QuizSessionRecord, QuizAttemptRecord.quiz_session_id == QuizSessionRecord.id)
            .where(QuizAttemptRecord.owner_id == owner_id)
            .order_by(QuizAttemptRecord.submitted_at.desc())
            .limit(1)
        ).first()
        latest_quiz_attempt = None
        if latest_attempt:
            attempt, title, topic = latest_attempt
            latest_quiz_attempt = {
                "attempt_id": attempt.id,
                "quiz_session_id": attempt.quiz_session_id,
                "title": title,
                "topic": topic,
                "score": attempt.score,
                "total_points": attempt.total_points,
                "submitted_at": attempt.submitted_at,
            }

        return {
            "counts": {
                "memories": memory_count,
                "task_history": task_count,
                "quiz_sessions": quiz_count,
                "quiz_attempts": attempt_count,
                "email_drafts": draft_count,
                "user_preferences": preference_count,
            },
            "memory_categories": [
                {"category": category, "count": count}
                for category, count in memory_category_counts.most_common()
            ],
            "recent_history": recent_history,
            "session_activity": session_activity,
            "latest_quiz_attempt": latest_quiz_attempt,
            "schema_readiness": {
                "conversation_storage_ready": False,
                "memory_embedding_ready": False,
                "email_approval_history_ready": False,
                "quiz_relationships_ready": True,
                "typed_json_ready": True,
            },
        }
