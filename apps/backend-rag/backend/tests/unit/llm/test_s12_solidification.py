"""
S12 LLM Layer Solidification — targeted tests for the 5 fixes applied.

FIX-1: providers/ollama.py — _async_client initialized in __init__
FIX-2: retry_handler.py   — error classification (429 / 503 / timeout) + jitter
FIX-3: genai_client.py    — structured logging on generate_content / stream
FIX-4: ollama_client.py   — structured logging on all Ollama calls
FIX-5: ollama_client.py   — bare except -> explicit debug log in is_ollama_available
"""

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure backend package importable
_backend = Path(__file__).parents[5] / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))


# ---------------------------------------------------------------------------
# FIX-1: OllamaProvider._async_client initialized in __init__
# ---------------------------------------------------------------------------
class TestFix1OllamaProviderInit:
    def test_async_client_attr_exists_at_construction(self):
        """_async_client must be set to None in __init__ — no AttributeError on first use."""
        from backend.llm.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        assert hasattr(provider, "_async_client"), "_async_client must be set in __init__"
        assert provider._async_client is None

    @pytest.mark.asyncio
    async def test_get_async_client_creates_client_on_first_call(self):
        """_get_async_client() must not raise AttributeError on first call."""
        from backend.llm.providers.ollama import OllamaProvider

        provider = OllamaProvider()
        client = await provider._get_async_client()
        assert client is not None
        await provider.aclose()

    def test_init_client_removes_inline_httpx(self):
        """_init_client must NOT create an httpx.AsyncClient inline (dead code removed)."""
        import inspect

        from backend.llm.providers.ollama import OllamaProvider

        src = inspect.getsource(OllamaProvider._init_client)
        assert "httpx.AsyncClient" not in src, (
            "_init_client must not instantiate httpx.AsyncClient inline (S04 rule)"
        )


