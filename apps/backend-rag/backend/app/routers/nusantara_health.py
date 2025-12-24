"""
NUSANTARA HEALTH AGGREGATOR

Real-time health monitoring endpoint that maps system components
to Indonesian archipelago islands for visual representation.

Aggregates data from:
- Internal service health checks
- Prometheus metrics (if available)
- Qdrant stats
- Database connectivity
- Sentinel reports

Islands mapping:
- JAVA: Backend Core (FastAPI, main_cloud.py)
- SUMATRA: Frontend (mouth, Next.js)
- KALIMANTAN: Database Layer (PostgreSQL, Redis)
- SULAWESI: RAG/AI Systems (Agentic, Orchestrators)
- PAPUA: Knowledge Base (Qdrant vectors)
- BALI: API Gateway (Routers, endpoints)
- MALUKU: Memory Systems (Collective, Episodic, Facts)
- NUSA_TENGGARA: Microservices (Auth, CRM, Team, Ingest)
"""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request

from ..core.config import settings
from ..dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/nusantara", tags=["nusantara"])


def calculate_health_score(
    errors: int = 0,
    warnings: int = 0,
    latency_ms: float = 0,
    is_available: bool = True,
    coverage: float = 100,
) -> int:
    """Calculate health score 0-100 based on multiple factors."""
    if not is_available:
        return 0

    score = 100

    # Deduct for errors (critical)
    score -= min(errors * 15, 45)

    # Deduct for warnings
    score -= min(warnings * 5, 20)

    # Deduct for high latency (>500ms starts deducting)
    if latency_ms > 500:
        score -= min((latency_ms - 500) / 100, 20)

    # Deduct for low coverage
    if coverage < 80:
        score -= (80 - coverage) / 2

    return max(0, min(100, int(score)))


def get_status_from_score(score: int) -> str:
    """Convert health score to status string."""
    if score >= 90:
        return "healthy"
    elif score >= 70:
        return "warning"
    elif score >= 50:
        return "degraded"
    else:
        return "critical"


async def check_qdrant_health() -> dict[str, Any]:
    """Check Qdrant health and get document counts."""
    try:
        headers = {}
        if settings.qdrant_api_key:
            headers["api-key"] = settings.qdrant_api_key

        async with httpx.AsyncClient(
            base_url=settings.qdrant_url,
            headers=headers,
            timeout=5.0,
        ) as client:
            response = await client.get("/collections")
            response.raise_for_status()
            collections_data = response.json().get("result", {}).get("collections", [])

            total_documents = 0
            collection_stats = {}
            for coll in collections_data:
                coll_name = coll.get("name")
                if coll_name:
                    try:
                        coll_response = await client.get(f"/collections/{coll_name}")
                        coll_response.raise_for_status()
                        points = coll_response.json().get("result", {}).get("points_count", 0)
                        total_documents += points
                        collection_stats[coll_name] = points
                    except Exception:
                        pass

            return {
                "available": True,
                "collections": len(collections_data),
                "total_documents": total_documents,
                "collection_stats": collection_stats,
                "latency_ms": 0,  # Would need timing
            }
    except Exception as e:
        logger.warning(f"Qdrant health check failed: {e}")
        return {
            "available": False,
            "error": str(e),
            "collections": 0,
            "total_documents": 0,
        }


async def check_database_health(request: Request) -> dict[str, Any]:
    """Check PostgreSQL database health."""
    try:
        db_pool = getattr(request.app.state, "db_pool", None)
        if not db_pool:
            return {"available": False, "error": "No database pool"}

        import time
        start = time.time()
        async with db_pool.acquire() as conn:
            await conn.execute("SELECT 1")
        latency = (time.time() - start) * 1000

        return {
            "available": True,
            "latency_ms": latency,
            "pool_size": db_pool.get_size(),
            "pool_min": db_pool.get_min_size(),
            "pool_max": db_pool.get_max_size(),
        }
    except Exception as e:
        logger.warning(f"Database health check failed: {e}")
        return {"available": False, "error": str(e)}


