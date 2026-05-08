from unittest.mock import AsyncMock, patch

from pydantic_ai.messages import (
    FinalResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
)

from backend.agent.core import StudentProductivityAgent
from backend.agent.pydantic_runtime import (
    PydanticAIRuntime,
    build_chat_uploads_prompt,
    build_tool_examples_prompt,
)
from backend.services.chat_file_service import ChatFileService
from backend.services.rag_service import RAGService


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


async def test_runtime_stream_handler_emits_all_text_chunks_immediately(db_session):
    runtime = PydanticAIRuntime(db_session)
    streamed_chunks = []

    async def on_response_chunk(chunk: str) -> None:
        streamed_chunks.append(chunk)

    handler = runtime._build_event_stream_handler(on_response_chunk)
    assert handler is not None

    async def intermediate_stream():
        yield PartStartEvent(index=0, part=TextPart("Thinking aloud"))

    await handler(None, intermediate_stream())
    assert streamed_chunks == ["Thinking aloud"]

    streamed_chunks.clear()

    async def final_text_stream():
        yield PartStartEvent(index=0, part=TextPart("Hello"))
        yield FinalResultEvent(tool_name=None, tool_call_id=None)
        yield PartDeltaEvent(index=0, delta=TextPartDelta(content_delta=" world"))

    await handler(None, final_text_stream())
    assert streamed_chunks == ["Hello", " world"]


async def test_runtime_injects_current_chat_upload_context(db_session, tmp_path):
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    (upload_root / "course.pdf.md").write_text(
        "The uploaded syllabus covers NLP grading and weekly schedule.",
        encoding="utf-8",
    )
    await RAGService(db_session).index_folder(
        ".",
        workspace_root=str(upload_root),
        owner_id=ChatFileService.chat_owner_id("chat-upload"),
    )

    prompt = build_chat_uploads_prompt(db_session, "chat-upload")

    assert "Current chat uploaded-file context" in prompt
    assert "course.pdf.md" in prompt
    assert "Do not use local file tools" in prompt


async def test_uploaded_file_queries_get_rag_examples_not_local_file_examples(db_session):
    prompt = await build_tool_examples_prompt(db_session, "分析一下我上传的 PDF")

    assert "rag_search" in prompt
    assert "rag_answer" in prompt
    assert "read_local_file" not in prompt
