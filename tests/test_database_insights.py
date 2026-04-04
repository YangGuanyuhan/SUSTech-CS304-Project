from backend.services.database_insights_service import DatabaseInsightsService
from backend.services.memory_service import MemoryService
from backend.services.quiz_service import QuizService
from backend.services.settings_service import SettingsService
from backend.services.task_service import TaskHistoryService
from backend.models.settings import LLMProfile


async def test_database_overview_reports_current_counts(db_session):
    await MemoryService(db_session).save_memory("assignment", {"course": "CS305"}, "blackboard", ["deadline"])
    await TaskHistoryService(db_session).add_history("chat-a", "hello", "world", ["memory_search"])
    await SettingsService(db_session).save_llm_profile(
        LLMProfile(name="local", provider="openai", model="gpt-4o-mini", base_url="https://example.com/v1")
    )

    quiz_service = QuizService(db_session)
    quiz = await quiz_service.create_quiz(
        chat_session_id="chat-a",
        topic="Databases",
        question_count=2,
        source_material="Transactions and isolation levels.",
    )
    await quiz_service.submit_attempt(
        quiz.id,
        [],
    )

    overview = await DatabaseInsightsService(db_session).get_overview()

    assert overview.counts.memories == 1
    assert overview.counts.task_history == 1
    assert overview.counts.quiz_sessions == 1
    assert overview.counts.quiz_attempts == 1
    assert overview.counts.user_preferences >= 1
    assert overview.memory_categories[0].category == "blackboard"
    assert overview.session_activity[0].session_id == "chat-a"
    assert overview.schema_readiness.typed_json_ready is True
    assert overview.schema_readiness.quiz_relationships_ready is True
