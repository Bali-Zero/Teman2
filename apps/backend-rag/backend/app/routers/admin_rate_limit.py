"""
Admin Rate-Limit Router.

Surfaces the in-process rate-limiter's observability snapshot:
backend (redis | memory | memory_degraded), last Redis error if any,
request counters, recovery attempts/successes, and the in-memory
fallback cardinality.

Admin auth via `verify_debug_access`.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from backend.app.routers.debug import verify_debug_access
from backend.app.utils.logging_utils import get_logger
from backend.middleware.rate_limiter import get_rate_limit_stats

logger = get_logger(__name__)

router = APIRouter(prefix="/api/admin/rate-limit", tags=["admin-rate-limit"])


@router.get("/stats")
async def rate_limit_stats(
    _: bool = Depends(verify_debug_access),
) -> dict[str, Any]:
    """
    Return:
      - backend: "redis" | "memory" | "memory_degraded"
      - connected: bool (Redis reachable)
      - rate_limits_configured: count of per-route rules
      - metrics: {redis_requests, redis_errors, memory_fallback_requests,
                  recovery_attempts, recovery_successes}
      - last_error: str | None
      - in_memory_keys: current cardinality of the fallback dict
      - recovery_cooldown_seconds: cooldown between reconnect attempts
    """
    return get_rate_limit_stats()
