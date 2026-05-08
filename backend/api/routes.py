"""API routes."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import string
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from backend.agent.core import StudentProductivityAgent
from backend.api.schemas import (
    BlackboardProfileRequest,
    BlackboardSettingsRequest,
    CalendarEventCreateRequest,
    CalendarEventMoveRequest,
    CalendarEventUpdateRequest,
    ChatApprovalRequest,
    ChatRequest,
    EmailConfirmRequest,
    EmailDraftRequest,
    LLMConnectionTestRequest,
    LLMProfileRequest,
    LLMSettingsRequest,
    MemoryDeleteByQueryRequest,
    QuizAttemptRequest,
    RAGIndexFolderRequest,
    RAGQueryRequest,
    RAGSettingsRequest,
)
from backend.config import get_settings
from backend.db.database import get_db_session
from backend.models.calendar import CalendarEventCreate, CalendarEventMove, CalendarEventUpdate
from backend.models.common import ApiResponse
from backend.models.rag import RAGDirectorySettings
from backend.models.settings import BlackboardProfile, LLMProfile
from backend.services.approval_service import approval_service
from backend.services.blackboard_file_service import BBContent, BBFileManager
from backend.services.blackboard_service import BlackboardService, DemoBlackboardProvider
from backend.services.calendar_service import CalendarService
from backend.services.chat_file_service import CHAT_FILE_CONTEXT_CHUNK_LIMIT, ChatFileService
from backend.services.database_insights_service import DatabaseInsightsService
from backend.services.email_service import EmailService, UnconfirmedSendError
from backend.services.llm_service import LLMConnectionError, LLMService
from backend.services.memory_service import MemoryService
from backend.services.quiz_service import QuizService
from backend.services.rag_service import RAGProviderError, RAGService, RAGServiceError
from backend.services.runtime_settings import (
    RuntimeBlackboardUpdate,
    RuntimeLLMUpdate,
    runtime_settings,
)
from backend.services.settings_service import SettingsService

router = APIRouter(prefix="/api")


def _workspace_system_roots() -> list[Path]:
    candidates: list[Path] = []
    if os.name == "nt":
        candidates.extend(Path(f"{letter}:/") for letter in string.ascii_uppercase)
    else:
        candidates.append(Path("/"))

    roots: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve(strict=True)
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if resolved.is_dir() and key not in seen:
            roots.append(resolved)
            seen.add(key)
    return roots


def _workspace_shortcuts() -> list[dict[str, str]]:
    shortcuts = [
        ("Home", Path.home()),
        ("Project", Path.cwd()),
    ]
    items: list[dict[str, str]] = []
    seen: set[str] = set()
    for name, shortcut in shortcuts:
        try:
            resolved = shortcut.expanduser().resolve(strict=True)
        except OSError:
            continue
        key = os.path.normcase(str(resolved))
        if resolved.is_dir() and key not in seen:
            items.append({"name": name, "path": str(resolved)})
            seen.add(key)
    return items


def _directory_payload(path: str | None = None) -> dict[str, object]:
    requested = Path(path).expanduser() if path else Path.home()
    try:
        current = requested.resolve(strict=True)
    except OSError as exc:
        raise HTTPException(status_code=404, detail=f"Directory not found: {requested}") from exc
    if not current.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {current}")

    entries: list[dict[str, str]] = []
    try:
        for child in current.iterdir():
            try:
                if child.is_dir():
                    entries.append({"name": child.name, "path": str(child.resolve(strict=True))})
            except OSError:
                continue
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"Permission denied: {current}") from exc

    entries.sort(key=lambda item: item["name"].lower())
    parent = current.parent if current.parent != current else None
    return {
        "path": str(current),
        "parent": str(parent) if parent else None,
        "shortcuts": _workspace_shortcuts(),
        "roots": [{"name": str(root), "path": str(root)} for root in _workspace_system_roots()],
        "entries": entries,
    }


def _chunk_text(text: str, chunk_size: int = 2000) -> list[str]:
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


def _serialize_tool_event(event: object) -> dict[str, object]:
    if hasattr(event, "model_dump"):
        return event.model_dump(mode="json")
    if isinstance(event, dict):
        return event
    return {"tool_name": "unknown", "arguments": {}, "status": "failed", "output": str(event)}


def _serialize_tool_events(tool_events: object) -> list[dict[str, object]]:
    if not isinstance(tool_events, list):
        return []
    return [_serialize_tool_event(event) for event in tool_events]


async def _stream_agent_result(
    result: dict[str, object],
    *,
    session_id: str,
    emit_initial_tool_events: bool = True,
    emit_response: bool = True,
):
    tool_events = result.get("tool_events", [])
    if emit_initial_tool_events and tool_events:
        yield {
            "event": "tool_events",
            "data": json.dumps({"tool_events": tool_events}),
        }

    approval_request = result.get("approval_request")
    if approval_request is not None:
        yield {
            "event": "approval_required",
            "data": json.dumps(
                {
                    **approval_request,
                    "tool_events": tool_events,
                }
            ),
        }
        yield {
            "event": "done",
            "data": json.dumps(
                {
                    "session_id": session_id,
                    "status": "approval_required",
                    "tool_events": tool_events,
                }
            ),
        }
        return

    if emit_response:
        for chunk in _chunk_text(str(result.get("response", ""))):
            yield {"event": "message", "data": json.dumps({"chunk": chunk})}
    yield {
        "event": "done",
        "data": json.dumps(
            {
                "session_id": session_id,
                "status": "completed",
                "tools_used": result.get("tools_used", []),
                "tool_events": tool_events,
            }
        ),
    }


async def _stream_agent_execution(*, session_id: str, execute):
    event_queue: asyncio.Queue[dict[str, str]] = asyncio.Queue()

    async def on_tool_events(tool_events: list[object]) -> None:
        await event_queue.put(
            {
                "event": "tool_events",
                "data": json.dumps({"tool_events": _serialize_tool_events(tool_events)}),
            }
        )
        # Yield once so the SSE loop can flush "running" updates before heavy tool work continues.
        await asyncio.sleep(0)

    async def on_response_chunk(chunk: str) -> None:
        if not chunk:
            return
        await event_queue.put(
            {
                "event": "message",
                "data": json.dumps({"chunk": chunk}),
            }
        )
        # Yield once so the SSE loop can flush "running" updates before heavy tool work continues.
        await asyncio.sleep(0)

    async def on_thinking_chunk(chunk: str) -> None:
        if not chunk:
            return
        await event_queue.put(
            {
                "event": "reasoning",
                "data": json.dumps({"chunk": chunk}),
            }
        )
        await asyncio.sleep(0)

    thinking_handler = (
        on_thinking_chunk if runtime_settings.get_llm_config().enable_reasoning else None
    )
    run_task = asyncio.create_task(execute(on_tool_events, on_response_chunk, thinking_handler))
    response_streamed = False
    try:
        while True:
            if run_task.done() and event_queue.empty():
                break
            try:
                event = await asyncio.wait_for(event_queue.get(), timeout=0.1)
            except TimeoutError:
                continue
            if event.get("event") == "message":
                response_streamed = True
            yield event

        result = await run_task
        async for event in _stream_agent_result(
            result,
            session_id=session_id,
            emit_initial_tool_events=False,
            emit_response=not response_streamed,
        ):
            yield event
    finally:
        if not run_task.done():
            run_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await run_task


@router.get("/health", response_model=ApiResponse[dict[str, str]])
async def health() -> ApiResponse[dict[str, str]]:
    return ApiResponse(success=True, data={"status": "ok"})


@router.get("/workspace/directories", response_model=ApiResponse[dict[str, object]])
async def list_workspace_directories(
    path: str | None = Query(default=None),
) -> ApiResponse[dict[str, object]]:
    return ApiResponse(success=True, data=_directory_payload(path))


@router.get("/settings/llm", response_model=ApiResponse[object])
async def get_llm_settings() -> ApiResponse[object]:
    return ApiResponse(success=True, data=runtime_settings.get_llm_config())


@router.put("/settings/llm", response_model=ApiResponse[object])
async def update_llm_settings(request: LLMSettingsRequest) -> ApiResponse[object]:
    config = runtime_settings.update_llm_config(
        RuntimeLLMUpdate.model_validate(request.model_dump())
    )
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
                enable_reasoning=request.enable_reasoning,
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
                enable_reasoning=previous.enable_reasoning,
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
            enable_reasoning=request.enable_reasoning,
        ),
        api_key=request.api_key,
    )
    return ApiResponse(success=True, data=profile)


@router.delete("/settings/llm/profiles/{name}", response_model=ApiResponse[dict[str, bool]])
async def delete_llm_profile(
    name: str, session: Session = Depends(get_db_session)
) -> ApiResponse[dict[str, bool]]:
    deleted = await SettingsService(session).delete_llm_profile(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data={"deleted": True})


@router.post("/settings/llm/profiles/{name}/apply", response_model=ApiResponse[object])
async def apply_llm_profile(
    name: str, session: Session = Depends(get_db_session)
) -> ApiResponse[object]:
    profile = await SettingsService(session).apply_llm_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data=profile)


# Blackboard Profile Settings
@router.get("/settings/blackboard/profiles", response_model=ApiResponse[object])
async def list_bb_profiles(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    profiles = await SettingsService(session).list_bb_profiles()
    return ApiResponse(success=True, data=profiles)


@router.put("/settings/blackboard/profiles", response_model=ApiResponse[object])
async def save_bb_profile(
    request: BlackboardProfileRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    profile = await SettingsService(session).save_bb_profile(
        BlackboardProfile(
            name=request.name,
            student_id=request.student_id,
            base_url=request.base_url,
        ),
        password=request.password,
    )
    return ApiResponse(success=True, data=profile)


@router.delete("/settings/blackboard/profiles/{name}", response_model=ApiResponse[dict[str, bool]])
async def delete_bb_profile(
    name: str, session: Session = Depends(get_db_session)
) -> ApiResponse[dict[str, bool]]:
    deleted = await SettingsService(session).delete_bb_profile(name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data={"deleted": True})


@router.post("/settings/blackboard/profiles/{name}/apply", response_model=ApiResponse[object])
async def apply_bb_profile(
    name: str, session: Session = Depends(get_db_session)
) -> ApiResponse[object]:
    profile = await SettingsService(session).apply_bb_profile(name)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ApiResponse(success=True, data=profile)


# Blackboard Settings
@router.get("/settings/blackboard", response_model=ApiResponse[object])
async def get_blackboard_settings() -> ApiResponse[object]:
    return ApiResponse(success=True, data=runtime_settings.get_blackboard_config())


@router.put("/settings/blackboard", response_model=ApiResponse[object])
async def update_blackboard_settings(request: BlackboardSettingsRequest) -> ApiResponse[object]:
    config = runtime_settings.update_blackboard_config(
        RuntimeBlackboardUpdate.model_validate(request.model_dump())
    )
    return ApiResponse(success=True, data=config)


@router.post("/settings/blackboard/test", response_model=ApiResponse[object])
async def test_blackboard_settings(request: BlackboardSettingsRequest) -> ApiResponse[object]:
    """Test Blackboard connection with provided credentials."""
    from backend.services.blackboard_service import BlackboardService

    # Get student_id: from request > runtime > settings
    if request.student_id:
        student_id = request.student_id
    else:
        bb_config = runtime_settings.get_blackboard_config()
        student_id = bb_config.student_id

    # Get password: from request > runtime
    if request.replace_password and request.password:
        password = request.password
    elif request.password:
        password = request.password
    else:
        password = runtime_settings.get_secret_blackboard_password()

    # Get base_url: from request > runtime > settings
    if request.base_url:
        base_url = request.base_url
    else:
        bb_config = runtime_settings.get_blackboard_config()
        base_url = bb_config.base_url
        if not base_url:
            settings = get_settings()
            base_url = settings.blackboard_base_url

    if not student_id or not password:
        return ApiResponse(
            success=False,
            data={
                "error": f"Missing credentials - student_id: {bool(student_id)}, password: {bool(password)}"
            },
        )

    try:
        logged_in = await BlackboardService.test_connection(student_id, password, base_url)
        return ApiResponse(
            success=logged_in,
            data={
                "logged_in": logged_in,
                "message": "Connection successful" if logged_in else "Connection failed",
            },
        )
    except Exception as e:
        return ApiResponse(success=False, data={"error": str(e)})


@router.post("/chat")
async def chat(
    request: ChatRequest,
    session: Session = Depends(get_db_session),
) -> EventSourceResponse:
    agent = StudentProductivityAgent(session)

    async def event_generator():
        try:
            async for event in _stream_agent_execution(
                session_id=request.session_id,
                execute=lambda on_tool_events, on_response_chunk, on_thinking_chunk: agent.run(
                    request.message,
                    request.session_id,
                    request.workspace_root,
                    on_tool_events=on_tool_events,
                    on_response_chunk=on_response_chunk,
                    on_thinking_chunk=on_thinking_chunk,
                ),
            ):
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
        raise HTTPException(
            status_code=400, detail="Approval request does not belong to this session"
        )

    agent = StudentProductivityAgent(session)

    async def event_generator():
        try:
            async for event in _stream_agent_execution(
                session_id=request.session_id,
                execute=lambda on_tool_events, on_response_chunk, on_thinking_chunk: (
                    agent.resume_approval(
                        request.approval_id,
                        approved=request.approved,
                        on_tool_events=on_tool_events,
                        on_response_chunk=on_response_chunk,
                        on_thinking_chunk=on_thinking_chunk,
                    )
                ),
            ):
                yield event
        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())


@router.get("/blackboard/courses", response_model=ApiResponse[object])
async def get_courses(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    result = await BlackboardService(session, DemoBlackboardProvider()).get_all_courses()
    return ApiResponse(success=True, data=result)


@router.get("/calendar/events", response_model=ApiResponse[object])
async def get_calendar_events(
    start: datetime = Query(...),
    end: datetime = Query(...),
    include_blackboard: bool = Query(default=True),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    result = await CalendarService(session).list_events(
        start=start,
        end=end,
        include_blackboard=include_blackboard,
    )
    return ApiResponse(success=True, data=result)


@router.post("/calendar/events", response_model=ApiResponse[object])
async def create_calendar_event(
    request: CalendarEventCreateRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        event = await CalendarService(session).create_event(
            CalendarEventCreate.model_validate(request.model_dump())
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, data=event)


@router.patch("/calendar/events/{event_id}", response_model=ApiResponse[object])
async def update_calendar_event(
    event_id: str,
    request: CalendarEventUpdateRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        event = await CalendarService(session).update_event(
            event_id,
            CalendarEventUpdate.model_validate(request.model_dump()),
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ApiResponse(success=True, data=event)


@router.post("/calendar/events/{event_id}/move", response_model=ApiResponse[object])
async def move_calendar_event(
    event_id: str,
    request: CalendarEventMoveRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        event = await CalendarService(session).move_event(
            event_id,
            CalendarEventMove.model_validate(request.model_dump()),
        )
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ApiResponse(success=True, data=event)


@router.delete("/calendar/events/{event_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_calendar_event(
    event_id: str,
    session: Session = Depends(get_db_session),
) -> ApiResponse[dict[str, bool]]:
    try:
        deleted = await CalendarService(session).delete_event(event_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ApiResponse(success=True, data={"deleted": deleted})


@router.post("/calendar/events/{event_id}/clone", response_model=ApiResponse[object])
async def clone_calendar_event(
    event_id: str,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        event = await CalendarService(session).clone_blackboard_event(event_id)
    except ValueError as exc:
        status_code = 404 if "not found" in str(exc).lower() else 400
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc
    return ApiResponse(success=True, data=event)


@router.post("/calendar/sync/blackboard", response_model=ApiResponse[object])
async def sync_blackboard_calendar(
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    result = await CalendarService(session).sync_blackboard()
    return ApiResponse(success=True, data=result)


@router.get("/database/overview", response_model=ApiResponse[object])
async def get_database_overview(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    overview = await DatabaseInsightsService(session).get_overview()
    return ApiResponse(success=True, data=overview)


@router.get("/rag/settings", response_model=ApiResponse[object])
async def get_rag_settings(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    return ApiResponse(success=True, data=RAGService(session).get_directory_settings())


@router.put("/rag/settings", response_model=ApiResponse[object])
async def update_rag_settings(
    request: RAGSettingsRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        settings = RAGService(session).save_directory_settings(
            RAGDirectorySettings.model_validate(request.model_dump())
        )
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, data=settings)


@router.post("/rag/index-folder", response_model=ApiResponse[object])
async def index_rag_folder(
    request: RAGIndexFolderRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    service = RAGService(session)
    try:
        workspace_root, path = service.resolve_index_scope(
            path=request.path,
            workspace_root=request.workspace_root,
        )
        directory_settings = service.get_directory_settings()
        result = await service.index_folder(
            path,
            workspace_root=workspace_root,
            recursive=(
                request.recursive
                if request.recursive is not None
                else directory_settings.recursive_default
            ),
            extensions=request.extensions,
        )
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RAGProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ApiResponse(success=True, data=result)


@router.get("/rag/sources", response_model=ApiResponse[object])
async def list_rag_sources(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    return ApiResponse(success=True, data=RAGService(session).list_sources())


@router.get("/rag/status", response_model=ApiResponse[object])
async def get_rag_status(session: Session = Depends(get_db_session)) -> ApiResponse[object]:
    return ApiResponse(success=True, data=RAGService(session).status())


@router.post("/rag/session-files/upload", response_model=ApiResponse[object])
async def upload_rag_session_files(
    session_id: str = Form(...),
    files: list[UploadFile] = File(...),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        result = await ChatFileService(session).upload_and_index(
            session_id=session_id,
            files=files,
        )
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RAGProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ApiResponse(success=True, data=result)


@router.get("/rag/session-files", response_model=ApiResponse[object])
async def list_rag_session_files(
    session_id: str = Query(...),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        sources = ChatFileService(session).list_files(session_id)
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApiResponse(success=True, data=sources)


@router.delete("/rag/session-files/{source_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_rag_session_file(
    source_id: str,
    session_id: str = Query(...),
    session: Session = Depends(get_db_session),
) -> ApiResponse[dict[str, bool]]:
    try:
        deleted = ChatFileService(session).delete_file(session_id=session_id, source_id=source_id)
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat file source not found")
    return ApiResponse(success=True, data={"deleted": True})


@router.post("/rag/query", response_model=ApiResponse[object])
async def query_rag(
    request: RAGQueryRequest,
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    try:
        owner_ids = (
            ChatFileService(session).query_owner_ids(request.session_id)
            if request.session_id
            else None
        )
        result = await RAGService(session).query(
            request.query,
            top_k=request.top_k,
            owner_ids=owner_ids,
            prefer_owner_context=bool(request.session_id),
            context_limit=CHAT_FILE_CONTEXT_CHUNK_LIMIT,
        )
    except RAGServiceError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RAGProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return ApiResponse(success=True, data=result)


@router.delete("/rag/sources/{source_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_rag_source(
    source_id: str,
    session: Session = Depends(get_db_session),
) -> ApiResponse[dict[str, bool]]:
    deleted = RAGService(session).delete_source(source_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="RAG source not found")
    return ApiResponse(success=True, data={"deleted": True})


@router.get("/memory", response_model=ApiResponse[object])
async def list_memories(
    category: str | None = Query(default=None),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    result = await MemoryService(session).list_memories(category)
    return ApiResponse(success=True, data=result)


@router.delete("/memory/{memory_id}", response_model=ApiResponse[dict[str, bool]])
async def delete_memory(
    memory_id: str, session: Session = Depends(get_db_session)
) -> ApiResponse[dict[str, bool]]:
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
    draft = await EmailService(session).draft_email(
        request.to, request.subject, request.body_instruction
    )
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


# ─────────────────────────────────────────
# Blackboard File Management APIs
# ─────────────────────────────────────────

# Global file manager instance for this session
_bb_file_managers: dict[str, BBFileManager] = {}
# Cache for authenticated providers
_bb_providers_cache: dict[str, tuple] = {}  # key -> (provider, timestamp)
# Cache loaded Blackboard content nodes by (course_id, node_id)
_bb_node_cache: dict[tuple[str, str], BBContent] = {}
# Cache course title by course_id to prevent UI title regression to raw ids
_bb_course_title_cache: dict[str, str] = {}


def _get_or_create_manager(session_id: str, cookies: dict) -> BBFileManager:
    """Get or create a Blackboard file manager for the session."""
    if session_id not in _bb_file_managers:
        _bb_file_managers[session_id] = BBFileManager(cookies)
    return _bb_file_managers[session_id]


async def _get_authenticated_provider():
    """
    Get an authenticated Blackboard provider using configured credentials.
    Returns (provider, is_authenticated) tuple.
    """
    import time

    from backend.services.blackboard_service import DemoBlackboardProvider

    provider = DemoBlackboardProvider()
    student_id = None

    try:
        student_id, _password, _base_url = provider._get_credentials()
    except Exception as exc:
        print(f"[BB] Failed to resolve credentials: {exc}")

    cache_key = f"{student_id or 'default'}"

    # Check cache (valid for 1 hour)
    if cache_key in _bb_providers_cache:
        cached_provider, timestamp = _bb_providers_cache[cache_key]
        if (
            time.time() - timestamp < 3600
            and getattr(cached_provider, "_cas_session", None) is not None
        ):
            return cached_provider, True

    # Try to authenticate with runtime/settings fallback credentials.
    try:
        logged_in = await provider.bypass_cas_login()
        if logged_in:
            _bb_providers_cache[cache_key] = (provider, time.time())
            print(f"[BB] Provider authenticated for {student_id}")
            return provider, True

        print(f"[BB] Failed to authenticate provider for {student_id}")
        return provider, False
    except Exception as e:
        print(f"[BB] Error authenticating provider: {e}")
        return provider, False


async def _ensure_bb_runtime_from_profile(session: Session) -> None:
    """If runtime Blackboard student_id is missing, try auto-applying a saved BB profile."""
    bb_config = runtime_settings.get_blackboard_config()
    if bb_config.student_id:
        return

    profiles = await SettingsService(session).list_bb_profiles()
    if not profiles:
        return

    # Profiles are sorted by name in SettingsService; use the first available one as fallback.
    fallback_profile = profiles[0]
    await SettingsService(session).apply_bb_profile(fallback_profile.name)
    print(f"[BB] Auto-applied Blackboard profile: {fallback_profile.name}")


@router.get("/blackboard/files/courses", response_model=ApiResponse[object])
async def get_blackboard_courses(
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    """Get list of all Blackboard courses for current user."""
    try:
        await _ensure_bb_runtime_from_profile(session)

        # Get authenticated provider
        provider, is_authenticated = await _get_authenticated_provider()
        print(f"[BB][files/courses] authenticated={is_authenticated}")

        if is_authenticated and provider:
            try:
                courses_list = await provider.get_all_courses()
                print(f"[BB] Successfully fetched {len(courses_list)} courses from Blackboard")

                if courses_list:
                    # Convert Course objects to API response format
                    courses = [
                        {
                            "id": c.course_id,
                            "title": c.name,
                            "type": "x-bb-course",
                            "course_id": c.course_id,
                            "has_children": True,
                            "is_loaded": False,
                            "children": [],
                            "attachments": [],
                        }
                        for c in courses_list
                    ]
                    for c in courses_list:
                        _bb_course_title_cache[c.course_id] = c.name
                    return ApiResponse(success=True, data={"courses": courses})
                else:
                    print("[BB] No courses returned from Blackboard")
            except Exception as e:
                print(f"[BB] Error fetching courses: {e}")
                import traceback

                traceback.print_exc()
        else:
            print("[BB] Provider not authenticated")
            return ApiResponse(
                success=False,
                data={"courses": []},
                error="Blackboard 登录失败，请在设置中重新输入账号密码",
            )

        return ApiResponse(
            success=False,
            data={"courses": []},
            error="Blackboard 未返回课程数据",
        )

    except Exception as e:
        print(f"[BB] Error in get_blackboard_courses: {e}")
        import traceback

        traceback.print_exc()
        return ApiResponse(success=True, data={"courses": []})


@router.get("/blackboard/files/tree/{course_id}", response_model=ApiResponse[object])
async def get_blackboard_file_tree(
    course_id: str,
    node_id: str | None = Query(None),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    """Get file tree for a Blackboard course or node."""
    try:
        await _ensure_bb_runtime_from_profile(session)
        print(f"[BB][files/tree] request course_id={course_id}, node_id={node_id}")
        provider, is_authenticated = await _get_authenticated_provider()
        if not is_authenticated or provider is None or provider._cas_session is None:
            raise HTTPException(
                status_code=401, detail="Blackboard 登录失败，请在设置中重新输入账号密码"
            )

        if is_authenticated and provider and provider._cas_session:
            cookie_dict = provider._cas_session.cookies.get_dict()
            manager = _get_or_create_manager(f"bb:{course_id}", cookie_dict)

            if node_id:
                node = _bb_node_cache.get((course_id, node_id))
                if node is None:
                    # Recover node metadata when cache is missing (e.g., backend restart).
                    node_title = "Folder"
                    node_type = "x-bb-folder"
                    node_has_children = True
                    try:
                        meta = await manager._get_json(
                            f"{manager.BASE_URL}/courses/{course_id}/contents/{node_id}"
                        )
                        node_title = meta.get("title") or node_title
                        handler = meta.get("contentHandler", {}).get("id", "")
                        if "/" in handler:
                            node_type = handler.split("/")[-1]
                        node_has_children = bool(meta.get("hasChildren", True))
                    except Exception as exc:
                        print(
                            f"[BB][files/tree] failed to resolve node metadata for {node_id}: {exc}"
                        )

                    node = BBContent(
                        id=node_id,
                        title=node_title,
                        type=node_type,
                        course_id=course_id,
                        has_children=node_has_children,
                    )
                    _bb_node_cache[(course_id, node_id)] = node

                await manager.fetch_node_children(node)
                print(
                    f"[BB][files/tree] loaded node={node_id}, children={len(node.children)}, attachments={len(node.attachments)}"
                )

                for child in node.children:
                    _bb_node_cache[(course_id, child.id)] = child

                payload = node.to_dict()
                for attachment in payload.get("attachments", []):
                    file_name = attachment.get("file_name", "download.bin")
                    attachment["download_url"] = (
                        f"/blackboard/files/download?course_id={course_id}"
                        f"&content_id={node.id}"
                        f"&attachment_id={attachment.get('id')}"
                        f"&file_name={quote(str(file_name))}"
                    )

                return ApiResponse(success=True, data=payload)

            course_node = BBContent(
                id=course_id,
                title=_bb_course_title_cache.get(course_id, f"Course {course_id}"),
                type="x-bb-course",
                course_id=course_id,
                has_children=True,
            )
            _bb_node_cache[(course_id, course_id)] = course_node

            await manager.fetch_node_children(course_node)
            print(
                f"[BB][files/tree] loaded root course={course_id}, children={len(course_node.children)}, attachments={len(course_node.attachments)}"
            )

            for child in course_node.children:
                _bb_node_cache[(course_id, child.id)] = child

            return ApiResponse(success=True, data=course_node.to_dict())
        raise HTTPException(status_code=500, detail="Blackboard 文件树加载失败")
    except HTTPException:
        raise
    except Exception as e:
        print(f"[BB] Error in tree retrieval: {e}")
        import traceback

        traceback.print_exc()
    raise HTTPException(status_code=502, detail="Blackboard 文件树加载失败")


@router.get("/blackboard/files/download")
async def download_blackboard_file(
    course_id: str = Query(...),
    content_id: str = Query(...),
    attachment_id: str = Query(...),
    file_name: str | None = Query(None),
) -> Response:
    """Proxy Blackboard attachment download using server-side authenticated session."""
    provider, is_authenticated = await _get_authenticated_provider()
    if not is_authenticated or provider is None or provider._cas_session is None:
        raise HTTPException(status_code=401, detail="Blackboard 未登录或会话已过期")

    download_url = (
        "https://bb.sustech.edu.cn/learn/api/public/v1"
        f"/courses/{course_id}/contents/{content_id}/attachments/{attachment_id}/download"
    )

    try:
        upstream = provider._cas_session.get(download_url, timeout=60)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"下载请求失败: {exc}") from exc

    if upstream.status_code != 200:
        raise HTTPException(
            status_code=upstream.status_code,
            detail=f"Blackboard 下载失败 (status={upstream.status_code})",
        )

    resolved_name = (file_name or f"{attachment_id}.bin").strip() or f"{attachment_id}.bin"
    headers = {"Content-Disposition": f"attachment; filename*=UTF-8''{quote(resolved_name)}"}
    media_type = upstream.headers.get("Content-Type", "application/octet-stream")
    return Response(content=upstream.content, media_type=media_type, headers=headers)


@router.post("/blackboard/files/download-batch", response_model=ApiResponse[object])
async def download_blackboard_batch(
    course_id: str = Query(...),
    node_id: str | None = Query(None),
    session: Session = Depends(get_db_session),
) -> ApiResponse[object]:
    """Start batch download for a course or node."""
    raise HTTPException(
        status_code=400, detail="节点本身不能下载，请双击文件夹展开后，双击具体的文件进行下载"
    )
