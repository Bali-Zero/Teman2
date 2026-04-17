"""
Claude client for article_composer — Max-plan OAuth subprocess edition.

Previously this wrapped ``anthropic.Anthropic`` (pay-as-you-go API key).
Project policy forbids ``ANTHROPIC_API_KEY`` — all Claude calls must go
through the Max OAuth token via ``claude -p`` (see
``memory/feedback_claude_oauth_only.md``).

This module now:
- calls ``backend.llm.claude_oauth_client.complete_async`` instead of the
  SDK,
- returns a lightweight object that mimics the subset of
  ``anthropic.types.Message`` actually consumed by the caller
  (``content[0].text``, ``usage.input_tokens``, ``usage.output_tokens``),
  so ``app/routers/article_composer.py`` keeps working unchanged,
- keeps the tenacity retry + circuit breaker for defense-in-depth on
  transient subprocess failures,
- drops the anthropic SDK import entirely — `get_anthropic_client` is
  gone, replaced by ``None``-returning compatibility shim only used by
  tests that import the symbol.
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

from backend.llm.claude_oauth_client import (
    ClaudeOAuthError,
    ClaudeOAuthNotAvailable,
    complete_async,
)

# The caller touches only these attributes on the return value:
# - message.content[0].text
# - message.usage.input_tokens
# - message.usage.output_tokens
#
# We reproduce that shape with plain dataclasses so the router keeps
# working unchanged.


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

    Exposes the same attribute tree (``content[0].text``, ``usage.*``) but
    carries no SDK dependency.
    """

    content: list[_TextBlock]
    usage: _Usage
    model: str
    token_label: str

    @property
    def input_text(self) -> str:
        return self.content[0].text if self.content else ""


# Backward-compatible export so
# `from backend.services.article_composer import Message` keeps working
# without dragging in the anthropic SDK at import time.
Message = ClaudeOAuthMessage  # type: ignore[misc]

logger = logging.getLogger(__name__)


class ClaudeClientError(RuntimeError):
    """Raised for any retryable transport error from the OAuth subprocess."""


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


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


# Global circuit breaker instance
_claude_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


# Rough token-count estimate: the OAuth subprocess has no usage telemetry
# (Claude CLI prints only the completion). We approximate tokens as
# ``len(text) // 4``, which is the industry rule-of-thumb and what
# ``backend.llm.token_estimator`` uses under the hood.
def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def get_anthropic_client() -> None:
    """Removed — kept only as a shim that raises, so callers fail loudly.

    This module no longer uses ``anthropic.Anthropic``. All Claude traffic
    goes via ``backend.llm.claude_oauth_client``. Any code still calling
    this helper is on the wrong path.
    """
    raise RuntimeError(
        "get_anthropic_client() is removed: Claude goes via Max OAuth now. "
        "Use call_claude_with_retry() or backend.llm.claude_oauth_client.",
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((ClaudeClientError, ClaudeOAuthError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_claude_with_retry(
    prompt: str,
    model: str = "claude-sonnet-4-6",
    max_tokens: int = 4096,
) -> ClaudeOAuthMessage:
    """Call Claude via Max OAuth with automatic retry on transient errors.

    Behavioral contract preserved from the SDK version:
    - Exponential backoff (2s, 4s, 8s), max 3 attempts on transient errors.
    - Circuit breaker protection (5 failures → OPEN for 60s).
    - Returns an object exposing ``content[0].text`` and
      ``usage.{input,output}_tokens`` just like the old Anthropic
      ``Message``, so the caller in
      ``app/routers/article_composer.py`` is untouched.

    Changes from the SDK version:
    - No ``cache_control`` — the ``claude -p`` CLI doesn't surface the
      request-body builder. The cache win is deferred until we move to a
      different transport (Claude Agent SDK or raw HTTP via OAuth).
    - ``usage.*`` are estimates (``len(text)//4``); the CLI doesn't return
      usage metadata.
    - ``max_tokens`` is **ignored** (the CLI has no flag for it). Left in
      the signature for drop-in compatibility.

    Args:
        prompt: The prompt to send to Claude.
        model: Model slug forwarded to ``claude -p --model``.
        max_tokens: Accepted but ignored (kept for API compat).

    Returns:
        :class:`ClaudeOAuthMessage` — SDK-shaped response wrapper.
    """
    del max_tokens  # retained for API compat; CLI has no max_tokens flag

    async def _make_request() -> ClaudeOAuthMessage:
        try:
            resp = await complete_async(prompt, model=model)
        except ClaudeOAuthNotAvailable:
            raise
        except ClaudeOAuthError as exc:
            # Let tenacity retry transient OAuth failures.
            raise ClaudeClientError(str(exc)) from exc

        return ClaudeOAuthMessage(
            content=[_TextBlock(text=resp.text)],
            usage=_Usage(
                input_tokens=_estimate_tokens(prompt),
                output_tokens=_estimate_tokens(resp.text),
            ),
            model=model,
            token_label=resp.token_label,
        )

    try:
        message = await _claude_circuit_breaker.call(_make_request)
    except ClaudeOAuthNotAvailable as exc:
        logger.error("claude CLI missing, no retry possible: %s", exc)
        raise
    except ClaudeClientError as exc:
        logger.warning(
            "Transient Claude error, tenacity will retry: %s",
            exc,
            extra={"error_type": "ClaudeClientError"},
        )
        raise

    logger.info(
        "Claude OAuth call successful",
        extra={
            "model": message.model,
            "input_tokens": message.usage.input_tokens,
            "output_tokens": message.usage.output_tokens,
            "token_label": message.token_label,
        },
    )
    return message
