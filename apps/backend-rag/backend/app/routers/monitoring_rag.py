"""
RAG Monitoring API Router

Provides REST endpoints for retrieval quality monitoring dashboard.
All endpoints require admin/founder access for security.

Endpoints:
- GET /api/monitoring/retrieval-quality - Current metrics snapshot
- GET /api/monitoring/scores-trend - Historical score trends
- GET /api/monitoring/abstain-rate - Abstain statistics
- GET /api/monitoring/latency - Latency percentiles
- POST /api/monitoring/alert-threshold - Configure alert thresholds
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from backend.app.dependencies import get_current_user
from backend.services.rag.evaluation.monitoring import (
    AlertThresholds,
    RetrievalQualityMonitor,
    get_retrieval_quality_monitor,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/monitoring", tags=["monitoring", "rag"])


# ============================================================================
# Pydantic Models
# ============================================================================


class AlertThresholdsRequest(BaseModel):
    """Request model for updating alert thresholds."""

    min_score: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum acceptable retrieval score (0.0-1.0)"
    )
    max_abstain_rate: float = Field(
        default=0.2, ge=0.0, le=1.0, description="Maximum acceptable abstain rate (0.0-1.0)"
    )
    max_latency_ms: float = Field(
        default=5000.0,
        ge=100.0,
        le=60000.0,
        description="Maximum acceptable latency in milliseconds",
    )
    min_cache_hit_rate: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Minimum acceptable cache hit rate (0.0-1.0)"
    )


class AlertThresholdsResponse(BaseModel):
    """Response model for alert thresholds."""

    min_score: float
    max_abstain_rate: float
    max_latency_ms: float
    min_cache_hit_rate: float
    updated_at: str


class RetrievalQualityResponse(BaseModel):
    """Response model for retrieval quality metrics."""

    time_range: str
    total_queries: int
    timestamp: str
    retrieval_quality: dict[str, Any]
    performance: dict[str, Any]
    usage_patterns: dict[str, Any]
    alerts: dict[str, Any]
    alert_thresholds: dict[str, float]


class ScoreTrendResponse(BaseModel):
    """Response model for score trends."""

    days: int
    trend: list[dict[str, Any]]


class AbstainStatisticsResponse(BaseModel):
    """Response model for abstain statistics."""

    period_days: int
    total_abstains: int
    total_queries: int
    abstain_rate: float
    by_reason: dict[str, int]
    daily_breakdown: list[dict[str, Any]]


class LatencyPercentilesResponse(BaseModel):
    """Response model for latency percentiles."""

    period_days: int
    total_queries: int
    percentiles: dict[str, float]
    min: float
    max: float
    avg: float


class ErrorResponse(BaseModel):
    """Error response model."""

    detail: str


# ============================================================================
# Authentication Helper
# ============================================================================


def verify_admin_access(current_user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
    """
    Verify that the user has admin or founder level access.

    Args:
        current_user: Current authenticated user

    Returns:
        User dict if authorized

    Raises:
        HTTPException: If user lacks required permissions
    """
    allowed_roles = ["admin", "Founder", "founder", "superuser"]
    user_role = current_user.get("role", "").lower()

    if user_role not in [r.lower() for r in allowed_roles]:
        logger.warning(
            f"Unauthorized access attempt to monitoring endpoint by user: {current_user.get('id')}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin or Founder role required for monitoring endpoints.",
        )

    return current_user


# ============================================================================
# API Endpoints
# ============================================================================


@router.get(
    "/retrieval-quality",
    response_model=RetrievalQualityResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get current retrieval quality metrics",
    description="Returns comprehensive retrieval quality metrics for the specified time range.",
)
async def get_retrieval_quality(
    time_range: str = Query(
        default="24h",
        pattern="^(1h|24h|1d|7d|30d)$",
        description="Time range for metrics aggregation",
    ),
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Get current retrieval quality metrics snapshot.

    - **time_range**: Time window for metrics (1h, 24h, 7d, 30d)

    Returns:
        Comprehensive metrics including scores, latency, cache rates, and alerts
    """
    try:
        logger.info(f"Retrieving quality metrics for time_range={time_range}")
        return await monitor.get_dashboard_data(time_range)

    except Exception as e:
        logger.error(f"Failed to retrieve quality metrics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve metrics: {str(e)}",
        ) from e