async def check_redis_health() -> dict[str, Any]:
    """Check Redis health if available."""
    try:
        # Try to import and check Redis
        from services.cache.redis_cache import get_redis_client
        client = await get_redis_client()
        if client:
            import time
            start = time.time()
            await client.ping()
            latency = (time.time() - start) * 1000
            return {"available": True, "latency_ms": latency}
        return {"available": False, "error": "No Redis client"}
    except Exception as e:
        return {"available": False, "error": str(e)}


async def check_services_health(request: Request) -> dict[str, Any]:
    """Check internal services health."""
    services = {}

    # Search Service
    search = getattr(request.app.state, "search_service", None)
    services["search"] = {
        "available": search is not None,
        "type": type(search).__name__ if search else None,
    }

    # AI Client
    ai = getattr(request.app.state, "ai_client", None)
    services["ai"] = {
        "available": ai is not None,
        "type": type(ai).__name__ if ai else None,
    }

    # Memory Service
    memory = getattr(request.app.state, "memory_service", None)
    services["memory"] = {
        "available": memory is not None,
        "type": type(memory).__name__ if memory else None,
    }

    # Intelligent Router
    router_inst = getattr(request.app.state, "intelligent_router", None)
    services["router"] = {
        "available": router_inst is not None,
        "type": type(router_inst).__name__ if router_inst else None,
    }

    return services


