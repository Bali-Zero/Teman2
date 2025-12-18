"""
ZANTARA MEDIA - Dashboard Router
Provides aggregated metrics and overview data
"""

import logging
from typing import Optional
from fastapi import APIRouter
from app.models import DashboardStats, PlatformStatus, DistributionPlatform
from app.db.content_repository import content_repository

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_db_stats() -> Optional[dict]:
    """Attempt to fetch stats from database, return None on failure."""
    try:
        return await content_repository.get_content_stats()
    except Exception as e:
        logger.warning(f"Failed to fetch database stats: {e}")
        return None


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Get aggregated dashboard statistics.
    Returns today's metrics, weekly summary, and platform status.
    Fetches real data from database when available, falls back to defaults.
    """
    db_stats = await _get_db_stats()

    if db_stats:
        return DashboardStats(
            today={
                "published": db_stats.get("published_count", 0),
                "scheduled": db_stats.get("scheduled_count", 0),
                "in_review": db_stats.get("review_count", 0),
                "intel_signals": 0,  # Would come from intel_signals table
                "engagements": db_stats.get("total_views", 0) or 0,
            },
            week={
                "total_published": db_stats.get("published_count", 0),
                "total_engagements": db_stats.get("total_views", 0) or 0,
                "new_leads": 0,  # Would come from CRM integration
                "avg_engagement_rate": float(db_stats.get("avg_engagement", 0) or 0),
            },
            platforms=[
                {"platform": "twitter", "posts": 0, "engagements": 0, "growth": 0},
                {"platform": "linkedin", "posts": 0, "engagements": 0, "growth": 0},
                {"platform": "instagram", "posts": 0, "engagements": 0, "growth": 0},
                {"platform": "telegram", "posts": 0, "engagements": 0, "growth": 0},
            ],
        )

    # Fallback to mock data when database is unavailable
    return DashboardStats(
        today={
            "published": 8,
            "scheduled": 12,
            "in_review": 3,
            "intel_signals": 12,
            "engagements": 15420,
        },
        week={
            "total_published": 34,
            "total_engagements": 89500,
            "new_leads": 156,
            "avg_engagement_rate": 4.2,
        },
        platforms=[
            {"platform": "twitter", "posts": 12, "engagements": 4500, "growth": 2.3},
            {"platform": "linkedin", "posts": 8, "engagements": 3200, "growth": 5.1},
            {"platform": "instagram", "posts": 15, "engagements": 8900, "growth": 3.8},
            {"platform": "telegram", "posts": 20, "engagements": 2100, "growth": 1.5},
        ],
    )


@router.get("/platforms/status", response_model=list[PlatformStatus])
async def get_platform_status():
    """
    Get connection status for all social media platforms.
    """
    # TODO: Check real connection status
    return [
        PlatformStatus(
            platform=DistributionPlatform.TWITTER,
            connected=True,
            followers=12400,
            posts_this_week=12,
        ),
        PlatformStatus(
            platform=DistributionPlatform.LINKEDIN,
            connected=True,
            followers=8200,
            posts_this_week=8,
        ),
        PlatformStatus(
            platform=DistributionPlatform.INSTAGRAM,
            connected=True,
            followers=15100,
            posts_this_week=15,
        ),
        PlatformStatus(
            platform=DistributionPlatform.TIKTOK,
            connected=True,
            followers=5800,
            posts_this_week=10,
        ),
        PlatformStatus(
            platform=DistributionPlatform.TELEGRAM,
            connected=True,
            followers=3200,
            posts_this_week=20,
        ),
        PlatformStatus(
            platform=DistributionPlatform.NEWSLETTER,
            connected=True,
            followers=4500,
            posts_this_week=2,
        ),
    ]


@router.get("/recent-activity")
async def get_recent_activity():
    """
    Get recent activity feed across all channels.
    """
    # TODO: Fetch from database
    return {
        "activities": [
            {
                "id": "1",
                "type": "content_published",
                "title": "New KITAS Regulations 2025",
                "timestamp": "2025-01-10T10:30:00Z",
                "user": "Zero",
            },
            {
                "id": "2",
                "type": "intel_processed",
                "title": "Tax deadline signal processed",
                "timestamp": "2025-01-10T09:15:00Z",
                "user": "AI Writer",
            },
            {
                "id": "3",
                "type": "distribution_scheduled",
                "title": "Twitter thread scheduled",
                "timestamp": "2025-01-10T08:45:00Z",
                "user": "System",
            },
        ]
    }


@router.get("/schedule/today")
async def get_today_schedule():
    """
    Get today's publishing schedule.
    """
    # TODO: Fetch from scheduler
    return {
        "entries": [
            {
                "time": "10:00",
                "title": "Newsletter send",
                "platform": "newsletter",
                "status": "pending",
            },
            {
                "time": "14:00",
                "title": "TikTok video post",
                "platform": "tiktok",
                "status": "pending",
            },
            {
                "time": "16:00",
                "title": "Twitter thread",
                "platform": "twitter",
                "status": "pending",
            },
            {
                "time": "18:00",
                "title": "LinkedIn article",
                "platform": "linkedin",
                "status": "pending",
            },
        ]
    }
