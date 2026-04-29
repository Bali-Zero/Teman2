"""
LKPM Deadline Notifier

Daily email reminder to tax consultants for pending LKPM reports.
Groups by assigned consultant, sends casual Indonesian emails with
color-coded HTML tables.  Telegram alert for urgent (<=3 days) drafts.
"""

from __future__ import annotations

import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx

from backend.app.utils.logging_utils import get_logger
from backend.services.compliance.lkpm_service import QUARTER_DEADLINES

logger = get_logger(__name__)

# -- Configuration ----------------------------------------------------------

_EMAIL_API_URL: str = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY: str = os.getenv("NUZANTARA_API_KEY", "")

ADMIN_EMAIL: str = "zero@balizero.com"
TELEGRAM_OWNER_CHAT_ID: int = 1125336968
TAX_CONSULTANT_MANAGER: str = "veronika.tax@balizero.com"
TAX_CONSULTANTS_NON_MANAGER: tuple[str, ...] = (
    "kadek.tax@balizero.com",
    "dewaayu.tax@balizero.com",
    "angel.tax@balizero.com",
    "faisha.tax@balizero.com",
)
TELEGRAM_URGENCY_DAYS: int = 3
LKPM_DASHBOARD_URL: str = "https://kita.balizero.com/lkpm"
KILLSWITCH_KEY: str = "lkpm_deadline_notifier_enabled"

# -- Row colors for "sisa hari" --
_ROW_COLORS: dict[str, str] = {
    "critical": "#FFCCCC",  # <=1 day
    "urgent": "#FFE0B2",  # <=3 days
    "warning": "#FFF9C4",  # <=7 days
    "ok": "#E8F5E9",  # >7 days
}

# -- Pending reports query --------------------------------------------------

_PENDING_QUERY = """
SELECT
    r.id,
    r.client_id,
    r.quarter,
    r.year,
    r.status,
    r.oss_submitted,
    r.lkpm_assigned_to,
    COALESCE(cfg.company_name, 'UNKNOWN') AS company_name,
    COALESCE(cfg.oss_username, '') AS oss_username
FROM lkpm_reports r
LEFT JOIN clients c ON c.id = r.client_id
LEFT JOIN lkpm_client_config cfg ON cfg.client_id = r.client_id
    AND COALESCE(cfg.company_id, 0) = COALESCE(r.company_id, 0)
WHERE r.status NOT IN ('submitted', 'archived')
  AND r.oss_submitted = false
  AND c.deleted_at IS NULL
ORDER BY r.id
"""


# -- Pure helpers -----------------------------------------------------------


def _compute_days_until_deadline(
    quarter: str,
    year: int,
    now: datetime | None = None,
) -> int | None:
    """Return days until the LKPM deadline for the given quarter/year.

    Returns None for unknown quarters.
    """
    deadline_spec = QUARTER_DEADLINES.get(quarter)
    if deadline_spec is None:
        return None

    month, day = deadline_spec
    deadline_year = year + 1 if quarter == "Q4" else year
    deadline_dt = datetime(deadline_year, month, day, tzinfo=timezone.utc)

    if now is None:
        now = datetime.now(timezone.utc)

    delta = deadline_dt.date() - now.date()
    return delta.days


def _format_deadline(quarter: str, year: int) -> str:
    """Return the deadline date as DD/MM/YYYY string, or '---' for unknown."""
    deadline_spec = QUARTER_DEADLINES.get(quarter)
    if deadline_spec is None:
        return "\u2014"

    month, day = deadline_spec
    deadline_year = year + 1 if quarter == "Q4" else year
    return f"{day:02d}/{month:02d}/{deadline_year}"


def _first_name_from_email(email: str) -> str:
    """Extract a friendly first name from an email address.

    Special case: 'dewaayu' -> 'Dewa Ayu'.
    """
    local = email.split("@")[0].split(".")[0].lower()
    if local == "dewaayu":
        return "Dewa Ayu"
    return local.capitalize()


def _row_color(days: int) -> str:
    """Pick background color based on days until deadline."""
    if days <= 1:
        return _ROW_COLORS["critical"]
    if days <= 3:
        return _ROW_COLORS["urgent"]
    if days <= 7:
        return _ROW_COLORS["warning"]
    return _ROW_COLORS["ok"]


# -- Notifier class ---------------------------------------------------------


