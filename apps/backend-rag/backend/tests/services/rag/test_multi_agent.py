"""
Test suite for Phase 6: Multi-Agent Coordinator

Tests the MultiAgentCoordinator, specialized agents (Legal, Financial, Timeline),
query detection logic, state management, and error handling.

Author: Nuzantara Team
Date: 2026-02-09

Test Coverage:
- Query Detection: 8 tests
- LegalAgent: 3 tests
- FinancialAgent: 4 tests
- TimelineAgent: 3 tests
- MultiAgentCoordinator: 4 tests
- State & Error Handling: 3 tests
Total: 25 tests (exceeds 15-test target)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.multi_agent_coordinator import (
    FinancialAgent,
    LegalAgent,
    MultiAgentCoordinator,
    MultiAgentState,
    TimelineAgent,
    _merge_agent_outputs,
    requires_multi_agent,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_llm():
    """Mock LangChain LLM with ainvoke."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock()
    return llm


@pytest.fixture
def mock_kg_retrieval():
    """Mock KGEnhancedRetrieval."""
    kg = MagicMock()
    kg.extract_entities_from_query = MagicMock(return_value=[])
    kg.find_kg_entities = AsyncMock(return_value=[])
    return kg


@pytest.fixture
def mock_pricing_service():
    """Mock PricingService with loaded prices."""
    ps = MagicMock()
    ps.loaded = True
    ps.get_pricing = MagicMock(return_value={"services": {}})
    ps.format_for_llm_context = MagicMock(return_value="## VISA PRICES\n- B211A: IDR 8,500,000")
    return ps


@pytest.fixture
def base_state() -> MultiAgentState:
    """Base MultiAgentState for testing."""
    return {
        "query": "How much will PT PMA cost and when can I start operations?",
        "user_context": {},
        "legal_analysis": "",
        "financial_breakdown": "",
        "timeline_estimate": "",
        "agent_outputs": [],
        "final_answer": "",
        "errors": [],
    }


# ============================================================================
# Test: Query Detection (requires_multi_agent)
# ============================================================================


class TestRequiresMultiAgent:
    """Test the requires_multi_agent detection function."""

    def test_cost_and_time_english(self):
        """Detect cost+timeline in English."""
        assert requires_multi_agent("How much will PT PMA cost and when can I start?") is True

    def test_cost_and_time_indonesian(self):
        """Detect cost+timeline in Indonesian."""
        assert requires_multi_agent("Berapa biaya PT PMA dan kapan bisa mulai?") is True

    def test_cost_and_time_italian(self):
        """Detect cost+timeline in Italian."""
        assert requires_multi_agent("Quanto costa aprire PT PMA e quanto tempo ci vuole?") is True

    def test_simple_query_no_trigger(self):
        """Simple single-domain query should NOT trigger."""
        assert requires_multi_agent("What is KITAS?") is False

    def test_cost_only_no_trigger(self):
        """Cost-only query should NOT trigger."""
        assert requires_multi_agent("How much does a visa cost?") is False

    def test_time_only_no_trigger(self):
        """Time-only query should NOT trigger."""
        assert requires_multi_agent("When can I get my KITAS?") is False

    def test_multiple_domains_via_entities(self):
        """Multiple domain entities should trigger."""
        entities = [
            {"entity_type": "kitas"},
            {"entity_type": "pph"},
        ]
        assert requires_multi_agent("I need KITAS and tax info", entities) is True

    def test_high_entity_count_trigger(self):
        """More than 5 entities should trigger."""
        entities = [{"entity_type": f"type_{i}"} for i in range(6)]
        assert requires_multi_agent("complex query about many things", entities) is True


# ============================================================================
# Test: LegalAgent
# ============================================================================


