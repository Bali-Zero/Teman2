"""Cache discipline primitives for service-layer mutations.

Historically every router that mutated shared state had to remember to call
``await invalidate_cache("zantara:...:*")`` after the write. That discipline
leaks across ~90 router paths and was missing in most service-layer methods
(EventBus handlers, portal mixins, background jobs). The audit for
air-a2-cache-invalidation-discipline documents the gap.

This module provides a single decorator — :func:`cache_invalidating` — that any
async mutation method can adopt. It calls the low-level
``backend.core.cache.invalidate_cache`` for every pattern after the wrapped
coroutine succeeds, and it swallows Redis/cache errors (logger.warning +
Prometheus counter) so a failing cache never blocks a successful mutation.

Patterns can be plain strings (``"zantara:crm_clients:*"``) or callables
receiving the same arguments as the wrapped function (``lambda self, client_id,
**_: f"zantara:crm_client:{client_id}:*"``). Lambdas let mutations targeting a
single entity avoid blowing away an entire namespace.

The decorator is intentionally thin: it relies on the existing
``backend.core.cache.invalidate_cache`` helper (Redis-backed with in-memory
fallback) and on ``backend.app.metrics`` counters for observability. Both
dependencies are imported lazily so tests can monkeypatch the underlying hooks
without pulling the FastAPI app graph.
"""
from __future__ import annotations

import inspect
import logging
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar, Union

logger = logging.getLogger(__name__)

PatternSpec = Union[str, Callable[..., str]]
_AsyncCallable = TypeVar("_AsyncCallable", bound=Callable[..., Awaitable[Any]])


async def _invalidate_cache(pattern: str) -> int:
    """Lazy wrapper around the core invalidate_cache helper.

    Kept as a module-level async function so tests can patch it without
    importing the FastAPI dependency graph.
    """
    from backend.core.cache import invalidate_cache as _core_invalidate_cache

    return await _core_invalidate_cache(pattern)


def _extract_namespace(pattern: str) -> str:
    """Derive a Prometheus label from a cache pattern.

    ``zantara:crm_clients_stats:*`` → ``crm_clients_stats``
    ``zantara:crm_client:42:*``     → ``crm_client``
    """
    if pattern.startswith("zantara:"):
        parts = pattern.split(":")
        if len(parts) >= 2:
            return parts[1] or "default"
    return pattern.split(":", 1)[0] or "default"


def _inc_success_counter(namespace: str) -> None:
    """Increment the success Prometheus counter. Safe if prometheus missing."""
    try:
        from backend.app.metrics import cache_invalidation_total

        cache_invalidation_total.labels(namespace=namespace, status="success").inc()
    except Exception:  # pragma: no cover — metrics must never break flow
        pass


def _inc_error_counter(namespace: str) -> None:
    """Increment the error Prometheus counter. Safe if prometheus missing."""
    try:
        from backend.app.metrics import cache_invalidation_error_total

        cache_invalidation_error_total.labels(namespace=namespace).inc()
    except Exception:  # pragma: no cover — metrics must never break flow
        pass


def _resolve_pattern(pattern: PatternSpec, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """Resolve a pattern spec to a concrete string, passing call args to callables."""
    if isinstance(pattern, str):
        return pattern
    if callable(pattern):
        return pattern(*args, **kwargs)
    raise TypeError(
        f"cache_invalidating patterns must be str or callable, got {type(pattern).__name__}",
    )


def cache_invalidating(patterns: list[PatternSpec]) -> Callable[[_AsyncCallable], _AsyncCallable]:
    """Wrap an async mutation method so it invalidates cache on success.

    Args:
        patterns: List of Redis key patterns. Each entry is either a literal
            string (``"zantara:crm_practices:*"``) or a callable invoked with
            the same ``*args, **kwargs`` as the wrapped function (typical:
            ``lambda self, client_id, **_: f"zantara:crm_client:{client_id}:*"``).

    Behaviour:
        - If the wrapped coroutine raises, no invalidation runs. The exception
          propagates.
        - On success, each pattern is resolved and invalidated in order. Failures
          are logged at WARNING level and increment
          ``cache_invalidation_error_total{namespace=...}`` but never propagate.
        - Successful invalidations increment
          ``cache_invalidation_total{namespace=..., status="success"}``.

    Example:
        >>> @cache_invalidating([
        ...     lambda self, client_id, **_: f"zantara:crm_client:{client_id}:*",
        ...     "zantara:crm_clients_stats:*",
        ... ])
        ... async def update_client(self, client_id: int, **payload): ...
    """
    if not isinstance(patterns, (list, tuple)) or not patterns:
        raise ValueError("cache_invalidating requires a non-empty list of patterns")

    def decorator(func: _AsyncCallable) -> _AsyncCallable:
        if not inspect.iscoroutinefunction(func):
            raise TypeError(
                f"cache_invalidating can only decorate async functions; "
                f"{func.__qualname__} is sync",
            )

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            result = await func(*args, **kwargs)

            for spec in patterns:
                try:
                    pattern = _resolve_pattern(spec, args, kwargs)
                except Exception as exc:  # malformed lambda, missing kwarg, etc.
                    logger.warning(
                        "cache_invalidating: failed to resolve pattern for %s: %s",
                        func.__qualname__,
                        exc,
                    )
                    _inc_error_counter("unresolved")
                    continue

                namespace = _extract_namespace(pattern)
                try:
                    await _invalidate_cache(pattern)
                    _inc_success_counter(namespace)
                except Exception as exc:
                    logger.warning(
                        "cache_invalidating: invalidation failed for %s (pattern=%s): %s",
                        func.__qualname__,
                        pattern,
                        exc,
                    )
                    _inc_error_counter(namespace)

            return result

        return wrapper  # type: ignore[return-value]

    return decorator


__all__ = ["cache_invalidating"]
