"""Quiz generation, grading, and history analysis."""

from __future__ import annotations

import asyncio
import json
import re
from statistics import mean
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db import crud
from backend.models.quiz import (
    QuizAnswerSubmission,
    QuizAttemptAnswerResult,
    QuizAttemptResult,
    QuizHistoryEntry,
    QuizHistorySummary,
    QuizQuestion,
    QuizSession,
)
from backend.services.llm_service import LLMConfigurationError, LLMConnectionError, LLMService


_WORD_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")


class QuizService:
    """Create quizzes, grade attempts, and summarize practice history."""

    def __init__(self, session: Session):
        self.session = session
        self.llm_service = LLMService()
        self.subjective_grading_timeout_seconds = float(get_settings().quiz_subjective_grading_timeout)

    async def create_quiz(
        self,
        *,
        chat_session_id: str,
        topic: str,
        question_count: int = 5,
        source_material: str | None = None,
        title: str | None = None,
    ) -> QuizSession:
        questions = await self._generate_questions(topic, question_count, source_material)
        session_record = await crud.create_quiz_session(
            self.session,
            chat_session_id=chat_session_id,
            title=title or f"{topic[:48]} Quiz",
            topic=topic,
            source_material=source_material,
        )
        question_records = await crud.create_quiz_questions(
            self.session,
            quiz_session_id=session_record.id,
            questions=[question.model_dump(mode="json") for question in questions],
        )
        persisted_questions = [
            QuizQuestion(
                id=record.id,
                question_type=record.question_type,
                prompt=record.prompt,
                options=json.loads(record.options_json),
                correct_answer=record.correct_answer,
                explanation=record.explanation,
                rubric=record.rubric,
                points=record.points,
            )
            for record in question_records
        ]
        return QuizSession(
            id=session_record.id,
            chat_session_id=session_record.chat_session_id,
            title=session_record.title,
            topic=session_record.topic,
            source_material=session_record.source_material,
            questions=persisted_questions,
            created_at=session_record.created_at,
        )

    async def get_quiz(self, quiz_id: str) -> QuizSession | None:
        session_record = await crud.get_quiz_session(self.session, quiz_id)
        if session_record is None:
            return None
        question_records = await crud.list_quiz_questions(self.session, quiz_id)
        return QuizSession(
            id=session_record.id,
            chat_session_id=session_record.chat_session_id,
            title=session_record.title,
            topic=session_record.topic,
            source_material=session_record.source_material,
            questions=[
                QuizQuestion(
                    id=record.id,
                    question_type=record.question_type,
                    prompt=record.prompt,
                    options=json.loads(record.options_json),
                    correct_answer=record.correct_answer,
                    explanation=record.explanation,
                    rubric=record.rubric,
                    points=record.points,
                )
                for record in question_records
            ],
            created_at=session_record.created_at,
        )

    async def submit_attempt(self, quiz_id: str, answers: list[QuizAnswerSubmission]) -> QuizAttemptResult:
        quiz = await self.get_quiz(quiz_id)
        if quiz is None:
            raise ValueError("Quiz not found")

        answers_by_id = {answer.question_id: answer.answer for answer in answers}
        results: list[QuizAttemptAnswerResult] = []
        for question in quiz.questions:
            submitted_answer = answers_by_id.get(question.id, "").strip()
            result = await self._grade_question(question, submitted_answer)
            results.append(result)

        score = round(sum(item.score for item in results), 2)
        total_points = round(sum(item.max_score for item in results), 2)
        summary = self._build_attempt_summary(results, score, total_points)

        attempt_record = await crud.create_quiz_attempt(
            self.session,
            quiz_session_id=quiz_id,
            score=score,
            total_points=total_points,
            summary=summary,
        )
        await crud.create_quiz_answers(
            self.session,
            attempt_id=attempt_record.id,
            answers=[
                {
                    "quiz_question_id": item.question_id,
                    "submitted_answer": item.submitted_answer,
                    "is_correct": None if item.is_correct is None else str(item.is_correct).lower(),
                    "score": item.score,
                    "feedback": item.feedback,
                }
                for item in results
            ],
        )

        return QuizAttemptResult(
            attempt_id=attempt_record.id,
            quiz_id=quiz_id,
            score=score,
            total_points=total_points,
            submitted_at=attempt_record.submitted_at,
            answers=results,
            summary=summary,
        )

    async def get_history_summary(self, limit: int = 5) -> QuizHistorySummary:
        attempts = await crud.list_recent_quiz_attempts(self.session, limit=limit)
        entries: list[QuizHistoryEntry] = []
        recent_topics: list[str] = []
        weak_areas: list[str] = []

        for attempt in attempts:
            quiz = await crud.get_quiz_session(self.session, attempt.quiz_session_id)
            if quiz is None:
                continue
            answers = await crud.list_quiz_answers_for_attempt(self.session, attempt.id)
            missed = [answer.feedback for answer in answers if answer.is_correct == "false" and answer.feedback]
            weak_areas.extend(missed[:2])
            recent_topics.append(quiz.topic)
            entries.append(
                QuizHistoryEntry(
                    quiz_id=quiz.id,
                    attempt_id=attempt.id,
                    title=quiz.title,
                    topic=quiz.topic,
                    score=attempt.score,
                    total_points=attempt.total_points,
                    submitted_at=attempt.submitted_at,
                    weak_areas=missed[:3],
                )
            )

        average_score = round(mean((entry.score / entry.total_points) * 100 for entry in entries), 2) if entries else 0.0
        analysis = self._build_history_analysis(entries, weak_areas)
        return QuizHistorySummary(
            attempts=entries,
            total_attempts=len(entries),
            average_score=average_score,
            recent_topics=list(dict.fromkeys(recent_topics))[:5],
            personalized_analysis=analysis,
        )

    async def _generate_questions(
        self,
        topic: str,
        question_count: int,
        source_material: str | None,
    ) -> list[QuizQuestion]:
        try:
            return await self._generate_questions_with_llm(topic, question_count, source_material)
        except Exception as e:
            # Log the error for debugging
            import logging
            logging.warning(f"Quiz generation failed, using fallback: {e}")
            return self._build_fallback_quiz(topic, question_count, source_material)

    async def _generate_questions_with_llm(
        self,
        topic: str,
        question_count: int,
        source_material: str | None,
    ) -> list[QuizQuestion]:
        prompt = f"""Generate a quiz about {topic}."""
        
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "generate_quiz",
                    "description": "Generates a list of quiz questions.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "questions": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "question_type": {
                                            "type": "string", 
                                            "enum": ["single_choice", "true_false", "short_answer"]
                                        },
                                        "prompt": {"type": "string"},
                                        "options": {
                                            "type": "array", 
                                            "items": {"type": "string"}
                                        },
                                        "correct_answer": {"type": "string"},
                                        "explanation": {"type": "string"},
                                        "rubric": {"type": ["string", "null"]},
                                        "points": {"type": "number"}
                                    },
                                    "required": ["question_type", "prompt", "options", "correct_answer", "explanation", "points"]
                                }
                            }
                        },
                        "required": ["questions"]
                    }
                }
            }
        ]

        response = await self.llm_service.create_chat_completion(
            [
                {"role": "system", "content": "You are a specialized quiz generation assistant."},
                {"role": "user", "content": prompt},
            ],
            tools=tools
        )
        
        tool_calls = response.choices[0].message.tool_calls
        if not tool_calls:
            raise ValueError("No tool calls returned from LLM for quiz generation.")
            
        payload = json.loads(tool_calls[0].function.arguments)
        
        questions = []
        for item in payload.get("questions", [])[:question_count]:
            questions.append(
                QuizQuestion(
                    id=str(uuid4()),
                    question_type=item["question_type"],
                    prompt=item["prompt"],
                    options=item.get("options", []),
                    correct_answer=item["correct_answer"],
                    explanation=item["explanation"],
                    rubric=item.get("rubric"),
                    points=float(item.get("points", 1.0)),
                )
            )
        if not questions:
            raise ValueError("Quiz generation returned no questions")
        return questions

    def _build_fallback_quiz(
        self,
        topic: str,
        question_count: int,
        source_material: str | None,
    ) -> list[QuizQuestion]:
        """Build a simple fallback quiz when LLM is unavailable.

        Note: This produces basic questions as a last resort.
        The quality is limited - ideally LLM should generate these.
        """
        base = (source_material or topic).strip()
        snippet = base[:120] or topic
        questions: list[QuizQuestion] = []

        # Generate varied questions based on topic
        templates = [
            # Single choice - basic concept
            QuizQuestion(
                id=str(uuid4()),
                question_type="single_choice",
                prompt=f"What is a key concept related to {topic}?",
                options=[
                    f"Understanding {topic}",
                    "Unrelated topic",
                    "Completely wrong answer",
                    "Another incorrect option",
                ],
                correct_answer=f"Understanding {topic}",
                explanation=f"The quiz was generated from the topic: {topic}",
                points=1.0,
            ),
            # True/False - basic fact
            QuizQuestion(
                id=str(uuid4()),
                question_type="true_false",
                prompt=f"True or False: {topic} is an important concept in the subject area.",
                options=["True", "False"],
                correct_answer="True",
                explanation="The quiz topic was requested by the user.",
                points=1.0,
            ),
            # Short answer
            QuizQuestion(
                id=str(uuid4()),
                question_type="short_answer",
                prompt=f"Explain one key point about {topic}:",
                options=[],
                correct_answer=snippet,
                explanation="A good answer should mention key aspects of the topic.",
                rubric=f"Discuss {topic} with relevant details.",
                points=2.0,
            ),
            # Multiple choice variant
            QuizQuestion(
                id=str(uuid4()),
                question_type="single_choice",
                prompt=f"Which best describes {topic}?",
                options=[
                    f"Core concept: {topic}",
                    "Something completely different",
                    "An unrelated idea",
                    "Nonsense answer",
                ],
                correct_answer=f"Core concept: {topic}",
                explanation=f"This question relates to the topic: {topic}",
                points=1.0,
            ),
            # Another True/False
            QuizQuestion(
                id=str(uuid4()),
                question_type="true_false",
                prompt=f"True or False: The study of {topic} is useful for learning.",
                options=["True", "False"],
                correct_answer="True",
                explanation="User-requested topics are valuable for learning.",
                points=1.0,
            ),
        ]

        # Cycle through templates
        while len(questions) < question_count:
            questions.append(templates[len(questions) % len(templates)].model_copy(update={"id": str(uuid4())}))

        return questions[:question_count]

    async def _grade_question(self, question: QuizQuestion, submitted_answer: str) -> QuizAttemptAnswerResult:
        if question.question_type in {"single_choice", "true_false"}:
            normalized_submitted = submitted_answer.strip().lower()
            normalized_correct = question.correct_answer.strip().lower()

            # For true_false, also consider the first word (user might type "true" or "true.")
            is_correct = normalized_submitted == normalized_correct
            if not is_correct and question.question_type == "true_false":
                first_word = normalized_submitted.split()[0] if normalized_submitted else ""
                correct_first = normalized_correct.split()[0] if normalized_correct else ""
                is_correct = first_word == correct_first

            # For single_choice, check if submitted answer matches any option (case-insensitive)
            if not is_correct and question.question_type == "single_choice" and question.options:
                for opt in question.options:
                    if normalized_submitted == opt.strip().lower():
                        is_correct = True
                        break

            return QuizAttemptAnswerResult(
                question_id=question.id,
                prompt=question.prompt,
                question_type=question.question_type,
                submitted_answer=submitted_answer,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                score=question.points if is_correct else 0.0,
                max_score=question.points,
                feedback=question.explanation if is_correct else f"Expected: {question.correct_answer}",
                explanation=question.explanation,
            )

        score, feedback = await self._grade_subjective_answer(question, submitted_answer)
        return QuizAttemptAnswerResult(
            question_id=question.id,
            prompt=question.prompt,
            question_type=question.question_type,
            submitted_answer=submitted_answer,
            correct_answer=question.correct_answer,
            is_correct=None,
            score=score,
            max_score=question.points,
            feedback=feedback,
            explanation=question.explanation,
        )

    async def _grade_subjective_answer(self, question: QuizQuestion, submitted_answer: str) -> tuple[float, str]:
        if not submitted_answer.strip():
            return 0.0, "No answer submitted."
        try:
            prompt = f"""
Grade this short-answer response.
Question: {question.prompt}
Reference answer: {question.correct_answer}
Rubric: {question.rubric or question.explanation}
Student answer: {submitted_answer}
Maximum score: {question.points}
""".strip()
            
            tools = [
                {
                    "type": "function",
                    "function": {
                        "name": "grade_answer",
                        "description": "Provide a score and feedback for a student's answer.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "score": {
                                    "type": "number",
                                    "description": "The score to award the student. Must be between 0 and the maximum score."
                                },
                                "feedback": {
                                    "type": "string",
                                    "description": "Constructive feedback on the student's answer."
                                }
                            },
                            "required": ["score", "feedback"]
                        }
                    }
                }
            ]

            response = await asyncio.wait_for(
                self.llm_service.create_chat_completion(
                    [
                        {"role": "system", "content": "You are an automated grader for short answers."},
                        {"role": "user", "content": prompt},
                    ],
                    tools=tools
                ),
                timeout=self.subjective_grading_timeout_seconds,
            )
            
            tool_calls = response.choices[0].message.tool_calls
            if not tool_calls:
                raise ValueError("No tool calls returned from LLM for grading.")
            
            payload = json.loads(tool_calls[0].function.arguments)
            score = max(0.0, min(question.points, float(payload["score"])))
            return round(score, 2), str(payload["feedback"])
        except (
            asyncio.TimeoutError,
            LLMConfigurationError,
            LLMConnectionError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ):
            return self._grade_subjective_answer_fallback(question, submitted_answer)

    def _grade_subjective_answer_fallback(self, question: QuizQuestion, submitted_answer: str) -> tuple[float, str]:
        answer_terms = set(_WORD_RE.findall(submitted_answer.lower()))
        reference_terms = set(_WORD_RE.findall((question.correct_answer or "").lower()))
        if not answer_terms or not reference_terms:
            return 0.0, "Answer was too brief to match the expected key ideas."
        overlap = len(answer_terms & reference_terms)
        ratio = overlap / max(1, len(reference_terms))
        score = round(min(question.points, question.points * min(1.0, ratio * 1.4)), 2)
        feedback = (
            "Good coverage of the reference idea."
            if score >= question.points * 0.8
            else "Partially correct. Include more of the expected key idea."
        )
        return score, feedback

    def _build_attempt_summary(
        self,
        results: list[QuizAttemptAnswerResult],
        score: float,
        total_points: float,
    ) -> str:
        incorrect = [item for item in results if item.is_correct is False or item.score < item.max_score]
        if not incorrect:
            return f"Great work. You scored {score}/{total_points} with no missed questions."
        focus = "; ".join(item.prompt[:80] for item in incorrect[:2])
        return f"You scored {score}/{total_points}. Review these areas: {focus}"

    def _build_history_analysis(self, entries: list[QuizHistoryEntry], weak_areas: list[str]) -> str:
        if not entries:
            return "No quiz attempts yet. Start with a short quiz to build a learning profile."
        latest = entries[0]
        if latest.score >= latest.total_points * 0.8:
            return "Recent performance is strong. Increase difficulty or expand into adjacent topics."
        if weak_areas:
            return f"Recent attempts show recurring weaknesses around: {weak_areas[0]}"
        return "Recent attempts show room for improvement. Revisit missed questions and retry with a shorter quiz."
