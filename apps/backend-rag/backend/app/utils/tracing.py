"""
OpenTelemetry Tracing Utilities
Provides utilities for distributed tracing with OpenTelemetry/Jaeger
"""

import logging
from contextlib import contextmanager
from typing import Any

logger = logging.getLogger(__name__)

# Try to import OpenTelemetry
OTEL_AVAILABLE = False
try:
    from opentelemetry import trace

    OTEL_AVAILABLE = True
except ImportError:
    pass


def get_tracer(name: str = "nuzantara-backend"):
    """
    Get OpenTelemetry tracer.

    Args:
        name: Tracer name

    Returns:
        Tracer instance or None if OpenTelemetry not available
    """
    if not OTEL_AVAILABLE:
        return None

    try:
        return trace.get_tracer(name)
    except Exception as e:
        logger.warning(f"Failed to get tracer: {e}")
        return None


@contextmanager
def trace_span(span_name: str, attributes: dict[str, Any] | None = None):
    """
    Context manager for creating a trace span.

    Args:
        span_name: Span name
        attributes: Optional span attributes

    Yields:
        Span object or None
    """
    tracer = get_tracer()
    if not tracer:
        yield None
        return

    try:
        with tracer.start_as_current_span(span_name) as span:
            if attributes and span:
                for key, value in attributes.items():
                    span.set_attribute(key, str(value))
            yield span
    except Exception as e:
        logger.warning(f"Failed to create span {span_name}: {e}")
        yield None


def add_span_event(event_name: str, attributes: dict[str, Any] | None = None) -> None:
    """
    Add an event to the current span.

    Args:
        event_name: Event name
        attributes: Optional event attributes
    """
    if not OTEL_AVAILABLE:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.add_event(event_name, attributes=attributes or {})
    except Exception as e:
        logger.debug(f"Failed to add span event: {e}")


def set_span_attribute(key: str, value: Any) -> None:
    """
    Set an attribute on the current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    if not OTEL_AVAILABLE:
        return

    try:
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute(key, str(value))
    except Exception as e:
        logger.debug(f"Failed to set span attribute: {e}")


def set_span_status(status: str, description: str | None = None) -> None:
    """
    Set status on the current span.

    Args:
        status: Status code ("ok" or "error")
        description: Optional status description
    """
    if not OTEL_AVAILABLE:
        return

    try:
        from opentelemetry.trace import Status, StatusCode

        span = trace.get_current_span()
        if span and span.is_recording():
            if status == "error":
                span.set_status(Status(StatusCode.ERROR, description))
            else:
                span.set_status(Status(StatusCode.OK, description))
    except Exception as e:
        logger.debug(f"Failed to set span status: {e}")

