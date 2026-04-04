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

    def __init__(self) -> None:
        self.redis_available = False
        self.redis_client = None

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
            manager.register_component("rate_limiter", "fallback_memory")
            logger.info("Rate limiter using in-memory storage")

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
            logger.warning(f"Rate limit Redis error, falling back to in-memory: {e}")
            # Fail-safe: use in-memory with stricter limits (half the normal limit)
            safe_limit = max(1, limit // 2)
            if key not in _rate_limit_storage:
                _rate_limit_storage[key] = []
            _rate_limit_storage[key] = [t for t in _rate_limit_storage[key] if t > window_start]
            count = len(_rate_limit_storage[key])
            allowed = count < safe_limit
            if allowed:
                _rate_limit_storage[key].append(current_time)
            remaining = max(0, safe_limit - count - 1)
            return allowed, {"limit": safe_limit, "remaining": remaining, "reset": current_time + window}


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
        "/api/v1/visa-oracle/chat": (10, 3600),  # 10 per hour per IP
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
