"""
Async utilities for performance optimization.

Provides helpers for concurrent execution, batching, and resource management.
"""

import asyncio
import contextlib
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


async def gather_with_concurrency(
    limit: int,
    *coros: Coroutine[Any, Any, T],
) -> list[T]:
    """
    Run coroutines with a concurrency limit.

    Args:
        limit: Maximum number of concurrent operations
        *coros: Coroutines to execute

    Returns:
        List of results in the same order as input
    """
    semaphore = asyncio.Semaphore(limit)

    async def sem_coro(coro: Coroutine[Any, Any, T]) -> T:
        async with semaphore:
            return await coro

    return await asyncio.gather(*(sem_coro(c) for c in coros))


async def batch_execute(
    items: list[T],
    processor: Callable[[T], Coroutine[Any, Any, Any]],
    batch_size: int = 10,
    concurrency: int = 5,
) -> list[Any]:
    """
    Process items in batches with controlled concurrency.

    Args:
        items: Items to process
        processor: Async function to process each item
        batch_size: Number of items per batch
        concurrency: Max concurrent operations within a batch

    Returns:
        List of results
    """
    results = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        batch_results = await gather_with_concurrency(
            concurrency,
            *(processor(item) for item in batch),
        )
        results.extend(batch_results)

    return results


class AsyncResourcePool:
    """Pool of async resources with automatic cleanup."""

    def __init__(
        self,
        factory: Callable[[], Coroutine[Any, Any, T]],
        max_size: int = 10,
        timeout: float = 30.0,
    ) -> None:
        self.factory = factory
        self.max_size = max_size
        self.timeout = timeout
        self._pool: asyncio.Queue[T] = asyncio.Queue(maxsize=max_size)
        self._size = 0
        self._lock = asyncio.Lock()

    async def acquire(self) -> T:
        """Acquire a resource from the pool."""
        async with self._lock:
            if not self._pool.empty():
                return await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.timeout,
                )
            if self._size < self.max_size:
                self._size += 1
                return await self.factory()

        # Wait for available resource
        return await asyncio.wait_for(
            self._pool.get(),
            timeout=self.timeout,
        )

    async def release(self, resource: T) -> None:
        """Release a resource back to the pool."""
        try:
            self._pool.put_nowait(resource)
        except asyncio.QueueFull:
            # Pool is full, cleanup resource if possible
            if hasattr(resource, "close"):
                await resource.close()
            async with self._lock:
                self._size -= 1

    async def cleanup(self) -> None:
        """Cleanup all resources in the pool."""
        while not self._pool.empty():
            try:
                resource = self._pool.get_nowait()
                if hasattr(resource, "close"):
                    await resource.close()
            except asyncio.QueueEmpty:
                break

        async with self._lock:
            self._size = 0


class CircuitBreaker:
    """Circuit breaker pattern for external service calls."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._failures = 0
        self._last_failure_time: float | None = None
        self._state = "closed"  # closed, open, half-open
        self._half_open_calls = 0
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[..., Coroutine[Any, Any, T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """Execute function with circuit breaker protection."""
        async with self._lock:
            if self._state == "open":
                if self._should_attempt_reset():
                    self._state = "half-open"
                    self._half_open_calls = 0
                else:
                    raise CircuitBreakerOpen("Circuit breaker is open")

            if self._state == "half-open" and self._half_open_calls >= self.half_open_max_calls:
                raise CircuitBreakerOpen("Circuit breaker is half-open, max calls reached")

            if self._state == "half-open":
                self._half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception:
            await self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        if self._last_failure_time is None:
            return True
        import time

        return time.time() - self._last_failure_time >= self.recovery_timeout

    async def _on_success(self) -> None:
        async with self._lock:
            self._failures = 0
            self._state = "closed"
            self._half_open_calls = 0

    async def _on_failure(self) -> None:
        import time

        async with self._lock:
            self._failures += 1
            self._last_failure_time = time.time()

            if self._failures >= self.failure_threshold:
                self._state = "open"

    @property
    def state(self) -> str:
        """Current circuit state."""
        return self._state


class CircuitBreakerOpen(Exception):
    """Raised when circuit breaker is open."""

    pass


class Debouncer:
    """Debounce multiple calls into a single execution."""

    def __init__(self, delay: float = 0.3) -> None:
        self.delay = delay
        self._task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    async def call(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any,
    ) -> None:
        """Schedule function call with debouncing."""
        async with self._lock:
            if self._task:
                self._task.cancel()

            self._task = asyncio.create_task(self._delayed_call(func, *args, **kwargs))

    async def _delayed_call(
        self, func: Callable[..., Coroutine[Any, Any, Any]], *args: Any, **kwargs: Any,
    ) -> None:
        await asyncio.sleep(self.delay)
        with contextlib.suppress(asyncio.CancelledError):
            await func(*args, **kwargs)
