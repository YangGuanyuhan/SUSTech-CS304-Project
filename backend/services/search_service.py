"""Search provider service."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from backend.config import get_settings
from backend.models.task import SearchResult


class SearchService:
    """Search wrapper with mock-first behavior and timeout handling."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_web(self, query: str, max_results: int = 5) -> list[SearchResult]:
        if self.settings.search_provider == "mock":
            now = datetime.now(timezone.utc)
            return [
                SearchResult(
                    title=f"Mock result for {query}",
                    url="https://example.com/mock-result",
                    snippet=f"Generated mock search result for query: {query}",
                    published_date=now,
                )
            ][:max_results]

        try:
            async with httpx.AsyncClient(timeout=self.settings.search_timeout) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params={"q": query, "count": max_results},
                    headers={"X-Subscription-Token": self.settings.brave_api_key or ""},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, httpx.TimeoutException):
            return []

        results = []
        for item in payload.get("web", {}).get("results", []):
            published = item.get("page_age")
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("description", ""),
                    published_date=datetime.fromisoformat(published) if published else None,
                )
            )
        return results[:max_results]
