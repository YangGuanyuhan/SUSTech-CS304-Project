"""Test tool learning functionality."""

import pytest

from backend.models.tooling import ToolTrace
from backend.services.tool_learning_service import ToolLearningService, get_static_examples


@pytest.mark.asyncio
async def test_record_tool_usage(db_session):
    """Test recording tool usage patterns."""
    service = ToolLearningService(db_session)

    # Record a tool usage
    await service.record_tool_usage(
        tool_name="memory_search",
        user_query="What did we discuss about Python?",
        tool_arguments={"query": "Python", "limit": 5},
        outcome="Found 3 relevant memories",
        success=True,
    )

    # Get examples
    examples = await service.get_tool_examples("memory_search", limit=5)

    assert len(examples) > 0
    assert examples[0]["user_query"] == "What did we discuss about Python?"
    assert examples[0]["tool_arguments"] == {"query": "Python", "limit": 5}


@pytest.mark.asyncio
async def test_increment_usage_count(db_session):
    """Test that repeated patterns increment usage count."""
    service = ToolLearningService(db_session)

    # Record same pattern twice
    await service.record_tool_usage(
        tool_name="calendar_list_events",
        user_query="What's on my schedule?",
        tool_arguments={"start": "2024-01-01", "end": "2024-01-02"},
        outcome="Found 2 events",
        success=True,
    )

    await service.record_tool_usage(
        tool_name="calendar_list_events",
        user_query="What's on my schedule?",
        tool_arguments={"start": "2024-01-01", "end": "2024-01-02"},
        outcome="Found 2 events",
        success=True,
    )

    # Should have only one pattern with usage_count = 2
    examples = await service.get_tool_examples("calendar_list_events")
    assert len(examples) == 1
    assert examples[0]["usage_count"] >= 2


@pytest.mark.asyncio
async def test_extract_patterns_from_tool_events(db_session):
    """Test extracting patterns from tool events."""
    service = ToolLearningService(db_session)

    # Create mock tool events
    tool_events = [
        ToolTrace(
            tool_name="memory_search",
            arguments={"query": "Python", "limit": 5},
            status="completed",
            output='[{"key": "python_pref", "value": "likes Python"}]',
        ),
        ToolTrace(
            tool_name="rag_search",
            arguments={"query": "algorithms", "top_k": 5},
            status="completed",
            output='[{"text": "Algorithm content..."}]',
        ),
    ]

    # Extract patterns
    await service.extract_patterns_from_tool_events(
        user_query="Tell me about Python and algorithms", tool_events=tool_events
    )

    # Check that patterns were recorded
    memory_examples = await service.get_tool_examples("memory_search")
    rag_examples = await service.get_tool_examples("rag_search")

    assert len(memory_examples) > 0
    assert len(rag_examples) > 0


@pytest.mark.asyncio
async def test_confidence_filtering(db_session):
    """Test filtering by confidence score."""
    service = ToolLearningService(db_session)

    # Record a successful pattern with moderate confidence
    await service.record_tool_usage(
        tool_name="test_tool",
        user_query="test query",
        tool_arguments={"arg": "value"},
        outcome="test outcome",
        success=True,  # Successful, will have 0.7 confidence
    )

    # Should appear with moderate confidence threshold
    examples = await service.get_tool_examples("test_tool", min_confidence=0.6)
    assert len(examples) > 0

    # Should not appear with very high confidence threshold
    examples = await service.get_tool_examples("test_tool", min_confidence=0.9)
    assert len(examples) == 0


def test_get_static_examples():
    """Test retrieving static tool examples."""
    # Get examples for memory_search
    examples = get_static_examples("memory_search")
    assert len(examples) > 0
    assert "scenario" in examples[0]
    assert "example_query" in examples[0]
    assert "tool_call" in examples[0]

    # Get examples for non-existent tool
    examples = get_static_examples("nonexistent_tool")
    assert len(examples) == 0


def test_static_examples_coverage():
    """Test that we have static examples for key tools."""
    key_tools = [
        "memory_search",
        "memory_save",
        "calendar_list_events",
        "rag_search",
        "read_local_file",
        "blackboard_get_all_courses",
    ]

    for tool in key_tools:
        examples = get_static_examples(tool)
        assert len(examples) > 0, f"Missing static examples for {tool}"
