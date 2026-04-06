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

from backend.app.core.config import settings
from backend.app.models import HealthResponse

logger = logging.getLogger(__name__)


_qdrant_client: httpx.AsyncClient | None = None


def _get_qdrant_client() -> httpx.AsyncClient:
    """Persistent httpx client for Qdrant health checks."""
    global _qdrant_client
    if _qdrant_client is None or _qdrant_client.is_closed:
        headers = {}
        if settings.qdrant_api_key:
            headers["api-key"] = settings.qdrant_api_key
        _qdrant_client = httpx.AsyncClient(
            base_url=settings.qdrant_url,
            headers=headers,
            timeout=5.0,
        )
    return _qdrant_client


async def close_qdrant_health_client() -> None:
    """Close the persistent Qdrant health check client."""
    global _qdrant_client
    if _qdrant_client and not _qdrant_client.is_closed:
        await _qdrant_client.aclose()
        _qdrant_client = None


async def get_qdrant_stats() -> dict[str, Any]:
    """
    Get real stats from Qdrant - collections count and total documents.
    """
    try:
        client = _get_qdrant_client()

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
                except Exception as coll_err:
                        logger.debug(f"Skip failed collection {coll_name}: {coll_err}")

            return {
                "collections": len(collections_data),
                "total_documents": total_documents,
            }
    except Exception as e:
        logger.warning(f"Failed to get Qdrant stats: {e}")
        return {"collections": 0, "total_documents": 0, "error": str(e)}


router = APIRouter(prefix="/health", tags=["health"])


