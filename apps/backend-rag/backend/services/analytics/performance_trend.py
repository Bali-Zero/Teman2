"""
Performance Trend Service
Responsibility: Performance trend analysis
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class PerformanceTrendService:
    """
    Service for analyzing performance trends.

    Responsibility: Analyze performance trends over time.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def analyze_performance_trends(self, user_email: str, weeks: int = 4) -> dict:
        """
        Analyze performance trends over time.
        Returns week-by-week trend data.
        """
        cutoff = datetime.now() - timedelta(weeks=weeks)

        sessions = await self.pool.fetch(
            """
            SELECT session_start, duration_minutes, conversations_count, activities_count
            FROM team_work_sessions
            WHERE user_email = $1
            AND session_start >= $2
            AND status = 'completed'
            ORDER BY session_start
        """,
            user_email,
            cutoff,
        )

        if not sessions:
            return {"error": "No sessions found"}

        # Group by week
        weekly_data = defaultdict(
            lambda: {"hours": 0, "conversations": 0, "activities": 0, "sessions": 0}
        )

        for s in sessions:
            week_start = s["session_start"] - timedelta(days=s["session_start"].weekday())
            week_key = week_start.strftime("%Y-W%U")

            weekly_data[week_key]["hours"] += (s["duration_minutes"] or 0) / 60
            weekly_data[week_key]["conversations"] += s["conversations_count"] or 0
            weekly_data[week_key]["activities"] += s["activities_count"] or 0
            weekly_data[week_key]["sessions"] += 1

        # Convert to sorted list
        weeks = []
        for week_key in sorted(weekly_data.keys()):
            data = weekly_data[week_key]
            weeks.append(
                {
                    "week": week_key,
                    "hours": round(data["hours"], 2),
                    "conversations": data["conversations"],
                    "activities": data["activities"],
                    "sessions": data["sessions"],
                    "conversations_per_hour": (
                        round(data["conversations"] / data["hours"], 2) if data["hours"] > 0 else 0
                    ),
                }
            )

        # Calculate trend
        if len(weeks) >= 2:
            first_half_hours = sum(w["hours"] for w in weeks[: len(weeks) // 2])
            second_half_hours = sum(w["hours"] for w in weeks[len(weeks) // 2 :])
            trend_direction = "Increasing" if second_half_hours > first_half_hours else "Decreasing"
        else:
            trend_direction = "Stable"

        return {
            "weekly_breakdown": weeks,
            "trend": {"direction": trend_direction, "total_weeks_analyzed": len(weeks)},
            "averages": {
                "hours_per_week": (
                    round(sum(w["hours"] for w in weeks) / len(weeks), 2) if weeks else 0
                ),
                "conversations_per_week": (
                    round(sum(w["conversations"] for w in weeks) / len(weeks), 1) if weeks else 0
                ),
            },
        }
