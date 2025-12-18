"""
Team Insights Service
Responsibility: Team collaboration insights
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class TeamInsightsService:
    """
    Service for generating team insights.

    Responsibility: Generate comprehensive team collaboration insights.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def generate_team_insights(self, days: int = 7) -> dict:
        """
        Generate comprehensive team collaboration insights.

        Provides:
        - Team sync patterns (who works when)
        - Collaboration opportunities
        - Team health score
        - Key metrics
        """
        cutoff = datetime.now() - timedelta(days=days)

        # Get all team sessions
        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email, session_start, session_end,
                   duration_minutes, conversations_count, activities_count,
                   EXTRACT(HOUR FROM session_start) as start_hour,
                   EXTRACT(DOW FROM session_start) as day_of_week
            FROM team_work_sessions
            WHERE session_start >= $1 AND status = 'completed'
            ORDER BY session_start
        """,
            cutoff,
        )

        if not sessions:
            return {"error": "No team sessions found"}

        # Calculate team metrics
        total_hours = sum((s["duration_minutes"] or 0) / 60 for s in sessions)
        total_conversations = sum(s["conversations_count"] or 0 for s in sessions)
        total_activities = sum(s["activities_count"] or 0 for s in sessions)

        unique_members = len({s["user_email"] for s in sessions})

        # Find overlap periods (when multiple people work)
        overlap_hours = defaultdict(set)
        for s in sessions:
            if s["session_start"] and s["session_end"]:
                start_hour = int(s["start_hour"])
                duration_hours = (s["duration_minutes"] or 0) / 60
                for h in range(start_hour, min(24, start_hour + int(duration_hours) + 1)):
                    overlap_hours[h].add(s["user_email"])

        # Identify best collaboration windows
        collaboration_windows = []
        for hour, members in overlap_hours.items():
            if len(members) >= 2:
                collaboration_windows.append(
                    {
                        "hour": f"{hour:02d}:00",
                        "team_members_online": len(members),
                        "members": list(members),
                    }
                )

        collaboration_windows.sort(key=lambda x: x["team_members_online"], reverse=True)

        # Team health score (0-100)
        # Based on: participation, workload balance, productivity
        participation_score = min(100, (unique_members / max(1, unique_members)) * 100)
        productivity_score = min(100, (total_conversations / max(1, total_hours)) * 20)

        team_health_score = (participation_score + productivity_score) / 2

        return {
            "team_summary": {
                "active_members": unique_members,
                "total_hours_worked": round(total_hours, 2),
                "total_conversations": total_conversations,
                "total_activities": total_activities,
                "avg_hours_per_member": (
                    round(total_hours / unique_members, 2) if unique_members > 0 else 0
                ),
                "avg_conversations_per_member": (
                    round(total_conversations / unique_members, 1) if unique_members > 0 else 0
                ),
            },
            "team_health_score": round(team_health_score, 1),
            "health_rating": (
                "Excellent"
                if team_health_score >= 80
                else (
                    "Good"
                    if team_health_score >= 60
                    else "Fair"
                    if team_health_score >= 40
                    else "Needs Attention"
                )
            ),
            "collaboration_windows": collaboration_windows[:5],  # Top 5
            "insights": self._generate_team_insights_text(
                unique_members,
                total_hours,
                total_conversations,
                collaboration_windows,
                team_health_score,
            ),
            "period_days": days,
        }

    def _generate_team_insights_text(
        self,
        members: int,
        hours: float,
        conversations: int,
        collab_windows: list[dict],
        health_score: float,
    ) -> list[str]:
        """Generate human-readable insights"""
        insights = []

        insights.append(f"👥 {members} active team members this period")
        insights.append(f"⏰ {round(hours, 1)} total hours worked")
        insights.append(f"💬 {conversations} conversations handled")

        if collab_windows:
            best_window = collab_windows[0]
            insights.append(
                f"🤝 Best collaboration time: {best_window['hour']} "
                f"({best_window['team_members_online']} members typically online)"
            )

        if health_score >= 80:
            insights.append("✅ Team is performing excellently")
        elif health_score >= 60:
            insights.append("👍 Team is performing well")
        else:
            insights.append("⚠️ Team performance could be improved")

        return insights
