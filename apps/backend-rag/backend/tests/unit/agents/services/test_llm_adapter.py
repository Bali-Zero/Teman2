"""
Unit tests for backend/agents/services/llm_adapter.py

Covers:
- LLMProvider, ErrorType, CircuitState enums
- CircuitBreakerState dataclass
- LLMMetrics dataclass (success_rate, avg_response_time)
- LLMRequest / LLMResponse dataclasses
- LLMAdapter:
  - _classify_error
  - _check_circuit_breaker / _record_circuit_breaker_success / _record_circuit_breaker_failure
  - generate (cache hit, mock provider, success, retry, permanent error, circuit breaker open)
  - _call_mock
  - _get_cache_key / _cache_response
  - _check_rate_limit
  - get_metrics / reset_metrics
  - health_check / close
- get_llm_adapter / close_llm_adapter singletons
"""

import asyncio
import logging
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.agents.services.llm_adapter import (
    CircuitBreakerState,
    CircuitState,
    ErrorType,
    LLMAdapter,
    LLMMetrics,
    LLMProvider,
    LLMRequest,
    LLMResponse,
    close_llm_adapter,
    get_llm_adapter,
)

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================
class TestEnums:
    """Verify enum members exist and have expected values."""

    def test_llm_provider(self) -> None:
        assert LLMProvider.OLLAMA.value == "ollama"
        assert LLMProvider.MOCK.value == "mock"

    def test_error_type(self) -> None:
        assert ErrorType.TRANSIENT.value == "transient"
        assert ErrorType.PERMANENT.value == "permanent"
        assert ErrorType.RATE_LIMIT.value == "rate_limit"

    def test_circuit_state(self) -> None:
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


# ============================================================================
# Dataclasses
# ============================================================================
class TestCircuitBreakerState:
    """Tests for CircuitBreakerState dataclass."""

    def test_defaults(self) -> None:
        cb = CircuitBreakerState()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_reset(self) -> None:
        cb = CircuitBreakerState(
            state=CircuitState.OPEN, failure_count=5, success_count=2,
            last_failure_time=100.0, opened_at=90.0,
        )
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
        assert cb.success_count == 0
        assert cb.opened_at == 0.0


class TestLLMMetrics:
    """Tests for LLMMetrics dataclass."""

    def test_defaults(self) -> None:
        m = LLMMetrics()
        assert m.total_requests == 0
        assert m.success_rate == 0.0
        assert m.avg_response_time == 0.0

    def test_success_rate(self) -> None:
        m = LLMMetrics(total_requests=10, successful_requests=7)
        assert m.success_rate == 70.0

    def test_avg_response_time(self) -> None:
        m = LLMMetrics(successful_requests=4, total_response_time=8.0)
        assert m.avg_response_time == 2.0


class TestLLMRequest:
    """Tests for LLMRequest dataclass."""

    def test_defaults(self) -> None:
        req = LLMRequest(prompt="test")
        assert req.prompt == "test"
        assert req.max_tokens == 4000
        assert req.temperature == 0.2
        assert req.provider is None
        assert req.system is None


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_defaults(self) -> None:
        resp = LLMResponse(text="hello")
        assert resp.text == "hello"
        assert resp.provider == LLMProvider.MOCK
        assert resp.cached is False


# ============================================================================
# LLMAdapter — error classification
# ============================================================================
class TestClassifyError:
    """Tests for _classify_error method."""

    def setup_method(self) -> None:
        self.adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)

    def test_model_not_found_is_permanent(self) -> None:
        assert self.adapter._classify_error(Exception("model not found")) == ErrorType.PERMANENT

    def test_unauthorized_is_permanent(self) -> None:
        assert self.adapter._classify_error(Exception("authentication failed")) == ErrorType.PERMANENT

    def test_invalid_prompt_is_permanent(self) -> None:
        assert self.adapter._classify_error(Exception("invalid prompt")) == ErrorType.PERMANENT

    def test_rate_limit_is_rate_limit(self) -> None:
        assert self.adapter._classify_error(Exception("rate limit exceeded")) == ErrorType.RATE_LIMIT

    def test_429_is_rate_limit(self) -> None:
        assert self.adapter._classify_error(Exception("HTTP 429")) == ErrorType.RATE_LIMIT

    def test_timeout_exception_is_transient(self) -> None:
        err = httpx.TimeoutException("timed out")
        assert self.adapter._classify_error(err) == ErrorType.TRANSIENT

    def test_connect_error_is_transient(self) -> None:
        err = httpx.ConnectError("refused")
        assert self.adapter._classify_error(err) == ErrorType.TRANSIENT

    def test_503_is_transient(self) -> None:
        assert self.adapter._classify_error(Exception("service unavailable 503")) == ErrorType.TRANSIENT

    def test_unknown_error_defaults_to_transient(self) -> None:
        assert self.adapter._classify_error(Exception("something weird")) == ErrorType.TRANSIENT

    @pytest.fixture(autouse=True)
    async def _cleanup(self) -> None:
        yield
        await self.adapter.close()


