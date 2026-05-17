"""
ZANTARA RAG - Health Check Router

Provides health check endpoints for monitoring service status:
- /health - Basic health check for load balancers
- /health/detailed - Comprehensive service status for debugging
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Request, Response

from backend.app.core.config import settings
from backend.app.models import HealthResponse
from backend.core.collection_registry import SKILLS_MIRROR_COLLECTION

logger = logging.getLogger(__name__)

# P0-0: how long /health tolerates `startup_complete=False` before flipping to 503.
# Cold-start RAG warmup (Qdrant + embeddings + KG) is ~30-90s on Fly.io shared-2x;
# 180s gives generous headroom while still catching deadlocked init that would
# otherwise stay "initializing" indefinitely. Fly.io now caps health-check
# grace_period at 60s; this deadline is the app-level guard after boot starts.
STARTUP_WARMUP_DEADLINE_S = float(os.getenv("STARTUP_WARMUP_DEADLINE_S", "180"))


_qdrant_client: httpx.AsyncClient | None = None


def _build_skills_mirror_probe(
    live_counts: dict[str, int],
    freshness: dict[str, Any],
) -> dict[str, Any]:
    """Build a read-only health/drift probe for the skills mirror collection."""
    live_points = live_counts.get(SKILLS_MIRROR_COLLECTION)
    registered = SKILLS_MIRROR_COLLECTION in freshness
    issues: list[str] = []

    if not registered:
        issues.append("missing_from_collection_manager")
    if live_points is None:
        issues.append("missing_from_qdrant")
    elif live_points == 0:
        issues.append("empty_collection")

    if not registered:
        status = "registry_drift"
    elif live_points is None:
        status = "missing"
    elif live_points == 0:
        status = "empty"
    else:
        status = "ok"

    return {
        "collection": SKILLS_MIRROR_COLLECTION,
        "status": status,
        "registered": registered,
        "live_points": live_points,
        "issues": issues,
    }


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


def _check_startup_failed(app) -> dict[str, Any] | None:
    """Return error dict if startup failed, None otherwise."""
    if getattr(app.state, "startup_failed", False):
        return {
            "status": "startup_failed",
            "error": getattr(app.state, "startup_error", "Unknown"),
        }
    return None


def _check_warmup_timeout(app) -> dict[str, Any] | None:
    """P0-0: return error dict if startup is incomplete and the warmup deadline has passed.

    Cicatrix STRUCTURAL 2026-04-29 — without this check, an init that hangs
    (deadlocked DB pool, Qdrant retry loop, slow embedding load) keeps the
    backend in "initializing" forever and Fly.io never auto-restarts.

    Returns None when:
      - startup_complete is True (happy path)
      - startup_started_at is missing (older code path / process group)
      - we are still inside STARTUP_WARMUP_DEADLINE_S (legitimate warmup)
    """
    if getattr(app.state, "startup_complete", False):
        return None
    started_at = getattr(app.state, "startup_started_at", None)
    if started_at is None:
        return None
    elapsed = time.time() - started_at
    if elapsed <= STARTUP_WARMUP_DEADLINE_S:
        return None
    return {
        "status": "startup_timeout",
        "error": (
            f"startup_complete=False after {int(elapsed)}s "
            f"(deadline {int(STARTUP_WARMUP_DEADLINE_S)}s)"
        ),
        "elapsed_seconds": int(elapsed),
    }


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
                    # Update per-collection Prometheus gauge
                    try:
                        from backend.app.metrics import qdrant_collection_points_count
                        qdrant_collection_points_count.labels(collection=coll_name).set(points)
                    except Exception:
                        pass
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


def _check_resource_thresholds(process_mode: str | None) -> tuple[str | None, str | None]:
    """
    Check memory and disk thresholds for Fly.io health-based auto-restart.

    Returns (status_override, message) if thresholds exceeded, else (None, None).
    Only triggers unhealthy (→ auto-restart) on the rag process to avoid
    restarting the light api process for legitimate ML model memory usage.
    """
    try:
        import psutil as _psutil

        # Memory check — RAG process only (ML models legitimately use ~70-80%)
        if process_mode == "rag":
            vm = _psutil.virtual_memory()
            mem_pct = vm.percent
            if mem_pct >= 90:
                logger.warning(f"Memory critical: {mem_pct:.1f}% used — triggering unhealthy")
                return "unhealthy", f"Memory {mem_pct:.1f}% >= 90% threshold"
            if mem_pct >= 85:
                logger.warning(f"Memory high: {mem_pct:.1f}% used")
                # degraded but not unhealthy — still serves traffic

        # Disk check — /data volume (Fly.io persistent storage)
        try:
            disk = _psutil.disk_usage("/data")
            disk_pct = disk.percent
            if disk_pct >= 90:
                logger.warning(f"Disk /data critical: {disk_pct:.1f}% — triggering unhealthy")
                return "unhealthy", f"Disk /data {disk_pct:.1f}% >= 90% threshold"
            if disk_pct >= 80:
                logger.warning(f"Disk /data high: {disk_pct:.1f}%")
                return "degraded", f"Disk /data {disk_pct:.1f}% >= 80% threshold"
        except (FileNotFoundError, PermissionError):
            pass  # /data not mounted on this process — normal for api process

    except ImportError:
        pass  # psutil not available — skip resource checks

    return None, None


@router.get(
    "", response_model=HealthResponse,
)  # /health without trailing slash (for Fly.io health checks)
@router.get(
    "/", response_model=HealthResponse, include_in_schema=False,
)  # /health/ with trailing slash
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    System health check - Non-blocking during startup.

    Returns "initializing" immediately if service not ready.
    Prevents container crashes during warmup by not creating heavy objects.

    Resource thresholds (Fly.io auto-restart via HTTP 503 + unhealthy status):
    - Memory >90% (rag process only): HTTP 503, status="unhealthy"
    - Disk /data >90%: HTTP 503, status="unhealthy"
    - Disk /data >80%: HTTP 200, status="degraded"

    NOTE: Fly.io [[services.http_checks]] only restarts on non-2xx responses.
    Returning JSON {"status":"unhealthy"} with HTTP 200 does NOT trigger restart.
    We must return HTTP 503 to make Fly.io act.
    """
    try:
        # P0-0: surface app.state.startup_failed as HTTP 503 BEFORE any other branch.
        # _check_startup_failed already exists (lines 48-55); the bug fixed here
        # is that health_check never called it, so a deterministically-broken
        # backend reported HTTP 200 + status='healthy' indefinitely. Fly.io
        # auto-restart only fires on non-2xx, so without 503 the machine never
        # recycles. See cicatrix STRUCTURAL 2026-04-29 'Backend /health masks
        # app.state.startup_failed'.
        startup_err = _check_startup_failed(request.app)
        if startup_err is not None:
            response.status_code = 503
            return HealthResponse(
                status="unhealthy",
                version="v100-qdrant",
                database={
                    "status": "unknown",
                    "type": "postgresql",
                    "message": startup_err["error"],
                },
                embeddings={
                    "status": "unknown",
                    "message": startup_err["status"],
                },
            )

        # P0-0: also flip to 503 if startup is still incomplete past the warmup
        # deadline. Below the deadline we keep returning 200 with the existing
        # "initializing" body so Fly.io's 600s grace period still works for
        # legitimate cold starts.
        warmup_err = _check_warmup_timeout(request.app)
        if warmup_err is not None:
            response.status_code = 503
            return HealthResponse(
                status="unhealthy",
                version="v100-qdrant",
                database={
                    "status": "unknown",
                    "type": "postgresql",
                    "message": warmup_err["error"],
                },
                embeddings={
                    "status": "unknown",
                    "message": warmup_err["status"],
                },
            )

        process_mode = getattr(request.app.state, "process_mode", None)

        # Get search service from backend.app.state
        search_service = getattr(request.app.state, "search_service", None)

        # Light process (api) has search_service=None by design — report healthy
        # Heavy process (rag) without search_service is still warming up
        if not search_service:
            is_light_process = process_mode == "light"
            if is_light_process:
                # Still check resources even for light process (disk is shared)
                status_override, override_msg = _check_resource_thresholds(process_mode)
                if status_override == "unhealthy":
                    response.status_code = 503
                return HealthResponse(
                    status=status_override or "healthy",
                    version="v100-qdrant",
                    database={"status": "connected", "type": "postgresql"},
                    embeddings={
                        "status": "operational",
                        "model": "text-embedding-3-small",
                        "dimensions": 1536,
                        "note": override_msg or "RAG handled by rag process group",
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
            # Check resource thresholds (memory + disk) — may trigger Fly.io auto-restart
            status_override, override_msg = _check_resource_thresholds(process_mode)

            # Set HTTP 503 for "unhealthy" so Fly.io [[services.http_checks]] triggers restart.
            # Fly.io only restarts on non-2xx — a JSON field alone does nothing.
            if status_override == "unhealthy":
                response.status_code = 503

            # Update DB pool Prometheus gauges
            db_pool = getattr(request.app.state, "db_pool", None)
            if db_pool:
                try:
                    from backend.app.metrics import (
                        active_connections,
                        db_pool_idle,
                        db_pool_size,
                    )
                    pool_sz = db_pool.get_size()
                    idle_sz = db_pool.get_idle_size()
                    db_pool_size.labels(service="rag").set(pool_sz)
                    db_pool_idle.labels(service="rag").set(idle_sz)
                    active_connections.set(pool_sz - idle_sz)
                except Exception:
                    pass

            # Get model info without triggering heavy operations
            model_info = getattr(search_service.embedder, "model", "unknown")
            dimensions = getattr(search_service.embedder, "dimensions", 0)

            # Get real Qdrant stats
            qdrant_stats = await get_qdrant_stats()

            return HealthResponse(
                status=status_override or "healthy",
                version="v100-qdrant",
                database={
                    "status": "connected",
                    "type": "qdrant",
                    "collections": qdrant_stats.get("collections", 0),
                    "total_documents": qdrant_stats.get("total_documents", 0),
                    **({"resource_warning": override_msg} if override_msg else {}),
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


@router.get("/db")
async def db_health(request: Request) -> dict:
    """Database health summary from Olympus Guardian."""
    olympus = getattr(request.app.state, "olympus", None)
    if olympus is None:
        return {"status": "not_initialized", "detail": "Olympus Guardian not running"}
    return await olympus.get_health_summary()


@router.get("/collections")
async def collections_health(request: Request) -> dict[str, Any]:
    """
    Collection freshness and live point count for all Qdrant collections.

    Combines the CollectionManager's freshness tracking (last ingest timestamp)
    with live Qdrant point counts. Useful for monitoring data staleness.

    Returns:
        dict: Per-collection last_updated timestamp, age, and live point count
    """
    # Get freshness data from CollectionManager if available
    freshness: dict[str, Any] = {}
    try:
        search_service = getattr(request.app.state, "search_service", None)
        if search_service:
            collection_manager = getattr(search_service, "collection_manager", None)
            if collection_manager and hasattr(collection_manager, "get_collection_freshness"):
                freshness = collection_manager.get_collection_freshness()
    except Exception as e:
        logger.warning(f"Failed to get collection freshness: {e}")

    # Get live point counts from Qdrant
    qdrant_stats = await get_qdrant_stats()
    live_counts: dict[str, int] = {}
    try:
        client = _get_qdrant_client()
        response = await client.get("/collections")
        response.raise_for_status()
        collections_data = response.json().get("result", {}).get("collections", [])
        for coll in collections_data:
            coll_name = coll.get("name")
            if coll_name:
                try:
                    coll_response = await client.get(f"/collections/{coll_name}")
                    coll_response.raise_for_status()
                    points = coll_response.json().get("result", {}).get("points_count", 0)
                    live_counts[coll_name] = points
                except Exception:
                    pass
    except Exception as e:
        logger.warning(f"Failed to get live Qdrant counts: {e}")

    # Merge freshness + live counts
    collections: dict[str, Any] = {}
    all_names = set(freshness.keys()) | set(live_counts.keys())
    for name in sorted(all_names):
        entry: dict[str, Any] = {}
        if name in freshness:
            entry.update(freshness[name])
        entry["live_points"] = live_counts.get(name, None)
        collections[name] = entry

    return {
        "status": "ok",
        "total_collections": len(collections),
        "total_documents": qdrant_stats.get("total_documents", 0),
        "collections": collections,
        "skills_mirror": _build_skills_mirror_probe(live_counts, freshness),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/redis")
async def redis_health(request: Request) -> dict[str, Any]:
    """
    Redis memory health endpoint.

    Returns memory usage, eviction policy, evicted keys count, and connected clients.
    Used by monitoring to detect memory pressure before Redis starts evicting keys.

    Returns:
        dict: Redis memory health info
    """
    redis_manager = getattr(request.app.state, "redis_manager", None)
    if not redis_manager:
        return {
            "status": "unavailable",
            "detail": "RedisManager not initialized",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    mem_info = await redis_manager.get_redis_memory_info()

    # Determine status based on memory pressure
    status = "healthy"
    if mem_info.get("error"):
        status = "error"
    elif mem_info.get("maxmemory", 0) > 0:
        usage_ratio = mem_info["used_memory"] / mem_info["maxmemory"]
        if usage_ratio > 0.9:
            status = "critical"
        elif usage_ratio > 0.75:
            status = "warning"

    return {
        "status": status,
        "memory": {
            "used": mem_info.get("used_memory_human", "0B"),
            "used_bytes": mem_info.get("used_memory", 0),
            "max": mem_info.get("maxmemory_human", "0B"),
            "max_bytes": mem_info.get("maxmemory", 0),
            "policy": mem_info.get("maxmemory_policy", "unknown"),
        },
        "evicted_keys": mem_info.get("evicted_keys", 0),
        "connected_clients": mem_info.get("connected_clients", 0),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/metrics/prometheus", include_in_schema=False)
async def prometheus_metrics():
    """Prometheus text format metrics for external scraping (Grafana Cloud, Prometheus)."""
    from starlette.responses import Response

    from backend.app.metrics import generate_latest

    return Response(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
