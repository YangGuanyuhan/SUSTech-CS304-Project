"""Real tool execution for the agent."""

from __future__ import annotations

import asyncio
import json
import re
import shlex
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from sqlalchemy.orm import Session

from backend.models.calendar import CalendarEventCreate, CalendarEventMove, CalendarEventUpdate
from backend.services.blackboard_service import BlackboardService, DemoBlackboardProvider
from backend.services.calendar_service import CalendarService
from backend.services.chat_file_service import CHAT_FILE_CONTEXT_CHUNK_LIMIT, ChatFileService
from backend.services.datetime_service import DateTimeService
from backend.services.memory_service import MemoryService
from backend.services.quiz_service import QuizService
from backend.services.rag_service import RAGProviderError, RAGService, RAGServiceError
from backend.services.runtime_settings import runtime_settings
from backend.services.settings_service import SettingsService

_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")
_APPROVAL_REQUIRED_TOOLS = {
    "write_local_file",
    "run_local_command",
    "fetch_webpage",
    "rag_index_folder",
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
                "description": "List files and directories inside the user-approved workspace root. Do not use for current-chat uploaded PDFs/PPTs/DOCX files; use rag_search or rag_answer instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "default": "."},
                        "recursive": {"type": "boolean", "default": False},
                        "max_entries": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 200,
                            "default": 50,
                        },
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_local_file",
                "description": "Read a UTF-8 text file inside the approved workspace root. Do not use for current-chat uploaded PDFs/PPTs/DOCX files; use rag_search or rag_answer instead.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "max_chars": {
                            "type": "integer",
                            "minimum": 100,
                            "maximum": 50000,
                            "default": 12000,
                        },
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
                        "max_chars": {
                            "type": "integer",
                            "minimum": 200,
                            "maximum": 50000,
                            "default": 12000,
                        },
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rag_index_folder",
                "description": "Index a configured RAG directory or authorized subdirectory into the knowledge base.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "default": ".",
                            "description": "Relative path under the default RAG directory, or an absolute path inside an authorized RAG root.",
                        },
                        "recursive": {"type": "boolean", "default": True},
                        "extensions": {"type": "array", "items": {"type": "string"}},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rag_search",
                "description": "Search current-chat uploaded PDF/PPTX/DOCX files first, then indexed local study materials and school information. Use this for 'my uploaded PDF', 'this PPT', 'attached file', '课件', or '上传的资料'.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "rag_answer",
                "description": "Answer or summarize using current-chat uploaded PDF/PPTX/DOCX files first, then the indexed local knowledge base, with citations. Best tool for analyzing uploaded files.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "top_k": {"type": "integer", "minimum": 1, "maximum": 20, "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_list_events",
                "description": "List calendar events in a time range, including Blackboard and local events.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "string",
                            "description": "ISO datetime start of the range.",
                        },
                        "end": {"type": "string", "description": "ISO datetime end of the range."},
                        "include_blackboard": {"type": "boolean", "default": True},
                    },
                    "required": ["start", "end"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_create_event",
                "description": "Create a local calendar event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "start_at": {
                            "type": "string",
                            "description": "ISO datetime for event start.",
                        },
                        "end_at": {"type": "string", "description": "ISO datetime for event end."},
                        "description": {"type": "string"},
                        "location": {"type": "string"},
                        "all_day": {"type": "boolean", "default": False},
                        "timezone": {"type": "string", "default": "UTC"},
                        "status": {
                            "type": "string",
                            "enum": ["not_started", "pending", "completed"],
                            "default": "not_started",
                        },
                    },
                    "required": ["title", "start_at", "end_at"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_update_event",
                "description": "Update a local calendar event by event id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "title": {"type": "string"},
                        "start_at": {"type": "string"},
                        "end_at": {"type": "string"},
                        "description": {"type": "string"},
                        "location": {"type": "string"},
                        "all_day": {"type": "boolean"},
                        "timezone": {"type": "string"},
                        "status": {
                            "type": "string",
                            "enum": ["not_started", "pending", "completed"],
                        },
                    },
                    "required": ["event_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_move_event",
                "description": "Move a local calendar event to a new start and end time.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                        "start_at": {"type": "string"},
                        "end_at": {"type": "string"},
                    },
                    "required": ["event_id", "start_at", "end_at"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_delete_event",
                "description": "Delete a local calendar event by event id.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                    },
                    "required": ["event_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_sync_blackboard",
                "description": "Sync Blackboard calendar items into the unified calendar.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "calendar_clone_blackboard_event",
                "description": "Copy a read-only Blackboard calendar event into a local editable event.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "event_id": {"type": "string"},
                    },
                    "required": ["event_id"],
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
                        "question_count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 5,
                        },
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
                "name": "blackboard_get_all_courses",
                "description": "Fetch all Blackboard courses available to the current user.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "blackboard_get_course_announcements",
                "description": "Get announcements for a specific Blackboard course.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {
                            "type": "string",
                            "pattern": "^_\\d+_\\d+$",
                            "description": "The exact 'course_id' field returned by the blackboard_get_all_courses tool. Required format is usually '_XXX_1'.",
                        }
                    },
                    "required": ["course_id"],
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
        {
            "type": "function",
            "function": {
                "name": "blackboard_download_files",
                "description": "Find Blackboard files in a course or folder and return browser-download URLs. Use query for folders/topics such as lab9. Use course_id from blackboard_get_all_courses.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "course_id": {
                            "type": "string",
                            "description": "The course ID from blackboard_get_all_courses.",
                        },
                        "node_id": {
                            "type": "string",
                            "description": "Optional specific node/folder ID to download from that node only.",
                        },
                        "query": {
                            "type": "string",
                            "description": "Optional case-insensitive folder/file title filter, e.g. lab9 or assignment 3.",
                        },
                        "max_files": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 500,
                            "default": 100,
                            "description": "Maximum number of matching file links to return.",
                        },
                    },
                    "required": ["course_id"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "email_test_connection",
                "description": "Test whether the configured email SMTP server is reachable and credentials are valid.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "email_read_latest",
                "description": "Read the most recent emails from the configured IMAP inbox.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "count": {
                            "type": "integer",
                            "minimum": 1,
                            "maximum": 10,
                            "default": 1,
                            "description": "Number of latest emails to fetch.",
                        },
                    },
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
        self.calendar_service = CalendarService(session)
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
        if tool_name == "rag_index_folder":
            return (
                f"Index local folder `{arguments.get('path', '.')}` into the knowledge base "
                "using the configured RAG directory permissions."
            )
        if tool_name == "email_send":
            to = arguments.get("to", "")
            subject = arguments.get("subject", "")
            return f"Send email to {to}: {subject}"
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
        if tool_name == "rag_index_folder":
            return await self._rag_index_folder(arguments, workspace_root)
        if tool_name == "rag_search":
            return await self._rag_search(arguments, chat_session_id=chat_session_id)
        if tool_name == "rag_answer":
            return await self._rag_answer(arguments, chat_session_id=chat_session_id)
        if tool_name == "calendar_list_events":
            return await self._calendar_list_events(arguments)
        if tool_name == "calendar_create_event":
            return await self._calendar_create_event(arguments)
        if tool_name == "calendar_update_event":
            return await self._calendar_update_event(arguments)
        if tool_name == "calendar_move_event":
            return await self._calendar_move_event(arguments)
        if tool_name == "calendar_delete_event":
            return await self._calendar_delete_event(arguments)
        if tool_name == "calendar_sync_blackboard":
            return await self._calendar_sync_blackboard()
        if tool_name == "calendar_clone_blackboard_event":
            return await self._calendar_clone_blackboard_event(arguments)
        if tool_name == "create_quiz":
            return await self._create_quiz(arguments, chat_session_id=chat_session_id)
        if tool_name == "quiz_history_summary":
            return await self._quiz_history_summary(arguments)
        if tool_name == "get_current_datetime":
            return await self._get_current_datetime()
        if tool_name == "blackboard_get_all_courses":
            return await self._blackboard_get_all_courses()
        if tool_name == "blackboard_get_course_announcements":
            return await self._blackboard_get_course_announcements(arguments)
        if tool_name == "blackboard_test_api_available":
            return await self._blackboard_test_api_available()
        if tool_name == "blackboard_get_calendar_items":
            return await self._blackboard_get_calendar_items()
        if tool_name == "blackboard_download_files":
            return await self._blackboard_download_files(arguments)
        if tool_name == "email_test_connection":
            return await self._email_test_connection()
        if tool_name == "email_read_latest":
            return await self._email_read_latest(arguments)
        if tool_name == "email_send":
            return await self._email_send(arguments)
        raise ToolExecutionError(f"Unknown tool `{tool_name}`.")

    async def _memory_search(self, arguments: dict[str, Any]) -> str:
        query = str(arguments.get("query", "")).strip()
        limit = int(arguments.get("limit", 5))
        if not query:
            raise ToolExecutionError("`query` is required for memory_search.")

        # Optional memory_type filter (string -> MemoryType)
        from backend.models.memory import MemoryType

        raw_types = arguments.get("memory_types") or []
        memory_types: list[MemoryType] | None = None
        if raw_types:
            memory_types = []
            for t in raw_types:
                try:
                    memory_types.append(MemoryType(t))
                except ValueError:
                    continue
            memory_types = memory_types or None

        # Primary path: long-term memory semantic search (cross-session)
        ltm_results = await self.memory_service.search_long_term_memories(
            query=query,
            memory_types=memory_types,
            limit=limit,
            semantic_threshold=float(arguments.get("threshold", 0.5)),
            use_hybrid=True,
        )

        # Fallback path: legacy keyword memories (still useful for older entries)
        legacy_results = []
        if len(ltm_results) < limit:
            legacy_remaining = limit - len(ltm_results)
            legacy_results = await self.memory_service.get_relevant_memories(
                query, limit=legacy_remaining
            )

        if not ltm_results and not legacy_results:
            return "No matching memories were found."

        payload = {
            "long_term": [
                {
                    "id": m.id,
                    "memory_type": m.memory_type.value,
                    "content": m.content,
                    "importance_score": m.importance_score,
                    "access_count": m.access_count,
                    "metadata": m.metadata,
                }
                for m in ltm_results
            ],
            "legacy": [
                {
                    "id": m.id,
                    "key": m.key,
                    "category": m.category,
                    "tags": m.tags,
                    "value": m.value,
                }
                for m in legacy_results
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    async def _memory_save(self, arguments: dict[str, Any]) -> str:
        from backend.models.memory import MemoryType

        # Two save modes:
        #  - key/value (legacy compatibility) -> stored as both legacy memory and LTM
        #  - content/memory_type (new style) -> LTM only
        content = arguments.get("content")
        memory_type_raw = arguments.get("memory_type")
        key = str(arguments.get("key", "")).strip()

        if not content and not key:
            raise ToolExecutionError(
                "memory_save requires either `content` (+optional `memory_type`) "
                "or `key`+`value` for legacy mode."
            )

        # Resolve memory type
        if memory_type_raw:
            try:
                memory_type = MemoryType(memory_type_raw)
            except ValueError as exc:
                raise ToolExecutionError(
                    f"Invalid memory_type `{memory_type_raw}`. "
                    f"Valid: {[t.value for t in MemoryType]}"
                ) from exc
        else:
            # Map legacy category to a memory type
            category = str(arguments.get("category", "general")).lower()
            category_map = {
                "user_preference": MemoryType.USER_PREFERENCE,
                "preference": MemoryType.USER_PREFERENCE,
                "factual": MemoryType.FACTUAL,
                "fact": MemoryType.FACTUAL,
                "procedural": MemoryType.PROCEDURAL,
                "how_to": MemoryType.PROCEDURAL,
                "episodic": MemoryType.EPISODIC,
                "event": MemoryType.EPISODIC,
                "tool_usage": MemoryType.TOOL_USAGE,
            }
            memory_type = category_map.get(category, MemoryType.FACTUAL)

        # Build content from key/value if needed
        if not content:
            content = f"{key}: {arguments.get('value')}"

        importance = float(arguments.get("importance_score", 0.8))
        ltm = await self.memory_service.save_long_term_memory(
            content=str(content),
            memory_type=memory_type,
            metadata={
                "tags": [str(tag) for tag in arguments.get("tags", [])],
                "key": key or None,
                "source": "memory_save_tool",
            },
            importance_score=importance,
            generate_embedding=True,
        )
        return json.dumps(
            {
                "saved": True,
                "id": ltm.id,
                "memory_type": ltm.memory_type.value,
                "content": ltm.content,
            },
            ensure_ascii=False,
        )

    async def _memory_delete(self, arguments: dict[str, Any]) -> str:
        # Two delete modes:
        #  - id: precise deletion of one LTM record
        #  - query: keyword sweep across both LTM and legacy memories
        memory_id = str(arguments.get("id", "")).strip()
        if memory_id:
            ltm_deleted = await self.memory_service.delete_long_term_memory(memory_id)
            legacy_deleted = await self.memory_service.delete_memory(memory_id)
            return json.dumps(
                {"deleted": ltm_deleted or legacy_deleted, "id": memory_id},
                ensure_ascii=False,
            )

        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ToolExecutionError("memory_delete requires either `id` or `query`.")

        # Sweep LTM via semantic search, then legacy via keyword
        ltm_hits = await self.memory_service.search_long_term_memories(
            query=query, limit=20, semantic_threshold=0.6
        )
        ltm_deleted_count = 0
        for hit in ltm_hits:
            if await self.memory_service.delete_long_term_memory(hit.id):
                ltm_deleted_count += 1
        legacy_deleted_count = await self.memory_service.delete_memories_by_query(query)

        return json.dumps(
            {"long_term_deleted": ltm_deleted_count, "legacy_deleted": legacy_deleted_count},
            ensure_ascii=False,
        )

    async def _list_local_files(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        effective_root = self._effective_workspace_root_for_path(
            workspace_root,
            str(arguments.get("path", ".")),
            directory_request=True,
            allow_rag_roots=True,
        )
        base = self._resolve_path(effective_root, str(arguments.get("path", ".")))
        recursive = bool(arguments.get("recursive", False))
        max_entries = int(arguments.get("max_entries", 50))
        pattern = "**/*" if recursive else "*"
        entries: list[dict[str, Any]] = []
        for item in sorted(base.glob(pattern))[:max_entries]:
            if item == base:
                continue
            entries.append(
                {
                    "path": item.relative_to(self._workspace_root(effective_root)).as_posix(),
                    "type": "directory" if item.is_dir() else "file",
                }
            )
        return json.dumps({"directory": base.as_posix(), "entries": entries}, ensure_ascii=False)

    async def _read_local_file(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        effective_root = self._effective_workspace_root_for_path(
            workspace_root,
            str(arguments.get("path", "")),
            directory_request=False,
            allow_rag_roots=True,
        )
        path = self._resolve_path(effective_root, str(arguments.get("path", "")))
        max_chars = int(arguments.get("max_chars", 12000))
        if not path.is_file():
            raise ToolExecutionError(f"`{path}` is not a readable file.")
        content = path.read_text(encoding="utf-8", errors="ignore")
        truncated = len(content) > max_chars
        payload = {
            "path": path.relative_to(self._workspace_root(effective_root)).as_posix(),
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

    async def _run_local_command(
        self, arguments: dict[str, Any], workspace_root: str | None
    ) -> str:
        cwd = self._workspace_root(workspace_root)
        command = self._normalize_command(arguments.get("command"), cwd)
        timeout_seconds = int(arguments.get("timeout_seconds", 20))

        # Check if we need to use shell (for built-in commands like cd)
        shell_builtins = {
            "cd",
            "pwd",
            "echo",
            "export",
            "source",
            "alias",
            "history",
            "fg",
            "bg",
            "jobs",
            "kill",
            "exit",
        }
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
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise ToolExecutionError(f"Command timed out after {timeout_seconds} seconds.") from exc

        payload = {
            "command": command,
            "cwd": str(cwd),
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8", errors="ignore")[:12000],
            "stderr": stderr.decode("utf-8", errors="ignore")[:12000],
        }
        return json.dumps(payload, ensure_ascii=False)

    def _normalize_command(self, raw_command: Any, cwd: Path) -> list[str]:
        if isinstance(raw_command, str):
            command = shlex.split(raw_command)
        elif (
            isinstance(raw_command, list)
            and raw_command
            and all(isinstance(item, str) for item in raw_command)
        ):
            command = list(raw_command)
        else:
            raise ToolExecutionError("`command` must be a non-empty string or string array.")

        first = command[0]
        candidate = cwd / first
        if candidate.is_file():
            if candidate.suffix == ".py":
                return [sys.executable, first, *command[1:]]
            if candidate.suffix == ".sh" and not candidate.stat().st_mode & 0o111:
                return ["bash", first, *command[1:]]
        return command

    async def _fetch_webpage(self, arguments: dict[str, Any]) -> str:
        url = str(arguments.get("url", "")).strip()
        max_chars = int(arguments.get("max_chars", 12000))
        if not url.startswith(("http://", "https://")):
            raise ToolExecutionError("`url` must start with http:// or https://")
        async with httpx.AsyncClient(
            timeout=20.0, follow_redirects=True, trust_env=False
        ) as client:
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

    async def _rag_index_folder(self, arguments: dict[str, Any], workspace_root: str | None) -> str:
        path = str(arguments.get("path", ".")).strip() or "."
        service = RAGService(self.session)
        try:
            effective_root, safe_path = service.resolve_index_scope(path=path)
            directory_settings = service.get_directory_settings()
            result = await service.index_folder(
                safe_path,
                workspace_root=effective_root,
                recursive=(
                    bool(arguments["recursive"])
                    if "recursive" in arguments
                    else directory_settings.recursive_default
                ),
                extensions=arguments.get("extensions"),
            )
        except (RAGProviderError, RAGServiceError) as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _rag_search(self, arguments: dict[str, Any], *, chat_session_id: str) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ToolExecutionError("`query` is required for rag_search.")
        owner_ids = ChatFileService(self.session).query_owner_ids(chat_session_id)
        rag_service = RAGService(self.session)
        hits = rag_service.sample_chunks(
            owner_id=owner_ids[0],
            limit=CHAT_FILE_CONTEXT_CHUNK_LIMIT,
        )
        if not hits:
            hits = rag_service.search(
                query,
                top_k=int(arguments.get("top_k", 5)),
                owner_ids=owner_ids,
            )
        if not hits:
            return "No matching uploaded file or knowledge base chunks were found."
        return json.dumps([hit.model_dump(mode="json") for hit in hits], ensure_ascii=False)

    async def _rag_answer(self, arguments: dict[str, Any], *, chat_session_id: str) -> str:
        query = str(arguments.get("query", "")).strip()
        if not query:
            raise ToolExecutionError("`query` is required for rag_answer.")
        try:
            owner_ids = ChatFileService(self.session).query_owner_ids(chat_session_id)
            result = await RAGService(self.session).query(
                query,
                top_k=int(arguments.get("top_k", 5)),
                owner_ids=owner_ids,
                prefer_owner_context=True,
                context_limit=CHAT_FILE_CONTEXT_CHUNK_LIMIT,
            )
        except (RAGProviderError, RAGServiceError) as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

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

    async def _calendar_list_events(self, arguments: dict[str, Any]) -> str:
        start = self._require_iso_datetime(arguments.get("start"), field_name="start")
        end = self._require_iso_datetime(arguments.get("end"), field_name="end")
        events = await self.calendar_service.list_events(
            start=start,
            end=end,
            include_blackboard=bool(arguments.get("include_blackboard", True)),
        )
        return json.dumps(events.model_dump(mode="json"), ensure_ascii=False)

    async def _calendar_create_event(self, arguments: dict[str, Any]) -> str:
        title = str(arguments.get("title", "")).strip()
        if not title:
            raise ToolExecutionError("`title` is required for calendar_create_event.")
        event = await self.calendar_service.create_event(
            CalendarEventCreate(
                title=title,
                start_at=self._require_iso_datetime(
                    arguments.get("start_at"), field_name="start_at"
                ),
                end_at=self._require_iso_datetime(arguments.get("end_at"), field_name="end_at"),
                description=self._optional_string(arguments.get("description")),
                location=self._optional_string(arguments.get("location")),
                all_day=bool(arguments.get("all_day", False)),
                timezone=str(arguments.get("timezone", "UTC")),
                status=self._normalize_status(arguments.get("status", "not_started")),
            )
        )
        return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)

    async def _calendar_update_event(self, arguments: dict[str, Any]) -> str:
        event_id = str(arguments.get("event_id", "")).strip()
        if not event_id:
            raise ToolExecutionError("`event_id` is required for calendar_update_event.")
        try:
            event = await self.calendar_service.update_event(
                event_id,
                CalendarEventUpdate(
                    title=self._optional_string(arguments.get("title")),
                    start_at=self._optional_iso_datetime(arguments.get("start_at")),
                    end_at=self._optional_iso_datetime(arguments.get("end_at")),
                    description=self._optional_string(arguments.get("description")),
                    location=self._optional_string(arguments.get("location")),
                    all_day=arguments.get("all_day"),
                    timezone=self._optional_string(arguments.get("timezone")),
                    status=self._normalize_optional_status(arguments.get("status")),
                ),
            )
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)

    async def _calendar_move_event(self, arguments: dict[str, Any]) -> str:
        event_id = str(arguments.get("event_id", "")).strip()
        if not event_id:
            raise ToolExecutionError("`event_id` is required for calendar_move_event.")
        try:
            event = await self.calendar_service.move_event(
                event_id,
                CalendarEventMove(
                    start_at=self._require_iso_datetime(
                        arguments.get("start_at"), field_name="start_at"
                    ),
                    end_at=self._require_iso_datetime(arguments.get("end_at"), field_name="end_at"),
                ),
            )
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)

    async def _calendar_delete_event(self, arguments: dict[str, Any]) -> str:
        event_id = str(arguments.get("event_id", "")).strip()
        if not event_id:
            raise ToolExecutionError("`event_id` is required for calendar_delete_event.")
        try:
            deleted = await self.calendar_service.delete_event(event_id)
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps({"deleted": deleted, "event_id": event_id}, ensure_ascii=False)

    async def _calendar_sync_blackboard(self) -> str:
        result = await self.calendar_service.sync_blackboard()
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _calendar_clone_blackboard_event(self, arguments: dict[str, Any]) -> str:
        event_id = str(arguments.get("event_id", "")).strip()
        if not event_id:
            raise ToolExecutionError("`event_id` is required for calendar_clone_blackboard_event.")
        try:
            event = await self.calendar_service.clone_blackboard_event(event_id)
        except ValueError as exc:
            raise ToolExecutionError(str(exc)) from exc
        return json.dumps(event.model_dump(mode="json"), ensure_ascii=False)

    async def _get_current_datetime(self) -> str:
        datetime_info = DateTimeService().get_current_datetime()
        return json.dumps(datetime_info.model_dump(mode="json"), ensure_ascii=False)

    async def _blackboard_get_all_courses(self) -> str:
        provider = await self._authenticated_blackboard_provider()
        service = BlackboardService(self.session, provider)
        result = await service.get_all_courses()
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _blackboard_get_course_announcements(self, arguments: dict[str, Any]) -> str:
        course_id = str(arguments.get("course_id", "")).strip()
        if not course_id:
            raise ToolExecutionError("`course_id` is required.")
        provider = await self._authenticated_blackboard_provider()
        service = BlackboardService(self.session, provider)
        result = await service.get_announcements(course_id)
        return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)

    async def _blackboard_test_api_available(self) -> str:
        import logging

        logger = logging.getLogger(__name__)

        await self._ensure_blackboard_runtime_from_profile()
        bb_config = runtime_settings.get_blackboard_config()
        password = runtime_settings.get_secret_blackboard_password()

        logger.info(
            f"BB config: student_id={bb_config.student_id}, base_url={bb_config.base_url}, password={'set' if password else 'None'}"
        )

        provider = DemoBlackboardProvider(
            student_id=bb_config.student_id, password=password, base_url=bb_config.base_url
        )
        authenticated = await provider.bypass_cas_login()
        api_available = await provider.test_api_available() if authenticated else False
        logger.info(
            "BB test_api_available result: authenticated=%s, api_available=%s",
            authenticated,
            api_available,
        )
        return json.dumps(
            {
                "available": authenticated,
                "authenticated": authenticated,
                "api_available": api_available,
                "message": (
                    "Blackboard CAS 登录成功。"
                    if authenticated
                    else "Blackboard CAS 登录失败，请检查学号和 CAS 密码。"
                ),
            },
            ensure_ascii=False,
        )

    async def _blackboard_get_calendar_items(self) -> str:
        bb_config = runtime_settings.get_blackboard_config()
        password = runtime_settings.get_secret_blackboard_password()
        provider = DemoBlackboardProvider(
            student_id=bb_config.student_id, password=password, base_url=bb_config.base_url
        )
        items = await provider.get_calendar_items()
        return json.dumps({"items": items}, ensure_ascii=False)

    async def _blackboard_download_files(self, arguments: dict[str, Any]) -> str:
        course_id = str(arguments.get("course_id", "")).strip()
        if not course_id:
            raise ToolExecutionError("`course_id` is required for blackboard_download_files.")

        node_id = self._optional_string(arguments.get("node_id"))
        query = self._optional_string(arguments.get("query"))
        try:
            max_files = int(arguments.get("max_files") or 100)
        except (TypeError, ValueError) as exc:
            raise ToolExecutionError("`max_files` must be an integer between 1 and 500.") from exc
        max_files = max(1, min(max_files, 500))

        provider = await self._authenticated_blackboard_provider()

        from backend.services.blackboard_file_service import BBFileManager

        if provider._cas_session is None:
            raise ToolExecutionError("Blackboard 未登录，请在设置中配置账号密码。")
        cookies = provider._cas_session.cookies.get_dict()
        manager = BBFileManager(cookies, download_root="./BB_Files")

        try:
            node = await self._build_blackboard_node(manager, course_id=course_id, node_id=node_id)
            await self._load_blackboard_tree(manager, node)
            files = self._collect_files_from_node(
                node,
                course_id,
                query=self._normalize_blackboard_text(query) if query else None,
            )
            total_found = len(files)
            files = files[:max_files]

            if not files:
                return json.dumps(
                    {
                        "message": "没有找到匹配的可下载文件",
                        "course_id": course_id,
                        "node_id": node_id,
                        "query": query,
                        "files_found": 0,
                        "files_returned": 0,
                        "files": [],
                    },
                    ensure_ascii=False,
                )

            download_urls = []
            for file_info in files:
                relative_url = (
                    f"/blackboard/files/download?course_id={quote(course_id, safe='')}"
                    f"&content_id={quote(file_info['content_id'], safe='')}"
                    f"&attachment_id={quote(file_info['id'], safe='')}"
                    f"&file_name={quote(file_info['file_name'], safe='')}"
                )
                api_url = f"/api{relative_url}"
                download_urls.append(
                    {
                        "file_name": file_info["file_name"],
                        "path": file_info["path"],
                        "content_id": file_info["content_id"],
                        "attachment_id": file_info["id"],
                        "download_url": api_url,
                        "browser_download_url": f"http://127.0.0.1:8000{api_url}",
                    }
                )

            return json.dumps(
                {
                    "message": (
                        f"找到 {total_found} 个匹配文件，返回 {len(download_urls)} 个浏览器下载链接。"
                        "打开 browser_download_url 会使用浏览器默认下载路径。"
                    ),
                    "course_id": course_id,
                    "node_id": node_id,
                    "query": query,
                    "files_found": total_found,
                    "files_returned": len(download_urls),
                    "truncated": total_found > len(download_urls),
                    "files": download_urls,
                },
                ensure_ascii=False,
            )
        finally:
            await manager.close()

    async def _authenticated_blackboard_provider(self) -> DemoBlackboardProvider:
        await self._ensure_blackboard_runtime_from_profile()
        bb_config = runtime_settings.get_blackboard_config()
        password = runtime_settings.get_secret_blackboard_password()
        provider = DemoBlackboardProvider(
            student_id=bb_config.student_id,
            password=password,
            base_url=bb_config.base_url,
        )
        logged_in = await provider.bypass_cas_login()
        if not logged_in or provider._cas_session is None:
            raise ToolExecutionError("Blackboard 未登录，请在设置中配置账号密码。")
        return provider

    async def _ensure_blackboard_runtime_from_profile(self) -> None:
        bb_config = runtime_settings.get_blackboard_config()
        if bb_config.student_id:
            return

        profiles = await SettingsService(self.session).list_bb_profiles()
        if profiles:
            await SettingsService(self.session).apply_bb_profile(profiles[0].name)

    async def _build_blackboard_node(self, manager, *, course_id: str, node_id: str | None):
        from backend.services.blackboard_file_service import BBContent

        if not node_id:
            return BBContent(
                id=course_id,
                title=f"Course {course_id}",
                type="x-bb-course",
                course_id=course_id,
                has_children=True,
            )

        node_title = "Target Node"
        node_type = "x-bb-folder"
        has_children = True
        try:
            metadata = await manager._get_json(
                f"{manager.BASE_URL}/courses/{course_id}/contents/{node_id}"
            )
            node_title = str(metadata.get("title") or node_title)
            handler = str(metadata.get("contentHandler", {}).get("id", "") or "")
            node_type = handler.rsplit("/", 1)[-1] if handler else node_type
            has_children = bool(metadata.get("hasChildren", has_children))
        except Exception as exc:
            print(f"[BB][agent_tool] failed to resolve node metadata for {node_id}: {exc}")

        return BBContent(
            id=node_id,
            title=node_title,
            type=node_type,
            course_id=course_id,
            has_children=has_children,
        )

    async def _load_blackboard_tree(
        self, manager, node, *, depth: int = 0, max_depth: int = 12
    ) -> None:
        await manager.fetch_node_children(node)
        if depth >= max_depth or not node.children:
            return
        await asyncio.gather(
            *(
                self._load_blackboard_tree(manager, child, depth=depth + 1, max_depth=max_depth)
                for child in node.children
            )
        )

    @staticmethod
    def _normalize_blackboard_text(value: str | None) -> str:
        text = re.sub(r"[\s_\-]+", "", str(value or "").casefold())
        return re.sub(r"\d+", lambda match: str(int(match.group(0))), text)

    def _collect_files_from_node(
        self,
        node,
        course_id: str,
        *,
        query: str | None = None,
        ancestor_matched: bool = False,
        path: list[str] | None = None,
    ) -> list:
        files = []
        current_path = [*(path or []), str(getattr(node, "title", "") or node.id)]
        path_text = " / ".join(current_path)
        node_matched = (
            ancestor_matched or query is None or query in self._normalize_blackboard_text(path_text)
        )

        for attachment in node.attachments:
            file_path = [*current_path, attachment.file_name]
            file_path_text = " / ".join(file_path)
            if node_matched or (query and query in self._normalize_blackboard_text(file_path_text)):
                files.append(
                    {
                        "id": attachment.id,
                        "file_name": attachment.file_name,
                        "download_url": attachment.download_url,
                        "content_id": node.id,
                        "course_id": course_id,
                        "path": file_path_text,
                    }
                )

        for child in node.children:
            files.extend(
                self._collect_files_from_node(
                    child,
                    course_id,
                    query=query,
                    ancestor_matched=node_matched,
                    path=current_path,
                )
            )
        return files

    async def _email_test_connection(self) -> str:
        import smtplib
        from email.mime.text import MIMEText
        from email.utils import formatdate

        from backend.services.runtime_settings import runtime_settings

        config = runtime_settings.get_email_config()
        password = runtime_settings.get_secret_email_password()

        if not config.smtp_user or not password:
            return json.dumps(
                {
                    "ok": False,
                    "error": "Email not configured. Please set SMTP credentials in Settings > Email.",
                },
                ensure_ascii=False,
            )

        msg = MIMEText("This is a test email from Student Productivity Agent.", "plain", "utf-8")
        msg["From"] = config.smtp_user
        msg["To"] = config.smtp_user
        msg["Subject"] = "[Agent Test] Email Configuration Check"
        msg["Date"] = formatdate(localtime=True)

        try:
            if config.smtp_encryption == "ssl":
                server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
                if config.smtp_encryption == "tls":
                    server.starttls()
            server.login(config.smtp_user, password)
            server.sendmail(config.smtp_user, [config.smtp_user], msg.as_string())
            server.quit()
            return json.dumps(
                {"ok": True, "message": "SMTP connection and authentication successful"},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"Email test failed: {e}"},
                ensure_ascii=False,
            )

    async def _email_read_latest(self, arguments: dict[str, Any]) -> str:
        import email
        import imaplib
        from email.header import decode_header

        from backend.services.runtime_settings import runtime_settings

        config = runtime_settings.get_email_config()
        password = runtime_settings.get_secret_email_password()

        if not config.smtp_user or not password:
            return json.dumps(
                {
                    "ok": False,
                    "error": "Email not configured. Please set SMTP/IMAP credentials in Settings > Email.",
                },
                ensure_ascii=False,
            )

        count = min(int(arguments.get("count", 5)), 20)

        def _decode_header(value: str) -> str:
            parts = decode_header(value)
            decoded = ""
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded += part.decode(charset or "utf-8", errors="ignore")
                else:
                    decoded += part
            return decoded

        def _get_body(msg: email.message.Message) -> str:
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    content_type = part.get_content_type()
                    if content_type == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            return payload.decode(charset, errors="ignore")
                    elif content_type == "text/html" and not body:
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            body = payload.decode(charset, errors="ignore")
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="ignore")
            return body[:2000]

        try:
            server = imaplib.IMAP4_SSL(config.imap_host, config.imap_port, timeout=15)
            server.login(config.smtp_user, password)
            server.select("INBOX")

            status, data = server.search(None, "ALL")
            if status != "OK" or not data[0]:
                server.logout()
                return json.dumps(
                    {"ok": True, "emails": [], "message": "Inbox is empty."}, ensure_ascii=False
                )

            all_ids = data[0].split()
            latest_ids = all_ids[-count:] if len(all_ids) >= count else all_ids

            emails = []
            for mid in reversed(latest_ids):
                status, msg_data = server.fetch(mid, "(RFC822)")
                if status != "OK":
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
                emails.append(
                    {
                        "subject": _decode_header(msg["Subject"] or "(no subject)"),
                        "from": _decode_header(msg["From"] or ""),
                        "to": _decode_header(msg["To"] or ""),
                        "date": msg["Date"] or "",
                        "body": _get_body(msg),
                    }
                )

            server.logout()
            return json.dumps({"ok": True, "emails": emails}, ensure_ascii=False)
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"IMAP read failed: {e}"},
                ensure_ascii=False,
            )

    async def _email_send(self, arguments: dict[str, Any]) -> str:
        import smtplib
        from email.mime.text import MIMEText

        from backend.services.runtime_settings import runtime_settings

        config = runtime_settings.get_email_config()
        password = runtime_settings.get_secret_email_password()

        to = arguments["to"]
        subject = arguments["subject"]
        body = arguments["body"]

        if not config.smtp_user or not password:
            return json.dumps(
                {
                    "ok": False,
                    "error": "SMTP not configured. Please set credentials in Settings > Email.",
                },
                ensure_ascii=False,
            )

        msg = MIMEText(body, "plain", "utf-8")
        msg["From"] = config.smtp_user
        msg["To"] = to
        msg["Subject"] = subject

        def _send() -> None:
            if config.smtp_encryption == "ssl":
                server = smtplib.SMTP_SSL(config.smtp_host, config.smtp_port, timeout=15)
            else:
                server = smtplib.SMTP(config.smtp_host, config.smtp_port, timeout=15)
                if config.smtp_encryption == "tls":
                    server.starttls()
            server.login(config.smtp_user, password)
            server.sendmail(config.smtp_user, [to], msg.as_string())
            server.quit()

        try:
            await asyncio.to_thread(_send)
            return json.dumps(
                {"ok": True, "message": f"Email sent to {to}."},
                ensure_ascii=False,
            )
        except Exception as e:
            return json.dumps(
                {"ok": False, "error": f"Send failed: {e}"},
                ensure_ascii=False,
            )

    def _workspace_root(self, workspace_root: str | None) -> Path:
        root = Path(workspace_root or "").expanduser()
        if not workspace_root:
            raise ToolExecutionError(
                "No workspace root is configured. Ask the user to set one first."
            )
        try:
            resolved = root.resolve(strict=True)
        except FileNotFoundError as exc:
            raise ToolExecutionError(f"Workspace root `{workspace_root}` does not exist.") from exc
        if not resolved.is_dir():
            raise ToolExecutionError(f"Workspace root `{workspace_root}` is not a directory.")
        return resolved

    def _effective_workspace_root_for_path(
        self,
        workspace_root: str | None,
        requested_path: str,
        *,
        directory_request: bool,
        allow_rag_roots: bool = False,
    ) -> str | None:
        if workspace_root:
            return workspace_root
        requested = Path(requested_path).expanduser()
        if not requested.is_absolute():
            # For read operations, try RAG authorized roots as fallback
            if allow_rag_roots:
                rag_root = self._find_rag_root_for_relative_path(requested_path)
                if rag_root:
                    return rag_root
            return workspace_root
        resolved = requested.resolve()
        # For read operations, check if path is inside an authorized RAG root
        if allow_rag_roots:
            rag_root = self._find_rag_root_containing(resolved)
            if rag_root:
                return rag_root
        if directory_request:
            if not resolved.is_dir():
                raise ToolExecutionError(f"`{requested_path}` is not a directory.")
            return str(resolved)
        parent = resolved.parent
        if not parent.is_dir():
            raise ToolExecutionError(f"Parent directory for `{requested_path}` does not exist.")
        return str(parent)

    def _find_rag_root_containing(self, resolved_path: Path) -> str | None:
        """Return a RAG authorized root containing `resolved_path`, or None."""
        try:
            from backend.services.rag_service import RAGService

            directory_settings = RAGService(self.session).get_directory_settings()
        except Exception:
            return None
        for root_str in directory_settings.allowed_roots or []:
            try:
                root = Path(root_str).expanduser().resolve()
            except Exception:
                continue
            try:
                resolved_path.relative_to(root)
                return str(root)
            except ValueError:
                continue
        return None

    def _find_rag_root_for_relative_path(self, requested_path: str) -> str | None:
        """For a relative path, return the default RAG root if the path exists under it."""
        try:
            from backend.services.rag_service import RAGService

            directory_settings = RAGService(self.session).get_directory_settings()
        except Exception:
            return None
        candidate_roots: list[str] = []
        if directory_settings.default_root:
            candidate_roots.append(directory_settings.default_root)
        candidate_roots.extend(directory_settings.allowed_roots or [])
        for root_str in candidate_roots:
            try:
                root = Path(root_str).expanduser().resolve()
                candidate = (root / requested_path).resolve()
                candidate.relative_to(root)
                if candidate.exists():
                    return str(root)
            except Exception:
                continue
        return None

    def _resolve_path(self, workspace_root: str | None, requested_path: str) -> Path:
        root = self._workspace_root(workspace_root)
        candidate = (
            (root / requested_path).resolve()
            if not Path(requested_path).is_absolute()
            else Path(requested_path).resolve()
        )
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise ToolExecutionError(
                "Requested path escapes the configured workspace root."
            ) from exc
        return candidate

    def _optional_string(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _require_iso_datetime(self, value: Any, *, field_name: str) -> datetime:
        if not isinstance(value, str) or not value.strip():
            raise ToolExecutionError(f"`{field_name}` must be a non-empty ISO datetime string.")
        return self._parse_iso_datetime(value, field_name=field_name)

    def _optional_iso_datetime(self, value: Any) -> datetime | None:
        if value is None:
            return None
        if not isinstance(value, str) or not value.strip():
            raise ToolExecutionError(
                "Optional datetime fields must be ISO datetime strings when provided."
            )
        return self._parse_iso_datetime(value, field_name="datetime")

    def _parse_iso_datetime(self, value: str, *, field_name: str) -> datetime:
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ToolExecutionError(
                f"`{field_name}` must be a valid ISO datetime string."
            ) from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)

    def _normalize_status(self, value: Any) -> str:
        if value is None:
            return "not_started"
        normalized = str(value).strip().lower()
        aliases = {
            "not_started": "not_started",
            "not-started": "not_started",
            "pending": "pending",
            "completed": "completed",
            "complete": "completed",
            "done": "completed",
        }
        if normalized not in aliases:
            raise ToolExecutionError("`status` must be one of: not_started, pending, completed.")
        return aliases[normalized]

    def _normalize_optional_status(self, value: Any) -> str | None:
        if value is None:
            return None
        return self._normalize_status(value)
