"""
ZANTARA RAG - Health Check Router

Provides health check endpoints for monitoring service status:
- /health - Basic health check for load balancers
- /health/detailed - Comprehensive service status for debugging
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request

from ..core.config import settings
from ..models import HealthResponse

logger = logging.getLogger(__name__)


async def get_qdrant_stats() -> dict[str, Any]:
    """
    Get real stats from Qdrant - collections count and total documents.
    """
    try:
        headers = {}
        if settings.qdrant_api_key:
            headers["api-key"] = settings.qdrant_api_key

        async with httpx.AsyncClient(
            base_url=settings.qdrant_url,
            headers=headers,
            timeout=5.0,
        ) as client:
            # Get all collections
            response = await client.get("/collections")
            response.raise_for_status()
            collections_data = response.json().get("result", {}).get("collections", [])

            total_documents = 0
            for coll in collections_data:
                coll_name = coll.get("name")
                if coll_name:
                    try:
                        coll_response = await client.get(f"/collections/{coll_name}")
                        coll_response.raise_for_status()
                        points = coll_response.json().get("result", {}).get("points_count", 0)
                        total_documents += points
                    except Exception:
                        pass  # Skip failed collections

            return {
                "collections": len(collections_data),
                "total_documents": total_documents,
            }
    except Exception as e:
        logger.warning(f"Failed to get Qdrant stats: {e}")
        return {"collections": 0, "total_documents": 0, "error": str(e)}


router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "", response_model=HealthResponse
)  # /health without trailing slash (for Fly.io health checks)
@router.get(
    "/", response_model=HealthResponse, include_in_schema=False
)  # /health/ with trailing slash
async def health_check(request: Request):
    """
    System health check - Non-blocking during startup.

    Returns "initializing" immediately if service not ready.
    Prevents container crashes during warmup by not creating heavy objects.
    """
    try:
        # Get search service from app.state
        search_service = getattr(request.app.state, "search_service", None)

        # CRITICAL: Return "initializing" immediately if service not ready
        # This prevents Fly.io from killing container during model loading
        if not search_service:
            logger.info("Health check: Service initializing (warmup in progress)")
            return HealthResponse(
                status="initializing",
                version="v100-qdrant",
                database={"status": "initializing", "message": "Warming up Qdrant connections"},
                embeddings={"status": "initializing", "message": "Loading embedding model"},
            )

        # Service is ready - perform lightweight check (no new instantiations)
        try:
            # Get model info without triggering heavy operations
            model_info = getattr(search_service.embedder, "model", "unknown")
            dimensions = getattr(search_service.embedder, "dimensions", 0)

            # Get real Qdrant stats
            qdrant_stats = await get_qdrant_stats()

            return HealthResponse(
                status="healthy",
                version="v100-qdrant",
                database={
                    "status": "connected",
                    "type": "qdrant",
                    "collections": qdrant_stats.get("collections", 0),
                    "total_documents": qdrant_stats.get("total_documents", 0),
                },
                embeddings={
                    "status": "operational",
                    "provider": getattr(search_service.embedder, "provider", "unknown"),
                    "model": model_info,
                    "dimensions": dimensions,
                },
            )
        except AttributeError as ae:
            # Embedder not fully initialized yet
            logger.warning(f"Health check: Embedder partially initialized: {ae}")
            return HealthResponse(
                status="initializing",
                version="v100-qdrant",
                database={"status": "partial", "message": "Services starting"},
                embeddings={"status": "loading", "message": str(ae)},
            )

    except Exception as e:
        # Log error but don't crash - return degraded status
        logger.error(f"Health check error: {e}", exc_info=True)
        return HealthResponse(
            status="degraded",
            version="v100-qdrant",
            database={"status": "error", "error": str(e)},
            embeddings={"status": "error", "error": str(e)},
        )


@router.get("/detailed")
async def detailed_health(request: Request) -> dict[str, Any]:
    """
    Detailed health check showing all service statuses.

    Returns comprehensive information about each service for debugging
    and monitoring purposes. Includes:
    - Individual service status (healthy/degraded/unavailable)
    - Error messages for failed services
    - Database connectivity check
    - Overall system health assessment

    Returns:
        dict: Detailed health status with per-service breakdown
    """
    services: dict[str, dict[str, Any]] = {}

    # Check SearchService (Critical)
    try:
        ss = getattr(request.app.state, "search_service", None)
        if ss:
            services["search"] = {
                "status": "healthy",
                "critical": True,
                "details": {
                    "provider": getattr(ss.embedder, "provider", "unknown"),
                    "model": getattr(ss.embedder, "model", "unknown"),
                },
            }
        else:
            services["search"] = {"status": "unavailable", "critical": True}
    except Exception as e:
        services["search"] = {"status": "error", "critical": True, "error": str(e)}

    # Check AI Client (Critical)
    try:
        ai = getattr(request.app.state, "ai_client", None)
        if ai:
            services["ai"] = {
                "status": "healthy",
                "critical": True,
                "details": {"type": type(ai).__name__},
            }
        else:
            services["ai"] = {"status": "unavailable", "critical": True}
    except Exception as e:
        services["ai"] = {"status": "error", "critical": True, "error": str(e)}

    # Check Database Pool
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if db_pool:
            # Perform a lightweight connectivity check
            async with db_pool.acquire() as conn:
                await conn.execute("SELECT 1")
            services["database"] = {
                "status": "healthy",
                "critical": False,
                "details": {
                    "min_size": db_pool.get_min_size(),
                    "max_size": db_pool.get_max_size(),
                    "size": db_pool.get_size(),
                },
            }
        else:
            services["database"] = {"status": "unavailable", "critical": False}
    except Exception as e:
        services["database"] = {"status": "error", "critical": False, "error": str(e)}

    # Check Memory Service
    try:
        memory_service = getattr(request.app.state, "memory_service", None)
        if memory_service:
            services["memory"] = {
                "status": "healthy",
                "critical": False,
                "details": {"type": type(memory_service).__name__},
            }
        else:
            services["memory"] = {"status": "unavailable", "critical": False}
    except Exception as e:
        services["memory"] = {"status": "error", "critical": False, "error": str(e)}

    # Check Intelligent Router
    try:
        router_instance = getattr(request.app.state, "intelligent_router", None)
        if router_instance:
            services["router"] = {
                "status": "healthy",
                "critical": False,
                "details": {"type": type(router_instance).__name__},
            }
        else:
            services["router"] = {"status": "unavailable", "critical": False}
    except Exception as e:
        services["router"] = {"status": "error", "critical": False, "error": str(e)}

    # Check Health Monitor
    try:
        health_monitor = getattr(request.app.state, "health_monitor", None)
        if health_monitor:
            services["health_monitor"] = {
                "status": "healthy",
                "critical": False,
                "details": {"running": getattr(health_monitor, "_running", False)},
            }
        else:
            services["health_monitor"] = {"status": "unavailable", "critical": False}
    except Exception as e:
        services["health_monitor"] = {"status": "error", "critical": False, "error": str(e)}

    # Get service registry status if available
    service_registry_status = None
    try:
        registry = getattr(request.app.state, "service_registry", None)
        if registry:
            service_registry_status = registry.get_status()
    except Exception as e:
        logger.warning(f"Failed to get service registry status: {e}")

    # Calculate overall status
    critical_services = ["search", "ai"]
    critical_healthy = all(
        services.get(s, {}).get("status") == "healthy" for s in critical_services
    )

    any_degraded = any(services.get(s, {}).get("status") != "healthy" for s in services)

    if not critical_healthy:
        overall_status = "critical"
    elif any_degraded:
        overall_status = "degraded"
    else:
        overall_status = "healthy"

    return {
        "status": overall_status,
        "services": services,
        "critical_services": critical_services,
        "registry": service_registry_status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "v100-qdrant",
    }


@router.get("/ready")
async def readiness_check(request: Request) -> dict[str, Any]:
    """
    Kubernetes-style readiness probe.

    Returns 200 only if critical services are ready to handle traffic.
    Used by load balancers to determine if instance should receive traffic.

    Returns:
        dict: Readiness status with critical service check
    """
    # Check critical services
    search_ready = getattr(request.app.state, "search_service", None) is not None
    ai_ready = getattr(request.app.state, "ai_client", None) is not None
    services_initialized = getattr(request.app.state, "services_initialized", False)

    is_ready = search_ready and ai_ready and services_initialized

    if not is_ready:
        from fastapi import HTTPException

        raise HTTPException(
            status_code=503,
            detail={
                "ready": False,
                "search_service": search_ready,
                "ai_client": ai_ready,
                "services_initialized": services_initialized,
            },
        )

    return {
        "ready": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/live")
async def liveness_check() -> dict[str, Any]:
    """
    Kubernetes-style liveness probe.

    Returns 200 if the application is running (even if not fully ready).
    Used by orchestrators to determine if instance needs restart.

    Returns:
        dict: Liveness status
    """
    return {
        "alive": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics/qdrant")
async def qdrant_metrics() -> dict[str, Any]:
    """
    Qdrant operation metrics for monitoring performance.

    Returns metrics including:
    - Search operation counts and average latency
    - Upsert operation counts and average latency
    - Document counts processed
    - Retry counts
    - Error counts
    """
    try:
        from core.qdrant_db import get_qdrant_metrics

        metrics = get_qdrant_metrics()
        return {
            "status": "ok",
            "metrics": metrics,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Failed to get Qdrant metrics: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# TEMPORARY debug endpoint removed - use /api/debug/state instead
# Configuration debugging is available via the debug router at /api/debug/state
# which requires authentication and is only available in development/staging
