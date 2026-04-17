"""LLM client for article_composer — now DeepSeek, previously Claude.

History:
- v1: wrapped ``anthropic.Anthropic`` (pay-as-you-go API key).
- v2: switched to Claude Max OAuth via ``claude -p`` subprocess
  (``backend.llm.claude_oauth_client``) per project policy
  ``memory/feedback_claude_oauth_only.md``.
- v3 (this file): migrated to DeepSeek (``deepseek-chat``) because the
  ``claude`` CLI hangs inside the Fly container on Linux non-TTY
  (``memory/feedback_claude_cli_linux_hang.md``). DeepSeek is ~100x
  cheaper than Claude Sonnet for structured JSON output and returns
  clean usage counters.

Public symbols preserved for router/backward-compat:
- ``call_claude_with_retry`` — same signature, internally calls DeepSeek.
- ``ClaudeClientError`` — same retryable exception class.
- ``ClaudeOAuthMessage`` (alias ``Message``) — same response shape
  (``content[0].text``, ``usage.input_tokens``, ``usage.output_tokens``).
- ``get_anthropic_client`` — still raises on call (unchanged).
"""

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.llm.deepseek_client import (
    DeepSeekAuthError,
    DeepSeekError,
    complete_async,
)


@dataclass(frozen=True)
class _TextBlock:
    text: str
    type: str = "text"


@dataclass(frozen=True)
class _Usage:
    input_tokens: int
    output_tokens: int


@dataclass(frozen=True)
class ClaudeOAuthMessage:
    """Minimal drop-in for anthropic.types.Message consumed by callers.

    Name retained for backward compatibility with the Claude-era code; the
    payload now comes from DeepSeek. Router only touches
    ``content[0].text`` and ``usage.{input,output}_tokens``.
    """

    content: list[_TextBlock]
    usage: _Usage
    model: str
    token_label: str

    @property
    def input_text(self) -> str:
        return self.content[0].text if self.content else ""


Message = ClaudeOAuthMessage  # backward-compat alias

logger = logging.getLogger(__name__)


class ClaudeClientError(RuntimeError):
    """Raised for retryable transport errors from the LLM client.

    Name retained from the Claude era. Now wraps transient DeepSeek HTTP
    errors so tenacity can retry them.
    """


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Simple circuit breaker implementation"""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time: float | None = None
        self.half_open_calls = 0

    async def call(self, func: Any, *args, **kwargs) -> Any:
        """Execute async function with circuit breaker protection."""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise ClaudeClientError("Circuit breaker is OPEN - service unavailable")

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _on_success(self) -> None:
        """Handle successful call"""
        if self.state == CircuitState.HALF_OPEN:
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                logger.info("Circuit breaker: CLOSED (service recovered)")
        else:
            self.failure_count = 0

    def _on_failure(self) -> None:
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning("Circuit breaker: OPEN (half-open test failed)")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.error(
                f"Circuit breaker: OPEN (failure threshold {self.failure_threshold} reached)",
            )


_llm_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


def get_anthropic_client() -> None:
    """Removed — kept only as a shim that raises, so callers fail loudly.

    This module has no Anthropic SDK dependency. Use
    :func:`call_claude_with_retry` or ``backend.llm.deepseek_client``.
    """
    raise RuntimeError(
        "get_anthropic_client() is removed. article_composer now uses DeepSeek "
        "via backend.llm.deepseek_client. Call call_claude_with_retry() instead.",
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ClaudeClientError, DeepSeekError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_claude_with_retry(
    prompt: str,
    model: str = "deepseek-chat",
    max_tokens: int = 4096,
) -> ClaudeOAuthMessage:
    """Call DeepSeek with automatic retry on transient errors.

    Signature kept for drop-in compatibility with the router that still
    imports this symbol. The ``model`` default changed from
    ``claude-sonnet-4-6`` to ``deepseek-chat``. The return object still
    exposes ``content[0].text`` and ``usage.{input,output}_tokens`` so the
    router needs no changes to its happy path.
    """

    async def _make_request() -> ClaudeOAuthMessage:
        try:
            resp = await complete_async(
                prompt,
                model=model,
                max_tokens=max_tokens,
                temperature=0.3,
                response_format={"type": "json_object"},
            )
        except DeepSeekAuthError:
            raise
        except DeepSeekError as exc:
            raise ClaudeClientError(str(exc)) from exc

        return ClaudeOAuthMessage(
            content=[_TextBlock(text=resp.text)],
            usage=_Usage(
                input_tokens=resp.input_tokens,
                output_tokens=resp.output_tokens,
            ),
            model=resp.model,
            token_label=f"deepseek_cache_hit={resp.cache_hit_tokens}",
        )

    try:
        message = await _llm_circuit_breaker.call(_make_request)
    except DeepSeekAuthError as exc:
        logger.error("DeepSeek auth failed, no retry possible: %s", exc)
        raise
    except ClaudeClientError as exc:
        logger.warning(
            "Transient DeepSeek error, tenacity will retry: %s",
            exc,
            extra={"error_type": "ClaudeClientError"},
        )
        raise

    logger.info(
        "DeepSeek call successful",
        extra={
            "model": message.model,
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
            "token_label": message.token_label,
        },
    )
    return message
