"""
Optimal Hours Service
Responsibility: Optimal hours identification
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class OptimalHoursService:
    """
    Service for identifying optimal hours.

    Responsibility: Identify most productive time windows.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def identify_optimal_hours(self, user_email: str | None = None, days: int = 30) -> dict:
        """
        Identify most productive time windows.
        Based on conversations-per-hour by time of day.
        """
        cutoff = datetime.now() - timedelta(days=days)

        if user_email:
            sessions = await self.pool.fetch(
                """
                SELECT EXTRACT(HOUR FROM session_start) as hour,
                       duration_minutes, conversations_count
                FROM team_work_sessions
                WHERE user_email = $1
                AND session_start >= $2
                AND status = 'completed'
                AND duration_minutes > 0
            """,
                user_email,
                cutoff,
            )
        else:
            sessions = await self.pool.fetch(
                """
                SELECT EXTRACT(HOUR FROM session_start) as hour,
                       duration_minutes, conversations_count
                FROM team_work_sessions
                WHERE session_start >= $1
                AND status = 'completed'
                AND duration_minutes > 0
            """,
                cutoff,
            )

        if not sessions:
            return {"error": "No sessions found"}

        # Group by hour
        hourly_data = defaultdict(lambda: {"total_minutes": 0, "total_conversations": 0})

        for s in sessions:
            hour = int(s["hour"])
            hourly_data[hour]["total_minutes"] += s["duration_minutes"] or 0
            hourly_data[hour]["total_conversations"] += s["conversations_count"] or 0

        # Calculate productivity by hour
        hourly_productivity = []
        for hour in range(24):
            if hour in hourly_data:
                data = hourly_data[hour]
                total_hours = data["total_minutes"] / 60
                conv_per_hour = data["total_conversations"] / total_hours if total_hours > 0 else 0

                hourly_productivity.append(
                    {
                        "hour": f"{hour:02d}:00",
                        "conversations_per_hour": round(conv_per_hour, 2),
                        "total_hours_worked": round(total_hours, 2),
                        "total_conversations": data["total_conversations"],
                    }
                )

        # Sort by productivity
        hourly_productivity.sort(key=lambda x: x["conversations_per_hour"], reverse=True)

        # Identify peak hours
        peak_hours = (
            hourly_productivity[:3] if len(hourly_productivity) >= 3 else hourly_productivity
        )

        return {
            "optimal_windows": peak_hours,
            "all_hours": hourly_productivity,
            "recommendation": f"Most productive: {', '.join(h['hour'] for h in peak_hours)}",
        }
