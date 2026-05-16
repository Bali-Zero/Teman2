"""API middleware — authentication, rate limiting, request tracing."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict

import structlog
from fastapi import Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from nuzantara_graph.config import settings

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# JWT Authentication (optional — allows anonymous access)
# ---------------------------------------------------------------------------

async def get_current_user(request: Request) -> dict:
    """Extract and validate JWT token from Authorization header.

    Returns user info dict. If no auth header, returns anonymous user.
    In development mode, auth is always optional.
    """
    auth_header = request.headers.get("authorization", "")

    if not auth_header or not auth_header.startswith("Bearer "):
        return {"user_id": "anonymous", "authenticated": False}

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return {"user_id": "anonymous", "authenticated": False}

    if not settings.jwt_secret:
        # No secret configured — skip validation
        return {"user_id": "anonymous", "authenticated": False}

    try:
        import jwt

        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "user_id": payload.get("sub", "unknown"),
            "authenticated": True,
            "claims": payload,
        }
    except Exception as e:
        logger.warning("jwt_validation_failed", error=str(e))
        raise HTTPException(status_code=401, detail="Invalid token") from e


# ---------------------------------------------------------------------------
# Rate Limiting (in-memory, per-user)
# ---------------------------------------------------------------------------

_MAX_TRACKED_KEYS = 10_000  # evict oldest keys to prevent unbounded growth


class _RateLimitStore:
    """In-memory sliding window rate limiter with bounded key set."""

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str, max_rpm: int) -> bool:
        """Return True if the request is allowed."""
        now = time.monotonic()
        window = 60.0  # 1 minute

        # Clean old entries for this key
        self._requests[key] = [
            t for t in self._requests[key] if now - t < window
        ]

        # Evict stale keys periodically to prevent memory leak
        if len(self._requests) > _MAX_TRACKED_KEYS:
            self._evict_stale(now, window)

        if len(self._requests[key]) >= max_rpm:
            return False

        self._requests[key].append(now)
        return True

    def remaining(self, key: str, max_rpm: int) -> int:
        now = time.monotonic()
        window = 60.0
        active = [t for t in self._requests[key] if now - t < window]
        return max(0, max_rpm - len(active))

    def _evict_stale(self, now: float, window: float) -> None:
        """Remove keys with no recent requests."""
        stale = [k for k, ts in self._requests.items() if not ts or now - ts[-1] >= window]
        for k in stale:
            del self._requests[k]


_rate_limiter = _RateLimitStore()


async def rate_limit(request: Request) -> None:
    """FastAPI dependency that enforces per-user rate limiting."""
    # Identify user from auth or IP
    user = request.headers.get("x-user-id", "")
    if not user:
        user = request.client.host if request.client else "unknown"

    if not _rate_limiter.check(user, settings.rate_limit_rpm):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again in 60 seconds.",
            headers={"Retry-After": "60"},
        )


# ---------------------------------------------------------------------------
# Request Tracing Middleware
# ---------------------------------------------------------------------------

class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Adds X-Request-ID header and logs request duration."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
        start = time.monotonic()

        # Bind request_id to structlog context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
            duration_ms = (time.monotonic() - start) * 1000

            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time-Ms"] = f"{duration_ms:.1f}"

            logger.info(
                "request_complete",
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                duration_ms=round(duration_ms, 1),
            )
            return response

        except Exception as e:
            duration_ms = (time.monotonic() - start) * 1000
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                duration_ms=round(duration_ms, 1),
            )
            raise
        finally:
            structlog.contextvars.unbind_contextvars("request_id")
