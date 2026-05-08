import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.tools import DeferredToolRequests

from backend.agent.core import StudentProductivityAgent
from backend.models.rag import RAGDirectorySettings
from backend.models.tooling import AgentTurnResult
from backend.services.agent_tool_service import AgentToolService, ToolExecutionError
from backend.services.approval_service import approval_service
from backend.services.rag_service import RAGService


def _fake_tool_call(name: str, arguments: dict[str, object], tool_call_id: str = "tool-1"):
    return SimpleNamespace(
        id=tool_call_id,
        function=SimpleNamespace(name=name, arguments=json.dumps(arguments, ensure_ascii=False)),
        model_dump=lambda **_: {
            "id": tool_call_id,
            "type": "function",
            "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
        },
    )


async def test_memory_tool_round_trip(db_session):
    service = AgentToolService(db_session)
    saved_raw = await service.execute(
        "memory_save",
        {"key": "favorite_editor", "value": "vscode", "category": "preference", "tags": ["dev"]},
        chat_session_id="chat-1",
        workspace_root=None,
    )
    saved = json.loads(saved_raw)
    assert saved["key"] == "favorite_editor"

    search_raw = await service.execute(
        "memory_search",
        {"query": "editor vscode"},
        chat_session_id="chat-1",
        workspace_root=None,
    )
    results = json.loads(search_raw)
    assert results[0]["key"] == "favorite_editor"


async def test_file_tool_rejects_path_escape(db_session, tmp_path):
    service = AgentToolService(db_session)
    outside_file = tmp_path.parent / "outside.txt"
    outside_file.write_text("secret", encoding="utf-8")
    with pytest.raises(ToolExecutionError):
        await service.execute(
            "read_local_file",
            {"path": str(outside_file)},
            chat_session_id="chat-1",
            workspace_root=str(tmp_path),
        )


async def test_file_tool_accepts_approved_absolute_directory_without_workspace(db_session, tmp_path):
    (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "list_local_files",
        {"path": str(tmp_path), "recursive": False},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert result["directory"] == tmp_path.as_posix()
    assert result["entries"][0]["path"] == "notes.md"


async def test_rag_index_folder_requires_configured_directory(db_session, tmp_path):
    (tmp_path / "notes.md").write_text("hello", encoding="utf-8")
    service = AgentToolService(db_session)

    with pytest.raises(ToolExecutionError):
        await service.execute(
            "rag_index_folder",
            {"path": str(tmp_path)},
            chat_session_id="chat-1",
            workspace_root=None,
        )


async def test_rag_index_folder_uses_authorized_default_directory(db_session, tmp_path):
    notes_root = tmp_path / "notes"
    notes_root.mkdir()
    (notes_root / "policy.md").write_text("The add/drop deadline is Friday.", encoding="utf-8")
    RAGService(db_session).save_directory_settings(
        RAGDirectorySettings(allowed_roots=[str(notes_root)], default_root=str(notes_root))
    )
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "rag_index_folder",
        {"path": "."},
        chat_session_id="chat-1",
        workspace_root=str(tmp_path.parent),
    )

    result = json.loads(result_raw)
    assert result["indexed"] == 1
    assert result["sources"][0]["relative_path"] == "policy.md"


async def test_rag_index_folder_rejects_path_outside_authorized_roots(db_session, tmp_path):
    notes_root = tmp_path / "notes"
    outside = tmp_path / "outside"
    notes_root.mkdir()
    outside.mkdir()
    RAGService(db_session).save_directory_settings(
        RAGDirectorySettings(allowed_roots=[str(notes_root)], default_root=str(notes_root))
    )
    service = AgentToolService(db_session)

    with pytest.raises(ToolExecutionError):
        await service.execute(
            "rag_index_folder",
            {"path": str(outside)},
            chat_session_id="chat-1",
            workspace_root=str(outside),
        )


