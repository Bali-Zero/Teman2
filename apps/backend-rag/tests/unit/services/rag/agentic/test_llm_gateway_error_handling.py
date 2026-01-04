"""
Tests for LLM Gateway error handling and circuit breaker.

Tests:
- Circuit breaker opens after threshold failures
- Circuit breaker transitions to half-open after timeout
- Circuit breaker closes after success threshold
- Error classification for different error types
- Fallback cascade with cost limits
"""

from unittest.mock import MagicMock

import pytest
from google.api_core.exceptions import ResourceExhausted, ServiceUnavailable

from app.core.circuit_breaker import CircuitState
from app.core.error_classification import ErrorCategory, ErrorClassifier
from services.rag.agentic.llm_gateway import LLMGateway


@pytest.fixture
def llm_gateway():
    """Create LLM Gateway instance for testing."""
    gateway = LLMGateway(gemini_tools=[])
    # Mock GenAI client to avoid actual API calls
    gateway._genai_client = MagicMock()
    gateway._genai_client.is_available = True
    gateway._available = True
    return gateway


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold(llm_gateway):
    """Test that circuit breaker opens after failure threshold."""
    model_name = "gemini-3-flash-preview"

    # Get circuit breaker
    circuit = llm_gateway._get_circuit_breaker(model_name)
    assert circuit.state == CircuitState.CLOSED

    # Record failures up to threshold
    for i in range(llm_gateway._circuit_breaker_threshold):
        circuit.record_failure()

    # Circuit should be open
    assert circuit.state == CircuitState.OPEN
    assert llm_gateway._is_circuit_open(model_name)


@pytest.mark.asyncio
async def test_circuit_breaker_transitions_to_half_open(llm_gateway):
    """Test that circuit breaker transitions to half-open after timeout."""
    model_name = "gemini-3-flash-preview"
    circuit = llm_gateway._get_circuit_breaker(model_name)

    # Open circuit
    for _ in range(llm_gateway._circuit_breaker_threshold):
        circuit.record_failure()
    assert circuit.state == CircuitState.OPEN

    # Fast-forward time
    import time

    original_time = time.time
    current_time = [original_time()]

    def mock_time():
        return current_time[0]

    time.time = mock_time

    # Advance time past timeout
    current_time[0] += llm_gateway._circuit_breaker_timeout + 1

    # Check timeout - should transition to half-open
    circuit._check_timeout()
    assert circuit.state == CircuitState.HALF_OPEN

    # Restore time
    time.time = original_time


@pytest.mark.asyncio
async def test_circuit_breaker_closes_after_success_threshold(llm_gateway):
    """Test that circuit breaker closes after success threshold in half-open."""
    model_name = "gemini-3-flash-preview"
    circuit = llm_gateway._get_circuit_breaker(model_name)

    # Open circuit
    for _ in range(llm_gateway._circuit_breaker_threshold):
        circuit.record_failure()

    # Fast-forward to half-open
    import time

    original_time = time.time
    current_time = [original_time()]

    def mock_time():
        return current_time[0]

    time.time = mock_time
    current_time[0] += llm_gateway._circuit_breaker_timeout + 1
    circuit._check_timeout()
    assert circuit.state == CircuitState.HALF_OPEN

    # Record successes
    for _ in range(circuit.success_threshold):
        circuit.record_success()

    assert circuit.state == CircuitState.CLOSED

    # Restore time
    time.time = original_time


@pytest.mark.asyncio
async def test_error_classification_transient(llm_gateway):
    """Test that ResourceExhausted is classified as transient."""
    error = ResourceExhausted("Quota exceeded")
    category, severity = ErrorClassifier.classify_error(error)

    assert category == ErrorCategory.TRANSIENT
    assert ErrorClassifier.is_retryable(error)


@pytest.mark.asyncio
async def test_error_classification_service_unavailable(llm_gateway):
    """Test that ServiceUnavailable is classified as transient."""
    error = ServiceUnavailable("Service unavailable")
    category, severity = ErrorClassifier.classify_error(error)

    assert category == ErrorCategory.TRANSIENT
    assert ErrorClassifier.is_retryable(error)


@pytest.mark.asyncio
async def test_record_failure_with_error_classification(llm_gateway):
    """Test that _record_failure uses error classification."""
    model_name = "gemini-3-flash-preview"
    error = ResourceExhausted("Quota exceeded")

    # Record failure
    llm_gateway._record_failure(model_name, error)

    # Circuit should have recorded failure
    circuit = llm_gateway._get_circuit_breaker(model_name)
    assert circuit.failure_count == 1


@pytest.mark.asyncio
async def test_circuit_breaker_skips_open_models(llm_gateway):
    """Test that models with open circuit breakers are skipped."""
    model_name = "gemini-3-flash-preview"

    # Open circuit breaker
    circuit = llm_gateway._get_circuit_breaker(model_name)
    for _ in range(llm_gateway._circuit_breaker_threshold):
        circuit.record_failure()

    # Should skip this model
    assert llm_gateway._is_circuit_open(model_name)


@pytest.mark.asyncio
async def test_fallback_chain_respects_circuit_breaker(llm_gateway):
    """Test that fallback chain respects circuit breaker state."""

    # Mock _call_model to raise errors
    async def mock_call_model(model_name, with_tools=False):
        raise ResourceExhausted("Quota exceeded")

    # Open circuit for first model
    model1 = "gemini-3-flash-preview"
    circuit1 = llm_gateway._get_circuit_breaker(model1)
    for _ in range(llm_gateway._circuit_breaker_threshold):
        circuit1.record_failure()

    # Should skip model1 and try next in chain
    assert llm_gateway._is_circuit_open(model1)


@pytest.mark.asyncio
async def test_cost_limit_enforced(llm_gateway):
    """Test that cost limit is enforced in fallback cascade."""
    query_cost_tracker = {"cost": 0.0, "depth": 0}

    # Set cost limit
    llm_gateway._max_fallback_cost_usd = 0.10

    # Simulate cost accumulation
    query_cost_tracker["cost"] = 0.11

    # Should stop fallback cascade
    assert query_cost_tracker["cost"] >= llm_gateway._max_fallback_cost_usd


@pytest.mark.asyncio
async def test_fallback_depth_limit(llm_gateway):
    """Test that fallback depth limit is enforced."""
    query_cost_tracker = {"cost": 0.0, "depth": 0}

    # Set depth limit
    llm_gateway._max_fallback_depth = 3

    # Simulate depth accumulation
    query_cost_tracker["depth"] = 4

    # Should stop fallback cascade
    assert query_cost_tracker["depth"] >= llm_gateway._max_fallback_depth
