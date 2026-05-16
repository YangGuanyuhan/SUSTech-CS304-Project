"""Search provider service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from backend.config import get_settings
from backend.models.task import SearchResult

logger = logging.getLogger(__name__)


class SearchService:
    """Search wrapper with mock-first behavior and timeout handling."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search_web(
        self,
        query: str,
        max_results: int = 5,
        country: str = "CN",
        search_lang: str = "zh-hans",
        freshness: str | None = None,
    ) -> list[SearchResult]:
        """Search the web using Brave Search API.

        Args:
            query: Search keywords
            max_results: Maximum number of results to return (1-10)
            country: Country preference (CN, US, JP, etc.)
            search_lang: Search language (zh-hans, en, etc.)
            freshness: Time filter (pd=today, pw=this week, pm=this month, py=this year)

        Returns:
            List of SearchResult objects
        """
        if self.settings.search_provider == "mock":
            now = datetime.now(UTC)
            return [
                SearchResult(
                    title=f"Mock result for {query}",
                    url="https://example.com/mock-result",
                    snippet=f"Generated mock search result for query: {query}",
                    published_date=now,
                )
            ][:max_results]

        if not self.settings.brave_api_key:
            logger.warning("BRAVE_API_KEY not configured, returning empty results")
            return []

        try:
            params = {
                "q": query,
                "count": min(max_results, 20),
                "country": country,
                "search_lang": search_lang,
            }
            if freshness:
                params["freshness"] = freshness

            async with httpx.AsyncClient(timeout=self.settings.search_timeout) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": self.settings.brave_api_key,
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException:
            logger.error("Brave Search API timeout")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Brave Search API error: {e.response.status_code}")
            return []
        except httpx.HTTPError as e:
            logger.error(f"Brave Search HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Brave Search unexpected error: {e}")
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
