"""
Rate limiting implementation using token bucket algorithm.

Provides rate limiting for:
- API requests
- Scraping operations
- AI service calls
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable
from functools import wraps

from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="rate_limiter")


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""

    requests_per_second: float = 1.0
    burst_size: int = 5
    window_size: float = 60.0  # For sliding window


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, name: str, rate: float = 1.0, capacity: int = 5):
        """
        Initialize token bucket.

        Args:
            name: Identifier for this bucket
            rate: Tokens added per second
            capacity: Maximum tokens in bucket
        """
        self.name = name
        self.rate = rate
        self.capacity = capacity

        self._tokens = capacity
        self._last_update = time.time()
        self._lock = asyncio.Lock()

        logger.debug(
            f"Token bucket '{name}' created",
            metadata={"rate": rate, "capacity": capacity},
        )

    async def acquire(self, tokens: int = 1, timeout: float | None = None) -> bool:
        """
        Acquire tokens from the bucket.

        Args:
            tokens: Number of tokens to acquire
            timeout: Maximum time to wait (None = wait forever)

        Returns:
            True if tokens were acquired, False if timed out
        """
        start_time = time.time()

        while True:
            async with self._lock:
                self._add_tokens()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True

                # Calculate wait time
                tokens_needed = tokens - self._tokens
                wait_time = tokens_needed / self.rate

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed + wait_time > timeout:
                    return False

            # Wait for tokens to be available
            await asyncio.sleep(min(wait_time, 0.1))

    def _add_tokens(self) -> None:
        """Add tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update
        self._last_update = now

        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)

    async def try_acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens without waiting."""
        async with self._lock:
            self._add_tokens()

            if self._tokens >= tokens:
                self._tokens -= tokens
                return True
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get bucket statistics."""
        return {
            "name": self.name,
            "rate": self.rate,
            "capacity": self.capacity,
            "available_tokens": self._tokens,
            "utilization": 1 - (self._tokens / self.capacity)
            if self.capacity > 0
            else 0,
        }


class SlidingWindowRateLimiter:
    """Sliding window rate limiter for precise control."""

    def __init__(self, name: str, max_requests: int = 100, window_size: float = 60.0):
        self.name = name
        self.max_requests = max_requests
        self.window_size = window_size

        self._requests: list = []
        self._lock = asyncio.Lock()

    async def acquire(self, timeout: float | None = None) -> bool:
        """Acquire permission to make a request."""
        start_time = time.time()

        while True:
            async with self._lock:
                now = time.time()
                cutoff = now - self.window_size

                # Remove old requests outside window
                self._requests = [t for t in self._requests if t > cutoff]

                if len(self._requests) < self.max_requests:
                    self._requests.append(now)
                    return True

            # Check timeout
            if timeout is not None and time.time() - start_time > timeout:
                return False

            await asyncio.sleep(0.1)

    def get_stats(self) -> dict[str, Any]:
        """Get limiter statistics."""
        now = time.time()
        cutoff = now - self.window_size
        recent_requests = len([t for t in self._requests if t > cutoff])

        return {
            "name": self.name,
            "max_requests": self.max_requests,
            "window_size": self.window_size,
            "current_requests": recent_requests,
            "remaining": self.max_requests - recent_requests,
        }


class RateLimiterRegistry:
    """Registry for managing multiple rate limiters."""

    def __init__(self):
        self._buckets: dict[str, TokenBucket] = {}
        self._windows: dict[str, SlidingWindowRateLimiter] = {}

    def create_bucket(
        self, name: str, rate: float = 1.0, capacity: int = 5
    ) -> TokenBucket:
        """Create or get a token bucket."""
        if name not in self._buckets:
            self._buckets[name] = TokenBucket(name, rate, capacity)
        return self._buckets[name]

    def create_window(
        self, name: str, max_requests: int = 100, window_size: float = 60.0
    ) -> SlidingWindowRateLimiter:
        """Create or get a sliding window limiter."""
        if name not in self._windows:
            self._windows[name] = SlidingWindowRateLimiter(
                name, max_requests, window_size
            )
        return self._windows[name]

    def get_bucket(self, name: str) -> TokenBucket | None:
        """Get a token bucket by name."""
        return self._buckets.get(name)

    def get_window(self, name: str) -> SlidingWindowRateLimiter | None:
        """Get a sliding window limiter by name."""
        return self._windows.get(name)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """Get stats for all rate limiters."""
        return {
            "buckets": {
                name: bucket.get_stats() for name, bucket in self._buckets.items()
            },
            "windows": {
                name: window.get_stats() for name, window in self._windows.items()
            },
        }

    async def reset_all(self) -> None:
        """Reset all rate limiters."""
        for bucket in self._buckets.values():
            async with bucket._lock:
                bucket._tokens = bucket.capacity
                bucket._last_update = time.time()

        for window in self._windows.values():
            async with window._lock:
                window._requests.clear()


# Global registry
_registry = RateLimiterRegistry()


def get_registry() -> RateLimiterRegistry:
    """Get the global rate limiter registry."""
    return _registry


def rate_limit(
    name: str, rate: float = 1.0, capacity: int = 5, timeout: float | None = None
):
    """Decorator for rate limiting function calls."""

    def decorator(func: Callable) -> Callable:
        bucket = _registry.create_bucket(name, rate, capacity)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            if not await bucket.acquire(timeout=timeout):
                logger.warning(
                    f"Rate limit exceeded for '{name}'", action=LogAction.SKIP
                )
                raise RateLimitExceededError(name)
            return await func(*args, **kwargs)

        return async_wrapper

    return decorator


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, limiter_name: str):
        self.limiter_name = limiter_name
        super().__init__(f"Rate limit exceeded for '{limiter_name}'")


# Pre-configured rate limiters for common use cases


async def limit_scrape_request(host: str) -> None:
    """Apply rate limiting for scraping a specific host."""
    bucket = _registry.create_bucket(
        name=f"scrape:{host}",
        rate=0.5,  # 1 request per 2 seconds
        capacity=2,
    )

    if not await bucket.acquire(timeout=30):
        logger.warning(
            f"Scrape rate limit exceeded for {host}",
            action=LogAction.SKIP,
            metadata={"host": host},
        )
        raise RateLimitExceededError(f"scrape:{host}")


async def limit_ai_request(provider: str = "openai") -> None:
    """Apply rate limiting for AI API calls."""
    bucket = _registry.create_bucket(
        name=f"ai:{provider}",
        rate=1.0,  # 1 request per second
        capacity=5,
    )

    if not await bucket.acquire(timeout=60):
        logger.warning(
            f"AI rate limit exceeded for {provider}",
            action=LogAction.SKIP,
            metadata={"provider": provider},
        )
        raise RateLimitExceededError(f"ai:{provider}")


__all__ = [
    "TokenBucket",
    "SlidingWindowRateLimiter",
    "RateLimiterRegistry",
    "RateLimitExceededError",
    "rate_limit",
    "get_registry",
    "limit_scrape_request",
    "limit_ai_request",
]
