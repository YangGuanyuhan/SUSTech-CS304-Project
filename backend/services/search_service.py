"""Search provider service."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import httpx

from backend.config import get_settings
from backend.models.task import SearchResult
from backend.services.runtime_settings import runtime_settings

logger = logging.getLogger(__name__)


class SearchService:
    """Search wrapper with provider selection and timeout handling."""

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
        """Search the web using the configured search provider.

        Args:
            query: Search keywords
            max_results: Maximum number of results to return (1-10)
            country: Country preference (CN, US, JP, etc.)
            search_lang: Search language (zh-hans, en, etc.)
            freshness: Time filter (pd=today, pw=this week, pm=this month, py=this year)

        Returns:
            List of SearchResult objects
        """
        provider = runtime_settings.get_search_config().provider
        if provider == "mock":
            now = datetime.now(UTC)
            return [
                SearchResult(
                    title=f"Mock result for {query}",
                    url="https://example.com/mock-result",
                    snippet=f"Generated mock search result for query: {query}",
                    published_date=now,
                )
            ][:max_results]

        if provider == "bocha":
            return await self._search_bocha(
                query=query,
                max_results=max_results,
                freshness=freshness,
            )

        return await self._search_brave(
            query=query,
            max_results=max_results,
            country=country,
            search_lang=search_lang,
            freshness=freshness,
        )

    async def _search_brave(
        self,
        *,
        query: str,
        max_results: int,
        country: str,
        search_lang: str,
        freshness: str | None,
    ) -> list[SearchResult]:
        """Search using Brave Search API."""
        api_key = runtime_settings.get_secret_search_api_key("brave")
        if not api_key:
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

            async with httpx.AsyncClient(timeout=runtime_settings.get_search_timeout()) as client:
                response = await client.get(
                    "https://api.search.brave.com/res/v1/web/search",
                    params=params,
                    headers={
                        "Accept": "application/json",
                        "Accept-Encoding": "gzip",
                        "X-Subscription-Token": api_key,
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

    async def _search_bocha(
        self,
        *,
        query: str,
        max_results: int,
        freshness: str | None,
    ) -> list[SearchResult]:
        """Search using Bocha AI Search API."""
        api_key = runtime_settings.get_secret_search_api_key("bocha")
        if not api_key:
            logger.warning("BOCHA_API_KEY not configured, returning empty results")
            return []

        freshness_map = {
            "pd": "oneDay",
            "pw": "oneWeek",
            "pm": "oneMonth",
            "py": "oneYear",
        }
        payload: dict[str, object] = {
            "query": query,
            "summary": True,
            "count": min(max_results, 10),
        }
        if freshness:
            payload["freshness"] = freshness_map.get(freshness, freshness)

        try:
            async with httpx.AsyncClient(timeout=runtime_settings.get_search_timeout()) as client:
                response = await client.post(
                    "https://api.bochaai.com/v1/web-search",
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                )
                response.raise_for_status()
                response_payload = response.json()
        except httpx.TimeoutException:
            logger.error("Bocha Search API timeout")
            return []
        except httpx.HTTPStatusError as e:
            logger.error(f"Bocha Search API error: {e.response.status_code}")
            return []
        except httpx.HTTPError as e:
            logger.error(f"Bocha Search HTTP error: {e}")
            return []
        except Exception as e:
            logger.error(f"Bocha Search unexpected error: {e}")
            return []

        result_items = response_payload.get("data", {}).get("webPages", {}).get("value", [])
        results = []
        for item in result_items:
            published = item.get("datePublished") or item.get("dateLastCrawled")
            published_date = None
            if published:
                try:
                    published_date = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    published_date = None
            results.append(
                SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("summary") or item.get("snippet") or "",
                    published_date=published_date,
                )
            )
        return results[:max_results]
