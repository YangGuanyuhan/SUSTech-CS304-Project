import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pydantic_ai.tools import DeferredToolRequests

from backend.agent.core import StudentProductivityAgent
from backend.config import get_settings
from backend.models.rag import RAGDirectorySettings
from backend.models.tooling import AgentTurnResult
from backend.services.agent_tool_service import AgentToolService, ToolExecutionError
from backend.services.approval_service import approval_service
from backend.services.chat_file_service import ChatFileService
from backend.services.rag_service import RAGService


def shared_root() -> Path:
    return Path(get_settings().shared_workspace_dir).resolve()


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
    assert saved["saved"] is True
    assert "favorite_editor" in saved["content"]

    search_raw = await service.execute(
        "memory_search",
        {"query": "editor vscode"},
        chat_session_id="chat-1",
        workspace_root=None,
    )
    results = json.loads(search_raw)
    assert results["long_term"][0]["metadata"]["key"] == "favorite_editor"


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


async def test_file_tool_accepts_approved_absolute_directory_without_workspace(
    db_session, tmp_path
):
    root = shared_root()
    root.mkdir(parents=True, exist_ok=True)
    (root / "notes.md").write_text("hello", encoding="utf-8")
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "list_local_files",
        {"path": str(root), "recursive": False},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert result["directory"] == root.as_posix()
    assert result["entries"][0]["path"] == "notes.md"


async def test_rag_index_folder_rejects_shared_workspace_escape(db_session, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "notes.md").write_text("hello", encoding="utf-8")
    service = AgentToolService(db_session)

    with pytest.raises(ToolExecutionError):
        await service.execute(
            "rag_index_folder",
            {"path": str(outside)},
            chat_session_id="chat-1",
            workspace_root=None,
        )


async def test_rag_index_folder_uses_authorized_default_directory(db_session, tmp_path):
    notes_root = shared_root() / "notes"
    notes_root.mkdir(parents=True)
    (notes_root / "policy.md").write_text("The add/drop deadline is Friday.", encoding="utf-8")
    RAGService(db_session).save_directory_settings(
        RAGDirectorySettings(allowed_roots=[str(notes_root)], default_root=str(notes_root))
    )
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "rag_index_folder",
        {"path": "."},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert result["indexed"] == 1
    assert result["sources"][0]["relative_path"] == "notes/policy.md"


async def test_rag_index_folder_rejects_path_outside_authorized_roots(db_session, tmp_path):
    notes_root = shared_root() / "notes"
    outside = tmp_path / "outside"
    notes_root.mkdir(parents=True)
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


async def test_rag_search_uses_global_scope_when_chat_uploads_exist(db_session, tmp_path):
    local_root = tmp_path / "local"
    chat_root = tmp_path / "chat"
    local_root.mkdir()
    chat_root.mkdir()
    (local_root / "global.md").write_text("The deadline is Monday.", encoding="utf-8")
    (chat_root / "upload.md").write_text("The deadline is Friday.", encoding="utf-8")
    await RAGService(db_session).index_folder(
        ".",
        workspace_root=str(local_root),
        owner_id="local-user",
    )
    await RAGService(db_session).index_folder(
        ".",
        workspace_root=str(chat_root),
        owner_id=ChatFileService.chat_owner_id("chat-1"),
    )
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "rag_search",
        {"query": "deadline", "top_k": 2},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert [hit["relative_path"] for hit in result] == ["global.md"]


async def test_uploaded_file_search_falls_back_to_uploaded_chunks_for_generic_query(
    db_session, tmp_path
):
    chat_root = tmp_path / "chat"
    chat_root.mkdir()
    (chat_root / "upload.md").write_text(
        "First uploaded section about scheduling.\n\nSecond uploaded section about memory.",
        encoding="utf-8",
    )
    await RAGService(db_session).index_folder(
        ".",
        workspace_root=str(chat_root),
        owner_id=ChatFileService.chat_owner_id("chat-1"),
    )
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "uploaded_file_search",
        {"query": "something unrelated", "top_k": 1},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert result[0]["relative_path"] == "upload.md"
    assert "scheduling" in result[0]["text"]


