"""Tracking tests for CLI runners (Task 7 — TDD).

Scope:
- DeepSeekHTTPRunner: HTTP path, both success and error branches.
- GeminiCLIRunner: deferred (subprocess stdout has no structured token counts).
- ClaudeCLIRunner: intentionally untested — Max OAuth flat rate, no tracking.

Key contract note:
  DeepSeekHTTPRunner.run() swallows ALL exceptions via its bare ``except
  Exception`` and returns ``RunnerResult(ok=False)``.  The @llm_cost_tracked
  decorator's ``finally`` block always fires, so ``record_llm_call`` is always
  called.  On the error branch the decorator sees ``success=True`` (no
  exception escaped); tokens default to 0 because ``set_usage`` was never
  reached.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.services.council.cli_runners import DeepSeekHTTPRunner

# ---------------------------------------------------------------------------
# Success path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_runner_records_cost_on_success() -> None:
    """Decorator fires with correct provider/tokens on a good HTTP response."""
    runner = DeepSeekHTTPRunner(api_key="test-key")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "test reply"}}],
        "model": "deepseek-v4-pro",
        "usage": {"prompt_tokens": 50, "completion_tokens": 20},
    }
    fake_resp.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    runner._client = mock_client

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await runner.run(prompt="test prompt")

    assert result.ok is True
    assert result.output == "test reply"

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "deepseek"
    assert kwargs["model"] == "deepseek-v4-pro"
    assert kwargs["input_tokens"] == 50
    assert kwargs["output_tokens"] == 20
    assert kwargs["success"] is True
    assert kwargs["error_class"] is None


# ---------------------------------------------------------------------------
# Error path — exception is swallowed by the runner's bare except
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_runner_records_on_exception() -> None:
    """Decorator's finally block fires even when the runner swallows the error.

    Because DeepSeekHTTPRunner catches all exceptions internally and returns
    RunnerResult(ok=False), the decorator sees no raised exception and records
    success=True with zero tokens (set_usage was never reached).
    """
    runner = DeepSeekHTTPRunner(api_key="test-key")

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(side_effect=RuntimeError("rate limit"))
    runner._client = mock_client

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await runner.run(prompt="x")

    # Runner swallows the error — returns failed RunnerResult without raising
    assert result.ok is False
    assert "rate limit" in (result.error or "")

    # Decorator still fires via finally
    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "deepseek"
    # success=True because no exception escaped the decorated function
    assert kwargs["success"] is True
    # Tokens are 0 because set_usage() was never called (error occurred before)
    assert kwargs["input_tokens"] == 0
    assert kwargs["output_tokens"] == 0


# ---------------------------------------------------------------------------
# HTTP 4xx / 5xx non-exception path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_runner_records_on_http_error_status() -> None:
    """When the API returns a non-200 status (no exception), tracking fires."""
    runner = DeepSeekHTTPRunner(api_key="test-key")

    fake_resp = MagicMock()
    fake_resp.status_code = 429
    fake_resp.text = "Too Many Requests"

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    runner._client = mock_client

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        result = await runner.run(prompt="x")

    assert result.ok is False
    assert "HTTP 429" in (result.error or "")

    mock_rec.assert_awaited_once()
    kwargs = mock_rec.await_args.kwargs
    assert kwargs["provider"] == "deepseek"
    assert kwargs["success"] is True   # no exception escaped
    assert kwargs["input_tokens"] == 0
    assert kwargs["output_tokens"] == 0


# ---------------------------------------------------------------------------
# Model attribute is forwarded correctly
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deepseek_runner_uses_instance_model_slug() -> None:
    """record_llm_call receives the model slug from self.model."""
    runner = DeepSeekHTTPRunner(api_key="test-key", model="deepseek-chat")

    fake_resp = MagicMock()
    fake_resp.status_code = 200
    fake_resp.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=fake_resp)
    runner._client = mock_client

    with patch(
        "backend.services.observability.tracking_decorator.record_llm_call",
        new=AsyncMock(),
    ) as mock_rec:
        await runner.run(prompt="slug test")

    kwargs = mock_rec.await_args.kwargs
    assert kwargs["model"] == "deepseek-chat"
    assert kwargs["input_tokens"] == 10
    assert kwargs["output_tokens"] == 5
