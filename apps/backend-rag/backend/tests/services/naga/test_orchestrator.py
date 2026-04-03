"""Tests for the NagaOrchestrator — Task 15.

All external dependencies (search agents, quality pipeline, synthesis,
claims extractor) are mocked.  Tests validate the orchestration logic:
classification, decomposition, budget enforcement, loop control, and
error resilience.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.claims.models import ClaimRecord
from backend.services.naga.orchestrator import (
    NagaOrchestrator,
    NagaResearchState,
    _decompose_query,
)
from backend.services.naga.quality.convergence import ConvergenceResult
from backend.services.naga.quality.crag_light import CragDecision
from backend.services.naga.search_agents.base import AgentResponse, SearchResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_deps(**overrides) -> MagicMock:
    """Create a mock deps object with all required callables."""
    deps = MagicMock()
    deps.exa_search = overrides.get("exa_search", AsyncMock())
    deps.brave_search = overrides.get("brave_search", AsyncMock())
    deps.fetch = overrides.get("fetch", AsyncMock(return_value="page body"))
    deps.ask_legal = overrides.get("ask_legal", AsyncMock(return_value={"answer": "legal info"}))
    deps.search_intel = overrides.get("search_intel", AsyncMock(return_value=[]))
    deps.notebook_query = overrides.get("notebook_query", AsyncMock(return_value={"text": ""}))
    deps.recall_similar = overrides.get("recall_similar", AsyncMock(return_value=[]))
    deps.gemini_generate = overrides.get("gemini_generate", AsyncMock(return_value={"text": "{}"}))
    return deps


def _make_search_result(url: str = "https://example.com/1", title: str = "Example") -> SearchResult:
    return SearchResult(
        url=url,
        title=title,
        content="Some content about KITAS visa requirements in Indonesia.",
        relevance_score=0.8,
        source_type="web",
    )


def _make_agent_response(
    n_results: int = 3,
    agent_name: str = "exa",
    calls: int = 1,
) -> AgentResponse:
    results = [
        _make_search_result(url=f"https://example.com/{i}", title=f"Result {i}")
        for i in range(n_results)
    ]
    return AgentResponse(
        agent_name=agent_name,
        results=results,
        search_calls_used=calls,
    )


def _make_claim(claim_id: str = "NB2-test0001", text: str = "KITAS requires passport") -> ClaimRecord:
    return ClaimRecord(
        claim_id=claim_id,
        claim_text=text,
        category="DOCUMENT_REQUIREMENT",
        confidence_class="VERIFIED",
        confidence_score=0.85,
        source_ids=["s0"],
        extracted="2026-04-03T00:00:00Z",
    )


# ---------------------------------------------------------------------------
# test_orchestrator_flash — quick search, no Gemini, returns report
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_flash() -> None:
    """Flash tier: single iteration, no Gemini bulk read, returns report."""
    deps = _make_deps()

    orch = NagaOrchestrator(deps)

    fake_response = _make_agent_response(n_results=2)

    with (
        patch(
            "backend.services.naga.orchestrator.ExaSearchAgent"
        ) as MockExa,
        patch(
            "backend.services.naga.orchestrator.BraveSearchAgent"
        ) as MockBrave,
        patch(
            "backend.services.naga.orchestrator.IndonesiaDomainAgent"
        ) as MockDomain,
        patch(
            "backend.services.naga.orchestrator.crag_evaluate"
        ) as mock_crag,
        patch(
            "backend.services.naga.orchestrator.check_convergence"
        ) as mock_conv,
        patch(
            "backend.services.naga.orchestrator.generate_report"
        ) as mock_report,
        patch(
            "backend.services.naga.orchestrator.extract_claims_from_response"
        ) as mock_claims,
    ):
        # Configure mocks
        MockExa.return_value.search = AsyncMock(return_value=fake_response)
        MockBrave.return_value.search = AsyncMock(return_value=fake_response)
        MockDomain.return_value.search = AsyncMock(return_value=fake_response)

        mock_crag.return_value = CragDecision(action="PASS", reason="ok", relevance_score=0.6)
        mock_conv.return_value = ConvergenceResult(
            decision="CONVERGED",
            reason="done",
            coverage=1.0,
            novelty=0.0,
            gap_questions=(),
        )
        mock_report.return_value = "**Flash report** — 2026-04-03\n\n- KITAS requires passport"
        mock_claims.return_value = [_make_claim()]

        result = await orch.research(
            query="What is KITAS?",
            tier="flash",
            domain="indonesia",
        )

    assert result["status"] == "completed"
    assert result["tier"] == "flash"
    assert result["report_markdown"] != ""
    assert result["iteration"] >= 1
    # Flash should NOT call gemini_bulk_read
    deps.gemini_generate.assert_not_awaited()


# ---------------------------------------------------------------------------
# test_orchestrator_deep — iterates, uses Gemini, extracts claims
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_deep() -> None:
    """Deep tier: multiple iterations possible, uses Gemini, extracts claims."""
    deps = _make_deps()

    orch = NagaOrchestrator(deps)

    fake_response = _make_agent_response(n_results=3)

    with (
        patch("backend.services.naga.orchestrator.ExaSearchAgent") as MockExa,
        patch("backend.services.naga.orchestrator.BraveSearchAgent") as MockBrave,
        patch("backend.services.naga.orchestrator.IndonesiaDomainAgent") as MockDomain,
        patch("backend.services.naga.orchestrator.crag_evaluate") as mock_crag,
        patch("backend.services.naga.orchestrator.check_convergence") as mock_conv,
        patch("backend.services.naga.orchestrator.score_sources") as mock_score,
        patch("backend.services.naga.orchestrator.gemini_bulk_read") as mock_gemini,
        patch("backend.services.naga.orchestrator.extract_claims_from_response") as mock_claims,
        patch("backend.services.naga.orchestrator.generate_report") as mock_report,
    ):
        MockExa.return_value.search = AsyncMock(return_value=fake_response)
        MockBrave.return_value.search = AsyncMock(return_value=fake_response)
        MockDomain.return_value.search = AsyncMock(return_value=fake_response)

        mock_crag.return_value = CragDecision(action="PASS", reason="ok", relevance_score=0.5)

        # Score sources returns the same sources with metadata
        scored = [_make_search_result(url=f"https://example.com/{i}") for i in range(3)]
        for s in scored:
            s.metadata["source_score"] = 0.7
        mock_score.return_value = scored

        # Gemini bulk read returns evidence
        evidence = {
            "sub_q_1": {
                "facts": [{"text": "KITAS requires passport", "source_ids": ["s0"], "confidence": 0.9}],
                "contradictions": [],
                "gaps": [],
                "data_points": [],
            },
        }
        mock_gemini.return_value = (evidence, "/tmp/naga/test/evidence.json")

        mock_claims.return_value = [_make_claim(), _make_claim(claim_id="NB2-test0002", text="Visa fee Rp 2M")]

        # First call: ITERATE, second: CONVERGED
        mock_conv.side_effect = [
            ConvergenceResult(
                decision="ITERATE",
                reason="need more",
                coverage=0.5,
                novelty=0.8,
                gap_questions=("sub_q_2",),
            ),
            ConvergenceResult(
                decision="CONVERGED",
                reason="done",
                coverage=1.0,
                novelty=0.05,
                gap_questions=(),
            ),
        ]

        mock_report.return_value = "# Research Report: KITAS analysis\n\nDetailed report."

        result = await orch.research(
            query="Analyze KITAS visa requirements for 2026",
            tier="deep",
            domain="indonesia",
        )

    assert result["status"] == "completed"
    assert result["tier"] == "deep"
    assert result["iteration"] >= 1
    assert result["claims_extracted"] >= 1
    assert result["evidence_map_uri"] != ""
    # Deep tier MUST call Gemini bulk read
    mock_gemini.assert_awaited()


# ---------------------------------------------------------------------------
# test_orchestrator_auto_classifies — tier="auto" triggers gateway
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_auto_classifies() -> None:
    """When tier="auto", the gateway is called to classify the query."""
    deps = _make_deps()
    orch = NagaOrchestrator(deps)

    fake_response = _make_agent_response(n_results=1)

    with (
        patch("backend.services.naga.orchestrator.classify_query") as mock_gw,
        patch("backend.services.naga.orchestrator.ExaSearchAgent") as MockExa,
        patch("backend.services.naga.orchestrator.BraveSearchAgent") as MockBrave,
        patch("backend.services.naga.orchestrator.IndonesiaDomainAgent") as MockDomain,
        patch("backend.services.naga.orchestrator.crag_evaluate") as mock_crag,
        patch("backend.services.naga.orchestrator.check_convergence") as mock_conv,
        patch("backend.services.naga.orchestrator.generate_report") as mock_report,
        patch("backend.services.naga.orchestrator.extract_claims_from_response") as mock_claims,
    ):
        from backend.services.naga.gateway import GatewayResult

        mock_gw.return_value = GatewayResult(
            tier="flash", domain="indonesia", mode="oneshot", ttl_seconds=30
        )

        MockExa.return_value.search = AsyncMock(return_value=fake_response)
        MockBrave.return_value.search = AsyncMock(return_value=fake_response)
        MockDomain.return_value.search = AsyncMock(return_value=fake_response)

        mock_crag.return_value = CragDecision(action="PASS", reason="ok", relevance_score=0.5)
        mock_conv.return_value = ConvergenceResult(
            decision="CONVERGED", reason="done", coverage=1.0, novelty=0.0, gap_questions=()
        )
        mock_report.return_value = "Flash report"
        mock_claims.return_value = [_make_claim()]

        result = await orch.research(
            query="What is KITAS?",
            tier="auto",
            domain="auto",
        )

    mock_gw.assert_called_once()
    assert result["status"] == "completed"
    # Gateway classified as flash
    assert result["tier"] == "flash"
    assert result["domain"] == "indonesia"


# ---------------------------------------------------------------------------
# test_orchestrator_respects_budget — stops when budget exhausted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_respects_budget() -> None:
    """Orchestrator stops looping when search budget is exhausted."""
    deps = _make_deps()
    orch = NagaOrchestrator(deps)

    # Return a response that uses many search calls
    big_response = AgentResponse(
        agent_name="exa",
        results=[_make_search_result(url=f"https://example.com/{i}") for i in range(5)],
        search_calls_used=10,  # uses lots of budget
    )

    with (
        patch("backend.services.naga.orchestrator.ExaSearchAgent") as MockExa,
        patch("backend.services.naga.orchestrator.BraveSearchAgent") as MockBrave,
        patch("backend.services.naga.orchestrator.IndonesiaDomainAgent") as MockDomain,
        patch("backend.services.naga.orchestrator.crag_evaluate") as mock_crag,
        patch("backend.services.naga.orchestrator.check_convergence") as mock_conv,
        patch("backend.services.naga.orchestrator.generate_report") as mock_report,
        patch("backend.services.naga.orchestrator.extract_claims_from_response") as mock_claims,
    ):
        MockExa.return_value.search = AsyncMock(return_value=big_response)
        MockBrave.return_value.search = AsyncMock(return_value=big_response)
        MockDomain.return_value.search = AsyncMock(return_value=big_response)

        mock_crag.return_value = CragDecision(action="PASS", reason="ok", relevance_score=0.5)

        # Always say TIMEOUT (budget exhausted)
        mock_conv.return_value = ConvergenceResult(
            decision="TIMEOUT",
            reason="budget exhausted",
            coverage=0.3,
            novelty=0.9,
            gap_questions=("q1",),
        )
        mock_report.return_value = "Partial report"
        mock_claims.return_value = []

        result = await orch.research(
            query="What is KITAS?",
            tier="flash",  # flash has max_searches=3, max_iterations=1
            domain="general",
        )

    assert result["status"] == "completed"
    assert result["convergence_decision"] in ("TIMEOUT", "CONVERGED")
    # Should complete within 1 iteration for flash
    assert result["iteration"] <= 1


# ---------------------------------------------------------------------------
# test_orchestrator_handles_search_error — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_orchestrator_handles_search_error() -> None:
    """When all search agents fail, orchestrator degrades gracefully."""
    deps = _make_deps()
    orch = NagaOrchestrator(deps)

    error_response = AgentResponse(
        agent_name="exa",
        results=[],
        search_calls_used=1,
        error="API rate limited",
    )

    with (
        patch("backend.services.naga.orchestrator.ExaSearchAgent") as MockExa,
        patch("backend.services.naga.orchestrator.BraveSearchAgent") as MockBrave,
        patch("backend.services.naga.orchestrator.IndonesiaDomainAgent") as MockDomain,
        patch("backend.services.naga.orchestrator.crag_evaluate") as mock_crag,
        patch("backend.services.naga.orchestrator.check_convergence") as mock_conv,
        patch("backend.services.naga.orchestrator.generate_report") as mock_report,
        patch("backend.services.naga.orchestrator.extract_claims_from_response") as mock_claims,
    ):
        MockExa.return_value.search = AsyncMock(return_value=error_response)
        MockBrave.return_value.search = AsyncMock(return_value=error_response)
        MockDomain.return_value.search = AsyncMock(return_value=error_response)

        mock_crag.return_value = CragDecision(
            action="ESCALATE", reason="no sources", relevance_score=0.0
        )
        mock_conv.return_value = ConvergenceResult(
            decision="TIMEOUT",
            reason="no results",
            coverage=0.0,
            novelty=0.0,
            gap_questions=("q1",),
        )
        mock_report.return_value = "No verifiable claims were found for this query."
        mock_claims.return_value = []

        result = await orch.research(
            query="What is KITAS?",
            tier="flash",
            domain="general",
        )

    # Must NOT crash — should return a valid state dict
    assert result["status"] == "completed"
    assert isinstance(result["report_markdown"], str)
    assert result["claims_extracted"] == 0


# ---------------------------------------------------------------------------
# test_decompose_query — heuristic decomposition
# ---------------------------------------------------------------------------


class TestDecomposeQuery:
    """Unit tests for the _decompose_query heuristic."""

    def test_flash_no_decomposition(self) -> None:
        """Flash tier returns only the original query."""
        subs = _decompose_query("What is KITAS?", "flash")
        assert subs == ["What is KITAS?"]

    def test_vs_comparison(self) -> None:
        """Queries containing 'vs' are decomposed into 3 sub-questions."""
        subs = _decompose_query("KITAS vs KITAP comparison", "deep")
        assert len(subs) == 3
        assert "KITAS" in subs[0]
        assert "KITAP" in subs[1]

    def test_confronto_comparison(self) -> None:
        """Queries containing 'confronto' trigger comparison decomposition."""
        subs = _decompose_query("confronto KITAS e KITAP", "deep")
        assert len(subs) == 3

    def test_default_decomposition(self) -> None:
        """Non-comparison deep queries get original + 'latest developments'."""
        subs = _decompose_query("KITAS requirements 2026", "deep")
        assert len(subs) == 2
        assert subs[0] == "KITAS requirements 2026"
        assert "latest developments" in subs[1].lower()


# ---------------------------------------------------------------------------
# test_state_dict_shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_dict_shape() -> None:
    """The returned dict must contain all NagaResearchState keys."""
    deps = _make_deps()
    orch = NagaOrchestrator(deps)

    fake_response = _make_agent_response(n_results=1)

    with (
        patch("backend.services.naga.orchestrator.ExaSearchAgent") as MockExa,
        patch("backend.services.naga.orchestrator.BraveSearchAgent") as MockBrave,
        patch("backend.services.naga.orchestrator.IndonesiaDomainAgent") as MockDomain,
        patch("backend.services.naga.orchestrator.crag_evaluate") as mock_crag,
        patch("backend.services.naga.orchestrator.check_convergence") as mock_conv,
        patch("backend.services.naga.orchestrator.generate_report") as mock_report,
        patch("backend.services.naga.orchestrator.extract_claims_from_response") as mock_claims,
    ):
        MockExa.return_value.search = AsyncMock(return_value=fake_response)
        MockBrave.return_value.search = AsyncMock(return_value=fake_response)
        MockDomain.return_value.search = AsyncMock(return_value=fake_response)

        mock_crag.return_value = CragDecision(action="PASS", reason="ok", relevance_score=0.5)
        mock_conv.return_value = ConvergenceResult(
            decision="CONVERGED", reason="done", coverage=1.0, novelty=0.0, gap_questions=()
        )
        mock_report.return_value = "Report"
        mock_claims.return_value = []

        result = await orch.research(query="test query", tier="flash", domain="general")

    expected_keys = set(NagaResearchState.__annotations__.keys())
    assert expected_keys.issubset(set(result.keys())), (
        f"Missing keys: {expected_keys - set(result.keys())}"
    )
