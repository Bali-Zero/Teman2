"""
Retry Handler - Centralized retry logic with exponential backoff

Separated from ZantaraAIClient to follow Single Responsibility Principle.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Retryable error keywords
RETRYABLE_ERROR_KEYWORDS = [
    "connection",
    "timeout",
    "network",
    "api",
    "rate",
    "server",
    "unavailable",
    "503",
    "502",
    "429",
]


class RetryHandler:
    """
    Centralized retry handler with exponential backoff.

    Provides consistent retry logic across all API calls.
    """

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        backoff_factor: int = 2,
    ):
        """
        Initialize RetryHandler.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds before first retry
            backoff_factor: Multiplier for exponential backoff
        """
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
            retryable_errors: List of error keywords that should trigger retry.
                If None, uses default RETRYABLE_ERROR_KEYWORDS.

        Returns:
            Result of operation if successful.

        Raises:
            Exception: Last exception if all retries fail.
        """
        if retryable_errors is None:
            retryable_errors = RETRYABLE_ERROR_KEYWORDS

        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                return await operation()
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                # Check if error is retryable
                is_retryable = any(keyword in error_msg for keyword in retryable_errors)

                if not is_retryable or attempt >= self.max_retries - 1:
                    # Not retryable or last attempt
                    logger.error(
                        f"❌ {operation_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    raise e

                # Calculate delay with exponential backoff
                delay = self.base_delay * (self.backoff_factor**attempt)
                logger.warning(
                    f"⚠️ {operation_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError(f"{operation_name} failed after {self.max_retries} attempts")










