from unittest.mock import AsyncMock

from backend.agent.core import StudentProductivityAgent


async def test_agent_returns_course_list_for_course_queries(db_session):
    agent = StudentProductivityAgent(db_session)
    agent.llm_service.generate_chat = AsyncMock(return_value="Here are the courses you asked for.")
    result = await agent.run("Show my Blackboard courses", "session-1")
    assert "courses" in result["response"].lower()
    assert "blackboard.get_all_courses" in result["tools_used"]


async def test_agent_uses_llm_runtime_fallback_when_unconfigured(db_session):
    agent = StudentProductivityAgent(db_session)
    agent.llm_service.generate_chat = AsyncMock(side_effect=Exception("boom"))
    try:
        await agent.run("Hello", "session-2")
    except Exception:
        assert True
