"""Tests for backend.services.rag.multi_agent_coordinator"""

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


# ── _merge_agent_outputs ────────────────────────────────────────────────────


class TestMergeAgentOutputs:
    def test_merge_empty(self):
        assert _merge_agent_outputs([], []) == []

    def test_merge_appends(self):
        result = _merge_agent_outputs([{"a": 1}], [{"b": 2}])
        assert len(result) == 2


# ── requires_multi_agent ────────────────────────────────────────────────────


class TestRequiresMultiAgent:
    def test_cost_and_time_en(self):
        assert requires_multi_agent("How much does it cost and when can I start?") is True

    def test_cost_and_time_id(self):
        assert requires_multi_agent("Berapa biaya dan kapan bisa mulai?") is True

    def test_cost_and_time_it(self):
        assert requires_multi_agent("Quanto costa e quanto tempo ci vuole?") is True

    def test_cost_only(self):
        assert requires_multi_agent("How much does KITAS cost?") is False

    def test_time_only(self):
        assert requires_multi_agent("How long does it take?") is False

    def test_multiple_domains(self):
        entities = [
            {"entity_type": "kitas"},
            {"entity_type": "pph"},
        ]
        assert requires_multi_agent("What visa and tax do I need?", entities) is True

    def test_high_entity_count(self):
        entities = [{"entity_type": f"type_{i}"} for i in range(6)]
        assert requires_multi_agent("complex query", entities) is True

    def test_many_conjunctions(self):
        assert requires_multi_agent("visa and company serta tax") is True

    def test_simple_query(self):
        assert requires_multi_agent("What is KITAS?") is False

    def test_none_entities(self):
        assert requires_multi_agent("simple query", entities=None) is False

    def test_company_domain(self):
        entities = [
            {"entity_type": "pt_pma"},
            {"entity_type": "biaya"},
        ]
        assert requires_multi_agent("PT PMA cost", entities) is True


# ── FinancialAgent._extract_service_type ────────────────────────────────────


class TestExtractServiceType:
    def test_business_setup(self):
        assert FinancialAgent._extract_service_type("How to set up PT PMA?") == "business_setup"

    def test_kitas(self):
        assert FinancialAgent._extract_service_type("KITAS application cost") == "kitas"

    def test_visa(self):
        assert FinancialAgent._extract_service_type("E-visa requirements") == "visa"

    def test_tax(self):
        assert FinancialAgent._extract_service_type("NPWP registration fee") == "tax_consulting"

    def test_legal(self):
        assert FinancialAgent._extract_service_type("notaris fee for akta") == "legal"

    def test_default(self):
        assert FinancialAgent._extract_service_type("random question") == "all"


# ── LegalAgent.analyze ──────────────────────────────────────────────────────


