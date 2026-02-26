"""
Unit tests for OrchestratorMetricsManager

Test coverage target: >95%
"""

from unittest.mock import MagicMock, patch

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.orchestrator_metrics import OrchestratorMetricsManager
from backend.services.tools.definitions import AgentState, AgentStep, ToolCall


@pytest.fixture
def metrics_manager():
    """Create OrchestratorMetricsManager instance"""
    return OrchestratorMetricsManager()


@pytest.fixture
def mock_state_with_steps():
    """Create mock AgentState with steps"""
    state = MagicMock(spec=AgentState)
    state.steps = []

    # Step 1: vector_search tool
    step1 = MagicMock(spec=AgentStep)
    step1.action = MagicMock(spec=ToolCall)
    step1.action.tool_name = "vector_search"
    step1.action.execution_time = 0.5
    step1.action.arguments = {"collection": "test_collection"}
    step1.action.result = {"doc1": "content1"}
    step1.observation = "Found 1 document"
    state.steps.append(step1)

    # Step 2: calculator tool
    step2 = MagicMock(spec=AgentStep)
    step2.action = MagicMock(spec=ToolCall)
    step2.action.tool_name = "calculator"
    step2.action.execution_time = 0.1
    step2.action.arguments = {}
    step2.action.result = "42"
    step2.observation = "Result: 42"
    state.steps.append(step2)

    # Step 3: No action
    step3 = MagicMock(spec=AgentStep)
    step3.action = None
    step3.observation = "Final answer"
    state.steps.append(step3)

    state.final_answer = "The answer is 42"
    state.evidence_score = 0.85
    state.verification_score = 0.9

    return state


@pytest.fixture
def mock_state_no_tools():
    """Create mock AgentState without tools"""
    state = MagicMock(spec=AgentState)
    state.steps = []
    state.final_answer = "Direct answer"
    state.evidence_score = 0.7
    return state


def test_extract_timings_from_state_with_tools(metrics_manager, mock_state_with_steps):
    """Test timing extraction with tool executions"""
    timings = metrics_manager.extract_timings_from_state(
        state=mock_state_with_steps, reasoning_duration=2.0, start_time=0.0
    )

    assert timings["total"] >= 0
    assert timings["reasoning"] == 2.0
    assert timings["search"] == 0.5  # vector_search time
    assert timings["tools"] == 0.6  # 0.5 + 0.1
    assert timings["llm"] == 1.4  # 2.0 - 0.6


def test_extract_timings_from_state_no_tools(metrics_manager, mock_state_no_tools):
    """Test timing extraction without tools"""
    timings = metrics_manager.extract_timings_from_state(
        state=mock_state_no_tools, reasoning_duration=1.5, start_time=0.0
    )

    assert timings["reasoning"] == 1.5
    assert timings["tools"] == 0.0
    assert timings["llm"] == 1.5  # All time is LLM


def test_extract_collections_from_state(metrics_manager, mock_state_with_steps):
    """Test collection extraction from state"""
    collections = metrics_manager.extract_collections_from_state(mock_state_with_steps)

    assert "test_collection" in collections
    assert len(collections) == 1


def test_extract_collections_from_state_no_vector_search(metrics_manager, mock_state_no_tools):
    """Test collection extraction without vector_search"""
    collections = metrics_manager.extract_collections_from_state(mock_state_no_tools)

    assert len(collections) == 0


def test_extract_sources_from_state(metrics_manager, mock_state_with_steps):
    """Test source extraction from state"""
    sources = metrics_manager.extract_sources_from_state(mock_state_with_steps)

    assert len(sources) == 2
    assert {"doc1": "content1"} in sources
    assert "42" in sources


def test_extract_sources_from_state_with_sources_attr(mock_state_with_steps):
    """Test source extraction when state has sources attribute"""
    mock_state_with_steps.sources = [{"source": "predefined"}]
    sources = OrchestratorMetricsManager().extract_sources_from_state(mock_state_with_steps)

    assert sources == [{"source": "predefined"}]


def test_calculate_context_used(metrics_manager, mock_state_with_steps):
    """Test context token calculation"""
    context_used = metrics_manager.calculate_context_used(mock_state_with_steps)

    assert context_used == len("Found 1 document") + len("Result: 42") + len("Final answer")


def test_record_rag_metrics(metrics_manager):
    """Test RAG metrics recording"""
    state = MagicMock()
    state.evidence_score = 0.85

    with patch(
        "backend.services.rag.agentic.orchestrator_metrics.metrics_collector"
    ) as mock_metrics:
        metrics_manager.record_rag_metrics(
            state=state,
            collections_used={"test_collection"},
            tool_execution_count=2,
            context_used=100,
            execution_time=1.5,
            sources=[{"doc": "content"}],
        )

        assert mock_metrics.record_rag_query.called
        assert mock_metrics.record_rag_detailed_metrics.called


def test_record_token_usage(metrics_manager):
    """Test token usage recording"""
    token_usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
    )

    with patch(
        "backend.services.rag.agentic.orchestrator_metrics.metrics_collector"
    ) as mock_metrics:
        metrics_manager.record_token_usage(
            model_used="gemini-flash", token_usage=token_usage, endpoint="chat"
        )

        mock_metrics.record_llm_token_usage.assert_called_once_with(
            model="gemini-flash",
            prompt_tokens=100,
            completion_tokens=50,
            cost_usd=0.001,
            endpoint="chat",
        )


def test_log_query_completion(metrics_manager, mock_state_with_steps):
    """Test query completion logging"""
    token_usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        cost_usd=0.001,
    )

    with patch("backend.services.rag.agentic.orchestrator_metrics.logger") as mock_logger:
        metrics_manager.log_query_completion(
            user_id="user123",
            query="test query",
            model_used="gemini-flash",
            execution_time=1.5,
            state=mock_state_with_steps,
            collections_used={"test_collection"},
            tool_execution_count=2,
            token_usage=token_usage,
        )

        mock_logger.info.assert_called_once()
        call_args = mock_logger.info.call_args
        assert "AgenticRAG" in call_args[0][0]
        assert call_args[1]["extra"]["user_id"] == "user123"
        assert call_args[1]["extra"]["model_used"] == "gemini-flash"
