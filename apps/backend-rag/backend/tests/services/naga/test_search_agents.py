"""Tests for Naga search agents base types."""

from datetime import date

import pytest

from backend.services.naga.search_agents.base import (
    AgentResponse,
    BaseSearchAgent,
    SearchResult,
)

# ---------------------------------------------------------------------------
# SearchResult dataclass
# ---------------------------------------------------------------------------


class TestSearchResult:
    """Verify SearchResult dataclass construction and defaults."""

    def test_creation_with_all_fields(self) -> None:
        result = SearchResult(
            url="https://pajak.go.id/info",
            title="Tax Info",
            content="Indonesian tax regulations overview.",
            relevance_score=0.85,
            source_type="gov",
            freshness_date=date(2026, 4, 1),
            metadata={"language": "id", "region": "bali"},
        )
        assert result.url == "https://pajak.go.id/info"
        assert result.title == "Tax Info"
        assert result.content == "Indonesian tax regulations overview."
        assert result.relevance_score == 0.85
        assert result.source_type == "gov"
        assert result.freshness_date == date(2026, 4, 1)
        assert result.metadata == {"language": "id", "region": "bali"}

    def test_defaults_relevance_zero(self) -> None:
        result = SearchResult(
            url="https://example.com",
            title="Example",
            content="Body text.",
        )
        assert result.relevance_score == 0.0

    def test_defaults_source_type_none(self) -> None:
        result = SearchResult(
            url="https://example.com",
            title="Example",
            content="Body text.",
        )
        assert result.source_type is None

    def test_defaults_freshness_date_none(self) -> None:
        result = SearchResult(
            url="https://example.com",
            title="Example",
            content="Body text.",
        )
        assert result.freshness_date is None

    def test_defaults_metadata_empty_dict(self) -> None:
        result = SearchResult(
            url="https://example.com",
            title="Example",
            content="Body text.",
        )
        assert result.metadata == {}

    def test_metadata_default_not_shared(self) -> None:
        """Each instance must get its own dict, not a shared mutable default."""
        r1 = SearchResult(url="https://a.com", title="A", content="a")
        r2 = SearchResult(url="https://b.com", title="B", content="b")
        r1.metadata["key"] = "value"
        assert "key" not in r2.metadata


# ---------------------------------------------------------------------------
# AgentResponse dataclass
# ---------------------------------------------------------------------------


class TestAgentResponse:
    """Verify AgentResponse construction and defaults."""

    def test_creation(self) -> None:
        resp = AgentResponse(agent_name="exa", search_calls_used=3)
        assert resp.agent_name == "exa"
        assert resp.search_calls_used == 3
        assert resp.results == []
        assert resp.error is None

    def test_results_default_not_shared(self) -> None:
        r1 = AgentResponse(agent_name="a")
        r2 = AgentResponse(agent_name="b")
        r1.results.append(
            SearchResult(url="https://x.com", title="X", content="x")
        )
        assert len(r2.results) == 0


# ---------------------------------------------------------------------------
# AgentResponse.merge
# ---------------------------------------------------------------------------