class TestLegalAgentAnalyze:
    @pytest.mark.asyncio
    async def test_success_with_kg(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Legal analysis result"))

        mock_kg = MagicMock()
        mock_kg.extract_entities_from_query = MagicMock(return_value=[("KITAS", "kitas")])
        mock_kg.find_kg_entities = AsyncMock(return_value=[
            {"name": "KITAS", "entity_type": "kitas"},
        ])

        agent = LegalAgent(llm=mock_llm, kg_retrieval=mock_kg)
        state: MultiAgentState = {
            "query": "What documents for KITAS?",
            "user_context": {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "legal_analysis" in result
        assert result["agent_outputs"][0]["agent"] == "legal"

    @pytest.mark.asyncio
    async def test_failure_returns_error(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM error"))

        agent = LegalAgent(llm=mock_llm, kg_retrieval=None)
        state: MultiAgentState = {
            "query": "test",
            "user_context": {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "unavailable" in result["legal_analysis"]
        assert "error" in result["agent_outputs"][0]


# ── FinancialAgent.analyze ──────────────────────────────────────────────────


class TestFinancialAgentAnalyze:
    @pytest.mark.asyncio
    async def test_success(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Cost breakdown"))

        mock_pricing = MagicMock()
        mock_pricing.get_pricing = MagicMock(return_value={})
        mock_pricing.format_for_llm_context = MagicMock(return_value="Pricing data")
        mock_pricing.loaded = True

        agent = FinancialAgent(llm=mock_llm, pricing_service=mock_pricing)
        state: MultiAgentState = {
            "query": "How much does PT PMA cost?",
            "user_context": {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "financial_breakdown" in result
        assert result["agent_outputs"][0]["agent"] == "financial"

    @pytest.mark.asyncio
    async def test_failure(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("fail"))

        mock_pricing = MagicMock()
        mock_pricing.get_pricing = MagicMock(side_effect=Exception("no prices"))

        agent = FinancialAgent(llm=mock_llm, pricing_service=mock_pricing)
        state: MultiAgentState = {
            "query": "cost?",
            "user_context": {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "unavailable" in result["financial_breakdown"]


# ── TimelineAgent.analyze ───────────────────────────────────────────────────


class TestTimelineAgentAnalyze:
    @pytest.mark.asyncio
    async def test_success_with_legal_context(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Timeline: 3 months"))

        agent = TimelineAgent(llm=mock_llm, kg_retrieval=None)
        state: MultiAgentState = {
            "query": "When can I start?",
            "user_context": {},
            "legal_analysis": "Step 1: Get NPWP\nStep 2: Register OSS",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "timeline_estimate" in result
        assert result["agent_outputs"][0]["had_legal_context"] is True

    @pytest.mark.asyncio
    async def test_failure(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("fail"))

        agent = TimelineAgent(llm=mock_llm, kg_retrieval=None)
        state: MultiAgentState = {
            "query": "timeline?",
            "user_context": {},
            "legal_analysis": "",
            "financial_breakdown": "",
            "timeline_estimate": "",
            "agent_outputs": [],
            "final_answer": "",
            "errors": [],
        }

        result = await agent.analyze(state)
        assert "unavailable" in result["timeline_estimate"]


# ── MultiAgentCoordinator ──────────────────────────────────────────────────


class TestMultiAgentCoordinator:
    def test_init(self):
        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            assert coordinator._llm is None  # lazy init

    @pytest.mark.asyncio
    async def test_process_failure(self):
        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            # Force _ensure_initialized to fail
            with patch.object(
                coordinator, "_ensure_initialized",
                side_effect=Exception("No LLM"),
            ):
                result = await coordinator.process("test query")
                assert "failed" in result["final_answer"].lower()
                assert len(result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_synthesize_outputs_success(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(return_value=MagicMock(content="Synthesized answer"))

        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            coordinator._llm = mock_llm

            state: MultiAgentState = {
                "query": "test",
                "user_context": {},
                "legal_analysis": "Legal stuff",
                "financial_breakdown": "Cost stuff",
                "timeline_estimate": "Timeline stuff",
                "agent_outputs": [],
                "final_answer": "",
                "errors": [],
            }

            result = await coordinator._synthesize_outputs(state)
            assert "Synthesized answer" in result["final_answer"]

    @pytest.mark.asyncio
    async def test_synthesize_outputs_failure(self):
        mock_llm = AsyncMock()
        mock_llm.ainvoke = AsyncMock(side_effect=Exception("LLM fail"))

        with patch(
            "backend.services.rag.multi_agent_coordinator.get_pricing_service",
            return_value=MagicMock(),
        ):
            coordinator = MultiAgentCoordinator()
            coordinator._llm = mock_llm

            state: MultiAgentState = {
                "query": "test",
                "user_context": {},
                "legal_analysis": "Legal",
                "financial_breakdown": "Financial",
                "timeline_estimate": "Timeline",
                "agent_outputs": [],
                "final_answer": "",
                "errors": [],
            }

            result = await coordinator._synthesize_outputs(state)
            assert "Legal" in result["final_answer"]
            assert "Financial" in result["final_answer"]
