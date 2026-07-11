from unittest.mock import AsyncMock

import pytest

from backend.llm.deepseek_client import DeepSeekError, DeepSeekResponse
from backend.services.article_composer import claude_client
from backend.services.article_composer.claude_client import (
    CircuitBreaker,
    CircuitState,
    ClaudeClientError,
    call_claude_with_retry,
    get_anthropic_client,
)


def test_get_anthropic_client_fails_loudly_after_deepseek_migration() -> None:
    with pytest.raises(RuntimeError, match="article_composer now uses DeepSeek"):
        get_anthropic_client()


@pytest.mark.asyncio
async def test_call_claude_with_retry_returns_backward_compatible_message(monkeypatch) -> None:
    complete_async = AsyncMock(
        return_value=DeepSeekResponse(
            text='{"ok": true}',
            model="deepseek-v4-pro",
            input_tokens=12,
            output_tokens=34,
            cache_hit_tokens=5,
            finish_reason="stop",
        )
    )
    monkeypatch.setattr(claude_client, "complete_async", complete_async)
    monkeypatch.setattr(claude_client, "_llm_circuit_breaker", CircuitBreaker())

    message = await call_claude_with_retry("compose article", model="deepseek-v4-pro", max_tokens=99)

    complete_async.assert_awaited_once_with(
        "compose article",
        model="deepseek-v4-pro",
        max_tokens=99,
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    assert message.content[0].text == '{"ok": true}'
    assert message.input_text == '{"ok": true}'
    assert message.usage.input_tokens == 12
    assert message.usage.output_tokens == 34
    assert message.model == "deepseek-v4-pro"
    assert message.token_label == "deepseek_cache_hit=5"


@pytest.mark.asyncio
async def test_call_claude_with_retry_wraps_transient_deepseek_errors(monkeypatch) -> None:
    monkeypatch.setattr(
        claude_client,
        "complete_async",
        AsyncMock(side_effect=DeepSeekError("temporary outage")),
    )
    monkeypatch.setattr(claude_client, "_llm_circuit_breaker", CircuitBreaker())

    with pytest.raises(ClaudeClientError, match="temporary outage"):
        await call_claude_with_retry("compose article")


@pytest.mark.asyncio
async def test_circuit_breaker_opens_after_threshold_and_resets_after_success() -> None:
    breaker = CircuitBreaker(failure_threshold=1, recovery_timeout=0, half_open_max_calls=1)

    async def fail() -> None:
        raise RuntimeError("down")

    async def succeed() -> str:
        return "ok"

    with pytest.raises(RuntimeError, match="down"):
        await breaker.call(fail)
    assert breaker.state == CircuitState.OPEN

    assert await breaker.call(succeed) == "ok"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.failure_count == 0
