"""
Correlation ID contextvar.

Single source of truth for the request-scoped correlation ID.
Populated once by RequestTracingMiddleware and read by any downstream
middleware, logger, or service that wants to stamp the current request.

The contextvar survives across awaits within the same asyncio task, which
covers the full request lifecycle inside Starlette/FastAPI.
"""

from __future__ import annotations

from contextvars import ContextVar

# Sentinel returned by get_correlation_id() when called outside a request.
UNKNOWN_CORRELATION_ID = "-"

_correlation_id: ContextVar[str] = ContextVar(
    "nuzantara_correlation_id", default=UNKNOWN_CORRELATION_ID,
)


def set_correlation_id(value: str) -> object:
    """Set the correlation ID for the current context. Returns a token for reset()."""
    return _correlation_id.set(value)


def reset_correlation_id(token: object) -> None:
    """Restore the previous correlation ID using the token from set_correlation_id()."""
    _correlation_id.reset(token)  # type: ignore[arg-type]


def get_correlation_id() -> str:
    """
    Return the current correlation ID, or UNKNOWN_CORRELATION_ID ("-") if
    no request is in scope (e.g., background task spawned outside a request).
    """
    return _correlation_id.get()
