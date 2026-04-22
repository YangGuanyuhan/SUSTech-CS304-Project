from unittest.mock import AsyncMock, patch

from backend.agent.core import StudentProductivityAgent
from backend.agent.pydantic_runtime import PydanticAIRuntime


async def test_agent_returns_llm_response(db_session):
    """Test that agent can return text responses from LLM."""
    agent = StudentProductivityAgent(db_session)

    # Mock the runtime to return a simple text response
    mock_result = AsyncMock()
    mock_result.output = "Here is the answer."

    mock_deps = AsyncMock()
    mock_deps.tool_events = []
    mock_deps.tools_used = []

    with patch.object(agent.runtime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (mock_result, mock_deps)
        with patch.object(
            agent.runtime, "extract_text_or_requests", return_value="Here is the answer."
        ):
            result = await agent.run("Hello", "session-1")
            assert result["response"] == "Here is the answer."
            assert result["thinking"] is None


async def test_agent_extracts_thinking_from_structured_response(db_session):
    agent = StudentProductivityAgent(db_session)

    mock_result = AsyncMock()
    mock_result.output = "<thinking>Check context</thinking><final>Here is the answer.</final>"

    mock_deps = AsyncMock()
    mock_deps.tool_events = []
    mock_deps.tools_used = []

    with patch.object(agent.runtime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (mock_result, mock_deps)
        with patch.object(
            agent.runtime,
            "extract_text_or_requests",
            return_value="<thinking>Check context</thinking><final>Here is the answer.</final>",
        ):
            result = await agent.run("Hello", "session-structured")
            assert result["response"] == "Here is the answer."
            assert result["thinking"] == "Check context"


async def test_agent_does_not_fail_when_thinking_parse_raises(db_session):
    agent = StudentProductivityAgent(db_session)

    mock_result = AsyncMock()
    mock_result.output = "Plain answer without tags"

    mock_deps = AsyncMock()
    mock_deps.tool_events = []
    mock_deps.tools_used = []

    with patch.object(agent.runtime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.return_value = (mock_result, mock_deps)
        with patch.object(
            agent.runtime,
            "extract_text_or_requests",
            return_value="Plain answer without tags",
        ):
            with patch("backend.agent.core.parse_thinking_response", side_effect=ValueError("bad")):
                result = await agent.run("Hello", "session-no-thinking")
                assert result["response"] == "Plain answer without tags"
                assert result["thinking"] is None


async def test_agent_uses_llm_runtime_fallback_when_unconfigured(db_session):
    """Test that agent returns fallback message when LLM is not configured."""
    agent = StudentProductivityAgent(db_session)

    # Mock runtime to raise an error (simulating missing API key)
    with patch.object(agent.runtime, "run", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = ValueError(
            "No API key is configured. Open the LLM settings panel first."
        )
        result = await agent.run("Hello", "session-2")
        assert "LLM is not ready yet" in result["response"]
        assert "No API key" in result["response"]


def test_runtime_wraps_plain_assistant_history_in_structured_tags(db_session):
    runtime = PydanticAIRuntime(db_session)

    messages = runtime._history_to_model_messages(
        [
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "plain answer"},
        ]
    )

    assert messages[1].parts[0].content == "<thinking>\n</thinking>\n<final>\nplain answer\n</final>"
