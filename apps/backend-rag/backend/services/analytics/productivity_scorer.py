"""
Productivity Scorer Service
Responsibility: Productivity scoring
"""

import logging
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class ProductivityScorerService:
    """
    Service for calculating productivity scores.

    Responsibility: Calculate productivity score for each team member.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def calculate_productivity_scores(self, days: int = 7) -> list[dict]:
        """
        Calculate productivity score for each team member.

        Score based on:
        - Conversations per hour
        - Activities per hour
        - Session consistency
        - Work time efficiency
        """
        cutoff = datetime.now() - timedelta(days=days)

        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email,
                   SUM(duration_minutes) as total_minutes,
                   SUM(conversations_count) as total_conversations,
                   SUM(activities_count) as total_activities,
                   COUNT(*) as session_count
            FROM team_work_sessions
            WHERE session_start >= $1 AND status = 'completed'
            GROUP BY user_name, user_email
        """,
            cutoff,
        )

        results = []
        for s in sessions:
            total_hours = (s["total_minutes"] or 0) / 60
            if total_hours == 0:
                continue

            # Calculate metrics
            conversations_per_hour = (s["total_conversations"] or 0) / total_hours
            activities_per_hour = (s["total_activities"] or 0) / total_hours
            avg_session_hours = total_hours / s["session_count"]

            # Productivity score (0-100)
            # - 40% from conversation rate (target: 2-5 per hour)
            # - 30% from activity rate (target: 10-30 per hour)
            # - 30% from session length consistency (target: 4-8 hours)

            conv_score = min(100, (conversations_per_hour / 5) * 100) * 0.4
            activity_score = min(100, (activities_per_hour / 30) * 100) * 0.3

            # Session length score (optimal 4-8 hours)
            if 4 <= avg_session_hours <= 8:
                length_score = 100 * 0.3
            elif avg_session_hours < 4:
                length_score = (avg_session_hours / 4) * 100 * 0.3
            else:
                length_score = max(0, (1 - (avg_session_hours - 8) / 4)) * 100 * 0.3

            productivity_score = conv_score + activity_score + length_score

            results.append(
                {
                    "user": s["user_name"],
                    "email": s["user_email"],
                    "productivity_score": round(productivity_score, 1),
                    "rating": (
                        "Excellent"
                        if productivity_score >= 80
                        else (
                            "Good"
                            if productivity_score >= 60
                            else "Fair"
                            if productivity_score >= 40
                            else "Needs Attention"
                        )
                    ),
                    "metrics": {
                        "conversations_per_hour": round(conversations_per_hour, 2),
                        "activities_per_hour": round(activities_per_hour, 2),
                        "avg_session_hours": round(avg_session_hours, 2),
                        "total_hours": round(total_hours, 2),
                        "sessions": s["session_count"],
                    },
                }
            )

        # Sort by score descending
        results.sort(key=lambda x: x["productivity_score"], reverse=True)
        return results
