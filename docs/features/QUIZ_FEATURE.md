# Quiz Feature

## Overview

The quiz feature enables the AI agent to generate and grade interactive quizzes inside chat conversations. Users can take quizzes on any topic, submit answers, and review their performance over time. The feature supports three question types, AI-powered short-answer grading, and a personal practice history panel.

## Question Types

| Type | Code | Grading |
|------|------|---------|
| Single Choice | `single_choice` | Exact match (supports letter labels A-D) |
| True / False | `true_false` | Exact match (supports Chinese aliases: 正确/错误) |
| Short Answer | `short_answer` | LLM grading with rubric; fallback to keyword overlap |

## Current Workflow

### Taking a Quiz

1. The user asks the agent to generate a quiz on a topic (e.g. "create a 5-question quiz about Python decorators").
2. The agent calls the `create_quiz` tool with a structured payload containing questions, options, correct answers, and explanations.
3. A `QuizPanel` renders inline in the chat, showing each question with interactive inputs.
4. The user fills in answers and clicks **提交测验** (Submit Quiz).
5. The system grades each answer and displays per-question results: correctness badge, feedback, and the correct answer.
6. A summary footer shows the total score.

### Reviewing History

1. Click the **测验历史** (Quiz History) button in the app header.
2. The history panel shows summary cards (total attempts, average score, personalized analysis) and a list of past attempts.
3. Click any attempt card to expand it and see the full per-question detail:
   - For **choice questions**: all options rendered with green (correct) and red (wrong pick) visual markers, plus a checkmark/cross icon.
   - For **short-answer questions**: your submitted answer, the reference answer, and AI-generated feedback.
4. Click the same card again to collapse it. Only one attempt is expanded at a time.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/quiz/history?limit=N` | Get history summary (attempts, average score, analysis) |
| `GET` | `/api/quiz/{quiz_id}` | Get a quiz session with all questions and correct answers |
| `POST` | `/api/quiz/{quiz_id}/attempts` | Submit answers and get graded results |
| `GET` | `/api/quiz/attempts/{attempt_id}` | Get detailed attempt results (per-question breakdown) |

### Submit Attempt Payload

```json
{
  "answers": [
    { "question_id": "<uuid>", "answer": "A decorator is a function that wraps another function" }
  ]
}
```

### Submit Attempt Response (`QuizAttemptResult`)

```json
{
  "attempt_id": "<uuid>",
  "quiz_id": "<uuid>",
  "score": 4.0,
  "total_points": 5.0,
  "submitted_at": "2026-05-22T10:30:00Z",
  "summary": "You scored 4.0/5.0. Review: decorator syntax",
  "answers": [
    {
      "question_id": "<uuid>",
      "prompt": "What is a Python decorator?",
      "question_type": "short_answer",
      "options": [],
      "submitted_answer": "A function that wraps another function",
      "correct_answer": "A callable that takes another function and extends its behavior",
      "is_correct": null,
      "score": 0.8,
      "max_score": 1.0,
      "feedback": "Good coverage of the reference idea.",
      "explanation": "Decorators use the @syntax to apply wrapper logic."
    }
  ]
}
```

## Scoring

- **Choice / True-False**: full points if the normalized answer matches the correct answer exactly, zero otherwise.
- **Short Answer**: the LLM grades on a scale of 0 to max points using a rubric. If the LLM is unavailable, a keyword-overlap fallback computes coverage against the reference answer and rubric terms.

## Frontend Entry Points

- **Chat** — ask the agent to create a quiz; take it inline via `QuizPanel`
- **Quiz History button** (app header) — opens `QuizHistoryPanel` overlay with summary cards, attempt list, and expandable detail

## Database Tables

| Table | Purpose |
|-------|---------|
| `quiz_sessions` | One quiz instance (title, topic, source material) |
| `quiz_questions` | Individual questions with type, prompt, options, correct answer, explanation |
| `quiz_attempts` | One submission per quiz session (aggregate score, summary) |
| `quiz_answers` | Per-question graded answer (submitted text, correctness, score, feedback) |

### Entity Relationships

```
quiz_sessions (1) ──< (N) quiz_questions
       |
       +───< quiz_attempts
                |
                +───< quiz_answers >─── quiz_questions
```

## Related Files

- `frontend/src/components/QuizPanel.vue` — inline quiz card (questions, inputs, results)
- `frontend/src/components/QuizHistoryPanel.vue` — history overlay (summary, attempt list, expandable detail)
- `frontend/src/components/ChatWindow.vue` — embeds QuizPanel for `create_quiz` tool calls
- `frontend/src/api/client.js` — `getQuizHistory`, `getQuiz`, `submitQuizAttempt`, `getQuizAttemptDetail`
- `backend/api/routes.py` — FastAPI quiz endpoints
- `backend/services/quiz_service.py` — quiz creation, grading, history analysis
- `backend/services/agent_tool_service.py` — `create_quiz` and `quiz_history_summary` agent tools
- `backend/db/repositories.py` — `QuizRepository` data access layer
- `backend/db/models.py` — SQLAlchemy ORM models (`QuizSessionRecord`, `QuizQuestionRecord`, `QuizAttemptRecord`, `QuizAnswerRecord`)
- `backend/models/quiz.py` — Pydantic business-logic models
- `tests/test_quiz_service.py` — unit tests