@router.get(
    "/scores-trend",
    response_model=ScoreTrendResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - Invalid days parameter"},
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get historical score trends",
    description="Returns daily score trends for the specified number of days.",
)
async def get_scores_trend(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to retrieve (1-30)"),
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Get historical score trends.

    - **days**: Number of days to analyze (1-30)

    Returns:
        Daily aggregated scores including average, p95, min, max
    """
    try:
        logger.info(f"Retrieving score trends for days={days}")
        trend = await monitor.get_scores_trend(days)
        return {
            "days": days,
            "trend": trend,
        }

    except Exception as e:
        logger.error(f"Failed to retrieve score trends: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve score trends: {str(e)}",
        ) from e


@router.get(
    "/abstain-rate",
    response_model=AbstainStatisticsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - Invalid days parameter"},
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get abstain rate statistics",
    description="Returns detailed statistics about ABSTAIN responses.",
)
async def get_abstain_statistics(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to analyze (1-30)"),
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Get abstain rate statistics.

    - **days**: Number of days to analyze (1-30)

    Returns:
        Abstain statistics including rate by reason and daily breakdown
    """
    try:
        logger.info(f"Retrieving abstain statistics for days={days}")
        return await monitor.get_abstain_statistics(days)

    except Exception as e:
        logger.error(f"Failed to retrieve abstain statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve abstain statistics: {str(e)}",
        ) from e


@router.get(
    "/latency",
    response_model=LatencyPercentilesResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - Invalid days parameter"},
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get latency percentile statistics",
    description="Returns detailed latency percentile breakdown.",
)
async def get_latency_percentiles(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to analyze (1-30)"),
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Get latency percentile statistics.

    - **days**: Number of days to analyze (1-30)

    Returns:
        Latency percentiles (p50, p75, p90, p95, p99, p99.9) plus min/max/avg
    """
    try:
        logger.info(f"Retrieving latency percentiles for days={days}")
        return await monitor.get_latency_percentiles(days)

    except Exception as e:
        logger.error(f"Failed to retrieve latency statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve latency statistics: {str(e)}",
        ) from e


@router.post(
    "/alert-threshold",
    response_model=AlertThresholdsResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request - Invalid threshold values"},
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Set alert thresholds",
    description="Configure alert thresholds for retrieval quality monitoring.",
)
async def set_alert_thresholds(
    thresholds: AlertThresholdsRequest,
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Set alert thresholds for monitoring.

    Configure thresholds for:
    - Minimum acceptable retrieval score
    - Maximum acceptable abstain rate
    - Maximum acceptable latency
    - Minimum acceptable cache hit rate

    When thresholds are breached, alerts are triggered in the dashboard.
    """
    try:
        logger.info(
            f"Updating alert thresholds by user {current_user.get('id')}: "
            f"min_score={thresholds.min_score}, "
            f"max_abstain_rate={thresholds.max_abstain_rate}"
        )

        new_thresholds = AlertThresholds(
            min_score=thresholds.min_score,
            max_abstain_rate=thresholds.max_abstain_rate,
            max_latency_ms=thresholds.max_latency_ms,
            min_cache_hit_rate=thresholds.min_cache_hit_rate,
        )

        monitor.set_alert_thresholds(new_thresholds)

        from datetime import datetime, timezone

        return {
            **new_thresholds.to_dict(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to set alert thresholds: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to set alert thresholds: {str(e)}",
        ) from e


@router.get(
    "/alert-threshold",
    response_model=AlertThresholdsResponse,
    responses={
        403: {"model": ErrorResponse, "description": "Forbidden - Admin access required"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
    summary="Get current alert thresholds",
    description="Returns the currently configured alert thresholds.",
)
async def get_alert_thresholds(
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
    current_user: dict[str, Any] = Depends(verify_admin_access),
) -> dict[str, Any]:
    """
    Get current alert threshold configuration.

    Returns:
        Current alert thresholds and last updated timestamp
    """
    try:
        thresholds = monitor.get_alert_thresholds()

        from datetime import datetime, timezone

        return {
            **thresholds.to_dict(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get alert thresholds: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert thresholds: {str(e)}",
        ) from e


@router.get(
    "/health",
    summary="Monitoring service health check",
    description="Returns health status of the monitoring service.",
)
async def health_check(
    monitor: RetrievalQualityMonitor = Depends(get_retrieval_quality_monitor),
) -> dict[str, Any]:
    """
    Health check endpoint for the monitoring service.

    Does not require authentication - useful for load balancers.

    Returns:
        Health status and basic service info
    """
    try:
        return {
            "status": "healthy",
            "service": "rag-monitoring",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Monitoring service unhealthy: {str(e)}",
        ) from e


# Import datetime for health check
from datetime import datetime, timezone