class TestLegalAgent:
    """Test LegalAgent analysis."""

    @pytest.mark.asyncio
    async def test_analyze_returns_legal_analysis(self, mock_llm, mock_kg_retrieval, base_state):
        """LegalAgent returns legal_analysis and agent_outputs."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="- NPWP required\n- Akta Pendirian needed",
        )

        agent = LegalAgent(mock_llm, mock_kg_retrieval)
        result = await agent.analyze(base_state)

        assert "legal_analysis" in result
        assert "NPWP" in result["legal_analysis"]
        assert len(result["agent_outputs"]) == 1
        assert result["agent_outputs"][0]["agent"] == "legal"

    @pytest.mark.asyncio
    async def test_analyze_uses_kg_entities(self, mock_llm, base_state):
        """LegalAgent uses KG entities when available."""
        kg = MagicMock()
        kg.extract_entities_from_query.return_value = [("PT PMA", "pt_pma")]
        kg.find_kg_entities = AsyncMock(
            return_value=[
                {"entity_id": "pt_pma:1", "entity_type": "pt_pma", "name": "PT PMA Setup"},
            ],
        )

        mock_llm.ainvoke.return_value = MagicMock(content="Legal steps for PT PMA")

        agent = LegalAgent(mock_llm, kg)
        result = await agent.analyze(base_state)

        assert result["agent_outputs"][0]["entities_used"] == 1
        kg.find_kg_entities.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_analyze_handles_llm_error(self, mock_llm, mock_kg_retrieval, base_state):
        """LegalAgent handles LLM errors gracefully."""
        mock_llm.ainvoke.side_effect = RuntimeError("LLM unavailable")

        agent = LegalAgent(mock_llm, mock_kg_retrieval)
        result = await agent.analyze(base_state)

        assert "unavailable" in result["legal_analysis"].lower()
        assert "error" in result["agent_outputs"][0]


# ============================================================================
# Test: FinancialAgent
# ============================================================================


class TestFinancialAgent:
    """Test FinancialAgent analysis."""

    @pytest.mark.asyncio
    async def test_analyze_returns_breakdown(self, mock_llm, mock_pricing_service, base_state):
        """FinancialAgent returns financial_breakdown."""
        mock_llm.ainvoke.return_value = MagicMock(content="Total: IDR 20,000,000")

        agent = FinancialAgent(mock_llm, mock_pricing_service)
        result = await agent.analyze(base_state)

        assert "financial_breakdown" in result
        assert "20,000,000" in result["financial_breakdown"]
        assert result["agent_outputs"][0]["agent"] == "financial"

    @pytest.mark.asyncio
    async def test_analyze_uses_pricing_service(self, mock_llm, mock_pricing_service, base_state):
        """FinancialAgent calls PricingService."""
        mock_llm.ainvoke.return_value = MagicMock(content="Cost breakdown")

        agent = FinancialAgent(mock_llm, mock_pricing_service)
        await agent.analyze(base_state)

        mock_pricing_service.get_pricing.assert_called_once()
        mock_pricing_service.format_for_llm_context.assert_called_once()

    def test_extract_service_type_pt_pma(self):
        """Extract business_setup from PT PMA query."""
        assert (
            FinancialAgent._extract_service_type("How much does PT PMA cost?") == "business_setup"
        )

    def test_extract_service_type_kitas(self):
        """Extract kitas from KITAS query."""
        assert FinancialAgent._extract_service_type("KITAS work permit price") == "kitas"

    def test_extract_service_type_visa(self):
        """Extract visa from visa query."""
        assert FinancialAgent._extract_service_type("How much is a visa to Bali?") == "visa"

    def test_extract_service_type_fallback(self):
        """Fallback to 'all' for unknown queries."""
        assert FinancialAgent._extract_service_type("random question") == "all"


# ============================================================================
# Test: TimelineAgent
# ============================================================================


class TestTimelineAgent:
    """Test TimelineAgent analysis."""

    @pytest.mark.asyncio
    async def test_analyze_returns_timeline(self, mock_llm, mock_kg_retrieval, base_state):
        """TimelineAgent returns timeline_estimate."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="Phase 1: 7 days\nPhase 2: 14 days\nTotal: 21 days",
        )

        agent = TimelineAgent(mock_llm, mock_kg_retrieval)
        result = await agent.analyze(base_state)

        assert "timeline_estimate" in result
        assert "21 days" in result["timeline_estimate"]
        assert result["agent_outputs"][0]["agent"] == "timeline"

    @pytest.mark.asyncio
    async def test_analyze_uses_legal_context(self, mock_llm, mock_kg_retrieval, base_state):
        """TimelineAgent uses legal_analysis from previous agent."""
        base_state["legal_analysis"] = "Step 1: Get NPWP\nStep 2: Register at OSS"
        mock_llm.ainvoke.return_value = MagicMock(content="Timeline based on legal steps")

        agent = TimelineAgent(mock_llm, mock_kg_retrieval)
        result = await agent.analyze(base_state)

        assert result["agent_outputs"][0]["had_legal_context"] is True

    @pytest.mark.asyncio
    async def test_analyze_handles_no_kg(self, mock_llm, base_state):
        """TimelineAgent works without KG retrieval."""
        mock_llm.ainvoke.return_value = MagicMock(content="Estimated 30 days")

        agent = TimelineAgent(mock_llm, None)
        result = await agent.analyze(base_state)

        assert "timeline_estimate" in result
        assert result["agent_outputs"][0]["duration_entities_used"] == 0


