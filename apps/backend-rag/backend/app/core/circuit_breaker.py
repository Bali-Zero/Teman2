"""
Circuit Breaker Pattern Implementation

Prevents cascading failures by stopping requests to failing services
and allowing them to recover.
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker implementation to prevent cascading failures.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing recovery, allow limited requests

    Transitions:
    - CLOSED -> OPEN: Failure threshold exceeded
    - OPEN -> HALF_OPEN: Timeout period elapsed
    - HALF_OPEN -> CLOSED: Success threshold met
    - HALF_OPEN -> OPEN: Failure threshold exceeded again
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        name: str = "circuit",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes in half-open to close circuit
            timeout: Seconds to wait before transitioning OPEN -> HALF_OPEN
            name: Name for logging
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.last_state_change_time = time.time()

    def _transition_to_open(self):
        """Transition circuit to OPEN state."""
        if self.state != CircuitState.OPEN:
            logger.warning(
                f"🔴 Circuit breaker '{self.name}' OPENED after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN
            self.last_failure_time = time.time()
            self.last_state_change_time = time.time()
            self.success_count = 0

    def _transition_to_half_open(self):
        """Transition circuit to HALF_OPEN state."""
        if self.state != CircuitState.HALF_OPEN:
            logger.info(f"🟡 Circuit breaker '{self.name}' HALF_OPEN - testing recovery")
            self.state = CircuitState.HALF_OPEN
            self.last_state_change_time = time.time()
            self.success_count = 0
            self.failure_count = 0

    def _transition_to_closed(self):
        """Transition circuit to CLOSED state."""
        if self.state != CircuitState.CLOSED:
            logger.info(
                f"🟢 Circuit breaker '{self.name}' CLOSED after {self.success_count} successes"
            )
            self.state = CircuitState.CLOSED
            self.last_state_change_time = time.time()
            self.failure_count = 0
            self.success_count = 0

    def _check_timeout(self):
        """Check if timeout period has elapsed for OPEN -> HALF_OPEN transition."""
        if self.state == CircuitState.OPEN and self.last_failure_time:
            elapsed = time.time() - self.last_failure_time
            if elapsed >= self.timeout:
                self._transition_to_half_open()

    def record_success(self):
        """Record a successful operation."""
        self._check_timeout()

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self._transition_to_closed()
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self):
        """Record a failed operation."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN:
            # Failure in half-open -> back to open
            self._transition_to_open()
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to_open()

    def is_open(self) -> bool:
        """Check if circuit is open (rejecting requests)."""
        self._check_timeout()
        return self.state == CircuitState.OPEN

    async def call(
        self,
        func: Callable[[], Any],
        fallback: Callable[[], Any] | None = None,
        operation_name: str | None = None,
    ) -> T:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            fallback: Optional fallback function if circuit is open
            operation_name: Name for logging

        Returns:
            Result of function or fallback

        Raises:
            RuntimeError: If circuit is open and no fallback provided
        """
        self._check_timeout()

        if self.is_open():
            if fallback:
                logger.debug(
                    f"Circuit breaker '{self.name}' OPEN, using fallback for {operation_name}"
                )
                try:
                    result = await fallback()
                    return result
                except Exception as e:
                    logger.error(f"Fallback also failed: {e}")
                    raise
            else:
                raise RuntimeError(
                    f"Circuit breaker '{self.name}' is OPEN. Service unavailable."
                )

        try:
            result = await func()
            self.record_success()
            return result
        except Exception as e:
            self.record_failure()
            raise

    def get_state(self) -> dict[str, Any]:
        """Get current circuit breaker state."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time,
            "time_since_last_failure": (
                time.time() - self.last_failure_time if self.last_failure_time else None
            ),
        }

