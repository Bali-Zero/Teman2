"""
Rate Limiting Middleware using Redis sliding window algorithm.

Provides:
- Per-IP rate limiting (default: 100 requests/minute)
- Per-user rate limiting for authenticated requests
- Excluded paths for health checks
- Custom limit headers in responses
"""

import time
from typing import Optional, Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from backend.core.cache import cache
from backend.core.logger import get_logger, LogAction

logger = get_logger(__name__, component="rate_limit")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Redis-based sliding window rate limiting middleware.

    Features:
    - Per-IP tracking with Redis
    - Configurable limits per path
    - Whitelist for internal IPs
    - Rate limit headers (X-RateLimit-*)
    """

    def __init__(
        self,
        app: ASGIApp,
        requests_per_minute: int = 100,
        burst_size: Optional[int] = None,
        excluded_paths: Optional[list] = None,
        whitelisted_ips: Optional[list] = None,
    ):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size or requests_per_minute
        self.excluded_paths = set(
            excluded_paths
            or [
                "/health",
                "/metrics",
                "/docs",
                "/redoc",
                "/openapi.json",
            ]
        )
        self.whitelisted_ips = set(whitelisted_ips or ["127.0.0.1", "::1"])

    def _get_client_id(self, request: Request) -> str:
        """Get unique identifier for the client."""
        # Try to get user ID from auth
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return f"user:{user_id}"

        # Fall back to IP address
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return f"ip:{forwarded.split(',')[0].strip()}"

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"

        return f"ip:{request.client.host if request.client else 'unknown'}"

    def _is_excluded(self, request: Request) -> bool:
        """Check if request path is excluded from rate limiting."""
        path = request.url.path
        return any(path.startswith(exc) for exc in self.excluded_paths)

    def _is_whitelisted(self, request: Request) -> bool:
        """Check if client IP is whitelisted."""
        client_ip = request.client.host if request.client else ""
        return client_ip in self.whitelisted_ips

    async def _check_rate_limit(self, client_id: str) -> tuple[bool, dict]:
        """
        Check if request is within rate limit using sliding window.

        Returns:
            (allowed: bool, headers: dict)
        """
        now = time.time()
        window = 60  # 1 minute window
        key = f"rate_limit:{client_id}"

        try:
            # Get current request count in window
            # Remove entries older than window
            cutoff = now - window

            # Use Redis sorted set for sliding window
            pipe = cache.redis.pipeline()

            # Remove old entries
            pipe.zremrangebyscore(key, 0, cutoff)

            # Count current entries
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry on the key
            pipe.expire(key, window)

            results = await pipe.execute()
            current_count = results[1]

            # Check if over limit
            remaining = max(0, self.requests_per_minute - current_count)
            allowed = current_count <= self.requests_per_minute

            # Calculate reset time
            reset_time = int(now + window)

            headers = {
                "X-RateLimit-Limit": str(self.requests_per_minute),
                "X-RateLimit-Remaining": str(remaining),
                "X-RateLimit-Reset": str(reset_time),
            }

            if not allowed:
                logger.warning(
                    "Rate limit exceeded",
                    action=LogAction.BLOCK,
                    metadata={
                        "client_id": client_id,
                        "count": current_count,
                        "limit": self.requests_per_minute,
                    },
                )

            return allowed, headers

        except Exception as e:
            # On Redis error, allow request but log error
            logger.error(
                "Rate limiting check failed",
                action=LogAction.ERROR,
                metadata={"error": str(e), "client_id": client_id},
            )
            return True, {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with rate limiting."""
        # Skip rate limiting for excluded paths
        if self._is_excluded(request):
            return await call_next(request)

        # Skip for whitelisted IPs
        if self._is_whitelisted(request):
            return await call_next(request)

        # Get client identifier
        client_id = self._get_client_id(request)

        # Check rate limit
        allowed, headers = await self._check_rate_limit(client_id)

        if not allowed:
            return Response(
                content='{"error": "Rate limit exceeded", "retry_after": 60}',
                status_code=429,
                headers={
                    **headers,
                    "Content-Type": "application/json",
                    "Retry-After": "60",
                },
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers to response
        for header, value in headers.items():
            response.headers[header] = value

        return response


class RateLimitConfig:
    """Configuration for rate limiting."""

    # Default: 100 requests per minute
    DEFAULT_LIMIT = 100

    # Stricter limits for specific paths
    PATH_LIMITS = {
        "/api/auth/": 10,  # 10 requests per minute for auth
        "/api/login": 5,  # 5 requests per minute for login
    }

    # Premium users get higher limits
    PREMIUM_LIMIT = 1000


def get_rate_limit_for_path(path: str, is_premium: bool = False) -> int:
    """Get rate limit for specific path."""
    if is_premium:
        return RateLimitConfig.PREMIUM_LIMIT

    for prefix, limit in RateLimitConfig.PATH_LIMITS.items():
        if path.startswith(prefix):
            return limit

    return RateLimitConfig.DEFAULT_LIMIT