class LKPMDeadlineNotifier:
    """Checks pending LKPM reports and sends deadline reminders."""

    def __init__(self, db_pool: Any) -> None:
        self._db_pool = db_pool
        self._client: httpx.AsyncClient | None = None

    async def check_and_notify(self) -> dict[str, Any]:
        """Main entry point: check kill switch, scan, classify, notify."""

        # Kill switch
        async with self._db_pool.acquire() as conn:
            enabled = await conn.fetchval(
                f"SELECT value FROM system_settings WHERE key = '{KILLSWITCH_KEY}'"
            )
        if enabled != "true":
            logger.warning(
                "LKPM deadline notifier BLOCKED -- awaiting owner approval "
                "(set %s=true)",
                KILLSWITCH_KEY,
            )
            return {"status": "blocked", "reason": "awaiting_owner_approval"}

        # Scan pending reports
        pending = await self._get_pending_reports()
        if not pending:
            return {"status": "ok", "emails_sent": 0, "telegram_sent": False}

        now = datetime.now(timezone.utc)

        # Enrich with deadline info and filter out overdue
        in_window: list[dict[str, Any]] = []
        for row in pending:
            days = _compute_days_until_deadline(row["quarter"], row["year"], now)
            if days is None or days < 0:
                continue  # Past deadline: skip silently
            row["days_until_deadline"] = days
            row["deadline_str"] = _format_deadline(row["quarter"], row["year"])
            in_window.append(row)

        if not in_window:
            return {"status": "ok", "emails_sent": 0, "telegram_sent": False}

        # Group by assignee
        by_assignee: dict[str | None, list[dict[str, Any]]] = defaultdict(list)
        for row in in_window:
            by_assignee[row.get("lkpm_assigned_to")].append(row)

        emails_sent = 0
        async with self._get_http_client() as client:
            self._client = client

            for assignee, rows in by_assignee.items():
                try:
                    if assignee:
                        await self._send_assignee_reminder(assignee, rows)
                    else:
                        await self._send_unassigned_alert(rows)
                    emails_sent += 1
                except Exception:
                    logger.exception(
                        "Failed to send LKPM reminder for assignee=%s", assignee
                    )

        # Telegram alert for urgent drafts
        telegram_sent = await self._maybe_send_telegram(in_window, now)

        return {
            "status": "ok",
            "emails_sent": emails_sent,
            "telegram_sent": telegram_sent,
        }

    # -- Database -----------------------------------------------------------

    async def _get_pending_reports(self) -> list[dict[str, Any]]:
        async with self._db_pool.acquire() as conn:
            rows = await conn.fetch(_PENDING_QUERY)
        return [dict(r) for r in rows]

    # -- Email senders ------------------------------------------------------

    async def _send_assignee_reminder(
        self,
        assignee_email: str,
        rows: list[dict[str, Any]],
    ) -> None:
        name = _first_name_from_email(assignee_email)
        n = len(rows)
        subject = f"[LKPM] Reminder: {n} laporan LKPM belum selesai"
        body = self._build_email_body(name, rows)
        await self._post_email(
            to=assignee_email,
            cc=ADMIN_EMAIL,
            subject=subject,
            html_body=body,
        )
        logger.info("LKPM reminder sent to %s (%d reports)", assignee_email, n)

    async def _send_unassigned_alert(
        self,
        rows: list[dict[str, Any]],
    ) -> None:
        n = len(rows)
        to_list = ", ".join(TAX_CONSULTANTS_NON_MANAGER)
        cc_list = f"{TAX_CONSULTANT_MANAGER}, {ADMIN_EMAIL}"
        subject = f"[LKPM] Alert: {n} laporan LKPM belum di-assign"
        body = self._build_email_body("Tim Tax", rows)
        await self._post_email(
            to=to_list,
            cc=cc_list,
            subject=subject,
            html_body=body,
        )
        logger.info("LKPM unassigned alert sent to team (%d reports)", n)

    # -- Telegram -----------------------------------------------------------

    async def _maybe_send_telegram(
        self,
        rows: list[dict[str, Any]],
        now: datetime,
    ) -> bool:
        """Send Telegram alert if any in-window row has days<=3 AND status='draft'."""
        urgent = [
            r for r in rows
            if r.get("days_until_deadline", 999) <= TELEGRAM_URGENCY_DAYS
            and r.get("status") == "draft"
        ]
        if not urgent:
            return False

        try:
            await self._send_telegram_alert(urgent)
            return True
        except Exception:
            logger.exception("Failed to send LKPM Telegram alert")
            return False

    async def _send_telegram_alert(self, urgent_rows: list[dict[str, Any]]) -> None:
        from backend.services.integrations.telegram_bot_service import TelegramBotService

        lines = [f"*LKPM URGENT* - {len(urgent_rows)} laporan draft mendekati deadline:\n"]
        for r in urgent_rows:
            days = r.get("days_until_deadline", "?")
            lines.append(
                f"  - {r['company_name']} ({r['quarter']} {r['year']}): "
                f"{days} hari lagi"
            )
        lines.append(f"\nDashboard: {LKPM_DASHBOARD_URL}")

        bot = TelegramBotService()
        await bot.send_message(
            chat_id=TELEGRAM_OWNER_CHAT_ID,
            text="\n".join(lines),
        )
        await bot.close()

    # -- HTML builder -------------------------------------------------------

    def _build_email_body(
        self,
        name: str,
        rows: list[dict[str, Any]],
    ) -> str:
        n = len(rows)
        table_rows = "\n".join(self._build_table_row(r) for r in rows)

        return f"""
<html>
<body style="font-family: Arial, sans-serif; color: #333; line-height: 1.6;">

<p>Halo {name}! \U0001f44b</p>

<p>Mau ngingetin aja \u2014 ada <strong>{n}</strong> laporan LKPM yang belum selesai.
Yuk dicek biar nggak kelewat deadline!</p>

<table border="1" cellpadding="8" cellspacing="0"
       style="border-collapse:collapse; width:100%; font-size:14px;">
  <thead style="background:#1a237e; color:#fff;">
    <tr>
      <th>Perusahaan</th>
      <th>OSS Username</th>
      <th>Status</th>
      <th>Sisa Hari</th>
    </tr>
  </thead>
  <tbody>
    {table_rows}
  </tbody>
</table>

<br>
<p>Kalau ada yang perlu dibantu, langsung hubungi aja ya.</p>

<p>Dashboard: <a href="{LKPM_DASHBOARD_URL}">{LKPM_DASHBOARD_URL}</a></p>

<p>\u2014 Zantara \u00b7 Bali Zero</p>
</body>
</html>
""".strip()

    @staticmethod
    def _build_table_row(row: dict[str, Any]) -> str:
        days = row.get("days_until_deadline", 999)
        bg = _row_color(days)
        return (
            f'<tr style="background:{bg};">'
            f"<td style='padding:8px;'>{row['company_name']}</td>"
            f"<td style='padding:8px;'>{row.get('oss_username', '')}</td>"
            f"<td style='padding:8px;'>{row.get('status', '')}</td>"
            f"<td style='padding:8px; font-weight:bold;'>{days} hari</td>"
            f"</tr>"
        )

    # -- HTTP ---------------------------------------------------------------

    async def _post_email(
        self,
        to: str,
        subject: str,
        html_body: str,
        cc: str | None = None,
    ) -> None:
        if self._client is None:
            raise RuntimeError("_post_email called outside HTTP client context")

        payload: dict[str, Any] = {
            "to": to,
            "subject": subject,
            "body": html_body,
        }
        if cc:
            payload["cc"] = cc

        response = await self._client.post(
            _EMAIL_API_URL,
            json=payload,
            headers={
                "X-API-Key": _EMAIL_API_KEY,
                "Content-Type": "application/json",
            },
            timeout=20.0,
        )
        response.raise_for_status()

    @staticmethod
    def _get_http_client() -> httpx.AsyncClient:
        # Caller wraps in `async with self._get_http_client() as client:`
        # — deterministic close. Equivalent to OK_CONTEXT_MANAGER per the
        # P0-5 audit; flagged only because the instantiation is on a
        # different line than the `async with`.
        return httpx.AsyncClient(  # golden-rule-10-exempt: factory used exclusively via `async with`
            headers={"User-Agent": "LKPMDeadlineNotifier/1.0"},
        )


# -- Standalone entry point -------------------------------------------------


async def run_lkpm_deadline_notifier_task(db_pool: Any) -> dict[str, Any]:
    """Entry point for cron / scheduler invocation."""
    notifier = LKPMDeadlineNotifier(db_pool)
    return await notifier.check_and_notify()
