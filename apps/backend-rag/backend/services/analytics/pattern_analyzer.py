"""
Pattern Analyzer Service
Responsibility: Work pattern analysis
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class PatternAnalyzerService:
    """
    Service for analyzing work patterns.

    Responsibility: Analyze work hour patterns and habits.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def analyze_work_patterns(self, user_email: str | None = None, days: int = 30) -> dict:
        """
        Analyze work hour patterns and habits.

        Returns:
        - Preferred start times
        - Typical session duration
        - Work day patterns (weekday vs weekend)
        - Consistency score
        """
        cutoff = datetime.now() - timedelta(days=days)

        # Get sessions
        if user_email:
            sessions = await self.pool.fetch(
                """
                SELECT session_start, duration_minutes,
                       EXTRACT(DOW FROM session_start) as day_of_week,
                       EXTRACT(HOUR FROM session_start) as start_hour
                FROM team_work_sessions
                WHERE user_email = $1
                AND session_start >= $2
                AND status = 'completed'
                ORDER BY session_start
            """,
                user_email,
                cutoff,
            )
        else:
            sessions = await self.pool.fetch(
                """
                SELECT user_email, session_start, duration_minutes,
                       EXTRACT(DOW FROM session_start) as day_of_week,
                       EXTRACT(HOUR FROM session_start) as start_hour
                FROM team_work_sessions
                WHERE session_start >= $1
                AND status = 'completed'
                ORDER BY session_start
            """,
                cutoff,
            )

        if not sessions:
            return {"error": "No sessions found"}

        # Analyze patterns
        start_hours = [float(s["start_hour"]) for s in sessions]
        durations = [float(s["duration_minutes"]) for s in sessions if s["duration_minutes"]]
        days_of_week = [s["day_of_week"] for s in sessions]

        # Calculate statistics
        avg_start_hour = statistics.mean(start_hours) if start_hours else 0
        std_start_hour = statistics.stdev(start_hours) if len(start_hours) > 1 else 0

        avg_duration = statistics.mean(durations) if durations else 0
        std_duration = statistics.stdev(durations) if len(durations) > 1 else 0

        # Day distribution
        day_counts = defaultdict(int)
        for day in days_of_week:
            day_counts[day] += 1

        # Consistency score (0-100, higher = more consistent)
        time_consistency = max(0, 100 - (std_start_hour * 10))
        duration_consistency = max(0, 100 - (std_duration / 6))
        consistency_score = (time_consistency + duration_consistency) / 2

        return {
            "patterns": {
                "avg_start_hour": round(avg_start_hour, 1),
                "start_hour_variance": round(std_start_hour, 2),
                "preferred_start_time": f"{int(avg_start_hour):02d}:{int((avg_start_hour % 1) * 60):02d}",
                "avg_session_duration_hours": round(avg_duration / 60, 2),
                "duration_variance_minutes": round(std_duration, 1),
            },
            "day_distribution": {
                "weekdays": sum(day_counts[d] for d in range(1, 6)),  # Mon-Fri
                "weekends": sum(day_counts[d] for d in [0, 6]),  # Sun, Sat
            },
            "consistency_score": round(consistency_score, 1),
            "consistency_rating": (
                "Excellent"
                if consistency_score >= 80
                else (
                    "Good"
                    if consistency_score >= 60
                    else "Fair"
                    if consistency_score >= 40
                    else "Variable"
                )
            ),
            "total_sessions_analyzed": len(sessions),
            "period_days": days,
        }
