"""Agent orchestration."""

from __future__ import annotations

from collections.abc import AsyncIterator

from openai.types.chat import ChatCompletionMessageParam
from sqlalchemy.orm import Session

from backend.agent.memory.store import get_relevant_memories
from backend.agent.tools.blackboard import get_all_courses
from backend.agent.tools.search import search_web
from backend.services.llm_service import LLMConfigurationError, LLMConnectionError, LLMService
from backend.services.runtime_settings import runtime_settings
from backend.services.task_service import TaskHistoryService

try:
    from pydantic_ai import Agent
except ImportError:  # pragma: no cover - optional dependency during static work
    Agent = None


SYSTEM_PROMPT = """
You are Student Productivity Agent, a study assistant for SUSTech students.
Use tools conservatively, never send emails without explicit confirmation, and
explain failures in a user-friendly way without exposing internal stack traces.
Respond in Markdown when useful.
""".strip()


class StudentProductivityAgent:
    """Thin orchestrator that keeps the agent boundary stable."""

    def __init__(self, session: Session):
        self.session = session
        self.agent = Agent(model="test", system_prompt=SYSTEM_PROMPT) if Agent is not None else None
        self.llm_service = LLMService()

    async def _build_messages(self, message: str, session_id: str) -> tuple[list[ChatCompletionMessageParam], list[str]]:
        memories = await get_relevant_memories(self.session, message, limit=3)
        history = await TaskHistoryService(self.session).get_recent_messages(session_id, limit=10)
        tools_used: list[str] = []
        context_sections: list[str] = []
        lowered = message.lower()

        if "course" in lowered or "blackboard" in lowered:
            courses = await get_all_courses(self.session)
            tools_used.append("blackboard.get_all_courses")
            context_sections.append(
                "Blackboard courses:\n" + "\n".join(f"- {course.name} ({course.code})" for course in courses.data)
            )

        if "search" in lowered:
            results = await search_web(message, max_results=3)
            tools_used.append("search.search_web")
            if results:
                context_sections.append(
                    "Search results:\n"
                    + "\n".join(f"- {item.title}: {item.snippet} ({item.url})" for item in results)
                )

        if memories:
            context_sections.append(
                "Relevant memory:\n" + "\n".join(f"- {memory.key}: {memory.value}" for memory in memories)
            )

        user_content = message
        if context_sections:
            user_content += "\n\nContext:\n" + "\n\n".join(context_sections)

        messages: list[ChatCompletionMessageParam] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_content})
        return messages, tools_used

    async def run(self, message: str, session_id: str) -> dict[str, object]:
        """Generate a response and record task history."""

        messages, tools_used = await self._build_messages(message, session_id)
        try:
            response = await self.llm_service.generate_chat(messages)
        except (LLMConfigurationError, LLMConnectionError) as exc:
            llm_config = runtime_settings.get_llm_config()
            response = (
                f"LLM is not ready yet: {exc}\n"
                f"Current runtime config: `{llm_config.provider}` / `{llm_config.model}`.\n"
                "Open the settings panel and configure an OpenAI-compatible endpoint."
            )
        except Exception as exc:
            response = f"LLM request failed: {exc}"

        await TaskHistoryService(self.session).add_history(session_id, message, response, tools_used)
        return {"response": response, "tools_used": tools_used}

    async def run_stream(self, message: str, session_id: str) -> AsyncIterator[str]:
        """Yield a text response in SSE-friendly chunks."""

        messages, tools_used = await self._build_messages(message, session_id)
        parts: list[str] = []
        try:
            async for chunk in self.llm_service.stream_chat_with_fallback(messages):
                parts.append(chunk)
                yield chunk
            response = "".join(parts).strip()
        except (LLMConfigurationError, LLMConnectionError) as exc:
            llm_config = runtime_settings.get_llm_config()
            response = (
                f"LLM is not ready yet: {exc}\n"
                f"Current runtime config: `{llm_config.provider}` / `{llm_config.model}`.\n"
                "Open the settings panel and configure an OpenAI-compatible endpoint."
            )
            yield response
        except Exception as exc:
            response = f"LLM request failed: {exc}"
            yield response

        await TaskHistoryService(self.session).add_history(session_id, message, response, tools_used)
