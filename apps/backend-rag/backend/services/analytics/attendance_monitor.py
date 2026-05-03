"""
Attendance Monitor Service
Responsibility: Late check-in alerts and consecutive-absence detection.

Two automations:
1. Late check-in alert  — triggered immediately when clock_in arrives after 09:30 Bali time.
   Sends a friendly email to the member (from zantara@balizero.com) + CC to zero@balizero.com.

2. Absent alert — called daily at 10:00 Bali time (from scheduler or daily_checkin_notifier).
   Finds members with no clock_in for 2+ consecutive working days (Mon–Fri) and sends a
   single summary email to zero@balizero.com.

Integration points:
- check_late_checkin()  called from TeamTimesheetService.clock_in() after saving the record.
- check_absent_members() called from DailyCheckinNotifier._send_daily_report() or scheduler loop.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import secrets
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import httpx

from backend.app.utils.logging_utils import get_logger

if TYPE_CHECKING:
    import asyncpg

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BALI_TZ = ZoneInfo("Asia/Makassar")

# Two-stage late policy (Bali time):
#   [start, GRACE)          → on time, no email
#   [GRACE, INCIDENT)       → gentle reminder email only (no incident, no escalation)
#   [INCIDENT, ...)         → opens a late-incident record with full escalation flow
LATE_GRACE_HOUR: int = 9
LATE_GRACE_MINUTE: int = 30  # 09:30 — below this nothing happens

LATE_INCIDENT_HOUR: int = 9
LATE_INCIDENT_MINUTE: int = 40  # 09:40 — at/after this an incident is opened

# Legacy aliases kept so existing imports / tests do not break.
LATE_THRESHOLD_HOUR: int = LATE_GRACE_HOUR
LATE_THRESHOLD_MINUTE: int = LATE_GRACE_MINUTE

ADMIN_EMAIL: str = "zero@balizero.com"

# These emails are exempt from late-arrival alerts (management / remote workers)
LATE_EXEMPT_EMAILS: frozenset[str] = frozenset(
    {
        "zero@balizero.com",
        "ruslana@balizero.com",
        "veronika@balizero.com",
    }
)

_EMAIL_API_URL: str = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY: str = os.getenv("NUZANTARA_API_KEY", "")

# Number of consecutive working days without clock-in before triggering an alert
ABSENT_THRESHOLD_DAYS: int = 2

# ---------------------------------------------------------------------------
# Late-incident escalation parameters
# ---------------------------------------------------------------------------

# How long an incident may stay in each waiting state before being promoted.
# Counted in *working hours* (Mon–Fri 00:00–23:59 Bali time, weekends skipped).
INCIDENT_REMINDER_AFTER_WORKING_HOURS: int = 24
INCIDENT_ULTIMATUM_AFTER_WORKING_HOURS: int = 24  # additional 24h after reminder

# State machine values — kept as plain strings to mirror the DB CHECK constraint.
STATE_AWAITING_REPLY: str = "AWAITING_REPLY"
STATE_REMINDER_SENT: str = "REMINDER_SENT"
STATE_ESCALATED: str = "ESCALATED"
STATE_RESOLVED: str = "RESOLVED"
STATE_RESOLVED_LATE: str = "RESOLVED_LATE"

# Public reply form on the HR portal. Token is appended at send time.
HR_REPLY_BASE_URL: str = os.getenv(
    "HR_LATE_REPLY_BASE_URL",
    "https://kita.balizero.com/hr/late-reply",
)

# Telegram digest target — Zero's personal chat with @Balizerobot.
# The fallback chat_id 1125336968 was verified live on 2026-04-07 by hitting
# Telegram getMe + sendMessage from inside the production container; CLAUDE.md
# §14 previously documented 413539912 which is unreachable ("chat not found").
# The TELEGRAM_OWNER_CHAT_ID env var still takes precedence if set.
TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_DIGEST_CHAT_ID: str = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")

# Telegram sendMessage hard limit is 4096 chars; leave headroom for the
# "(part N/M)\n" header that chunked messages get.
TELEGRAM_MAX_MSG_LEN: int = 4000

# Manager routing: which supervisor to CC on the ultimatum email.
# - tax team (any *.tax@balizero.com) -> Veronika
# - dea / rina                          -> Ruslana
# - everyone else                       -> only zero@ in CC
TAX_MANAGER_EMAIL: str = "veronika@balizero.com"
RUSLANA_REPORTS: frozenset[str] = frozenset(
    {"dea@balizero.com", "rina@balizero.com"},
)
RUSLANA_EMAIL: str = "ruslana@balizero.com"

# Background scheduler intervals.
ESCALATION_SCAN_INTERVAL_SECONDS: int = 15 * 60  # every 15 minutes
DAILY_DIGEST_HOUR: int = 18  # 18:00 WITA
DAILY_DIGEST_MINUTE: int = 0
CLOCKIN_REMINDER_HOUR: int = 9
CLOCKIN_REMINDER_MINUTE: int = 15


def resolve_responsible_manager(email: str) -> str | None:
    """
    Return the supervisor email to CC on the ultimatum, or None if there is
    no specific supervisor (in which case only ``zero@balizero.com`` is CC'd).

    Routing rules (per Zero, 2026-04-07):
        - *.tax@balizero.com  -> veronika@balizero.com
        - dea@ / rina@        -> ruslana@balizero.com
        - everyone else       -> None (zero@ only)
    """
    normalized = email.lower().strip()
    if normalized in RUSLANA_REPORTS:
        return RUSLANA_EMAIL
    local_part = normalized.split("@", 1)[0]
    if local_part.endswith(".tax"):
        return TAX_MANAGER_EMAIL
    return None


# ---------------------------------------------------------------------------
# Shared email shell
# ---------------------------------------------------------------------------


def _chunk_telegram_message(
    message: str,
    *,
    max_len: int = TELEGRAM_MAX_MSG_LEN,
) -> list[str]:
    """
    Split a Telegram message into ≤ ``max_len`` chunks on newline boundaries.

    Returns a list with at least one element. If the input is short enough,
    the list contains the original message unchanged. If splitting is needed,
    each chunk is prefixed with a "(part N/M)\\n" header so the recipient can
    tell what they are reading.

    Lines longer than ``max_len`` are hard-broken at ``max_len`` characters —
    this should never happen for the digest (rows are short) but it stops the
    function returning a chunk that would itself be rejected by Telegram.
    """
    if len(message) <= max_len:
        return [message]

    # First pass: greedy pack lines into chunks ≤ max_len.
    raw_chunks: list[str] = []
    current: list[str] = []
    current_len: int = 0
    for raw_line in message.split("\n"):
        # Hard-break a line that on its own exceeds the limit.
        line_pieces: list[str] = (
            [raw_line[i : i + max_len] for i in range(0, len(raw_line), max_len)]
            if len(raw_line) > max_len
            else [raw_line]
        )
        for line in line_pieces:
            # +1 for the newline that joins lines inside a chunk.
            extra = len(line) + (1 if current else 0)
            if current_len + extra > max_len:
                raw_chunks.append("\n".join(current))
                current = [line]
                current_len = len(line)
            else:
                current.append(line)
                current_len += extra
    if current:
        raw_chunks.append("\n".join(current))

    # Second pass: prefix each chunk with "(part N/M)" header.
    total = len(raw_chunks)
    return [f"(part {i + 1}/{total})\n{chunk}" for i, chunk in enumerate(raw_chunks)]


def _render_email_shell(
    *,
    header_title: str,
    accent: str,
    body_html: str,
) -> str:
    """
    Shared HTML wrapper for all attendance emails.

    Keeps a single source of truth for colors, typography, and layout so the
    gentle reminder, incident email, 24h reminder and ultimatum all look like
    part of the same conversation.
    """
    return f"""<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 560px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .header {{
            background: {accent};
            color: white;
            padding: 28px 32px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 600;
        }}
        .content {{
            padding: 32px;
            color: #333333;
            line-height: 1.7;
            font-size: 15px;
        }}
        .footer {{
            text-align: center;
            padding: 20px 32px;
            color: #888888;
            font-size: 12px;
            border-top: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{header_title}</h1>
        </div>
        <div class="content">{body_html}
            <p style="margin-top: 24px; color:#888; font-size:12px;">
                Bali Zero Management · Zantara CRM
            </p>
        </div>
        <div class="footer">
            Bali Zero · Zantara Team Management
        </div>
    </div>
</body>
</html>"""


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AttendanceMonitor:
    """
    Monitors team attendance and dispatches email alerts for:
    - Late check-ins (gentle reminder + incident escalation state machine)
    - Consecutive absences (2+ working days without any clock-in)

    Owns two long-running background tasks (started by ``start_schedulers``):
    - escalation_scan_task: every 15 minutes, calls ``run_escalation_scan``.
    - daily_digest_task:    every day at 18:00 WITA, calls
                            ``send_daily_telegram_digest``.

    The ``check_late_checkin`` and ``check_absent_members`` methods can still
    be invoked directly (e.g. from ``TeamTimesheetService.clock_in``).
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.pool = db_pool
        self._escalation_task: asyncio.Task | None = None
        self._digest_task: asyncio.Task | None = None
        self._running: bool = False
        logger.info("AttendanceMonitor initialized")

    # ------------------------------------------------------------------
    # Background scheduler lifecycle
    # ------------------------------------------------------------------

    async def start_schedulers(self) -> None:
        """Start the escalation-scan and daily-digest background loops."""
        if self._running:
            logger.warning("AttendanceMonitor: schedulers already running")
            return
        self._running = True
        self._escalation_task = asyncio.create_task(
            self._escalation_loop(),
            name="attendance-escalation-loop",
        )
        self._digest_task = asyncio.create_task(
            self._daily_digest_loop(),
            name="attendance-daily-digest-loop",
        )
        logger.info(
            "AttendanceMonitor: schedulers started "
            "(escalation every %ds, digest at %02d:%02d WITA)",
            ESCALATION_SCAN_INTERVAL_SECONDS,
            DAILY_DIGEST_HOUR,
            DAILY_DIGEST_MINUTE,
        )

    async def stop_schedulers(self) -> None:
        """Stop background loops cleanly. Safe to call multiple times."""
        self._running = False
        for task in (self._escalation_task, self._digest_task):
            if task is None:
                continue
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._escalation_task = None
        self._digest_task = None
        logger.info("AttendanceMonitor: schedulers stopped")

    async def _escalation_loop(self) -> None:
        """
        Run ``run_escalation_scan`` every ESCALATION_SCAN_INTERVAL_SECONDS.

        Logs an INFO heartbeat on every iteration (with worker pid + loop id)
        so silent failures of the scheduling loop become visible in production
        — even on iterations where the scan finds nothing to promote. Without
        this heartbeat, ``run_escalation_scan`` only logs at DEBUG when
        ``counters`` is empty, making it impossible to tell from logs whether
        the loop is alive or dead.
        """
        loop_id = id(asyncio.get_running_loop())
        pid = os.getpid()
        iteration = 0
        logger.info(
            "AttendanceMonitor._escalation_loop: STARTED pid=%d loop_id=%d "
            "interval=%ds",
            pid,
            loop_id,
            ESCALATION_SCAN_INTERVAL_SECONDS,
        )
        while self._running:
            iteration += 1
            try:
                # PANOPTICON: Clock-in reminder at 09:15 WITA
                now_bali = datetime.now(BALI_TZ)
                if (
                    now_bali.hour == CLOCKIN_REMINDER_HOUR
                    and now_bali.minute >= CLOCKIN_REMINDER_MINUTE
                    and now_bali.minute < CLOCKIN_REMINDER_MINUTE + 15
                    and now_bali.weekday() < 5  # Mon-Fri only
                ):
                    if not getattr(self, "_reminder_sent_date", None) == now_bali.date():
                        await self.send_clockin_reminder()
                        self._reminder_sent_date = now_bali.date()

                counters = await self.run_escalation_scan()
                logger.info(
                    "AttendanceMonitor._escalation_loop: heartbeat "
                    "iter=%d pid=%d counters=%s",
                    iteration,
                    pid,
                    counters,
                )
            except Exception as exc:
                logger.exception(
                    "AttendanceMonitor._escalation_loop: scan failed iter=%d — %s",
                    iteration,
                    exc,
                )
            try:
                await asyncio.sleep(ESCALATION_SCAN_INTERVAL_SECONDS)
            except asyncio.CancelledError:
                logger.info(
                    "AttendanceMonitor._escalation_loop: cancelled iter=%d pid=%d",
                    iteration,
                    pid,
                )
                break
        logger.warning(
            "AttendanceMonitor._escalation_loop: EXITED pid=%d iter=%d _running=%s",
            pid,
            iteration,
            self._running,
        )

    async def _daily_digest_loop(self) -> None:
        """
        Sleep until the next 18:00 WITA, send the digest, repeat.

        On startup the loop computes the next digest time and sleeps until
        then — so deploys at e.g. 09:00 WITA wait until 18:00 same day, and
        deploys at 18:30 wait until 18:00 next day.
        """
        loop_id = id(asyncio.get_running_loop())
        pid = os.getpid()
        logger.info(
            "AttendanceMonitor._daily_digest_loop: STARTED pid=%d loop_id=%d",
            pid,
            loop_id,
        )
        while self._running:
            now = datetime.now(BALI_TZ)
            target = now.replace(
                hour=DAILY_DIGEST_HOUR,
                minute=DAILY_DIGEST_MINUTE,
                second=0,
                microsecond=0,
            )
            if target <= now:
                target = target + timedelta(days=1)
            sleep_seconds = (target - now).total_seconds()
            logger.info(
                "AttendanceMonitor._daily_digest_loop: next digest in %.0fs (at %s) pid=%d",
                sleep_seconds,
                target.isoformat(),
                pid,
            )
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                logger.info(
                    "AttendanceMonitor._daily_digest_loop: cancelled pid=%d", pid,
                )
                break
            try:
                await self.send_daily_telegram_digest()
            except Exception as exc:
                logger.exception(
                    "AttendanceMonitor._daily_digest_loop: digest failed pid=%d — %s",
                    pid,
                    exc,
                )
        logger.warning(
            "AttendanceMonitor._daily_digest_loop: EXITED pid=%d _running=%s",
            pid,
            self._running,
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def check_late_checkin(self, email: str, checkin_time: datetime) -> None:
        """
        Called immediately when a clock_in event is recorded.

        Two-stage policy (Bali time):
          * clock_in < 09:30               → nothing (on time)
          * 09:30 <= clock_in < 09:40      → gentle reminder only (Indonesian, no incident)
          * clock_in >= 09:40              → incident opened (handled by commit 2)

        Skips members in LATE_EXEMPT_EMAILS (zero, ruslana, veronika) and members
        who have an approved leave request covering today.

        Args:
            email: The team member's email address.
            checkin_time: The clock-in datetime, already expressed in Bali timezone.
        """
        # Skip exempt members (management / remote workers).
        if email.lower() in LATE_EXEMPT_EMAILS:
            logger.debug("check_late_checkin: %s is exempt — skipping", email)
            return

        grace_start = checkin_time.replace(
            hour=LATE_GRACE_HOUR,
            minute=LATE_GRACE_MINUTE,
            second=0,
            microsecond=0,
        )
        incident_start = checkin_time.replace(
            hour=LATE_INCIDENT_HOUR,
            minute=LATE_INCIDENT_MINUTE,
            second=0,
            microsecond=0,
        )

        # On time — below grace window.
        if checkin_time < grace_start:
            logger.debug(
                "check_late_checkin: %s checked in at %s — on time, skipping",
                email,
                checkin_time.strftime("%H:%M"),
            )
            return

        # Skip if there is an approved leave request covering today.
        today: date = checkin_time.date()
        if await self._has_approved_leave(email, today):
            logger.info(
                "check_late_checkin: %s has approved leave for %s — skipping late alert",
                email,
                today,
            )
            return

        member = await self._get_member_by_email(email)
        full_name: str = member["full_name"] if member else email
        checkin_str = checkin_time.strftime("%H:%M")

        # Grace window: 09:30 ≤ clock_in < 09:40 → gentle reminder only.
        if checkin_time < incident_start:
            logger.info(
                "check_late_checkin: %s in grace window at %s — sending gentle reminder",
                email,
                checkin_str,
            )
            await self._send_gentle_reminder(email, full_name, checkin_str)
            return

        # Incident window: clock_in ≥ 09:40 — open or update an incident row
        # and send the mandatory-reply email with a signed reply link.
        logger.info(
            "check_late_checkin: %s in incident window at %s — opening incident",
            email,
            checkin_str,
        )
        await self._send_incident_opened_notification(email, full_name, checkin_time)

    async def check_absent_members(self) -> None:
        """
        Called daily at 10:00 Bali time.

        Finds every active team member whose last clock_in date is at least
        ABSENT_THRESHOLD_DAYS working days before today (or who has never
        clocked in).  Sends a single summary email to zero@balizero.com.
        """
        today: date = datetime.now(BALI_TZ).date()
        logger.info("check_absent_members: running absence scan for %s", today)

        active_members = await self._get_active_members()
        if not active_members:
            logger.info("check_absent_members: no active members found — skipping")
            return

        absent_members: list[dict] = []

        for member in active_members:
            member_email: str = member["email"]
            last_date = await self._get_last_clockin_date(member_email)

            if last_date is None:
                # Never clocked in — treat as infinitely absent.
                absent_members.append(
                    {
                        "email": member_email,
                        "full_name": member["full_name"],
                        "absent_days": None,  # "unknown / never clocked in"
                        "last_seen": "mai",
                    },
                )
                logger.debug("check_absent_members: %s has never clocked in", member_email)
                continue

            working_days_absent = await self._count_working_days_since(last_date, today)

            if working_days_absent >= ABSENT_THRESHOLD_DAYS:
                absent_members.append(
                    {
                        "email": member_email,
                        "full_name": member["full_name"],
                        "absent_days": working_days_absent,
                        "last_seen": last_date.strftime("%d/%m/%Y"),
                    },
                )
                logger.info(
                    "check_absent_members: %s absent for %d working day(s) (last seen %s)",
                    member_email,
                    working_days_absent,
                    last_date,
                )

        if not absent_members:
            logger.info(
                "check_absent_members: no absences >= %d working days found for %s",
                ABSENT_THRESHOLD_DAYS,
                today,
            )
            return

        await self._send_absent_alert(absent_members)

    async def get_logged_in_not_clocked(self) -> list[dict]:
        """Find team members who logged in today but haven't clocked in."""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT a.email
                FROM auth_audit_log a
                WHERE a.timestamp AT TIME ZONE 'Asia/Makassar' >= (NOW() AT TIME ZONE 'Asia/Makassar')::date
                  AND a.success = true
                  AND a.email LIKE '%@balizero.com'
                  AND a.email NOT IN (
                      SELECT email FROM team_timesheet
                      WHERE action_type = 'clock_in'
                        AND timestamp AT TIME ZONE 'Asia/Makassar' >= (NOW() AT TIME ZONE 'Asia/Makassar')::date
                  )
                ORDER BY a.email
                """,
            )
            return [dict(r) for r in rows]

    async def send_clockin_reminder(self) -> None:
        """Send Telegram alert to Zero listing members who logged in but haven't clocked in."""
        missing = await self.get_logged_in_not_clocked()

        if not missing:
            logger.info("Clock-in reminder: all logged-in members have clocked in")
            return

        names = [m["email"].split("@")[0].replace(".", " ").title() for m in missing]
        text = (
            f"\u23f0 *Clock-In Reminder*\n\n"
            f"{len(missing)} membri loggati ma senza clock-in:\n"
            + "\n".join(f"\u2022 {name}" for name in names)
            + "\n\n_PANOPTICON auto-alert_"
        )

        telegram_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")

        if not telegram_token:
            logger.warning("Clock-in reminder: TELEGRAM_BOT_TOKEN not set")
            return

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.telegram.org/bot{telegram_token}/sendMessage",
                    json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
                )
                logger.info("Clock-in reminder sent: %d members missing", len(missing))
        except httpx.HTTPError as e:
            logger.warning("Clock-in reminder send failed (HTTP): %s", e)
        except Exception as e:
            logger.exception("Clock-in reminder send failed: %s", e)

    # ------------------------------------------------------------------
    # Private DB helpers
    # ------------------------------------------------------------------

    async def _has_approved_leave(self, email: str, check_date: date) -> bool:
        """
        Returns True if the team member has an approved leave request that covers
        check_date (i.e. start_date <= check_date <= end_date).

        Joins team_members → hr_employees → hr_leave_requests.
        Returns False if the member has no HR employee record or no matching leave.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 1
                FROM hr_leave_requests lr
                JOIN hr_employees emp ON emp.id = lr.employee_id
                JOIN team_members tm ON tm.id = emp.team_member_id
                WHERE tm.email = $1
                  AND lr.status = 'approved'
                  AND lr.start_date <= $2
                  AND lr.end_date   >= $2
                LIMIT 1
                """,
                email,
                check_date,
            )
        return row is not None

    async def _get_active_members(self) -> list[dict]:
        """
        Returns a list of {email, full_name} for all is_active=TRUE members
        from the team_members table.
        """
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT email, full_name
                FROM team_members
                WHERE is_active = TRUE
                ORDER BY full_name
                """,
            )
        return [{"email": row["email"], "full_name": row["full_name"]} for row in rows]

    async def _get_member_by_email(self, email: str) -> dict | None:
        """
        Returns {email, full_name} for a single member, or None if not found.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT email, full_name
                FROM team_members
                WHERE email = $1
                """,
                email,
            )
        if row is None:
            return None
        return {"email": row["email"], "full_name": row["full_name"]}

    async def _get_last_clockin_date(self, email: str) -> date | None:
        """
        Returns the calendar date (in Bali timezone) of the most recent
        clock_in action for the given email, or None if no record exists.
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    DATE(created_at AT TIME ZONE 'Asia/Makassar') AS last_date
                FROM team_timesheet
                WHERE email = $1
                  AND action_type = 'clock_in'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                email,
            )
        if row is None or row["last_date"] is None:
            return None
        return row["last_date"]

    # ------------------------------------------------------------------
    # Working-day counter (pure logic, kept async for interface symmetry)
    # ------------------------------------------------------------------

    async def _count_working_days_since(self, last_date: date, today: date) -> int:
        """
        Count Monday–Friday days strictly between last_date (exclusive) and
        today (inclusive).

        Examples
        --------
        last_date=Monday, today=Wednesday  → 2  (Tue + Wed)
        last_date=Friday,  today=Monday    → 1  (Mon; weekend skipped)
        last_date=today                    → 0
        """
        if last_date >= today:
            return 0

        count: int = 0
        cursor: date = last_date + timedelta(days=1)
        while cursor <= today:
            if cursor.weekday() < 5:  # 0=Mon … 4=Fri
                count += 1
            cursor += timedelta(days=1)
        return count

    # ------------------------------------------------------------------
    # Email senders
    # ------------------------------------------------------------------

    async def _post_email(
        self,
        *,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
        log_tag: str = "email",
    ) -> None:
        """
        Internal helper: POST a rendered email to the notifications API.

        Centralises the httpx call + structured logging so callers only worry
        about subject + body.

        ``cc`` is a single comma-separated string per the SendEmailRequest
        schema in backend.app.modules.notifications.router (it does NOT accept
        a list). Callers with multiple recipients must join them themselves.
        """
        payload: dict = {"to": to, "subject": subject, "body": html_body}
        if cc:
            payload["cc"] = cc

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _EMAIL_API_URL,
                    headers={"X-API-Key": _EMAIL_API_KEY},
                    json=payload,
                )
                response.raise_for_status()
            logger.info(
                "%s: sent to %s (cc=%s) subject=%r",
                log_tag,
                to,
                cc,
                subject,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "%s: HTTP %s sending to %s — %s",
                log_tag,
                exc.response.status_code,
                to,
                exc.response.text,
            )
        except (httpx.TimeoutException, httpx.ConnectError, OSError) as exc:
            logger.warning(
                "%s: network error sending to %s — %s",
                log_tag,
                to,
                exc,
            )
        except Exception as exc:
            logger.exception(
                "%s: failed to send to %s — %s",
                log_tag,
                to,
                exc,
            )

    async def _send_gentle_reminder(
        self,
        email: str,
        full_name: str,
        checkin_time: str,
    ) -> None:
        """
        Stage 1 — grace window (09:30 ≤ clock_in < 09:40).

        Sends a friendly 1-to-1 reminder in Indonesian. No CC, no incident,
        no escalation. Purely informational.
        """
        first_name: str = full_name.split()[0] if full_name else email
        subject: str = f"Pengingat check-in — {first_name}, {checkin_time}"

        html_body: str = _render_email_shell(
            header_title=f"Halo {first_name} 👋",
            accent="#f6ad55",  # amber — soft
            body_html=f"""
            <p>
                Check-in kamu hari ini tercatat pukul
                <strong>{checkin_time} WITA</strong>, sedikit melewati jam mulai 09:30.
            </p>
            <p>
                Ini hanya pengingat ramah — tidak ada tindakan yang perlu kamu lakukan.
                Mohon usahakan check-in sebelum jam <strong>09:30</strong> mulai besok ya. 🙏
            </p>
            <p style="margin-top: 18px; color:#666; font-size:13px;">
                Jika kamu butuh cuti atau izin, silakan ajukan leave request melalui portal HR.
            </p>
            """,
        )

        # No CC — this is strictly 1-to-1.
        await self._post_email(
            to=email,
            subject=subject,
            html_body=html_body,
            cc=None,
            log_tag="gentle_reminder",
        )

    async def _send_incident_opened_notification(
        self,
        email: str,
        full_name: str,
        checkin_time_dt: datetime,
    ) -> None:
        """
        Stage 2 — incident window (clock_in ≥ 09:40).

        1. Insert a row in ``attendance_late_incidents`` (state=AWAITING_REPLY)
           with a freshly generated reply_token.
        2. Send a 1-to-1 Indonesian email asking for a mandatory reply, with a
           signed reply link the team member can use without authentication.

        If an incident already exists for (email, late_date) the insert is a
        no-op (UNIQUE constraint) and no second email is sent — this protects
        against duplicate clock_in events on the same day.
        """
        first_name: str = full_name.split()[0] if full_name else email
        checkin_str: str = checkin_time_dt.strftime("%H:%M")
        late_date: date = checkin_time_dt.date()
        reply_token: str = secrets.token_urlsafe(32)
        manager_email: str | None = resolve_responsible_manager(email)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO attendance_late_incidents (
                    email, full_name, late_date, checkin_time,
                    state, first_email_sent_at, reply_token,
                    responsible_manager_email
                )
                VALUES ($1, $2, $3, $4, $5, NOW(), $6, $7)
                ON CONFLICT (email, late_date) DO NOTHING
                RETURNING id, reply_token
                """,
                email,
                full_name,
                late_date,
                checkin_time_dt,
                STATE_AWAITING_REPLY,
                reply_token,
                manager_email,
            )

        if row is None:
            logger.info(
                "_send_incident_opened: incident already exists for %s on %s — "
                "skipping duplicate email",
                email,
                late_date,
            )
            return

        incident_id = row["id"]
        token = row["reply_token"]
        reply_link = f"{HR_REPLY_BASE_URL}/{incident_id}?token={token}"

        subject: str = f"Keterlambatan hari ini — {first_name}, {checkin_str}"

        html_body: str = _render_email_shell(
            header_title=f"Halo {first_name} — Keterlambatan tercatat",
            accent="#ed8936",
            body_html=f"""
            <p>
                Check-in kamu hari ini tercatat pukul
                <strong>{checkin_str} WITA</strong>, setelah batas 09:40.
            </p>
            <div style="background:#fffaf0; border-left:4px solid #ed8936;
                        padding:12px 16px; border-radius:0 8px 8px 0;
                        margin:20px 0; font-size:14px;">
                Mohon jelaskan <strong>alasan keterlambatan hari ini</strong>
                melalui formulir berikut. Balasan bersifat <strong>wajib</strong>.
            </div>
            <p style="text-align:center; margin:24px 0;">
                <a href="{reply_link}"
                   style="display:inline-block; background:#ed8936; color:white;
                          text-decoration:none; padding:12px 26px; border-radius:6px;
                          font-weight:600; font-size:15px;">
                    Kirim alasan keterlambatan →
                </a>
            </p>
            <p style="font-size:13px; color:#777;">
                Jika keterlambatan karena alasan yang sudah direncanakan (cuti, izin,
                dinas luar), pastikan leave request sudah diajukan dan disetujui sebelumnya.
            </p>
            <p style="margin-top: 16px; color: #555;">
                Terima kasih atas perhatian dan kerjasamanya. 🙏
            </p>
            """,
        )

        await self._post_email(
            to=email,
            subject=subject,
            html_body=html_body,
            cc=None,
            log_tag="incident_opened",
        )

    # ------------------------------------------------------------------
    # Escalation state machine
    # ------------------------------------------------------------------

    async def run_escalation_scan(self) -> dict[str, int]:
        """
        Promote stale late incidents through the state machine.

        Called every 15 minutes by the attendance scheduler. Returns a small
        dict of counters for observability.

        Promotion rules (working hours = Mon–Fri, weekends skipped):
            AWAITING_REPLY -> REMINDER_SENT  if first_email_sent_at is older
                                              than INCIDENT_REMINDER_AFTER_WORKING_HOURS
            REMINDER_SENT  -> ESCALATED      if reminder_sent_at is older than
                                              INCIDENT_ULTIMATUM_AFTER_WORKING_HOURS

        Incidents whose ``reply_received_at`` has been populated by the HR
        reply form are skipped — they will be transitioned to RESOLVED /
        RESOLVED_LATE inside the same scan.

        Implementation notes
        --------------------
        The DB phase (SELECT, UPDATE, RETURNING) and the I/O phase (HTTP email
        + Telegram) are deliberately separated:

          * Phase 1 (under pool.acquire) does ALL the SQL — including the
            state-promoting UPDATEs — and builds two in-memory lists of work
            items containing every field the email senders need. This means
            the connection is held only for a few milliseconds even on busy
            mornings, instead of being blocked behind 30-second httpx calls.

          * Phase 2 (no connection held) iterates the lists and sends the
            emails / Telegram pings. Each item is wrapped in its own try /
            except so a single failure does not abort the rest of the scan.

        State is committed to the DB BEFORE any email is attempted. This trades
        a possible "missed email on crash" against the much worse alternative
        of "duplicate email on crash" — the cron will not re-promote an
        already-promoted row, but a missed email is at least visible in the
        Telegram digest the same evening.
        """
        now = datetime.now(BALI_TZ)
        resolved = 0
        resolved_late = 0
        to_remind: list[dict] = []
        to_escalate: list[dict] = []

        # ─── Phase 1: DB only (no HTTP) ────────────────────────────────────
        async with self.pool.acquire() as conn:
            # 1a. Resolve any incidents that received a reply since last scan.
            #     AWAITING_REPLY + reply -> RESOLVED
            #     REMINDER_SENT  + reply -> RESOLVED_LATE
            #     ESCALATED      + reply -> stays ESCALATED (history preserved)
            resolved_rows = await conn.fetch(
                """
                UPDATE attendance_late_incidents
                   SET state = $1
                 WHERE state = $2
                   AND reply_received_at IS NOT NULL
                RETURNING id
                """,
                STATE_RESOLVED,
                STATE_AWAITING_REPLY,
            )
            resolved = len(resolved_rows)

            resolved_late_rows = await conn.fetch(
                """
                UPDATE attendance_late_incidents
                   SET state = $1
                 WHERE state = $2
                   AND reply_received_at IS NOT NULL
                RETURNING id
                """,
                STATE_RESOLVED_LATE,
                STATE_REMINDER_SENT,
            )
            resolved_late = len(resolved_late_rows)

            # 1b. AWAITING_REPLY -> REMINDER_SENT (rows old enough only).
            awaiting = await conn.fetch(
                """
                SELECT id, email, full_name, late_date, first_email_sent_at,
                       reply_token, responsible_manager_email
                  FROM attendance_late_incidents
                 WHERE state = $1
                   AND reply_received_at IS NULL
                """,
                STATE_AWAITING_REPLY,
            )
            for inc in awaiting:
                hours = self._working_hours_between(inc["first_email_sent_at"], now)
                if hours < INCIDENT_REMINDER_AFTER_WORKING_HOURS:
                    continue
                await conn.execute(
                    """
                    UPDATE attendance_late_incidents
                       SET state = $1, reminder_sent_at = NOW()
                     WHERE id = $2
                    """,
                    STATE_REMINDER_SENT,
                    inc["id"],
                )
                to_remind.append(
                    {
                        "id": inc["id"],
                        "email": inc["email"],
                        "full_name": inc["full_name"] or inc["email"],
                        "late_date": inc["late_date"],
                        "reply_token": inc["reply_token"],
                    },
                )

            # 1c. REMINDER_SENT -> ESCALATED (rows old enough only).
            reminder_sent_rows = await conn.fetch(
                """
                SELECT id, email, full_name, late_date, reminder_sent_at,
                       responsible_manager_email
                  FROM attendance_late_incidents
                 WHERE state = $1
                   AND reply_received_at IS NULL
                """,
                STATE_REMINDER_SENT,
            )
            for inc in reminder_sent_rows:
                hours = self._working_hours_between(inc["reminder_sent_at"], now)
                if hours < INCIDENT_ULTIMATUM_AFTER_WORKING_HOURS:
                    continue
                await conn.execute(
                    """
                    UPDATE attendance_late_incidents
                       SET state = $1, ultimatum_sent_at = NOW()
                     WHERE id = $2
                    """,
                    STATE_ESCALATED,
                    inc["id"],
                )
                to_escalate.append(
                    {
                        "id": inc["id"],
                        "email": inc["email"],
                        "full_name": inc["full_name"] or inc["email"],
                        "late_date": inc["late_date"],
                        "manager_email": inc["responsible_manager_email"],
                    },
                )
        # ─── End of Phase 1 — connection released here ─────────────────────

        # ─── Phase 2: HTTP I/O (no connection held) ────────────────────────
        for inc in to_remind:
            try:
                await self._send_reminder_email(
                    incident_id=inc["id"],
                    email=inc["email"],
                    full_name=inc["full_name"],
                    late_date=inc["late_date"],
                    reply_token=inc["reply_token"],
                )
            except httpx.HTTPError as exc:
                # State is already promoted in DB. Log loud so the missed
                # email is visible in monitoring.
                logger.error(
                    "run_escalation_scan: reminder email FAILED (HTTP) for "
                    "incident_id=%s email=%s — %s",
                    inc["id"],
                    inc["email"],
                    exc,
                )
            except Exception as exc:
                logger.exception(
                    "run_escalation_scan: reminder email FAILED for "
                    "incident_id=%s email=%s — %s",
                    inc["id"],
                    inc["email"],
                    exc,
                )

        for inc in to_escalate:
            try:
                await self._send_ultimatum_email(
                    incident_id=inc["id"],
                    email=inc["email"],
                    full_name=inc["full_name"],
                    late_date=inc["late_date"],
                    manager_email=inc["manager_email"],
                )
            except httpx.HTTPError as exc:
                logger.error(
                    "run_escalation_scan: ultimatum email FAILED (HTTP) for "
                    "incident_id=%s email=%s — %s",
                    inc["id"],
                    inc["email"],
                    exc,
                )
            except Exception as exc:
                logger.exception(
                    "run_escalation_scan: ultimatum email FAILED for "
                    "incident_id=%s email=%s — %s",
                    inc["id"],
                    inc["email"],
                    exc,
                )

            # Ultimatum is the only event that breaks the "digest only"
            # Telegram rule — send an immediate ping out-of-band.
            try:
                await self._send_telegram(
                    f"🚨 ULTIMATUM inviato — {inc['email']}\n"
                    f"Ritardo del {inc['late_date'].strftime('%d/%m/%Y')}, "
                    f"nessuna risposta in 48h lavorative.\n"
                    f"CC: zero@"
                    + (
                        f" + {inc['manager_email']}"
                        if inc["manager_email"]
                        else ""
                    ),
                )
            except httpx.HTTPError as exc:
                logger.warning(
                    "run_escalation_scan: telegram ping FAILED (HTTP) for "
                    "incident_id=%s — %s",
                    inc["id"],
                    exc,
                )
            except Exception as exc:
                logger.exception(
                    "run_escalation_scan: telegram ping FAILED for "
                    "incident_id=%s — %s",
                    inc["id"],
                    exc,
                )

        counters = {
            "resolved": resolved,
            "resolved_late": resolved_late,
            "promoted_to_reminder": len(to_remind),
            "promoted_to_ultimatum": len(to_escalate),
        }
        if any(counters.values()):
            logger.info("run_escalation_scan: %s", counters)
        else:
            logger.debug("run_escalation_scan: nothing to do")
        return counters

    @staticmethod
    def _working_hours_between(start: datetime, end: datetime) -> float:
        """
        Count hours between two datetimes, skipping Saturdays and Sundays.

        Both datetimes are converted to Bali timezone before counting. The
        algorithm walks day-by-day in Bali time so weekend rollover is exact:
        a clock_in on Friday 09:45 will only start its 24h reminder counter
        on Monday 00:00 — i.e. the cron will not promote it on the weekend.
        """
        if start.tzinfo is None:
            start = start.replace(tzinfo=BALI_TZ)
        if end.tzinfo is None:
            end = end.replace(tzinfo=BALI_TZ)
        start_bali = start.astimezone(BALI_TZ)
        end_bali = end.astimezone(BALI_TZ)
        if end_bali <= start_bali:
            return 0.0

        total_seconds: float = 0.0
        cursor = start_bali
        while cursor < end_bali:
            # End of the current calendar day in Bali time.
            day_end = (cursor + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            slice_end = min(day_end, end_bali)
            if cursor.weekday() < 5:  # Mon–Fri only
                total_seconds += (slice_end - cursor).total_seconds()
            cursor = slice_end
        return total_seconds / 3600.0

    async def _send_reminder_email(
        self,
        *,
        incident_id,
        email: str,
        full_name: str,
        late_date: date,
        reply_token: str,
    ) -> None:
        """
        Stage 3 — 24h reminder (Indonesian, no CC).

        Sent when an AWAITING_REPLY incident is older than 24 working hours.
        Warns explicitly that further silence triggers an escalation.
        """
        first_name = full_name.split()[0] if full_name else email
        reply_link = f"{HR_REPLY_BASE_URL}/{incident_id}?token={reply_token}"
        date_str = late_date.strftime("%d/%m/%Y")
        subject = f"Pengingat — keterlambatan {date_str} belum dijawab"

        html_body = _render_email_shell(
            header_title=f"Halo {first_name} — Pengingat penting",
            accent="#dd6b20",
            body_html=f"""
            <p>
                Kami belum menerima alasan keterlambatan kamu pada
                <strong>{date_str}</strong>.
            </p>
            <div style="background:#fff5f5; border-left:4px solid #dd6b20;
                        padding:12px 16px; border-radius:0 8px 8px 0;
                        margin:20px 0; font-size:14px;">
                Mohon dikirim secepatnya. <strong>Tidak menjawab dapat memicu
                eskalasi terhadap kepatuhan dan kedisiplinan</strong> kamu.
            </div>
            <p style="text-align:center; margin:24px 0;">
                <a href="{reply_link}"
                   style="display:inline-block; background:#dd6b20; color:white;
                          text-decoration:none; padding:12px 26px; border-radius:6px;
                          font-weight:600; font-size:15px;">
                    Kirim alasan sekarang →
                </a>
            </p>
            <p style="font-size:13px; color:#777;">
                Jika sudah terkirim sebelumnya dan email ini tetap kamu terima,
                mohon hubungi langsung Zero atau manajermu.
            </p>
            """,
        )
        await self._post_email(
            to=email,
            subject=subject,
            html_body=html_body,
            cc=None,
            log_tag="reminder_sent",
        )

    async def _send_ultimatum_email(
        self,
        *,
        incident_id,
        email: str,
        full_name: str,
        late_date: date,
        manager_email: str | None,
    ) -> None:
        """
        Stage 4 — ultimatum (English, CC zero@ + supervisor if any).

        Sent when a REMINDER_SENT incident is older than 24 additional working
        hours. Switches to English because the supervisor (Ruslana / Veronika)
        is on the thread.

        No reply link is included: the conduct review is now formal and any
        explanation must be provided directly to the supervisor.
        """
        first_name = full_name.split()[0] if full_name else email
        date_str = late_date.strftime("%d %B %Y")
        subject = f"⚠️ Conduct escalation — unanswered late check-in ({date_str})"

        # The notifications API accepts cc as a single comma-separated string.
        cc_recipients: list[str] = [ADMIN_EMAIL]
        if manager_email:
            cc_recipients.append(manager_email)
        cc_str = ", ".join(cc_recipients)

        manager_line = (
            f"<p>This message has been escalated to <strong>{manager_email}</strong> "
            f"and to Bali Zero management.</p>"
            if manager_email
            else "<p>This message has been escalated to Bali Zero management.</p>"
        )

        html_body = _render_email_shell(
            header_title=f"{first_name} — Conduct escalation",
            accent="#c53030",
            body_html=f"""
            <p>
                Your late check-in on <strong>{date_str}</strong> has not been
                answered despite two prior emails over the past 48 working hours.
            </p>
            <div style="background:#fff5f5; border-left:4px solid #c53030;
                        padding:14px 18px; border-radius:0 8px 8px 0;
                        margin:20px 0; font-size:14px;">
                As of now this incident is logged as a <strong>conduct issue</strong>.
                Repeated occurrences will be considered a formal disciplinary matter
                under your employment terms.
            </div>
            {manager_line}
            <p>
                You are required to discuss this incident <strong>in person</strong>
                with your supervisor before the end of the next working day.
            </p>
            <p style="margin-top: 24px; color: #555;">
                Bali Zero Management
            </p>
            """,
        )
        await self._post_email(
            to=email,
            subject=subject,
            html_body=html_body,
            cc=cc_str,
            log_tag="ultimatum_sent",
        )

    # ------------------------------------------------------------------
    # Telegram digest
    # ------------------------------------------------------------------

    async def _send_telegram(self, message: str) -> None:
        """
        POST a plain-text message to Telegram. Silent no-op if the bot token
        is not configured (e.g. in unit tests).

        Long messages (> TELEGRAM_MAX_MSG_LEN ≈ 4000 chars) are split on
        newline boundaries via ``_chunk_telegram_message`` and sent as
        multiple sendMessage calls, each prefixed with "(part N/M)". The
        4096-char Telegram hard limit is otherwise easy to hit on heavy days.
        """
        if not TELEGRAM_BOT_TOKEN:
            logger.debug("_send_telegram: no token configured — skipping")
            return
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        chunks = _chunk_telegram_message(message)

        async with httpx.AsyncClient(timeout=15.0) as client:
            for idx, chunk in enumerate(chunks, start=1):
                payload = {
                    "chat_id": TELEGRAM_DIGEST_CHAT_ID,
                    "text": chunk,
                    "disable_web_page_preview": True,
                }
                try:
                    response = await client.post(url, json=payload)
                    response.raise_for_status()
                    logger.info(
                        "_send_telegram: sent chunk %d/%d (%d chars)",
                        idx,
                        len(chunks),
                        len(chunk),
                    )
                except httpx.HTTPStatusError as exc:
                    logger.warning(
                        "_send_telegram: HTTP %s on chunk %d/%d — %s",
                        exc.response.status_code,
                        idx,
                        len(chunks),
                        exc.response.text[:200],
                    )
                    # Keep going so a transient error on one chunk does not
                    # block the rest of the digest.
                except (httpx.TimeoutException, httpx.ConnectError, OSError) as exc:
                    logger.warning(
                        "_send_telegram: network error on chunk %d/%d — %s",
                        idx,
                        len(chunks),
                        exc,
                    )
                except Exception as exc:
                    logger.exception(
                        "_send_telegram: failed chunk %d/%d — %s",
                        idx,
                        len(chunks),
                        exc,
                    )

    async def send_daily_telegram_digest(self) -> bool:
        """
        Build and send the 18:00 WITA daily digest. Returns True if a message
        was sent, False if there was nothing to report (silent day).

        Aggregates four sections — only those with data are included:
          • New late incidents opened today
          • Replies received today
          • Currently escalated (ESCALATED state)
          • Closed today (RESOLVED / RESOLVED_LATE state changes today)
        """
        today = datetime.now(BALI_TZ).date()

        async with self.pool.acquire() as conn:
            new_today = await conn.fetch(
                """
                SELECT email,
                       to_char(checkin_time AT TIME ZONE 'Asia/Makassar', 'HH24:MI') AS hhmm,
                       state
                  FROM attendance_late_incidents
                 WHERE late_date = $1
                 ORDER BY checkin_time
                """,
                today,
            )
            replies_today = await conn.fetch(
                """
                SELECT email,
                       late_date,
                       LEFT(reply_content, 80) AS preview
                  FROM attendance_late_incidents
                 WHERE reply_received_at IS NOT NULL
                   AND (reply_received_at AT TIME ZONE 'Asia/Makassar')::date = $1
                 ORDER BY reply_received_at
                """,
                today,
            )
            escalated = await conn.fetch(
                """
                SELECT email, late_date
                  FROM attendance_late_incidents
                 WHERE state = $1
                 ORDER BY late_date DESC
                """,
                STATE_ESCALATED,
            )
            closed_today = await conn.fetchval(
                """
                SELECT COUNT(*)
                  FROM attendance_late_incidents
                 WHERE state IN ($1, $2)
                   AND (updated_at AT TIME ZONE 'Asia/Makassar')::date = $3
                """,
                STATE_RESOLVED,
                STATE_RESOLVED_LATE,
                today,
            )

        if not new_today and not replies_today and not escalated and not closed_today:
            logger.info(
                "send_daily_telegram_digest: nothing to report for %s — staying silent",
                today,
            )
            return False

        lines: list[str] = [
            f"🕘 Ritardi & risposte — {today.strftime('%d/%m/%Y')}",
            "",
        ]

        if new_today:
            lines.append(f"⚠️ Ritardi oggi ({len(new_today)}):")
            for r in new_today:
                state_label = {
                    STATE_AWAITING_REPLY: "incident aperto",
                    STATE_REMINDER_SENT: "reminder inviato",
                    STATE_ESCALATED: "ESCALATED",
                    STATE_RESOLVED: "risolto",
                    STATE_RESOLVED_LATE: "risolto in ritardo",
                }.get(r["state"], r["state"])
                lines.append(f"  • {r['email']} — {r['hhmm']} → {state_label}")
            lines.append("")

        if replies_today:
            lines.append(f"💬 Risposte ricevute oggi ({len(replies_today)}):")
            for r in replies_today:
                preview = (r["preview"] or "").replace("\n", " ")
                lines.append(
                    f"  • {r['email']} ({r['late_date'].strftime('%d/%m')}): "
                    f"\"{preview}\"",
                )
            lines.append("")

        if escalated:
            lines.append(f"🚨 Escalation attive ({len(escalated)}):")
            for r in escalated:
                lines.append(
                    f"  • {r['email']} — {r['late_date'].strftime('%d/%m/%Y')}",
                )
            lines.append("")

        if closed_today:
            lines.append(f"✅ Chiusi oggi: {closed_today}")

        await self._send_telegram("\n".join(lines).rstrip())
        return True

    async def _send_absent_alert(self, absent_members: list[dict]) -> None:
        """
        Send a single absent-members summary email to zero@balizero.com.

        Subject: "⚠️ Assenze team — [date]"
        Body: HTML table listing absent members with days absent and last-seen date.
        """
        today_str: str = datetime.now(BALI_TZ).strftime("%d/%m/%Y")
        subject: str = f"⚠️ Assenze team — {today_str}"

        # Build table rows
        table_rows: str = ""
        for m in absent_members:
            days_label: str = (
                f"{m['absent_days']} gg lavorativi"
                if m["absent_days"] is not None
                else "Nessun check-in registrato"
            )
            table_rows += f"""
            <tr>
                <td style="padding:10px 14px; border-bottom:1px solid #e8e8e8;">
                    {m["full_name"]}
                </td>
                <td style="padding:10px 14px; border-bottom:1px solid #e8e8e8; color:#555;">
                    {m["email"]}
                </td>
                <td style="padding:10px 14px; border-bottom:1px solid #e8e8e8; color:#e53e3e; font-weight:600;">
                    {days_label}
                </td>
                <td style="padding:10px 14px; border-bottom:1px solid #e8e8e8; color:#777;">
                    {m["last_seen"]}
                </td>
            </tr>"""

        html_body: str = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #f5f5f5;
            margin: 0;
            padding: 20px;
        }}
        .container {{
            max-width: 680px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        }}
        .header {{
            background: linear-gradient(135deg, #e53e3e 0%, #c53030 100%);
            color: white;
            padding: 28px 32px;
        }}
        .header h1 {{
            margin: 0 0 6px 0;
            font-size: 20px;
            font-weight: 600;
        }}
        .header p {{
            margin: 0;
            opacity: 0.85;
            font-size: 14px;
        }}
        .content {{
            padding: 32px;
            color: #333333;
        }}
        .summary-badge {{
            display: inline-block;
            background: #fff5f5;
            border: 1px solid #fed7d7;
            color: #c53030;
            border-radius: 20px;
            padding: 6px 16px;
            font-size: 14px;
            font-weight: 600;
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}
        thead tr {{
            background: #f8f8f8;
        }}
        thead th {{
            padding: 10px 14px;
            text-align: left;
            font-weight: 600;
            color: #555555;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 2px solid #e8e8e8;
        }}
        .footer {{
            text-align: center;
            padding: 20px 32px;
            color: #888888;
            font-size: 12px;
            border-top: 1px solid #f0f0f0;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Assenze team</h1>
            <p>Report giornaliero — {today_str} · 10:00 WITA</p>
        </div>
        <div class="content">
            <div class="summary-badge">
                {len(absent_members)} membro/i assente/i ≥ {ABSENT_THRESHOLD_DAYS} giorni lavorativi
            </div>
            <table>
                <thead>
                    <tr>
                        <th>Nome</th>
                        <th>Email</th>
                        <th>Assenza</th>
                        <th>Ultimo check-in</th>
                    </tr>
                </thead>
                <tbody>
                    {table_rows}
                </tbody>
            </table>
            <p style="margin-top:24px; font-size:13px; color:#777;">
                Questo report viene generato automaticamente ogni mattina alle 10:00 WITA
                per i membri con {ABSENT_THRESHOLD_DAYS}+ giorni lavorativi senza check-in.
            </p>
        </div>
        <div class="footer">
            Bali Zero · Zantara Team Management
        </div>
    </div>
</body>
</html>"""

        payload: dict = {
            "to": ADMIN_EMAIL,
            "subject": subject,
            "body": html_body,
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    _EMAIL_API_URL,
                    headers={"X-API-Key": _EMAIL_API_KEY},
                    json=payload,
                )
                response.raise_for_status()
            logger.info(
                "_send_absent_alert: sent absence summary (%d members) to %s",
                len(absent_members),
                ADMIN_EMAIL,
            )
        except httpx.HTTPStatusError as exc:
            logger.error(
                "_send_absent_alert: HTTP %s sending to %s — %s",
                exc.response.status_code,
                ADMIN_EMAIL,
                exc.response.text,
            )
        except (httpx.TimeoutException, httpx.ConnectError, OSError) as exc:
            logger.warning(
                "_send_absent_alert: network error sending to %s — %s",
                ADMIN_EMAIL,
                exc,
            )
        except Exception as exc:
            logger.exception(
                "_send_absent_alert: failed to send — %s",
                exc,
            )
