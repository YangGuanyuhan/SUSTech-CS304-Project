"""Agent orchestration with OpenAI-compatible tool calls."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.orm import Session

from backend.models.tooling import AgentTurnResult
from backend.services.agent_tool_service import (
    AgentToolService,
    ToolExecutionError,
    get_tool_definitions,
)
from backend.services.approval_service import approval_service
from backend.services.llm_service import LLMConfigurationError, LLMConnectionError, LLMService
from backend.services.llm_logging_service import llm_logger
from backend.services.runtime_settings import runtime_settings
from backend.services.task_service import TaskHistoryService

try:
    from pydantic_ai import Agent
except ImportError:  # pragma: no cover - optional dependency during static work
    Agent = None


SYSTEM_PROMPT = """
You are Student Productivity Agent, a study assistant for SUSTech students.
You have access to real backend tools. Treat local file access, local command execution,
web access, and memory operations as available capabilities provided by tools.

Tool usage rules:
1. When the user asks to read files, list directories, write files, run commands, or visit webpages,
   prefer the matching tool instead of replying that you cannot access the local machine or the web.
2. For file tools and command tools, stay within the configured workspace root.
3. For local file access, local command execution, and webpage access, the backend may require user approval.
   You should still initiate the tool call when it is needed; the system will handle approval.
4. Do not say that you are blocked by sandbox or security restrictions unless a tool result explicitly says so.
5. Only claim an action succeeded after you receive a tool result confirming it.
6. Use memory tools to save durable user preferences, project facts, and useful follow-up context when appropriate.
7. If a tool result reports an error, explain that error plainly and suggest the next step.

