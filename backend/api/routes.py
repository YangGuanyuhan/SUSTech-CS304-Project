"""API routes."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.orm import Session

from backend.agent.core import StudentProductivityAgent
from backend.api.schemas import (
    ChatApprovalRequest,
    ChatRequest,
    EmailConfirmRequest,
    EmailDraftRequest,
    LLMConnectionTestRequest,
    LLMProfileRequest,
    LLMSettingsRequest,
    MemoryDeleteByQueryRequest,
    QuizAttemptRequest,
)
from backend.db.database import get_db_session
from backend.models.common import ApiResponse
from backend.models.settings import LLMProfile
from backend.services.blackboard_service import BlackboardService, MockBlackboardProvider
from backend.services.approval_service import approval_service
from backend.services.database_insights_service import DatabaseInsightsService
from backend.services.email_service import EmailService, UnconfirmedSendError
from backend.services.llm_service import LLMConnectionError, LLMService
from backend.services.memory_service import MemoryService
from backend.services.quiz_service import QuizService
from backend.services.runtime_settings import RuntimeLLMUpdate, runtime_settings
from backend.services.settings_service import SettingsService


router = APIRouter(prefix="/api")


def _chunk_text(text: str, chunk_size: int = 2000) -> list[str]:
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


async def _stream_agent_result(result: dict[str, object], *, session_id: str):
    approval_request = result.get("approval_request")
    if approval_request is not None:
        yield {
            "event": "approval_required",
            "data": json.dumps(
                {
                    **approval_request,
                    "tool_events": result.get("tool_events", []),
                }
            ),
        }
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "session_id": session_id,
                    "status": "approval_required",
                    "tool_events": result.get("tool_events", []),
                }
            ),
        }
        return

    # Return full response at once
    yield {"event": "message", "data": json.dumps({"chunk": str(result.get("response", ""))})}
    yield {
        "event": "done",
        "data": json.dumps(
            {
                "session_id": session_id,
                "status": "completed",
                "tools_used": result.get("tools_used", []),
                "tool_events": result.get("tool_events", []),
            }
        ),
    }


@router.get("/health", response_model=ApiResponse[dict[str, str]])
async def health() -> ApiResponse[dict[str, str]]:
    return ApiResponse(success=True, data={"status": "ok"})


@router.get("/settings/llm", response_model=ApiResponse[object])
async def get_llm_settings() -> ApiResponse[object]:
    return ApiResponse(success=True, data=runtime_settings.get_llm_config())


@router.put("/settings/llm", response_model=ApiResponse[object])
async def update_llm_settings(request: LLMSettingsRequest) -> ApiResponse[object]:
    config = runtime_settings.update_llm_config(RuntimeLLMUpdate.model_validate(request.model_dump()))
    return ApiResponse(success=True, data=config)


@router.post("/settings/llm/test", response_model=ApiResponse[object])
async def test_llm_settings(request: LLMConnectionTestRequest) -> ApiResponse[object]:
    previous = runtime_settings.get_llm_config()
    previous_secret = runtime_settings.get_secret_api_key()
    if any(value is not None for value in request.model_dump().values()):
        runtime_settings.update_llm_config(
            RuntimeLLMUpdate(
                provider=request.provider or previous.provider,
                model=request.model or previous.model,
                base_url=request.base_url if request.base_url is not None else previous.base_url,
                api_key=request.api_key,
            )
        )
    try:
        result = await LLMService().test_connection()
    except (LLMConnectionError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    finally:
        runtime_settings.update_llm_config(
            RuntimeLLMUpdate(
                provider=previous.provider,
                model=previous.model,
                base_url=previous.base_url,
                api_key=previous_secret,
                replace_api_key=True,
            )
        )
    return ApiResponse(success=True, data=result)


@router.get("/settings/llm/profiles", response_model=ApiResponse[object])
async def list_llm_profiles(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    profiles = await SettingsService(session).list_llm_profiles()
    return ApiResponse(success=True, data=profiles)


@router.put("/settings/llm/profiles", response_model=ApiResponse[object])
async def save_llm_profile(
    request: LLMProfileRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    profile = await SettingsService(session).save_llm_profile(
        LLMProfile(
            name=request.name,
            provider=request.provider,
            model=request.model,
            base_url=request.base_url,
        ),
        api_key=request.api_key,
    )
    return ApiResponse(success=True, data=profile)


@router.delete("/settings/llm/profiles/{name}", response_model=ApiResponse[dict[str, bool]])
async def delete_llm_profile(name: str, session: Session = Depends(get_db_session)) -> ApiResponse[dict[str, bool]]:
    deleted = await SettingsService(session).delete_llm_profile(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data={"deleted": True})


@router.post("/settings/llm/profiles/{name}/apply", response_model=ApiResponse[object])
async def apply_llm_profile(name: str, session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    profile = await SettingsService(session).apply_llm_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data=profile)


@router.post("/chat")
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_db_session),
) -> EventSourceResponse:
    agent = StudentProductivityAgent(session)

    async def event_generator():
        try:
            result = await agent.run(request.message, request.session_id, request.workspace_root)
            async for event in _stream_agent_result(result, session_id=request.session_id):
                yield event
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.post("/chat/approval")
async def handle_chat_approval(
    request: ChatApprovalRequest,
    session: Session = Depends(get_db_session),
) -> EventSourceResponse:
    pending = approval_service.get(request.approval_id)
    if pending is None:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if pending.session_id != request.session_id:
        raise HTTPException(status_code=400, detail="Approval request does not belong to this session")

    agent = StudentProductivityAgent(session)

    async def event_generator():
        result = await agent.resume_approval(request.approval_id, approved=request.approved)
        async for event in _stream_agent_result(result, session_id=request.session_id):
            yield event

    return EventSourceResponse(event_generator())


@router.get("/blackboard/courses", response_model=ApiResponse[object])
async def get_courses(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    result = await BlackboardService(session, MockBlackboardProvider()).get_all_courses()
    return ApiResponse(success=True, data=result)


@router.get("/database/overview", response_model=ApiResponse[object])
async def get_database_overview(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    overview = await DatabaseInsightsService(session).get_overview()
    return ApiResponse(success=True, data=overview)


@router.get("/memory", response_model=ApiResponse[object])
async def list_memories(
    category: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    result = await MemoryService(session).list_memories(category)
    return ApiResponse(success=True, data=result)


@router.delete("/memory/{memory_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_memory(memory_id: str, session: Session = Depends(get_db_session)) -> ApiResponse[dict[str, bool]]:
    deleted = await MemoryService(session).delete_memory(memory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Memory not found")
    return ApiResponse(success=True, data={"deleted": deleted})


@router.post("/memory/delete-by-query", response_model=ApiResponse[dict[str, int]])
async def delete_memory_by_query(
    request: MemoryDeleteByQueryRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[dict[str, int]]:
    deleted = await MemoryService(session).delete_memories_by_query(request.query)
    return ApiResponse(success=True, data={"deleted": deleted})


@router.get("/quiz/history", response_model=ApiResponse[object])
async def get_quiz_history(
    limit: int = Query(default=5, ge=1, le=20),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    history = await QuizService(session).get_history_summary(limit=limit)
    return ApiResponse(success=True, data=history)


@router.get("/quiz/{quiz_id}", response_model=ApiResponse[object])
async def get_quiz(quiz_id: str, session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    quiz = await QuizService(session).get_quiz(quiz_id)
    if quiz is None:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return ApiResponse(success=True, data=quiz)


@router.post("/quiz/{quiz_id}/attempts", response_model=ApiResponse[object])
async def submit_quiz_attempt(
    quiz_id: str,
    request: QuizAttemptRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        result = await QuizService(session).submit_attempt(quiz_id, request.answers)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ApiResponse(success=True, data=result)


@router.post("/email/draft", response_model=ApiResponse[object])
async def create_email_draft(
    request: EmailDraftRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    draft = await EmailService(session).draft_email(request.to, request.subject, request.body_instruction)
    return ApiResponse(success=True, data=draft)


@router.post("/email/confirm/{draft_id}", response_model=ApiResponse[object])
async def confirm_email(
    draft_id: str,
    request: EmailConfirmRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        result = await EmailService(session).send_email(draft_id, request.confirmed)
    except UnconfirmedSendError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, data=result)