# ============================================================================
# Test: MultiAgentCoordinator
# ============================================================================


class TestMultiAgentCoordinator:
    """Test the full MultiAgentCoordinator workflow."""

    @pytest.mark.asyncio
    async def test_process_returns_all_fields(self, mock_kg_retrieval, mock_pricing_service):
        """Full process returns all expected fields."""
        with patch(
            "backend.services.rag.multi_agent_coordinator._get_multi_agent_llm",
        ) as mock_get_llm:
            llm = AsyncMock()
            llm.ainvoke.return_value = MagicMock(content="Test output")
            mock_get_llm.return_value = llm

            coordinator = MultiAgentCoordinator(
                kg_retrieval=mock_kg_retrieval,
                pricing_service=mock_pricing_service,
            )

            result = await coordinator.process(
                "How much will PT PMA cost and when can I start?",
                {"citizenship": "Italian"},
            )

            assert "final_answer" in result
            assert "legal_analysis" in result
            assert "financial_breakdown" in result
            assert "timeline_estimate" in result
            assert "agent_outputs" in result
            assert "execution_time_s" in result

    @pytest.mark.asyncio
    async def test_process_calls_all_agents(self, mock_kg_retrieval, mock_pricing_service):
        """All three agents + synthesizer are called."""
        with patch(
            "backend.services.rag.multi_agent_coordinator._get_multi_agent_llm",
        ) as mock_get_llm:
            llm = AsyncMock()
            llm.ainvoke.return_value = MagicMock(content="Agent output")
            mock_get_llm.return_value = llm

            coordinator = MultiAgentCoordinator(
                kg_retrieval=mock_kg_retrieval,
                pricing_service=mock_pricing_service,
            )

            result = await coordinator.process("PT PMA cost and timeline?")

            agent_names = [o["agent"] for o in result.get("agent_outputs", [])]
            assert "legal" in agent_names
            assert "financial" in agent_names
            assert "timeline" in agent_names
            assert "synthesizer" in agent_names

    @pytest.mark.asyncio
    async def test_process_handles_total_failure(self):
        """Coordinator handles complete LLM failure gracefully."""
        with patch(
            "backend.services.rag.multi_agent_coordinator._get_multi_agent_llm",
        ) as mock_get_llm:
            mock_get_llm.side_effect = ValueError("No LLM available")

            coordinator = MultiAgentCoordinator()

            result = await coordinator.process("test query")

            assert "errors" in result
            assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_process_with_no_dependencies(self, mock_pricing_service):
        """Coordinator works without KG retrieval (None)."""
        with patch(
            "backend.services.rag.multi_agent_coordinator._get_multi_agent_llm",
        ) as mock_get_llm:
            llm = AsyncMock()
            llm.ainvoke.return_value = MagicMock(content="Output without KG")
            mock_get_llm.return_value = llm

            coordinator = MultiAgentCoordinator(
                kg_retrieval=None,
                pricing_service=mock_pricing_service,
                db_pool=None,
            )

            result = await coordinator.process("Simple cost question")

            assert result["final_answer"] != ""


# ============================================================================
# Test: State & Error Handling
# ============================================================================


class TestStateManagement:
    """Test state management and error handling."""

    def test_merge_agent_outputs_reducer(self):
        """Agent output reducer appends correctly."""
        existing = [{"agent": "legal", "output": "step 1"}]
        new = [{"agent": "financial", "output": "cost info"}]

        merged = _merge_agent_outputs(existing, new)

        assert len(merged) == 2
        assert merged[0]["agent"] == "legal"
        assert merged[1]["agent"] == "financial"

    def test_merge_agent_outputs_empty(self):
        """Reducer handles empty lists."""
        assert _merge_agent_outputs([], []) == []
        assert _merge_agent_outputs([], [{"agent": "legal"}]) == [{"agent": "legal"}]

    def test_initial_state_structure(self, base_state):
        """Initial state has all required keys."""
        required_keys = {
            "query",
            "user_context",
            "legal_analysis",
            "financial_breakdown",
            "timeline_estimate",
            "agent_outputs",
            "final_answer",
            "errors",
        }
        assert required_keys.issubset(set(base_state.keys()))


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
