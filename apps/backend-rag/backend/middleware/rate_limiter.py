"""
Rate Limiting Middleware for ZANTARA
Prevents API abuse and ensures fair usage

Features:
- IP-based rate limiting
- User-based rate limiting
- Configurable limits per endpoint
- Redis-backed for distributed systems
"""

import logging
import time

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

# In-memory rate limit storage (fallback) with eviction
_rate_limit_storage: dict[str, list[float]] = {}
_MAX_RATE_LIMIT_KEYS = 10_000
_EVICTION_STALE_SECONDS = 120


def _evict_stale_keys() -> None:
    """Evict stale keys to prevent unbounded memory growth."""
    global _rate_limit_storage
    if len(_rate_limit_storage) <= _MAX_RATE_LIMIT_KEYS:
        return
    cutoff = time.time() - _EVICTION_STALE_SECONDS
    _rate_limit_storage = {
        k: v for k, v in _rate_limit_storage.items()
        if v and v[-1] > cutoff
    }


class RateLimiter:
    """
    Sliding-window rate limiter.

    - Primary backend: Redis via `RedisManager` (distributed across replicas).
    - Fallback: in-memory dict with stricter limits (half the configured
      per-route limit) when Redis is unreachable or returns errors.
    - Self-healing: after a Redis error flips `redis_available` to False,
      subsequent requests try to reconnect on a cooldown (see
      `_RECOVERY_COOLDOWN`). This way a transient Redis hiccup doesn't
      leave the limiter permanently degraded.

    Observability:
    - `self.metrics` exposes running counters that the admin
      `/api/admin/rate-limit/stats` endpoint reads.
    """

    _RECOVERY_COOLDOWN = 10.0  # seconds between reconnect attempts

    def __init__(self) -> None:
        self.redis_available = False
        self.redis_client = None
        self._last_recovery_attempt: float = 0.0
        self._last_error: str | None = None
        self.metrics: dict[str, int] = {
            "redis_requests": 0,
            "redis_errors": 0,
            "memory_fallback_requests": 0,
            "recovery_attempts": 0,
            "recovery_successes": 0,
        }

        self._connect_from_manager()

    def _connect_from_manager(self) -> None:
        """(Re)acquire a sync Redis client from the central manager."""
        # Get sync Redis client from centralized RedisManager
        from backend.core.redis_manager import RedisManager

        manager = RedisManager.get_instance()
        client = manager.get_sync_client()
        if client is not None:
            self.redis_client = client
            self.redis_available = True
            manager.register_component("rate_limiter", "active")
            logger.info("Rate limiter using Redis via RedisManager")
        else:
            self.redis_client = None
            self.redis_available = False
            manager.register_component("rate_limiter", "fallback_memory")
            logger.warning("Rate limiter using in-memory storage — no Redis available, rate limits not shared across workers")

    def _try_recover(self) -> None:
        """Attempt to reconnect to Redis if we've been in fallback mode."""
        now = time.time()
        if now - self._last_recovery_attempt < self._RECOVERY_COOLDOWN:
            return
        self._last_recovery_attempt = now
        self.metrics["recovery_attempts"] += 1
        was_unavailable = not self.redis_available
        self._connect_from_manager()
        if was_unavailable and self.redis_available:
            self.metrics["recovery_successes"] += 1
            self._last_error = None
            logger.info("Rate limiter Redis connection recovered")

    def is_allowed(self, key: str, limit: int, window: int) -> tuple[bool, dict]:
        """
        Check if request is allowed under rate limit

        Args:
            key: Unique identifier (IP or user)
            limit: Max requests allowed
            window: Time window in seconds

        Returns:
            (allowed, info_dict)
        """
        current_time = int(time.time())
        window_start = current_time - window

        # If we previously degraded to in-memory, try to reconnect on a
        # cooldown so a transient Redis outage doesn't leave the limiter
        # permanently unshared across workers.
        if not self.redis_available:
            self._try_recover()

        try:
            if self.redis_available and self.redis_client:
                # Redis-backed sliding window
                self.metrics["redis_requests"] += 1
                pipe = self.redis_client.pipeline()

                # Remove old entries
                pipe.zremrangebyscore(key, 0, window_start)

                # Count current requests
                pipe.zcard(key)

                # Add current request
                pipe.zadd(key, {str(current_time): current_time})

                # Set expiration
                pipe.expire(key, window)

                results = pipe.execute()
                count = results[1]

                allowed = count < limit
                remaining = max(0, limit - count - 1)

                return allowed, {
                    "limit": limit,
                    "remaining": remaining,
                    "reset": current_time + window,
                    "backend": "redis",
                }
            else:
                # In-memory fallback (with eviction guard)
                self.metrics["memory_fallback_requests"] += 1
                _evict_stale_keys()
                if key not in _rate_limit_storage:
                    _rate_limit_storage[key] = []

                # Remove old entries
                _rate_limit_storage[key] = [t for t in _rate_limit_storage[key] if t > window_start]

                count = len(_rate_limit_storage[key])
                allowed = count < limit

                if allowed:
                    _rate_limit_storage[key].append(current_time)

                remaining = max(0, limit - count - 1)

                return allowed, {
                    "limit": limit,
                    "remaining": remaining,
                    "reset": current_time + window,
                    "backend": "memory",
                }

        except Exception as e:
            # Redis call raised mid-flight. Record the error and use the
            # half-limit in-memory fallback for THIS request. We intentionally
            # do NOT flip self.redis_available to False here — the existing
            # behavior is to retry Redis on every call (per-request
            # fail-safe). The `_try_recover` cooldown path above handles the
            # other failure mode: Redis was down at boot and comes back.
            self.metrics["redis_errors"] += 1
            self._last_error = f"{type(e).__name__}: {e}"
            logger.warning(f"Rate limit Redis error, falling back to in-memory: {e}")
            # Fail-safe: in-memory with half limit so a Redis outage doesn't
            # multiply effective capacity by the number of replicas.
            safe_limit = max(1, limit // 2)
            if key not in _rate_limit_storage:
                _rate_limit_storage[key] = []
            _rate_limit_storage[key] = [t for t in _rate_limit_storage[key] if t > window_start]
            count = len(_rate_limit_storage[key])
            allowed = count < safe_limit
            if allowed:
                _rate_limit_storage[key].append(current_time)
            remaining = max(0, safe_limit - count - 1)
            return allowed, {
                "limit": safe_limit,
                "remaining": remaining,
                "reset": current_time + window,
                "backend": "memory_degraded",
            }


# Global rate limiter instance
rate_limiter = RateLimiter()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware to enforce rate limits on API endpoints
    """

    # Rate limit configuration per endpoint pattern
    RATE_LIMITS = {
        # Strict limits for expensive operations
        "/api/agents/journey/create": (10, 3600),  # 10 per hour
        "/api/agents/compliance/track": (20, 3600),  # 20 per hour
        "/api/agents/ingestion/run": (5, 3600),  # 5 per hour
        # CRM endpoints - moderate limits
        "/api/crm/clients": (100, 60),  # 100 per minute
        "/api/crm/practices": (100, 60),  # 100 per minute
        "/api/crm/interactions": (150, 60),  # 150 per minute (more frequent)
        "/api/crm/shared-memory": (60, 60),  # 60 per minute (expensive queries)
        # CRM stats endpoints - stricter limits (cached but still protect)
        "/api/crm/clients/stats": (30, 60),  # 30 per minute
        "/api/crm/practices/stats": (30, 60),  # 30 per minute
        "/api/crm/interactions/stats": (30, 60),  # 30 per minute
        "/api/crm/shared-memory/team-overview": (20, 60),  # 20 per minute
        "/api/crm/shared-memory/upcoming-renewals": (20, 60),  # 20 per minute
        # Moderate limits for read operations
        "/api/agents/journey/": (60, 60),  # 60 per minute
        "/api/agents/compliance/": (60, 60),  # 60 per minute
        "/api/agents/": (100, 60),  # 100 per minute
        # Generous limits for general endpoints
        "/bali-zero/chat": (30, 60),  # 30 per minute (includes reranker usage)
        "/search": (60, 60),  # 60 per minute
        "/api/": (120, 60),  # 120 per minute
        # Reranker-specific endpoints (if any in future)
        "/rerank": (100, 60),  # 100 per minute (anti-abuse)
        # Public endpoint rate limits (Security Audit 2026-01-13)
        "/api/intel/scraper/submit": (10, 60),  # 10 per minute - prevent spam
        "/api/intel/staging/approve/": (20, 60),  # 20 per minute - prevent abuse
        "/api/audio/": (30, 60),  # 30 per minute - prevent cost abuse (TTS/STT)
        "/api/whatsapp/send": (30, 60),  # 30 per minute - prevent send/message abuse
        "/api/knowledge/visa": (100, 60),  # 100 per minute - public knowledge base
        "/preview/": (60, 60),  # 60 per minute - article previews
        "/preview/upload": (10, 60),  # 10 per minute - prevent storage abuse
        "/api/legal/parent-documents": (20, 60),  # 20 per minute - internal ingestion
        # Default for all other endpoints
        "*": (200, 60),  # 200 per minute
    }

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client identifier from authenticated state (set by HybridAuthMiddleware)
        client_ip = request.client.host if request.client else "unknown"
        authenticated_user = getattr(request.state, "user", None)
        if authenticated_user and isinstance(authenticated_user, dict):
            user_id = authenticated_user.get("email") or authenticated_user.get("sub") or client_ip
        else:
            user_id = client_ip

        # Find matching rate limit
        limit, window = self._get_rate_limit(request.url.path)

        # Fail-open if the limiter malfunctions beyond its internal Redis fallback —
        # a hot-path middleware bug must not take the whole API offline.
        rate_limit_key = f"ratelimit:{user_id}:{request.url.path}"
        try:
            allowed, info = rate_limiter.is_allowed(rate_limit_key, limit, window)
        except Exception:
            logger.exception(f"Rate limiter failure, failing open for {request.url.path}")
            return await call_next(request)

        if not allowed:
            logger.warning(f"⚠️ Rate limit exceeded: {user_id} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Limit: {limit} per {window}s",
                    "limit": info["limit"],
                    "remaining": info["remaining"],
                    "reset": info["reset"],
                },
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": str(info["remaining"]),
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(window),
                },
            )

        # Add rate limit headers to response
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response

    def _get_rate_limit(self, path: str) -> tuple[int, int]:
        """Find matching rate limit for path"""
        # Try exact match first
        if path in self.RATE_LIMITS:
            return self.RATE_LIMITS[path]

        # Try prefix match
        for pattern, limit_config in self.RATE_LIMITS.items():
            if pattern != "*" and path.startswith(pattern):
                return limit_config

        # Default rate limit
        return self.RATE_LIMITS["*"]


def get_rate_limit_stats() -> dict:
    """Get rate limiting statistics"""
    return {
        "backend": "redis" if rate_limiter.redis_available else "memory",
        "connected": rate_limiter.redis_available,
        "rate_limits_configured": len(RateLimitMiddleware.RATE_LIMITS),
        "metrics": dict(rate_limiter.metrics),
        "last_error": rate_limiter._last_error,
        "in_memory_keys": len(_rate_limit_storage),
        "recovery_cooldown_seconds": RateLimiter._RECOVERY_COOLDOWN,
    }