async def test_agent_returns_approval_request_for_local_file_tools(db_session, tmp_path):
    """Test that agent returns approval request when tool requires approval."""
    agent = StudentProductivityAgent(db_session)

    # Mock the runtime to return a DeferredToolRequests (approval required)
    deferred_output = DeferredToolRequests(
        approvals=[
            SimpleNamespace(
                tool_call_id="tool-call-1",
                tool_name="read_local_file",
                args={"path": "notes.txt"},
            )
        ],
        calls=[],
        metadata={},
    )

    mock_result = AsyncMock()
    mock_result.output = deferred_output
    mock_result.all_messages = lambda: []

    mock_deps = AsyncMock()
    mock_deps.tool_events = []
    mock_deps.tools_used = []

    with patch.object(agent.runtime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (mock_result, mock_deps)
        with patch.object(agent.runtime, "extract_text_or_requests", return_value=deferred_output):
            with patch.object(
                agent.runtime, "parse_tool_arguments", return_value={"path": "notes.txt"}
            ):
                result = await agent.run("Read notes.txt", "session-approval", str(tmp_path))

                # Should return batch approval request
                assert result["approval_request"] is not None
                assert result["approval_request"]["approvals"][0]["tool_name"] == "read_local_file"
                assert result["tool_events"][0]["status"] == "awaiting_approval"


async def test_agent_resume_approval_returns_all_batch_approval_results(db_session, tmp_path):
    agent = StudentProductivityAgent(db_session)
    batch = approval_service.create_batch(
        session_id="session-batch-approval",
        user_input="List and index files",
        tool_calls=[
            {
                "tool_call_id": "call-1",
                "tool_name": "list_local_files",
                "tool_arguments": {"path": str(tmp_path)},
                "summary": "List files",
            },
            {
                "tool_call_id": "call-2",
                "tool_name": "rag_index_folder",
                "tool_arguments": {"path": str(tmp_path)},
                "summary": "Index folder",
            },
        ],
        workspace_root=None,
        messages=[],
        tools_used=[],
        tool_events=[],
        deferred_metadata={},
    )
    captured = {}

    async def fake_run_turn(**kwargs):
        captured["deferred_tool_results"] = kwargs["deferred_tool_results"]
        return AgentTurnResult(response="done")

    with patch.object(agent, "_run_turn", side_effect=fake_run_turn):
        result = await agent.resume_approval(batch.id, approved=True)

    assert result["response"] == "done"
    assert set(captured["deferred_tool_results"].approvals) == {"call-1", "call-2"}


@pytest.mark.skip(reason="Requires PydanticAI runtime mocking - complex test")
async def test_agent_resume_approval_executes_tool_and_finishes(db_session, tmp_path):
    """Test that approving a tool allows agent to continue and execute the tool."""
    pass


async def test_command_tool_accepts_string_command(db_session, tmp_path):
    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "run_local_command",
        {"command": "echo test"},
        chat_session_id="chat-1",
        workspace_root=str(tmp_path),
    )
    result = json.loads(result_raw)
    assert result["returncode"] == 0


async def test_command_tool_runs_python_script_with_interpreter(db_session, tmp_path):
    script = tmp_path / "hello.py"
    script.write_text("print('hello from script')\n", encoding="utf-8")

    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "run_local_command",
        {"command": ["hello.py"]},
        chat_session_id="chat-1",
        workspace_root=str(tmp_path),
    )
    result = json.loads(result_raw)
    assert result["returncode"] == 0
    assert "hello from script" in result["stdout"]


async def test_blackboard_get_all_courses_tool_returns_payload(db_session, monkeypatch):
    from backend.services import agent_tool_service

    class FakeResult:
        def model_dump(self, mode: str = "json"):
            assert mode == "json"
            return {
                "data": [
                    {
                        "course_id": "_101_1",
                        "name": "Software Engineering",
                        "blackboard_course_id": "CS304-2026",
                    }
                ],
                "is_cached": False,
                "cached_at": None,
                "warning": None,
            }

    class FakeBlackboardService:
        def __init__(self, _session, _provider):
            pass

        async def get_all_courses(self):
            return FakeResult()

    monkeypatch.setattr(agent_tool_service, "BlackboardService", FakeBlackboardService)

    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "blackboard_get_all_courses",
        {},
        chat_session_id="chat-1",
        workspace_root=None,
    )
    result = json.loads(result_raw)
    assert result["is_cached"] is False
    assert len(result["data"]) == 1
    assert result["data"][0]["course_id"] == "_101_1"