async def test_uploaded_file_search_returns_uploaded_chunks_for_generic_file_question(
    db_session, tmp_path
):
    chat_root = tmp_path / "chat"
    chat_root.mkdir()
    (chat_root / "upload.md").write_text(
        "The uploaded file explains page replacement algorithms.",
        encoding="utf-8",
    )
    await RAGService(db_session).index_folder(
        ".",
        workspace_root=str(chat_root),
        owner_id=ChatFileService.chat_owner_id("chat-1"),
    )
    service = AgentToolService(db_session)

    result_raw = await service.execute(
        "uploaded_file_search",
        {"query": "uploaded PDF", "top_k": 2},
        chat_session_id="chat-1",
        workspace_root=None,
    )

    result = json.loads(result_raw)
    assert result[0]["relative_path"] == "upload.md"
    assert "page replacement" in result[0]["text"]


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
    root = shared_root()
    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "run_local_command",
        {"command": "echo test"},
        chat_session_id="chat-1",
        workspace_root=str(root),
    )
    result = json.loads(result_raw)
    assert result["returncode"] == 0


async def test_command_tool_runs_python_script_with_interpreter(db_session, tmp_path):
    root = shared_root()
    root.mkdir(parents=True, exist_ok=True)
    script = root / "hello.py"
    script.write_text("print('hello from script')\n", encoding="utf-8")

    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "run_local_command",
        {"command": ["hello.py"]},
        chat_session_id="chat-1",
        workspace_root=str(root),
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
    monkeypatch.setattr(
        service,
        "_authenticated_blackboard_provider",
        AsyncMock(return_value=object()),
    )
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


async def test_blackboard_download_files_recurses_and_returns_browser_links(
    db_session, monkeypatch
):
    from backend.services import blackboard_file_service
    from backend.services.blackboard_file_service import BBContent, BBFile

    class FakeCookieJar:
        def get_dict(self):
            return {"session": "ok"}

    class FakeSession:
        cookies = FakeCookieJar()

    class FakeProvider:
        _cas_session = FakeSession()

    class FakeManager:
        BASE_URL = "https://bb.example.test/learn/api/public/v1"

        def __init__(self, cookies, download_root="./BB_Files"):
            self.cookies = cookies
            self.download_root = download_root

        async def fetch_node_children(self, node):
            if node.is_loaded:
                return
            if node.id == "_101_1":
                node.children = [
                    BBContent(
                        id="lab9",
                        title="Lab 09",
                        type="x-bb-folder",
                        course_id="_101_1",
                        has_children=True,
                        parent_node=node,
                    ),
                    BBContent(
                        id="lab10",
                        title="Lab 10",
                        type="x-bb-folder",
                        course_id="_101_1",
                        has_children=True,
                        parent_node=node,
                    ),
                ]
            elif node.id == "lab9":
                node.children = [
                    BBContent(
                        id="doc9",
                        title="Spec",
                        type="x-bb-document",
                        course_id="_101_1",
                        parent_node=node,
                    )
                ]
            elif node.id == "doc9":
                node.attachments = [
                    BBFile(
                        id="att 1",
                        file_name="Lab 9 中文.pdf",
                        download_url="https://bb.example.test/raw",
                        parent_content=node,
                    )
                ]
            elif node.id == "lab10":
                node.children = [
                    BBContent(
                        id="doc10",
                        title="Spec",
                        type="x-bb-document",
                        course_id="_101_1",
                        parent_node=node,
                    )
                ]
            elif node.id == "doc10":
                node.attachments = [
                    BBFile(
                        id="att 10",
                        file_name="Lab 10.pdf",
                        download_url="https://bb.example.test/raw10",
                        parent_content=node,
                    )
                ]
            node.is_loaded = True

        async def close(self):
            return None

    monkeypatch.setattr(blackboard_file_service, "BBFileManager", FakeManager)

    service = AgentToolService(db_session)
    monkeypatch.setattr(
        service,
        "_authenticated_blackboard_provider",
        AsyncMock(return_value=FakeProvider()),
    )

    result_raw = await service.execute(
        "blackboard_download_files",
        {"course_id": "_101_1", "query": "lab9"},
        chat_session_id="chat-1",
        workspace_root=None,
    )
    result = json.loads(result_raw)

    assert result["files_found"] == 1
    assert result["files_returned"] == 1
    assert result["files"][0]["file_name"] == "Lab 9 中文.pdf"
    assert result["files"][0]["path"] == "Course _101_1 / Lab 09 / Spec / Lab 9 中文.pdf"
    assert result["files"][0]["download_url"].startswith("/api/blackboard/files/download")
    assert "attachment_id=att%201" in result["files"][0]["browser_download_url"]
    assert (
        "file_name=Lab%209%20%E4%B8%AD%E6%96%87.pdf" in result["files"][0]["browser_download_url"]
    )
