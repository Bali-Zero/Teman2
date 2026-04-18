"""Retry policy + exception taxonomy for the jobs runner.

The runner retries only exceptions classified as 'transient'. Anything not
explicitly transient is permanent — handlers must opt in to retry by raising
TransientError or using the @transient_on decorator.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Awaitable, Callable, Literal


class JobError(Exception):
    """Base class for all runner-aware exceptions."""


class TransientError(JobError):
    """Retry-eligible. Network, DB pool, upstream 5xx, timeout."""


class PermanentError(JobError):
    """Do not retry. Validation, auth, handler bug."""


class OAuthViolation(PermanentError):
    """Raised by the oauth_guard middleware when ANTHROPIC_API_KEY is set."""


class CostExceeded(PermanentError):
    """Raised by the cost_cap middleware when handler overshoots budget."""


Classification = Literal["transient", "permanent"]


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int
    backoff_seconds: tuple[float, ...]

    def __post_init__(self) -> None:
        if len(self.backoff_seconds) != self.max_attempts - 1:
            raise ValueError(
                f"backoff_seconds length must be max_attempts - 1 "
                f"({self.max_attempts - 1}), got {len(self.backoff_seconds)}"
            )

    def backoff_for(self, next_attempt: int) -> float:
        """Backoff to sleep before next_attempt (2-indexed: attempt 2, 3, ...)."""
        idx = next_attempt - 2
        if idx < 0 or idx >= len(self.backoff_seconds):
            raise IndexError(f"no backoff for attempt={next_attempt}")
        return self.backoff_seconds[idx]


DEFAULT_RETRY = RetryPolicy(max_attempts=3, backoff_seconds=(0.5, 2.0))


def classify(exc: BaseException) -> Classification:
    if isinstance(exc, TransientError):
        return "transient"
    return "permanent"


def transient_on(
    *exc_classes: type[BaseException],
) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
    """Decorator: re-raise listed exceptions as TransientError.

    Other exceptions pass through untouched, so they are classified permanent.
    """

    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            try:
                return await fn(*args, **kwargs)
            except exc_classes as exc:
                raise TransientError(str(exc)) from exc

        return wrapper

    return decorator
