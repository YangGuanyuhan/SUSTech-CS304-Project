"""Tests for web search functionality."""

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from backend.models.task import SearchResult
from backend.services.agent_tool_service import (
    AgentToolService,
    ToolExecutionError,
    get_tool_definitions,
)


def test_web_search_tool_not_registered_without_api_key():
    """Test that web_search tool is NOT registered when BRAVE_API_KEY is not set."""
    with patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(brave_api_key=None)

        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" not in tool_names


def test_web_search_tool_not_registered_with_empty_api_key():
    """Test that web_search tool is NOT registered when BRAVE_API_KEY is empty string."""
    with patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(brave_api_key="")

        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" not in tool_names


def test_web_search_tool_registered_with_api_key():
    """Test that web_search tool IS registered when BRAVE_API_KEY is set."""
    with patch("backend.config.get_settings") as mock_settings:
        mock_settings.return_value = SimpleNamespace(brave_api_key="BSA-test-key")

        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" in tool_names

        # Verify tool definition structure
        web_search_tool = next(t for t in tools if t["function"]["name"] == "web_search")
        assert web_search_tool["type"] == "function"
        assert "query" in web_search_tool["function"]["parameters"]["properties"]
        assert "query" in web_search_tool["function"]["parameters"]["required"]


async def test_web_search_returns_results(db_session):
    """Test that web_search tool returns formatted results."""
    mock_results = [
        SearchResult(
            title="Test Result",
            url="https://example.com",
            snippet="Test snippet",
            published_date=None,
        )
    ]

    with patch(
        "backend.services.search_service.SearchService.search_web", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = mock_results

        service = AgentToolService(db_session)
        result_raw = await service.execute(
            "web_search",
            {"query": "test query", "max_results": 5},
            chat_session_id="chat-1",
            workspace_root=None,
        )

        result = json.loads(result_raw)
        assert result["count"] == 1
        assert result["results"][0]["title"] == "Test Result"
        assert result["results"][0]["url"] == "https://example.com"
        assert result["query"] == "test query"
        mock_search.assert_called_once_with(
            query="test query",
            max_results=5,
            country="CN",
            search_lang="zh-hans",
            freshness=None,
        )


async def test_web_search_handles_empty_results(db_session):
    """Test that web_search handles empty results gracefully."""
    with patch(
        "backend.services.search_service.SearchService.search_web", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = []

        service = AgentToolService(db_session)
        result_raw = await service.execute(
            "web_search",
            {"query": "no results"},
            chat_session_id="chat-1",
            workspace_root=None,
        )

        result = json.loads(result_raw)
        assert result["results"] == []
        assert result["count"] == 0
        assert "No search results" in result["message"]


async def test_web_search_requires_query(db_session):
    """Test that web_search requires a query parameter."""
    service = AgentToolService(db_session)

    with pytest.raises(ToolExecutionError, match="query.*required"):
        await service.execute(
            "web_search",
            {},
            chat_session_id="chat-1",
            workspace_root=None,
        )


async def test_web_search_handles_api_error(db_session):
    """Test that web_search handles API errors gracefully."""
    with patch(
        "backend.services.search_service.SearchService.search_web", new_callable=AsyncMock
    ) as mock_search:
        mock_search.side_effect = Exception("API Error")

        service = AgentToolService(db_session)
        result_raw = await service.execute(
            "web_search",
            {"query": "error test"},
            chat_session_id="chat-1",
            workspace_root=None,
        )

        result = json.loads(result_raw)
        assert result["results"] == []
        assert "Search failed" in result["message"]


async def test_web_search_with_custom_parameters(db_session):
    """Test that web_search passes custom parameters correctly."""
    mock_results = [
        SearchResult(
            title="Result 1",
            url="https://example.com/1",
            snippet="Snippet 1",
            published_date=None,
        ),
        SearchResult(
            title="Result 2",
            url="https://example.com/2",
            snippet="Snippet 2",
            published_date=None,
        ),
    ]

    with patch(
        "backend.services.search_service.SearchService.search_web", new_callable=AsyncMock
    ) as mock_search:
        mock_search.return_value = mock_results

        service = AgentToolService(db_session)
        result_raw = await service.execute(
            "web_search",
            {
                "query": "custom query",
                "max_results": 2,
                "country": "US",
                "search_lang": "en",
                "freshness": "pw",
            },
            chat_session_id="chat-1",
            workspace_root=None,
        )

        result = json.loads(result_raw)
        assert result["count"] == 2
        mock_search.assert_called_once_with(
            query="custom query",
            max_results=2,
            country="US",
            search_lang="en",
            freshness="pw",
        )