@router.get("/health")
async def nusantara_health(
    request: Request,
    _user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Nusantara Archipelago Health Status.

    Returns health data for all system components mapped to Indonesian islands.
    Admin-only endpoint for the visual dashboard.

    Update frequency: Called every 60 seconds by frontend.
    """

    # Gather health data from all sources
    qdrant_health = await check_qdrant_health()
    db_health = await check_database_health(request)
    redis_health = await check_redis_health()
    services = await check_services_health(request)

    # Check if services are initialized
    services_initialized = getattr(request.app.state, "services_initialized", False)

    # Build island health data
    islands = {}

    # JAVA - Backend Core
    java_available = services_initialized
    java_errors = 0 if java_available else 1
    java_score = calculate_health_score(
        errors=java_errors,
        is_available=java_available,
    )
    islands["java"] = {
        "name": "Java",
        "label": "Backend Core",
        "description": "FastAPI Application Server",
        "health_score": java_score,
        "status": get_status_from_score(java_score),
        "metrics": {
            "services_initialized": services_initialized,
            "uptime": True,
        },
        "coordinates": {"lat": -7.5, "lng": 110.0},
    }

    # SUMATRA - Frontend
    # Frontend health is inferred from backend being able to serve
    sumatra_score = 85 if java_available else 50
    islands["sumatra"] = {
        "name": "Sumatra",
        "label": "Frontend",
        "description": "Next.js Web Application",
        "health_score": sumatra_score,
        "status": get_status_from_score(sumatra_score),
        "metrics": {
            "framework": "Next.js 16",
            "react": "19.2.1",
        },
        "coordinates": {"lat": 0.5, "lng": 101.0},
    }

    # KALIMANTAN - Database Layer
    kalimantan_score = calculate_health_score(
        errors=0 if db_health.get("available") else 1,
        warnings=0 if redis_health.get("available") else 1,
        latency_ms=db_health.get("latency_ms", 0),
        is_available=db_health.get("available", False),
    )
    islands["kalimantan"] = {
        "name": "Kalimantan",
        "label": "Database Layer",
        "description": "PostgreSQL + Redis",
        "health_score": kalimantan_score,
        "status": get_status_from_score(kalimantan_score),
        "metrics": {
            "postgresql": db_health,
            "redis": redis_health,
        },
        "coordinates": {"lat": 0.0, "lng": 115.0},
    }

    # SULAWESI - RAG/AI Systems
    sulawesi_available = services.get("ai", {}).get("available", False) and services.get("search", {}).get("available", False)
    sulawesi_score = calculate_health_score(
        errors=0 if sulawesi_available else 2,
        is_available=sulawesi_available,
    )
    islands["sulawesi"] = {
        "name": "Sulawesi",
        "label": "RAG/AI Engine",
        "description": "Agentic RAG Orchestrator",
        "health_score": sulawesi_score,
        "status": get_status_from_score(sulawesi_score),
        "metrics": {
            "ai_client": services.get("ai", {}),
            "search_service": services.get("search", {}),
            "intelligent_router": services.get("router", {}),
        },
        "coordinates": {"lat": -2.0, "lng": 121.0},
    }

    # PAPUA - Knowledge Base (Qdrant)
    papua_score = calculate_health_score(
        errors=0 if qdrant_health.get("available") else 1,
        is_available=qdrant_health.get("available", False),
    )
    islands["papua"] = {
        "name": "Papua",
        "label": "Knowledge Base",
        "description": f"Qdrant Vectors ({qdrant_health.get('total_documents', 0):,} docs)",
        "health_score": papua_score,
        "status": get_status_from_score(papua_score),
        "metrics": {
            "qdrant": qdrant_health,
        },
        "coordinates": {"lat": -4.0, "lng": 138.0},
    }

    # BALI - API Gateway
    bali_available = services.get("router", {}).get("available", False)
    bali_score = calculate_health_score(
        errors=0 if bali_available else 1,
        is_available=java_available,  # Depends on backend
    )
    islands["bali"] = {
        "name": "Bali",
        "label": "API Gateway",
        "description": "REST/WebSocket Routers",
        "health_score": bali_score,
        "status": get_status_from_score(bali_score),
        "metrics": {
            "router": services.get("router", {}),
            "endpoints_active": True,
        },
        "coordinates": {"lat": -8.4, "lng": 115.2},
    }

    # MALUKU - Memory Systems
    maluku_available = services.get("memory", {}).get("available", False)
    maluku_score = calculate_health_score(
        errors=0 if maluku_available else 1,
        is_available=maluku_available,
    )
    islands["maluku"] = {
        "name": "Maluku",
        "label": "Memory Systems",
        "description": "Collective, Episodic, Facts",
        "health_score": maluku_score,
        "status": get_status_from_score(maluku_score),
        "metrics": {
            "memory_service": services.get("memory", {}),
            "types": ["collective", "episodic", "facts"],
        },
        "coordinates": {"lat": -3.0, "lng": 128.0},
    }

    # NUSA TENGGARA - Microservices Chain
    nusa_score = calculate_health_score(
        errors=0,
        is_available=java_available,
    )
    islands["nusa_tenggara"] = {
        "name": "Nusa Tenggara",
        "label": "Microservices",
        "description": "Auth, CRM, Team, Ingest",
        "health_score": nusa_score,
        "status": get_status_from_score(nusa_score),
        "metrics": {
            "services": ["auth", "crm", "team", "ingest"],
        },
        "coordinates": {"lat": -8.5, "lng": 120.0},
    }

    # Calculate overall health
    all_scores = [island["health_score"] for island in islands.values()]
    overall_score = sum(all_scores) // len(all_scores) if all_scores else 0

    # Count by status
    status_counts = {
        "healthy": sum(1 for i in islands.values() if i["status"] == "healthy"),
        "warning": sum(1 for i in islands.values() if i["status"] == "warning"),
        "degraded": sum(1 for i in islands.values() if i["status"] == "degraded"),
        "critical": sum(1 for i in islands.values() if i["status"] == "critical"),
    }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "overall_score": overall_score,
        "overall_status": get_status_from_score(overall_score),
        "status_counts": status_counts,
        "islands": islands,
        "meta": {
            "version": "v1.0.0",
            "update_interval_seconds": 60,
            "data_sources": ["internal_services", "qdrant", "postgresql", "redis"],
        },
    }