class TestAgentResponseMerge:
    """Verify merge deduplication, summing, and ordering."""

    @pytest.fixture()
    def result_a(self) -> SearchResult:
        return SearchResult(
            url="https://a.com",
            title="First A",
            content="Content A",
            relevance_score=0.9,
        )

    @pytest.fixture()
    def result_b(self) -> SearchResult:
        return SearchResult(
            url="https://b.com",
            title="Result B",
            content="Content B",
            relevance_score=0.7,
        )

    @pytest.fixture()
    def result_a_duplicate(self) -> SearchResult:
        """Same URL as result_a but different title/content."""
        return SearchResult(
            url="https://a.com",
            title="Duplicate A",
            content="Different content A",
            relevance_score=0.5,
        )

    def test_merge_deduplicates_by_url(
        self,
        result_a: SearchResult,
        result_b: SearchResult,
        result_a_duplicate: SearchResult,
    ) -> None:
        resp1 = AgentResponse(
            agent_name="exa",
            results=[result_a, result_b],
            search_calls_used=2,
        )
        resp2 = AgentResponse(
            agent_name="brave",
            results=[result_a_duplicate],
            search_calls_used=1,
        )
        merged = AgentResponse.merge([resp1, resp2])
        urls = [r.url for r in merged.results]
        assert urls == ["https://a.com", "https://b.com"]

    def test_merge_preserves_first_occurrence(
        self,
        result_a: SearchResult,
        result_a_duplicate: SearchResult,
    ) -> None:
        resp1 = AgentResponse(
            agent_name="exa",
            results=[result_a],
            search_calls_used=1,
        )
        resp2 = AgentResponse(
            agent_name="brave",
            results=[result_a_duplicate],
            search_calls_used=1,
        )
        merged = AgentResponse.merge([resp1, resp2])
        assert merged.results[0].title == "First A"
        assert merged.results[0].relevance_score == 0.9

    def test_merge_sums_search_calls(
        self,
        result_a: SearchResult,
        result_b: SearchResult,
    ) -> None:
        resp1 = AgentResponse(
            agent_name="exa",
            results=[result_a],
            search_calls_used=3,
        )
        resp2 = AgentResponse(
            agent_name="brave",
            results=[result_b],
            search_calls_used=5,
        )
        merged = AgentResponse.merge([resp1, resp2])
        assert merged.search_calls_used == 8

    def test_merge_sets_agent_name_merged(
        self,
        result_a: SearchResult,
    ) -> None:
        resp = AgentResponse(
            agent_name="exa",
            results=[result_a],
            search_calls_used=1,
        )
        merged = AgentResponse.merge([resp])
        assert merged.agent_name == "merged"

    def test_merge_handles_empty_list(self) -> None:
        merged = AgentResponse.merge([])
        assert merged.agent_name == "merged"
        assert merged.results == []
        assert merged.search_calls_used == 0
        assert merged.error is None

    def test_merge_handles_responses_with_empty_results(self) -> None:
        resp1 = AgentResponse(agent_name="exa", search_calls_used=2)
        resp2 = AgentResponse(agent_name="brave", search_calls_used=1)
        merged = AgentResponse.merge([resp1, resp2])
        assert merged.results == []
        assert merged.search_calls_used == 3

    def test_merge_handles_responses_with_errors(
        self,
        result_a: SearchResult,
    ) -> None:
        resp1 = AgentResponse(
            agent_name="exa",
            results=[result_a],
            search_calls_used=1,
        )
        resp2 = AgentResponse(
            agent_name="brave",
            search_calls_used=0,
            error="Rate limit exceeded",
        )
        merged = AgentResponse.merge([resp1, resp2])
        assert len(merged.results) == 1
        assert merged.search_calls_used == 1


# ---------------------------------------------------------------------------
# BaseSearchAgent ABC
# ---------------------------------------------------------------------------


class TestBaseSearchAgent:
    """Verify BaseSearchAgent is abstract and cannot be instantiated."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseSearchAgent()  # type: ignore[abstract]

    def test_concrete_subclass_works(self) -> None:
        class StubAgent(BaseSearchAgent):
            name: str = "stub"

            async def search(
                self,
                query: str,
                sub_question: str,
                max_results: int = 10,
            ) -> AgentResponse:
                return AgentResponse(agent_name=self.name, search_calls_used=0)

        agent = StubAgent()
        assert agent.name == "stub"

    @pytest.mark.asyncio()
    async def test_concrete_subclass_search_returns_agent_response(self) -> None:
        class StubAgent(BaseSearchAgent):
            name: str = "stub"

            async def search(
                self,
                query: str,
                sub_question: str,
                max_results: int = 10,
            ) -> AgentResponse:
                return AgentResponse(
                    agent_name=self.name,
                    results=[
                        SearchResult(
                            url="https://stub.com",
                            title="Stub",
                            content="stub content",
                        )
                    ],
                    search_calls_used=1,
                )

        agent = StubAgent()
        response = await agent.search("test query", "sub question")
        assert isinstance(response, AgentResponse)
        assert len(response.results) == 1
        assert response.search_calls_used == 1
