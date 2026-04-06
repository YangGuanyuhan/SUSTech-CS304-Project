"""Real tool execution for the agent."""

from __future__ import annotations

import asyncio
import json
import re
import shlex
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from backend.services.datetime_service import DateTimeService
from backend.services.blackboard_service import DemoBlackboardProvider
from backend.services.memory_service import MemoryService
from backend.services.quiz_service import QuizService


_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_APPROVAL_REQUIRED_TOOLS = {
    "list_local_files",
    "read_local_file",
    "write_local_file",
    "run_local_command",
    "fetch_webpage",
}


def get_tool_definitions() -> list[dict[str, Any]]:
    """Return OpenAI-compatible tool schemas."""

    return [
        {
            "type": "function",
            "function": {
                "name": "memory_search",
                "description": "Search saved memories relevant to the current request.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_save",
                "description": "Save a durable memory for future conversations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string"},
                        "value": {},
                        "category": {"type": "string", "default": "general"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["key", "value"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "memory_delete",
                "description": "Delete memories that match a natural-language query.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_local_files",
                "description": "List files and directories inside the user-approved workspace root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "default": "."},
                        "recursive": {"type": "boolean", "default": False},
                        "max_entries": {"type": "integer", "minimum": 1, "maximum": 200, "default": 50},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_local_file",
                "description": "Read a UTF-8 text file inside the approved workspace root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_chars": {"type": "integer", "minimum": 100, "maximum": 50000, "default": 12000},
                    },
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_local_file",
                "description": "Write or append UTF-8 text into a file inside the approved workspace root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                        "append": {"type": "boolean", "default": False},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_local_command",
                "description": "Run a local command inside the approved workspace root.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "description": "Command and arguments as a JSON array.",
                        },
                        "timeout_seconds": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 120,
                            "default": 20,
                        },
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_webpage",
                "description": "Fetch and summarize a public webpage with user approval.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "max_chars": {"type": "integer", "minimum": 200, "maximum": 50000, "default": 12000},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "create_quiz",
                "description": "Create a quiz session for the user and return structured quiz questions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "topic": {"type": "string"},
                        "question_count": {"type": "integer", "minimum": 1, "maximum": 10, "default": 5},
                        "source_material": {"type": "string"},
                        "title": {"type": "string"},
                    },
                    "required": ["topic"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "quiz_history_summary",
                "description": "Summarize the user's recent quiz attempts for personalized study guidance.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_current_datetime",
                "description": "Get current date and time with structured fields including timezone and UTC offset.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "blackboard_test_api_available",
                "description": "Check whether Blackboard API endpoint users/me is currently available.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "blackboard_get_calendar_items",
                "description": "Fetch key assignment-related calendar items from Blackboard.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]


class ToolExecutionError(ValueError):
    """Raised when a tool request is invalid or unsafe."""


class AgentToolService:
    """Execute real tools with workspace scoping and approval checks."""

    def __init__(self, session: Session):
        self.session = session
        self.memory_service = MemoryService(session)
        self.quiz_service = QuizService(session)

    def requires_approval(self, tool_name: str) -> bool:
        return tool_name in _APPROVAL_REQUIRED_TOOLS

    def build_approval_summary(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        workspace_root: str | None,
    ) -> str:
        if tool_name == "list_local_files":
            return f"List files under `{arguments.get('path', '.')}` in workspace `{workspace_root or '<unset>'}`."
        if tool_name == "read_local_file":
            return f"Read local file `{arguments.get('path', '')}` in workspace `{workspace_root or '<unset>'}`."
        if tool_name == "write_local_file":
            mode = "append to" if arguments.get("append") else "write"
            return f"{mode.capitalize()} local file `{arguments.get('path', '')}` in workspace `{workspace_root or '<unset>'}`."
        if tool_name == "run_local_command":
            raw_command = arguments.get("command", [])
            command = raw_command if isinstance(raw_command, str) else " ".join(raw_command)
            return f"Run local command `{command}` in workspace `{workspace_root or '<unset>'}`."
        if tool_name == "fetch_webpage":
            return f"Visit webpage `{arguments.get('url', '')}` and extract content."
        return f"Execute tool `{tool_name}`."

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        chat_session_id: str,
        workspace_root: str | None,
    ) -> str:
        if tool_name == "memory_search":
            return await self._memory_search(arguments)
        if tool_name == "memory_save":
            return await self._memory_save(arguments)
        if tool_name == "memory_delete":
            return await self._memory_delete(arguments)
        if tool_name == "list_local_files":
            return await self._list_local_files(arguments, workspace_root)
        if tool_name == "read_local_file":
            return await self._read_local_file(arguments, workspace_root)
        if tool_name == "write_local_file":
            return await self._write_local_file(arguments, workspace_root)
        if tool_name == "run_local_command":
            return await self._run_local_command(arguments, workspace_root)
        if tool_name == "fetch_webpage":
            return await self._fetch_webpage(arguments)
        if tool_name == "create_quiz":
            return await self._create_quiz(arguments, chat_session_id=chat_session_id)
        if tool_name == "quiz_history_summary":
            return await self._quiz_history_summary(arguments)
        if tool_name == "get_current_datetime":
            return await self._get_current_datetime()
        if tool_name == "blackboard_test_api_available":
            return await self._blackboard_test_api_available()
        if tool_name == "blackboard_get_calendar_items":
            return await self._blackboard_get_calendar_items()
        raise ToolExecutionError(f"Unknown tool `{tool_name}`.")

    async def _memory_search(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        limit = int(arguments.get("limit", 5))
        if not query:
            raise ToolExecutionError("`query` is required for memory_search.")
        memories = await self.memory_service.get_relevant_memories(query, limit=limit)
        if not memories:
            return "No matching memories were found."
        payload = [
            {
                "id": item.id,
                "key": item.key,
                "category": item.category,
                "tags": item.tags,
                "value": item.value,
            }
            for item in memories
        ]
        return json.dumps(payload, ensure_ascii=False)

    async def _memory_save(self, arguments: dict[str, Any]) -> str:
        key = str(arguments.get("key", "")).strip()
        if not key:
            raise ToolExecutionError("`key` is required for memory_save.")
        record = await self.memory_service.save_memory(
            key=key,
            value=arguments.get("value"),
            category=str(arguments.get("category", "general")),
            tags=[str(tag) for tag in arguments.get("tags", [])],
        )
        return json.dumps(record.model_dump(mode="json"), ensure_ascii=False)

    async def _memory_delete(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ToolExecutionError("`query` is required for memory_delete.")
        deleted = await self.memory_service.delete_memories_by_query(query)
        return json.dumps({"deleted": deleted}, ensure_ascii=False)

    async def _list_local_files(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        base = self._resolve_path(workspace_root, str(arguments.get("path", ".")))
        recursive = bool(arguments.get("recursive", False))
        max_entries = int(arguments.get("max_entries", 50))
        pattern = "**/*" if recursive else "*"
        entries: list[dict[str, Any]] = []
        for item in sorted(base.glob(pattern))[:max_entries]:
            if item == base:
                continue
            entries.append(
                {
                    "path": item.relative_to(self._workspace_root(workspace_root)).as_posix(),
                    "type": "directory" if item.is_dir() else "file",
                }
            )
        return json.dumps({"directory": base.as_posix(), "entries": entries}, ensure_ascii=False)

    async def _read_local_file(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        path = self._resolve_path(workspace_root, str(arguments.get("path", "")))
        max_chars = int(arguments.get("max_chars", 12000))
        if not path.is_file():
            raise ToolExecutionError(f"`{path}` is not a readable file.")
        content = path.read_text(encoding="utf-8", errors="ignore")
        truncated = len(content) > max_chars
        payload = {
            "path": path.relative_to(self._workspace_root(workspace_root)).as_posix(),
            "truncated": truncated,
            "content": content[:max_chars],
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _write_local_file(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        path = self._resolve_path(workspace_root, str(arguments.get("path", "")))
        content = str(arguments.get("content", ""))
        append = bool(arguments.get("append", False))
        path.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with path.open(mode, encoding="utf-8") as handle:
            handle.write(content)
        return json.dumps(
            {
                "path": path.relative_to(self._workspace_root(workspace_root)).as_posix(),
                "bytes_written": len(content.encode("utf-8")),
                "append": append,
            },
            ensure_ascii=False,
        )

    async def _run_local_command(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        cwd = self._workspace_root(workspace_root)
        command = self._normalize_command(arguments.get("command"), cwd)
        timeout_seconds = int(arguments.get("timeout_seconds", 20))

        # Check if we need to use shell (for built-in commands like cd)
        shell_builtins = {"cd", "pwd", "echo", "export", "source", "alias", "history", "fg", "bg", "jobs", "kill", "exit"}
        use_shell = command[0] in shell_builtins

        if use_shell:
            # Use shell for built-in commands
            cmd_str = " ".join(command) if isinstance(command, list) else command
            process = await asyncio.create_subprocess_shell(
                cmd_str,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        else:
            process = await asyncio.create_subprocess_exec(
                *command,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout_seconds)
        except asyncio.TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ToolExecutionError(f"Command timed out after {timeout_seconds} seconds.") from exc

        payload = {
            "command": command,
            "cwd": str(cwd),
            "returncode": process.returncode,
            "ok": process.returncode == 0,
            "stdout": stdout.decode("utf-8", errors="ignore")[:12000],
            "stderr": stderr.decode("utf-8", errors="ignore")[:12000],
            "error": None if process.returncode == 0 else "Command exited with non-zero status.",
        }
        return json.dumps(payload, ensure_ascii=False)

    def _normalize_command(self, raw_command: Any, cwd: Path) -> list[str]:
        if isinstance(raw_command, str):
            command = shlex.split(raw_command)
        elif isinstance(raw_command, list) and raw_command and all(isinstance(item, str) for item in raw_command):
            command = list(raw_command)
        else:
            raise ToolExecutionError("`command` must be a non-empty string or string array.")

        first = command[0]
        candidate = cwd / first
        if candidate.is_file():
            if candidate.suffix == ".py":
                return ["python3", first, *command[1:]]
            if candidate.suffix == ".sh" and not candidate.stat().st_mode & 0o111:
                return ["bash", first, *command[1:]]
        return command

    async def _fetch_webpage(self, arguments: dict[str, Any]) -> str:
        url = str(arguments.get("url", "")).strip()
        max_chars = int(arguments.get("max_chars", 12000))
        if not url.startswith(("http://", "https://")):
            raise ToolExecutionError("`url` must start with http:// or https://")
        async with httpx.AsyncClient(timeout=20.0, follow_redirects=True, trust_env=False) as client:
            response = await client.get(url)
            response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        text = response.text
        if "html" in content_type:
            text = _WHITESPACE_RE.sub(" ", _TAG_RE.sub(" ", text)).strip()
        payload = {
            "url": str(response.url),
            "status_code": response.status_code,
            "content_type": content_type,
            "content": text[:max_chars],
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _create_quiz(self, arguments: dict[str, Any], *, chat_session_id: str) -> str:
        topic = str(arguments.get("topic", "")).strip()
        if not topic:
            raise ToolExecutionError("`topic` is required for create_quiz.")
        quiz = await self.quiz_service.create_quiz(
            chat_session_id=chat_session_id,
            topic=topic,
            question_count=int(arguments.get("question_count", 5)),
            source_material=arguments.get("source_material"),
            title=arguments.get("title"),
        )
        return json.dumps({"quiz_session": quiz.model_dump(mode="json")}, ensure_ascii=False)

    async def _quiz_history_summary(self, arguments: dict[str, Any]) -> str:
        history = await self.quiz_service.get_history_summary(limit=int(arguments.get("limit", 5)))
        return json.dumps({"history": history.model_dump(mode="json")}, ensure_ascii=False)

    async def _get_current_datetime(self) -> str:
        datetime_info = DateTimeService().get_current_datetime()
        return json.dumps(datetime_info.model_dump(mode="json"), ensure_ascii=False)

    async def _blackboard_test_api_available(self) -> str:
        provider = DemoBlackboardProvider()
        available = await provider.test_api_available()
        return json.dumps({"available": available}, ensure_ascii=False)

    async def _blackboard_get_calendar_items(self) -> str:
        provider = DemoBlackboardProvider()
        items = await provider.get_calendar_items()
        return json.dumps({"items": items}, ensure_ascii=False)

    def _workspace_root(self, workspace_root: str | None) -> Path:
        root = Path(workspace_root or "").expanduser()
        if not workspace_root:
            raise ToolExecutionError("No workspace root is configured. Ask the user to set one first.")
        try:
            resolved = root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ToolExecutionError(f"Workspace root `{workspace_root}` does not exist.") from exc
        if not resolved.is_dir():
            raise ToolExecutionError(f"Workspace root `{workspace_root}` is not a directory.")
        return resolved

    def _resolve_path(self, workspace_root: str | None, requested_path: str) -> Path:
        root = self._workspace_root(workspace_root)
        candidate = (root / requested_path).resolve() if not Path(requested_path).is_absolute() else Path(requested_path).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ToolExecutionError("Requested path escapes the configured workspace root.") from exc
        return candidate
