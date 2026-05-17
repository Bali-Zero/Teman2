"""
Health check endpoints for Kubernetes and monitoring.

Provides:
- Liveness probe
- Readiness probe
- Deep health checks with dependencies
- Metrics endpoint
"""

import time
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from datetime import datetime

from backend.core.logger import get_logger, LogAction
from backend.db.connection import health_check as db_health_check
from backend.core.cache import cache

logger = get_logger(__name__, component="health")

router = APIRouter(prefix="/health", tags=["health"])


class HealthStatus(BaseModel):
    """Health status response."""

    status: str
    timestamp: str
    version: str = "1.0.0"
    uptime_seconds: float
    checks: dict[str, Any] = {}


class ComponentHealth(BaseModel):
    """Individual component health."""

    status: str
    response_time_ms: float
    details: dict[str, Any] = {}


# Track application start time
_start_time = time.time()


async def get_basic_health() -> dict[str, Any]:
    """Basic health check - lightweight."""
    return {"status": "healthy", "uptime_seconds": round(time.time() - _start_time, 2)}


@router.get("/live", status_code=status.HTTP_200_OK)
async def liveness_probe() -> dict[str, str]:
    """
    Kubernetes liveness probe.

    Returns 200 if the application is running.
    If this fails, Kubernetes will restart the container.
    """
    return {"status": "alive"}


