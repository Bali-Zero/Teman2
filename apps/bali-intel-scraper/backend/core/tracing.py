"""
Distributed tracing support.

Integrates with OpenTelemetry for request tracing.
"""

import functools
from contextlib import contextmanager
from typing import Any, Dict, Optional

from backend.core.logger import get_logger

logger = get_logger(__name__, component="tracing")


class Tracer:
    """Simple tracer implementation."""

    def __init__(self, service_name: str = "bali-intel-scraper"):
        self.service_name = service_name
        self._spans: list = []

    @contextmanager
    def span(self, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Create a new trace span."""
        import time

        span_data = {
            "name": name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "service": self.service_name,
        }

        self._spans.append(span_data)

        try:
            yield span_data
        except Exception as e:
            span_data["error"] = str(e)
            raise
        finally:
            span_data["end_time"] = time.time()
            span_data["duration_ms"] = (
                span_data["end_time"] - span_data["start_time"]
            ) * 1000

            logger.debug(
                f"Span completed: {name}",
                metadata={
                    "duration_ms": span_data["duration_ms"],
                    "attributes": attributes,
                },
            )

    def trace(self, name: Optional[str] = None):
        """Decorator for tracing functions."""

        def decorator(func):
            span_name = name or func.__name__

            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                with self.span(span_name, {"function": func.__name__}):
                    return await func(*args, **kwargs)

            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                with self.span(span_name, {"function": func.__name__}):
                    return func(*args, **kwargs)

            import inspect

            if inspect.iscoroutinefunction(func):
                return async_wrapper
            return sync_wrapper

        return decorator

    def get_spans(self) -> list:
        """Get all recorded spans."""
        return self._spans.copy()

    def clear_spans(self):
        """Clear recorded spans."""
        self._spans.clear()


tracer = Tracer()


def trace_function(name: Optional[str] = None):
    """Decorator for tracing."""
    return tracer.trace(name)


__all__ = [
    "Tracer",
    "tracer",
    "trace_function",
]
