"""Exa neural semantic search agent.

Uses a callable ``mcp_call`` (wrapping the Exa MCP tool
``mcp__exa__web_search_advanced_exa``) to perform neural / keyword /
auto searches and maps the results to :class:`SearchResult` objects.
"""

from __future__ import annotations

import logging
from typing import Callable

from backend.services.naga.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

logger = logging.getLogger(__name__)


class ExaSearchAgent(BaseSearchAgent):
    """Exa neural search agent.

    Parameters
    ----------
    mcp_call:
        An async callable that wraps the Exa MCP tool.  In production this
        is ``mcp__exa__web_search_advanced_exa``; in tests it is mocked.
    """

    name: str = "exa"

    def __init__(self, mcp_call: Callable) -> None:  # noqa: ANN401
        self._mcp_call = mcp_call

    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
        include_domains: list[str] | None = None,
        exclude_domains: list[str] | None = None,
        search_type: str = "neural",
    ) -> AgentResponse:
        """Execute an Exa search combining *query* and *sub_question*.

        Args:
            query: The top-level research question.
            sub_question: A focused sub-question from decomposition.
            max_results: Maximum number of results to return.
            include_domains: Optional allowlist of domains.
            exclude_domains: Optional blocklist of domains.
            search_type: One of ``neural``, ``keyword``, or ``auto``.

        Returns:
            An :class:`AgentResponse` with mapped results or an error.
        """
        combined_query = f"{query} — {sub_question}"

        kwargs: dict = {
            "query": combined_query,
            "numResults": max_results,
            "type": search_type,
        }
        if include_domains:
            kwargs["includeDomains"] = include_domains
        if exclude_domains:
            kwargs["excludeDomains"] = exclude_domains

        try:
            raw_response = await self._mcp_call(**kwargs)
            results = self._map_results(raw_response)
            return AgentResponse(
                agent_name=self.name,
                results=results,
                search_calls_used=1,
            )
        except Exception as exc:
            logger.warning("Exa search failed: %s", exc)
            return AgentResponse(
                agent_name=self.name,
                results=[],
                search_calls_used=1,
                error=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _map_results(raw_response: dict) -> list[SearchResult]:
        """Convert Exa API results to :class:`SearchResult` objects."""
        results: list[SearchResult] = []
        for item in raw_response.get("results", []):
            metadata: dict = {}
            if item.get("highlights"):
                metadata["highlights"] = item["highlights"]
            if item.get("summary"):
                metadata["summary"] = item["summary"]

            results.append(
                SearchResult(
                    url=item.get("url", ""),
                    title=item.get("title", ""),
                    content=item.get("text", ""),
                    relevance_score=float(item.get("score", 0.0)),
                    source_type="web",
                    metadata=metadata,
                )
            )
        return results
