"""TDD test suite — R5 Phase 5: KG fast-path in OrchestratorCore.

When SurfaceDecision.is_kg_surface=True, process_query_core must:
1. Call kg_langgraph_orchestrator.query() directly (bypass Qdrant ReAct loop)
2. Return CoreResult with model_used="kg_langgraph" + surface="kg"
3. Gracefully degrade (return None fast-path) when kg_orchestrator is None
4. Gracefully degrade when kg_orchestrator.query() raises
5. Not enter the ReAct loop for KG queries
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.rag.agentic.schema import CoreResult
from backend.services.routing.surface_router import Surface, SurfaceDecision

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_kg_decision() -> SurfaceDecision:
    return SurfaceDecision(
        surface=Surface.KG,
        primary_collection="",
        collections=[],
        domain="kg",
        confidence=0.88,
        layer_used=1,
        is_local_only=False,
        latency_ms=0.5,
        is_kg_surface=True,
    )


def _make_qdrant_decision() -> SurfaceDecision:
    return SurfaceDecision(
        surface=Surface.QDRANT_VISA,
        primary_collection="visa_oracle",
        collections=["visa_oracle"],
        domain="visa",
        confidence=0.90,
        layer_used=1,
        is_local_only=False,
        latency_ms=0.5,
        is_kg_surface=False,
    )


def _make_kg_orchestrator_result() -> dict:
    return {
        "workflow": {
            "type": "entity_resolution",
            "name": "Company Director Lookup",
            "steps": [{"step": 1, "action": "Resolve entity from Neo4j"}],
            "source": "neo4j",
            "confidence": 0.85,
        },
        "evidence": [{"entity": "John Doe", "role": "Director"}],
        "reasoning": "Found 1 matching entity in KG.",
    }


# ---------------------------------------------------------------------------
# 1. KG fast-path integration — _try_kg_fast_path method
# ---------------------------------------------------------------------------

class TestKGFastPath:
    """Tests for OrchestratorCore._try_kg_fast_path (internal helper)."""

    @pytest.fixture()
    def mock_kg_orchestrator(self):
        m = AsyncMock()
        m.app = MagicMock()  # simulate initialized orchestrator
        m.query = AsyncMock(return_value=_make_kg_orchestrator_result())
        return m

    @pytest.mark.asyncio
    async def test_kg_fast_path_returns_core_result(self, mock_kg_orchestrator):
        """_try_kg_fast_path returns CoreResult when kg_orchestrator is available."""

        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_kg_decision()

        result = await core._try_kg_fast_path(
            query="chi è il direttore di PT Bali XYZ?",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is not None
        assert isinstance(result, CoreResult)
        assert result.model_used == "kg_langgraph"

    @pytest.mark.asyncio
    async def test_kg_fast_path_returns_none_when_no_orchestrator(self):
        """_try_kg_fast_path returns None when kg_langgraph_orchestrator is None."""

        core = _make_minimal_core(kg_langgraph_orchestrator=None)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_kg_decision()

        result = await core._try_kg_fast_path(
            query="struttura societaria azienda",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_kg_fast_path_returns_none_when_not_kg_surface(self, mock_kg_orchestrator):
        """_try_kg_fast_path returns None for Qdrant surfaces (is_kg_surface=False)."""

        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_qdrant_decision()

        result = await core._try_kg_fast_path(
            query="KITAS renewal requirements",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_kg_fast_path_returns_none_when_no_surface_router(self, mock_kg_orchestrator):
        """_try_kg_fast_path returns None gracefully when surface_router is None."""

        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = None

        result = await core._try_kg_fast_path(
            query="entity relationship query",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_kg_fast_path_degrades_on_kg_error(self, mock_kg_orchestrator):
        """_try_kg_fast_path returns None (graceful degrade) when kg_orchestrator.query raises."""
        mock_kg_orchestrator.query.side_effect = RuntimeError("Neo4j connection failed")


        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_kg_decision()

        result = await core._try_kg_fast_path(
            query="organigramma aziendale",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is None  # graceful degrade → caller falls through to ReAct

    @pytest.mark.asyncio
    async def test_kg_fast_path_calls_initialize_when_app_is_none(self, mock_kg_orchestrator):
        """_try_kg_fast_path calls kg_orchestrator.initialize() when app is None."""
        mock_kg_orchestrator.app = None  # not yet initialized
        mock_kg_orchestrator.initialize = AsyncMock()


        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_kg_decision()

        await core._try_kg_fast_path(
            query="who is the company director?",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        mock_kg_orchestrator.initialize.assert_called_once()

    @pytest.mark.asyncio
    async def test_kg_fast_path_sources_contain_surface_kg(self, mock_kg_orchestrator):
        """CoreResult sources from KG fast-path include source_type 'kg'."""

        core = _make_minimal_core(kg_langgraph_orchestrator=mock_kg_orchestrator)
        core._surface_router = MagicMock()
        core._surface_router.decide.return_value = _make_kg_decision()

        result = await core._try_kg_fast_path(
            query="chi è il fondatore?",
            user_context={},
            extracted_entities={},
            start_time=0.0,
        )

        assert result is not None
        assert any(s.get("type") == "kg" for s in result.sources)


# ---------------------------------------------------------------------------
# 2. OrchestratorCore._surface_router attribute
# ---------------------------------------------------------------------------

class TestOrchestratorCoreSurfaceRouterAttr:
    def test_core_has_surface_router_attr(self):
        """OrchestratorCore must expose _surface_router attribute (default None)."""
        core = _make_minimal_core()
        assert hasattr(core, "_surface_router")

    def test_surface_router_defaults_to_none(self):
        """_surface_router defaults to None when not provided."""
        core = _make_minimal_core()
        assert core._surface_router is None

    def test_surface_router_can_be_set_post_init(self):
        """_surface_router can be injected post-init (pattern used by service_initializer)."""
        from backend.services.routing.surface_router import SurfaceRouter
        core = _make_minimal_core()
        router = SurfaceRouter()
        core._surface_router = router
        assert core._surface_router is router


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _make_minimal_core(kg_langgraph_orchestrator=None):
    """Build a minimal OrchestratorCore with all dependencies mocked."""
    from backend.services.rag.agentic.orchestrator_core import OrchestratorCore

    return OrchestratorCore(
        llm_gateway=MagicMock(),
        reasoning_engine=MagicMock(),
        prompt_builder=MagicMock(),
        query_gates=MagicMock(),
        memory_handler=MagicMock(),
        context_window_manager=MagicMock(),
        entity_extractor=MagicMock(),
        kg_retrieval=None,
        semantic_cache=None,
        kg_langgraph_orchestrator=kg_langgraph_orchestrator,
    )
