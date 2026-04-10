from unittest.mock import AsyncMock, patch

from backend.agent.core import StudentProductivityAgent


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
