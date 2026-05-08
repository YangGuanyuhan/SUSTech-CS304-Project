"""Agent orchestration backed by PydanticAI."""

from __future__ import annotations

import inspect
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic_ai.tools import DeferredToolRequests
from sqlalchemy.orm import Session

from backend.agent.pydantic_runtime import PydanticAIRuntime
from backend.models.tooling import AgentTurnResult, ToolTrace
from backend.services.approval_service import approval_service
from backend.services.context_manager import ContextWindowManager
from backend.services.llm_logging_service import llm_logger
from backend.services.memory_consolidator import MemoryConsolidator
from backend.services.runtime_settings import runtime_settings
from backend.services.task_service import TaskHistoryService
from backend.services.tool_learning_service import ToolLearningService


class StudentProductivityAgent:
    """Agent facade that preserves the existing API contract."""

    def __init__(self, session: Session):
        self.session = session
        self.runtime = PydanticAIRuntime(session)
        self.context_manager = ContextWindowManager(session)
        self.tool_learning = ToolLearningService(session)
        self.memory_consolidator = MemoryConsolidator(session)

    async def _build_history(
        self, session_id: str, max_context_tokens: int = 8000
    ) -> list[dict[str, str]]:
        """Build conversation history with intelligent context management."""
        # Get recent messages from database
        raw_messages = await TaskHistoryService(self.session).get_recent_messages(
            session_id, limit=20
        )

        if not raw_messages:
            return []

        # Apply context window management
        prepared_messages, stats = await self.context_manager.prepare_context(
            raw_messages, max_context_tokens=max_context_tokens, min_recent_messages=5
        )

        # Log compression stats if compression occurred
        if stats["compression_ratio"] < 1.0:
            llm_logger.log_event(
                session_id,
                "context_compression",
                {
                    "original_messages": stats["original_message_count"],
                    "final_messages": stats["final_message_count"],
                    "original_tokens": stats["original_tokens"],
                    "final_tokens": stats["final_tokens"],
                    "tokens_saved": stats["tokens_saved"],
                    "compression_ratio": round(stats["compression_ratio"], 3),
                },
            )

        return prepared_messages

    async def _emit_tool_events(
        self,
        on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None,
        tool_events: list[ToolTrace],
    ) -> None:
        if on_tool_events is None:
            return
        snapshot = [event.model_copy(deep=True) for event in tool_events]
        maybe_awaitable = on_tool_events(snapshot)
        if inspect.isawaitable(maybe_awaitable):
            await maybe_awaitable

    def _approval_result(
        self,
        *,
        session_id: str,
        user_input: str,
        workspace_root: str | None,
        run_result: Any,
        deferred: DeferredToolRequests,
        tool_events: list[ToolTrace],
        tools_used: list[str],
    ) -> AgentTurnResult:
        if not deferred.approvals:
            return AgentTurnResult(
                response="The model requested a deferred tool flow that this server does not support yet.",
                tool_events=tool_events,
                tools_used=tools_used,
            )

        # Build list of all tool calls needing approval
        tool_calls = []
        for approval_call in deferred.approvals:
            arguments = self.runtime.parse_tool_arguments(approval_call.args)
            tool_name = approval_call.tool_name
            tool_calls.append(
                {
                    "tool_call_id": approval_call.tool_call_id,
                    "tool_name": tool_name,
                    "tool_arguments": arguments,
                    "summary": self.runtime.tool_service.build_approval_summary(
                        tool_name,
                        arguments,
                        workspace_root=workspace_root,
                    ),
                }
            )
            # Add to tool events
            tool_events.append(
                ToolTrace(
                    tool_name=tool_name,
                    arguments=arguments,
                    status="awaiting_approval",
                )
            )

        # Create batch approval request
        batch_request = approval_service.create_batch(
            session_id=session_id,
            user_input=user_input,
            tool_calls=tool_calls,
            workspace_root=workspace_root,
            messages=list(run_result.all_messages()),
            tools_used=list(tools_used),
            tool_events=list(tool_events),
            deferred_metadata=dict(deferred.metadata),
        )

        # Log all approvals
        for approval in batch_request.approvals:
            llm_logger.log_event(
                session_id,
                "approval_required",
                {
                    "approval_id": approval.id,
                    "tool_name": approval.tool_name,
                    "arguments": approval.arguments,
                    "summary": approval.summary,
                },
            )

        return AgentTurnResult(
            tools_used=tools_used,
            tool_events=tool_events,
            approval_request=batch_request,
        )

    async def _run_turn(
        self,
        *,
        user_input: str | None,
        session_id: str,
        workspace_root: str | None,
        history: list[dict[str, str]] | None = None,
        message_history: list[Any] | None = None,
        deferred_tool_results: Any | None = None,
        prior_tool_events: list[ToolTrace] | None = None,
        prior_tools_used: list[str] | None = None,
        on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None = None,
        on_response_chunk: Callable[[str], Awaitable[None] | None] | None = None,
        on_thinking_chunk: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> AgentTurnResult:
        llm_logger.log_event(
            session_id,
            "llm_request",
            {
                "history": history or [],
                "user_input": user_input or "",
                "workspace_root": workspace_root,
                "runtime": "pydantic_ai",
            },
        )
        prior_events_snapshot = list(prior_tool_events or [])

        async def runtime_tool_events_callback(tool_events: list[ToolTrace]) -> None:
            await self._emit_tool_events(on_tool_events, prior_events_snapshot + list(tool_events))

        run_result, deps = await self.runtime.run(
            user_input=user_input,
            session_id=session_id,
            workspace_root=workspace_root,
            history=history,
            message_history=message_history,
            deferred_tool_results=deferred_tool_results,
            on_tool_events=runtime_tool_events_callback if on_tool_events else None,
            on_response_chunk=on_response_chunk,
            on_thinking_chunk=on_thinking_chunk,
        )
        output = self.runtime.extract_text_or_requests(run_result)
        tool_events = prior_events_snapshot + deps.tool_events
        tools_used = list(prior_tools_used or []) + deps.tools_used

        if isinstance(output, DeferredToolRequests):
            llm_logger.log_event(
                session_id,
                "llm_response",
                {
                    "deferred_approvals": [
                        {
                            "tool_name": call.tool_name,
                            "tool_call_id": call.tool_call_id,
                            "arguments": self.runtime.parse_tool_arguments(call.args),
                        }
                        for call in output.approvals
                    ],
                    "deferred_calls": [call.tool_name for call in output.calls],
                },
            )
            approval_result = self._approval_result(
                session_id=session_id,
                user_input=user_input or "",
                workspace_root=workspace_root,
                run_result=run_result,
                deferred=output,
                tool_events=tool_events,
                tools_used=tools_used,
            )
            await self._emit_tool_events(on_tool_events, approval_result.tool_events)
            return approval_result

        response_text = str(output).strip()
        llm_logger.log_event(
            session_id,
            "llm_response",
            {
                "content": response_text[:3000]
                + ("...<truncated>" if len(response_text) > 3000 else ""),
                "tools_used": tools_used,
            },
        )
        for event in deps.tool_events:
            if event.output:
                llm_logger.log_event(
                    session_id,
                    "tool_result",
                    {
                        "tool_name": event.tool_name,
                        "arguments": event.arguments,
                        "status": event.status,
                        "result": event.output[:3000]
                        + ("...<truncated>" if len(event.output) > 3000 else ""),
                    },
                )
        return AgentTurnResult(
            response=response_text,
            tools_used=tools_used,
            tool_events=tool_events,
        )

    async def run(
        self,
        message: str,
        session_id: str,
        workspace_root: str | None = None,
        on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None = None,
        on_response_chunk: Callable[[str], Awaitable[None] | None] | None = None,
        on_thinking_chunk: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> dict[str, object]:
        """Generate a response and record task history."""

        try:
            result = await self._run_turn(
                user_input=message,
                session_id=session_id,
                workspace_root=workspace_root,
                history=await self._build_history(session_id),
                on_tool_events=on_tool_events,
                on_response_chunk=on_response_chunk,
                on_thinking_chunk=on_thinking_chunk,
            )
        except Exception as exc:
            llm_config = runtime_settings.get_llm_config()
            result = AgentTurnResult(
                response=(
                    f"LLM is not ready yet: {exc}\n"
                    f"Current runtime config: `{llm_config.provider}` / `{llm_config.model}`.\n"
                    "Open the settings panel and configure an OpenAI-compatible endpoint."
                ),
                tool_events=[],
            )

        if result.approval_request is None:
            await TaskHistoryService(self.session).add_history(
                session_id,
                message,
                result.response,
                result.tools_used,
            )

            # Learn from successful tool usage
            if result.tool_events:
                await self.tool_learning.extract_patterns_from_tool_events(
                    user_query=message,
                    tool_events=result.tool_events,
                )

            # Extract memories from conversation
            try:
                await self.memory_consolidator.extract_memory_from_conversation(
                    user_input=message,
                    agent_response=result.response,
                    session_id=session_id,
                )
            except Exception:
                # Don't fail the request if memory extraction fails
                pass

        return result.model_dump(mode="json")

    async def resume_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
        on_tool_events: Callable[[list[ToolTrace]], Awaitable[None] | None] | None = None,
        on_response_chunk: Callable[[str], Awaitable[None] | None] | None = None,
        on_thinking_chunk: Callable[[str], Awaitable[None] | None] | None = None,
    ) -> dict[str, object]:
        pending = approval_service.pop(approval_id)
        if pending is None:
            return AgentTurnResult(
                response="Approval request was not found or has already been handled."
            ).model_dump(mode="json")

        # Build deferred results for all tool calls in the batch
        deferred_results = None
        for tool_call in pending.tool_calls:
            result = self.runtime.build_deferred_approval_result(
                tool_call["tool_call_id"],
                approved=approved,
            )
            if deferred_results is None:
                deferred_results = result
            else:
                # DeferredToolResults stores approvals/calls as dictionaries keyed by
                # tool_call_id. PydanticAI requires a result for every deferred call.
                if hasattr(deferred_results, "approvals") and hasattr(result, "approvals"):
                    deferred_results.approvals.update(result.approvals)
                if hasattr(deferred_results, "calls") and hasattr(result, "calls"):
                    deferred_results.calls.update(result.calls)
                if hasattr(deferred_results, "metadata") and hasattr(result, "metadata"):
                    deferred_results.metadata.update(result.metadata)

        if pending.deferred_metadata and deferred_results:
            deferred_results.metadata.update(pending.deferred_metadata)

        # Update tool events: remove awaiting_approval status for all tools in batch
        pending.tool_events = [
            event
            for event in pending.tool_events
            if not (
                any(
                    event.tool_name == tc["tool_name"] and event.arguments == tc["tool_arguments"]
                    for tc in pending.tool_calls
                )
                and event.status == "awaiting_approval"
            )
        ]

        if not approved:
            # Add denied status for all tools in the batch
            for tool_call in pending.tool_calls:
                pending.tool_events.append(
                    ToolTrace(
                        tool_name=tool_call["tool_name"],
                        arguments=tool_call["tool_arguments"],
                        status="denied",
                        output='{"ok": false, "error": "User denied approval."}',
                    )
                )

        # Log approval resolution for each tool
        for tool_call in pending.tool_calls:
            llm_logger.log_event(
                pending.session_id,
                "approval_resolution",
                {
                    "approval_id": pending.id,
                    "approved": approved,
                    "tool_name": tool_call["tool_name"],
                    "arguments": tool_call["tool_arguments"],
                },
            )

        try:
            result = await self._run_turn(
                user_input=None,
                session_id=pending.session_id,
                workspace_root=pending.workspace_root,
                message_history=pending.messages,
                deferred_tool_results=deferred_results,
                prior_tool_events=pending.tool_events,
                prior_tools_used=pending.tools_used,
                on_tool_events=on_tool_events,
                on_response_chunk=on_response_chunk,
                on_thinking_chunk=on_thinking_chunk,
            )
        except Exception as exc:
            result = AgentTurnResult(
                response=f"LLM request failed: {exc}",
                tools_used=pending.tools_used,
                tool_events=pending.tool_events,
            )

        if result.approval_request is None:
            await TaskHistoryService(self.session).add_history(
                pending.session_id,
                pending.user_input,
                result.response,
                result.tools_used,
            )

            # Learn from successful tool usage after approval
            if result.tool_events:
                await self.tool_learning.extract_patterns_from_tool_events(
                    user_query=pending.user_input,
                    tool_events=result.tool_events,
                )

        return result.model_dump(mode="json")


def create_agent(session: Session) -> StudentProductivityAgent:
    """Factory function to create an agent instance."""
    return StudentProductivityAgent(session)
