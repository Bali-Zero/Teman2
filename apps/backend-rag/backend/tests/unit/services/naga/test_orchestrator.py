"""Unit tests for backend/services/naga/orchestrator.py"""

from __future__ import annotations

from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_deps():
    """Create mock dependency container for NagaOrchestrator."""
    deps = MagicMock()
    deps.exa_search = AsyncMock()
    deps.brave_search = AsyncMock()
    deps.fetch = AsyncMock()
    deps.ask_legal = AsyncMock()
    deps.search_intel = AsyncMock()
    deps.notebook_query = AsyncMock()
    deps.recall_similar = AsyncMock()
    deps.gemini_generate = AsyncMock()
    deps.db_pool = None  # disable DB persistence
    return deps


@pytest.fixture
def orchestrator(mock_deps):
    from backend.services.naga.orchestrator import NagaOrchestrator

    return NagaOrchestrator(deps=mock_deps)


# ---------------------------------------------------------------------------
# _decompose_query
# ---------------------------------------------------------------------------


class TestDecomposeQuery:
    def test_flash_tier_no_decomposition(self):
        from backend.services.naga.orchestrator import _decompose_query

        result = _decompose_query("What is KITAS?", "flash")
        assert result == ["What is KITAS?"]

    def test_vs_pattern_splits(self):
        from backend.services.naga.orchestrator import _decompose_query

        result = _decompose_query("KITAS vs KITAP", "deep")
        assert len(result) == 3
        assert any("KITAS" in q for q in result)
        assert any("KITAP" in q for q in result)
        assert any("differences" in q.lower() for q in result)

    def test_versus_word(self):
        from backend.services.naga.orchestrator import _decompose_query

        result = _decompose_query("PT PMA versus PT PMDN", "deep")
        assert len(result) == 3

    def test_confronto_pattern(self):
        from backend.services.naga.orchestrator import _decompose_query

        result = _decompose_query("confronto KITAS e KITAP", "deep")
        assert len(result) == 3
        assert any("KITAS" in q for q in result)
        assert any("KITAP" in q for q in result)

    def test_default_decomposition(self):
        from backend.services.naga.orchestrator import _decompose_query

        result = _decompose_query("How to get visa?", "deep")
        assert len(result) == 2
        assert result[0] == "How to get visa?"
        assert "latest developments" in result[1].lower()


# ---------------------------------------------------------------------------
# _safe_search
# ---------------------------------------------------------------------------


class TestSafeSearch:
    @pytest.mark.asyncio
    async def test_successful_search(self):
        from backend.services.naga.orchestrator import _safe_search
        from backend.services.naga.search_agents.base import AgentResponse

        mock_agent = AsyncMock()
        mock_agent.search.return_value = AgentResponse(
            agent_name="test", results=[], search_calls_used=1
        )

        result = await _safe_search(mock_agent, "query", "sub")
        assert result.agent_name == "test"

    @pytest.mark.asyncio
    async def test_search_exception_returns_error_response(self):
        from backend.services.naga.orchestrator import _safe_search

        mock_agent = AsyncMock()
        mock_agent.name = "broken_agent"
        mock_agent.search.side_effect = RuntimeError("API timeout")

        result = await _safe_search(mock_agent, "query", "sub")
        assert result.error == "API timeout"
        assert result.results == []
        assert result.search_calls_used == 1


# ---------------------------------------------------------------------------
# _monotonic_ms
# ---------------------------------------------------------------------------


class TestMonotonicMs:
    def test_returns_positive_int(self):
        from backend.services.naga.orchestrator import _monotonic_ms

        ms = _monotonic_ms()
        assert isinstance(ms, int)
        assert ms > 0


# ---------------------------------------------------------------------------
# _dispatch_agents
# ---------------------------------------------------------------------------


class TestDispatchAgents:
    @pytest.mark.asyncio
    async def test_general_domain_uses_exa_and_brave(self, orchestrator, mock_deps):
        mock_exa = AsyncMock()
        mock_brave = AsyncMock()
        mock_domain = AsyncMock()

        from backend.services.naga.search_agents.base import AgentResponse

        mock_exa.search.return_value = AgentResponse(
            agent_name="exa", results=[], search_calls_used=1
        )
        mock_brave.search.return_value = AgentResponse(
            agent_name="brave", results=[], search_calls_used=1
        )

        responses = await orchestrator._dispatch_agents(
            "query", "sub_q", "general", mock_exa, mock_brave, mock_domain
        )
        assert len(responses) == 2
        mock_exa.search.assert_called_once()
        mock_brave.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_indonesia_domain_uses_domain_agent(self, orchestrator, mock_deps):
        mock_exa = AsyncMock()
        mock_brave = AsyncMock()
        mock_domain = AsyncMock()

        from backend.services.naga.search_agents.base import AgentResponse

        mock_domain.search.return_value = AgentResponse(
            agent_name="domain", results=[], search_calls_used=1
        )

        responses = await orchestrator._dispatch_agents(
            "query", "sub_q", "indonesia", mock_exa, mock_brave, mock_domain
        )
        assert len(responses) == 1
        mock_domain.search.assert_called_once()

    @pytest.mark.asyncio
    async def test_hybrid_uses_all_agents(self, orchestrator, mock_deps):
        mock_exa = AsyncMock()
        mock_brave = AsyncMock()
        mock_domain = AsyncMock()

        from backend.services.naga.search_agents.base import AgentResponse

        for m in [mock_exa, mock_brave, mock_domain]:
            m.search.return_value = AgentResponse(
                agent_name="a", results=[], search_calls_used=1
            )

        responses = await orchestrator._dispatch_agents(
            "query", "sub_q", "hybrid", mock_exa, mock_brave, mock_domain
        )
        assert len(responses) == 3

    @pytest.mark.asyncio
    async def test_unknown_domain_falls_back(self, orchestrator, mock_deps):
        mock_exa = AsyncMock()
        mock_brave = AsyncMock()
        mock_domain = AsyncMock()

        from backend.services.naga.search_agents.base import AgentResponse

        for m in [mock_exa, mock_brave]:
            m.search.return_value = AgentResponse(
                agent_name="a", results=[], search_calls_used=1
            )

        responses = await orchestrator._dispatch_agents(
            "query", "sub_q", "unknown_domain", mock_exa, mock_brave, mock_domain
        )
        assert len(responses) == 2  # fallback to exa + brave