# ============================================================================
# LLMAdapter — circuit breaker logic
# ============================================================================
class TestCircuitBreaker:
    """Tests for circuit breaker transitions."""

    def setup_method(self) -> None:
        self.adapter = LLMAdapter(
            auto_start_ollama=False, max_retries=1,
            circuit_breaker_failure_threshold=3,
            circuit_breaker_timeout=10.0,
            circuit_breaker_success_threshold=2,
        )

    def test_closed_allows_requests(self) -> None:
        assert self.adapter._check_circuit_breaker() is True

    def test_open_rejects_within_timeout(self) -> None:
        self.adapter.circuit_breaker.state = CircuitState.OPEN
        self.adapter.circuit_breaker.opened_at = time.time()
        assert self.adapter._check_circuit_breaker() is False

    def test_open_transitions_to_half_open_after_timeout(self) -> None:
        self.adapter.circuit_breaker.state = CircuitState.OPEN
        self.adapter.circuit_breaker.opened_at = time.time() - 20.0  # past timeout
        assert self.adapter._check_circuit_breaker() is True
        assert self.adapter.circuit_breaker.state == CircuitState.HALF_OPEN

    def test_record_success_in_half_open(self) -> None:
        self.adapter.circuit_breaker.state = CircuitState.HALF_OPEN
        self.adapter._record_circuit_breaker_success()
        self.adapter._record_circuit_breaker_success()
        assert self.adapter.circuit_breaker.state == CircuitState.CLOSED

    def test_record_failure_in_half_open_reopens(self) -> None:
        self.adapter.circuit_breaker.state = CircuitState.HALF_OPEN
        self.adapter._record_circuit_breaker_failure(ErrorType.TRANSIENT)
        assert self.adapter.circuit_breaker.state == CircuitState.OPEN

    def test_record_failure_opens_circuit_after_threshold(self) -> None:
        for _ in range(3):
            self.adapter._record_circuit_breaker_failure(ErrorType.TRANSIENT)
        assert self.adapter.circuit_breaker.state == CircuitState.OPEN
        assert self.adapter.metrics.circuit_breaker_trips == 1

    def test_permanent_error_does_not_affect_circuit_breaker(self) -> None:
        self.adapter._record_circuit_breaker_failure(ErrorType.PERMANENT)
        assert self.adapter.circuit_breaker.failure_count == 0

    def test_success_decrements_failure_count(self) -> None:
        self.adapter.circuit_breaker.failure_count = 2
        self.adapter._record_circuit_breaker_success()
        assert self.adapter.circuit_breaker.failure_count == 1

    @pytest.fixture(autouse=True)
    async def _cleanup(self) -> None:
        yield
        await self.adapter.close()


