from __future__ import annotations

from unittest.mock import AsyncMock

from backend.models.quiz import QuizAnswerSubmission, QuizQuestion
from backend.services.llm_service import LLMConfigurationError
from backend.services.quiz_service import QuizService


async def test_quiz_service_creates_fallback_quiz(db_session):
    service = QuizService(db_session)
    service.llm_service.create_chat_completion = AsyncMock(side_effect=LLMConfigurationError("missing"))

    quiz = await service.create_quiz(
        chat_session_id="chat-quiz",
        topic="Operating Systems",
        question_count=3,
        source_material="Processes, threads, and scheduling.",
    )

    assert quiz.topic == "Operating Systems"
    assert len(quiz.questions) == 3


async def test_quiz_service_grades_attempt_and_returns_summary(db_session):
    service = QuizService(db_session)
    service.llm_service.create_chat_completion = AsyncMock(side_effect=LLMConfigurationError("missing"))

    quiz = await service.create_quiz(
        chat_session_id="chat-quiz",
        topic="Databases",
        question_count=3,
        source_material="Normalization and transactions.",
    )

    attempt = await service.submit_attempt(
        quiz.id,
        [
            QuizAnswerSubmission(question_id=quiz.questions[0].id, answer=quiz.questions[0].correct_answer),
            QuizAnswerSubmission(question_id=quiz.questions[1].id, answer="False"),
            QuizAnswerSubmission(question_id=quiz.questions[2].id, answer="Transactions keep data consistent."),
        ],
    )

    assert attempt.quiz_id == quiz.id
    assert len(attempt.answers) == 3
    assert attempt.total_points > 0


async def test_quiz_history_summary_aggregates_attempts(db_session):
    service = QuizService(db_session)
    service.llm_service.create_chat_completion = AsyncMock(side_effect=LLMConfigurationError("missing"))

    quiz = await service.create_quiz(
        chat_session_id="chat-history",
        topic="Computer Networks",
        question_count=2,
        source_material="Routing and congestion control.",
    )
    await service.submit_attempt(
        quiz.id,
        [
            QuizAnswerSubmission(question_id=quiz.questions[0].id, answer=quiz.questions[0].correct_answer),
            QuizAnswerSubmission(question_id=quiz.questions[1].id, answer="False"),
        ],
    )

    history = await service.get_history_summary(limit=5)
    assert history.total_attempts >= 1
    assert history.attempts[0].quiz_id == quiz.id


async def test_true_false_grading_accepts_false_for_chinese_wrong_answer(db_session):
    service = QuizService(db_session)
    question = QuizQuestion(
        id="q1",
        question_type="true_false",
        prompt="Firewall can prevent all network attacks.",
        options=["True", "False"],
        correct_answer="错误",
        explanation="Expected: 错误",
        points=1.0,
    )

    result = await service._grade_question(question, "False")

    assert result.is_correct is True
    assert result.score == 1.0
