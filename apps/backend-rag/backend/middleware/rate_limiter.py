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

# In-memory rate limit storage (fallback)
_rate_limit_storage = {}


class RateLimiter:
    """
    Rate limiter with sliding window algorithm
    """

    def __init__(self):
        self.redis_available = False
        self.redis_client = None

        # Try to connect to Redis
        from app.core.config import settings

        redis_url = settings.redis_url
        if redis_url:
            try:
                import redis

                self.redis_client = redis.from_url(redis_url, decode_responses=True)
                self.redis_client.ping()
                self.redis_available = True
                logger.info("✅ Rate limiter using Redis")
            except Exception as e:
                logger.warning(f"⚠️ Rate limiter using memory: {e}")
        else:
            logger.info("ℹ️ Rate limiter using in-memory storage")

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

        try:
            if self.redis_available and self.redis_client:
                # Redis-backed sliding window
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
                }
            else:
                # In-memory fallback
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
                }

        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # On error, allow request (fail open)
            return True, {"limit": limit, "remaining": limit, "reset": current_time + window}


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
        # Default for all other endpoints
        "*": (200, 60),  # 200 per minute
    }

    async def dispatch(self, request: Request, call_next):
        # Skip rate limiting for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)

        # Get client identifier (IP or user)
        client_ip = request.client.host if request.client else "unknown"
        user_id = request.headers.get("X-User-ID", client_ip)

        # Find matching rate limit
        limit, window = self._get_rate_limit(request.url.path)

        # Check rate limit
        rate_limit_key = f"ratelimit:{user_id}:{request.url.path}"
        allowed, info = rate_limiter.is_allowed(rate_limit_key, limit, window)

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
    }
