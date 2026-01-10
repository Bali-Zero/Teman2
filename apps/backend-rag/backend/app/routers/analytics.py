"""
Analytics Router
Provides comprehensive analytics endpoints for the Founder dashboard.
Access restricted to zero@balizero.com only.
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend.app.dependencies import get_current_user
from backend.app.utils.crm_utils import is_super_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


class AnalyticsUser(BaseModel):
    """User model for analytics access"""

    email: str
    name: str | None = None


def verify_founder_access(user: dict = Depends(get_current_user)) -> dict:
    """
    Verify that the current user is the Founder.

    Args:
        user: Current authenticated user from JWT

    Returns:
        User dict if authorized

    Raises:
        HTTPException: 403 if not the Founder
    """
    if not is_super_admin(user):
        logger.warning(f"Analytics access denied for {user.get('email')}")
        raise HTTPException(
            status_code=403, detail="Analytics dashboard is restricted to the Founder only"
        )
    return user


# ============================================================================
# OVERVIEW ENDPOINT
# ============================================================================


class OverviewStats(BaseModel):
    """Overview statistics"""

    conversations_today: int = 0
    conversations_week: int = 0
    users_active: int = 0
    error_rate: float = 0.0
    uptime_seconds: float = 0.0
    revenue_pipeline: float = 0.0
    services_healthy: int = 0
    services_total: int = 0


@router.get("/overview", response_model=OverviewStats)
async def get_overview(
    request: Request, user: dict = Depends(verify_founder_access)
) -> OverviewStats:
    """Get overview statistics for the dashboard"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_overview_stats()


# ============================================================================
# RAG PIPELINE ENDPOINT
# ============================================================================


class RAGStats(BaseModel):
    """RAG pipeline statistics"""

    avg_latency_ms: float = 0.0
    embedding_latency_ms: float = 0.0
    search_latency_ms: float = 0.0
    rerank_latency_ms: float = 0.0
    llm_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    token_usage_today: int = 0
    queries_today: int = 0
    top_queries: list[dict] = []
    early_exit_rate: float = 0.0


@router.get("/rag", response_model=RAGStats)
async def get_rag_stats(request: Request, user: dict = Depends(verify_founder_access)) -> RAGStats:
    """Get RAG pipeline statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_rag_stats()


# ============================================================================
# CRM ENDPOINT
# ============================================================================


class CRMStats(BaseModel):
    """CRM statistics"""

    clients_total: int = 0
    clients_active: int = 0
    clients_by_status: dict[str, int] = {}
    practices_total: int = 0
    practices_by_status: dict[str, int] = {}
    revenue_quoted: float = 0.0
    revenue_paid: float = 0.0
    renewals_30_days: int = 0
    renewals_60_days: int = 0
    renewals_90_days: int = 0
    documents_pending: int = 0


@router.get("/crm", response_model=CRMStats)
async def get_crm_stats(request: Request, user: dict = Depends(verify_founder_access)) -> CRMStats:
    """Get CRM statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_crm_stats()


# ============================================================================
# TEAM ENDPOINT
# ============================================================================


class TeamStats(BaseModel):
    """Team productivity statistics"""

    hours_today: float = 0.0
    hours_week: float = 0.0
    conversations_by_agent: dict[str, int] = {}
    productivity_scores: dict[str, float] = {}
    active_sessions: int = 0
    action_items_open: int = 0


@router.get("/team", response_model=TeamStats)
async def get_team_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> TeamStats:
    """Get team productivity statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_team_stats()


# ============================================================================
# SYSTEM HEALTH ENDPOINT
# ============================================================================


class SystemStats(BaseModel):
    """System health statistics"""

    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    memory_percent: float = 0.0
    db_connections_active: int = 0
    db_connections_idle: int = 0
    response_time_p50: float = 0.0
    response_time_p95: float = 0.0
    response_time_p99: float = 0.0
    requests_per_minute: float = 0.0
    error_rate_percent: float = 0.0
    services: list[dict] = []


@router.get("/system", response_model=SystemStats)
async def get_system_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> SystemStats:
    """Get system health statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_system_stats()


# ============================================================================
# QDRANT ENDPOINT
# ============================================================================


class QdrantStats(BaseModel):
    """Qdrant vector database statistics"""

    total_documents: int = 0
    collections: list[dict] = []
    search_latency_avg_ms: float = 0.0
    search_operations_today: int = 0
    upsert_operations_today: int = 0
    error_count: int = 0


@router.get("/qdrant", response_model=QdrantStats)
async def get_qdrant_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> QdrantStats:
    """Get Qdrant vector database statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_qdrant_stats()


# ============================================================================
# FEEDBACK ENDPOINT
# ============================================================================


class FeedbackStats(BaseModel):
    """Feedback and quality statistics"""

    avg_rating: float = 0.0
    rating_distribution: dict[str, int] = {}
    total_ratings: int = 0
    negative_feedback_count: int = 0
    recent_negative_feedback: list[dict] = []
    quality_trend: list[dict] = []


@router.get("/feedback", response_model=FeedbackStats)
async def get_feedback_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> FeedbackStats:
    """Get feedback and quality statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_feedback_stats()


# ============================================================================
# LLM TOKEN USAGE ENDPOINT
# ============================================================================


class LLMUsageStats(BaseModel):
    """LLM token usage and cost statistics"""

    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    usage_by_model: list[dict] = []
    usage_by_endpoint: list[dict] = []
    daily_trend: list[dict] = []
    generated_at: str = ""


