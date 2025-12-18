"""
Burnout Detector Service
Responsibility: Burnout signal detection
"""

import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta

import asyncpg

logger = logging.getLogger(__name__)


class BurnoutDetectorService:
    """
    Service for detecting burnout signals.

    Responsibility: Detect early warning signs of burnout.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool

    async def detect_burnout_signals(self, user_email: str | None = None) -> list[dict]:
        """
        Detect early warning signs of burnout.

        Warning signals:
        - Increasing work hours over time
        - Decreasing conversations per hour (efficiency drop)
        - Working on weekends frequently
        - Very long sessions (>10 hours)
        - Inconsistent work patterns
        """
        cutoff = datetime.now() - timedelta(days=30)

        if user_email:
            sessions = await self.pool.fetch(
                """
                SELECT user_name, user_email, session_start, duration_minutes,
                       conversations_count, activities_count,
                       EXTRACT(DOW FROM session_start) as day_of_week
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
                SELECT user_name, user_email, session_start, duration_minutes,
                       conversations_count, activities_count,
                       EXTRACT(DOW FROM session_start) as day_of_week
                FROM team_work_sessions
                WHERE session_start >= $1
                AND status = 'completed'
                ORDER BY session_start
            """,
                cutoff,
            )

        # Group by user
        user_sessions = defaultdict(list)
        for s in sessions:
            user_sessions[s["user_email"]].append(s)

        results = []
        for email, user_sess in user_sessions.items():
            if len(user_sess) < 3:  # Need at least 3 sessions
                continue

            warnings = []
            risk_score = 0

            # Check 1: Increasing hours trend
            recent_hours = sum(s["duration_minutes"] for s in user_sess[-5:]) / 60
            older_hours = sum(s["duration_minutes"] for s in user_sess[:5]) / 60
            if recent_hours > older_hours * 1.3:
                warnings.append("📈 Work hours increasing (+30%)")
                risk_score += 25

            # Check 2: Very long sessions (>10 hours)
            long_sessions = sum(1 for s in user_sess if (s["duration_minutes"] or 0) > 600)
            if long_sessions >= 2:
                warnings.append(f"⏰ {long_sessions} very long sessions (>10h)")
                risk_score += 20

            # Check 3: Weekend work
            weekend_sessions = sum(1 for s in user_sess if s["day_of_week"] in [0, 6])
            if weekend_sessions >= 2:
                warnings.append(f"📅 Working {weekend_sessions} weekends")
                risk_score += 15

            # Check 4: Declining efficiency
            if len(user_sess) >= 6:
                recent_conv_per_hour = sum(s["conversations_count"] for s in user_sess[-3:]) / (
                    sum(s["duration_minutes"] for s in user_sess[-3:]) / 60
                )
                older_conv_per_hour = sum(s["conversations_count"] for s in user_sess[:3]) / (
                    sum(s["duration_minutes"] for s in user_sess[:3]) / 60
                )
                if recent_conv_per_hour < older_conv_per_hour * 0.7:
                    warnings.append("📉 Conversation efficiency dropped -30%")
                    risk_score += 20

            # Check 5: Inconsistent patterns
            durations = [s["duration_minutes"] for s in user_sess if s["duration_minutes"]]
            if len(durations) > 3:
                std_duration = statistics.stdev(durations)
                avg_duration = statistics.mean(durations)
                if std_duration > avg_duration * 0.5:
                    warnings.append("🔄 Highly inconsistent work patterns")
                    risk_score += 20

            if warnings:
                results.append(
                    {
                        "user": user_sess[0]["user_name"],
                        "email": email,
                        "burnout_risk_score": min(100, risk_score),
                        "risk_level": (
                            "High Risk"
                            if risk_score >= 60
                            else "Medium Risk"
                            if risk_score >= 40
                            else "Low Risk"
                        ),
                        "warning_signals": warnings,
                        "warning_count": len(warnings),
                        "total_sessions_analyzed": len(user_sess),
                    }
                )

        # Sort by risk score descending
        results.sort(key=lambda x: x["burnout_risk_score"], reverse=True)
        return results
