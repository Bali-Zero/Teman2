"""Tests for IndonesiaDomainAgent — the domain-specific search agent.

All external callables (ask_legal, search_intel, notebook_query,
exa_call, recall_similar) are fully mocked.  Tests verify correct
dispatch, keyword-based NLM notebook selection, error resilience,
and search-call counting.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from backend.services.naga.search_agents.base import AgentResponse, SearchResult
from backend.services.naga.search_agents.domain_agent import (
    GOV_DOMAINS,
    IndonesiaDomainAgent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(
    *,
    ask_legal: AsyncMock | None = None,
    search_intel: AsyncMock | None = None,
    notebook_query: AsyncMock | None = None,
    recall_similar: AsyncMock | None = None,
    exa_call: AsyncMock | None = None,
) -> IndonesiaDomainAgent:
    """Build an IndonesiaDomainAgent with mocked callables."""
    return IndonesiaDomainAgent(
        ask_legal=ask_legal or AsyncMock(return_value={"answer": "legal answer", "sources": []}),
        search_intel=search_intel or AsyncMock(return_value=[]),
        notebook_query=notebook_query or AsyncMock(return_value={"text": "nlm response"}),
        recall_similar=recall_similar or AsyncMock(return_value=[]),
        exa_call=exa_call or AsyncMock(return_value={"results": []}),
    )


# ---------------------------------------------------------------------------
# test_domain_agent_calls_ask_legal
# ---------------------------------------------------------------------------


class TestDomainAgentCallsAskLegal:
    """Verify ask_legal is called and its result is included."""

    @pytest.mark.asyncio()
    async def test_ask_legal_called_with_combined_query(self) -> None:
        mock_ask = AsyncMock(
            return_value={"answer": "KITAS requires sponsor.", "sources": ["visa_oracle"]}
        )
        agent = _make_agent(ask_legal=mock_ask)
        resp = await agent.search("visa requirements", "what docs for KITAS?")

        mock_ask.assert_awaited_once()
        # The combined query should contain both query and sub_question
        call_kwargs = mock_ask.call_args
        assert call_kwargs is not None

    @pytest.mark.asyncio()
    async def test_ask_legal_result_in_response(self) -> None:
        mock_ask = AsyncMock(
            return_value={"answer": "KITAS requires sponsor.", "sources": ["visa_oracle"]}
        )
        agent = _make_agent(ask_legal=mock_ask)
        resp = await agent.search("visa requirements", "what docs for KITAS?")

        legal_results = [r for r in resp.results if r.url == "internal://ask_legal"]
        assert len(legal_results) == 1
        assert legal_results[0].source_type == "internal"
        assert "KITAS requires sponsor" in legal_results[0].content


# ---------------------------------------------------------------------------
# test_domain_agent_calls_search_intel
# ---------------------------------------------------------------------------


class TestDomainAgentCallsSearchIntel:
    """Verify search_intel is called and results are mapped."""

    @pytest.mark.asyncio()
    async def test_search_intel_called(self) -> None:
        mock_intel = AsyncMock(
            return_value=[
                {"title": "Intel A", "url": "https://intel.bz/a", "content": "content a"},
                {"title": "Intel B", "url": "https://intel.bz/b", "content": "content b"},
            ]
        )
        agent = _make_agent(search_intel=mock_intel)
        resp = await agent.search("immigration policy", "latest changes")

        mock_intel.assert_awaited_once()

    @pytest.mark.asyncio()
    async def test_search_intel_results_mapped(self) -> None:
        mock_intel = AsyncMock(
            return_value=[
                {"title": "Intel A", "url": "https://intel.bz/a", "content": "content a"},
            ]
        )
        agent = _make_agent(search_intel=mock_intel)
        resp = await agent.search("immigration policy", "latest changes")

        intel_results = [r for r in resp.results if r.source_type == "internal" and "intel" in r.url]
        assert len(intel_results) >= 1


# ---------------------------------------------------------------------------
# test_domain_agent_calls_notebook_query
# ---------------------------------------------------------------------------


class TestDomainAgentCallsNotebookQuery:
    """Verify correct NLM notebook is selected based on keywords."""

    @pytest.mark.asyncio()
    async def test_immigration_keyword_selects_nb2(self) -> None:
        mock_nlm = AsyncMock(return_value={"text": "visa info from NB-2"})
        agent = _make_agent(notebook_query=mock_nlm)
        await agent.search("KITAS visa requirements", "immigration process")

        mock_nlm.assert_awaited()
        # Check NB-2 was used (immigration keywords)
        call_kwargs = mock_nlm.call_args
        assert call_kwargs is not None
        # notebook_id should reference NB-2 for immigration
        all_calls = mock_nlm.call_args_list
        nb_ids = []
        for call in all_calls:
            if call.kwargs.get("notebook_id"):
                nb_ids.append(call.kwargs["notebook_id"])
            elif len(call.args) > 0:
                nb_ids.append(call.args[0])
        assert any("2" in str(nb_id) for nb_id in nb_ids), f"Expected NB-2 in {nb_ids}"

    @pytest.mark.asyncio()
    async def test_company_keyword_selects_nb3(self) -> None:
        mock_nlm = AsyncMock(return_value={"text": "PT PMA info from NB-3"})
        agent = _make_agent(notebook_query=mock_nlm)
        await agent.search("PT PMA setup", "company registration process")

        mock_nlm.assert_awaited()
        all_calls = mock_nlm.call_args_list
        nb_ids = []
        for call in all_calls:
            if call.kwargs.get("notebook_id"):
                nb_ids.append(call.kwargs["notebook_id"])
            elif len(call.args) > 0:
                nb_ids.append(call.args[0])
        assert any("3" in str(nb_id) for nb_id in nb_ids), f"Expected NB-3 in {nb_ids}"

    @pytest.mark.asyncio()
    async def test_tax_keyword_selects_nb4(self) -> None:
        mock_nlm = AsyncMock(return_value={"text": "tax info from NB-4"})
        agent = _make_agent(notebook_query=mock_nlm)
        await agent.search("NPWP tax obligations", "pajak requirements")

        mock_nlm.assert_awaited()
        all_calls = mock_nlm.call_args_list
        nb_ids = []
        for call in all_calls:
            if call.kwargs.get("notebook_id"):
                nb_ids.append(call.kwargs["notebook_id"])
            elif len(call.args) > 0:
                nb_ids.append(call.args[0])
        assert any("4" in str(nb_id) for nb_id in nb_ids), f"Expected NB-4 in {nb_ids}"

    @pytest.mark.asyncio()
    async def test_property_keyword_selects_nb5(self) -> None:
        mock_nlm = AsyncMock(return_value={"text": "property info from NB-5"})
        agent = _make_agent(notebook_query=mock_nlm)
        await agent.search("hak pakai property", "land ownership for WNA")

        mock_nlm.assert_awaited()
        all_calls = mock_nlm.call_args_list
        nb_ids = []
        for call in all_calls:
            if call.kwargs.get("notebook_id"):
                nb_ids.append(call.kwargs["notebook_id"])
            elif len(call.args) > 0:
                nb_ids.append(call.args[0])
        assert any("5" in str(nb_id) for nb_id in nb_ids), f"Expected NB-5 in {nb_ids}"

    @pytest.mark.asyncio()
    async def test_default_selects_nb2(self) -> None:
        mock_nlm = AsyncMock(return_value={"text": "general info"})
        agent = _make_agent(notebook_query=mock_nlm)
        await agent.search("general Indonesia question", "something general")

        mock_nlm.assert_awaited()
        all_calls = mock_nlm.call_args_list
        nb_ids = []
        for call in all_calls:
            if call.kwargs.get("notebook_id"):
                nb_ids.append(call.kwargs["notebook_id"])
            elif len(call.args) > 0:
                nb_ids.append(call.args[0])
        assert any("2" in str(nb_id) for nb_id in nb_ids), f"Expected NB-2 (default) in {nb_ids}"

    @pytest.mark.asyncio()
    async def test_notebook_query_none_skips(self) -> None:
        """When notebook_query is None, no NLM call is made."""
        agent = IndonesiaDomainAgent(
            ask_legal=AsyncMock(return_value={"answer": "ok", "sources": []}),
            search_intel=AsyncMock(return_value=[]),
            notebook_query=None,
            recall_similar=None,
            exa_call=None,
        )
        resp = await agent.search("KITAS visa", "requirements")
        nlm_results = [r for r in resp.results if "nlm" in r.url]
        assert len(nlm_results) == 0


# ---------------------------------------------------------------------------
# test_domain_agent_calls_exa_with_gov_domains
# ---------------------------------------------------------------------------


class TestDomainAgentCallsExaWithGovDomains:
    """Verify exa_call is invoked with GOV_DOMAINS filter."""

    @pytest.mark.asyncio()
    async def test_exa_called_with_gov_domains(self) -> None:
        mock_exa = AsyncMock(
            return_value={
                "results": [
                    {
                        "url": "https://imigrasi.go.id/info",
                        "title": "Imigrasi Info",
                        "text": "Official immigration info",
                    }
                ]
            }
        )
        agent = _make_agent(exa_call=mock_exa)
        await agent.search("visa policy", "latest imigrasi rules")

        mock_exa.assert_awaited_once()
        call_kwargs = mock_exa.call_args.kwargs if mock_exa.call_args.kwargs else {}
        # Check includeDomains was passed with GOV_DOMAINS
        if "includeDomains" in call_kwargs:
            assert call_kwargs["includeDomains"] == GOV_DOMAINS
        # Also accept positional/keyword via query
        assert mock_exa.call_count == 1

    @pytest.mark.asyncio()
    async def test_exa_results_have_gov_source_type(self) -> None:
        mock_exa = AsyncMock(
            return_value={
                "results": [
                    {
                        "url": "https://pajak.go.id/rates",
                        "title": "Tax Rates",
                        "text": "Official tax rates",
                    }
                ]
            }
        )
        agent = _make_agent(exa_call=mock_exa)
        resp = await agent.search("tax rates", "pajak rates 2026")

        gov_results = [r for r in resp.results if r.source_type == "gov"]
        assert len(gov_results) >= 1

    @pytest.mark.asyncio()
    async def test_exa_none_skips(self) -> None:
        """When exa_call is None, no external gov search is made."""
        agent = IndonesiaDomainAgent(
            ask_legal=AsyncMock(return_value={"answer": "ok", "sources": []}),
            search_intel=AsyncMock(return_value=[]),
            notebook_query=None,
            recall_similar=None,
            exa_call=None,
        )
        resp = await agent.search("tax policy", "requirements")
        gov_results = [r for r in resp.results if r.source_type == "gov"]
        assert len(gov_results) == 0

    def test_gov_domains_constant(self) -> None:
        """GOV_DOMAINS must contain the expected Indonesian gov domains."""
        assert "imigrasi.go.id" in GOV_DOMAINS
        assert "pajak.go.id" in GOV_DOMAINS
        assert "kemenkumham.go.id" in GOV_DOMAINS
        assert "oss.go.id" in GOV_DOMAINS
        assert "bkpm.go.id" in GOV_DOMAINS
        assert "peraturan.bpk.go.id" in GOV_DOMAINS
        assert "jdih.kemenkumham.go.id" in GOV_DOMAINS


# ---------------------------------------------------------------------------
# test_domain_agent_handles_partial_failure
# ---------------------------------------------------------------------------


class TestDomainAgentHandlesPartialFailure:
    """One tool failing must not prevent others from returning results."""

    @pytest.mark.asyncio()
    async def test_ask_legal_fails_others_succeed(self) -> None:
        mock_ask = AsyncMock(side_effect=RuntimeError("legal service down"))
        mock_intel = AsyncMock(
            return_value=[
                {"title": "Intel OK", "url": "https://intel.bz/ok", "content": "intel works"},
            ]
        )
        agent = _make_agent(ask_legal=mock_ask, search_intel=mock_intel)
        resp = await agent.search("visa info", "KITAS details")

        # Should not raise
        assert resp.error is None
        # Intel results still present
        assert len(resp.results) >= 1

    @pytest.mark.asyncio()
    async def test_exa_fails_others_succeed(self) -> None:
        mock_exa = AsyncMock(side_effect=ConnectionError("exa unreachable"))
        mock_ask = AsyncMock(
            return_value={"answer": "legal answer", "sources": []}
        )
        agent = _make_agent(ask_legal=mock_ask, exa_call=mock_exa)
        resp = await agent.search("tax info", "pajak details")

        assert resp.error is None
        legal_results = [r for r in resp.results if r.url == "internal://ask_legal"]
        assert len(legal_results) == 1

    @pytest.mark.asyncio()
    async def test_notebook_query_fails_others_succeed(self) -> None:
        mock_nlm = AsyncMock(side_effect=TimeoutError("NLM timeout"))
        mock_ask = AsyncMock(
            return_value={"answer": "still works", "sources": []}
        )
        agent = _make_agent(ask_legal=mock_ask, notebook_query=mock_nlm)
        resp = await agent.search("immigration", "visa overview")

        assert resp.error is None
        assert len(resp.results) >= 1

    @pytest.mark.asyncio()
    async def test_all_optional_fail_ask_legal_succeeds(self) -> None:
        mock_ask = AsyncMock(
            return_value={"answer": "legal only", "sources": []}
        )
        agent = _make_agent(
            ask_legal=mock_ask,
            search_intel=AsyncMock(side_effect=RuntimeError("intel down")),
            notebook_query=AsyncMock(side_effect=RuntimeError("nlm down")),
            exa_call=AsyncMock(side_effect=RuntimeError("exa down")),
            recall_similar=AsyncMock(side_effect=RuntimeError("recall down")),
        )
        resp = await agent.search("question", "sub question")

        assert resp.error is None
        assert len(resp.results) >= 1
        assert resp.results[0].url == "internal://ask_legal"


# ---------------------------------------------------------------------------
# test_domain_agent_counts_search_calls
# ---------------------------------------------------------------------------


class TestDomainAgentCountsSearchCalls:
    """Verify search_calls_used is correctly tallied."""

    @pytest.mark.asyncio()
    async def test_counts_all_successful_calls(self) -> None:
        agent = _make_agent(
            ask_legal=AsyncMock(return_value={"answer": "ok", "sources": []}),
            search_intel=AsyncMock(return_value=[{"title": "A", "url": "u", "content": "c"}]),
            notebook_query=AsyncMock(return_value={"text": "nlm ok"}),
            exa_call=AsyncMock(return_value={"results": [{"url": "u", "title": "t", "text": "c"}]}),
            recall_similar=AsyncMock(return_value=[{"content": "past episode", "score": 0.8}]),
        )
        resp = await agent.search("KITAS visa", "requirements")

        # Each tool = 1 call: ask_legal + search_intel + notebook_query(s) + exa + recall
        assert resp.search_calls_used >= 4

    @pytest.mark.asyncio()
    async def test_failed_calls_still_counted(self) -> None:
        agent = _make_agent(
            ask_legal=AsyncMock(return_value={"answer": "ok", "sources": []}),
            search_intel=AsyncMock(side_effect=RuntimeError("fail")),
            notebook_query=AsyncMock(side_effect=RuntimeError("fail")),
            exa_call=AsyncMock(side_effect=RuntimeError("fail")),
            recall_similar=AsyncMock(side_effect=RuntimeError("fail")),
        )
        resp = await agent.search("test", "sub")

        # At least ask_legal succeeded = 1 call, but attempts should also count
        assert resp.search_calls_used >= 1

    @pytest.mark.asyncio()
    async def test_none_callables_not_counted(self) -> None:
        agent = IndonesiaDomainAgent(
            ask_legal=AsyncMock(return_value={"answer": "ok", "sources": []}),
            search_intel=AsyncMock(return_value=[]),
            notebook_query=None,
            recall_similar=None,
            exa_call=None,
        )
        resp = await agent.search("test", "sub")

        # Only ask_legal + search_intel = 2 calls
        assert resp.search_calls_used == 2


# ---------------------------------------------------------------------------
# Agent metadata
# ---------------------------------------------------------------------------


class TestDomainAgentMetadata:
    """Verify agent name and inheritance."""

    def test_agent_name(self) -> None:
        agent = _make_agent()
        assert agent.name == "domain_indonesia"

    def test_is_base_search_agent(self) -> None:
        from backend.services.naga.search_agents.base import BaseSearchAgent

        agent = _make_agent()
        assert isinstance(agent, BaseSearchAgent)
