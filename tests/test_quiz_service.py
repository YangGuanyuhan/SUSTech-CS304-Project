from __future__ import annotations

from unittest.mock import AsyncMock

from backend.models.quiz import QuizAnswerSubmission, QuizDraft, QuizQuestion, QuizQuestionCreate
from backend.services.llm_service import LLMConfigurationError
from backend.services.quiz_service import QuizService


def _build_quiz_draft(topic: str, source_material: str, question_count: int) -> QuizDraft:
    questions = [
        QuizQuestionCreate(
            question_type="single_choice",
            prompt=f"What is a key idea in {topic}?",
            options=["Core idea", "Wrong idea", "Another wrong idea", "Irrelevant idea"],
            correct_answer="Core idea",
            explanation=f"The source material emphasizes core ideas in {topic}.",
            points=1.0,
        ),
        QuizQuestionCreate(
            question_type="true_false",
            prompt=f"True or False: {topic} is relevant to the current lesson.",
            options=["True", "False"],
            correct_answer="True",
            explanation=f"{topic} is explicitly part of the quiz scope.",
            points=1.0,
        ),
        QuizQuestionCreate(
            question_type="short_answer",
            prompt=f"Explain one important point about {topic}.",
            options=[],
            correct_answer=source_material,
            explanation="A correct answer should cover the main point from the source material.",
            rubric="Mention the main idea from the provided source material in your own words.",
            points=2.0,
        ),
    ]
    return QuizDraft(
        topic=topic,
        question_count=question_count,
        source_material=source_material,
        questions=questions[:question_count],
    )


async def test_quiz_service_creates_quiz_from_structured_payload(db_session):
    service = QuizService(db_session)

    quiz = await service.create_quiz(
        chat_session_id="chat-quiz",
        quiz=_build_quiz_draft("Operating Systems", "Processes, threads, and scheduling.", 3),
    )

    assert quiz.topic == "Operating Systems"
    assert len(quiz.questions) == 3
    assert quiz.questions[0].correct_answer == "Core idea"


async def test_quiz_service_grades_attempt_and_returns_summary(db_session):
    service = QuizService(db_session)
    service.llm_service.create_chat_completion = AsyncMock(
        side_effect=LLMConfigurationError("missing")
    )

    quiz = await service.create_quiz(
        chat_session_id="chat-quiz",
        quiz=_build_quiz_draft("Databases", "Normalization and transactions.", 3),
    )

    attempt = await service.submit_attempt(
        quiz.id,
        [
            QuizAnswerSubmission(
                question_id=quiz.questions[0].id, answer=quiz.questions[0].correct_answer
            ),
            QuizAnswerSubmission(question_id=quiz.questions[1].id, answer="False"),
            QuizAnswerSubmission(
                question_id=quiz.questions[2].id, answer="Transactions keep data consistent."
            ),
        ],
    )

    assert attempt.quiz_id == quiz.id
    assert len(attempt.answers) == 3
    assert attempt.total_points > 0


async def test_quiz_history_summary_aggregates_attempts(db_session):
    service = QuizService(db_session)

    quiz = await service.create_quiz(
        chat_session_id="chat-history",
        quiz=_build_quiz_draft("Computer Networks", "Routing and congestion control.", 2),
    )
    await service.submit_attempt(
        quiz.id,
        [
            QuizAnswerSubmission(
                question_id=quiz.questions[0].id, answer=quiz.questions[0].correct_answer
            ),
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


async def test_quiz_service_accepts_chinese_true_false_payload(db_session):
    service = QuizService(db_session)

    quiz = await service.create_quiz(
        chat_session_id="chat-cn-tf",
        quiz=QuizDraft(
            topic="网络安全",
            question_count=1,
            questions=[
                QuizQuestionCreate(
                    question_type="true_false",
                    prompt="防火墙可以阻止所有攻击。",
                    options=["正确", "错误"],
                    correct_answer="错误",
                    explanation="防火墙不能阻止所有类型的攻击。",
                    points=1.0,
                )
            ],
        ),
    )

    assert quiz.questions[0].options == ["True", "False"]
    assert quiz.questions[0].correct_answer == "False"


async def test_single_choice_grading_accepts_option_letter(db_session):
    service = QuizService(db_session)
    question = QuizQuestion(
        id="q-sc",
        question_type="single_choice",
        prompt="Which protocol is connection-oriented?",
        options=["UDP", "TCP", "ICMP", "ARP"],
        correct_answer="TCP",
        explanation="TCP is connection-oriented.",
        points=1.0,
    )

    result = await service._grade_question(question, "B")

    assert result.is_correct is True
    assert result.score == 1.0


async def test_subjective_fallback_uses_rubric_terms(db_session):
    service = QuizService(db_session)
    service.llm_service.create_chat_completion = AsyncMock(
        side_effect=LLMConfigurationError("missing")
    )
    question = QuizQuestion(
        id="q-sa",
        question_type="short_answer",
        prompt="Why is scheduling important?",
        options=[],
        correct_answer="Scheduling allocates CPU time among runnable tasks.",
        explanation="Explain the purpose of scheduling.",
        rubric="Mention CPU time allocation, fairness, or runnable tasks.",
        points=2.0,
    )

    score, feedback = await service._grade_subjective_answer(
        question, "It decides how CPU time is shared fairly across runnable tasks."
    )

    assert score > 0.0
    assert isinstance(feedback, str)
