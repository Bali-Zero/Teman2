"""
Team Analytics API Router
Exposes TeamAnalyticsService functionality via REST API endpoints
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_database_pool
from services.team_analytics_service import TeamAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/team-analytics", tags=["team-analytics"])

# Global service instance
_team_analytics_service: Optional[TeamAnalyticsService] = None


def get_team_analytics_service(db_pool=Depends(get_database_pool)) -> TeamAnalyticsService:
    """Get or create TeamAnalyticsService instance"""
    global _team_analytics_service
    if _team_analytics_service is None:
        _team_analytics_service = TeamAnalyticsService(db_pool)
    return _team_analytics_service


@router.get("/patterns")
async def get_work_patterns(
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Analyze work hour patterns and habits"""
    try:
        patterns = await service.analyze_work_patterns(user_email, days)
        return {"success": True, "data": patterns}
    except Exception as e:
        logger.error(f"Failed to analyze work patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/productivity")
async def get_productivity_scores(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Calculate productivity scores for team members"""
    try:
        scores = await service.calculate_productivity_scores(days)
        return {"success": True, "scores": scores}
    except Exception as e:
        logger.error(f"Failed to calculate productivity scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/burnout")
async def get_burnout_signals(
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Detect early warning signs of burnout"""
    try:
        signals = await service.detect_burnout_signals(user_email)
        return {"success": True, "signals": signals}
    except Exception as e:
        logger.error(f"Failed to detect burnout signals: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/{user_email}")
async def get_performance_trends(
    user_email: str,
    weeks: int = Query(4, ge=1, le=52, description="Number of weeks to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Analyze performance trends over time"""
    try:
        trends = await service.analyze_performance_trends(user_email, weeks)
        return {"success": True, "trends": trends}
    except Exception as e:
        logger.error(f"Failed to analyze performance trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/workload-balance")
async def get_workload_balance(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Analyze workload distribution across team"""
    try:
        balance = await service.analyze_workload_balance(days)
        return {"success": True, "balance": balance}
    except Exception as e:
        logger.error(f"Failed to analyze workload balance: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/optimal-hours")
async def get_optimal_hours(
    user_email: Optional[str] = Query(None, description="Filter by user email"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Identify most productive time windows"""
    try:
        optimal = await service.identify_optimal_hours(user_email, days)
        return {"success": True, "optimal_hours": optimal}
    except Exception as e:
        logger.error(f"Failed to identify optimal hours: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/team-insights")
async def get_team_insights(
    days: int = Query(7, ge=1, le=365, description="Number of days to analyze"),
    service: TeamAnalyticsService = Depends(get_team_analytics_service),
):
    """Generate comprehensive team collaboration insights"""
    try:
        insights = await service.generate_team_insights(days)
        return {"success": True, "insights": insights}
    except Exception as e:
        logger.error(f"Failed to generate team insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))