# ---------------------------------------------------------------------------
# FIX-2: retry_handler.py — error classification + jitter
# ---------------------------------------------------------------------------
class TestFix2RetryClassification:
    def test_classify_rate_limit_429(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("HTTP 429 Too Many Requests") == "rate_limit"

    def test_classify_rate_limit_quota(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("RESOURCE_EXHAUSTED: quota exceeded") == "rate_limit"

    def test_classify_overload_503(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("503 Service Unavailable") == "overload"

    def test_classify_transient_timeout(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("Read timeout after 30s") == "transient"

    def test_classify_transient_connection(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("Connection refused") == "transient"

    def test_classify_permanent_validation(self):
        from backend.llm.retry_handler import _classify_error

        assert _classify_error("invalid model name") == "permanent"

    def test_compute_delay_rate_limit_longer_than_transient(self):
        from backend.llm.retry_handler import _compute_delay

        rl_delay = _compute_delay("rate_limit", 0, base_delay=2.0, backoff_factor=2)
        tr_delay = _compute_delay("transient", 0, base_delay=2.0, backoff_factor=2)
        # Rate-limit base is 10s; transient base is 2s. Even with ±25% jitter, rl > tr.
        assert rl_delay > tr_delay

    def test_compute_delay_jitter_not_deterministic(self):
        """Two calls with same args must (probabilistically) produce different values."""
        from backend.llm.retry_handler import _compute_delay

        delays = {_compute_delay("transient", 0, 2.0, 2) for _ in range(20)}
        # With 20 samples and ±25% jitter, at least 2 distinct values expected.
        assert len(delays) > 1

    @pytest.mark.asyncio
    async def test_rate_limit_error_is_retried(self):
        """429-style errors must trigger retry (not immediate fail)."""
        from backend.llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01, backoff_factor=1)
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            if calls < 2:
                raise Exception("429 rate limit exceeded")
            return "ok"

        result = await handler.execute_with_retry(op, "test_op")
        assert result == "ok"
        assert calls == 2

    @pytest.mark.asyncio
    async def test_permanent_error_fails_immediately(self):
        """Non-retryable errors must not consume retry budget."""
        from backend.llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=3, base_delay=0.01, backoff_factor=1)
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            raise ValueError("invalid model name xyz")

        with pytest.raises(ValueError, match="invalid model name"):
            await handler.execute_with_retry(op, "test_op")

        assert calls == 1, "Permanent error must not retry"

    @pytest.mark.asyncio
    async def test_custom_retryable_errors_backward_compat(self):
        """Passing custom retryable_errors list must still work (backward compat)."""
        from backend.llm.retry_handler import RetryHandler

        handler = RetryHandler(max_retries=2, base_delay=0.01, backoff_factor=1)
        calls = 0

        async def op():
            nonlocal calls
            calls += 1
            if calls < 2:
                raise Exception("custom_transient_error")
            return "ok"

        result = await handler.execute_with_retry(op, "op", retryable_errors=["custom_transient"])
        assert result == "ok"
        assert calls == 2


# ---------------------------------------------------------------------------
# FIX-3: genai_client.py — structured logging
# ---------------------------------------------------------------------------
class TestFix3GenAIStructuredLogging:
    @pytest.mark.asyncio
    async def test_generate_content_logs_structured(self, caplog):
        """generate_content must emit a log record with provider, model, latency_ms fields."""
        import logging

        from backend.llm.genai_client import GenAIClient

        client = GenAIClient.__new__(GenAIClient)
        client._available = True

        mock_response = MagicMock()
        mock_response.text = "Hello"
        mock_response.usage_metadata = MagicMock(prompt_token_count=10, candidates_token_count=5)

        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(return_value=mock_response)
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        client._client = mock_client

        with caplog.at_level(logging.INFO, logger="backend.llm.genai_client"):
            result = await client.generate_content("test", model="gemini-2.0-flash")

        assert result["text"] == "Hello"
        # Find the structured log record
        llm_records = [r for r in caplog.records if "LLM call" in r.getMessage() or
                       getattr(r, "provider", None) == "gemini"]
        assert len(llm_records) >= 1

    @pytest.mark.asyncio
    async def test_generate_content_logs_on_error(self, caplog):
        """generate_content must log even when the call fails."""
        import logging

        from backend.llm.genai_client import GenAIClient

        client = GenAIClient.__new__(GenAIClient)
        client._available = True

        mock_aio = MagicMock()
        mock_aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API error"))
        mock_client = MagicMock()
        mock_client.aio = mock_aio
        client._client = mock_client

        with caplog.at_level(logging.ERROR, logger="backend.llm.genai_client"):
            with pytest.raises(RuntimeError):
                await client.generate_content("test", model="gemini-2.0-flash")

        error_records = [r for r in caplog.records if r.levelno >= logging.ERROR]
        assert len(error_records) >= 1


# ---------------------------------------------------------------------------
# FIX-4: ollama_client.py — structured logging
# ---------------------------------------------------------------------------
class TestFix4OllamaStructuredLogging:
    @pytest.mark.asyncio
    async def test_ollama_generate_logs_structured(self, caplog):
        """ollama_generate must emit a structured INFO log with provider/model/latency_ms."""
        import logging

        import httpx

        import backend.llm.ollama_client as oc

        oc._client = None

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "result",
            "prompt_eval_count": 5,
            "eval_count": 3,
        }

        mock_client = MagicMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        with patch("backend.llm.ollama_client._get_client", return_value=mock_client):
            with caplog.at_level(logging.INFO, logger="backend.llm.ollama_client"):
                result = await oc.ollama_generate("hello", model="qwen3.5:9b")

        assert result == "result"
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) >= 1

    @pytest.mark.asyncio
    async def test_ollama_generate_returns_none_on_connect_error(self):
        """ConnectError must return None (no exception propagated)."""
        import httpx

        import backend.llm.ollama_client as oc

        oc._client = None

        mock_client = MagicMock()
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with patch("backend.llm.ollama_client._get_client", return_value=mock_client):
            result = await oc.ollama_generate("hello")

        assert result is None


# ---------------------------------------------------------------------------
# FIX-5: ollama_client.py — is_ollama_available bare except -> debug log
# ---------------------------------------------------------------------------
class TestFix5OllamaAvailabilityLogging:
    @pytest.mark.asyncio
    async def test_availability_check_logs_on_exception(self, caplog):
        """is_ollama_available must log debug message (not swallow silently) on exception."""
        import logging

        import httpx

        import backend.llm.ollama_client as oc

        oc._client = None

        mock_client = MagicMock()
        mock_client.get = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.is_closed = False

        with patch("backend.llm.ollama_client._get_client", return_value=mock_client):
            with caplog.at_level(logging.DEBUG, logger="backend.llm.ollama_client"):
                result = await oc.is_ollama_available()

        assert result is False
        debug_records = [r for r in caplog.records if r.levelno == logging.DEBUG]
        assert len(debug_records) >= 1

    def test_is_ollama_available_no_bare_except(self):
        """is_ollama_available must not contain a bare 'except:' clause."""
        import inspect

        import backend.llm.ollama_client as oc

        src = inspect.getsource(oc.is_ollama_available)
        lines = [ln.strip() for ln in src.splitlines()]
        bare = [ln for ln in lines if ln == "except:"]
        assert bare == [], f"Found bare except clauses: {bare}"


# ---------------------------------------------------------------------------
# R1: zantara_ai_client.py — stream retry uses _classify_error / _compute_delay
# ---------------------------------------------------------------------------
class TestR1StreamRetryClassification:
    def test_stream_imports_classify_and_compute(self):
        """zantara_ai_client must import _classify_error and _compute_delay from retry_handler."""
        import backend.llm.zantara_ai_client as zac

        assert hasattr(zac, "_classify_error"), "must import _classify_error"
        assert hasattr(zac, "_compute_delay"), "must import _compute_delay"

    def test_stream_no_raw_backoff_formula(self):
        """Stream retry must not duplicate raw backoff formula (base_delay * backoff_factor**attempt)."""
        import inspect

        import backend.llm.zantara_ai_client as zac

        src = inspect.getsource(zac.ZantaraAIClient.stream)
        # The old duplicated formula was: base_delay * (backoff_factor**attempt)
        assert "base_delay * (self.retry_handler.backoff_factor**attempt)" not in src, (
            "Raw backoff formula must be replaced by _compute_delay()"
        )


# ---------------------------------------------------------------------------
# R2: genai_client.py — DEFAULT_TIMEOUT_MS + HttpOptions in config
# ---------------------------------------------------------------------------
class TestR2TimeoutInConfig:
    def test_default_timeout_ms_exists(self):
        """GenAIClient must expose DEFAULT_TIMEOUT_MS class attribute."""
        from backend.llm.genai_client import GenAIClient

        assert hasattr(GenAIClient, "DEFAULT_TIMEOUT_MS")
        assert GenAIClient.DEFAULT_TIMEOUT_MS > 0

    def test_get_config_includes_http_options(self):
        """_get_config must embed HttpOptions(timeout=...) in GenerateContentConfig."""
        from google.genai import types

        from backend.llm.genai_client import GenAIClient

        client = GenAIClient.__new__(GenAIClient)
        client._available = True

        # Patch genai/types availability
        config = client._get_config(max_output_tokens=512, temperature=0.5)
        assert config is not None
        assert config.http_options is not None
        assert config.http_options.timeout == GenAIClient.DEFAULT_TIMEOUT_MS

    def test_get_config_custom_timeout(self):
        """_get_config with explicit timeout_ms overrides the default."""
        from backend.llm.genai_client import GenAIClient

        client = GenAIClient.__new__(GenAIClient)
        client._available = True

        config = client._get_config(timeout_ms=5_000)
        assert config.http_options.timeout == 5_000

    def test_generate_content_signature_has_timeout_ms(self):
        """generate_content and generate_content_stream must accept timeout_ms kwarg."""
        import inspect

        from backend.llm.genai_client import GenAIClient

        sig_gen = inspect.signature(GenAIClient.generate_content)
        sig_stream = inspect.signature(GenAIClient.generate_content_stream)
        assert "timeout_ms" in sig_gen.parameters
        assert "timeout_ms" in sig_stream.parameters


# ---------------------------------------------------------------------------
# R5: LLMMetricsEmitter — unit tests
# ---------------------------------------------------------------------------
class TestR5MetricsEmitter:
    @pytest.mark.asyncio
    async def test_emit_noop_when_redis_unavailable(self):
        """emit_llm_metric must not raise when Redis is unavailable."""
        from backend.llm.metrics_emitter import emit_llm_metric

        with patch("backend.llm.metrics_emitter._get_redis", return_value=None):
            # Should complete without raising
            await emit_llm_metric(
                provider="gemini", model="gemini-2.0-flash",
                latency_ms=250, prompt_tokens=100, completion_tokens=50,
            )

    @pytest.mark.asyncio
    async def test_emit_calls_xadd_when_redis_available(self):
        """emit_llm_metric must call redis.xadd with correct stream key and fields."""
        from backend.llm.metrics_emitter import _STREAM_KEY, emit_llm_metric

        mock_redis = AsyncMock()

        with patch("backend.llm.metrics_emitter._get_redis", return_value=mock_redis):
            await emit_llm_metric(
                provider="ollama", model="qwen3.5:9b",
                latency_ms=420, prompt_tokens=80, completion_tokens=30,
                status="ok",
            )

        mock_redis.xadd.assert_called_once()
        call_args = mock_redis.xadd.call_args
        assert call_args[0][0] == _STREAM_KEY
        fields = call_args[0][1]
        assert fields["provider"] == "ollama"
        assert fields["model"] == "qwen3.5:9b"
        assert fields["latency_ms"] == "420"
        assert fields["prompt_tokens"] == "80"
        assert fields["completion_tokens"] == "30"
        assert fields["status"] == "ok"

    @pytest.mark.asyncio
    async def test_emit_swallows_redis_error(self):
        """emit_llm_metric must not propagate Redis errors (fire-and-forget)."""
        from backend.llm.metrics_emitter import emit_llm_metric

        mock_redis = AsyncMock()
        mock_redis.xadd.side_effect = ConnectionError("Redis down")

        with patch("backend.llm.metrics_emitter._get_redis", return_value=mock_redis):
            # Must not raise
            await emit_llm_metric(
                provider="gemini", model="gemini-2.0-flash", latency_ms=100,
            )

    @pytest.mark.asyncio
    async def test_emit_error_status(self):
        """emit_llm_metric with status='error' must persist that field."""
        from backend.llm.metrics_emitter import emit_llm_metric

        mock_redis = AsyncMock()

        with patch("backend.llm.metrics_emitter._get_redis", return_value=mock_redis):
            await emit_llm_metric(
                provider="gemini", model="gemini-2.0-flash",
                latency_ms=50, status="error",
            )

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["status"] == "error"

    @pytest.mark.asyncio
    async def test_emit_extra_fields(self):
        """emit_llm_metric extra dict is merged into stream fields."""
        from backend.llm.metrics_emitter import emit_llm_metric

        mock_redis = AsyncMock()

        with patch("backend.llm.metrics_emitter._get_redis", return_value=mock_redis):
            await emit_llm_metric(
                provider="gemini", model="gemini-2.0-flash",
                latency_ms=100, extra={"chunks": "12"},
            )

        fields = mock_redis.xadd.call_args[0][1]
        assert fields["chunks"] == "12"
