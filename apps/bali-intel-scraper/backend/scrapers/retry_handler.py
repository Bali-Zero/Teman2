"""
Retry handler with exponential backoff and jitter.

Provides intelligent retry logic for failed operations.
"""

import asyncio
import random
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any
from collections.abc import Callable

from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="retry_handler")


class RetryStrategy(Enum):
    """Retry backoff strategies."""

    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    EXPONENTIAL_JITTER = "exponential_jitter"


@dataclass
class RetryConfig:
    """Retry configuration."""

    max_retries: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    on_retry: Callable | None = None
    on_failure: Callable | None = None


class RetryHandler:
    """Handles retry logic with configurable strategies."""

    def __init__(self, config: RetryConfig | None = None):
        self.config = config or RetryConfig()

    def calculate_delay(self, attempt: int) -> float:
        """Calculate delay for the given attempt."""
        if self.config.strategy == RetryStrategy.FIXED:
            return self.config.base_delay

        elif self.config.strategy == RetryStrategy.LINEAR:
            return min(self.config.base_delay * attempt, self.config.max_delay)

        elif self.config.strategy == RetryStrategy.EXPONENTIAL:
            return min(self.config.base_delay * (2**attempt), self.config.max_delay)

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_JITTER:
            base = min(self.config.base_delay * (2**attempt), self.config.max_delay)
            # Add 0-25% jitter
            jitter = base * 0.25 * random.random()
            return base + jitter

        return self.config.base_delay

    async def execute(
        self, func: Callable, *args, operation_name: str = "operation", **kwargs
    ) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.config.max_retries + 1):
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)

                if attempt > 0:
                    logger.info(
                        f"{operation_name} succeeded after {attempt} retries",
                        action=LogAction.END,
                        metadata={"retries": attempt},
                    )

                return result

            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt == self.config.max_retries:
                    break

                delay = self.calculate_delay(attempt)

                logger.warning(
                    f"{operation_name} failed, retrying in {delay:.2f}s",
                    action=LogAction.RETRY,
                    metadata={
                        "attempt": attempt + 1,
                        "max_retries": self.config.max_retries,
                        "delay": round(delay, 2),
                        "error": str(e),
                    },
                )

                if self.config.on_retry:
                    if asyncio.iscoroutinefunction(self.config.on_retry):
                        await self.config.on_retry(e, attempt)
                    else:
                        self.config.on_retry(e, attempt)

                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            f"{operation_name} failed after {self.config.max_retries} retries",
            action=LogAction.ERROR,
            metadata={"retries": self.config.max_retries, "error": str(last_exception)},
        )

        if self.config.on_failure:
            if asyncio.iscoroutinefunction(self.config.on_failure):
                await self.config.on_failure(last_exception)
            else:
                self.config.on_failure(last_exception)

        raise last_exception


def with_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_JITTER,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
):
    """Decorator for adding retry logic to functions."""

    def decorator(func: Callable) -> Callable:
        handler = RetryConfig(
            max_retries=max_retries,
            base_delay=base_delay,
            max_delay=max_delay,
            strategy=strategy,
            retryable_exceptions=retryable_exceptions,
        )
        retry_handler = RetryHandler(handler)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await retry_handler.execute(
                func, *args, operation_name=func.__name__, **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, run in executor
            loop = asyncio.get_event_loop()
            return loop.run_until_complete(
                retry_handler.execute(
                    func, *args, operation_name=func.__name__, **kwargs
                )
            )

        import inspect

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


class CircuitBreakerAwareRetry:
    """Retry handler that works with circuit breakers."""

    def __init__(
        self,
        config: RetryConfig | None = None,
        circuit_breaker_name: str | None = None,
    ):
        self.config = config or RetryConfig()
        self.circuit_breaker_name = circuit_breaker_name
        self._retry_handler = RetryHandler(self.config)

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute with retry and circuit breaker."""
        if self.circuit_breaker_name:
            from backend.core.circuit_breaker import get_registry

            registry = get_registry()
            breaker = registry.get(self.circuit_breaker_name)

            if breaker and breaker.is_open:
                logger.warning(
                    f"Circuit breaker '{self.circuit_breaker_name}' is open, skipping",
                    action=LogAction.SKIP,
                )
                raise Exception(
                    f"Circuit breaker '{self.circuit_breaker_name}' is open"
                )

        return await self._retry_handler.execute(func, *args, **kwargs)


# Pre-configured retry handlers for common scenarios


async def retry_with_backoff(
    func: Callable, *args, max_retries: int = 3, **kwargs
) -> Any:
    """Quick retry with exponential backoff."""
    handler = RetryHandler(
        RetryConfig(max_retries=max_retries, strategy=RetryStrategy.EXPONENTIAL_JITTER)
    )
    return await handler.execute(func, *args, **kwargs)


async def retry_network_request(func: Callable, *args, **kwargs) -> Any:
    """Retry specifically for network requests."""
    handler = RetryHandler(
        RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=120.0,
            strategy=RetryStrategy.EXPONENTIAL_JITTER,
            retryable_exceptions=(
                ConnectionError,
                TimeoutError,
                OSError,
            ),
        )
    )
    return await handler.execute(
        func, *args, operation_name="network_request", **kwargs
    )


__all__ = [
    "RetryHandler",
    "RetryConfig",
    "RetryStrategy",
    "with_retry",
    "CircuitBreakerAwareRetry",
    "retry_with_backoff",
    "retry_network_request",
]
