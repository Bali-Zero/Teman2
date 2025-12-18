import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


def db_retry(max_retries: int = 3, delay: float = 1.0, backoff_factor: float = 2.0):
    """
    Decorator to retry database operations on transient errors (e.g., 503).

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier for delay after each failure.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            last_error = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    error_msg = str(e).lower()

                    # Check for transient errors
                    is_transient = (
                        "503" in error_msg
                        or "unavailable" in error_msg
                        or "connection" in error_msg
                        or "timeout" in error_msg
                        or "deadlock" in error_msg
                    )

                    if is_transient and attempt < max_retries:
                        logger.warning(
                            f"⚠️ DB Operation failed (attempt {attempt + 1}/{max_retries}): {e}. "
                            f"Retrying in {current_delay:.2f}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        # If not transient or max retries reached, re-raise
                        if attempt == max_retries:
                            logger.error(f"❌ DB Operation failed after {max_retries} retries: {e}")
                        raise last_error
            return None  # Should not be reached

        return wrapper

    return decorator
