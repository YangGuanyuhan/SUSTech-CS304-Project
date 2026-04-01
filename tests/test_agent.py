from unittest.mock import AsyncMock

from backend.agent.core import StudentProductivityAgent
from backend.services.llm_service import LLMConfigurationError


async def test_agent_returns_llm_response(db_session):
    agent = StudentProductivityAgent(db_session)
    agent.llm_service.create_chat_completion = AsyncMock(
        return_value=type(
            "Response",
            (),
            {
                "choices": [
                    type(
                        "Choice",
                        (),
                        {"message": type("Message", (), {"content": "Here is the answer.", "tool_calls": None})()},
                    )
                ]
            },
        )()
    )
    result = await agent.run("Hello", "session-1")
    assert result["response"] == "Here is the answer."


async def test_agent_uses_llm_runtime_fallback_when_unconfigured(db_session):
    agent = StudentProductivityAgent(db_session)
    agent.llm_service.create_chat_completion = AsyncMock(side_effect=LLMConfigurationError("No API key"))
    result = await agent.run("Hello", "session-2")
    assert "LLM is not ready yet" in result["response"]
