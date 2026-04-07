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

import os
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
# Shared email shell
# ---------------------------------------------------------------------------


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
    - Late check-ins (after 09:30 Bali time)
    - Consecutive absences (2+ working days without any clock-in)

    Does NOT own a scheduler loop — callers must invoke the check methods
    at the appropriate time.
    """

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.pool = db_pool
        logger.info("AttendanceMonitor initialized")

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

        # Incident window: clock_in ≥ 09:40.
        # Commit 1: sends a stronger notification email (still 1-to-1, Indonesian).
        # Commit 2: will also open a row in attendance_late_incidents and kick off
        #           the reply/reminder/ultimatum state machine.
        logger.info(
            "check_late_checkin: %s in incident window at %s — opening incident",
            email,
            checkin_str,
        )
        await self._send_incident_opened_notification(email, full_name, checkin_str)

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
        cc: str | list[str] | None = None,
        log_tag: str = "email",
    ) -> None:
        """
        Internal helper: POST a rendered email to the notifications API.

        Centralises the httpx call + structured logging so callers only worry
        about subject + body.
        """
        payload: dict = {"to": to, "subject": subject, "body": html_body}
        if cc is not None:
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
        except Exception as exc:
            logger.error(
                "%s: failed to send to %s — %s",
                log_tag,
                to,
                exc,
                exc_info=True,
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
        checkin_time: str,
    ) -> None:
        """
        Stage 2 — incident window (clock_in ≥ 09:40).

        Sends a more serious 1-to-1 email in Indonesian asking for a mandatory
        reply explaining the reason for the late arrival.

        NOTE (commit 1): this method currently only sends the email. Commit 2
        will also insert a row in ``attendance_late_incidents`` and embed a
        signed reply link so the escalation cron can track response status.
        """
        first_name: str = full_name.split()[0] if full_name else email
        subject: str = f"Keterlambatan hari ini — {first_name}, {checkin_time}"

        html_body: str = _render_email_shell(
            header_title=f"Halo {first_name} — Keterlambatan tercatat",
            accent="#ed8936",  # orange — stronger
            body_html=f"""
            <p>
                Check-in kamu hari ini tercatat pukul
                <strong>{checkin_time} WITA</strong>, setelah batas 09:40.
            </p>
            <div style="background:#fffaf0; border-left:4px solid #ed8936;
                        padding:12px 16px; border-radius:0 8px 8px 0;
                        margin:20px 0; font-size:14px;">
                Mohon balas email ini atau hubungi manajermu untuk menjelaskan
                <strong>alasan keterlambatan hari ini</strong>. Balasan bersifat wajib.
            </div>
            <p>
                Jika keterlambatan karena alasan yang sudah direncanakan (cuti, izin, dinas luar),
                pastikan leave request sudah diajukan dan disetujui sebelumnya.
            </p>
            <p style="margin-top: 24px; color: #555;">
                Terima kasih atas perhatian dan kerjasamanya. 🙏
            </p>
            """,
        )

        # Still no CC at stage 2 — escalation CC only at ultimatum stage.
        await self._post_email(
            to=email,
            subject=subject,
            html_body=html_body,
            cc=None,
            log_tag="incident_opened",
        )

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
        except Exception as exc:
            logger.error(
                "_send_absent_alert: failed to send — %s",
                exc,
                exc_info=True,
            )
