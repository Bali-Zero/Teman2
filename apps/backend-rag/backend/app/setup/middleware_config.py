"""
Middleware Configuration Module

Handles registration of all middleware components for FastAPI application.
"""

import logging

from fastapi import FastAPI
from middleware.error_monitoring import ErrorMonitoringMiddleware
from middleware.hybrid_auth import HybridAuthMiddleware
from middleware.rate_limiter import RateLimitMiddleware
from middleware.request_tracing import RequestTracingMiddleware

from .cors_config import register_cors_middleware

logger = logging.getLogger("zantara.backend")


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware components on FastAPI application.

    Middleware order matters:
    1. CORS (first, wraps all responses)
    2. Hybrid Authentication (after CORS)
    3. Request Tracing (correlation IDs, end-to-end tracing)
    4. Error Monitoring (monitors 4xx/5xx errors, sends alerts)
    5. Rate Limiting (prevents API abuse, DoS protection)

    Args:
        app: FastAPI application instance
    """
    # Add CORS middleware first so it wraps all downstream middleware and responses.
    # Starlette wraps middleware in reverse order; the first added user-middleware is the outermost.
    register_cors_middleware(app)

    # Add Hybrid Authentication middleware (after CORS)
    app.add_middleware(HybridAuthMiddleware)

    # Add Request Tracing middleware (correlation IDs, end-to-end tracing)
    app.add_middleware(RequestTracingMiddleware)

    # Add Error Monitoring middleware (monitors 4xx/5xx errors, sends alerts)
    app.add_middleware(ErrorMonitoringMiddleware)

    # Add Rate Limiting middleware (prevents API abuse, DoS protection)
    app.add_middleware(RateLimitMiddleware)

    logger.info("✅ Middleware registered: CORS + Auth + Tracing + ErrorMonitoring + RateLimiting")

