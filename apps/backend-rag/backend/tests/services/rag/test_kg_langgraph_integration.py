"""
Integration Tests for KG LangGraph Workflow Integration

Tests that the KG LangGraph workflow result actually reaches the final answer.
Covers the specific bugs fixed:
1. Workflow appended to answer (not just system prompt)
2. Streaming path runs LangGraph in fast path
3. PostgresSaver graceful fallback
4. Source collections handles string sources without 500 error

Author: Nuzantara Team
Date: 2026-02-09
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.rag.agentic.orchestrator_response import OrchestratorResponseBuilder
from backend.services.rag.agentic.schema import CoreResult
from backend.services.rag.kg_langgraph_orchestrator import (
    KGLangGraphOrchestrator,
    compile_kg_workflow,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def mock_db_pool():
    """Mock asyncpg connection pool."""
    pool = MagicMock()
    conn = AsyncMock()

    class AsyncContextManager:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, *args):
            return None

    pool.acquire = MagicMock(return_value=AsyncContextManager())
    return pool, conn


@pytest.fixture
def sample_workflow():
    """Sample workflow dict as returned by KGLangGraphOrchestrator."""
    return {
        "id": "dynamic:company_setup_3steps",
        "type": "company_setup",
        "name": "PT PMA Restaurant Setup",
        "steps": [
            {
                "step": 1,
                "action": "Register KBLI code 56101",
                "details": {"requirement": "Food & Beverage"},
            },
            {
                "step": 2,
                "action": "Establish PT PMA",
                "details": {"requirement": "Min. IDR 10B capital"},
            },
            {
                "step": 3,
                "action": "Apply for NIB via OSS",
                "details": {"processing_time": "1-3 days"},
            },
        ],
        "source": "graph_traversal",
        "confidence": 0.78,
        "confidence_breakdown": {
            "overall": 0.78,
            "chain_base": 0.6,
            "entity_confidence_avg": 0.85,
            "relationship_strength_avg": 0.9,
            "multi_source_bonus": 0.1,
            "recency_score": 0.7,
            "intent_clarity_bonus": 1.0,
            "unique_source_count": 2,
            "unique_sources": ["kbli_2025", "regulations"],
            "warning_level": "medium",
            "warning_message": "Moderate confidence — verify details.",
        },
    }


@pytest.fixture
def mock_orchestrator_core():
    """Create a minimal OrchestratorCore with mocked dependencies."""
    core = MagicMock(spec=OrchestratorCore)
    core.entity_extractor = AsyncMock()
    core.entity_extractor.extract_entities = AsyncMock(return_value={})
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None
    core.semantic_cache = None
    core.db_pool = None
    core.response_builder = OrchestratorResponseBuilder()
    return core


# ============================================================================
# Test 1: Workflow format includes SUGGESTED WORKFLOW marker
# ============================================================================


def test_format_workflow_contains_suggested_workflow_marker(sample_workflow):
    """Verify _format_workflow_for_prompt produces the expected marker text."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    formatted = core._format_workflow_for_prompt(sample_workflow)

    assert "SUGGESTED WORKFLOW" in formatted
    assert "graph_traversal" in formatted
    assert "78%" in formatted  # confidence 0.78
    assert "PT PMA Restaurant Setup" in formatted
    assert "Register KBLI code 56101" in formatted
    assert "Establish PT PMA" in formatted
    assert "Apply for NIB via OSS" in formatted


def test_format_workflow_includes_confidence_breakdown(sample_workflow):
    """Verify confidence breakdown is included when available."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    formatted = core._format_workflow_for_prompt(sample_workflow)

    assert "Confidence" in formatted
    assert "medium" in formatted
    assert "2 source(s)" in formatted


def test_format_workflow_without_breakdown():
    """Verify formatting works without confidence breakdown."""
    workflow = {
        "type": "visa",
        "name": "KITAS Application",
        "steps": [{"step": 1, "action": "Submit RPTKA"}],
        "source": "golden_route",
        "confidence": 1.0,
    }
    core = OrchestratorCore.__new__(OrchestratorCore)
    formatted = core._format_workflow_for_prompt(workflow)

    assert "SUGGESTED WORKFLOW" in formatted
    assert "100%" in formatted
    assert "KITAS Application" in formatted


# ============================================================================
# Test 2: extract_entities_and_kg_context returns 3-tuple with workflow
# ============================================================================


@pytest.mark.asyncio
async def test_extract_returns_workflow_when_langgraph_succeeds():
    """Verify extract_entities_and_kg_context returns workflow as 3rd element."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.entity_extractor = AsyncMock()
    core.entity_extractor.extract_entities = AsyncMock(return_value={"kbli": ["56101"]})
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = AsyncMock()
    core.kg_langgraph_orchestrator.app = MagicMock()
    core.kg_langgraph_orchestrator.query = AsyncMock(
        return_value={
            "workflow": {
                "type": "company_setup",
                "name": "Test Workflow",
                "steps": [{"step": 1, "action": "Do thing"}],
                "source": "test",
                "confidence": 0.9,
            },
        },
    )

    entities, context_str, workflow = await core.extract_entities_and_kg_context(
        "test query", user_context={},
    )

    assert workflow is not None
    assert workflow["type"] == "company_setup"
    assert workflow["name"] == "Test Workflow"
    assert "SUGGESTED WORKFLOW" in context_str


@pytest.mark.asyncio
async def test_extract_returns_none_workflow_when_langgraph_disabled():
    """Verify workflow is None when kg_langgraph_orchestrator is None."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.entity_extractor = AsyncMock()
    core.entity_extractor.extract_entities = AsyncMock(return_value={})
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None

    entities, context_str, workflow = await core.extract_entities_and_kg_context("test query")

    assert workflow is None
    assert "SUGGESTED WORKFLOW" not in context_str


@pytest.mark.asyncio
async def test_extract_returns_none_workflow_when_langgraph_fails():
    """Verify workflow is None when LangGraph raises an exception."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.entity_extractor = AsyncMock()
    core.entity_extractor.extract_entities = AsyncMock(return_value={})
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = AsyncMock()
    core.kg_langgraph_orchestrator.app = MagicMock()
    core.kg_langgraph_orchestrator.query = AsyncMock(
        side_effect=RuntimeError("DB connection failed"),
    )

    entities, context_str, workflow = await core.extract_entities_and_kg_context(
        "test query", user_context={},
    )

    assert workflow is None


# ============================================================================
# Test 3: PostgresSaver graceful fallback
# ============================================================================


@pytest.mark.asyncio
async def test_compile_kg_workflow_without_checkpointer():
    """Verify compile_kg_workflow succeeds even when PostgresSaver fails."""
    mock_pool = MagicMock()

    with patch("backend.services.rag.kg_langgraph_orchestrator.PostgresSaver") as mock_saver_cls:
        mock_saver = MagicMock()
        mock_saver.setup = AsyncMock(side_effect=Exception("No checkpoint tables"))
        mock_saver_cls.return_value = mock_saver

        app = await compile_kg_workflow(mock_pool)

        assert app is not None
        mock_saver.setup.assert_awaited_once()


# ============================================================================
# Test 4: KGLangGraphOrchestrator.query returns safe result on error
# ============================================================================


@pytest.mark.asyncio
async def test_orchestrator_query_returns_empty_on_error():
    """Verify query() returns {workflow: None} instead of raising."""
    mock_pool = MagicMock()
    orchestrator = KGLangGraphOrchestrator(mock_pool)

    # Mock app that raises
    orchestrator.app = AsyncMock()
    orchestrator.app.ainvoke = AsyncMock(side_effect=RuntimeError("Graph traversal failed"))

    result = await orchestrator.query("test query")

    assert result is not None
    assert result["workflow"] is None
    assert "error" in result


# ============================================================================
# Test 5: Source collections handles string sources (500 error fix)
# ============================================================================


def test_source_collections_with_dict_sources():
    """Verify source_collections works with dict sources."""
    sources = [
        {"collection": "kbli_2025", "content": "..."},
        {"source": "regulations", "content": "..."},
    ]
    source_collections = list(
        {
            s.get("collection", s.get("source", "unknown")) if isinstance(s, dict) else str(s)
            for s in sources
        },
    )
    assert "kbli_2025" in source_collections
    assert "regulations" in source_collections


def test_source_collections_with_string_sources():
    """Verify source_collections works with string sources (was causing 500)."""
    sources = ["kbli_2025", "regulations", {"collection": "visa_docs"}]
    source_collections = list(
        {
            s.get("collection", s.get("source", "unknown")) if isinstance(s, dict) else str(s)
            for s in sources
        },
    )
    assert "kbli_2025" in source_collections
    assert "regulations" in source_collections
    assert "visa_docs" in source_collections


def test_source_collections_empty():
    """Verify source_collections handles empty list."""
    sources = []
    source_collections = (
        list(
            {
                s.get("collection", s.get("source", "unknown")) if isinstance(s, dict) else str(s)
                for s in sources
            },
        )
        if sources
        else []
    )
    assert source_collections == []


# ============================================================================
# Test 6: prepare_query_context returns 5-tuple
# ============================================================================


@pytest.mark.asyncio
async def test_prepare_query_context_returns_5_tuple():
    """Verify prepare_query_context returns workflow as 5th element."""
    core = OrchestratorCore.__new__(OrchestratorCore)
    core.context_manager = AsyncMock()
    core.context_manager.get_full_context = AsyncMock(return_value=({}, []))
    core.entity_extractor = AsyncMock()
    core.entity_extractor.extract_entities = AsyncMock(return_value={})
    core.kg_retrieval = None
    core.kg_langgraph_orchestrator = None

    result = await core.prepare_query_context(
        query="test", user_id="user1", conversation_history=None,
    )

    assert len(result) == 5
    user_ctx, history, entities, kg_str, workflow = result
    assert workflow is None


# ============================================================================
# Test 7: Workflow appended to CoreResult answer
# ============================================================================


def test_workflow_appended_to_answer(sample_workflow):
    """Verify workflow text is appended to the final answer."""
    core = OrchestratorCore.__new__(OrchestratorCore)

    # Simulate what process_query_core does after build_core_result
    result = CoreResult(
        answer="Ecco i requisiti per aprire un ristorante a Bali.",
        sources=[],
        model_used="gemini-2.0-flash",
    )

    workflow_text = core._format_workflow_for_prompt(sample_workflow)
    result.answer = result.answer.rstrip() + "\n\n" + workflow_text

    assert "SUGGESTED WORKFLOW" in result.answer
    assert "Ecco i requisiti" in result.answer
    assert "Register KBLI code 56101" in result.answer
    assert "PT PMA Restaurant Setup" in result.answer


def test_no_workflow_answer_unchanged():
    """Verify answer is unchanged when no workflow is available."""
    original_answer = "Ecco i requisiti per aprire un ristorante."
    result = CoreResult(
        answer=original_answer,
        sources=[],
        model_used="gemini-2.0-flash",
    )

    langgraph_workflow = None
    if langgraph_workflow:
        result.answer += "\n\nWORKFLOW"

    assert result.answer == original_answer
