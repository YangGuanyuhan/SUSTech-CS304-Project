"""Quiz generation, grading, and history analysis."""

from __future__ import annotations

import asyncio
import json
import re
from statistics import mean
from uuid import uuid4

from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.db.repositories import QuizRepository
from backend.models.quiz import (
    QuizAnswerSubmission,
    QuizAttemptAnswerResult,
    QuizAttemptResult,
    QuizDraft,
    QuizHistoryEntry,
    QuizHistorySummary,
    QuizQuestion,
    QuizSession,
    normalize_true_false_token,
)
from backend.services.llm_service import LLMConfigurationError, LLMConnectionError, LLMService

_WORD_RE = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")
_CHOICE_PREFIX_RE = re.compile(r"^\(?([A-Da-d])[\).:\-]\s*")


class QuizService:
    """Persist quizzes, grade attempts, and summarize practice history."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = QuizRepository(session)
        self.llm_service = LLMService()
        self.subjective_grading_timeout_seconds = float(
            get_settings().quiz_subjective_grading_timeout
        )

    async def create_quiz(
        self,
        *,
        chat_session_id: str,
        quiz: QuizDraft,
    ) -> QuizSession:
        quiz = QuizDraft.model_validate(quiz)
        materialized_questions = [
            QuizQuestion(
                id=str(uuid4()),
                question_type=question.question_type,
                prompt=question.prompt,
                options=list(question.options),
                correct_answer=question.correct_answer,
                explanation=question.explanation,
                rubric=question.rubric,
                points=question.points,
            )
            for question in quiz.questions
        ]
        session_record = self.repository.create_session(
            chat_session_id=chat_session_id,
            title=quiz.title or f"{quiz.topic[:48]} Quiz",
            topic=quiz.topic,
            source_material=quiz.source_material,
        )
        question_records = self.repository.create_questions(
            quiz_session_id=session_record.id,
            questions=[question.model_dump(mode="json") for question in materialized_questions],
        )
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
                    options=record.options,
                    correct_answer=record.correct_answer,
                    explanation=record.explanation,
                    rubric=record.rubric,
                    points=record.points,
                )
                for record in question_records
            ],
            created_at=session_record.created_at,
        )

    async def get_quiz(self, quiz_id: str) -> QuizSession | None:
        session_record = self.repository.get_session(quiz_id)
        if session_record is None:
            return None
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
                    options=record.options,
                    correct_answer=record.correct_answer,
                    explanation=record.explanation,
                    rubric=record.rubric,
                    points=record.points,
                )
                for record in session_record.questions
            ],
            created_at=session_record.created_at,
        )

    async def submit_attempt(
        self, quiz_id: str, answers: list[QuizAnswerSubmission]
    ) -> QuizAttemptResult:
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

        attempt_record = self.repository.create_attempt(
            quiz_session_id=quiz_id,
            score=score,
            total_points=total_points,
            summary=summary,
        )
        self.repository.create_answers(
            attempt_id=attempt_record.id,
            answers=[
                {
                    "quiz_question_id": item.question_id,
                    "submitted_answer": item.submitted_answer,
                    "is_correct": item.is_correct,
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
        attempts = self.repository.list_recent_attempts(limit=limit)
        entries: list[QuizHistoryEntry] = []
        recent_topics: list[str] = []
        weak_areas: list[str] = []

        for attempt in attempts:
            quiz = self.repository.get_session(attempt.quiz_session_id)
            if quiz is None:
                continue
            answers = self.repository.list_answers_for_attempt(attempt.id)
            missed = [
                answer.feedback
                for answer in answers
                if answer.is_correct is False and answer.feedback
            ]
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

        average_score = (
            round(mean((entry.score / entry.total_points) * 100 for entry in entries), 2)
            if entries
            else 0.0
        )
        analysis = self._build_history_analysis(entries, weak_areas)
        return QuizHistorySummary(
            attempts=entries,
            total_attempts=len(entries),
            average_score=average_score,
            recent_topics=list(dict.fromkeys(recent_topics))[:5],
            personalized_analysis=analysis,
        )

    @staticmethod
    def _normalize_choice_text(value: str) -> str:
        return " ".join(value.strip().casefold().split())

    def _resolve_single_choice_submission(
        self, question: QuizQuestion, submitted_answer: str
    ) -> str:
        cleaned = submitted_answer.strip()
        if not cleaned:
            return ""

        label = cleaned[0].upper() if len(cleaned) == 1 and cleaned[0].isalpha() else None
        if label is None:
            match = _CHOICE_PREFIX_RE.match(cleaned)
            label = match.group(1).upper() if match else None
        if label is not None:
            index = ord(label) - ord("A")
            if 0 <= index < len(question.options):
                return question.options[index]
        return cleaned

    async def _grade_question(
        self, question: QuizQuestion, submitted_answer: str
    ) -> QuizAttemptAnswerResult:
        if question.question_type in {"single_choice", "true_false"}:
            resolved_submission = submitted_answer
            if question.question_type == "single_choice":
                resolved_submission = self._resolve_single_choice_submission(
                    question, submitted_answer
                )
            normalized_submitted = self._normalize_choice_text(resolved_submission)
            normalized_correct = self._normalize_choice_text(question.correct_answer)

            is_correct = normalized_submitted == normalized_correct
            if question.question_type == "true_false":
                normalized_bool_submitted = normalize_true_false_token(submitted_answer)
                normalized_bool_correct = normalize_true_false_token(question.correct_answer)
                if normalized_bool_submitted is not None and normalized_bool_correct is not None:
                    is_correct = normalized_bool_submitted == normalized_bool_correct

            return QuizAttemptAnswerResult(
                question_id=question.id,
                prompt=question.prompt,
                question_type=question.question_type,
                submitted_answer=submitted_answer,
                correct_answer=question.correct_answer,
                is_correct=is_correct,
                score=question.points if is_correct else 0.0,
                max_score=question.points,
                feedback=question.explanation
                if is_correct
                else f"Expected: {question.correct_answer}",
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

    async def _grade_subjective_answer(
        self, question: QuizQuestion, submitted_answer: str
    ) -> tuple[float, str]:
        if not submitted_answer.strip():
            return 0.0, "No answer submitted."
        try:
            prompt = f"""
