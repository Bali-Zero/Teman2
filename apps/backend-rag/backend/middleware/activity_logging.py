"""
Activity Logging Middleware
Automatically logs all HTTP requests for audit trail and analytics

Features:
- Logs every API call (method, endpoint, user, response time)
- Captures request/response details
- Tracks user sessions
- Performance monitoring
- Error tracking
"""

import time
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.app.utils.logging_utils import get_logger
from backend.services.monitoring.activity_logger import activity_logger

logger = get_logger(__name__)


class ActivityLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all HTTP requests for audit trail

    Logs:
    - All API calls with timing
    - User authentication info
    - Request/response details
    - Errors
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.excluded_paths = {
            "/health",
            "/metrics",
            "/favicon.ico",
            "/api/health",
            "/api/v1/health",
            "/docs",
            "/redoc",
            "/openapi.json",
        }

    def _should_log(self, path: str) -> bool:
        """Determine if request should be logged"""
        # Skip health checks and static assets
        if path in self.excluded_paths:
            return False

        # Skip if path starts with excluded prefix
        for excluded in self.excluded_paths:
            if path.startswith(excluded):
                return False

        return True

    def _get_user_email(self, request: Request) -> str | None:
        """Extract user email from request"""
        # Try to get from request state (set by auth middleware)
        user = getattr(request.state, "user", None)
        if user:
            if isinstance(user, dict):
                return user.get("email")
            elif hasattr(user, "email"):
                return user.email

        # Try to get from headers (for debugging)
        return request.headers.get("X-User-Email")

    def _get_session_id(self, request: Request) -> str | None:
        """Extract session ID from request"""
        # Try cookies
        session_id = request.cookies.get("session_id")
        if session_id:
            return session_id

        # Try headers
        return request.headers.get("X-Session-ID")

    def _get_ip_address(self, request: Request) -> str:
        """Get client IP address"""
        # Check Fly.io headers first
        ip = request.headers.get("Fly-Client-IP")
        if ip:
            return ip

        # Check X-Forwarded-For
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()

        # Check X-Real-IP
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # Fallback to client host
        if request.client:
            return request.client.host

        return "unknown"

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and log activity

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        # Skip logging for excluded paths
        if not self._should_log(request.url.path):
            return await call_next(request)

        # Capture start time
        start_time = time.time()

        # Extract request metadata
        user_email = self._get_user_email(request)
        session_id = self._get_session_id(request)
        ip_address = self._get_ip_address(request)
        user_agent = request.headers.get("User-Agent", "")
        correlation_id = request.headers.get("X-Correlation-ID")

        # Process request
        response = None
        error_message = None

        try:
            response = await call_next(request)
            return response

        except Exception as e:
            error_message = str(e)
            logger.error(
                f"❌ Request failed: {request.method} {request.url.path}",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "user_email": user_email,
                    "error": str(e),
                },
            )
            raise

        finally:
            # Calculate response time
            response_time_ms = int((time.time() - start_time) * 1000)

            # Get response status
            status_code = response.status_code if response else 500

            # Log API call (async, non-blocking)
            try:
                # Get query params
                query_params = dict(request.query_params) if request.query_params else None

                # Get request body (if applicable)
                request_body = None
                if request.method in ["POST", "PUT", "PATCH"]:
                    # Note: Body is consumed by route, so we can't read it here
                    # We could store it in request.state during route processing
                    request_body = getattr(request.state, "request_body", None)

                # Log the API call
                await activity_logger.log_api_call(
                    method=request.method,
                    endpoint=request.url.path,
                    response_status=status_code,
                    response_time_ms=response_time_ms,
                    user_email=user_email,
                    query_params=query_params,
                    request_body=request_body,
                    error_message=error_message,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    correlation_id=correlation_id,
                    session_id=session_id,
                )

                # Update session activity
                if session_id and user_email:
                    await activity_logger.log_session(
                        session_id=session_id,
                        user_email=user_email,
                        event_type="activity",
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )

            except Exception as log_error:
                # Don't fail the request if logging fails
                logger.warning(f"⚠️ Failed to log API call: {log_error}")

            # Log slow requests
            if response_time_ms > 1000:
                logger.warning(
                    f"⏱️ Slow request: {request.method} {request.url.path} ({response_time_ms}ms)",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "response_time_ms": response_time_ms,
                        "user_email": user_email,
                    },
                )


def setup_activity_logging(app):
    """
    Setup activity logging middleware

    Args:
        app: FastAPI app instance
    """
    app.add_middleware(ActivityLoggingMiddleware)
    logger.info("✅ Activity logging middleware enabled")
