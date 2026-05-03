"""
Retry Handler - Centralized retry logic with exponential backoff + jitter

Separated from ZantaraAIClient to follow Single Responsibility Principle.
S12: Added error classification (429 rate-limit vs 503 overload vs timeout),
     jitter to prevent thundering herd, and structured retry logging.
"""

import asyncio
import logging
import random
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Keyword sets for error classification
_RATE_LIMIT_KEYWORDS = {"429", "rate limit", "quota", "resource_exhausted", "too many requests"}
_OVERLOAD_KEYWORDS = {"503", "502", "overloaded", "unavailable", "service unavailable"}
_TRANSIENT_KEYWORDS = {"connection", "timeout", "network", "reset", "broken pipe"}

# Legacy alias — kept for callers that pass custom retryable_errors
RETRYABLE_ERROR_KEYWORDS = [
    "connection", "timeout", "network", "api", "rate", "server",
    "unavailable", "503", "502", "429",
]

# Rate-limit backoff: longer base + bigger cap (Gemini 429 → 60s window)
_RATE_LIMIT_BASE_DELAY = 10.0
_RATE_LIMIT_MAX_DELAY = 60.0


def _classify_error(error_msg: str) -> str:
    """Return 'rate_limit', 'overload', 'transient', or 'permanent'."""
    msg = error_msg.lower()
    if any(k in msg for k in _RATE_LIMIT_KEYWORDS):
        return "rate_limit"
    if any(k in msg for k in _OVERLOAD_KEYWORDS):
        return "overload"
    if any(k in msg for k in _TRANSIENT_KEYWORDS):
        return "transient"
    return "permanent"


def _compute_delay(error_class: str, attempt: int, base_delay: float, backoff_factor: int) -> float:
    """Exponential backoff with ±25% jitter. Rate-limit errors get a longer base."""
    if error_class == "rate_limit":
        raw = min(_RATE_LIMIT_BASE_DELAY * (backoff_factor ** attempt), _RATE_LIMIT_MAX_DELAY)
    else:
        raw = base_delay * (backoff_factor ** attempt)
    jitter = raw * 0.25 * (random.random() * 2 - 1)  # ±25%
    return max(0.1, raw + jitter)


class RetryHandler:
    """
    Centralized retry handler with exponential backoff.

    Provides consistent retry logic across all API calls.
    Error classification: 429 (rate-limit) → long backoff; 503/timeout → normal backoff.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        backoff_factor: int = 2,
    ) -> None:
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.backoff_factor = backoff_factor

    async def execute_with_retry(
        self,
        operation: Callable[[], Any],
        operation_name: str = "operation",
        retryable_errors: list[str] | None = None,
    ) -> T:
        """
        Execute operation with retry logic.

        Args:
            operation: Async function to execute
            operation_name: Name of operation for logging
            retryable_errors: Custom keyword list; if None uses built-in classification.

        Returns:
            Result of operation if successful.

        Raises:
            Exception: Last exception if all retries exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                error_msg = str(e)
                error_class = _classify_error(error_msg)

                # Custom keyword list takes precedence (backward compat)
                if retryable_errors is not None:
                    msg_lower = error_msg.lower()
                    is_retryable = any(k in msg_lower for k in retryable_errors)
                else:
                    is_retryable = error_class != "permanent"

                if not is_retryable or attempt >= self.max_retries - 1:
                    logger.error(
                        "LLM retry exhausted",
                        extra={
                            "operation": operation_name,
                            "attempt": attempt + 1,
                            "max_retries": self.max_retries,
                            "error_class": error_class,
                            "error": str(e),
                        },
                    )
                    raise e

                delay = _compute_delay(error_class, attempt, self.base_delay, self.backoff_factor)
                logger.warning(
                    "LLM retry scheduled",
                    extra={
                        "operation": operation_name,
                        "attempt": attempt + 1,
                        "max_retries": self.max_retries,
                        "error_class": error_class,
                        "delay_s": round(delay, 2),
                        "error": str(e),
                    },
                )
                await asyncio.sleep(delay)

        if last_exception:
            raise last_exception
        raise RuntimeError(f"{operation_name} failed after {self.max_retries} attempts")
