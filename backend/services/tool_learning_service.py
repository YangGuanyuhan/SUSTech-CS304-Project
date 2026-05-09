"""Tool usage pattern learning service."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.db.repositories import ToolUsagePatternRepository
from backend.models.tooling import ToolTrace


class ToolLearningService:
    """Learn and retrieve successful tool usage patterns."""

    def __init__(self, session: Session):
        self.session = session
        self.repository = ToolUsagePatternRepository(session)

    async def record_tool_usage(
        self,
        tool_name: str,
        user_query: str,
        tool_arguments: dict[str, Any],
        outcome: str,
        success: bool = True,
    ) -> None:
        """
        Record a tool usage pattern.

        Args:
            tool_name: Name of the tool used
            user_query: The user's original query
            tool_arguments: Arguments passed to the tool
            outcome: Result or outcome description
            success: Whether the tool call was successful
        """
        # Check if similar pattern already exists
        existing_patterns = self.repository.find_similar(
            tool_name=tool_name, min_confidence=0.5, limit=10
        )

        # Look for exact match
        for pattern in existing_patterns:
            if (
                pattern.user_query.lower() == user_query.lower()
                and pattern.tool_arguments == tool_arguments
            ):
                # Increment usage count for existing pattern
                self.repository.increment_usage(pattern.id)
                return

        # Create new pattern
        self.repository.create(
            tool_name=tool_name,
            user_query=user_query,
            tool_arguments=tool_arguments,
            outcome=outcome,
            success=success,
            confidence_score=0.7 if success else 0.3,  # Initial confidence
        )

    async def get_tool_examples(
        self, tool_name: str, limit: int = 5, min_confidence: float = 0.6
    ) -> list[dict[str, Any]]:
        """
        Get successful usage examples for a tool.

        Args:
            tool_name: Name of the tool
            limit: Maximum number of examples
            min_confidence: Minimum confidence score

        Returns:
            List of example dicts with query, arguments, and outcome
        """
        # Get all patterns for this tool (not just successful ones for testing)
        all_patterns = self.repository.list_by_tool(tool_name=tool_name, limit=limit * 2)

        # Filter by confidence and success
        patterns = [p for p in all_patterns if p.confidence_score >= min_confidence and p.success][
            :limit
        ]

        examples = []
        for pattern in patterns:
            examples.append(
                {
                    "user_query": pattern.user_query,
                    "tool_arguments": pattern.tool_arguments,
                    "outcome": pattern.outcome,
                    "confidence": pattern.confidence_score,
                    "usage_count": pattern.usage_count,
                }
            )

        return examples

    async def extract_patterns_from_tool_events(
        self, user_query: str, tool_events: list[ToolTrace]
    ) -> None:
        """
        Extract and record patterns from successful tool events.

        Args:
            user_query: The user's original query
            tool_events: List of tool execution traces
        """
        for event in tool_events:
            # Only record successful tool calls
            if event.status == "completed" and event.output:
                await self.record_tool_usage(
                    tool_name=event.tool_name,
                    user_query=user_query,
                    tool_arguments=event.arguments,
                    outcome=event.output[:200],  # Truncate long outputs
                    success=True,
                )


# Static tool usage examples (seed data)
STATIC_TOOL_EXAMPLES = {
    "memory_search": [
        {
            "scenario": "When user asks about previous discussions",
            "example_query": "What did we discuss about Python?",
            "tool_call": {"query": "Python", "limit": 5},
            "expected_outcome": "Returns relevant memories containing 'Python'",
        },
        {
            "scenario": "When user wants to recall preferences",
            "example_query": "What are my preferences?",
            "tool_call": {"query": "preference", "limit": 10},
            "expected_outcome": "Returns user preference memories",
        },
    ],
    "memory_save": [
        {
            "scenario": "When user shares a preference",
            "example_query": "I prefer Python over JavaScript",
            "tool_call": {
                "key": "language_preference",
                "value": "Python",
                "category": "user_preference",
                "tags": ["programming", "language"],
            },
            "expected_outcome": "Saves user preference for future reference",
        },
        {
            "scenario": "When user provides important information",
            "example_query": "Remember that my project deadline is next Friday",
            "tool_call": {
                "key": "project_deadline",
                "value": "next Friday",
                "category": "general",
                "tags": ["deadline", "project"],
            },
            "expected_outcome": "Stores deadline information",
        },
    ],
    "calendar_list_events": [
        {
            "scenario": "When user asks about schedule",
            "example_query": "What's on my schedule today?",
            "tool_call": {"start": "2024-01-15T00:00:00Z", "end": "2024-01-15T23:59:59Z"},
            "expected_outcome": "Returns today's calendar events",
        },
        {
            "scenario": "When user asks about upcoming events",
            "example_query": "What do I have this week?",
            "tool_call": {"start": "2024-01-15T00:00:00Z", "end": "2024-01-21T23:59:59Z"},
            "expected_outcome": "Returns this week's events",
        },
    ],
    "rag_search": [
        {
            "scenario": "When user asks about an uploaded file in the current chat",
            "example_query": "分析一下我上传的 PDF",
            "tool_call": {"query": "uploaded PDF summary main points", "top_k": 10},
            "expected_outcome": "Retrieves content from current-chat uploaded files before any local workspace search",
        },
        {
            "scenario": "When user asks about course materials",
            "example_query": "What does the lecture say about algorithms?",
            "tool_call": {"query": "algorithms", "top_k": 5},
            "expected_outcome": "Searches indexed course materials for algorithm content",
        },
        {
            "scenario": "When user needs information from notes",
            "example_query": "Find information about data structures in my notes",
            "tool_call": {"query": "data structures", "top_k": 5},
            "expected_outcome": "Retrieves relevant sections from indexed notes",
        },
    ],
    "rag_answer": [
        {
            "scenario": "When user wants a summary or analysis of an uploaded PDF/PPT",
            "example_query": "总结一下我上传的课件",
            "tool_call": {"query": "summarize uploaded course material", "top_k": 10},
            "expected_outcome": "Answers from current-chat uploaded file content with citations",
        },
    ],
    "read_local_file": [
        {
            "scenario": "When user asks about code in a specific file",
            "example_query": "What's in main.py?",
            "tool_call": {"path": "main.py", "max_chars": 12000},
            "expected_outcome": "Reads and returns content of main.py",
        },
        {
            "scenario": "When user wants to see a configuration file",
            "example_query": "Show me the config file",
            "tool_call": {"path": "config.json", "max_chars": 12000},
            "expected_outcome": "Displays configuration file content",
        },
    ],
    "blackboard_get_all_courses": [
        {
            "scenario": "When user asks about their courses",
            "example_query": "What courses am I taking?",
            "tool_call": {},
            "expected_outcome": "Fetches list of enrolled courses from Blackboard",
        },
        {
            "scenario": "When user wants course information",
            "example_query": "Show me my classes",
            "tool_call": {},
            "expected_outcome": "Returns all courses with details",
        },
    ],
    "create_quiz": [
        {
            "scenario": "When user wants to practice a topic",
            "example_query": "Create a quiz about Python functions",
            "tool_call": {"topic": "Python functions", "question_count": 5},
            "expected_outcome": "Generates 5 quiz questions about Python functions",
        },
    ],
    "list_local_files": [
        {
            "scenario": "When user wants to see project structure",
            "example_query": "What files are in the src directory?",
            "tool_call": {"path": "src", "recursive": False, "max_entries": 50},
            "expected_outcome": "Lists files and directories in src/",
        },
    ],
}


def get_static_examples(tool_name: str) -> list[dict[str, Any]]:
    """Get static examples for a tool."""
    return STATIC_TOOL_EXAMPLES.get(tool_name, [])
