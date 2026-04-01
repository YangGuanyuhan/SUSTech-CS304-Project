"""Agent-facing search tool."""

from __future__ import annotations

from backend.models.task import SearchResult
from backend.services.search_service import SearchService


async def search_web(query: str, max_results: int = 5) -> list[SearchResult]:
    """Search the web for structured results."""

    return await SearchService().search_web(query, max_results)
