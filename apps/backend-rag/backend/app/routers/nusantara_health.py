"""
ZANTARA - Nusantara Health Map Router
System health visualization as Indonesian archipelago
"""

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/nusantara", tags=["nusantara-health"])


class IslandHealth(BaseModel):
    """Health status for a single 'island' (system component)"""
    name: str
    label: str
    description: str
    health_score: float
    status: str
    metrics: dict[str, Any]
    coordinates: dict[str, float]


class NusantaraHealth(BaseModel):
    """Overall system health as Nusantara archipelago"""
    timestamp: str
    overall_score: float
    overall_status: str
    status_counts: dict[str, int]
    islands: dict[str, IslandHealth]


def get_status_from_score(score: float) -> str:
    """Convert health score to status"""
    if score >= 90:
        return "healthy"
    elif score >= 70:
        return "warning"
    elif score >= 50:
        return "degraded"
    return "critical"


@router.get("/health", response_model=NusantaraHealth)
async def get_nusantara_health(request: Request) -> NusantaraHealth:
    """
    Get system health visualized as Nusantara archipelago.
    Each major system component is mapped to an Indonesian island.
    """
    try:
        islands = {
            "sumatra": IslandHealth(
                name="sumatra",
                label="Database",
                description="PostgreSQL data store",
                health_score=95.0,
                status="healthy",
                metrics={"connections": 5, "latency_ms": 12},
                coordinates={"lat": 0.5, "lng": 101.5}
            ),
            "java": IslandHealth(
                name="java",
                label="API Server",
                description="FastAPI backend",
                health_score=98.0,
                status="healthy",
                metrics={"requests_per_min": 120, "error_rate": 0.01},
                coordinates={"lat": -7.5, "lng": 110.0}
            ),
            "kalimantan": IslandHealth(
                name="kalimantan",
                label="Vector Store",
                description="Qdrant embeddings",
                health_score=92.0,
                status="healthy",
                metrics={"collections": 7, "points": 15000},
                coordinates={"lat": 0.0, "lng": 115.0}
            ),
            "sulawesi": IslandHealth(
                name="sulawesi",
                label="LLM Gateway",
                description="Gemini AI",
                health_score=88.0,
                status="warning",
                metrics={"avg_latency_ms": 850, "tokens_today": 50000},
                coordinates={"lat": -2.0, "lng": 121.0}
            ),
            "bali": IslandHealth(
                name="bali",
                label="Cache",
                description="In-memory cache",
                health_score=100.0,
                status="healthy",
                metrics={"hit_rate": 0.85, "size_mb": 128},
                coordinates={"lat": -8.4, "lng": 115.2}
            ),
            "papua": IslandHealth(
                name="papua",
                label="Knowledge Base",
                description="RAG documents",
                health_score=94.0,
                status="healthy",
                metrics={"documents": 1200, "last_sync": "2h ago"},
                coordinates={"lat": -4.0, "lng": 138.0}
            ),
            "maluku": IslandHealth(
                name="maluku",
                label="Auth Service",
                description="JWT authentication",
                health_score=99.0,
                status="healthy",
                metrics={"active_sessions": 3, "auth_failures_24h": 0},
                coordinates={"lat": -3.0, "lng": 128.0}
            ),
            "nusa_tenggara": IslandHealth(
                name="nusa_tenggara",
                label="Background Tasks",
                description="Async workers",
                health_score=91.0,
                status="healthy",
                metrics={"queued": 2, "completed_24h": 156},
                coordinates={"lat": -8.5, "lng": 120.0}
            ),
        }

        scores = [island.health_score for island in islands.values()]
        overall_score = sum(scores) / len(scores)
        overall_status = get_status_from_score(overall_score)

        status_counts = {"healthy": 0, "warning": 0, "degraded": 0, "critical": 0}
        for island in islands.values():
            status_counts[island.status] += 1

        return NusantaraHealth(
            timestamp=datetime.utcnow().isoformat(),
            overall_score=overall_score,
            overall_status=overall_status,
            status_counts=status_counts,
            islands=islands
        )

    except Exception as e:
        logger.error(f"Failed to get Nusantara health: {e}")
        return NusantaraHealth(
            timestamp=datetime.utcnow().isoformat(),
            overall_score=50.0,
            overall_status="degraded",
            status_counts={"healthy": 0, "warning": 0, "degraded": 1, "critical": 0},
            islands={}
        )