You are a lenient and fair teaching assistant grading a short-answer quiz.
Question: {question.prompt}
Reference answer: {question.correct_answer}
Rubric: {question.rubric or question.explanation}
Student answer: {submitted_answer}
Maximum score: {question.points}

STRICT SCORING GUIDANCE (YOU MUST FOLLOW THESE RULES):
1. NO EXTERNAL CRITERIA: Evaluate the student's answer STRICTLY against the Reference answer and Rubric. DO NOT invent new requirements. If the question or rubric does not explicitly ask for examples, dates, or specific terminology, DO NOT penalize the student for omitting them.
2. FULL CREDIT DEFAULT: If the student's answer captures the core meaning or fundamental principle of the Reference answer, you MUST award the maximum score ({question.points}). Do not deduct points just because the answer is brief or lacks elaboration.
3. PENALIZE ONLY FOR ERRORS: Deduct points ONLY if the student's answer contains direct factual errors, contradicts the reference, or completely misses the core concept.
4. SYNONYMS ARE ACCEPTABLE: Accept answers formulated in the student's own words as long as the underlying logic is correct. 

Remember: Your goal is to verify if the student understands the basic concept, not to evaluate their essay-writing skills.
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
                                    "description": "The score to award the student. Must be between 0 and the maximum score.",
                                },
                                "feedback": {
                                    "type": "string",
                                    "description": "Constructive feedback on the student's answer.",
                                },
                            },
                            "required": ["score", "feedback"],
                        },
                    },
                }
            ]

            response = await asyncio.wait_for(
                self.llm_service.create_chat_completion(
                    [
                        {
                            "role": "system",
                            "content": "You are an automated grader for short answers.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    tools=tools,
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
            TimeoutError,
            LLMConfigurationError,
            LLMConnectionError,
            ValueError,
            KeyError,
            json.JSONDecodeError,
        ):
            return self._grade_subjective_answer_fallback(question, submitted_answer)

    def _grade_subjective_answer_fallback(
        self, question: QuizQuestion, submitted_answer: str
    ) -> tuple[float, str]:
        answer_terms = set(_WORD_RE.findall(submitted_answer.lower()))
        reference_terms = set(_WORD_RE.findall((question.correct_answer or "").lower()))
        rubric_terms = set(
            _WORD_RE.findall((question.rubric or question.explanation or "").lower())
        )
        target_terms = reference_terms | rubric_terms
        if not answer_terms or not target_terms:
            return 0.0, "Answer was too brief to match the expected key ideas."
        overlap = len(answer_terms & target_terms)
        coverage = overlap / max(1, len(target_terms))
        core_overlap = len(answer_terms & reference_terms)
        core_coverage = core_overlap / max(1, len(reference_terms)) if reference_terms else coverage
        ratio = max(coverage, core_coverage)
        score = round(min(question.points, question.points * min(1.0, ratio * 1.5)), 2)
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
        incorrect = [
            item for item in results if item.is_correct is False or item.score < item.max_score
        ]
        if not incorrect:
            return f"Great work. You scored {score}/{total_points} with no missed questions."
        focus = "; ".join(item.prompt[:80] for item in incorrect[:2])
        return f"You scored {score}/{total_points}. Review these areas: {focus}"

    def _build_history_analysis(
        self, entries: list[QuizHistoryEntry], weak_areas: list[str]
    ) -> str:
        if not entries:
            return "No quiz attempts yet. Start with a short quiz to build a learning profile."
        latest = entries[0]
        if latest.score >= latest.total_points * 0.8:
            return (
                "Recent performance is strong. Increase difficulty or expand into adjacent topics."
            )
        if weak_areas:
            return f"Recent attempts show recurring weaknesses around: {weak_areas[0]}"
        return "Recent attempts show room for improvement. Revisit missed questions and retry with a shorter quiz."
