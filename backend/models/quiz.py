"""Quiz models."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

QuizQuestionType = Literal["single_choice", "true_false", "short_answer"]
_TRUE_FALSE_PUNCTUATION = ".,!?;:，。！？；：()[]{}\"'“”‘’`·、<>《》"
_TRUE_FALSE_ALIASES: dict[str, str] = {
    "true": "true",
    "t": "true",
    "yes": "true",
    "y": "true",
    "1": "true",
    "correct": "true",
    "right": "true",
    "正确": "true",
    "对": "true",
    "是": "true",
    "没错": "true",
    "true/yes": "true",
    "false": "false",
    "f": "false",
    "no": "false",
    "n": "false",
    "0": "false",
    "incorrect": "false",
    "wrong": "false",
    "错误": "false",
    "错": "false",
    "否": "false",
    "不对": "false",
    "不是": "false",
    "不能": "false",
    "xx": "false",
    "��ȷ": "true",
    "��": "true",
    "����": "false",
}


def _clean_text(value: str) -> str:
    return value.strip()


def normalize_true_false_token(value: str | None) -> str | None:
    if value is None:
        return None
    token = _clean_text(str(value)).lower()
    if not token:
        return None
    token = token.strip(_TRUE_FALSE_PUNCTUATION)
    token = " ".join(token.split())
    if token in _TRUE_FALSE_ALIASES:
        return _TRUE_FALSE_ALIASES[token]
    first = token.split()[0] if token else ""
    if first in _TRUE_FALSE_ALIASES:
        return _TRUE_FALSE_ALIASES[first]
    return None


class QuizModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class QuizQuestionCreate(QuizModel):
    question_type: QuizQuestionType
    prompt: str = Field(
        min_length=1,
        description="The full question text shown to the student.",
    )
    options: list[str] = Field(
        default_factory=list,
        description=(
            "Required for single_choice and true_false questions. "
            "For true_false, ALWAYS provide exactly ['True', 'False']. "
            "For short_answer, ALWAYS provide []."
        ),
    )
    correct_answer: str = Field(
        min_length=1,
        description=(
            "The expected correct answer. For single_choice it must exactly match one option. "
            "For true_false it must be 'True' or 'False'."
        ),
    )
    explanation: str = Field(
        min_length=1,
        description="Short explanation shown after grading.",
    )
    rubric: str | None = Field(
        default=None,
        description=(
            "Required for short_answer questions. Describe the grading criteria or key ideas "
            "needed for full credit. Leave null for other question types."
        ),
    )
    points: float = Field(
        default=1.0,
        gt=0,
        le=100,
        description="Points awarded for this question.",
    )

    @field_validator("prompt", "correct_answer", "explanation", mode="before")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return _clean_text(str(value))

    @field_validator("rubric", mode="before")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = _clean_text(str(value))
        return stripped or None

    @field_validator("options", mode="before")
    @classmethod
    def _normalize_options(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise TypeError("options must be a list of strings.")
        cleaned = [_clean_text(str(item)) for item in value]
        if any(not item for item in cleaned):
            raise ValueError("options cannot contain empty values.")
        if len(set(cleaned)) != len(cleaned):
            raise ValueError("options must not contain duplicate values.")
        return cleaned

    @model_validator(mode="after")
    def _validate_question_shape(self) -> QuizQuestionCreate:
        if self.question_type == "single_choice":
            if len(self.options) < 2:
                raise ValueError("single_choice questions must provide at least two options.")
            if self.correct_answer not in self.options:
                raise ValueError("single_choice correct_answer must match one of the options.")
            return self

        if self.question_type == "true_false":
            normalized_options = {normalize_true_false_token(option) for option in self.options}
            if normalized_options != {"true", "false"} or len(self.options) != 2:
                raise ValueError(
                    "true_false questions must provide exactly two options: True and False."
                )
            normalized_answer = normalize_true_false_token(self.correct_answer)
            if normalized_answer not in {"true", "false"}:
                raise ValueError("true_false correct_answer must be either True or False.")
            self.options = ["True", "False"]
            self.correct_answer = "True" if normalized_answer == "true" else "False"
            return self

        if self.options:
            raise ValueError("short_answer questions cannot define options.")
        if not self.rubric:
            raise ValueError("short_answer questions must include a grading rubric.")
        return self


class QuizDraft(QuizModel):
    topic: str = Field(min_length=1, description="Main quiz topic.")
    question_count: int = Field(
        ge=1,
        le=10,
        description="Must exactly match the number of question objects in questions.",
    )
    questions: list[QuizQuestionCreate] = Field(
        min_length=1,
        max_length=10,
        description="The complete list of quiz questions to persist.",
    )
    title: str | None = Field(default=None, description="Optional quiz title.")
    source_material: str | None = Field(
        default=None,
        description="Optional source context used to author the quiz.",
    )

    @field_validator("topic", mode="before")
    @classmethod
    def _strip_topic(cls, value: str) -> str:
        return _clean_text(str(value))

    @field_validator("title", "source_material", mode="before")
    @classmethod
    def _strip_nullable_fields(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = _clean_text(str(value))
        return stripped or None

    @model_validator(mode="after")
    def _validate_question_count(self) -> QuizDraft:
        if len(self.questions) != self.question_count:
            raise ValueError("question_count must match the number of questions provided.")
        return self


class QuizCreateToolArguments(QuizModel):
    quiz: QuizDraft = Field(
        description=(
            "Complete quiz payload. Important formatting rules: "
            "true_false questions must include options exactly ['True', 'False']; "
            "single_choice correct_answer must match an option exactly; "
            "short_answer questions must use options=[] and include a rubric."
        )
    )


class QuizQuestion(QuizModel):
    id: str
    question_type: QuizQuestionType
    prompt: str
    options: list[str] = Field(default_factory=list)
    correct_answer: str
    explanation: str
    rubric: str | None = None
    points: float = 1.0


class QuizSession(QuizModel):
    id: str
    chat_session_id: str
    title: str
    topic: str
    source_material: str | None = None
    questions: list[QuizQuestion]
    created_at: datetime


class QuizAnswerSubmission(QuizModel):
    question_id: str
    answer: str


class QuizAttemptAnswerResult(QuizModel):
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


class QuizAttemptResult(QuizModel):
    attempt_id: str
    quiz_id: str
    score: float
    total_points: float
    submitted_at: datetime
    answers: list[QuizAttemptAnswerResult]
    summary: str


class QuizHistoryEntry(QuizModel):
    quiz_id: str
    attempt_id: str
    title: str
    topic: str
    score: float
    total_points: float
    submitted_at: datetime
    weak_areas: list[str] = Field(default_factory=list)


class QuizHistorySummary(QuizModel):
    attempts: list[QuizHistoryEntry]
    total_attempts: int
    average_score: float
    recent_topics: list[str]
    personalized_analysis: str


class QuizToolPayload(QuizModel):
    quiz_session: QuizSession


class QuizSubmissionRequest(QuizModel):
    answers: list[QuizAnswerSubmission]


class QuizHistoryToolPayload(QuizModel):
    history: QuizHistorySummary
