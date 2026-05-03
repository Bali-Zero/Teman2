"""
Tests for async_utils module.
"""

import asyncio

import pytest

from backend.app.utils.async_utils import (
    CircuitBreaker,
    CircuitBreakerOpen,
    Debouncer,
    gather_with_concurrency,
)


class TestGatherWithConcurrency:
    """Tests for gather_with_concurrency function."""

    @pytest.mark.asyncio
    async def test_respects_concurrency_limit(self):
        """Test that concurrency limit is respected."""
        running = 0
        max_running = 0

        async def task(id):
            nonlocal running, max_running
            running += 1
            max_running = max(max_running, running)
            await asyncio.sleep(0.1)
            running -= 1
            return id

        results = await gather_with_concurrency(
            2,  # Max 2 concurrent
            *[task(i) for i in range(5)],
        )

        assert max_running <= 2
        assert sorted(results) == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio
    async def test_returns_results_in_order(self):
        """Test that results are returned in input order."""

        async def task(id):
            await asyncio.sleep(0.01 * (5 - id))  # Reverse order completion
            return id

        results = await gather_with_concurrency(3, *[task(i) for i in range(5)])
        assert results == [0, 1, 2, 3, 4]


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.mark.asyncio
    async def test_initially_closed(self):
        """Test that circuit starts in closed state."""
        cb = CircuitBreaker()
        assert cb.state == "closed"

    @pytest.mark.asyncio
    async def test_opens_after_failures(self):
        """Test that circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=3)

        async def failing_func():
            raise Exception("Always fails")

        for _ in range(3):
            with pytest.raises(Exception):
                await cb.call(failing_func)

        assert cb.state == "open"

    @pytest.mark.asyncio
    async def test_raises_when_open(self):
        """Test that calls fail when circuit is open."""
        cb = CircuitBreaker(failure_threshold=1)

        async def failing_func():
            raise Exception("Fails")

        with pytest.raises(Exception):
            await cb.call(failing_func)

        with pytest.raises(CircuitBreakerOpen):
            await cb.call(failing_func)

    @pytest.mark.asyncio
    async def test_closes_after_success(self):
        """Test that circuit closes after successful call."""
        cb = CircuitBreaker(failure_threshold=1)

        async def failing_func():
            raise Exception("Fails")

        async def success_func():
            return "success"

        # Open the circuit
        with pytest.raises(Exception):
            await cb.call(failing_func)

        # Force reset by waiting
        import time

        cb._last_failure_time = time.time() - 100
        cb._state = "half-open"

        # Success should close it
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state == "closed"


class TestDebouncer:
    """Tests for Debouncer class."""

    @pytest.mark.asyncio
    async def test_debounces_multiple_calls(self):
        """Test that multiple calls are debounced."""
        debouncer = Debouncer(delay=0.05)
        call_count = 0

        async def increment():
            nonlocal call_count
            call_count += 1

        # Call multiple times rapidly
        for _ in range(5):
            await debouncer.call(increment)

        # Wait for debounce delay
        await asyncio.sleep(0.1)

        # Should only be called once
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_allows_new_call_after_delay(self):
        """Test that new calls work after delay."""
        debouncer = Debouncer(delay=0.05)
        call_count = 0

        async def increment():
            nonlocal call_count
            call_count += 1

        await debouncer.call(increment)
        await asyncio.sleep(0.1)

        await debouncer.call(increment)
        await asyncio.sleep(0.1)

        assert call_count == 2
