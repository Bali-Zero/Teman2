"""
Comprehensive unit tests for backend/services/rag/agentic/orchestrator_core.py
Covers: OrchestratorCore init, check_faq_cache, check_semantic_cache,
        extract_entities_and_kg_context, _format_workflow_for_prompt,
        _track_workflow, execute_react_loop, process_query_core.

SCAR WARNING: Always mock context_manager.get_basic_context with AsyncMock
returning empty profiles/facts to prevent real db_pool usage.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.schema import CoreResult
from backend.services.tools.definitions import AgentState


# ---------------------------------------------------------------------------
# Common patches
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _patch_tracing():
    """Disable tracing for all tests."""
    with patch("backend.services.rag.agentic.orchestrator_core.trace_span") as ts, \
         patch("backend.services.rag.agentic.orchestrator_core.set_span_attribute"), \
         patch("backend.services.rag.agentic.orchestrator_core.set_span_status"):
        ts.return_value.__enter__ = MagicMock()
        ts.return_value.__exit__ = MagicMock(return_value=False)
        yield


@pytest.fixture(autouse=True)
def _patch_traceable():
    """Disable langsmith traceable decorator."""
    with patch("backend.services.rag.agentic.orchestrator_core.traceable", lambda **kw: lambda f: f):
        yield


@pytest.fixture
def mock_deps():
    """Create all mock dependencies for OrchestratorCore."""
    llm_gw = MagicMock()
    reasoning = MagicMock()
    prompt_builder = MagicMock()
    query_gates = MagicMock()
    memory_handler = MagicMock()
    ctx_window = MagicMock()
    entity_ext = MagicMock()
    entity_ext.extract_entities = AsyncMock(return_value={})
    kg_retrieval = None
    semantic_cache = None
    faq_cache = None
    db_pool = None

    return {
        "llm_gateway": llm_gw,
        "reasoning_engine": reasoning,
        "prompt_builder": prompt_builder,
        "query_gates": query_gates,
        "memory_handler": memory_handler,
        "context_window_manager": ctx_window,
        "entity_extractor": entity_ext,
        "kg_retrieval": kg_retrieval,
        "semantic_cache": semantic_cache,
        "faq_cache": faq_cache,
        "db_pool": db_pool,
    }


@pytest.fixture
def orch(mock_deps):
    """Create OrchestratorCore with all mocked deps."""
    with patch("backend.services.rag.agentic.orchestrator_core.QueryPlanner"), \
         patch("backend.services.rag.agentic.orchestrator_core.MultiAgentCoordinator"), \
         patch("backend.services.rag.agentic.orchestrator_core.requires_multi_agent", return_value=False), \
         patch("backend.services.rag.agentic.orchestrator_core.KGAutoExpansion"):
        from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
        core = OrchestratorCore(**mock_deps)
        # SCAR: Mock context_manager.get_basic_context
        core.context_manager.get_basic_context = AsyncMock(return_value={
            "profiles": [],
            "facts": [],
        })
        return core


# ============================================================================
# check_faq_cache
# ============================================================================

class TestCheckFaqCache:

    @pytest.mark.asyncio
    async def test_no_faq_cache_returns_none(self, orch):
        orch.faq_cache = None
        result = await orch.check_faq_cache("test", {}, time.time())
        assert result is None

    @pytest.mark.asyncio
    async def test_faq_cache_miss(self, orch):
        orch.faq_cache = AsyncMock()
        orch.faq_cache.get = AsyncMock(return_value=None)
        with patch("backend.app.metrics.faq_cache_misses_total", MagicMock(), create=True):
            result = await orch.check_faq_cache("unknown query", {}, time.time())
        assert result is None

    @pytest.mark.asyncio
    async def test_faq_cache_hit(self, orch):
        orch.faq_cache = AsyncMock()
        orch.faq_cache.get = AsyncMock(return_value={
            "answer": "KITAS costs Rp 10M",
            "metadata": {"domain": "visa", "source": "team_qa"},
        })
        with patch("backend.app.metrics.faq_cache_hits_total", MagicMock(), create=True):
            result = await orch.check_faq_cache("quanto costa kitas?", {}, time.time())
        assert result is not None
        assert isinstance(result, CoreResult)
        assert result.answer == "KITAS costs Rp 10M"
        assert result.model_used == "faq_cache"

    @pytest.mark.asyncio
    async def test_faq_cache_exception_returns_none(self, orch):
        orch.faq_cache = AsyncMock()
        orch.faq_cache.get = AsyncMock(side_effect=RuntimeError("redis down"))
        with patch("backend.app.metrics.faq_cache_errors_total", MagicMock(), create=True):
            result = await orch.check_faq_cache("test", {}, time.time())
        assert result is None


# ============================================================================
# check_semantic_cache
# ============================================================================

class TestCheckSemanticCache:

    @pytest.mark.asyncio
    async def test_no_cache_returns_none(self, orch):
        orch.semantic_cache = None
        result = await orch.check_semantic_cache("test", {}, time.time())
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_miss(self, orch):
        orch.semantic_cache = AsyncMock()
        orch.semantic_cache.get_cached_result = AsyncMock(return_value=None)
        result = await orch.check_semantic_cache("test", {}, time.time())
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self, orch):
        orch.semantic_cache = AsyncMock()
        orch.semantic_cache.get_cached_result = AsyncMock(return_value={
            "result": {"answer": "cached answer", "sources": [{"title": "doc1"}]},
        })
        result = await orch.check_semantic_cache("test", {"entity": "visa"}, time.time())
        assert result is not None
        assert isinstance(result, CoreResult)
        assert result.answer == "cached answer"
        assert result.cache_hit is True

    @pytest.mark.asyncio
    async def test_cache_error_returns_none(self, orch):
        orch.semantic_cache = AsyncMock()
        orch.semantic_cache.get_cached_result = AsyncMock(side_effect=RuntimeError("fail"))
        result = await orch.check_semantic_cache("test", {}, time.time())
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_with_embedding(self, orch):
        """Test semantic cache with retriever embedding generation."""
        orch.semantic_cache = AsyncMock()
        orch.semantic_cache.get_cached_result = AsyncMock(return_value=None)
        mock_retriever = MagicMock()
        mock_retriever.embedder.generate_query_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        orch.retriever = mock_retriever

        result = await orch.check_semantic_cache("test", {}, time.time())
        assert result is None  # Miss, but embedding was computed


# ============================================================================
# extract_entities_and_kg_context
# ============================================================================

class TestExtractEntitiesAndKgContext:

    @pytest.mark.asyncio
    async def test_entity_extraction_only(self, orch):
        orch.entity_extractor.extract_entities = AsyncMock(return_value={"visa_type": "KITAS"})
        orch.kg_retrieval = None
        orch.kg_langgraph_orchestrator = None

        entities, context_str, workflow = await orch.extract_entities_and_kg_context("KITAS question")
        assert entities["visa_type"] == "KITAS"
        assert "KITAS" in context_str

    @pytest.mark.asyncio
    async def test_entity_extraction_failure_returns_empty(self, orch):
        orch.entity_extractor.extract_entities = AsyncMock(side_effect=RuntimeError("NLP fail"))
        orch.kg_retrieval = None
        orch.kg_langgraph_orchestrator = None

        entities, context_str, workflow = await orch.extract_entities_and_kg_context("test")
        assert entities == {}

    @pytest.mark.asyncio
    async def test_kg_context_included(self, orch):
        orch.entity_extractor.extract_entities = AsyncMock(return_value={})
        mock_kg = MagicMock()
        mock_kg.get_context_for_query = AsyncMock(return_value=MagicMock(
            graph_summary="KG: KITAS requires sponsor",
            entities_found=["KITAS"],
            relationships=["REQUIRES"],
        ))
        orch.kg_retrieval = mock_kg
        orch.kg_langgraph_orchestrator = None

        _, context_str, _ = await orch.extract_entities_and_kg_context("test")
        assert "KG: KITAS requires sponsor" in context_str

    @pytest.mark.asyncio
    async def test_kg_failure_graceful(self, orch):
        orch.entity_extractor.extract_entities = AsyncMock(return_value={})
        mock_kg = MagicMock()
        mock_kg.get_context_for_query = AsyncMock(side_effect=RuntimeError("Neo4j down"))
        orch.kg_retrieval = mock_kg
        orch.kg_langgraph_orchestrator = None

        entities, context_str, workflow = await orch.extract_entities_and_kg_context("test")
        assert workflow is None


# ============================================================================
# _format_workflow_for_prompt
# ============================================================================

class TestFormatWorkflowForPrompt:

    def test_basic_workflow(self, orch):
        workflow = {
            "type": "visa_application",
            "name": "KITAS Application",
            "steps": [
                {"step": 1, "action": "Gather documents"},
                {"step": 2, "action": "Submit application"},
            ],
            "source": "kg_langgraph",
            "confidence": 0.85,
        }
        result = orch._format_workflow_for_prompt(workflow)
        assert "KITAS Application" in result
        assert "Gather documents" in result
        assert "Submit application" in result
        assert "85%" in result

    def test_workflow_with_details(self, orch):
        workflow = {
            "type": "process",
            "name": "PT PMA Setup",
            "steps": [
                {"step": 1, "action": "Register", "details": {"requirement": "Passport"}},
                {"step": 2, "action": "Pay fees", "details": {"location": "BKPM Office"}},
                {"step": 3, "action": "Wait", "details": {"processing_time": "14 days"}},
            ],
            "source": "kg",
            "confidence": 0.7,
        }
        result = orch._format_workflow_for_prompt(workflow)
        assert "Passport" in result
        assert "BKPM Office" in result
        assert "14 days" in result

    def test_workflow_with_low_confidence_warning(self, orch):
        workflow = {
            "type": "workflow",
            "name": "Test",
            "steps": [],
            "source": "kg",
            "confidence": 0.3,
            "confidence_breakdown": {
                "warning_level": "low",
                "warning_message": "Limited data available",
                "unique_source_count": 1,
                "relationship_strength_avg": 0.2,
            },
        }
        result = orch._format_workflow_for_prompt(workflow)
        assert "WARNING" in result
        assert "Limited data" in result

    def test_workflow_empty_steps(self, orch):
        workflow = {
            "type": "workflow",
            "name": "Empty",
            "steps": [],
            "source": "unknown",
            "confidence": 0.0,
        }
        result = orch._format_workflow_for_prompt(workflow)
        assert "Empty" in result
        assert "IMPORTANT" in result


# ============================================================================
# _track_workflow
# ============================================================================

class TestTrackWorkflow:

    @pytest.mark.asyncio
    async def test_no_db_pool_skips(self, orch):
        orch.db_pool = None
        await orch._track_workflow(query="test", workflow={"type": "visa"})
        # Should return without error

    @pytest.mark.asyncio
    async def test_with_db_pool_logs(self, orch):
        mock_pool = MagicMock()
        mock_repo = AsyncMock()
        orch.db_pool = mock_pool

        with patch("backend.services.rag.agentic.orchestrator_core.WorkflowAnalyticsRepository") as MockRepo:
            MockRepo.return_value = mock_repo
            await orch._track_workflow(
                query="visa question",
                workflow={"type": "visa", "name": "KITAS", "steps": [{"step": 1}], "source": "kg", "confidence": 0.9},
                execution_time_ms=150,
                user_email="test@test.com",
            )
            mock_repo.log_workflow.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_db_error_handled(self, orch):
        mock_pool = MagicMock()
        orch.db_pool = mock_pool

        with patch("backend.services.rag.agentic.orchestrator_core.WorkflowAnalyticsRepository") as MockRepo:
            MockRepo.return_value.log_workflow = AsyncMock(side_effect=RuntimeError("db fail"))
            await orch._track_workflow(query="test", workflow={"type": "x"})
            # Should not raise


# ============================================================================
# execute_react_loop
# ============================================================================

class TestExecuteReactLoop:

    @pytest.mark.asyncio
    async def test_successful_loop(self, orch):
        from backend.services.llm_clients.pricing import TokenUsage

        state = AgentState(query="hello", max_steps=3)
        state.final_answer = "Hi!"
        state.steps = []

        orch.reasoning_engine.execute_react_loop = AsyncMock(return_value=(
            state, "gemini-flash", [], TokenUsage(),
        ))

        with patch("backend.services.rag.agentic.orchestrator_core.wrap_query_with_language_instruction", return_value="hello"):
            result_state, model, usage, duration = await orch.execute_react_loop(
                state=state,
                chat=MagicMock(),
                system_prompt="sys",
                query="hello",
                user_id="u1",
                model_tier="flash",
                tool_execution_counter={"count": 0},
            )
        assert model == "gemini-flash"

    @pytest.mark.asyncio
    async def test_loop_runtime_error_propagated(self, orch):
        state = AgentState(query="fail")
        orch.reasoning_engine.execute_react_loop = AsyncMock(side_effect=RuntimeError("boom"))

        with patch("backend.services.rag.agentic.orchestrator_core.wrap_query_with_language_instruction", return_value="fail"):
            with pytest.raises(RuntimeError):
                await orch.execute_react_loop(
                    state=state,
                    chat=MagicMock(),
                    system_prompt="sys",
                    query="fail",
                    user_id="u1",
                    model_tier="flash",
                    tool_execution_counter={"count": 0},
                )

    @pytest.mark.asyncio
    async def test_loop_unexpected_error_wrapped(self, orch):
        state = AgentState(query="fail")
        orch.reasoning_engine.execute_react_loop = AsyncMock(side_effect=TypeError("unexpected"))

        with patch("backend.services.rag.agentic.orchestrator_core.wrap_query_with_language_instruction", return_value="fail"):
            with pytest.raises(RuntimeError, match="ReAct loop failed"):
                await orch.execute_react_loop(
                    state=state,
                    chat=MagicMock(),
                    system_prompt="sys",
                    query="fail",
                    user_id="u1",
                    model_tier="flash",
                    tool_execution_counter={"count": 0},
                )


# ============================================================================
# OrchestratorCore init
# ============================================================================

class TestOrchestratorCoreInit:

    def test_init_without_db_pool(self, mock_deps):
        mock_deps["db_pool"] = None
        with patch("backend.services.rag.agentic.orchestrator_core.QueryPlanner"), \
             patch("backend.services.rag.agentic.orchestrator_core.MultiAgentCoordinator"), \
             patch("backend.services.rag.agentic.orchestrator_core.KGAutoExpansion"):
            from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
            core = OrchestratorCore(**mock_deps)
        assert core._kg_auto_expansion is None

    def test_init_with_db_pool(self, mock_deps):
        mock_deps["db_pool"] = MagicMock()
        with patch("backend.services.rag.agentic.orchestrator_core.QueryPlanner"), \
             patch("backend.services.rag.agentic.orchestrator_core.MultiAgentCoordinator"), \
             patch("backend.services.rag.agentic.orchestrator_core.KGAutoExpansion") as MockKG:
            MockKG.return_value = MagicMock()
            from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
            core = OrchestratorCore(**mock_deps)
        assert core._kg_auto_expansion is not None

    def test_init_kg_auto_expansion_fails_gracefully(self, mock_deps):
        mock_deps["db_pool"] = MagicMock()
        with patch("backend.services.rag.agentic.orchestrator_core.QueryPlanner"), \
             patch("backend.services.rag.agentic.orchestrator_core.MultiAgentCoordinator"), \
             patch("backend.services.rag.agentic.orchestrator_core.KGAutoExpansion", side_effect=RuntimeError("init fail")):
            from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
            core = OrchestratorCore(**mock_deps)
        assert core._kg_auto_expansion is None
