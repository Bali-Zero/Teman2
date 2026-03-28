"""
Error Monitoring Middleware
Captures 4xx/5xx HTTP errors and sends alerts
"""

import logging
import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

# Cooldown period for latency alerts (seconds) — one alert per path per period
LATENCY_ALERT_COOLDOWN_SECONDS = 300  # 5 min per path (digest hourly gestisce throttling)


class ErrorMonitoringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to monitor HTTP errors and send alerts for 4xx/5xx responses
    """

    def __init__(self, app, alert_service=None) -> None:
        super().__init__(app)
        self.alert_service = alert_service
        self._latency_alert_last_sent: dict[str, float] = {}
        # enabled is evaluated per-request to support startup/lazy init via app.state
        if alert_service is not None:
            logger.info("✅ ErrorMonitoringMiddleware initialized with AlertService")
        else:
            logger.info(
                "ℹ️ ErrorMonitoringMiddleware initialized without AlertService (will use app.state if available)"
            )

    def _resolve_alert_service(self, request: Request):
        if self.alert_service is not None:
            return self.alert_service
        return getattr(request.app.state, "alert_service", None)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and monitor for errors
        """
        # Generate request ID for tracking
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Record start time
        start_time = time.time()

        try:
            # Process request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Check if response is an error (4xx or 5xx)
            if response.status_code >= 400:
                await self._handle_error_response(
                    request=request,
                    response=response,
                    request_id=request_id,
                    duration_ms=duration_ms,
                )

            # Check for high latency
            alert_service = self._resolve_alert_service(request)
            if alert_service is not None:
                from backend.app.core.config import settings

                # Webhook paths do AI processing (15-30s normal), skip latency alerts
                # Webhook paths do AI processing (15-30s normal), skip latency alerts
                skip_latency = request.url.path in (
                    "/health",
                    "/webhook/instagram",
                    "/webhook/whatsapp",
                    "/webhook/telegram",
                    "/webhook/twitter",
                )
                if duration_ms > settings.latency_alert_threshold_ms and not skip_latency:
                    # Cooldown: only send one alert per path per 5 minutes
                    now = time.time()
                    path_key = request.url.path
                    last_sent = self._latency_alert_last_sent.get(path_key, 0)
                    if now - last_sent >= LATENCY_ALERT_COOLDOWN_SECONDS:
                        self._latency_alert_last_sent[path_key] = now
                        try:
                            await alert_service.send_latency_alert(
                                duration_ms=duration_ms,
                                method=request.method,
                                path=request.url.path,
                                threshold_ms=settings.latency_alert_threshold_ms,
                                request_id=request_id,
                                user_agent=request.headers.get("user-agent"),
                            )
                        except Exception as e:
                            logger.error(f"Failed to send latency alert: {e}")

            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as exc:
            # Handle unhandled exceptions
            logger.error(f"Unhandled exception in request {request_id}: {exc}")

            # Calculate duration
            duration_ms = (time.time() - start_time) * 1000

            # Send alert for server error
            alert_service = self._resolve_alert_service(request)
            if alert_service is not None:
                try:
                    await alert_service.send_http_error_alert(
                        status_code=500,
                        method=request.method,
                        path=request.url.path,
                        error_detail=str(exc),
                        request_id=request_id,
                        user_agent=request.headers.get("user-agent"),
                    )
                except Exception as alert_exc:
                    logger.error(f"Failed to send alert for exception: {alert_exc}")

            # Return error response
            return JSONResponse(
                status_code=500,
                content={
                    "detail": "Internal server error",
                    "request_id": request_id,
                    "error": str(exc) if logger.level == logging.DEBUG else "Internal server error",
                },
                headers={"X-Request-ID": request_id},
            )

    async def _handle_error_response(
        self, request: Request, response: Response, request_id: str, duration_ms: float
    ):
        """
        Handle error response (4xx/5xx)
        """
        status_code = response.status_code
        method = request.method
        path = request.url.path
        user_agent = request.headers.get("user-agent", "Unknown")

        # Suppress noisy logs for known non-critical patterns
        _suppressed_patterns = {
            401: ("/api/dashboard/",),  # Browser tabs with expired JWT
            404: ("/api/drive/",),  # Deleted Drive folders
        }
        is_suppressed = any(path.startswith(p) for p in _suppressed_patterns.get(status_code, ()))

        if is_suppressed:
            logger.debug(f"[{request_id}] {method} {path} → {status_code} (suppressed)")
            return

        # Log error
        logger.warning(
            f"[{request_id}] {method} {path} → {status_code} "
            f"({duration_ms:.2f}ms) | UA: {user_agent[:50]}"
        )

        # Send alert if enabled and if it's a server error (5xx) or critical client error
        alert_service = self._resolve_alert_service(request)
        if alert_service is not None:
            # Only alert for:
            # - All 5xx errors (except 503 transient)
            # - 429 (Too Many Requests) - potential DoS
            # - 403 (Forbidden) - potential security issue
            should_alert = (
                (status_code >= 500 and status_code != 503)
                or status_code == 429
                or status_code == 403
            )

            if should_alert:
                try:
                    # Try to extract error detail from response body
                    error_detail = None
                    try:
                        if hasattr(response, "body"):
                            body = response.body
                            if isinstance(body, bytes):
                                import json

                                body_json = json.loads(body.decode())
                                error_detail = body_json.get("detail", body_json.get("message"))
                    except Exception:
                        pass  # Ignore body parsing errors

                    await alert_service.send_http_error_alert(
                        status_code=status_code,
                        method=method,
                        path=path,
                        error_detail=error_detail,
                        request_id=request_id,
                        user_agent=user_agent,
                    )
                except Exception as exc:
                    logger.error(f"Failed to send error alert: {exc}")


def create_error_monitoring_middleware(alert_service: Any = None) -> Any:
    """
    Factory function to create ErrorMonitoringMiddleware

    Args:
        alert_service: Optional AlertService instance

    Returns:
        ErrorMonitoringMiddleware instance
    """

    def middleware_factory(app: Any) -> Any:
        return ErrorMonitoringMiddleware(app, alert_service)

    return middleware_factory
