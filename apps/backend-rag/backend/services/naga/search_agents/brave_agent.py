"""Brave Web Search agent for Naga research pipeline.

Uses the Brave Search API (via ``brave_call``) to query an independent web
index, then optionally fetches full page content for the top results via
``fetch_call``.  When content fetching fails for a given URL the agent
falls back to the snippet/description returned by Brave.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Coroutine

from backend.services.naga.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)

# Brave Web Search API hard limit
_BRAVE_MAX_COUNT = 20


class BraveSearchAgent(BaseSearchAgent):
    """Search agent backed by the Brave Web Search API.

    Parameters
    ----------
    brave_call:
        Async callable wrapping ``mcp__brave-search__brave_web_search``.
        Expected signature: ``(query: str, count: int) -> dict``.
    fetch_call:
        Async callable wrapping ``mcp__nuzantara-fetch__fetch``.
        Expected signature: ``(url: str, max_length: int) -> str``.
    """

    name: str = "brave"

    def __init__(
        self,
        brave_call: Callable[..., Coroutine[Any, Any, dict]],
        fetch_call: Callable[..., Coroutine[Any, Any, str]],
    ) -> None:
        self._brave_call = brave_call
        self._fetch_call = fetch_call

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
        fetch_top_n: int = 5,
    ) -> AgentResponse:
        """Execute a Brave web search and return an :class:`AgentResponse`.

        Args:
            query: The top-level research question.
            sub_question: A focused sub-question derived from decomposition.
            max_results: Maximum number of results to request from Brave
                (capped at 20).
            fetch_top_n: Number of top results whose full page content
                should be fetched.

        Returns:
            An :class:`AgentResponse` with mapped :class:`SearchResult` items.
        """
        combined_query = f"{query} {sub_question}".strip()
        count = min(max_results, _BRAVE_MAX_COUNT)

        try:
            raw = await self._brave_call(query=combined_query, count=count)
        except Exception as exc:
            logger.warning("Brave search failed: %s", exc)
            return AgentResponse(
                agent_name=self.name,
                error=f"Brave search error: {exc}",
            )

        web_section = raw.get("web")
        if web_section is None:
            logger.warning("Brave response missing 'web' key: %s", list(raw.keys()))
            return AgentResponse(
                agent_name=self.name,
                error="Brave response missing 'web' key",
            )

        brave_results: list[dict] = web_section.get("results", [])
        results: list[SearchResult] = []

        for idx, item in enumerate(brave_results):
            url: str = item.get("url", "")
            title: str = item.get("title", "")
            description: str = item.get("description", "")
            age: str | None = item.get("age")

            # Attempt to fetch full content for the top N results
            content = description
            if idx < fetch_top_n:
                content = await self._fetch_content(url, description)

            results.append(
                SearchResult(
                    url=url,
                    title=title,
                    content=content,
                    source_type="web",
                    metadata={"age": age, "agent": "brave"},
                )
            )

        logger.info(
            "Brave agent returned %d results for query: %.80s",
            len(results),
            combined_query,
        )
        return AgentResponse(
            agent_name=self.name,
            results=results,
            search_calls_used=1,
        )

    async def _fetch_content(self, url: str, fallback: str) -> str:
        """Fetch full page content, falling back to *fallback* on failure."""
        try:
            body = await self._fetch_call(url=url, max_length=50000)
            if body:
                return body
            logger.debug("Empty fetch response for %s, using description", url)
            return fallback
        except Exception as exc:
            logger.debug("Fetch failed for %s: %s — using description", url, exc)
            return fallback