@router.get("/llm-usage", response_model=LLMUsageStats)
async def get_llm_usage_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> LLMUsageStats:
    """Get detailed LLM token usage and cost statistics.

    This endpoint provides:
    - Total tokens used (prompt + completion)
    - Total cost in USD
    - Breakdown by model
    - Breakdown by endpoint
    - Daily trend data
    """
    from datetime import datetime, timezone

    from prometheus_client import REGISTRY

    # Extract metrics from Prometheus registry
    usage_by_model: dict[str, dict] = {}
    usage_by_endpoint: dict[str, dict] = {}
    total_prompt = 0
    total_completion = 0
    total_cost = 0.0

    try:
        # Get all metrics from the registry
        for metric in REGISTRY.collect():
            # llm_prompt_tokens_total
            if metric.name == "zantara_llm_prompt_tokens_total":
                for sample in metric.samples:
                    if sample.name.endswith("_total"):
                        model = sample.labels.get("model", "unknown")
                        endpoint = sample.labels.get("endpoint", "unknown")
                        value = int(sample.value)
                        total_prompt += value

                        if model not in usage_by_model:
                            usage_by_model[model] = {
                                "model": model,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "cost_usd": 0.0,
                            }
                        usage_by_model[model]["prompt_tokens"] += value

                        if endpoint not in usage_by_endpoint:
                            usage_by_endpoint[endpoint] = {
                                "endpoint": endpoint,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                            }
                        usage_by_endpoint[endpoint]["prompt_tokens"] += value

            # llm_completion_tokens_total
            elif metric.name == "zantara_llm_completion_tokens_total":
                for sample in metric.samples:
                    if sample.name.endswith("_total"):
                        model = sample.labels.get("model", "unknown")
                        endpoint = sample.labels.get("endpoint", "unknown")
                        value = int(sample.value)
                        total_completion += value

                        if model not in usage_by_model:
                            usage_by_model[model] = {
                                "model": model,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "cost_usd": 0.0,
                            }
                        usage_by_model[model]["completion_tokens"] += value

                        if endpoint not in usage_by_endpoint:
                            usage_by_endpoint[endpoint] = {
                                "endpoint": endpoint,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                            }
                        usage_by_endpoint[endpoint]["completion_tokens"] += value

            # llm_cost_usd_total
            elif metric.name == "zantara_llm_cost_usd_total":
                for sample in metric.samples:
                    if sample.name.endswith("_total"):
                        model = sample.labels.get("model", "unknown")
                        value = float(sample.value)
                        total_cost += value

                        if model not in usage_by_model:
                            usage_by_model[model] = {
                                "model": model,
                                "prompt_tokens": 0,
                                "completion_tokens": 0,
                                "cost_usd": 0.0,
                            }
                        usage_by_model[model]["cost_usd"] += value

    except Exception as e:
        logger.warning(f"Failed to collect LLM metrics: {e}")

    return LLMUsageStats(
        total_prompt_tokens=total_prompt,
        total_completion_tokens=total_completion,
        total_tokens=total_prompt + total_completion,
        total_cost_usd=round(total_cost, 6),
        usage_by_model=list(usage_by_model.values()),
        usage_by_endpoint=list(usage_by_endpoint.values()),
        daily_trend=[],  # Would need time-series DB for this
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


# ============================================================================
# ALERTS ENDPOINT
# ============================================================================


class AlertStats(BaseModel):
    """Alert and error statistics"""

    active_alerts: list[dict] = []
    recent_errors: list[dict] = []
    slow_queries: list[dict] = []
    auth_failures_today: int = 0
    error_count_today: int = 0


@router.get("/alerts", response_model=AlertStats)
async def get_alert_stats(
    request: Request, user: dict = Depends(verify_founder_access)
) -> AlertStats:
    """Get alert and error statistics"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)
    return await aggregator.get_alert_stats()


# ============================================================================
# ALL-IN-ONE ENDPOINT (for initial load)
# ============================================================================


class AllAnalytics(BaseModel):
    """All analytics combined for initial load"""

    overview: OverviewStats
    rag: RAGStats
    crm: CRMStats
    team: TeamStats
    system: SystemStats
    qdrant: QdrantStats
    feedback: FeedbackStats
    alerts: AlertStats
    generated_at: str


@router.get("/all", response_model=AllAnalytics)
async def get_all_analytics(
    request: Request, user: dict = Depends(verify_founder_access)
) -> AllAnalytics:
    """Get all analytics in one request for initial dashboard load"""
    from backend.services.analytics.analytics_aggregator import AnalyticsAggregator

    aggregator = AnalyticsAggregator(request.app.state)

    # Fetch all stats in parallel
    import asyncio

    overview, rag, crm, team, system, qdrant, feedback, alerts = await asyncio.gather(
        aggregator.get_overview_stats(),
        aggregator.get_rag_stats(),
        aggregator.get_crm_stats(),
        aggregator.get_team_stats(),
        aggregator.get_system_stats(),
        aggregator.get_qdrant_stats(),
        aggregator.get_feedback_stats(),
        aggregator.get_alert_stats(),
    )

    return AllAnalytics(
        overview=overview,
        rag=rag,
        crm=crm,
        team=team,
        system=system,
        qdrant=qdrant,
        feedback=feedback,
        alerts=alerts,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )
