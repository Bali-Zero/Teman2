"""
Unit tests for OrchestratorCore

Test coverage target: >90% (complex integration)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.orchestrator_core import OrchestratorCore
from backend.services.tools.definitions import AgentState


@pytest.fixture
def mock_llm_gateway():
    """Mock LLMGateway"""
    gateway = MagicMock()
    gateway.create_chat_with_history = MagicMock(return_value=MagicMock())
    return gateway


@pytest.fixture
def mock_reasoning_engine():
    """Mock ReasoningEngine"""
    engine = MagicMock()
    state = MagicMock(spec=AgentState)
    state.final_answer = "Test answer"
    state.steps = []
    state.evidence_score = 0.85
    state.verification_score = 0.9
    state.sources = []

    engine.execute_react_loop = AsyncMock(
        return_value=(state, "gemini-flash", [], TokenUsage())
    )
    return engine


@pytest.fixture
def mock_prompt_builder():
    """Mock SystemPromptBuilder"""
    builder = MagicMock()
    builder.build_system_prompt = MagicMock(return_value="System prompt")
    return builder


@pytest.fixture
def mock_query_gates():
    """Mock QueryGates"""
    gates = MagicMock()
    gates.run_all_gates = MagicMock(return_value=MagicMock(triggered=False))
    return gates


@pytest.fixture
def mock_memory_handler():
    """Mock MemoryHandler"""
    return MagicMock()


@pytest.fixture
def mock_context_window_manager():
    """Mock ContextWindowManager"""
    return MagicMock()


@pytest.fixture
def mock_entity_extractor():
    """Mock EntityExtractionService"""
    extractor = MagicMock()
    extractor.extract_entities = AsyncMock(return_value={"person": "John"})
    return extractor


@pytest.fixture
def mock_kg_retrieval():
    """Mock KGEnhancedRetrieval"""
    return None  # Optional


@pytest.fixture
def mock_semantic_cache():
    """Mock SemanticCache"""
    cache = MagicMock()
    cache.get_cached_result = AsyncMock(return_value=None)
    return cache


@pytest.fixture
def orchestrator_core(
    mock_llm_gateway,
    mock_reasoning_engine,
    mock_prompt_builder,
    mock_query_gates,
    mock_memory_handler,
    mock_context_window_manager,
    mock_entity_extractor,
    mock_kg_retrieval,
    mock_semantic_cache,
):
    """Create OrchestratorCore instance"""
    return OrchestratorCore(
        llm_gateway=mock_llm_gateway,
        reasoning_engine=mock_reasoning_engine,
        prompt_builder=mock_prompt_builder,
        query_gates=mock_query_gates,
        memory_handler=mock_memory_handler,
        context_window_manager=mock_context_window_manager,
        entity_extractor=mock_entity_extractor,
        kg_retrieval=mock_kg_retrieval,
        semantic_cache=mock_semantic_cache,
        db_pool=MagicMock(),
    )


@pytest.mark.asyncio
async def test_check_semantic_cache_hit(orchestrator_core, mock_semantic_cache):
    """Test semantic cache hit"""
    cached_result = {
        "result": {"answer": "Cached answer", "sources": [{"doc": "content"}]}
    }
    mock_semantic_cache.get_cached_result = AsyncMock(return_value=cached_result)

    result = await orchestrator_core.check_semantic_cache(
        query="test", extracted_entities={}, start_time=0.0
    )

    assert result is not None
    assert result.answer == "Cached answer"
    assert result.model_used == "cache"
    assert result.cache_hit is True


@pytest.mark.asyncio
async def test_check_semantic_cache_miss(orchestrator_core, mock_semantic_cache):
    """Test semantic cache miss"""
    mock_semantic_cache.get_cached_result = AsyncMock(return_value=None)

    result = await orchestrator_core.check_semantic_cache(
        query="test", extracted_entities={}, start_time=0.0
    )

    assert result is None


@pytest.mark.asyncio
async def test_extract_entities_and_kg_context(orchestrator_core, mock_entity_extractor):
    """Test entity and KG context extraction"""
    entities, context = await orchestrator_core.extract_entities_and_kg_context("test query")

    assert entities == {"person": "John"}
    assert isinstance(context, str)
    mock_entity_extractor.extract_entities.assert_called_once_with("test query")


@pytest.mark.asyncio
async def test_extract_entities_and_kg_context_with_kg(orchestrator_core, mock_entity_extractor):
    """Test entity and KG context extraction with KG retrieval"""
    # Add KG retrieval
    mock_kg = MagicMock()
    kg_context = MagicMock()
    kg_context.graph_summary = "KG summary"
    kg_context.entities_found = ["entity1"]
    kg_context.relationships = ["rel1"]
    mock_kg.get_context_for_query = AsyncMock(return_value=kg_context)
    orchestrator_core.kg_retrieval = mock_kg

    entities, context = await orchestrator_core.extract_entities_and_kg_context("test query")

    assert "KNOWN ENTITIES" in context
    assert "KG summary" in context
    mock_kg.get_context_for_query.assert_called_once()


@pytest.mark.asyncio
async def test_execute_react_loop_success(
    orchestrator_core, mock_reasoning_engine, mock_llm_gateway
):
    """Test successful ReAct loop execution"""
    state, model, token_usage, duration = await orchestrator_core.execute_react_loop(
        state=MagicMock(spec=AgentState),
        chat=MagicMock(),
        system_prompt="System prompt",
        query="test query",
        user_id="user123",
        model_tier="FLASH",
        tool_execution_counter={"count": 0},
    )

    assert state is not None
    assert model == "gemini-flash"
    assert isinstance(token_usage, TokenUsage)
    assert duration >= 0
    mock_reasoning_engine.execute_react_loop.assert_called_once()


@pytest.mark.asyncio
async def test_process_query_core_gate_triggered(orchestrator_core, mock_query_gates):
    """Test process_query_core with gate triggered"""
    gate_result = MagicMock()
    gate_result.triggered = True
    gate_result.response = "Gate response"
    mock_query_gates.run_all_gates = MagicMock(return_value=gate_result)

    with patch.object(
        orchestrator_core.query_gates,
        "gate_result_to_core_result",
        return_value=MagicMock(answer="Gate response"),
    ):
        result = await orchestrator_core.process_query_core(
            query="test",
            user_id="user123",
            conversation_history=None,
            start_time=0.0,
        )

        assert result.answer == "Gate response"
        mock_query_gates.run_all_gates.assert_called_once()


@pytest.mark.asyncio
async def test_process_query_core_full_flow(orchestrator_core):
    """Test complete process_query_core flow"""
    # Setup mocks
    orchestrator_core.query_gates.run_all_gates.return_value = MagicMock(triggered=False)
    orchestrator_core.semantic_cache.get_cached_result = AsyncMock(return_value=None)

    with patch.object(
        orchestrator_core.context_manager, "get_full_context", new_callable=AsyncMock
    ) as mock_context, patch.object(
        orchestrator_core, "extract_entities_and_kg_context", new_callable=AsyncMock
    ) as mock_extract, patch.object(
        orchestrator_core, "execute_react_loop", new_callable=AsyncMock
    ) as mock_react, patch.object(
        orchestrator_core.metrics_manager, "extract_timings_from_state"
    ) as mock_timings, patch.object(
        orchestrator_core.metrics_manager, "extract_collections_from_state"
    ) as mock_collections, patch.object(
        orchestrator_core.metrics_manager, "extract_sources_from_state"
    ) as mock_sources, patch.object(
        orchestrator_core.metrics_manager, "calculate_context_used"
    ) as mock_context_used, patch.object(
        orchestrator_core.metrics_manager, "record_rag_metrics"
    ), patch.object(
        orchestrator_core.metrics_manager, "record_token_usage"
    ), patch.object(
        orchestrator_core.metrics_manager, "log_query_completion"
    ), patch.object(
        orchestrator_core.response_builder, "build_core_result"
    ) as mock_build:

        mock_context.return_value = ({}, [])
        mock_extract.return_value = ({}, "")
        state = MagicMock(spec=AgentState)
        state.final_answer = "Answer"
        state.steps = []
        mock_react.return_value = (state, "gemini-flash", TokenUsage(), 1.0)
        mock_timings.return_value = {"total": 1.0}
        mock_collections.return_value = set()
        mock_sources.return_value = []
        mock_context_used.return_value = 100
        mock_build.return_value = MagicMock(answer="Answer")

        result = await orchestrator_core.process_query_core(
            query="test query",
            user_id="user123",
            conversation_history=None,
            start_time=0.0,
        )

        assert result is not None
        mock_context.assert_called_once()
        mock_extract.assert_called_once()
        mock_react.assert_called_once()