# ============================================================================
# LLMAdapter — generate
# ============================================================================
class TestGenerate:
    """Tests for the generate() method."""

    def setup_method(self) -> None:
        self.adapter = LLMAdapter(
            auto_start_ollama=False, max_retries=2,
            retry_backoff_base=0.01, retry_jitter=0.0,
        )

    @pytest.mark.asyncio
    async def test_cache_hit(self) -> None:
        """Cached response should be returned immediately."""
        req = LLMRequest(prompt="cached prompt")
        cached_resp = LLMResponse(text="cached", provider=LLMProvider.OLLAMA)
        cache_key = self.adapter._get_cache_key(req)
        self.adapter.cache[cache_key] = cached_resp

        result = await self.adapter.generate(req)
        assert result.text == "cached"
        assert self.adapter.metrics.cache_hits == 1

    @pytest.mark.asyncio
    async def test_mock_provider(self) -> None:
        """Mock provider should return mock response."""
        req = LLMRequest(prompt="test", provider=LLMProvider.MOCK)
        result = await self.adapter.generate(req)
        assert result.provider == LLMProvider.MOCK
        assert len(result.text) > 0

    @pytest.mark.asyncio
    async def test_successful_ollama_call(self) -> None:
        """Successful Ollama call should return response and update metrics."""
        req = LLMRequest(prompt="hello world")
        mock_resp = LLMResponse(
            text="generated text", tokens_used=10,
            response_time=0.5, provider=LLMProvider.OLLAMA,
        )
        self.adapter._call_ollama = AsyncMock(return_value=mock_resp)

        result = await self.adapter.generate(req)
        assert result.text == "generated text"
        assert result.provider == LLMProvider.OLLAMA
        assert self.adapter.metrics.successful_requests == 1
        assert self.adapter.metrics.total_tokens == 10

    @pytest.mark.asyncio
    async def test_permanent_error_no_retry(self) -> None:
        """Permanent errors should not retry."""
        req = LLMRequest(prompt="bad prompt")
        self.adapter._call_ollama = AsyncMock(
            side_effect=Exception("model not found"),
        )

        result = await self.adapter.generate(req)
        assert result.provider == LLMProvider.MOCK
        assert self.adapter.metrics.permanent_errors == 1
        self.adapter._call_ollama.assert_called_once()

    @pytest.mark.asyncio
    async def test_transient_error_retries(self) -> None:
        """Transient errors should trigger retries."""
        req = LLMRequest(prompt="retry test")
        mock_resp = LLMResponse(text="ok", provider=LLMProvider.OLLAMA, tokens_used=5)
        self.adapter._call_ollama = AsyncMock(
            side_effect=[Exception("timeout happened"), mock_resp],
        )
        self.adapter._ensure_ollama_available = AsyncMock()

        result = await self.adapter.generate(req)
        assert result.text == "ok"
        assert self.adapter._call_ollama.call_count == 2

    @pytest.mark.asyncio
    async def test_all_retries_exhausted(self) -> None:
        """When all retries fail, return mock."""
        req = LLMRequest(prompt="fail")
        self.adapter._call_ollama = AsyncMock(
            side_effect=Exception("connection refused"),
        )
        self.adapter._ensure_ollama_available = AsyncMock()

        result = await self.adapter.generate(req)
        assert result.provider == LLMProvider.MOCK
        assert "unavailable" in result.text.lower() or "mock" in result.text.lower()

    @pytest.mark.asyncio
    async def test_circuit_breaker_open_returns_mock(self) -> None:
        """When circuit breaker is open, return mock immediately."""
        req = LLMRequest(prompt="blocked")
        self.adapter.circuit_breaker.state = CircuitState.OPEN
        self.adapter.circuit_breaker.opened_at = time.time()

        result = await self.adapter.generate(req)
        assert result.provider == LLMProvider.MOCK
        assert "circuit breaker" in result.text.lower()

    @pytest.fixture(autouse=True)
    async def _cleanup(self) -> None:
        yield
        await self.adapter.close()


