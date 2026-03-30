"""
Middleware Configuration Module

Handles registration of all middleware components for FastAPI application.
"""

import logging

from fastapi import FastAPI

from backend.app.setup.cors_config import register_cors_middleware
from backend.middleware.activity_logging import ActivityLoggingMiddleware
from backend.middleware.error_monitoring import ErrorMonitoringMiddleware
from backend.middleware.hybrid_auth import HybridAuthMiddleware
from backend.middleware.rate_limiter import RateLimitMiddleware
from backend.middleware.request_tracing import RequestTracingMiddleware

try:
    from backend.middleware.pii_scanner import PIIScannerMiddleware as _PIIScannerMiddleware

    _pii_scanner_available = True
except ImportError:
    _PIIScannerMiddleware = None  # type: ignore[assignment]
    _pii_scanner_available = False

logger = logging.getLogger("zantara.backend")


def _register_brotli_middleware(app: FastAPI) -> bool:
    """
    Register Brotli compression middleware if available.
    Falls back to GZip if brotli-asgi is not installed.
    Returns True if Brotli was registered, False otherwise.
    """
    try:
        from brotli_asgi import BrotliMiddleware

        app.add_middleware(
            BrotliMiddleware,
            minimum_size=500,  # Only compress responses > 500 bytes
            gzip_fallback=True,  # Fall back to gzip if client doesn't support br
        )
        return True
    except ImportError:
        try:
            from starlette.middleware.gzip import GZipMiddleware

            app.add_middleware(GZipMiddleware, minimum_size=500)
            logger.warning("⚠️ brotli-asgi not installed, using GZip fallback")
            return False
        except Exception:
            logger.warning("⚠️ No compression middleware available")
            return False


def register_middleware(app: FastAPI) -> None:
    """
    Register all middleware components on FastAPI application.

    Middleware order matters (Starlette wraps in reverse order):
    1. CORS (first, wraps all responses)
    2. Brotli/GZip Compression (compress all responses)
    3. Hybrid Authentication (after CORS)
    4. Request Tracing (correlation IDs, end-to-end tracing)
    5. Error Monitoring (monitors 4xx/5xx errors, sends alerts)
    6. Rate Limiting (prevents API abuse, DoS protection)
    7. Activity Logging (audit trail)

    Args:
        app: FastAPI application instance
    """
    # Add CORS middleware first so it wraps all downstream middleware and responses.
    # Starlette wraps middleware in reverse order; the first added user-middleware is the outermost.
    register_cors_middleware(app)

    # Add Brotli compression (or GZip fallback) - compresses all API responses
    has_brotli = _register_brotli_middleware(app)
    compression = "Brotli" if has_brotli else "GZip"

    # Add Hybrid Authentication middleware (after CORS)
    app.add_middleware(HybridAuthMiddleware)

    # Add Request Tracing middleware (correlation IDs, end-to-end tracing)
    app.add_middleware(RequestTracingMiddleware)

    # Add Error Monitoring middleware (monitors 4xx/5xx errors, sends alerts)
    app.add_middleware(ErrorMonitoringMiddleware)

    # Add Rate Limiting middleware (prevents API abuse, DoS protection)
    app.add_middleware(RateLimitMiddleware)

    # Add Activity Logging middleware (logs all API calls for audit trail)
    app.add_middleware(ActivityLoggingMiddleware)

    # Add PII Scanner middleware (redacts Indonesian PII from /api/agentic/* responses)
    # UU PDP No. 27/2022 Art. 35, 36, 38 compliance
    if _pii_scanner_available:
        app.add_middleware(_PIIScannerMiddleware)
        pii_label = " + PIIScanner"
    else:
        logger.warning("⚠️ presidio_analyzer not installed — PIIScanner middleware disabled")
        pii_label = ""

    logger.info(
        f"✅ Middleware registered: CORS + {compression} + Auth + Tracing + ErrorMonitoring + RateLimiting + ActivityLogging{pii_label}",
    )
