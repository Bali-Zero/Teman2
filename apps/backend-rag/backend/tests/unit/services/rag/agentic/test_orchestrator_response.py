"""
Unit tests for OrchestratorResponseBuilder

Test coverage target: >95%
"""

import time
from unittest.mock import MagicMock

import pytest

from backend.services.llm_clients.pricing import TokenUsage
from backend.services.rag.agentic.orchestrator_response import OrchestratorResponseBuilder
from backend.services.tools.definitions import AgentState


@pytest.fixture
def response_builder():
    """Create OrchestratorResponseBuilder instance"""
    return OrchestratorResponseBuilder()


@pytest.fixture
def mock_state():
    """Create mock AgentState"""
    state = MagicMock(spec=AgentState)
    state.final_answer = "Test answer"
    state.evidence_score = 0.85
    state.verification_score = 0.9
    return state


@pytest.fixture
def mock_token_usage():
    """Create mock TokenUsage"""
    usage = TokenUsage()
    usage.prompt_tokens = 100
    usage.completion_tokens = 50
    usage.total_tokens = 150
    usage.cost_usd = 0.001
    return usage


def test_build_core_result_success(response_builder, mock_state, mock_token_usage):
    """Test successful CoreResult building"""
    sources = [{"doc": "content"}]
    extracted_entities = {"person": "John", "location": "Bali"}
    timings = {"total": 1.5, "llm": 1.0, "search": 0.5}
    start_time = time.time()

    result = response_builder.build_core_result(
        state=mock_state,
        sources=sources,
        extracted_entities=extracted_entities,
        model_used="gemini-flash",
        token_usage=mock_token_usage,
        timings=timings,
        start_time=start_time,
    )

    assert result.answer == "Test answer"
    assert result.sources == sources
    assert result.entities == extracted_entities
    assert result.model_used == "gemini-flash"
    assert result.evidence_score == 0.85
    assert result.verification_score == 0.9
    assert result.verification_status == "passed"  # > 0.7
    assert result.document_count == 1
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
    assert result.total_tokens == 150
    assert result.cost_usd == 0.001


def test_build_core_result_unchecked_verification(response_builder, mock_state, mock_token_usage):
    """Test CoreResult with unchecked verification status"""
    mock_state.verification_score = 0.5  # < 0.7
    timings = {"total": 1.5}

    result = response_builder.build_core_result(
        state=mock_state,
        sources=[],
        extracted_entities={},
        model_used="gemini-flash",
        token_usage=mock_token_usage,
        timings=timings,
        start_time=time.time(),
    )

    assert result.verification_status == "unchecked"


def test_build_gate_response_success(response_builder):
    """Test gate response building"""
    start_time = time.time()
    result = response_builder.build_gate_response(
        answer="Hello!",
        model_used="greeting-gate",
        verification_score=1.0,
        evidence_score=1.0,
        verification_status="passed",
        start_time=start_time,
    )

    assert result.answer == "Hello!"
    assert result.model_used == "greeting-gate"
    assert result.verification_score == 1.0
    assert result.evidence_score == 1.0
    assert result.verification_status == "passed"
    assert result.document_count == 0
    assert result.sources == []
    assert result.timings["total"] >= 0


def test_build_gate_response_with_entities(response_builder):
    """Test gate response with entities"""
    entities = {"person": "John"}
    result = response_builder.build_gate_response(
        answer="Hi John!",
        model_used="greeting-gate",
        entities=entities,
        start_time=time.time(),
    )

    assert result.entities == entities


def test_build_clarification_response(response_builder):
    """Test clarification response building"""
    ambiguity_info = {
        "is_ambiguous": True,
        "confidence": 0.8,
        "reasons": ["multiple interpretations"],
        "entities": {"topic": "visa"},
    }
    start_time = time.time()

    result = response_builder.build_clarification_response(
        clarification_msg="Could you clarify?",
        ambiguity_info=ambiguity_info,
        start_time=start_time,
    )

    assert result.answer == "Could you clarify?"
    assert result.is_ambiguous is True
    assert result.clarification_question == "Could you clarify?"
    assert result.verification_score == 0.0
    assert result.evidence_score == 0.0
    assert result.verification_status == "skipped"
    assert result.entities == {"topic": "visa"}


def test_build_out_of_domain_response(response_builder):
    """Test out-of-domain response building"""
    start_time = time.time()
    result = response_builder.build_out_of_domain_response(
        answer_text="I can't help with that.",
        reason="off_topic",
        start_time=start_time,
    )

    assert result.answer == "I can't help with that."
    assert result.model_used == "out-of-domain-off_topic"
    assert result.verification_score == 0.0
    assert result.evidence_score == 0.0
    assert result.verification_status == "blocked"
    assert "Query blocked: off_topic" in result.warnings


def test_build_core_result_default_values(response_builder, mock_state, mock_token_usage):
    """Test CoreResult with default values"""
    # State without evidence_score/verification_score attributes
    mock_state_no_scores = MagicMock(spec=AgentState)
    mock_state_no_scores.final_answer = "Answer"
    # Use getattr to simulate missing attributes
    type(mock_state_no_scores).evidence_score = property(lambda self: 0.0)
    type(mock_state_no_scores).verification_score = property(lambda self: 0.0)

    result = response_builder.build_core_result(
        state=mock_state_no_scores,
        sources=[],
        extracted_entities={},
        model_used="test",
        token_usage=mock_token_usage,
        timings={"total": 1.0},
        start_time=time.time(),
    )

    assert result.evidence_score == 0.0
    assert result.verification_score == 0.0