# ============================================================================
# LLMAdapter — _call_mock
# ============================================================================
class TestCallMock:
    """Tests for _call_mock."""

    @pytest.mark.asyncio
    async def test_returns_mock_response(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        req = LLMRequest(prompt="test prompt")
        result = await adapter._call_mock(req)
        assert result.provider == LLMProvider.MOCK
        assert len(result.text) > 0
        await adapter.close()


# ============================================================================
# LLMAdapter — cache
# ============================================================================
class TestCache:
    """Tests for cache methods."""

    def test_get_cache_key_deterministic(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        req = LLMRequest(prompt="same prompt", max_tokens=100, temperature=0.5)
        k1 = adapter._get_cache_key(req)
        k2 = adapter._get_cache_key(req)
        assert k1 == k2

    def test_cache_eviction(self) -> None:
        adapter = LLMAdapter(
            auto_start_ollama=False, max_retries=1,
            cache_size=2,
        )
        r1 = LLMResponse(text="a")
        r2 = LLMResponse(text="b")
        r3 = LLMResponse(text="c")
        adapter._cache_response("k1", r1)
        adapter._cache_response("k2", r2)
        assert len(adapter.cache) == 2
        adapter._cache_response("k3", r3)
        assert len(adapter.cache) == 2
        assert "k1" not in adapter.cache


# ============================================================================
# LLMAdapter — rate limiting
# ============================================================================
class TestRateLimit:
    """Tests for rate limiting."""

    @pytest.mark.asyncio
    async def test_increments_counter(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1, rate_limit=100)
        await adapter._check_rate_limit()
        assert adapter.request_count == 1
        await adapter.close()

    @pytest.mark.asyncio
    async def test_resets_after_minute(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1, rate_limit=100)
        adapter.request_count = 50
        adapter.last_reset = time.time() - 120  # 2 minutes ago
        await adapter._check_rate_limit()
        assert adapter.request_count == 1  # reset + 1
        await adapter.close()


# ============================================================================
# LLMAdapter — metrics & health
# ============================================================================
class TestMetricsAndHealth:
    """Tests for get_metrics, reset_metrics, health_check."""

    def test_get_metrics(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        metrics = adapter.get_metrics()
        assert "total_requests" in metrics
        assert "circuit_breaker_state" in metrics
        assert metrics["circuit_breaker_state"] == "closed"

    def test_reset_metrics(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        adapter.metrics.total_requests = 100
        adapter.cache["test"] = LLMResponse(text="x")
        adapter.reset_metrics()
        assert adapter.metrics.total_requests == 0
        assert len(adapter.cache) == 0

    @pytest.mark.asyncio
    async def test_health_check_ollama_down(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(side_effect=Exception("connection refused"))
        health = await adapter.health_check()
        assert health["ollama"] is False
        assert health["mock"] is True

    @pytest.mark.asyncio
    async def test_health_check_ollama_up_no_model(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "llama3:latest"}]}
        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_resp)
        health = await adapter.health_check()
        assert health["ollama"] is False  # qwen not found

    @pytest.mark.asyncio
    async def test_health_check_ollama_up_with_model(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"models": [{"name": "qwen2.5:latest"}]}
        adapter.client = AsyncMock()
        adapter.client.get = AsyncMock(return_value=mock_resp)
        health = await adapter.health_check()
        assert health["ollama"] is True


# ============================================================================
# LLMAdapter — _call_ollama
# ============================================================================
class TestCallOllama:
    """Tests for _call_ollama."""

    @pytest.mark.asyncio
    async def test_successful_call(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "generated text here"}
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_response)

        req = LLMRequest(prompt="test")
        result = await adapter._call_ollama(req)
        assert result.text == "generated text here"
        assert result.provider == LLMProvider.OLLAMA

    @pytest.mark.asyncio
    async def test_empty_response_raises(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": ""}
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_response)

        req = LLMRequest(prompt="test")
        with pytest.raises(RuntimeError, match="Ollama call failed"):
            await adapter._call_ollama(req)

    @pytest.mark.asyncio
    async def test_timeout_raises(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(side_effect=httpx.TimeoutException("timed out"))

        req = LLMRequest(prompt="test")
        with pytest.raises(RuntimeError, match="Ollama timeout"):
            await adapter._call_ollama(req)

    @pytest.mark.asyncio
    async def test_system_prompt_included(self) -> None:
        adapter = LLMAdapter(auto_start_ollama=False, max_retries=1)
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": "ok"}
        adapter.client = AsyncMock()
        adapter.client.post = AsyncMock(return_value=mock_response)

        req = LLMRequest(prompt="test", system="You are a helper")
        await adapter._call_ollama(req)
        call_args = adapter.client.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["system"] == "You are a helper"


# ============================================================================
# Singleton helpers
# ============================================================================
class TestSingleton:
    """Tests for get_llm_adapter / close_llm_adapter."""

    @pytest.mark.asyncio
    async def test_get_and_close_singleton(self) -> None:
        import backend.agents.services.llm_adapter as mod
        mod._llm_adapter = None  # reset
        adapter = get_llm_adapter()
        assert adapter is not None
        assert get_llm_adapter() is adapter  # same instance
        await close_llm_adapter()
        assert mod._llm_adapter is None
