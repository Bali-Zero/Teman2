"""
Work Session Tracking Service
Tracks team member work hours and activities
All reports sent to ZERO only
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

import asyncpg

logger = logging.getLogger(__name__)


class WorkSessionService:
    """
    Track team work sessions and send reports to ZERO
    ZERO decides what to share with team

    Data persistence:
    - PostgreSQL: Primary storage (Fly.io cloud database)
    - JSONL file: Local backup log (work_sessions_log.jsonl)
    """

    def __init__(self):
        from app.core.config import settings

        self.db_url = settings.database_url
        self.pool = None
        self.zero_email = "zero@balizero.com"  # All notifications go here

        # Setup local backup file
        self.data_dir = Path(__file__).parent.parent / "data"
        self.log_file = self.data_dir / "work_sessions_log.jsonl"
        self._ensure_data_dir()

    def _ensure_data_dir(self):
        """Ensure data directory exists"""
        try:
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"📁 Work sessions log: {self.log_file}")
        except Exception as e:
            logger.warning(f"⚠️ Could not create data directory: {e}")

    def _write_to_log(self, event_type: str, data: dict):
        """
        Write event to JSONL backup file
        Each line is a JSON object with timestamp
        """
        try:
            event = {"timestamp": datetime.now().isoformat(), "event_type": event_type, **data}

            with open(self.log_file, "a") as f:
                f.write(json.dumps(event) + "\n")

        except Exception as e:
            logger.warning(f"⚠️ Failed to write to log file: {e}")

    async def connect(self):
        """Initialize connection pool"""
        if self.db_url:
            self.pool = await asyncpg.create_pool(self.db_url)
            logger.info("✅ WorkSessionService connected to PostgreSQL")
        else:
            logger.warning("⚠️ DATABASE_URL not found - WorkSessionService disabled")

    async def start_session(self, user_id: str, user_name: str, user_email: str) -> dict:
        """
        Start work session when team member logs into webapp
        Auto-called on first activity of the day
        """
        if not self.pool:
            return {"error": "Database not available"}

        try:
            # Check if already has active session today
            today_start = datetime.now().replace(hour=0, minute=0, second=0)

            existing = await self.pool.fetchrow(
                """
                SELECT id, session_start FROM team_work_sessions
                WHERE user_id = $1
                AND session_start >= $2
                AND status = 'active'
                ORDER BY session_start DESC
                LIMIT 1
            """,
                user_id,
                today_start,
            )

            if existing:
                logger.info(f"⏰ {user_name} already has active session")
                return {
                    "status": "already_active",
                    "session_id": existing["id"],
                    "started_at": existing["session_start"].isoformat(),
                }

            # Create new session
            session = await self.pool.fetchrow(
                """
                INSERT INTO team_work_sessions
                (user_id, user_name, user_email, session_start, last_activity, status)
                VALUES ($1, $2, $3, NOW(), NOW(), 'active')
                RETURNING id, session_start
            """,
                user_id,
                user_name,
                user_email,
            )

            logger.info(f"✅ Work session started: {user_name} at {session['session_start']}")

            # Write to backup log file
            self._write_to_log(
                "session_start",
                {
                    "session_id": session["id"],
                    "user_id": user_id,
                    "user_name": user_name,
                    "user_email": user_email,
                    "session_start": session["session_start"].isoformat(),
                },
            )

            # Notify ZERO
            await self._notify_zero(
                subject=f"🟢 {user_name} started work",
                message=f"""
Team member: {user_name}
Email: {user_email}
Started at: {session["session_start"].strftime("%H:%M")}

