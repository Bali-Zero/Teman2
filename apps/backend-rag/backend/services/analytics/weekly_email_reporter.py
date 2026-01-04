"""
Weekly Email Activity Reporter

Sends a weekly email every Sunday at 4:00 PM Bali time to zero@balizero.com
with individual team member email activities.
"""

import asyncio
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

BALI_TZ = ZoneInfo("Asia/Makassar")
ADMIN_EMAIL = "zero@balizero.com"
CHECK_TIME_HOUR = 16  # 4:00 PM Bali time
CHECK_TIME_MINUTE = 0
SUNDAY = 6  # datetime.weekday() returns 6 for Sunday


class WeeklyEmailReporter:
    """
    Sends weekly email with team email activity at 4:00 PM Bali time on Sundays.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.task: asyncio.Task | None = None
        self.running = False
        logger.info("✅ WeeklyEmailReporter initialized")

    async def start(self):
        """Start the weekly reporter background task."""
        if self.running:
            logger.warning("⚠️ Weekly reporter already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info(
            f"📧 Weekly email reporter started (sends Sundays at {CHECK_TIME_HOUR}:00 Bali time)"
        )

    async def stop(self):
        """Stop the reporter."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Weekly email reporter stopped")

    async def _scheduler_loop(self):
        """Background loop that checks every minute if it's time to send."""
        last_sent_date = None

        while self.running:
            try:
                now = datetime.now(BALI_TZ)
                today = now.date()

                # Check if it's Sunday at 4:00 PM and we haven't sent today
                if (
                    now.weekday() == SUNDAY
                    and now.hour == CHECK_TIME_HOUR
                    and now.minute == CHECK_TIME_MINUTE
                    and last_sent_date != today
                ):
                    await self._send_weekly_report()
                    last_sent_date = today
                    logger.info(f"📧 Weekly email activity report sent for week ending {today}")

            except Exception as e:
                logger.error(f"❌ Weekly reporter error: {e}")

            # Check every minute
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.info("🛑 Weekly reporter loop cancelled")
                break

    async def _get_team_members(self) -> list[dict]:
        """Get all active team members."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, email, full_name, department
                FROM team_members
                WHERE is_active = TRUE
                ORDER BY department, full_name
                """
            )
            return [dict(row) for row in rows]

    async def _get_email_activity(self, user_id: str, days: int = 7) -> dict:
        """Get email activity for a user over the past N days."""
        async with self.pool.acquire() as conn:
            # Get activity from email_activity_log
            activity_rows = await conn.fetch(
                """
                SELECT
                    operation,
                    COUNT(*) as count
                FROM email_activity_log
                WHERE user_id = $1
                AND created_at >= NOW() - $2::interval
                GROUP BY operation
                """,
                user_id,
                f"{days} days",
            )

            activity = {
                "sent": 0,
                "received": 0,
                "read": 0,
                "replied": 0,
                "forwarded": 0,
                "deleted": 0,
            }

            for row in activity_rows:
                if row["operation"] in activity:
                    activity[row["operation"]] = row["count"]

            # Also check zoho_email_cache for unread count
            unread_count = await conn.fetchval(
                """
                SELECT COUNT(*) FROM zoho_email_cache
                WHERE user_id = $1 AND is_read = FALSE
                """,
                user_id,
            )
            activity["unread"] = unread_count or 0

            return activity

    async def _get_weekly_summary(self) -> dict:
        """Get overall weekly summary statistics."""
        async with self.pool.acquire() as conn:
            week_start = datetime.now(BALI_TZ) - timedelta(days=7)

            # Total emails sent this week
            total_sent = await conn.fetchval(
                """
                SELECT COUNT(*) FROM email_activity_log
                WHERE operation = 'sent' AND created_at >= $1
                """,
                week_start,
            )

            # Total emails received (estimated from cache)
            total_received = await conn.fetchval(
                """
                SELECT COUNT(*) FROM zoho_email_cache
                WHERE cached_at >= $1
                """,
                week_start,
            )

            # Most active user
            most_active = await conn.fetchrow(
                """
                SELECT user_id, COUNT(*) as activity_count
                FROM email_activity_log
                WHERE created_at >= $1
                GROUP BY user_id
                ORDER BY activity_count DESC
                LIMIT 1
                """,
                week_start,
            )

            return {
                "total_sent": total_sent or 0,
                "total_received": total_received or 0,
                "most_active_user": most_active["user_id"] if most_active else None,
                "most_active_count": most_active["activity_count"] if most_active else 0,
            }

    def _build_html_email(
        self, team_activities: list[dict], summary: dict, week_end: datetime
    ) -> str:
        """Build HTML email content."""
        week_start = week_end - timedelta(days=7)
        date_range = f"{week_start.strftime('%d %B')} - {week_end.strftime('%d %B %Y')}"

        # Build individual member activity rows
        member_rows = ""
        for member in team_activities:
            activity = member["activity"]
            total_activity = (
                activity["sent"]
                + activity["received"]
                + activity["replied"]
                + activity["forwarded"]
            )

            # Activity bar (visual indicator)
            bar_width = min(100, total_activity * 5)  # Scale: 20 activities = 100%
            bar_color = "#667eea" if total_activity > 10 else "#94a3b8"

            member_rows += f"""
            <tr>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    <strong>{member.get("full_name", member["email"])}</strong>
                    <br><span style="color: #888; font-size: 12px;">{member.get("department", "Team")}</span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    📤 {activity["sent"]}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    📥 {activity["received"]}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    ↩️ {activity["replied"]}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee; text-align: center;">
                    📬 {activity["unread"]}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #eee;">
                    <div style="background: #f0f0f0; border-radius: 4px; height: 8px; width: 100px;">
                        <div style="background: {bar_color}; border-radius: 4px; height: 8px; width: {bar_width}px;"></div>
                    </div>
                </td>
            </tr>
            """

        # Find most and least active
        active_members = [
            m for m in team_activities if m["activity"]["sent"] + m["activity"]["replied"] > 0
        ]
        inactive_members = [
            m for m in team_activities if m["activity"]["sent"] + m["activity"]["replied"] == 0
        ]

        # Build inactive warning if any
        inactive_warning = ""
        if inactive_members:
            inactive_names = ", ".join(
                [m.get("full_name", m["email"]) for m in inactive_members[:5]]
            )
            inactive_warning = f"""
            <div style="background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px; padding: 15px; margin-top: 20px;">
                <strong>⚠️ Nessuna attività email:</strong> {inactive_names}
                {" e altri " + str(len(inactive_members) - 5) if len(inactive_members) > 5 else ""}
            </div>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 700px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #fff; padding: 20px; border: 1px solid #eee; border-radius: 0 0 8px 8px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: #f8f9fa; padding: 12px; text-align: left; font-size: 13px; }}
                .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; display: flex; gap: 20px; }}
                .summary-card {{ flex: 1; text-align: center; }}
                .summary-number {{ font-size: 28px; font-weight: bold; color: #667eea; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">📊 Weekly Email Activity Report</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">{date_range}</p>
                </div>
                <div class="content">
                    <div class="summary">
                        <div class="summary-card">
                            <div class="summary-number">{summary["total_sent"]}</div>
                            <div style="color: #888;">Email Inviati</div>
                        </div>
                        <div class="summary-card">
                            <div class="summary-number">{summary["total_received"]}</div>
                            <div style="color: #888;">Email Ricevuti</div>
                        </div>
                        <div class="summary-card">
                            <div class="summary-number">{len(active_members)}/{len(team_activities)}</div>
                            <div style="color: #888;">Membri Attivi</div>
                        </div>
                    </div>

                    <h3>👥 Attività Individuale</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Membro</th>
                                <th style="text-align: center;">Inviati</th>
                                <th style="text-align: center;">Ricevuti</th>
                                <th style="text-align: center;">Risposte</th>
                                <th style="text-align: center;">Non Letti</th>
                                <th>Attività</th>
                            </tr>
                        </thead>
                        <tbody>
                            {member_rows if member_rows else '<tr><td colspan="6" style="padding: 20px; text-align: center; color: #888;">Nessun dato disponibile</td></tr>'}
                        </tbody>
                    </table>

                    {inactive_warning}

                    <div class="footer">
                        <p>Zantara Email Management • Bali Zero</p>
                        <p style="font-size: 11px;">Report generato automaticamente ogni domenica alle 16:00 (Bali time)</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    async def _send_weekly_report(self):
        """Send the weekly email activity report."""
        # Check SMTP config
        if not settings.smtp_host or not settings.smtp_user:
            logger.warning("⚠️ SMTP not configured, skipping weekly email report")
            return

        try:
            # Get data
            team_members = await self._get_team_members()
            summary = await self._get_weekly_summary()

            # Get activity for each member
            team_activities = []
            for member in team_members:
                activity = await self._get_email_activity(member["id"])
                team_activities.append({**member, "activity": activity})

            # Build email
            now = datetime.now(BALI_TZ)
            subject = f"📊 Weekly Email Report - {now.strftime('%d/%m/%Y')}"
            html_content = self._build_html_email(team_activities, summary, now)

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.smtp_from or settings.smtp_user
            msg["To"] = ADMIN_EMAIL

            # Attach HTML
            msg.attach(MIMEText(html_content, "html"))

            # Send via SMTP
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
                if settings.smtp_use_tls:
                    server.starttls()
                server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)

            logger.info(f"✅ Weekly email report sent to {ADMIN_EMAIL}")

        except Exception as e:
            logger.error(f"❌ Failed to send weekly email report: {e}")

    async def send_now(self):
        """Send the report immediately (for testing)."""
        await self._send_weekly_report()


# Singleton
_reporter: WeeklyEmailReporter | None = None


def get_weekly_reporter() -> WeeklyEmailReporter | None:
    return _reporter


def init_weekly_reporter(db_pool: asyncpg.Pool) -> WeeklyEmailReporter:
    global _reporter
    _reporter = WeeklyEmailReporter(db_pool)
    return _reporter
