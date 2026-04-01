from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.agent.core import StudentProductivityAgent
from backend.services.agent_tool_service import AgentToolService, ToolExecutionError


def _fake_response(*, content=None, tool_calls=None):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=content,
                    tool_calls=tool_calls,
                )
            )
        ]
    )


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


async def test_agent_returns_approval_request_for_local_file_tools(db_session, tmp_path):
    agent = StudentProductivityAgent(db_session)
    agent.llm_service.create_chat_completion = AsyncMock(
        return_value=_fake_response(
            tool_calls=[_fake_tool_call("read_local_file", {"path": "notes.txt"})]
        )
    )

    result = await agent.run("Read notes.txt", "session-approval", str(tmp_path))
    assert result["approval_request"]["tool_name"] == "read_local_file"
    assert result["tool_events"][0]["status"] == "awaiting_approval"


async def test_agent_resume_approval_executes_tool_and_finishes(db_session, tmp_path):
    notes = tmp_path / "notes.txt"
    notes.write_text("important notes", encoding="utf-8")

    agent = StudentProductivityAgent(db_session)
    agent.llm_service.create_chat_completion = AsyncMock(
        side_effect=[
            _fake_response(tool_calls=[_fake_tool_call("read_local_file", {"path": "notes.txt"})]),
            _fake_response(content="I read the file successfully."),
        ]
    )

    pending = await agent.run("Read notes.txt", "session-resume", str(tmp_path))
    result = await agent.resume_approval(pending["approval_request"]["id"], approved=True)

    assert result["response"] == "I read the file successfully."
    assert "read_local_file" in result["tools_used"]
    assert result["tool_events"][0]["status"] == "completed"


async def test_command_tool_accepts_string_command(db_session, tmp_path):
    service = AgentToolService(db_session)
    result_raw = await service.execute(
        "run_local_command",
        {"command": "pwd"},
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