Session ID: {session["id"]}
""",
            )

            return {
                "status": "started",
                "session_id": session["id"],
                "started_at": session["session_start"].isoformat(),
                "user": user_name,
            }

        except Exception as e:
            logger.error(f"❌ Failed to start session: {e}")
            return {"error": str(e)}

    async def update_activity(self, user_id: str):
        """Update last activity timestamp for active session"""
        if not self.pool:
            return

        try:
            await self.pool.execute(
                """
                UPDATE team_work_sessions
                SET last_activity = NOW(),
                    activities_count = activities_count + 1,
                    updated_at = NOW()
                WHERE user_id = $1 AND status = 'active'
            """,
                user_id,
            )
        except Exception as e:
            logger.error(f"Failed to update activity: {e}")

    async def increment_conversations(self, user_id: str):
        """Increment conversation counter for active session"""
        if not self.pool:
            return

        try:
            await self.pool.execute(
                """
                UPDATE team_work_sessions
                SET conversations_count = conversations_count + 1,
                    last_activity = NOW(),
                    updated_at = NOW()
                WHERE user_id = $1 AND status = 'active'
            """,
                user_id,
            )
        except Exception as e:
            logger.error(f"Failed to increment conversations: {e}")

    async def end_session(self, user_id: str, notes: str | None = None) -> dict:
        """
        End work session when team member says "logout today"
        Sends report to ZERO
        """
        if not self.pool:
            return {"error": "Database not available"}

        try:
            # Get active session
            session = await self.pool.fetchrow(
                """
                SELECT id, session_start, user_name, user_email,
                       activities_count, conversations_count
                FROM team_work_sessions
                WHERE user_id = $1 AND status = 'active'
                ORDER BY session_start DESC
                LIMIT 1
            """,
                user_id,
            )

            if not session:
                return {"status": "no_active_session", "message": "No active session found"}

            # Calculate duration
            session_start = session["session_start"]
            session_end = datetime.now(session_start.tzinfo)
            duration_minutes = int((session_end - session_start).total_seconds() / 60)

            # Update session
            await self.pool.execute(
                """
                UPDATE team_work_sessions
                SET session_end = $1,
                    duration_minutes = $2,
                    status = 'completed',
                    notes = $3,
                    updated_at = NOW()
                WHERE id = $4
            """,
                session_end,
                duration_minutes,
                notes,
                session["id"],
            )

            logger.info(f"✅ Session ended: {session['user_name']} ({duration_minutes} min)")

            # Write to backup log file
            self._write_to_log(
                "session_end",
                {
                    "session_id": session["id"],
                    "user_id": user_id,
                    "user_name": session["user_name"],
                    "user_email": session["user_email"],
                    "session_start": session_start.isoformat(),
                    "session_end": session_end.isoformat(),
                    "duration_minutes": duration_minutes,
                    "duration_hours": round(duration_minutes / 60, 2),
                    "activities_count": session["activities_count"],
                    "conversations_count": session["conversations_count"],
                    "notes": notes,
                },
            )

            # Send detailed report to ZERO
            await self._notify_zero_session_end(
                user_name=session["user_name"],
                user_email=session["user_email"],
                start=session_start,
                end=session_end,
                duration_minutes=duration_minutes,
                activities=session["activities_count"],
                conversations=session["conversations_count"],
                notes=notes,
            )

            return {
                "status": "completed",
                "session_id": session["id"],
                "user": session["user_name"],
                "started_at": session_start.isoformat(),
                "ended_at": session_end.isoformat(),
                "duration_minutes": duration_minutes,
                "duration_hours": round(duration_minutes / 60, 2),
                "activities": session["activities_count"],
                "conversations": session["conversations_count"],
            }

        except Exception as e:
            logger.error(f"❌ Failed to end session: {e}")
            return {"error": str(e)}

    async def get_today_sessions(self) -> list[dict]:
        """Get all sessions for today - for ZERO dashboard"""
        if not self.pool:
            return []

        today_start = datetime.now().replace(hour=0, minute=0, second=0)

        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email, session_start, session_end,
                   duration_minutes, activities_count, conversations_count,
                   status, last_activity, notes
            FROM team_work_sessions
            WHERE session_start >= $1
            ORDER BY session_start DESC
        """,
            today_start,
        )

        return [dict(s) for s in sessions]

    async def get_week_summary(self) -> dict:
        """Get weekly summary - for ZERO dashboard"""
        if not self.pool:
            return {}

        week_start = datetime.now() - timedelta(days=7)

        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email, session_start, duration_minutes,
                   conversations_count, activities_count
            FROM team_work_sessions
            WHERE session_start >= $1 AND status = 'completed'
            ORDER BY session_start
        """,
            week_start,
        )

        # Aggregate by user
        user_stats = {}
        for s in sessions:
            email = s["user_email"]
            if email not in user_stats:
                user_stats[email] = {
                    "name": s["user_name"],
                    "email": email,
                    "total_hours": 0,
                    "total_conversations": 0,
                    "total_activities": 0,
                    "days_worked": 0,
                    "sessions": [],
                }

            hours = (s["duration_minutes"] or 0) / 60
            user_stats[email]["total_hours"] += hours
            user_stats[email]["total_conversations"] += s["conversations_count"] or 0
            user_stats[email]["total_activities"] += s["activities_count"] or 0
            user_stats[email]["sessions"].append(
                {"date": s["session_start"].strftime("%Y-%m-%d"), "hours": round(hours, 2)}
            )

        # Count unique days
        for stats in user_stats.values():
            unique_dates = {s["date"] for s in stats["sessions"]}
            stats["days_worked"] = len(unique_dates)
            stats["avg_hours_per_day"] = (
                round(stats["total_hours"] / stats["days_worked"], 2)
                if stats["days_worked"] > 0
                else 0
            )

        return {
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": datetime.now().strftime("%Y-%m-%d"),
            "team_stats": list(user_stats.values()),
            "total_team_hours": sum(s["total_hours"] for s in user_stats.values()),
        }

    async def generate_daily_report(self, date: datetime | None = None) -> dict:
        """
        Generate daily report for ZERO
        Summarizes all team activity for the day
        """
        if not self.pool:
            return {"error": "Database not available"}

        if not date:
            date = datetime.now()

        day_start = date.replace(hour=0, minute=0, second=0)
        day_end = day_start + timedelta(days=1)

        # Get all sessions for the day
        sessions = await self.pool.fetch(
            """
            SELECT user_name, user_email, session_start, session_end,
                   duration_minutes, activities_count, conversations_count,
                   status, notes
            FROM team_work_sessions
            WHERE session_start >= $1 AND session_start < $2
            ORDER BY session_start
        """,
            day_start,
            day_end,
        )

        # Calculate totals
        total_hours = 0
        total_conversations = 0
        team_summary = []

        for session in sessions:
            duration_hours = (session["duration_minutes"] or 0) / 60
            total_hours += duration_hours
            total_conversations += session["conversations_count"] or 0

            team_summary.append(
                {
                    "name": session["user_name"],
                    "email": session["user_email"],
                    "start": (
                        session["session_start"].strftime("%H:%M")
                        if session["session_start"]
                        else None
                    ),
                    "end": (
                        session["session_end"].strftime("%H:%M")
                        if session["session_end"]
                        else "In corso"
                    ),
                    "hours": round(duration_hours, 2),
                    "conversations": session["conversations_count"] or 0,
                    "activities": session["activities_count"] or 0,
                    "status": session["status"],
                    "notes": session["notes"],
                }
            )

        report = {
            "date": date.strftime("%Y-%m-%d"),
            "total_hours": round(total_hours, 2),
            "total_conversations": total_conversations,
            "team_members_active": len(sessions),
            "team_summary": team_summary,
        }

        # Save report
        try:
            await self.pool.execute(
                """
                INSERT INTO team_daily_reports (report_date, team_summary, total_hours, total_conversations)
                VALUES ($1, $2::jsonb, $3, $4)
                ON CONFLICT (report_date) DO UPDATE
                SET team_summary = $2::jsonb, total_hours = $3, total_conversations = $4
            """,
                date.date(),
                report,
                total_hours,
                total_conversations,
            )
        except Exception as e:
            logger.error(f"Failed to save daily report: {e}")

        return report

    async def _notify_zero_session_end(
        self,
        user_name: str,
        user_email: str,
        start: datetime,
        end: datetime,
        duration_minutes: int,
        activities: int,
        conversations: int,
        notes: str | None,
    ):
        """Send notification to ZERO about session end"""

        hours = duration_minutes // 60
        minutes = duration_minutes % 60

        subject = f"🏁 {user_name} finished work - {hours}h {minutes}m"

        # Prepare notes section (avoid nested f-strings)
        notes_section = f"📝 NOTES FROM TEAM MEMBER:\n{notes}\n\n" if notes else ""

        message = f"""
TEAM MEMBER WORK SESSION COMPLETED

👤 Team Member: {user_name}
📧 Email: {user_email}

⏰ SCHEDULE:
• Start: {start.strftime("%H:%M")}
• End: {end.strftime("%H:%M")}
• Duration: {hours}h {minutes}m

📊 ACTIVITY SUMMARY:
• {conversations} conversations handled
• {activities} total activities

{notes_section}---
View full dashboard: /admin/zero/dashboard
"""

        await self._notify_zero(subject, message)

    async def _notify_zero(self, subject: str, message: str):
        """
        Send notification to ZERO
        For now just logs - you can add actual email sending here
        """
        logger.info(
            f"""
════════════════════════════════════════════════
📧 NOTIFICATION TO ZERO
════════════════════════════════════════════════
Subject: {subject}

{message}
════════════════════════════════════════════════
        """
        )

        # Email sending can be implemented using NotificationHub service
