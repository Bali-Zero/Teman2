"""
Team Timesheet Service
Manages team member work hours tracking (clock-in/clock-out)
Timezone: Asia/Makassar (Bali Time, UTC+8)
"""

import asyncio
import contextlib
import json
import logging
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import asyncpg

logger = logging.getLogger(__name__)

# Bali timezone
BALI_TZ = ZoneInfo("Asia/Makassar")


class TeamTimesheetService:
    """
    Team work hours tracking service

    Features:
    - Clock in/out tracking
    - Auto-logout at 18:30 Bali time
    - Daily/weekly/monthly summaries
    - Real-time online status
    - Admin-only dashboard data
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.auto_logout_task: asyncio.Task | None = None
        self.running = False
        logger.info("✅ TeamTimesheetService initialized")

    async def start_auto_logout_monitor(self):
        """Start background task for auto-logout at 18:30"""
        if self.running:
            logger.warning("⚠️ Auto-logout monitor already running")
            return

        self.running = True
        self.auto_logout_task = asyncio.create_task(self._auto_logout_loop())
        logger.info("🕕 Auto-logout monitor started (18:30 Bali time)")

    async def stop_auto_logout_monitor(self):
        """Stop auto-logout monitor"""
        self.running = False
        if self.auto_logout_task:
            self.auto_logout_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.auto_logout_task
        logger.info("🛑 Auto-logout monitor stopped")

    async def _auto_logout_loop(self):
        """Background loop checking for expired sessions every 5 minutes"""
        while self.running:
            try:
                await self._process_auto_logout()
            except Exception as e:
                logger.error(f"❌ Auto-logout check failed: {e}")

            # Check every 5 minutes
            await asyncio.sleep(300)

    async def _process_auto_logout(self):
        """Process auto-logout for sessions past 18:30 Bali time"""
        async with self.pool.acquire() as conn:
            result = await conn.fetch("SELECT * FROM auto_logout_expired_sessions()")

            if result:
                for row in result:
                    logger.info(
                        f"🕕 Auto-logout: {row.get('out_email')} "
                        f"(clocked in at {row.get('out_clock_in_time')}, "
                        f"auto-logged out at {row.get('out_auto_logout_time')})"
                    )

    async def clock_in(
        self, user_id: str, email: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Clock in a team member

        Args:
            user_id: User identifier
            email: User email
            metadata: Optional metadata (ip_address, user_agent)

        Returns:
            Dict with clock-in confirmation and current status
        """
        async with self.pool.acquire() as conn:
            # Check if already clocked in today
            current_status = await self._get_user_current_status(conn, user_id)

            if current_status and current_status["is_online"]:
                bali_time = current_status["last_action_bali"]
                return {
                    "success": False,
                    "error": "already_clocked_in",
                    "message": f"Already clocked in at {bali_time.strftime('%H:%M')} Bali time",
                    "clocked_in_at": bali_time.isoformat(),
                }

            # Insert clock-in
            now = datetime.now(BALI_TZ)
            await conn.execute(
                """
                INSERT INTO team_timesheet (user_id, email, action_type, metadata)
                VALUES ($1, $2, 'clock_in', $3::jsonb)
                """,
                user_id,
                email,
                json.dumps(metadata or {}),
            )

            logger.info(f"🟢 Clock-in: {email} at {now.strftime('%H:%M')} Bali time")

            # NOTE: Admin notification removed - will be replaced by MCP
            logger.info(f"📢 Admin notification: {email} clocked in (MCP pending)")

            return {
                "success": True,
                "action": "clock_in",
                "timestamp": now.isoformat(),
                "bali_time": now.strftime("%H:%M"),
                "message": "Successfully clocked in",
            }

    async def clock_out(
        self, user_id: str, email: str, metadata: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Clock out a team member

        Args:
            user_id: User identifier
            email: User email
            metadata: Optional metadata

        Returns:
            Dict with clock-out confirmation and hours worked
        """
        async with self.pool.acquire() as conn:
            # Check if currently clocked in
            current_status = await self._get_user_current_status(conn, user_id)

            if not current_status or not current_status["is_online"]:
                return {
                    "success": False,
                    "error": "not_clocked_in",
                    "message": "Not currently clocked in",
                }

            # Insert clock-out
            now = datetime.now(BALI_TZ)
            await conn.execute(
                """
                INSERT INTO team_timesheet (user_id, email, action_type, metadata)
                VALUES ($1, $2, 'clock_out', $3::jsonb)
                """,
                user_id,
                email,
                json.dumps(metadata or {}),
            )

            # Calculate hours worked
            clock_in_time = current_status["last_action_bali"]
            # Ensure clock_in_time is timezone-aware
            if clock_in_time.tzinfo is None:
                clock_in_time = clock_in_time.replace(tzinfo=BALI_TZ)
            duration = now - clock_in_time
            hours_worked = duration.total_seconds() / 3600

            logger.info(
                f"🔴 Clock-out: {email} at {now.strftime('%H:%M')} Bali time "
                f"({hours_worked:.2f}h worked)"
            )

            # NOTE: Admin notification removed - will be replaced by MCP
            logger.info(
                f"📢 Admin notification: {email} clocked out, worked {hours_worked:.2f}h (MCP pending)"
            )

            return {
                "success": True,
                "action": "clock_out",
                "timestamp": now.isoformat(),
                "bali_time": now.strftime("%H:%M"),
                "clock_in_time": clock_in_time.isoformat(),
                "hours_worked": round(hours_worked, 2),
                "message": f"Successfully clocked out. Worked {hours_worked:.2f} hours",
            }

    async def get_my_status(self, user_id: str) -> dict[str, Any]:
        """
        Get current user's work status

        Args:
            user_id: User identifier

        Returns:
            Dict with current status, today's hours, and week summary
        """
        async with self.pool.acquire() as conn:
            # Current status
            status = await self._get_user_current_status(conn, user_id)

            # Today's hours
            today_bali = datetime.now(BALI_TZ).date()
            today_hours = await conn.fetchrow(
                """
                SELECT hours_worked
                FROM daily_work_hours
                WHERE user_id = $1 AND work_date = $2
                """,
                user_id,
                today_bali,
            )

            # This week's summary
            week_summary = await conn.fetchrow(
                """
                SELECT total_hours, days_worked
                FROM weekly_work_summary
                WHERE user_id = $1
                  AND week_start = DATE_TRUNC('week', $2::date)
                """,
                user_id,
                today_bali,
            )

            return {
                "user_id": user_id,
                "is_online": status["is_online"] if status else False,
                "last_action": status["last_action_bali"].isoformat() if status else None,
                "last_action_type": status["action_type"] if status else None,
                "today_hours": float(today_hours["hours_worked"]) if today_hours else 0.0,
                "week_hours": float(week_summary["total_hours"]) if week_summary else 0.0,
                "week_days": int(week_summary["days_worked"]) if week_summary else 0,
            }

    async def get_team_online_status(self) -> list[dict[str, Any]]:
        """
        Get current online status of all team members (ADMIN ONLY)

        Returns:
            List of user statuses
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM team_online_status ORDER BY email")

            return [
                {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "is_online": row["is_online"],
                    "last_action": row["last_action_bali"].isoformat(),
                    "last_action_type": row["action_type"],
                }
                for row in rows
            ]

    async def get_daily_hours(self, date: datetime | None = None) -> list[dict[str, Any]]:
        """
        Get work hours for a specific date (ADMIN ONLY)

        Args:
            date: Target date (defaults to today in Bali time)

        Returns:
            List of user work hours for the date
        """
        if date is None:
            date = datetime.now(BALI_TZ).date()
        elif isinstance(date, datetime):
            date = date.date()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM daily_work_hours
                WHERE work_date = $1
                ORDER BY hours_worked DESC
                """,
                date,
            )

            return [
                {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "date": row["work_date"].isoformat(),
                    "clock_in": row["clock_in_bali"].strftime("%H:%M"),
                    "clock_out": row["clock_out_bali"].strftime("%H:%M"),
                    "hours_worked": float(row["hours_worked"]),
                }
                for row in rows
            ]

    async def get_weekly_summary(self, week_start: datetime | None = None) -> list[dict[str, Any]]:
        """
        Get weekly work summary (ADMIN ONLY)

        Args:
            week_start: Start of week (defaults to current week)

        Returns:
            List of user weekly summaries
        """
        if week_start is None:
            today = datetime.now(BALI_TZ).date()
            week_start = today - timedelta(days=today.weekday())
        elif isinstance(week_start, datetime):
            week_start = week_start.date()

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM weekly_work_summary
                WHERE week_start = DATE_TRUNC('week', $1::date)
                ORDER BY total_hours DESC
                """,
                week_start,
            )

            return [
                {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "week_start": row["week_start"].isoformat(),
                    "days_worked": int(row["days_worked"]),
                    "total_hours": float(row["total_hours"]),
                    "avg_hours_per_day": float(row["avg_hours_per_day"]),
                }
                for row in rows
            ]

    async def get_monthly_summary(
        self, month_start: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Get monthly work summary (ADMIN ONLY)

        Args:
            month_start: Start of month (defaults to current month)

        Returns:
            List of user monthly summaries
        """
        if month_start is None:
            today = datetime.now(BALI_TZ).date()
            month_start = today.replace(day=1)
        elif isinstance(month_start, datetime):
            month_start = month_start.date().replace(day=1)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM monthly_work_summary
                WHERE month_start = DATE_TRUNC('month', $1::date)
                ORDER BY total_hours DESC
                """,
                month_start,
            )

            return [
                {
                    "user_id": row["user_id"],
                    "email": row["email"],
                    "month_start": row["month_start"].isoformat(),
                    "days_worked": int(row["days_worked"]),
                    "total_hours": float(row["total_hours"]),
                    "avg_hours_per_day": float(row["avg_hours_per_day"]),
                }
                for row in rows
            ]

    async def export_timesheet_csv(self, start_date: datetime, end_date: datetime) -> str:
        """
        Export timesheet data as CSV (ADMIN ONLY)

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            CSV string
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM daily_work_hours
                WHERE work_date BETWEEN $1 AND $2
                ORDER BY work_date DESC, email
                """,
                start_date.date() if isinstance(start_date, datetime) else start_date,
                end_date.date() if isinstance(end_date, datetime) else end_date,
            )

        # Build CSV
        csv_lines = ["Email,Date,Clock In,Clock Out,Hours Worked"]
        for row in rows:
            csv_lines.append(
                f"{row['email']},"
                f"{row['work_date'].isoformat()},"
                f"{row['clock_in_bali'].strftime('%H:%M')},"
                f"{row['clock_out_bali'].strftime('%H:%M')},"
                f"{row['hours_worked']}"
            )

        return "\n".join(csv_lines)

    async def _get_user_current_status(
        self, conn: asyncpg.Connection, user_id: str
    ) -> dict[str, Any] | None:
        """Get user's current online/offline status"""
        row = await conn.fetchrow("SELECT * FROM team_online_status WHERE user_id = $1", user_id)

        if not row:
            return None

        return {
            "user_id": row["user_id"],
            "email": row["email"],
            "last_action_bali": row["last_action_bali"],
            "action_type": row["action_type"],
            "is_online": row["is_online"],
        }


# Singleton instance
_timesheet_service: TeamTimesheetService | None = None


def get_timesheet_service() -> TeamTimesheetService | None:
    """Get the global TeamTimesheetService instance"""
    return _timesheet_service


def init_timesheet_service(db_pool: asyncpg.Pool) -> TeamTimesheetService:
    """Initialize the global TeamTimesheetService instance"""
    global _timesheet_service
    _timesheet_service = TeamTimesheetService(db_pool)
    return _timesheet_service
