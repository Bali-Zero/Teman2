"""
Claude API Client with Retry Logic and Circuit Breaker

Best Practices 2026 Implementation:
- Retry with exponential backoff
- Circuit breaker for resilience
- Connection pooling
- Structured error handling
"""

import logging
import os
import time
from enum import Enum
from typing import TYPE_CHECKING, Any

import anthropic
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

if TYPE_CHECKING:
    from anthropic.types import Message
else:
    # Runtime type hint - use Any to avoid import issues
    Message = type(None)  # Will be replaced at runtime

logger = logging.getLogger(__name__)


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

    def call(self, func: Any, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise anthropic.APIError(
                    message="Circuit breaker is OPEN - service unavailable",
                    response=None,
                    body=None,
                    request=None,
                )

        try:
            result = func(*args, **kwargs)
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
                f"Circuit breaker: OPEN (failure threshold {self.failure_threshold} reached)"
            )


# Global circuit breaker instance
_claude_circuit_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=60)


# Global Anthropic client instance (connection pooling)
_anthropic_client: anthropic.Anthropic | None = None


def get_anthropic_client() -> anthropic.Anthropic:
    """
    Get or create Anthropic client singleton with connection pooling.

    Best Practice: Reuse client instance instead of creating new one each time.
    """
    global _anthropic_client

    if _anthropic_client is None:
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY environment variable not set")

        _anthropic_client = anthropic.Anthropic(
            api_key=api_key,
            max_retries=0,  # We handle retries ourselves with tenacity
            timeout=30.0,  # 30 second timeout
        )
        logger.info("Initialized Anthropic client with connection pooling")

    return _anthropic_client


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(
        (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
        )
    ),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
async def call_claude_with_retry(
    prompt: str,
    model: str = "claude-sonnet-4-20250514",
    max_tokens: int = 4096,
) -> "Message":
    """
    Call Claude API with automatic retry on transient errors.

    Best Practices 2026:
    - Exponential backoff (2s, 4s, 8s)
    - Retry only on transient errors (rate limit, connection, timeout)
    - Circuit breaker protection
    - Structured error logging

    Args:
        prompt: The prompt to send to Claude
        model: Model to use (default: claude-sonnet-4-20250514)
        max_tokens: Maximum tokens to generate

    Returns:
        Claude API response message

    Raises:
        anthropic.APIError: For non-retryable errors or after max retries
    """
    client = get_anthropic_client()

    def _make_request() -> Any:
        """Make the actual API request"""
        return client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

    try:
        # Use circuit breaker
        message = _claude_circuit_breaker.call(_make_request)

        logger.info(
            "Claude API call successful",
            extra={
                "model": model,
                "input_tokens": message.usage.input_tokens,
                "output_tokens": message.usage.output_tokens,
            },
        )

        return message

    except anthropic.RateLimitError as e:
        logger.warning(
            f"Rate limit hit, retrying: {e}",
            extra={
                "error_type": "RateLimitError",
                "retry_after": getattr(e, "retry_after", None),
            },
        )
        raise

    except anthropic.APIConnectionError as e:
        logger.warning(
            f"Connection error, retrying: {e}",
            extra={"error_type": "APIConnectionError"},
        )
        raise

    except anthropic.APITimeoutError as e:
        logger.warning(
            f"Timeout error, retrying: {e}",
            extra={"error_type": "APITimeoutError"},
        )
        raise

    except anthropic.APIError as e:
        # Non-retryable errors (authentication, invalid request, etc.)
        logger.error(
            f"Claude API error (non-retryable): {e}",
            extra={
                "error_type": type(e).__name__,
                "error_message": str(e),
            },
        )
        raise
