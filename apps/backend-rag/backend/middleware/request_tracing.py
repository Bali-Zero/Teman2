"""
Request Tracing Middleware
Provides end-to-end request tracing with correlation IDs
"""

import logging
import time
import uuid
from collections.abc import Callable
from collections import OrderedDict
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# In-memory trace storage (LRU cache with max size)
MAX_TRACES = 1000
_trace_storage: OrderedDict[str, dict[str, Any]] = OrderedDict()


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for end-to-end request tracing with correlation IDs.
    
    Features:
    - Generates correlation ID for each request
    - Tracks request through all services
    - Logs timing for each step
    - Stores traces in memory for debug endpoints
    """

    def __init__(self, app, max_traces: int = MAX_TRACES):
        """
        Initialize request tracing middleware.

        Args:
            app: FastAPI application instance
            max_traces: Maximum number of traces to store in memory
        """
        super().__init__(app)
        self.max_traces = max_traces

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with tracing.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response with tracing headers
        """
        # Get or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request_id = getattr(request.state, "request_id", None) or correlation_id

        # Store correlation ID in request state
        request.state.correlation_id = correlation_id
        request.state.request_id = request_id

        # Initialize trace
        trace_start = time.time()
        trace: dict[str, Any] = {
            "correlation_id": correlation_id,
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "query_params": dict(request.query_params),
            "start_time": trace_start,
            "steps": [],
            "duration_ms": None,
            "status_code": None,
            "error": None,
        }

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - trace_start) * 1000
            trace["duration_ms"] = duration_ms
            trace["status_code"] = response.status_code

            # Add correlation ID to response headers
            response.headers["X-Correlation-ID"] = correlation_id
            response.headers["X-Request-ID"] = request_id

            # Store trace
            self._store_trace(correlation_id, trace)

            return response

        except Exception as exc:
            # Handle exceptions
            duration_ms = (time.time() - trace_start) * 1000
            trace["duration_ms"] = duration_ms
            trace["status_code"] = 500
            trace["error"] = {
                "type": type(exc).__name__,
                "message": str(exc),
            }

            # Store trace
            self._store_trace(correlation_id, trace)

            # Re-raise exception
            raise

    def _store_trace(self, correlation_id: str, trace: dict[str, Any]) -> None:
        """
        Store trace in memory (LRU cache).

        Args:
            correlation_id: Correlation ID
            trace: Trace data
        """
        global _trace_storage

        # Remove oldest if at max capacity
        if len(_trace_storage) >= self.max_traces:
            _trace_storage.popitem(last=False)  # Remove oldest

        # Store trace
        _trace_storage[correlation_id] = trace

        # Move to end (most recent)
        _trace_storage.move_to_end(correlation_id)

    @staticmethod
    def add_step(correlation_id: str, step_name: str, duration_ms: float, **metadata) -> None:
        """
        Add a step to a trace.

        Args:
            correlation_id: Correlation ID
            step_name: Step name
            duration_ms: Step duration in milliseconds
            **metadata: Additional step metadata
        """
        global _trace_storage

        if correlation_id in _trace_storage:
            trace = _trace_storage[correlation_id]
            trace["steps"].append(
                {
                    "name": step_name,
                    "duration_ms": duration_ms,
                    "timestamp": time.time(),
                    **metadata,
                }
            )

    @staticmethod
    def get_trace(correlation_id: str) -> dict[str, Any] | None:
        """
        Get trace by correlation ID.

        Args:
            correlation_id: Correlation ID

        Returns:
            Trace data or None if not found
        """
        global _trace_storage
        return _trace_storage.get(correlation_id)

    @staticmethod
    def get_recent_traces(limit: int = 100) -> list[dict[str, Any]]:
        """
        Get recent traces.

        Args:
            limit: Maximum number of traces to return

        Returns:
            List of recent traces
        """
        global _trace_storage
        return list(_trace_storage.values())[-limit:]

    @staticmethod
    def clear_traces() -> int:
        """
        Clear all stored traces.

        Returns:
            Number of traces cleared
        """
        global _trace_storage
        count = len(_trace_storage)
        _trace_storage.clear()
        return count


def get_correlation_id(request: Request) -> str:
    """
    Get correlation ID from request.

    Args:
        request: FastAPI request

    Returns:
        Correlation ID
    """
    return getattr(request.state, "correlation_id", None) or getattr(
        request.state, "request_id", None
    ) or str(uuid.uuid4())

