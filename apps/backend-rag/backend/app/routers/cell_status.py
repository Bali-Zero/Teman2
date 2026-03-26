"""CELL organism status endpoint — serves dashboard data."""
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends

from backend.app.dependencies import get_current_user, get_database_pool
from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/cell", tags=["cell"])


@router.get("/status")
async def get_cell_status(
    db_pool=Depends(get_database_pool),
    user=Depends(get_current_user),
) -> dict[str, Any]:
    """Get CELL organism status for dashboard."""
    async with db_pool.acquire() as conn:
        last = await conn.fetchrow(
            "SELECT * FROM cell_pulse_log ORDER BY created_at DESC LIMIT 1"
        )
        recent = await conn.fetch(
            """SELECT pulse_number, health_status, response_time_ms, created_at
               FROM cell_pulse_log ORDER BY created_at DESC LIMIT 50"""
        )
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        stats = await conn.fetchrow(
            """SELECT
                 COUNT(*) as total,
                 COUNT(*) FILTER (WHERE health_status = 'green') as green_count,
                 COUNT(*) FILTER (WHERE health_status = 'yellow') as yellow_count,
                 COUNT(*) FILTER (WHERE health_status = 'red') as red_count
               FROM cell_pulse_log
               WHERE created_at > $1""",
            cutoff,
        )

    alive = False
    if last:
        age = (datetime.now(timezone.utc) - last["created_at"]).total_seconds()
        alive = age < 120

    total = stats["total"] if stats else 0

    return {
        "alive": alive,
        "last_pulse": dict(last) if last else None,
        "recent_pulses": [dict(r) for r in recent],
        "uptime_24h": {
            "green_percent": round(stats["green_count"] / total * 100, 1) if total > 0 else 0,
            "yellow_percent": round(stats["yellow_count"] / total * 100, 1) if total > 0 else 0,
            "red_percent": round(stats["red_count"] / total * 100, 1) if total > 0 else 0,
            "total_pulses": total,
        },
    }