@router.get("/ready", status_code=status.HTTP_200_OK)
async def readiness_probe() -> dict[str, Any]:
    """
    Kubernetes readiness probe.

    Returns 200 if the application is ready to accept traffic.
    If this fails, Kubernetes will remove the pod from service.
    """
    checks = {}
    all_healthy = True

    # Check database
    try:
        db_health = await db_health_check()
        checks["database"] = {
            "status": db_health.get("status", "unknown"),
            "response_time_ms": db_health.get("latency_ms", 0),
        }
        if db_health.get("status") != "healthy":
            all_healthy = False
    except Exception as e:
        checks["database"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    # Check cache
    try:
        cache_health = await cache.health_check()
        checks["cache"] = cache_health
        if cache_health.get("status") != "healthy":
            all_healthy = False
    except Exception as e:
        checks["cache"] = {"status": "unhealthy", "error": str(e)}
        all_healthy = False

    status_code = (
        status.HTTP_200_OK if all_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    )

    return {"status": "ready" if all_healthy else "not_ready", "checks": checks}


@router.get("/deep", response_model=HealthStatus)
async def deep_health_check() -> HealthStatus:
    """
    Comprehensive health check with all dependencies.

    Returns detailed health information about all system components.
    """
    start_time = time.time()
    checks: dict[str, Any] = {}
    all_healthy = True

    # Database check
    db_start = time.time()
    try:
        db_result = await db_health_check()
        checks["database"] = ComponentHealth(
            status=db_result.get("status", "unknown"),
            response_time_ms=round((time.time() - db_start) * 1000, 2),
            details={
                "pool_size": db_result.get("pool_size"),
                "free_connections": db_result.get("free_connections"),
            },
        )
        if db_result.get("status") != "healthy":
            all_healthy = False
    except Exception as e:
        checks["database"] = ComponentHealth(
            status="unhealthy",
            response_time_ms=round((time.time() - db_start) * 1000, 2),
            details={"error": str(e)},
        )
        all_healthy = False

    # Cache check
    cache_start = time.time()
    try:
        cache_result = await cache.health_check()
        checks["cache"] = ComponentHealth(
            status=cache_result.get("status", "unknown"),
            response_time_ms=round((time.time() - cache_start) * 1000, 2),
            details={
                "used_memory": cache_result.get("used_memory"),
                "connected_clients": cache_result.get("connected_clients"),
            },
        )
        if cache_result.get("status") != "healthy":
            all_healthy = False
    except Exception as e:
        checks["cache"] = ComponentHealth(
            status="unhealthy",
            response_time_ms=round((time.time() - cache_start) * 1000, 2),
            details={"error": str(e)},
        )
        all_healthy = False

    # Task queue check
    from backend.core.task_queue import task_queue

    queue_start = time.time()
    try:
        queue_stats = task_queue.get_stats()
        checks["task_queue"] = ComponentHealth(
            status="healthy" if queue_stats.get("running") else "unhealthy",
            response_time_ms=round((time.time() - queue_start) * 1000, 2),
            details=queue_stats,
        )
        if not queue_stats.get("running"):
            all_healthy = False
    except Exception as e:
        checks["task_queue"] = ComponentHealth(
            status="unhealthy",
            response_time_ms=round((time.time() - queue_start) * 1000, 2),
            details={"error": str(e)},
        )
        all_healthy = False

    # System resources check
    try:
        import psutil

        memory = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        checks["system"] = ComponentHealth(
            status="healthy",
            response_time_ms=0,
            details={
                "memory_percent": memory.percent,
                "disk_percent": disk.percent,
                "cpu_percent": psutil.cpu_percent(interval=0.1),
            },
        )

        # Alert if resources are constrained
        if memory.percent > 90 or disk.percent > 90:
            checks["system"].status = "warning"
            logger.warning(
                "System resources constrained",
                action=LogAction.ANALYZE,
                metadata={
                    "memory_percent": memory.percent,
                    "disk_percent": disk.percent,
                },
            )

    except ImportError:
        checks["system"] = ComponentHealth(
            status="unknown",
            response_time_ms=0,
            details={"message": "psutil not installed"},
        )

    total_time = round((time.time() - start_time) * 1000, 2)

    logger.info(
        "Deep health check completed",
        action=LogAction.ANALYZE,
        metadata={
            "total_time_ms": total_time,
            "all_healthy": all_healthy,
            "checks_count": len(checks),
        },
    )

    return HealthStatus(
        status="healthy" if all_healthy else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        uptime_seconds=round(time.time() - _start_time, 2),
        checks={
            k: v.dict() if isinstance(v, ComponentHealth) else v
            for k, v in checks.items()
        },
    )


@router.get("/stats")
async def get_stats() -> dict[str, Any]:
    """Get runtime statistics."""
    from backend.core.task_queue import task_queue
    from backend.core.circuit_breaker import get_registry as get_cb_registry
    from backend.core.rate_limiter import get_registry as get_rl_registry

    return {
        "uptime_seconds": round(time.time() - _start_time, 2),
        "task_queue": task_queue.get_stats(),
        "circuit_breakers": get_cb_registry().get_all_stats(),
        "rate_limiters": get_rl_registry().get_all_stats(),
    }


@router.post("/reset")
async def reset_system() -> dict[str, str]:
    """
    Reset all circuit breakers and rate limiters.
    Admin use only.
    """
    from backend.core.circuit_breaker import get_registry as get_cb_registry
    from backend.core.rate_limiter import get_registry as get_rl_registry

    try:
        await get_cb_registry().reset_all()
        await get_rl_registry().reset_all()

        logger.info("System reset completed", action=LogAction.UPDATE)

        return {"status": "reset_complete"}
    except Exception as e:
        logger.error(
            "System reset failed", action=LogAction.ERROR, metadata={"error": str(e)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset failed: {str(e)}",
        ) from e


# Middleware for tracking request health
class HealthTrackingMiddleware:
    """Middleware to track request metrics for health monitoring."""

    def __init__(self, app):
        self.app = app
        self.request_count = 0
        self.error_count = 0
        self.request_times: list[float] = []

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.time()
        self.request_count += 1

        async def wrapped_send(message):
            if message["type"] == "http.response.start":
                status = message.get("status", 200)
                if status >= 500:
                    self.error_count += 1
            await send(message)

        try:
            await self.app(scope, receive, wrapped_send)
        except Exception:
            self.error_count += 1
            raise
        finally:
            duration = time.time() - start_time
            self.request_times.append(duration)

            # Keep only last 1000 request times
            if len(self.request_times) > 1000:
                self.request_times = self.request_times[-1000:]

    def get_metrics(self) -> dict[str, Any]:
        """Get request metrics."""
        if not self.request_times:
            return {
                "total_requests": self.request_count,
                "error_count": self.error_count,
                "error_rate": 0,
            }

        avg_time = sum(self.request_times) / len(self.request_times)

        return {
            "total_requests": self.request_count,
            "error_count": self.error_count,
            "error_rate": self.error_count / max(self.request_count, 1),
            "avg_response_time_ms": round(avg_time * 1000, 2),
            "p95_response_time_ms": round(
                sorted(self.request_times)[int(len(self.request_times) * 0.95)] * 1000,
                2,
            )
            if len(self.request_times) >= 20
            else None,
        }


__all__ = [
    "router",
    "liveness_probe",
    "readiness_probe",
    "deep_health_check",
    "HealthTrackingMiddleware",
]
