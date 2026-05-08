"""PydanticAI-backed runtime that preserves the existing API contract."""

from __future__ import annotations

import asyncio
import inspect
import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Annotated, Any

from httpx import AsyncClient
from pydantic import Field
from pydantic_ai import Agent, DeferredToolResults, RunContext
from pydantic_ai.messages import (
    ModelRequest,
    ModelResponse,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
    UserPromptPart,
)
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.tools import DeferredToolRequests, ToolApproved, ToolDenied
from sqlalchemy.orm import Session

from backend.models.tooling import ToolTrace
from backend.services.agent_tool_service import AgentToolService
from backend.services.runtime_settings import runtime_settings
from backend.services.tool_learning_service import ToolLearningService, get_static_examples

SYSTEM_PROMPT = """
You are Student Productivity Agent, a study assistant for SUSTech students.
You have access to real backend tools. Treat local file access, local command execution,
web access, and memory operations as available capabilities provided by tools.

Tool usage rules:
1. When the user asks to read files, list directories, write files, run commands, or visit webpages,
   prefer the matching tool instead of replying that you cannot access the local machine or the web.
2. For file tools and command tools, stay within the configured workspace root.
3. For local file access, local command execution, and webpage access, the backend may require user approval.
   Reading files and listing directories no longer require approval, but writing, executing commands, and webpage fetches still do.
   You should still initiate the tool call when it is needed; the system will handle approval where applicable.
4. Do not say that you are blocked by sandbox or security restrictions unless a tool result explicitly says so.
5. Only claim an action succeeded after you receive a tool result confirming it.
6. Use memory tools to save durable user preferences, project facts, and useful follow-up context when appropriate.
7. If a tool result reports an error, explain that error plainly and suggest the next step.
8. Do NOT guess or hallucinate timestamps or dates. If the user does not explicitly mention a specific time, do not include unverified times when saving memories.
9. When saving memories, only record what actually happened in this conversation.
   Do not infer or assume actions that were not explicitly performed or confirmed by a tool result.
10. After successfully creating a quiz, do NOT present questions in chat.
    Instead, inform the user that the quiz is ready and direct them to the quiz
    interface to begin.
11. Use calendar tools for scheduling requests, event lookup, reminders, or timetable management.
12. Blackboard calendar events are read-only. If the user wants to modify one, first copy it into a local event.
13. When the user asks about indexed study materials, course notes, school information, PDFs,
    slides, documents, or the local knowledge base, prefer rag_search or rag_answer before
    answering from general knowledge. If the knowledge base has no relevant hit, say that plainly.
14. RAG indexing is limited to directories configured in the Knowledge Base page. Use
    rag_index_folder with a relative path under the default RAG directory whenever possible.
    Do not ask to index arbitrary computer paths outside the configured RAG roots.

Response style:
- Be concise and practical.
- Respond in Markdown when useful.
- Do not invent file contents, command output, or webpage content.
""".strip()


async def build_tool_examples_prompt(session: Session, user_query: str) -> str:
    """
    Build dynamic tool examples based on learned patterns and static examples.

    Args:
        session: Database session
        user_query: Current user query

    Returns:
        Formatted tool examples string
    """
    tool_learning = ToolLearningService(session)

    # Identify potentially relevant tools based on query keywords
    query_lower = user_query.lower()
    relevant_tools = []

    if any(word in query_lower for word in ["remember", "recall", "discussed", "said"]):
        relevant_tools.append("memory_search")
    if any(word in query_lower for word in ["save", "remember", "store", "keep"]):
        relevant_tools.append("memory_save")
    if any(word in query_lower for word in ["schedule", "calendar", "event", "meeting"]):
        relevant_tools.append("calendar_list_events")
    if any(word in query_lower for word in ["course", "material", "notes", "lecture"]):
        relevant_tools.append("rag_search")
    if any(word in query_lower for word in ["file", "code", "read", "show"]):
        relevant_tools.append("read_local_file")
    if any(word in query_lower for word in ["class", "courses"]):
        relevant_tools.append("blackboard_get_all_courses")

    if not relevant_tools:
        return ""

    # Build examples prompt
    examples_parts = ["\n\nTool Usage Examples:"]

    for tool_name in relevant_tools[:5]:  # Limit tools considered to keep prompt focused
        section: list[str] = []

        # 1) Static examples (curated, always sensible)
        static_examples = get_static_examples(tool_name)
        for ex in static_examples[:3]:
            section.append(
                f"  - When: {ex['scenario']}\n"
                f"    Example: \"{ex['example_query']}\"\n"
                f"    Result: {ex['expected_outcome']}"
            )

        # 2) Learned patterns (real successful past usage)
        try:
            learned = await tool_learning.get_tool_examples(
                tool_name, limit=2, min_confidence=0.6
            )
        except Exception:
            learned = []
        for pat in learned:
            section.append(
                f"  - Learned (used {pat['usage_count']}x, confidence {pat['confidence']:.2f}):\n"
                f"    Query: \"{pat['user_query']}\"\n"
                f"    Args: {pat['tool_arguments']}"
            )

        if section:
            examples_parts.append(f"\n{tool_name}:")
            examples_parts.extend(section)

    return "\n".join(examples_parts) if len(examples_parts) > 1 else ""


