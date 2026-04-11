"""Tests for backend.services.rag.agentic.kg_orchestrator"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.kg_orchestrator import (
    AgenticResponse,
    KGAgenticOrchestrator,
)


@pytest.fixture
def mock_db_pool():
    return AsyncMock()


@pytest.fixture
def mock_retriever():
    return MagicMock()


@pytest.fixture
def orchestrator(mock_db_pool, mock_retriever):
    with (
        patch("backend.services.rag.agentic.kg_orchestrator.KGEnhancedRetrieval"),
        patch("backend.services.rag.agentic.kg_orchestrator.VectorSearchTool"),
        patch("backend.services.rag.agentic.kg_orchestrator.LLMGateway"),
        patch("backend.services.rag.agentic.kg_orchestrator.IntentClassifier"),
    ):
        return KGAgenticOrchestrator(db_pool=mock_db_pool, retriever=mock_retriever)


# ── AgenticResponse dataclass ───────────────────────────────────────────────


class TestAgenticResponse:
    def test_defaults(self):
        resp = AgenticResponse(answer="Test", confidence=0.8, reasoning_trace=["step1"])
        assert resp.answer == "Test"
        assert resp.confidence == 0.8
        assert resp.sources == []
        assert resp.estimated_timeline is None
        assert resp.estimated_cost is None
        assert resp.collections_searched == []
        assert resp.total_time_ms == 0.0

    def test_full_construction(self):
        resp = AgenticResponse(
            answer="Answer",
            confidence=0.9,
            reasoning_trace=["s1", "s2"],
            sources=[{"doc_id": "1"}],
            estimated_timeline="~3 months",
            estimated_cost="$1,000 - $5,000 USD",
            intent_category="visa",
            golden_route_matched="route_1",
            kg_entities_found=5,
            collections_searched=["visa_oracle"],
            total_time_ms=1500.0,
            model_used="gemini-2.5-flash",
        )
        assert resp.model_used == "gemini-2.5-flash"
        assert len(resp.sources) == 1


# ── _classify_intent ────────────────────────────────────────────────────────


class TestClassifyIntent:
    @pytest.mark.asyncio
    async def test_classify_success(self, orchestrator):
        orchestrator.intent_classifier.classify_intent = AsyncMock(
            return_value={"category": "visa", "confidence": 0.9, "suggested_ai": "fast"},
        )
        result = await orchestrator._classify_intent("How to get KITAS?")
        assert result["category"] == "visa"

    @pytest.mark.asyncio
    async def test_classify_fallback_on_error(self, orchestrator):
        orchestrator.intent_classifier.classify_intent = AsyncMock(
            side_effect=Exception("fail"),
        )
        result = await orchestrator._classify_intent("test query")
        assert result["category"] == "unknown"
        assert result["confidence"] == 0.5


# ── _get_kg_context ─────────────────────────────────────────────────────────


class TestGetKgContext:
    @pytest.mark.asyncio
    async def test_success(self, orchestrator):
        mock_context = MagicMock()
        mock_context.entities_found = [{"name": "KITAS"}]
        mock_context.relationships = []
        mock_context.golden_route = None
        orchestrator.kg_retrieval.get_context_for_query = AsyncMock(
            return_value=mock_context,
        )
        result = await orchestrator._get_kg_context("KITAS query")
        assert len(result.entities_found) == 1

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, orchestrator):
        orchestrator.kg_retrieval.get_context_for_query = AsyncMock(
            side_effect=Exception("fail"),
        )
        result = await orchestrator._get_kg_context("test")
        assert result.entities_found == []
        assert result.golden_route is None


# ── _route_collections ──────────────────────────────────────────────────────


class TestRouteCollections:
    def test_visa_intent(self, orchestrator):
        intent = {"category": "visa"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        kg_ctx.golden_route = None
        result = orchestrator._route_collections(intent, kg_ctx)
        assert "visa_oracle" in result

    def test_company_intent(self, orchestrator):
        intent = {"category": "company"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        kg_ctx.golden_route = None
        result = orchestrator._route_collections(intent, kg_ctx)
        assert "legal_unified" in result

    def test_kbli_entity_type(self, orchestrator):
        intent = {"category": "unknown"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = [{"entity_type": "kbli"}]
        kg_ctx.golden_route = None
        result = orchestrator._route_collections(intent, kg_ctx)
        assert "kbli_2025_final" in result

    def test_tax_entity_type(self, orchestrator):
        intent = {"category": "unknown"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = [{"entity_type": "pph"}]
        kg_ctx.golden_route = None
        result = orchestrator._route_collections(intent, kg_ctx)
        assert "tax_genius" in result

    def test_golden_route_restaurant(self, orchestrator):
        intent = {"category": "unknown"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        kg_ctx.golden_route = MagicMock()
        kg_ctx.golden_route.route_id = "restaurant_bali"
        result = orchestrator._route_collections(intent, kg_ctx)
        assert "legal_unified" in result
        assert "kbli_2025_final" in result

    def test_no_matches(self, orchestrator):
        intent = {"category": "unknown"}
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        kg_ctx.golden_route = None
        result = orchestrator._route_collections(intent, kg_ctx)
        assert result == []


# ── _calculate_confidence ───────────────────────────────────────────────────


class TestCalculateConfidence:
    def test_base_confidence(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": []},
            golden_route=None,
            response_length=50,
        )
        assert result == 0.5

    def test_golden_route_boost(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": []},
            golden_route=MagicMock(),
            response_length=50,
        )
        assert result >= 0.75

    def test_entities_boost(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = [{"name": f"e{i}"} for i in range(10)]
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": []},
            golden_route=None,
            response_length=50,
        )
        assert result > 0.5

    def test_sources_boost(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": [{"id": i} for i in range(10)]},
            golden_route=None,
            response_length=50,
        )
        assert result > 0.5

    def test_long_response_boost(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": []},
            golden_route=None,
            response_length=500,
        )
        assert result == 0.55

    def test_cap_at_095(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = [{"name": f"e{i}"} for i in range(20)]
        result = orchestrator._calculate_confidence(
            kg_context=kg_ctx,
            search_results={"sources": [{"id": i} for i in range(20)]},
            golden_route=MagicMock(),
            response_length=1000,
        )
        assert result <= 0.95


# ── _build_response ─────────────────────────────────────────────────────────


class TestBuildResponse:
    def test_with_golden_route(self, orchestrator):
        golden = MagicMock()
        golden.route_id = "r1"
        golden.estimated_timeline_months = 3
        golden.estimated_cost_range_usd = (1000, 5000)

        kg_ctx = MagicMock()
        kg_ctx.entities_found = [{"name": "e1"}]

        import time
        resp = orchestrator._build_response(
            answer="Answer",
            confidence=0.8,
            reasoning_trace=["s1"],
            sources=[],
            intent_result={"category": "visa"},
            kg_context=kg_ctx,
            golden_route=golden,
            collections_searched=["visa_oracle"],
            model_used="gemini",
            start_time=time.time() - 1.0,
        )
        assert resp.estimated_timeline == "~3 months"
        assert "$1,000" in resp.estimated_cost
        assert resp.golden_route_matched == "r1"
        assert resp.total_time_ms > 0

    def test_without_golden_route(self, orchestrator):
        kg_ctx = MagicMock()
        kg_ctx.entities_found = []

        import time
        resp = orchestrator._build_response(
            answer="Answer",
            confidence=0.5,
            reasoning_trace=[],
            sources=[],
            intent_result={"category": "unknown"},
            kg_context=kg_ctx,
            golden_route=None,
            collections_searched=[],
            model_used="test",
            start_time=time.time(),
        )
        assert resp.estimated_timeline is None
        assert resp.estimated_cost is None
        assert resp.golden_route_matched is None

    def test_short_timeline(self, orchestrator):
        golden = MagicMock()
        golden.route_id = "r2"
        golden.estimated_timeline_months = 0.5
        golden.estimated_cost_range_usd = None

        kg_ctx = MagicMock()
        kg_ctx.entities_found = []

        import time
        resp = orchestrator._build_response(
            answer="A", confidence=0.5, reasoning_trace=[], sources=[],
            intent_result={}, kg_context=kg_ctx, golden_route=golden,
            collections_searched=[], model_used="x", start_time=time.time(),
        )
        assert "days" in resp.estimated_timeline
        assert resp.estimated_cost is None


# ── process (integration-level mock) ────────────────────────────────────────


class TestProcess:
    @pytest.mark.asyncio
    async def test_process_error_returns_fallback(self, orchestrator):
        with patch.object(
            orchestrator, "_classify_intent",
            new_callable=AsyncMock,
            side_effect=Exception("boom"),
        ):
            resp = await orchestrator.process(query="test", session_id="s1")
            assert resp.confidence == 0.0
            assert "errore" in resp.answer.lower() or "error" in resp.reasoning_trace[-1].lower()
