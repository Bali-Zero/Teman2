"""Tests for BraveSearchAgent — mocks both brave_call and fetch_call."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.naga.search_agents.base import AgentResponse, SearchResult
from backend.services.naga.search_agents.brave_agent import BraveSearchAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_brave_response(results: list[dict]) -> dict:
    """Build a minimal Brave Web Search API response dict."""
    return {"web": {"results": results}}


def _brave_result(
    url: str = "https://example.com",
    title: str = "Example",
    description: str = "A description.",
    age: str = "2 days ago",
) -> dict:
    return {"url": url, "title": title, "description": description, "age": age}


# ---------------------------------------------------------------------------
# test_brave_search_returns_results
# ---------------------------------------------------------------------------


class TestBraveSearchReturnsResults:
    """BraveSearchAgent maps Brave API results to SearchResult objects."""

    @pytest.mark.asyncio()
    async def test_maps_brave_results_to_search_results(self) -> None:
        brave_results = [
            _brave_result(
                url="https://imigrasi.go.id/kitas",
                title="KITAS Requirements",
                description="Official KITAS page.",
                age="1 day ago",
            ),
            _brave_result(
                url="https://pajak.go.id/npwp",
                title="NPWP Info",
                description="Tax ID information.",
                age="3 days ago",
            ),
        ]
        brave_call = AsyncMock(return_value=_make_brave_response(brave_results))
        fetch_call = AsyncMock(return_value="Full content of the page about KITAS.")

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(
            query="Indonesia visa requirements",
            sub_question="What documents are needed for KITAS?",
            max_results=10,
            fetch_top_n=5,
        )

        assert isinstance(response, AgentResponse)
        assert response.agent_name == "brave"
        assert response.error is None
        assert len(response.results) == 2
        assert response.search_calls_used == 1

        first = response.results[0]
        assert first.url == "https://imigrasi.go.id/kitas"
        assert first.title == "KITAS Requirements"
        assert first.source_type == "web"
        assert first.metadata.get("agent") == "brave"
        assert first.metadata.get("age") == "1 day ago"

    @pytest.mark.asyncio()
    async def test_caps_max_results_at_20(self) -> None:
        """Brave API allows max 20 results; agent enforces this."""
        brave_call = AsyncMock(return_value=_make_brave_response([]))
        fetch_call = AsyncMock()

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        await agent.search(
            query="test",
            sub_question="sub",
            max_results=50,
        )

        brave_call.assert_awaited_once()
        call_kwargs = brave_call.call_args
        # count should be capped at 20
        assert call_kwargs.kwargs.get("count", call_kwargs[1].get("count", None)) <= 20

    @pytest.mark.asyncio()
    async def test_combines_query_and_sub_question(self) -> None:
        brave_call = AsyncMock(return_value=_make_brave_response([]))
        fetch_call = AsyncMock()

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        await agent.search(
            query="Indonesia business",
            sub_question="PT PMA requirements",
        )

        call_args = brave_call.call_args
        sent_query = call_args.kwargs.get("query", call_args[0][0] if call_args[0] else None)
        assert "Indonesia business" in sent_query
        assert "PT PMA requirements" in sent_query


# ---------------------------------------------------------------------------
# test_brave_search_fetches_content
# ---------------------------------------------------------------------------


class TestBraveSearchFetchesContent:
    """Verify fetch_call is invoked for the top N results."""

    @pytest.mark.asyncio()
    async def test_fetch_called_for_top_n_results(self) -> None:
        brave_results = [
            _brave_result(url=f"https://example.com/{i}", title=f"Page {i}")
            for i in range(7)
        ]
        brave_call = AsyncMock(return_value=_make_brave_response(brave_results))
        fetch_call = AsyncMock(return_value="Fetched body content.")

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(
            query="test",
            sub_question="sub",
            max_results=10,
            fetch_top_n=3,
        )

        # fetch_call should be invoked exactly 3 times (fetch_top_n=3)
        assert fetch_call.await_count == 3
        # All 7 results should still be present
        assert len(response.results) == 7

        # The first 3 should have fetched content
        for i in range(3):
            assert response.results[i].content == "Fetched body content."

        # Results 4-7 should fall back to the Brave description
        for i in range(3, 7):
            assert response.results[i].content == "A description."

    @pytest.mark.asyncio()
    async def test_fetch_passes_url_and_max_length(self) -> None:
        brave_results = [_brave_result(url="https://target.com/page")]
        brave_call = AsyncMock(return_value=_make_brave_response(brave_results))
        fetch_call = AsyncMock(return_value="content")

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        await agent.search(
            query="q", sub_question="sq", max_results=5, fetch_top_n=5
        )

        fetch_call.assert_awaited_once()
        call_kwargs = fetch_call.call_args.kwargs
        assert call_kwargs["url"] == "https://target.com/page"
        assert call_kwargs["max_length"] == 50000


# ---------------------------------------------------------------------------
# test_brave_search_falls_back_to_description
# ---------------------------------------------------------------------------


class TestBraveSearchFallsBackToDescription:
    """When fetch_call fails, agent falls back to the Brave description."""

    @pytest.mark.asyncio()
    async def test_fetch_exception_falls_back_to_description(self) -> None:
        brave_results = [
            _brave_result(
                url="https://broken.com",
                title="Broken Page",
                description="Brave snippet for broken page.",
            ),
        ]
        brave_call = AsyncMock(return_value=_make_brave_response(brave_results))
        fetch_call = AsyncMock(side_effect=Exception("Connection timeout"))

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(
            query="test", sub_question="sub", fetch_top_n=5
        )

        assert response.error is None
        assert len(response.results) == 1
        assert response.results[0].content == "Brave snippet for broken page."

    @pytest.mark.asyncio()
    async def test_fetch_returns_empty_falls_back(self) -> None:
        """If fetch returns empty string, fall back to description."""
        brave_results = [
            _brave_result(
                url="https://empty.com",
                description="Brave snippet.",
            ),
        ]
        brave_call = AsyncMock(return_value=_make_brave_response(brave_results))
        fetch_call = AsyncMock(return_value="")

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(
            query="test", sub_question="sub", fetch_top_n=5
        )

        assert response.results[0].content == "Brave snippet."


# ---------------------------------------------------------------------------
# test_brave_search_handles_error
# ---------------------------------------------------------------------------


class TestBraveSearchHandlesError:
    """When brave_call itself fails, agent returns AgentResponse with error."""

    @pytest.mark.asyncio()
    async def test_brave_call_exception_returns_error_response(self) -> None:
        brave_call = AsyncMock(side_effect=RuntimeError("Brave API down"))
        fetch_call = AsyncMock()

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(
            query="test", sub_question="sub"
        )

        assert isinstance(response, AgentResponse)
        assert response.agent_name == "brave"
        assert response.error is not None
        assert "Brave API down" in response.error
        assert response.results == []
        assert response.search_calls_used == 0
        fetch_call.assert_not_awaited()

    @pytest.mark.asyncio()
    async def test_missing_web_key_returns_error(self) -> None:
        """If Brave response lacks the 'web' key, treat it as error."""
        brave_call = AsyncMock(return_value={"query": {"original": "test"}})
        fetch_call = AsyncMock()

        agent = BraveSearchAgent(brave_call=brave_call, fetch_call=fetch_call)
        response = await agent.search(query="test", sub_question="sub")

        assert response.error is not None
        assert response.results == []
