"""
X/Twitter Social Listening Monitor — API Endpoints.

Provides stats and recent tweet data from the X keyword monitor.
"""

import logging
from typing import Any

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/x-monitor", tags=["X Monitor"])


def _get_monitor(request: Request) -> Any | None:
    """Get XMonitorService from app state."""
    return getattr(request.app.state, "x_monitor_service", None)


@router.get("/stats")
async def get_monitor_stats(request: Request) -> dict[str, Any]:
    """Get X social listening statistics."""
    monitor = _get_monitor(request)
    if not monitor:
        return {"status": "disabled", "total": 0, "leads": 0}

    stats = await monitor.get_stats()
    return {"status": "active", **stats}


@router.get("/recent")
async def get_recent_tweets(request: Request, limit: int = 20) -> dict[str, Any]:
    """Get recent monitored tweets."""
    monitor = _get_monitor(request)
    if not monitor:
        return {"status": "disabled", "tweets": []}

    limit = min(limit, 100)
    tweets = await monitor.get_recent(limit=limit)

    # Serialize datetime fields
    for t in tweets:
        for key in ("created_at", "tweet_created_at"):
            if t.get(key) is not None:
                t[key] = t[key].isoformat()

    return {"status": "active", "count": len(tweets), "tweets": tweets}
