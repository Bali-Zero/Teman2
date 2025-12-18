"""
Workload Balance Service
Responsibility: Workload distribution analysis
"""

import logging
import statistics
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class WorkloadBalanceService:
    """
    Service for analyzing workload balance.

    Responsibility: Analyze workload distribution across team.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def analyze_workload_balance(self, days: int = 7) -> dict:
        """
        Analyze workload distribution across team.
        Identifies imbalances and suggests redistribution.
        """
        cutoff = datetime.now() - timedelta(days=days)

        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email,
                   SUM(duration_minutes) as total_minutes,
                   SUM(conversations_count) as total_conversations,
                   COUNT(*) as session_count
            FROM team_work_sessions
            WHERE session_start >= $1 AND status = 'completed'
            GROUP BY user_name, user_email
        """,
            cutoff,
        )

        if not sessions:
            return {"error": "No sessions found"}

        team_stats = []
        total_hours = 0
        total_conversations = 0

        for s in sessions:
            hours = (s["total_minutes"] or 0) / 60
            total_hours += hours
            total_conversations += s["total_conversations"] or 0

            team_stats.append(
                {
                    "user": s["user_name"],
                    "email": s["user_email"],
                    "hours": round(hours, 2),
                    "conversations": s["total_conversations"] or 0,
                    "sessions": s["session_count"],
                }
            )

        # Calculate shares and ideal distribution
        team_size = len(team_stats)
        ideal_hours_per_person = total_hours / team_size if team_size > 0 else 0

        for stat in team_stats:
            stat["hours_share_percent"] = (
                round((stat["hours"] / total_hours * 100), 1) if total_hours > 0 else 0
            )
            stat["conversations_share_percent"] = (
                round((stat["conversations"] / total_conversations * 100), 1)
                if total_conversations > 0
                else 0
            )
            stat["deviation_from_ideal"] = round(stat["hours"] - ideal_hours_per_person, 2)

        # Sort by hours descending
        team_stats.sort(key=lambda x: x["hours"], reverse=True)

        # Calculate balance score
        hours_list = [s["hours"] for s in team_stats]
        if len(hours_list) > 1:
            std_hours = statistics.stdev(hours_list)
            avg_hours = statistics.mean(hours_list)
            coefficient_variation = (std_hours / avg_hours) * 100 if avg_hours > 0 else 0
            balance_score = max(0, 100 - coefficient_variation)
        else:
            balance_score = 100

        return {
            "team_distribution": team_stats,
            "balance_metrics": {
                "balance_score": round(balance_score, 1),
                "balance_rating": (
                    "Well Balanced"
                    if balance_score >= 80
                    else "Moderately Balanced"
                    if balance_score >= 60
                    else "Imbalanced"
                ),
                "ideal_hours_per_person": round(ideal_hours_per_person, 2),
                "total_team_hours": round(total_hours, 2),
                "team_size": team_size,
            },
            "recommendations": self._generate_workload_recommendations(
                team_stats, ideal_hours_per_person
            ),
        }

    def _generate_workload_recommendations(self, team_stats: list[dict], ideal: float) -> list[str]:
        """Generate workload redistribution recommendations"""
        recommendations = []

        overworked = [s for s in team_stats if s["deviation_from_ideal"] > ideal * 0.3]
        underutilized = [s for s in team_stats if s["deviation_from_ideal"] < -ideal * 0.3]

        if overworked:
            for s in overworked:
                recommendations.append(
                    f"⚠️ {s['user']} is working {abs(s['deviation_from_ideal']):.1f}h above average - consider redistributing tasks"
                )

        if underutilized:
            for s in underutilized:
                recommendations.append(
                    f"💡 {s['user']} has capacity for {abs(s['deviation_from_ideal']):.1f}h more work"
                )

        if not recommendations:
            recommendations.append("✅ Team workload is well balanced")

        return recommendations
