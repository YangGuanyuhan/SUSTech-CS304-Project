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
from backend.services.runtime_settings import RuntimeSearchConfig
from backend.services.search_service import SearchService


def test_web_search_tool_not_registered_without_api_key():
    """Test that web_search tool is NOT registered when BRAVE_API_KEY is not set."""
    with (
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_config",
            return_value=RuntimeSearchConfig(
                provider="brave", api_key_configured=False, timeout=30
            ),
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_secret_search_api_key",
            return_value=None,
        ),
    ):
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" not in tool_names


def test_web_search_tool_not_registered_with_empty_api_key():
    """Test that web_search tool is NOT registered when BRAVE_API_KEY is empty string."""
    with (
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_config",
            return_value=RuntimeSearchConfig(
                provider="brave", api_key_configured=False, timeout=30
            ),
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_secret_search_api_key",
            return_value="",
        ),
    ):
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" not in tool_names


def test_web_search_tool_registered_with_api_key():
    """Test that web_search tool IS registered when BRAVE_API_KEY is set."""
    with (
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_config",
            return_value=RuntimeSearchConfig(provider="brave", api_key_configured=True, timeout=30),
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_secret_search_api_key",
            return_value="BSA-test-key",
        ),
    ):
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" in tool_names

        # Verify tool definition structure
        web_search_tool = next(t for t in tools if t["function"]["name"] == "web_search")
        assert web_search_tool["type"] == "function"
        assert "query" in web_search_tool["function"]["parameters"]["properties"]
        assert "query" in web_search_tool["function"]["parameters"]["required"]


def test_web_search_tool_registered_with_bocha_api_key():
    """Test that web_search tool is registered when Bocha is configured."""
    with (
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_config",
            return_value=RuntimeSearchConfig(provider="bocha", api_key_configured=True, timeout=30),
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_secret_search_api_key",
            return_value="sk-test-key",
        ),
    ):
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" in tool_names


def test_web_search_tool_registered_with_mock_provider():
    """Test that mock provider registers web_search without a real API key."""
    with patch(
        "backend.services.runtime_settings.runtime_settings.get_search_config",
        return_value=RuntimeSearchConfig(provider="mock", api_key_configured=True, timeout=30),
    ):
        tools = get_tool_definitions()
        tool_names = [t["function"]["name"] for t in tools]
        assert "web_search" in tool_names


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


async def test_search_service_bocha_provider_parses_results():
    """Test that Bocha provider calls the expected endpoint and parses results."""
    settings = SimpleNamespace(
        search_provider="bocha",
        bocha_api_key="sk-test-key",
        search_timeout=30,
    )
    payload = {
        "data": {
            "webPages": {
                "value": [
                    {
                        "name": "Bocha Result",
                        "url": "https://example.com/bocha",
                        "summary": "Bocha summary",
                        "datePublished": "2026-05-16T10:00:00Z",
                    }
                ]
            }
        }
    }

    class MockResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return payload

    class MockClient:
        def __init__(self, timeout):
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, json, headers):
            assert url == "https://api.bochaai.com/v1/web-search"
            assert json["query"] == "bocha query"
            assert json["count"] == 2
            assert json["freshness"] == "oneWeek"
            assert headers["Authorization"] == "Bearer sk-test-key"
            return MockResponse()

    with (
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_config",
            return_value=RuntimeSearchConfig(provider="bocha", api_key_configured=True, timeout=30),
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_secret_search_api_key",
            return_value=settings.bocha_api_key,
        ),
        patch(
            "backend.services.runtime_settings.runtime_settings.get_search_timeout", return_value=30
        ),
        patch("httpx.AsyncClient", MockClient),
    ):
        results = await SearchService().search_web(
            query="bocha query",
            max_results=2,
            freshness="pw",
        )

    assert len(results) == 1
    assert results[0].title == "Bocha Result"
    assert results[0].url == "https://example.com/bocha"
    assert results[0].snippet == "Bocha summary"