Response style:
- Be concise and practical.
- Respond in Markdown when useful.
- Do not invent file contents, command output, or webpage content.
""".strip()


class StudentProductivityAgent:
    """Thin orchestrator that keeps the agent boundary stable."""

    def __init__(self, session: Session):
        self.session = session
        self.agent = Agent(model="test", system_prompt=SYSTEM_PROMPT) if Agent is not None else None
        self.llm_service = LLMService()
        self.tool_service = AgentToolService(session)

    def _serialize_messages(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return json.loads(json.dumps(messages, ensure_ascii=False))

    async def _build_messages(self, message: str, session_id: str, workspace_root: str | None) -> list[dict[str, Any]]:
        history = await TaskHistoryService(self.session).get_recent_messages(session_id, limit=10)
        workspace_instruction = (
            f"Approved workspace root: `{workspace_root}`. "
            "Local file and command tools must stay inside this root."
            if workspace_root
            else "No workspace root is configured yet. Do not use local file or command tools until the user sets one."
        )
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": f"{SYSTEM_PROMPT}\n\n{workspace_instruction}"}
        ]
        messages.extend(history)
        messages.append({"role": "user", "content": message})
        return messages

    async def _continue_with_messages(
        self,
        *,
        user_input: str,
        session_id: str,
        messages: list[dict[str, Any]],
        tools_used: list[str],
        workspace_root: str | None,
    ) -> AgentTurnResult:
        while True:
            llm_logger.log_event(
                session_id,
                "llm_request",
                {
                    "messages": llm_logger.summarize_messages(messages),
                    "tools": [tool["function"]["name"] for tool in get_tool_definitions()],
                    "workspace_root": workspace_root,
                },
            )
            response = await self.llm_service.create_chat_completion(messages, tools=get_tool_definitions())
            llm_logger.log_event(session_id, "llm_response", llm_logger.summarize_response(response))
            assistant = response.choices[0].message
            assistant_message: dict[str, Any] = {"role": "assistant"}
            if assistant.content:
                assistant_message["content"] = assistant.content
            if assistant.tool_calls:
                assistant_message["tool_calls"] = [
                    tool_call.model_dump(mode="json", exclude_none=True) for tool_call in assistant.tool_calls
                ]
            messages.append(assistant_message)

            if not assistant.tool_calls:
                return AgentTurnResult(response=(assistant.content or "").strip(), tools_used=tools_used)

            for tool_call in assistant.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments or "{}")
                except json.JSONDecodeError:
                    arguments = {}

                if self.tool_service.requires_approval(tool_name):
                    approval_request = approval_service.create(
                        session_id=session_id,
                        user_input=user_input,
                        tool_call_id=tool_call.id,
                        tool_name=tool_name,
                        tool_arguments=arguments,
                        summary=self.tool_service.build_approval_summary(
                            tool_name,
                            arguments,
                            workspace_root=workspace_root,
                        ),
                        workspace_root=workspace_root,
                        messages=self._serialize_messages(messages),
                        tools_used=list(tools_used),
                    )
                    llm_logger.log_event(
                        session_id,
                        "approval_required",
                        {
                            "approval_id": approval_request.id,
                            "tool_name": tool_name,
                            "arguments": arguments,
                            "summary": approval_request.summary,
                        },
                    )
                    return AgentTurnResult(tools_used=tools_used, approval_request=approval_request)

                tool_result = await self._execute_tool(tool_name, arguments, workspace_root=workspace_root)
                tools_used.append(tool_name)
                llm_logger.log_event(
                    session_id,
                    "tool_result",
                    {
                        "tool_name": tool_name,
                        "arguments": arguments,
                        "result": tool_result[:3000] + ("...<truncated>" if len(tool_result) > 3000 else ""),
                    },
                )
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result,
                    }
                )

    async def _execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        workspace_root: str | None,
    ) -> str:
        try:
            return await self.tool_service.execute(tool_name, arguments, workspace_root=workspace_root)
        except ToolExecutionError as exc:
            return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
        except Exception as exc:
            return json.dumps({"ok": False, "error": f"Tool failed: {exc}"}, ensure_ascii=False)

    async def run(self, message: str, session_id: str, workspace_root: str | None = None) -> dict[str, object]:
        """Generate a response and record task history."""

        try:
            result = await self._continue_with_messages(
                user_input=message,
                session_id=session_id,
                messages=await self._build_messages(message, session_id, workspace_root),
                tools_used=[],
                workspace_root=workspace_root,
            )
        except (LLMConfigurationError, LLMConnectionError) as exc:
            llm_config = runtime_settings.get_llm_config()
            result = AgentTurnResult(
                response=(
                    f"LLM is not ready yet: {exc}\n"
                    f"Current runtime config: `{llm_config.provider}` / `{llm_config.model}`.\n"
                    "Open the settings panel and configure an OpenAI-compatible endpoint."
                )
            )
        except Exception as exc:
            result = AgentTurnResult(response=f"LLM request failed: {exc}")

        if result.approval_request is None:
            await TaskHistoryService(self.session).add_history(
                session_id,
                message,
                result.response,
                result.tools_used,
            )
        return result.model_dump(mode="json")

    async def resume_approval(
        self,
        approval_id: str,
        *,
        approved: bool,
    ) -> dict[str, object]:
        pending = approval_service.pop(approval_id)
        if pending is None:
            return AgentTurnResult(response="Approval request was not found or has already been handled.").model_dump(
                mode="json"
            )

        if approved:
            tool_result = await self._execute_tool(
                pending.tool_name,
                pending.tool_arguments,
                workspace_root=pending.workspace_root,
            )
            pending.tools_used.append(pending.tool_name)
        else:
            tool_result = json.dumps(
                {"ok": False, "error": f"User denied approval for `{pending.tool_name}`."},
                ensure_ascii=False,
            )
        llm_logger.log_event(
            pending.session_id,
            "approval_resolution",
            {
                "approval_id": pending.id,
                "approved": approved,
                "tool_name": pending.tool_name,
                "arguments": pending.tool_arguments,
                "result": tool_result[:3000] + ("...<truncated>" if len(tool_result) > 3000 else ""),
            },
        )

        pending.messages.append(
            {
                "role": "tool",
                "tool_call_id": pending.tool_call_id,
                "content": tool_result,
            }
        )

        try:
            result = await self._continue_with_messages(
                user_input=pending.user_input,
                session_id=pending.session_id,
                messages=pending.messages,
                tools_used=pending.tools_used,
                workspace_root=pending.workspace_root,
            )
        except (LLMConfigurationError, LLMConnectionError) as exc:
            llm_config = runtime_settings.get_llm_config()
            result = AgentTurnResult(
                response=(
                    f"LLM is not ready yet: {exc}\n"
                    f"Current runtime config: `{llm_config.provider}` / `{llm_config.model}`.\n"
                    "Open the settings panel and configure an OpenAI-compatible endpoint."
                ),
                tools_used=pending.tools_used,
            )
        except Exception as exc:
            result = AgentTurnResult(response=f"LLM request failed: {exc}", tools_used=pending.tools_used)

        if result.approval_request is None:
            await TaskHistoryService(self.session).add_history(
                pending.session_id,
                pending.user_input,
                result.response,
                result.tools_used,
            )
        return result.model_dump(mode="json")

    async def run_stream(
        self,
        message: str,
        session_id: str,
        workspace_root: str | None = None,
    ) -> AsyncIterator[str]:
        """Yield a text response in SSE-friendly chunks."""

        result = await self.run(message, session_id, workspace_root)
        if result.get("approval_request"):
            return
        response = str(result.get("response", ""))
        if not response:
            return
        chunk_size = 600
        for index in range(0, len(response), chunk_size):
            yield response[index : index + chunk_size]
