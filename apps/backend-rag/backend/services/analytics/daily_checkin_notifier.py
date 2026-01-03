"""
Daily Check-in Email Notifier

Sends a daily email at 10:00 Bali time to zero@balizero.com
with team check-in status.
"""

import asyncio
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from zoneinfo import ZoneInfo

import asyncpg

from app.core.config import settings

logger = logging.getLogger(__name__)

BALI_TZ = ZoneInfo("Asia/Makassar")
ADMIN_EMAIL = "zero@balizero.com"
CHECK_TIME_HOUR = 10  # 10:00 Bali time
CHECK_TIME_MINUTE = 0


class DailyCheckinNotifier:
    """
    Sends daily email with team check-in status at 10:00 Bali time.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.pool = db_pool
        self.task: asyncio.Task | None = None
        self.running = False
        logger.info("✅ DailyCheckinNotifier initialized")

    async def start(self):
        """Start the daily notifier background task."""
        if self.running:
            logger.warning("⚠️ Daily notifier already running")
            return

        self.running = True
        self.task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"📧 Daily check-in notifier started (sends at {CHECK_TIME_HOUR}:00 Bali time)")

    async def stop(self):
        """Stop the notifier."""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Daily check-in notifier stopped")

    async def _scheduler_loop(self):
        """Background loop that checks every minute if it's time to send."""
        last_sent_date = None

        while self.running:
            try:
                now = datetime.now(BALI_TZ)
                today = now.date()

                # Check if it's 10:00 and we haven't sent today
                if (
                    now.hour == CHECK_TIME_HOUR
                    and now.minute == CHECK_TIME_MINUTE
                    and last_sent_date != today
                ):
                    await self._send_daily_report()
                    last_sent_date = today
                    logger.info(f"📧 Daily check-in email sent for {today}")

            except Exception as e:
                logger.error(f"❌ Daily notifier error: {e}")

            # Check every minute
            await asyncio.sleep(60)

    async def _get_checkin_data(self) -> list[dict]:
        """Get today's check-in data from the database."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    email,
                    action_type,
                    created_at AT TIME ZONE 'Asia/Makassar' as action_time
                FROM team_timesheet
                WHERE DATE(created_at AT TIME ZONE 'Asia/Makassar') = CURRENT_DATE
                ORDER BY created_at DESC
                """
            )

            return [
                {
                    "email": row["email"],
                    "action": row["action_type"],
                    "time": row["action_time"].strftime("%H:%M"),
                }
                for row in rows
            ]

    async def _get_online_status(self) -> list[dict]:
        """Get current online status of all team members."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    email,
                    is_online,
                    last_action_bali
                FROM team_online_status
                ORDER BY is_online DESC, email
                """
            )

            return [
                {
                    "email": row["email"],
                    "online": row["is_online"],
                    "last_action": row["last_action_bali"].strftime("%H:%M") if row["last_action_bali"] else "-",
                }
                for row in rows
            ]

    def _build_html_email(self, checkins: list[dict], online_status: list[dict]) -> str:
        """Build HTML email content."""
        now = datetime.now(BALI_TZ)
        date_str = now.strftime("%A, %d %B %Y")

        # Count online members
        online_count = sum(1 for s in online_status if s["online"])
        total_count = len(online_status)

        # Build online status table
        online_rows = ""
        for s in online_status:
            status_icon = "🟢" if s["online"] else "⚪"
            status_text = "Online" if s["online"] else "Offline"
            online_rows += f"""
            <tr>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{status_icon} {s['email']}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{status_text}</td>
                <td style="padding: 8px; border-bottom: 1px solid #eee;">{s['last_action']}</td>
            </tr>
            """

        # Build checkin activity table
        checkin_rows = ""
        if checkins:
            for c in checkins[:20]:  # Last 20 actions
                action_icon = "🟢" if c["action"] == "clock_in" else "🔴"
                action_text = "Check-in" if c["action"] == "clock_in" else "Check-out"
                checkin_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{c['time']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{c['email']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{action_icon} {action_text}</td>
                </tr>
                """
        else:
            checkin_rows = """
            <tr>
                <td colspan="3" style="padding: 20px; text-align: center; color: #888;">
                    Nessun check-in oggi
                </td>
            </tr>
            """

        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #fff; padding: 20px; border: 1px solid #eee; border-radius: 0 0 8px 8px; }}
                table {{ width: 100%; border-collapse: collapse; }}
                th {{ background: #f8f9fa; padding: 10px; text-align: left; }}
                .summary {{ background: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 20px; }}
                .footer {{ text-align: center; color: #888; font-size: 12px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1 style="margin: 0;">📊 Team Check-in Report</h1>
                    <p style="margin: 10px 0 0 0; opacity: 0.9;">{date_str}</p>
                </div>
                <div class="content">
                    <div class="summary">
                        <h3 style="margin: 0 0 10px 0;">Riepilogo alle {now.strftime('%H:%M')}</h3>
                        <p style="margin: 0; font-size: 24px;">
                            <strong>{online_count}</strong> / {total_count} membri online
                        </p>
                    </div>

                    <h3>👥 Stato Team</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Membro</th>
                                <th>Stato</th>
                                <th>Ultima azione</th>
                            </tr>
                        </thead>
                        <tbody>
                            {online_rows}
                        </tbody>
                    </table>

                    <h3 style="margin-top: 30px;">📋 Attività Oggi</h3>
                    <table>
                        <thead>
                            <tr>
                                <th>Ora</th>
                                <th>Membro</th>
                                <th>Azione</th>
                            </tr>
                        </thead>
                        <tbody>
                            {checkin_rows}
                        </tbody>
                    </table>

                    <div class="footer">
                        <p>Zantara Team Management • Bali Zero</p>
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return html

    async def _send_daily_report(self):
        """Send the daily check-in report email."""
        # Check SMTP config
        if not settings.smtp_host or not settings.smtp_user:
            logger.warning("⚠️ SMTP not configured, skipping daily email")
            return

        try:
            # Get data
            checkins = await self._get_checkin_data()
            online_status = await self._get_online_status()

            # Build email
            now = datetime.now(BALI_TZ)
            subject = f"📊 Team Check-in Report - {now.strftime('%d/%m/%Y')}"
            html_content = self._build_html_email(checkins, online_status)

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

            logger.info(f"✅ Daily check-in email sent to {ADMIN_EMAIL}")

        except Exception as e:
            logger.error(f"❌ Failed to send daily email: {e}")

    async def send_now(self):
        """Send the report immediately (for testing)."""
        await self._send_daily_report()


# Singleton
_notifier: DailyCheckinNotifier | None = None


def get_daily_notifier() -> DailyCheckinNotifier | None:
    return _notifier


def init_daily_notifier(db_pool: asyncpg.Pool) -> DailyCheckinNotifier:
    global _notifier
    _notifier = DailyCheckinNotifier(db_pool)
    return _notifier
