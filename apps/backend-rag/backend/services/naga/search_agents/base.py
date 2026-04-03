"""Base types for all Naga search agents.

Every concrete agent (Exa, Brave, Domain, Academic) inherits from
:class:`BaseSearchAgent` and returns an :class:`AgentResponse` whose
results are :class:`SearchResult` dataclasses.

The orchestrator calls :meth:`AgentResponse.merge` to combine parallel
agent responses before passing them into the quality pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date


@dataclass
class SearchResult:
    """A single search result returned by any agent.

    Attributes:
        url: Canonical URL of the source page.
        title: Page / document title.
        content: Extracted text content (may be truncated).
        relevance_score: Agent-assigned relevance in ``[0, 1]``.
        source_type: Category tag — ``web``, ``gov``, ``academic``,
            ``internal``, or ``blog``.  ``None`` when unknown.
        freshness_date: Publication or last-modified date, if available.
        metadata: Arbitrary extra fields the agent wants to carry forward.
    """

    url: str
    title: str
    content: str
    relevance_score: float = 0.0
    source_type: str | None = None
    freshness_date: date | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class AgentResponse:
    """Container returned by every search agent.

    Attributes:
        agent_name: Identifier of the agent that produced this response.
        results: Ordered list of :class:`SearchResult` items.
        search_calls_used: Number of external API calls consumed.
        error: Human-readable error string if the agent failed.
    """

    agent_name: str
    results: list[SearchResult] = field(default_factory=list)
    search_calls_used: int = 0
    error: str | None = None

    @staticmethod
    def merge(responses: list[AgentResponse]) -> AgentResponse:
        """Merge multiple agent responses, deduplicating by URL.

        * First occurrence of a URL wins (preserves the earlier agent's
          copy).
        * ``search_calls_used`` is summed across all responses.
        * The returned ``agent_name`` is always ``"merged"``.
        """
        seen_urls: set[str] = set()
        merged_results: list[SearchResult] = []
        total_calls: int = 0

        for resp in responses:
            total_calls += resp.search_calls_used
            for result in resp.results:
                if result.url not in seen_urls:
                    seen_urls.add(result.url)
                    merged_results.append(result)

        return AgentResponse(
            agent_name="merged",
            results=merged_results,
            search_calls_used=total_calls,
        )


class BaseSearchAgent(ABC):
    """Abstract base for every Naga search agent.

    Concrete subclasses **must** override :pyattr:`name` and implement
    :meth:`search`.
    """

    name: str = "base"

    @abstractmethod
    async def search(
        self,
        query: str,
        sub_question: str,
        max_results: int = 10,
    ) -> AgentResponse:
        """Execute a search and return an :class:`AgentResponse`.

        Args:
            query: The top-level research question.
            sub_question: A focused sub-question derived from the
                decomposition step.
            max_results: Maximum number of results to return.
        """
        ...