@dataclass
class AgentDeps:
    """Per-run dependencies and mutable execution state."""

    session: Session
    session_id: str
    workspace_root: str | None
    tool_service: AgentToolService
    tool_events: list[ToolTrace] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None = None


class PydanticAIRuntime:
    """Bridge current app protocols onto PydanticAI."""

    def __init__(self, session: Session):
        self.session = session
        self.tool_service = AgentToolService(session)

    def _build_model(self) -> OpenAIModel:
        config = runtime_settings.get_llm_config()
        api_key = runtime_settings.get_secret_api_key()
        if config.provider.strip().lower() != "openai":
            raise ValueError("Only OpenAI-compatible providers are supported right now.")
        if not api_key:
            raise ValueError("No API key is configured. Open the LLM settings panel first.")

        provider = OpenAIProvider(
            base_url=config.base_url or None,
            api_key=api_key,
            http_client=AsyncClient(trust_env=False),
        )
        if config.enable_reasoning:
            from pydantic_ai.profiles.openai import OpenAIModelProfile

            profile = OpenAIModelProfile(openai_chat_thinking_field="reasoning_content")
            return OpenAIModel(config.model, provider=provider, profile=profile)
        return OpenAIModel(config.model, provider=provider)

    def _build_agent(self, system_prompt: str = SYSTEM_PROMPT) -> Agent[AgentDeps, str | DeferredToolRequests]:
        agent = Agent[AgentDeps, str | DeferredToolRequests](
            model=self._build_model(),
            deps_type=AgentDeps,
            output_type=str | DeferredToolRequests,
            system_prompt=system_prompt,
            retries=1,
            defer_model_check=True,
        )

        @agent.system_prompt(dynamic=True)
        def workspace_instruction(ctx: RunContext[AgentDeps]) -> str:
            if ctx.deps.workspace_root:
                return (
                    f"Approved workspace root: `{ctx.deps.workspace_root}`. "
                    "Local file and command tools must stay inside this root."
                )
            return (
                "No workspace root is configured yet. "
                "Do not use local file or command tools until the user sets one."
            )

        async def _notify_tool_events(ctx: RunContext[AgentDeps]) -> None:
            callback = ctx.deps.on_tool_events
            if callback is None:
                return
            snapshot = [event.model_copy(deep=True) for event in ctx.deps.tool_events]
            maybe_awaitable = callback(snapshot)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable

        async def _execute_tool(
            ctx: RunContext[AgentDeps],
            tool_name: str,
            arguments: dict[str, Any],
        ) -> str:
            running_event = ToolTrace(tool_name=tool_name, arguments=arguments, status="running")
            ctx.deps.tool_events.append(running_event)
            await _notify_tool_events(ctx)
            # Let the event loop flush the "running" SSE event before tool execution starts.
            await asyncio.sleep(0)
            try:
                output = await ctx.deps.tool_service.execute(
                    tool_name,
                    arguments,
                    chat_session_id=ctx.deps.session_id,
                    workspace_root=ctx.deps.workspace_root,
                )
            except Exception as exc:
                running_event.status = "failed"
                running_event.output = json.dumps(
                    {"ok": False, "error": str(exc)},
                    ensure_ascii=False,
                )
                await _notify_tool_events(ctx)
                raise

            running_event.status = "failed" if '"ok": false' in output.lower() else "completed"
            running_event.output = output
            ctx.deps.tools_used.append(tool_name)
            await _notify_tool_events(ctx)
            return output

        @agent.tool(name="memory_search")
        async def memory_search(
            ctx: RunContext[AgentDeps],
            query: str,
            limit: int = 5,
            memory_types: list[str] | None = None,
        ) -> str:
            """Semantic search across long-term memories (cross-session) and legacy memories.

            memory_types can optionally filter to one or more of:
            'user_preference', 'factual', 'procedural', 'episodic', 'tool_usage'.
            """
            return await _execute_tool(
                ctx,
                "memory_search",
                {"query": query, "limit": limit, "memory_types": memory_types or []},
            )

        @agent.tool(name="memory_save")
        async def memory_save(
            ctx: RunContext[AgentDeps],
            content: str | None = None,
            memory_type: str | None = None,
            key: str | None = None,
            value: Any = None,
            category: str = "general",
            tags: list[str] | None = None,
            importance_score: float = 0.8,
        ) -> str:
            """Save a durable memory.

            Preferred: pass content + memory_type ('user_preference'/'factual'/'procedural'/'episodic').
            Legacy: pass key + value (will be stored as a factual memory unless category maps to a type).
            """
            args: dict[str, Any] = {
                "content": content,
                "memory_type": memory_type,
                "key": key,
                "value": value,
                "category": category,
                "tags": tags or [],
                "importance_score": importance_score,
            }
            return await _execute_tool(ctx, "memory_save", args)

        @agent.tool(name="memory_delete")
        async def memory_delete(
            ctx: RunContext[AgentDeps],
            query: str | None = None,
            id: str | None = None,
        ) -> str:
            """Delete memories. Use `id` for precise deletion or `query` for keyword sweep."""
            return await _execute_tool(
                ctx, "memory_delete", {"query": query or "", "id": id or ""}
            )

        @agent.tool(name="calendar_list_events")
        async def calendar_list_events(
            ctx: RunContext[AgentDeps],
            start: str,
            end: str,
            include_blackboard: bool = True,
        ) -> str:
            return await _execute_tool(
                ctx,
                "calendar_list_events",
                {"start": start, "end": end, "include_blackboard": include_blackboard},
            )

        @agent.tool(name="calendar_create_event")
        async def calendar_create_event(
            ctx: RunContext[AgentDeps],
            title: str,
            start_at: str,
            end_at: str,
            description: str | None = None,
            location: str | None = None,
            all_day: bool = False,
            timezone: str = "UTC",
            status: str = "not_started",
        ) -> str:
            return await _execute_tool(
                ctx,
                "calendar_create_event",
                {
                    "title": title,
                    "start_at": start_at,
                    "end_at": end_at,
                    "description": description,
                    "location": location,
                    "all_day": all_day,
                    "timezone": timezone,
                    "status": status,
                },
            )

        @agent.tool(name="calendar_update_event")
        async def calendar_update_event(
            ctx: RunContext[AgentDeps],
            event_id: str,
            title: str | None = None,
            start_at: str | None = None,
            end_at: str | None = None,
            description: str | None = None,
            location: str | None = None,
            all_day: bool | None = None,
            timezone: str | None = None,
            status: str | None = None,
        ) -> str:
            return await _execute_tool(
                ctx,
                "calendar_update_event",
                {
                    "event_id": event_id,
                    "title": title,
                    "start_at": start_at,
                    "end_at": end_at,
                    "description": description,
                    "location": location,
                    "all_day": all_day,
                    "timezone": timezone,
                    "status": status,
                },
            )

        @agent.tool(name="calendar_move_event")
        async def calendar_move_event(
            ctx: RunContext[AgentDeps],
            event_id: str,
            start_at: str,
            end_at: str,
        ) -> str:
            return await _execute_tool(
                ctx,
                "calendar_move_event",
                {"event_id": event_id, "start_at": start_at, "end_at": end_at},
            )

        @agent.tool(name="calendar_delete_event")
        async def calendar_delete_event(ctx: RunContext[AgentDeps], event_id: str) -> str:
            return await _execute_tool(ctx, "calendar_delete_event", {"event_id": event_id})

        @agent.tool(name="calendar_sync_blackboard")
        async def calendar_sync_blackboard(ctx: RunContext[AgentDeps]) -> str:
            return await _execute_tool(ctx, "calendar_sync_blackboard", {})

        @agent.tool(name="calendar_clone_blackboard_event")
        async def calendar_clone_blackboard_event(ctx: RunContext[AgentDeps], event_id: str) -> str:
            return await _execute_tool(
                ctx, "calendar_clone_blackboard_event", {"event_id": event_id}
            )

        @agent.tool(name="list_local_files")
        async def list_local_files(
            ctx: RunContext[AgentDeps],
            path: str = ".",
            recursive: bool = False,
            max_entries: int = 50,
        ) -> str:
            return await _execute_tool(
                ctx,
                "list_local_files",
                {"path": path, "recursive": recursive, "max_entries": max_entries},
            )

        @agent.tool(name="read_local_file")
        async def read_local_file(
            ctx: RunContext[AgentDeps], path: str, max_chars: int = 12000
        ) -> str:
            return await _execute_tool(
                ctx, "read_local_file", {"path": path, "max_chars": max_chars}
            )

        @agent.tool(name="write_local_file", requires_approval=True)
        async def write_local_file(
            ctx: RunContext[AgentDeps],
            path: str,
            content: str,
            append: bool = False,
        ) -> str:
            return await _execute_tool(
                ctx,
                "write_local_file",
                {"path": path, "content": content, "append": append},
            )

        @agent.tool(name="run_local_command", requires_approval=True)
        async def run_local_command(
            ctx: RunContext[AgentDeps],
            command: list[str] | str,
            timeout_seconds: int = 20,
        ) -> str:
            return await _execute_tool(
                ctx,
                "run_local_command",
                {"command": command, "timeout_seconds": timeout_seconds},
            )

        @agent.tool(name="fetch_webpage", requires_approval=True)
        async def fetch_webpage(
            ctx: RunContext[AgentDeps], url: str, max_chars: int = 12000
        ) -> str:
            return await _execute_tool(ctx, "fetch_webpage", {"url": url, "max_chars": max_chars})

        @agent.tool(name="rag_index_folder", requires_approval=True)
        async def rag_index_folder(
            ctx: RunContext[AgentDeps],
            path: str = ".",
            recursive: bool = True,
            extensions: list[str] | None = None,
        ) -> str:
            return await _execute_tool(
                ctx,
                "rag_index_folder",
                {"path": path, "recursive": recursive, "extensions": extensions or []},
            )

        @agent.tool(name="rag_search")
        async def rag_search(ctx: RunContext[AgentDeps], query: str, top_k: int = 5) -> str:
            return await _execute_tool(ctx, "rag_search", {"query": query, "top_k": top_k})

        @agent.tool(name="rag_answer")
        async def rag_answer(ctx: RunContext[AgentDeps], query: str, top_k: int = 5) -> str:
            return await _execute_tool(ctx, "rag_answer", {"query": query, "top_k": top_k})

        @agent.tool(name="create_quiz")
        async def create_quiz(
            ctx: RunContext[AgentDeps],
            topic: str,
            question_count: int = 5,
            source_material: str | None = None,
            title: str | None = None,
        ) -> str:
            return await _execute_tool(
                ctx,
                "create_quiz",
                {
                    "topic": topic,
                    "question_count": question_count,
                    "source_material": source_material,
                    "title": title,
                },
            )

        @agent.tool(name="quiz_history_summary")
        async def quiz_history_summary(ctx: RunContext[AgentDeps], limit: int = 5) -> str:
            return await _execute_tool(ctx, "quiz_history_summary", {"limit": limit})

        @agent.tool(name="get_current_datetime")
        async def get_current_datetime(ctx: RunContext[AgentDeps]) -> str:
            return await _execute_tool(ctx, "get_current_datetime", {})

        @agent.tool(name="blackboard_get_all_courses")
        async def blackboard_get_all_courses(ctx: RunContext[AgentDeps]) -> str:
            return await _execute_tool(ctx, "blackboard_get_all_courses", {})

        @agent.tool(name="blackboard_get_course_announcements")
        async def blackboard_get_course_announcements(
            ctx: RunContext[AgentDeps],
            course_id: Annotated[
                str,
                Field(
                    pattern=r"^_\d+_\d+$",
                    description="The exact 'course_id' field returned by the blackboard_get_all_courses tool. Required format is usually '_XXXX_X'.",
                ),
            ],
        ) -> str:
            """
            Get announcements for a specific Blackboard course.

            Args:
                course_id: The ID of the course in Blackboard (e.g. _8012_1).
            """
            return await _execute_tool(
                ctx, "blackboard_get_course_announcements", {"course_id": course_id}
            )

        @agent.tool(name="blackboard_test_api_available")
        async def blackboard_test_api_available(ctx: RunContext[AgentDeps]) -> str:
            return await _execute_tool(ctx, "blackboard_test_api_available", {})

        @agent.tool(name="blackboard_get_calendar_items")
        async def blackboard_get_calendar_items(ctx: RunContext[AgentDeps]) -> str:
            return await _execute_tool(ctx, "blackboard_get_calendar_items", {})

        return agent

    def _history_to_model_messages(self, history: list[dict[str, str]]):
        messages: list[ModelRequest | ModelResponse] = []
        for item in history:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                messages.append(ModelRequest(parts=[UserPromptPart(content)]))
            elif role == "assistant":
                messages.append(ModelResponse(parts=[TextPart(content)]))
        return messages

    @staticmethod
    async def _emit_response_chunk(
        callback: Callable[[str], Awaitable[None] | None] | None,
        chunk: str,
    ) -> None:
        if callback is None or not chunk:
            return
        maybe_awaitable = callback(chunk)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    def _build_event_stream_handler(
        self,
        on_response_chunk: Callable[[str], Awaitable[None] | None] | None,
        on_thinking_chunk: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        if on_response_chunk is None and on_thinking_chunk is None:
            return None

        async def event_stream_handler(_run_ctx, event_stream) -> None:
            async for event in event_stream:
                if isinstance(event, PartStartEvent):
                    if isinstance(event.part, TextPart):
                        await self._emit_response_chunk(on_response_chunk, event.part.content)
                    elif isinstance(event.part, ThinkingPart):
                        await self._emit_response_chunk(on_thinking_chunk, event.part.content)
                elif isinstance(event, PartDeltaEvent):
                    if isinstance(event.delta, TextPartDelta):
                        await self._emit_response_chunk(
                            on_response_chunk, event.delta.content_delta
                        )
                    elif isinstance(event.delta, ThinkingPartDelta):
                        await self._emit_response_chunk(
                            on_thinking_chunk, event.delta.content_delta
                        )

        return event_stream_handler

    async def run(
        self,
        *,
        user_input: str | None,
        session_id: str,
        workspace_root: str | None,
        history: list[dict[str, str]] | None = None,
        message_history: list[Any] | None = None,
        deferred_tool_results: DeferredToolResults | None = None,
        on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None = None,
        on_response_chunk: Callable[[str], Awaitable[None] | None] | None = None,
        on_thinking_chunk: Callable[[str], Awaitable[None] | None] | None = None,
    ):
        deps = AgentDeps(
            session=self.session,
            session_id=session_id,
            workspace_root=workspace_root,
            tool_service=self.tool_service,
            on_tool_events=on_tool_events,
        )

        # Build dynamic system prompt with tool examples
        dynamic_prompt = SYSTEM_PROMPT
        if user_input:
            tool_examples = await build_tool_examples_prompt(self.session, user_input)
            if tool_examples:
                dynamic_prompt = SYSTEM_PROMPT + tool_examples

        # Build agent with dynamic prompt
        agent = self._build_agent(system_prompt=dynamic_prompt)
        final_history = message_history or self._history_to_model_messages(history or [])
        run_result = await agent.run(
            user_prompt=user_input,
            message_history=final_history,
            deferred_tool_results=deferred_tool_results,
            deps=deps,
            event_stream_handler=self._build_event_stream_handler(
                on_response_chunk, on_thinking_chunk=on_thinking_chunk
            ),
        )
        return run_result, deps

    # async def run_stream(
    #     self,
    #     *,
    #     user_input: str | None,
    #     session_id: str,
    #     workspace_root: str | None,
    #     history: list[dict[str, str]] | None = None,
    #     message_history: list[Any] | None = None,
    #     deferred_tool_results: DeferredToolResults | None = None,
    # ) -> tuple[Any, AgentDeps, Any]:
    #     """Run agent with streaming output.

    #     Returns a tuple of (result, deps, stream_context) where stream_context
    #     is an async context manager that provides the stream.
    #     """
    #     deps = AgentDeps(
    #         session=self.session,
    #         session_id=session_id,
    #         workspace_root=workspace_root,
    #         tool_service=self.tool_service,
    #     )
    #     agent = self._build_agent()
    #     final_history = message_history or self._history_to_model_messages(history or [])

    #     # Use streaming run - returns an async context manager
    #     # We return the context manager itself, caller needs to use 'async with'
    #     stream_context = agent.run_stream(
    #         user_prompt=user_input,
    #         message_history=final_history,
    #         deferred_tool_results=deferred_tool_results,
    #         deps=deps,
    #     )

    #     return run_result, deps

    @staticmethod
    def extract_text_or_requests(run_result: Any) -> str | DeferredToolRequests:
        return run_result.output if hasattr(run_result, "output") else run_result.response

    @staticmethod
    def build_deferred_approval_result(
        tool_call_id: str,
        *,
        approved: bool,
    ) -> DeferredToolResults:
        if approved:
            return DeferredToolResults(approvals={tool_call_id: ToolApproved()})
        return DeferredToolResults(
            approvals={tool_call_id: ToolDenied(message="The tool call was denied by the user.")}
        )

    @staticmethod
    def parse_tool_arguments(args: dict[str, Any] | str | None) -> dict[str, Any]:
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                return json.loads(args)
            except json.JSONDecodeError:
                return {"raw": args}
        return {}
