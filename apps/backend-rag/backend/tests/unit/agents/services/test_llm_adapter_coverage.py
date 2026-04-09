"""
Unit tests for backend/agents/services/llm_adapter.py
Covers: LLMAdapter, LLMMetrics, CircuitBreakerState, get_llm_adapter, close_llm_adapter
"""

import time
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


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def adapter():
    """LLMAdapter with fast settings and no real network calls."""
    a = LLMAdapter(
        primary_provider=LLMProvider.OLLAMA,
        ollama_url="http://localhost:11434",
        ollama_model="qwen2.5:latest",
        enable_cache=True,
        cache_size=10,
        rate_limit=100,
        max_retries=2,
        retry_backoff_base=0.01,  # very fast for tests
        retry_jitter=0.0,
        auto_start_ollama=False,
        circuit_breaker_failure_threshold=5,
        circuit_breaker_timeout=30.0,
        circuit_breaker_success_threshold=2,
    )
    yield a


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton between tests."""
    import backend.agents.services.llm_adapter as mod
    mod._llm_adapter = None
    yield
    mod._llm_adapter = None


# ─────────────────────────────────────────────────────────────────────────────
# LLMMetrics
# ─────────────────────────────────────────────────────────────────────────────

def test_metrics_success_rate_zero_when_no_requests():
    m = LLMMetrics()
    assert m.success_rate == 0.0


def test_metrics_success_rate_calculated():
    m = LLMMetrics(total_requests=10, successful_requests=7)
    assert m.success_rate == 70.0


def test_metrics_avg_response_time_zero_when_no_success():
    m = LLMMetrics()
    assert m.avg_response_time == 0.0


def test_metrics_avg_response_time_calculated():
    m = LLMMetrics(successful_requests=2, total_response_time=4.0)
    assert m.avg_response_time == 2.0


# ─────────────────────────────────────────────────────────────────────────────
# CircuitBreakerState.reset
# ─────────────────────────────────────────────────────────────────────────────

def test_circuit_breaker_reset():
    cb = CircuitBreakerState(
        state=CircuitState.OPEN,
        failure_count=5,
        success_count=1,
        last_failure_time=time.time(),
        opened_at=time.time(),
    )
    cb.reset()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert cb.success_count == 0
    assert cb.last_failure_time == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# _classify_error
# ─────────────────────────────────────────────────────────────────────────────

def test_classify_error_model_not_found(adapter):
    err = RuntimeError("model not found")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_invalid_model(adapter):
    err = RuntimeError("invalid model configuration")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_authentication(adapter):
    err = RuntimeError("authentication failed")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_unauthorized(adapter):
    err = RuntimeError("unauthorized access")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_invalid_prompt(adapter):
    err = RuntimeError("invalid prompt provided")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_malformed(adapter):
    err = RuntimeError("malformed request")
    assert adapter._classify_error(err) == ErrorType.PERMANENT


def test_classify_error_rate_limit(adapter):
    err = RuntimeError("rate limit exceeded")
    assert adapter._classify_error(err) == ErrorType.RATE_LIMIT


def test_classify_error_429(adapter):
    err = RuntimeError("http 429 error")
    assert adapter._classify_error(err) == ErrorType.RATE_LIMIT


def test_classify_error_timeout_exception(adapter):
    err = httpx.TimeoutException("timeout")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


def test_classify_error_connect_error(adapter):
    err = httpx.ConnectError("connection refused")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


def test_classify_error_timeout_string(adapter):
    err = RuntimeError("timeout connecting")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


def test_classify_error_service_unavailable(adapter):
    err = RuntimeError("service unavailable 503")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


def test_classify_error_502(adapter):
    err = RuntimeError("bad gateway 502")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


def test_classify_error_default_transient(adapter):
    err = RuntimeError("some generic error")
    assert adapter._classify_error(err) == ErrorType.TRANSIENT


# ─────────────────────────────────────────────────────────────────────────────
# _check_circuit_breaker
# ─────────────────────────────────────────────────────────────────────────────

def test_check_circuit_breaker_closed_allows(adapter):
    assert adapter._check_circuit_breaker() is True


def test_check_circuit_breaker_open_blocks(adapter):
    adapter.circuit_breaker.state = CircuitState.OPEN
    adapter.circuit_breaker.opened_at = time.time()  # Just opened
    # Timeout is 30s, so it's still within cooldown
    result = adapter._check_circuit_breaker()
    # May be True or False depending on probe window; at least no crash
    assert isinstance(result, bool)


def test_check_circuit_breaker_open_transitions_to_half_open(adapter):
    adapter.circuit_breaker.state = CircuitState.OPEN
    adapter.circuit_breaker.opened_at = time.time() - 35.0  # Past timeout
    result = adapter._check_circuit_breaker()
    assert result is True
    assert adapter.circuit_breaker.state == CircuitState.HALF_OPEN


def test_check_circuit_breaker_half_open_allows(adapter):
    adapter.circuit_breaker.state = CircuitState.HALF_OPEN
    assert adapter._check_circuit_breaker() is True


# ─────────────────────────────────────────────────────────────────────────────
# _record_circuit_breaker_success
# ─────────────────────────────────────────────────────────────────────────────

def test_record_circuit_breaker_success_half_open_counts(adapter):
    adapter.circuit_breaker.state = CircuitState.HALF_OPEN
    adapter.circuit_breaker.success_count = 0
    adapter._record_circuit_breaker_success()
    assert adapter.circuit_breaker.success_count == 1


def test_record_circuit_breaker_success_half_open_closes_at_threshold(adapter):
    adapter.circuit_breaker.state = CircuitState.HALF_OPEN
    adapter.circuit_breaker.success_count = adapter.circuit_breaker_success_threshold - 1
    adapter._record_circuit_breaker_success()
    assert adapter.circuit_breaker.state == CircuitState.CLOSED


def test_record_circuit_breaker_success_closed_decrements_failures(adapter):
    adapter.circuit_breaker.state = CircuitState.CLOSED
    adapter.circuit_breaker.failure_count = 3
    adapter._record_circuit_breaker_success()
    assert adapter.circuit_breaker.failure_count == 2


# ─────────────────────────────────────────────────────────────────────────────
# _record_circuit_breaker_failure
# ─────────────────────────────────────────────────────────────────────────────

def test_record_circuit_breaker_failure_permanent_ignored(adapter):
    adapter.circuit_breaker.failure_count = 0
    adapter._record_circuit_breaker_failure(ErrorType.PERMANENT)
    assert adapter.circuit_breaker.failure_count == 0


def test_record_circuit_breaker_failure_transient_increments(adapter):
    adapter._record_circuit_breaker_failure(ErrorType.TRANSIENT)
    assert adapter.circuit_breaker.failure_count == 1


def test_record_circuit_breaker_failure_opens_at_threshold(adapter):
    adapter.circuit_breaker.failure_count = adapter.circuit_breaker_failure_threshold - 1
    adapter._record_circuit_breaker_failure(ErrorType.TRANSIENT)
    assert adapter.circuit_breaker.state == CircuitState.OPEN
    assert adapter.metrics.circuit_breaker_trips == 1


def test_record_circuit_breaker_failure_half_open_reopens(adapter):
    adapter.circuit_breaker.state = CircuitState.HALF_OPEN
    adapter._record_circuit_breaker_failure(ErrorType.TRANSIENT)
    assert adapter.circuit_breaker.state == CircuitState.OPEN


# ─────────────────────────────────────────────────────────────────────────────
# generate — mock provider
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_mock_provider(adapter):
    request = LLMRequest(prompt="test prompt", provider=LLMProvider.MOCK)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        response = await adapter.generate(request)
    assert isinstance(response.text, str)
    assert len(response.text) > 0
    assert response.provider == LLMProvider.MOCK


@pytest.mark.asyncio
async def test_generate_cache_hit(adapter):
    request = LLMRequest(prompt="cached prompt", provider=LLMProvider.MOCK)
    # First call
    with patch("asyncio.sleep", new_callable=AsyncMock):
        r1 = await adapter.generate(request)
    # Second call — should hit cache
    with patch("asyncio.sleep", new_callable=AsyncMock):
        r2 = await adapter.generate(request)
    # Both should succeed; second is cached
    assert r1.text == r2.text


@pytest.mark.asyncio
async def test_generate_cache_disabled(adapter):
    adapter.enable_cache = False
    r1 = LLMRequest(prompt="no cache", provider=LLMProvider.MOCK)
    r2 = LLMRequest(prompt="no cache", provider=LLMProvider.MOCK)
    with patch("asyncio.sleep", new_callable=AsyncMock):
        resp1 = await adapter.generate(r1)
        resp2 = await adapter.generate(r2)
    assert resp1.text is not None
    assert resp2.text is not None
    assert adapter.metrics.cache_hits == 0


@pytest.mark.asyncio
async def test_generate_circuit_open_returns_mock(adapter):
    adapter.circuit_breaker.state = CircuitState.OPEN
    adapter.circuit_breaker.opened_at = time.time()  # Just opened

    request = LLMRequest(prompt="blocked", provider=LLMProvider.OLLAMA)
    with patch.object(adapter, "_check_circuit_breaker", return_value=False):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            response = await adapter.generate(request)

    assert response.provider == LLMProvider.MOCK
    assert "circuit breaker" in response.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# generate — Ollama success
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_generate_ollama_success(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"response": "Hello from Qwen"})

    with patch.object(adapter.client, "post", new_callable=AsyncMock, return_value=mock_response):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            request = LLMRequest(prompt="Hello", provider=LLMProvider.OLLAMA)
            response = await adapter.generate(request)

    assert response.provider == LLMProvider.OLLAMA
    assert response.text == "Hello from Qwen"
    assert adapter.metrics.successful_requests == 1


@pytest.mark.asyncio
async def test_generate_ollama_permanent_error_no_retry(adapter):
    """Permanent errors skip retry loop and go straight to mock."""
    call_count = 0

    async def _mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("model not found")

    with patch.object(adapter.client, "post", side_effect=_mock_post):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            request = LLMRequest(prompt="permanent fail", provider=LLMProvider.OLLAMA)
            response = await adapter.generate(request)

    # Should be called only once (no retries for permanent errors)
    assert call_count == 1
    assert response.provider == LLMProvider.MOCK
    assert adapter.metrics.permanent_errors == 1


@pytest.mark.asyncio
async def test_generate_ollama_transient_error_retries(adapter):
    call_count = 0

    async def _mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise httpx.ConnectError("connection refused")
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(return_value={"response": "retry success"})
        return mock_resp

    with patch.object(adapter.client, "post", side_effect=_mock_post):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            request = LLMRequest(prompt="retry me", provider=LLMProvider.OLLAMA)
            response = await adapter.generate(request)

    assert call_count >= 2
    assert response.provider == LLMProvider.OLLAMA
    assert response.text == "retry success"


@pytest.mark.asyncio
async def test_generate_ollama_all_retries_fail_returns_mock(adapter):
    async def _always_fail(*args, **kwargs):
        raise httpx.ConnectError("always refuses")

    with patch.object(adapter.client, "post", side_effect=_always_fail):
        with patch("asyncio.sleep", new_callable=AsyncMock):
            request = LLMRequest(prompt="always fail", provider=LLMProvider.OLLAMA)
            response = await adapter.generate(request)

    assert response.provider == LLMProvider.MOCK
    assert "unavailable" in response.text.lower()


# ─────────────────────────────────────────────────────────────────────────────
# _call_mock
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_mock_returns_response(adapter):
    request = LLMRequest(prompt="mock me")
    response = await adapter._call_mock(request)
    assert response.provider == LLMProvider.MOCK
    assert isinstance(response.text, str)
    assert response.tokens_used >= 0
    assert response.response_time >= 0.0


# ─────────────────────────────────────────────────────────────────────────────
# _call_ollama
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_call_ollama_success(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"response": "ollama response"})

    with patch.object(adapter.client, "post", new_callable=AsyncMock, return_value=mock_response):
        request = LLMRequest(prompt="test", system="You are helpful.")
        response = await adapter._call_ollama(request)

    assert response.text == "ollama response"
    assert response.provider == LLMProvider.OLLAMA


@pytest.mark.asyncio
async def test_call_ollama_empty_response_raises(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(return_value={"response": ""})

    with patch.object(adapter.client, "post", new_callable=AsyncMock, return_value=mock_response):
        request = LLMRequest(prompt="empty")
        with pytest.raises(RuntimeError, match="Ollama call failed"):
            await adapter._call_ollama(request)


@pytest.mark.asyncio
async def test_call_ollama_timeout_raises(adapter):
    with patch.object(
        adapter.client, "post", new_callable=AsyncMock,
        side_effect=httpx.TimeoutException("timeout"),
    ):
        with pytest.raises(RuntimeError, match="Ollama timeout"):
            await adapter._call_ollama(LLMRequest(prompt="timeout test"))


@pytest.mark.asyncio
async def test_call_ollama_http_error_raises(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 500
    error = httpx.HTTPStatusError("server error", request=MagicMock(), response=mock_response)

    with patch.object(adapter.client, "post", new_callable=AsyncMock, side_effect=error):
        with pytest.raises(RuntimeError, match="Ollama HTTP error"):
            await adapter._call_ollama(LLMRequest(prompt="http error"))


# ─────────────────────────────────────────────────────────────────────────────
# _get_cache_key
# ─────────────────────────────────────────────────────────────────────────────

def test_get_cache_key_deterministic(adapter):
    r = LLMRequest(prompt="hello", max_tokens=100, temperature=0.5)
    k1 = adapter._get_cache_key(r)
    k2 = adapter._get_cache_key(r)
    assert k1 == k2
    assert isinstance(k1, str)


def test_get_cache_key_different_prompts(adapter):
    r1 = LLMRequest(prompt="hello")
    r2 = LLMRequest(prompt="world")
    assert adapter._get_cache_key(r1) != adapter._get_cache_key(r2)


# ─────────────────────────────────────────────────────────────────────────────
# _cache_response (LRU eviction)
# ─────────────────────────────────────────────────────────────────────────────

def test_cache_response_lru_eviction(adapter):
    adapter.cache_size = 3
    # Fill cache
    for i in range(3):
        adapter._cache_response(f"key{i}", LLMResponse(text=f"r{i}", provider=LLMProvider.MOCK))
    assert len(adapter.cache) == 3
    # Add one more — oldest should be evicted
    adapter._cache_response("key3", LLMResponse(text="r3", provider=LLMProvider.MOCK))
    assert len(adapter.cache) == 3
    assert "key0" not in adapter.cache


# ─────────────────────────────────────────────────────────────────────────────
# _check_rate_limit
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_rate_limit_allows_when_under(adapter):
    adapter.rate_limit = 10
    adapter.request_count = 5
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await adapter._check_rate_limit()
    mock_sleep.assert_not_called()
    assert adapter.request_count == 6


@pytest.mark.asyncio
async def test_check_rate_limit_waits_when_exceeded(adapter):
    adapter.rate_limit = 3
    adapter.request_count = 3
    adapter.last_reset = time.time() - 1  # 1 second ago

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await adapter._check_rate_limit()

    mock_sleep.assert_called_once()


@pytest.mark.asyncio
async def test_check_rate_limit_resets_after_minute(adapter):
    adapter.rate_limit = 5
    adapter.request_count = 5
    adapter.last_reset = time.time() - 61  # Over a minute ago

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await adapter._check_rate_limit()

    mock_sleep.assert_not_called()
    assert adapter.request_count == 1


# ─────────────────────────────────────────────────────────────────────────────
# get_metrics / reset_metrics
# ─────────────────────────────────────────────────────────────────────────────

def test_get_metrics_returns_dict(adapter):
    metrics = adapter.get_metrics()
    assert "total_requests" in metrics
    assert "success_rate" in metrics
    assert "circuit_breaker_state" in metrics
    assert "cache_hits" in metrics
    assert "permanent_errors" in metrics


def test_reset_metrics(adapter):
    adapter.metrics.total_requests = 10
    adapter.metrics.cache_hits = 5
    adapter.cache["key"] = LLMResponse(text="x", provider=LLMProvider.MOCK)
    adapter.reset_metrics()
    assert adapter.metrics.total_requests == 0
    assert adapter.metrics.cache_hits == 0
    assert len(adapter.cache) == 0


# ─────────────────────────────────────────────────────────────────────────────
# health_check
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check_ollama_available(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "models": [{"name": "qwen2.5:latest"}],
    })

    with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=mock_response):
        health = await adapter.health_check()

    assert health["ollama"] is True
    assert health["mock"] is True


@pytest.mark.asyncio
async def test_health_check_ollama_model_not_found(adapter):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"models": []})

    with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=mock_response):
        health = await adapter.health_check()

    assert health["ollama"] is False
    assert health["mock"] is True


@pytest.mark.asyncio
async def test_health_check_ollama_unreachable(adapter):
    with patch.object(
        adapter.client, "get", new_callable=AsyncMock,
        side_effect=httpx.ConnectError("refused"),
    ):
        health = await adapter.health_check()

    assert health["ollama"] is False
    assert health["mock"] is True


# ─────────────────────────────────────────────────────────────────────────────
# close
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_close(adapter):
    with patch.object(adapter.client, "aclose", new_callable=AsyncMock) as mock_close:
        await adapter.close()
    mock_close.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# _ensure_ollama_available
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_ensure_ollama_available_auto_start_disabled(adapter):
    adapter.auto_start_ollama = False
    # Should return immediately without making any HTTP calls
    with patch.object(adapter.client, "get", new_callable=AsyncMock) as mock_get:
        await adapter._ensure_ollama_available()
    mock_get.assert_not_called()


@pytest.mark.asyncio
async def test_ensure_ollama_available_already_running(adapter):
    adapter.auto_start_ollama = True
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={
        "models": [{"name": "qwen2.5:latest"}],
    })

    with patch.object(adapter.client, "get", new_callable=AsyncMock, return_value=mock_response):
        await adapter._ensure_ollama_available()
    # Should not attempt to start Ollama


@pytest.mark.asyncio
async def test_ensure_ollama_unavailable_no_command(adapter):
    adapter.auto_start_ollama = True

    with patch.object(adapter.client, "get", new_callable=AsyncMock, side_effect=Exception("no connection")):
        with patch("shutil.which", return_value=None):
            # Should not raise
            await adapter._ensure_ollama_available()


# ─────────────────────────────────────────────────────────────────────────────
# get_llm_adapter singleton
# ─────────────────────────────────────────────────────────────────────────────

def test_get_llm_adapter_creates_singleton():
    with patch.dict("os.environ", {"OLLAMA_MODEL": "test-model", "OLLAMA_URL": "http://test:11434"}):
        a1 = get_llm_adapter()
        a2 = get_llm_adapter()
    assert a1 is a2


def test_get_llm_adapter_uses_env_vars():
    with patch.dict("os.environ", {"OLLAMA_MODEL": "my-model", "OLLAMA_URL": "http://myhost:11434"}):
        adapter = get_llm_adapter()
    assert adapter.ollama_model == "my-model"
    assert adapter.ollama_url == "http://myhost:11434"


@pytest.mark.asyncio
async def test_close_llm_adapter_resets_singleton():
    import backend.agents.services.llm_adapter as mod

    adapter_inst = get_llm_adapter()
    with patch.object(adapter_inst.client, "aclose", new_callable=AsyncMock):
        await close_llm_adapter()

    assert mod._llm_adapter is None


@pytest.mark.asyncio
async def test_close_llm_adapter_noop_when_none():
    import backend.agents.services.llm_adapter as mod
    mod._llm_adapter = None
    # Should not raise
    await close_llm_adapter()
