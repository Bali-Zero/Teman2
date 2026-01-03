"""
Unit tests for CircuitBreaker
Target: >95% coverage
"""

import sys
import time
from pathlib import Path

import pytest

backend_path = Path(__file__).parent.parent.parent.parent.parent / "backend"
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))

from app.core.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Tests for CircuitBreaker"""

    def test_init(self):
        """Test initialization"""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.failure_threshold == 5
        assert breaker.success_threshold == 2
        assert breaker.timeout == 60.0

    def test_init_custom_params(self):
        """Test initialization with custom parameters"""
        breaker = CircuitBreaker(
            failure_threshold=3,
            success_threshold=1,
            timeout=30.0,
            name="test_breaker"
        )
        assert breaker.failure_threshold == 3
        assert breaker.success_threshold == 1
        assert breaker.timeout == 30.0
        assert breaker.name == "test_breaker"

    def test_record_success_closed(self):
        """Test recording success in CLOSED state"""
        breaker = CircuitBreaker()
        breaker.record_success()
        assert breaker.failure_count == 0
        assert breaker.state == CircuitState.CLOSED

    def test_record_success_half_open(self):
        """Test recording success in HALF_OPEN state"""
        breaker = CircuitBreaker(success_threshold=2)
        breaker.state = CircuitState.HALF_OPEN
        breaker.success_count = 1

        breaker.record_success()
        # After transition to CLOSED, success_count is reset to 0
        assert breaker.state == CircuitState.CLOSED
        assert breaker.success_count == 0

    def test_record_failure_closed(self):
        """Test recording failure in CLOSED state"""
        breaker = CircuitBreaker(failure_threshold=2)
        breaker.record_failure()
        assert breaker.failure_count == 1
        assert breaker.state == CircuitState.CLOSED

        breaker.record_failure()
        assert breaker.failure_count == 2
        assert breaker.state == CircuitState.OPEN

    def test_record_failure_half_open(self):
        """Test recording failure in HALF_OPEN state"""
        breaker = CircuitBreaker()
        breaker.state = CircuitState.HALF_OPEN
        breaker.record_failure()
        assert breaker.state == CircuitState.OPEN

    def test_is_open_closed(self):
        """Test is_open when circuit is CLOSED"""
        breaker = CircuitBreaker()
        assert breaker.is_open() is False

    def test_is_open_open(self):
        """Test is_open when circuit is OPEN"""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.record_failure()
        assert breaker.is_open() is True

    def test_is_open_half_open(self):
        """Test is_open when circuit is HALF_OPEN"""
        breaker = CircuitBreaker()
        breaker.state = CircuitState.HALF_OPEN
        assert breaker.is_open() is False

    def test_transition_to_open(self):
        """Test transition to OPEN state"""
        breaker = CircuitBreaker()
        breaker._transition_to_open()
        assert breaker.state == CircuitState.OPEN
        assert breaker.last_failure_time is not None

    def test_transition_to_half_open(self):
        """Test transition to HALF_OPEN state"""
        breaker = CircuitBreaker()
        breaker._transition_to_half_open()
        assert breaker.state == CircuitState.HALF_OPEN
        assert breaker.success_count == 0
        assert breaker.failure_count == 0

    def test_transition_to_closed(self):
        """Test transition to CLOSED state"""
        breaker = CircuitBreaker()
        breaker.state = CircuitState.OPEN
        breaker._transition_to_closed()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0

    @pytest.mark.asyncio
    async def test_call_success(self):
        """Test calling function successfully"""
        breaker = CircuitBreaker()

        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_failure(self):
        """Test calling function that fails"""
        breaker = CircuitBreaker(failure_threshold=1)

        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_call_open_circuit(self):
        """Test calling function when circuit is OPEN"""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.state = CircuitState.OPEN

        async def func():
            return "should not execute"

        with pytest.raises(RuntimeError, match="Circuit breaker.*is OPEN"):
            await breaker.call(func)

    @pytest.mark.asyncio
    async def test_call_open_circuit_with_fallback(self):
        """Test calling function when circuit is OPEN with fallback"""
        breaker = CircuitBreaker(failure_threshold=1)
        breaker.state = CircuitState.OPEN

        async def func():
            return "should not execute"

        async def fallback():
            return "fallback result"

        result = await breaker.call(func, fallback=fallback)
        assert result == "fallback result"

    @pytest.mark.asyncio
    async def test_call_half_open_success(self):
        """Test calling function in HALF_OPEN state with success"""
        breaker = CircuitBreaker(success_threshold=1)
        breaker.state = CircuitState.HALF_OPEN

        async def success_func():
            return "success"

        result = await breaker.call(success_func)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_call_half_open_failure(self):
        """Test calling function in HALF_OPEN state with failure"""
        breaker = CircuitBreaker()
        breaker.state = CircuitState.HALF_OPEN

        async def fail_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    def test_timeout_transition(self):
        """Test timeout transition from OPEN to HALF_OPEN"""
        breaker = CircuitBreaker(timeout=0.1)
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = time.time() - 0.2  # Past timeout

        # Check timeout - should transition
        breaker._check_timeout()
        assert breaker.state == CircuitState.HALF_OPEN

    def test_no_timeout_transition(self):
        """Test no timeout transition when timeout not elapsed"""
        breaker = CircuitBreaker(timeout=60.0)
        breaker.state = CircuitState.OPEN
        breaker.last_failure_time = time.time()  # Just now

        breaker._check_timeout()
        assert breaker.state == CircuitState.OPEN  # Still open

    def test_get_state(self):
        """Test getting circuit breaker state"""
        breaker = CircuitBreaker()
        breaker.state = CircuitState.OPEN
        breaker.failure_count = 5

        state = breaker.get_state()
        assert state["state"] == "open"
        assert state["failure_count"] == 5
        assert state["name"] == "circuit"