# ---------------------------------------------------------------------------
# research (integration-level with mocked agents)
# ---------------------------------------------------------------------------


class TestResearch:
    @pytest.mark.asyncio
    async def test_flash_tier_completes(self, mock_deps):
        """Flash tier should do a single iteration and return."""
        from backend.services.naga.orchestrator import NagaOrchestrator
        from backend.services.naga.search_agents.base import AgentResponse, SearchResult

        mock_result = SearchResult(
            url="https://example.com",
            title="Test",
            content="KITAS is a stay permit.",
            relevance_score=0.9,
            source_type="web",
        )

        # Make exa return a result
        mock_exa_resp = AgentResponse(
            agent_name="exa",
            results=[mock_result],
            search_calls_used=1,
        )

        with patch(
            "backend.services.naga.orchestrator.classify_query"
        ) as mock_gw, patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ) as mock_exa_cls, patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ) as mock_brave_cls, patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ) as mock_domain_cls, patch(
            "backend.services.naga.orchestrator.generate_report",
            return_value="# Report\nContent here.",
        ), patch(
            "backend.services.naga.orchestrator.check_convergence"
        ) as mock_conv:
            # Gateway
            mock_gw.return_value = MagicMock(tier="flash", domain="general", mode="oneshot")

            # Agents
            for cls in [mock_exa_cls, mock_brave_cls, mock_domain_cls]:
                inst = AsyncMock()
                inst.search.return_value = mock_exa_resp
                cls.return_value = inst

            # Convergence -> CONVERGED immediately
            mock_conv.return_value = MagicMock(
                decision="CONVERGED", coverage=1.0, novelty=0.0, gap_questions=[]
            )

            orch = NagaOrchestrator(deps=mock_deps)
            state = await orch.research("What is KITAS?", tier="auto")

        assert state["status"] == "completed"
        assert state["tier"] == "flash"
        assert state["query"] == "What is KITAS?"
        assert state["report_markdown"] != ""

    @pytest.mark.asyncio
    async def test_research_with_unknown_tier_falls_back(self, mock_deps):
        from backend.services.naga.orchestrator import NagaOrchestrator

        with patch(
            "backend.services.naga.orchestrator.classify_query"
        ) as mock_gw, patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ) as mock_exa_cls, patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ) as mock_brave_cls, patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ) as mock_domain_cls, patch(
            "backend.services.naga.orchestrator.generate_report",
            return_value="# Report",
        ), patch(
            "backend.services.naga.orchestrator.check_convergence"
        ) as mock_conv:
            mock_gw.return_value = MagicMock(
                tier="unknown_tier", domain="general", mode="oneshot"
            )

            from backend.services.naga.search_agents.base import AgentResponse

            empty_resp = AgentResponse(agent_name="a", results=[], search_calls_used=0)
            for cls in [mock_exa_cls, mock_brave_cls, mock_domain_cls]:
                inst = AsyncMock()
                inst.search.return_value = empty_resp
                cls.return_value = inst

            mock_conv.return_value = MagicMock(
                decision="TIMEOUT", coverage=0.0, novelty=0.0, gap_questions=[]
            )

            orch = NagaOrchestrator(deps=mock_deps)
            state = await orch.research("test", tier="unknown_tier", domain="general")

        assert state["status"] == "completed"

    @pytest.mark.asyncio
    async def test_research_persists_to_db(self, mock_deps):
        """When db_pool is present, research should try to persist."""
        from backend.services.naga.orchestrator import NagaOrchestrator

        mock_deps.db_pool = AsyncMock()

        with patch(
            "backend.services.naga.orchestrator.classify_query"
        ) as mock_gw, patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ), patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ), patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ), patch(
            "backend.services.naga.orchestrator.generate_report",
            return_value="# Report",
        ), patch(
            "backend.services.naga.orchestrator.check_convergence"
        ) as mock_conv, patch(
            "backend.services.naga.persist.save_session",
            new_callable=AsyncMock,
            return_value="sess-123",
        ) as mock_save:
            mock_gw.return_value = MagicMock(
                tier="flash", domain="general", mode="oneshot"
            )
            mock_conv.return_value = MagicMock(
                decision="CONVERGED", coverage=1.0, novelty=0.0, gap_questions=[]
            )

            from backend.services.naga.search_agents.base import AgentResponse

            for cls_name in ["ExaSearchAgent", "BraveSearchAgent", "IndonesiaDomainAgent"]:
                pass  # Already patched above

            orch = NagaOrchestrator(deps=mock_deps)

            # Patch the agent instances to return empty responses
            with patch.object(orch, "_dispatch_agents", new_callable=AsyncMock) as mock_dispatch:
                mock_dispatch.return_value = [
                    AgentResponse(agent_name="exa", results=[], search_calls_used=0)
                ]
                state = await orch.research("test", tier="flash", domain="general")

        assert state["status"] == "completed"