@router.get(
    "", response_model=HealthResponse,
)  # /health without trailing slash (for Fly.io health checks)
@router.get(
    "/", response_model=HealthResponse, include_in_schema=False,
)  # /health/ with trailing slash
async def health_check(request: Request) -> HealthResponse:
    """
    System health check - Non-blocking during startup.

    Returns "initializing" immediately if service not ready.
    Prevents container crashes during warmup by not creating heavy objects.
    """
    try:
        # Get search service from backend.app.state
        search_service = getattr(request.app.state, "search_service", None)

        # Light process (api) has search_service=None by design — report healthy
        # Heavy process (rag) without search_service is still warming up
        if not search_service:
            is_light_process = getattr(request.app.state, "process_mode", None) == "light"
            if is_light_process:
                return HealthResponse(
                    status="healthy",
                    version="v100-qdrant",
                    database={"status": "connected", "type": "postgresql"},
                    embeddings={
                        "status": "operational",
                        "model": "text-embedding-3-small",
                        "dimensions": 1536,
                        "note": "RAG handled by rag process group",
                    },
                )
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
                "critical": True,
                "details": {"type": type(router_instance).__name__},
            }
        else:
            services["router"] = {"status": "unavailable", "critical": True}
    except Exception as e:
        services["router"] = {"status": "error", "critical": True, "error": str(e)}

    # Check Health Monitor
    try:
        health_monitor = getattr(request.app.state, "health_monitor", None)
        if health_monitor:
            # Use public get_status method which checks task liveness
            monitor_status = health_monitor.get_status()
            services["health_monitor"] = {
                "status": "healthy",
                "critical": False,
                "details": monitor_status,
            }
        else:
            services["health_monitor"] = {"status": "unavailable", "critical": False}
    except Exception as e:
        services["health_monitor"] = {"status": "error", "critical": False, "error": str(e)}

    # Check Query Cache
    try:
        from backend.core.cache import get_cache_service

        cache_stats = get_cache_service().get_stats()
        services["query_cache"] = {
            "status": "healthy",
            "critical": False,
            "details": cache_stats,
        }
    except Exception as e:
        services["query_cache"] = {"status": "unavailable", "critical": False, "error": str(e)}

    # Check Rate Limiter
    try:
        from backend.middleware.rate_limiter import get_rate_limit_stats

        rl_stats = get_rate_limit_stats()
        services["rate_limiter"] = {
            "status": "healthy",
            "critical": False,
            "details": rl_stats,
        }
    except Exception as e:
        services["rate_limiter"] = {"status": "unavailable", "critical": False, "error": str(e)}

    # Check Redis (via RedisManager)
    try:
        redis_manager = getattr(request.app.state, "redis_manager", None)
        if redis_manager:
            redis_health = await redis_manager.health_check()
            services["redis"] = {
                "status": "healthy" if redis_health.get("connected") else "unavailable",
                "critical": False,
                "details": {
                    "connected": redis_health.get("connected", False),
                    "latency_ms": redis_health.get("latency_ms", -1),
                    "keys": redis_health.get("keys", 0),
                    "memory_used": redis_health.get("memory_used", "0B"),
                    "components": redis_health.get("components", {}),
                },
            }
        else:
            services["redis"] = {
                "status": "unavailable",
                "critical": False,
                "details": {"reason": "RedisManager not initialized"},
            }
    except Exception as e:
        services["redis"] = {"status": "error", "critical": False, "error": str(e)}

    # Get service registry status if available
    service_registry_status = None
    try:
        registry = getattr(request.app.state, "service_registry", None)
        if registry:
            service_registry_status = registry.get_status()
    except Exception as e:
        logger.warning(f"Failed to get service registry status: {e}")

    # Check KG LangGraph Orchestrator (Phase 3)
    try:
        import os

        kg_langgraph_enabled = os.getenv("ENABLE_KG_LANGGRAPH", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        # Get orchestrator from global instance if available
        from backend.app.dependencies import _agentic_rag_orchestrator

        if _agentic_rag_orchestrator and hasattr(
            _agentic_rag_orchestrator, "kg_langgraph_orchestrator",
        ):
            kg_orchestrator = _agentic_rag_orchestrator.kg_langgraph_orchestrator
            if kg_orchestrator:
                services["kg_langgraph"] = {
                    "status": "healthy",
                    "critical": False,
                    "details": {
                        "enabled": True,
                        "initialized": kg_orchestrator.app is not None,
                    },
                }
            else:
                services["kg_langgraph"] = {
                    "status": "disabled",
                    "critical": False,
                    "details": {
                        "enabled": False,
                        "reason": "ENABLE_KG_LANGGRAPH=false or db_pool missing",
                    },
                }
        else:
            # Orchestrator not yet created (lazy-init on first query)
            if kg_langgraph_enabled:
                services["kg_langgraph"] = {
                    "status": "pending_first_query",
                    "critical": False,
                    "details": {
                        "enabled": True,
                        "reason": "Lazy-init: orchestrator will initialize on first query",
                    },
                }
            else:
                services["kg_langgraph"] = {
                    "status": "disabled",
                    "critical": False,
                    "details": {
                        "enabled": False,
                        "reason": "ENABLE_KG_LANGGRAPH=false",
                    },
                }
    except Exception as e:
        services["kg_langgraph"] = {"status": "error", "critical": False, "error": str(e)}

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
    # Light process (api): ready when db_pool is available
    is_light = getattr(request.app.state, "process_mode", None) == "light"
    if is_light:
        db_ready = getattr(request.app.state, "db_pool", None) is not None
        if not db_ready:
            from fastapi import HTTPException

            raise HTTPException(
                status_code=503,
                detail={"ready": False, "process": "light", "db_pool": False},
            )
        return {
            "ready": True,
            "process": "light",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Heavy process (rag): ready when critical services are initialized
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
                "process": "rag",
                "search_service": search_ready,
                "ai_client": ai_ready,
                "services_initialized": services_initialized,
            },
        )

    return {
        "ready": True,
        "process": "rag",
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
        from backend.core.qdrant_db import get_qdrant_metrics

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


@router.get("/kg-stats")
async def knowledge_graph_stats(request: Request) -> dict[str, Any]:
    """
    Knowledge Graph statistics for auditing and monitoring.

    Returns:
        dict: KG statistics including node/edge counts and distributions
    """
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if not db_pool:
            return {
                "status": "error",
                "error": "Database pool not available",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        async with db_pool.acquire() as conn:
            # Total counts
            nodes = await conn.fetchval("SELECT COUNT(*) FROM kg_nodes")
            edges = await conn.fetchval("SELECT COUNT(*) FROM kg_edges")

            # By collection
            by_coll = await conn.fetch("""
                SELECT source_collection, COUNT(*) as count
                FROM kg_nodes
                GROUP BY source_collection
                ORDER BY count DESC
            """)

            # By entity type
            by_type = await conn.fetch("""
                SELECT entity_type, COUNT(*) as count
                FROM kg_nodes
                GROUP BY entity_type
                ORDER BY count DESC
                LIMIT 15
            """)

            # By relationship type
            by_rel = await conn.fetch("""
                SELECT relationship_type, COUNT(*) as count
                FROM kg_edges
                GROUP BY relationship_type
                ORDER BY count DESC
                LIMIT 15
            """)

            # KBLI nodes
            kbli_nodes = await conn.fetchval(
                "SELECT COUNT(*) FROM kg_nodes WHERE entity_id LIKE 'kbli:%'",
            )

            # Perizinan nodes
            perizinan_nodes = await conn.fetchval(
                "SELECT COUNT(*) FROM kg_nodes WHERE entity_type = 'perizinan'",
            )

            # Orphan nodes
            orphans = await conn.fetchval("""
                SELECT COUNT(*) FROM kg_nodes n
                WHERE NOT EXISTS (
                    SELECT 1 FROM kg_edges e
                    WHERE e.source_entity_id = n.entity_id
                       OR e.target_entity_id = n.entity_id
                )
            """)

            # Connectivity
            connected = nodes - orphans
            connectivity_pct = (connected / nodes * 100) if nodes > 0 else 0
            avg_edges_per_node = (edges / nodes) if nodes > 0 else 0

            return {
                "status": "ok",
                "summary": {
                    "total_nodes": nodes,
                    "total_edges": edges,
                    "connected_nodes": connected,
                    "orphan_nodes": orphans,
                    "connectivity_pct": round(connectivity_pct, 1),
                    "avg_edges_per_node": round(avg_edges_per_node, 1),
                    "kbli_nodes": kbli_nodes,
                    "perizinan_nodes": perizinan_nodes,
                },
                "nodes_by_collection": [
                    {"collection": row["source_collection"] or "NULL", "count": row["count"]}
                    for row in by_coll
                ],
                "top_entity_types": [
                    {"entity_type": row["entity_type"], "count": row["count"]} for row in by_type
                ],
                "top_relationship_types": [
                    {"relationship_type": row["relationship_type"], "count": row["count"]}
                    for row in by_rel
                ],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    except Exception as e:
        logger.error(f"Failed to get KG stats: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


@router.get("/metrics/summary")
async def metrics_summary(request: Request) -> dict[str, Any]:
    """
    Human-readable JSON metrics summary for debugging and MCP tools.

    Aggregates the most important Prometheus metrics into a single JSON response.
    Unlike /metrics (Prometheus text format), this is designed for:
    - curl debugging
    - MCP check_health_detailed
    - Dashboard quick-glance

    Returns:
        dict: Top-level system, RAG, cache, AI, and resource metrics
    """
    import time as time_mod

    import psutil as _psutil

    from backend.app.metrics import (
        BOOT_TIME,
    )

    now = datetime.now(timezone.utc)
    uptime_seconds = time_mod.time() - BOOT_TIME

    # Resource snapshot
    process = _psutil.Process()
    mem_info = process.memory_info()
    rss_mb = mem_info.rss / (1024 * 1024)

    # DB pool
    db_pool_info = {}
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool:
        try:
            db_pool_info = {
                "size": db_pool.get_size(),
                "max_size": db_pool.get_max_size(),
                "idle": db_pool.get_idle_size(),
                "saturation_pct": round((db_pool.get_size() / db_pool.get_max_size()) * 100, 1)
                if db_pool.get_max_size() > 0
                else 0,
            }
        except Exception:
            db_pool_info = {"error": "unavailable"}

    # Health monitor status
    health_monitor_info = {}
    health_monitor = getattr(request.app.state, "health_monitor", None)
    if health_monitor:
        try:
            hm_status = health_monitor.get_status()
            health_monitor_info = {
                "running": hm_status.get("running", False),
                "services": hm_status.get("last_status", {}),
                "resources": hm_status.get("resources", {}),
            }
        except Exception:
            health_monitor_info = {"error": "unavailable"}

    # Alert service channels
    alert_channels = {}
    try:
        from backend.services.monitoring.alert_service import get_alert_service

        alert_svc = get_alert_service()
        alert_channels = {
            "telegram": alert_svc.enable_telegram,
            "slack": alert_svc.enable_slack,
            "discord": alert_svc.enable_discord,
            "logging": True,
        }
    except Exception:
        alert_channels = {"error": "unavailable"}

    # Qdrant stats (cached — reuse from health check)
    qdrant_info = await get_qdrant_stats()

    return {
        "status": "ok",
        "timestamp": now.isoformat(),
        "system": {
            "uptime_seconds": round(uptime_seconds, 0),
            "uptime_human": _format_uptime(uptime_seconds),
            "memory_rss_mb": round(rss_mb, 1),
            "cpu_percent": process.cpu_percent(interval=None),
            "pid": process.pid,
        },
        "database": {
            "pool": db_pool_info,
        },
        "vector_db": {
            "collections": qdrant_info.get("collections", 0),
            "total_documents": qdrant_info.get("total_documents", 0),
        },
        "monitoring": {
            "health_monitor": health_monitor_info,
            "alert_channels": alert_channels,
            "latency_threshold_ms": settings.latency_alert_threshold_ms,
            "memory_threshold_pct": settings.memory_alert_threshold_percent,
        },
        "config": {
            "embedding_model": "text-embedding-3-small",
            "version": "v100-qdrant",
        },
    }


def _format_uptime(seconds: float) -> str:
    """Format uptime seconds into human-readable string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
