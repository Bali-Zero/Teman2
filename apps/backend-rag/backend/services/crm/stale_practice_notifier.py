"""
Stale Practice Notifier Service

Detects practices with no activity for 7+ days and alerts:
- zero@balizero.com (summary of ALL stale practices, grouped by team leader)
- Each unique team leader (individual list of their stale practices)

Active statuses checked: inquiry, waiting_documents, sending_invoice, on_process
Runs as a scheduled task (daily recommended).
"""

import os
from datetime import date, datetime, timezone
from typing import Any

import asyncpg

from backend.app.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Internal email API — Brevo via /api/notifications/send-email, from=zantara@balizero.com
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")

ADMIN_EMAIL = "zero@balizero.com"
STALE_DAYS = 7

# Statuses considered "active" (non-terminal)
ACTIVE_STATUSES = ("inquiry", "waiting_documents", "sending_invoice", "on_process")

# CRM base URL for individual practice links
CRM_PRACTICE_URL = "https://zantara-crm.vercel.app/process/{id}"


class StalePracticeNotifier:
    """Service to detect stale practices and notify the admin and team leaders."""

    def __init__(self, db_pool: asyncpg.Pool) -> None:
        self.db_pool = db_pool

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def check_and_notify(self) -> dict[str, Any]:
        """
        Find all active practices with no activity in the last 7 days and send alerts.

        A practice is considered stale when BOTH conditions hold:
        1. practices.updated_at < NOW() - INTERVAL '7 days'
        2. No activity_log entry with entity_type='practice' AND entity_id=p.id
           exists in the last 7 days.

        Sends:
        - One summary email to zero@ with ALL stale practices (HTML table).
        - One email per unique team leader listing only their stale practices.

        Returns:
            dict with keys: stale_count, leaders_notified, admin_notified, errors
        """
        result: dict[str, Any] = {
            "stale_count": 0,
            "leaders_notified": 0,
            "admin_notified": False,
            "errors": [],
        }

        try:
            stale = await self._get_stale_practices()
        except Exception as exc:
            logger.error("Failed to query stale practices", exc_info=True)
            result["errors"].append(f"DB query failed: {exc}")
            return result

        result["stale_count"] = len(stale)

        if not stale:
            logger.info("No stale practices found — nothing to notify.")
            return result

        logger.info(
            "Stale practices found",
            extra={"context": {"count": len(stale), "stale_days": STALE_DAYS}},
        )

        # Send summary to admin
        try:
            await self._send_zero_summary(stale)
            result["admin_notified"] = True
        except Exception as exc:
            logger.error("Failed to send admin summary email", exc_info=True)
            result["errors"].append(f"Admin email failed: {exc}")

        # Group by team leader and send individual alerts
        by_leader: dict[str, list[dict[str, Any]]] = {}
        for practice in stale:
            leader_email: str | None = practice.get("assigned_to")
            if not leader_email:
                continue
            by_leader.setdefault(leader_email, []).append(practice)

        for leader_email, practices in by_leader.items():
            try:
                await self._send_team_leader_alert(leader_email, practices)
                result["leaders_notified"] += 1
            except Exception as exc:
                logger.error(
                    "Failed to send team-leader alert",
                    extra={"context": {"leader": leader_email}},
                    exc_info=True,
                )
                result["errors"].append(f"Leader email ({leader_email}) failed: {exc}")

        logger.info("Stale practice notification run complete", extra={"context": result})
        return result

    # ------------------------------------------------------------------
    # Private: DB query
    # ------------------------------------------------------------------

    async def _get_stale_practices(self) -> list[dict[str, Any]]:
        """
        Return active practices where BOTH:
        1. practices.updated_at < NOW() - INTERVAL '7 days'
        2. No activity_log entry (entity_type='practice', entity_id=p.id)
           exists in the last 7 days.

        Each row contains:
            id, client_name, practice_type_name, status, assigned_to,
            days_stale, updated_at
        """
        query = """
            SELECT
                p.id,
                c.full_name                          AS client_name,
                COALESCE(pt.name, 'N/A')             AS practice_type_name,
                p.status,
                p.assigned_to,
                EXTRACT(
                    DAY FROM (NOW() - p.updated_at)
                )::int                               AS days_stale,
                p.updated_at
            FROM practices p
            JOIN clients c ON c.id = p.client_id
            LEFT JOIN practice_types pt ON pt.id = p.practice_type_id
            WHERE
                p.status = ANY($1::text[])
                AND p.updated_at < NOW() - INTERVAL '7 days'
                AND NOT EXISTS (
                    SELECT 1
                    FROM activity_log al
                    WHERE al.entity_type = 'practice'
                      AND al.entity_id   = p.id::text
                      AND al.created_at  > NOW() - INTERVAL '7 days'
                )
            ORDER BY p.updated_at ASC
        """
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(query, list(ACTIVE_STATUSES))
            return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Private: Email senders
    # ------------------------------------------------------------------

    async def _send_zero_summary(self, stale: list[dict[str, Any]]) -> None:
        """
        Send an HTML summary email to zero@ listing ALL stale practices,
        grouped by team leader.
        """
        import httpx

        today: str = date.today().isoformat()
        subject = f"\u23f0 {len(stale)} pratiche ferme da {STALE_DAYS}+ giorni \u2014 {today}"

        # Group by leader for the table
        by_leader: dict[str, list[dict[str, Any]]] = {}
        for p in stale:
            leader: str = p.get("assigned_to") or "Non assegnata"
            by_leader.setdefault(leader, []).append(p)

        # Build HTML rows grouped by leader
        rows_html = ""
        for leader, practices in sorted(by_leader.items()):
            rows_html += (
                f'<tr><td colspan="6" style="background:#1e293b;color:#94a3b8;'
                f'padding:6px 10px;font-size:12px;font-weight:600;">'
                f"Team Leader: {leader}</td></tr>\n"
            )
            for p in practices:
                crm_url = CRM_PRACTICE_URL.format(id=p["id"])
                updated_str = _fmt_datetime(p.get("updated_at"))
                rows_html += (
                    f"<tr>"
                    f'<td style="{_TD}">'
                    f'<a href="{crm_url}" style="color:#60a5fa;">#{p["id"]}</a></td>'
                    f'<td style="{_TD}">{_esc(p["client_name"])}</td>'
                    f'<td style="{_TD}">{_esc(p["practice_type_name"])}</td>'
                    f'<td style="{_TD}">{_esc(p["status"])}</td>'
                    f'<td style="{_TD}">{updated_str}</td>'
                    f'<td style="{_TD};color:#f87171;font-weight:600;">'
                    f'{p["days_stale"]} giorni</td>'
                    f"</tr>\n"
                )

        body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
          <div style="max-width:820px;margin:0 auto;">
            <h2 style="color:#f1f5f9;margin-bottom:4px;">
              \u23f0 Pratiche ferme da {STALE_DAYS}+ giorni
            </h2>
            <p style="color:#94a3b8;margin-top:0;">
              Report generato il {today} &mdash; {len(stale)} pratiche totali
            </p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
              <thead>
                <tr style="background:#1e3a5f;">
                  <th style="{_TH}">ID</th>
                  <th style="{_TH}">Cliente</th>
                  <th style="{_TH}">Tipo pratica</th>
                  <th style="{_TH}">Status</th>
                  <th style="{_TH}">Ultimo aggiorn.</th>
                  <th style="{_TH}">Giorni ferma</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            <p style="margin-top:24px;font-size:13px;color:#64748b;">
              Inviato automaticamente da Zantara CRM &mdash;
              <a href="https://zantara-crm.vercel.app" style="color:#60a5fa;">
                Apri CRM
              </a>
            </p>
          </div>
        </body>
        </html>
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={"to": ADMIN_EMAIL, "subject": subject, "body": body},
            )
            response.raise_for_status()

        logger.info(
            "Admin summary sent",
            extra={"context": {"to": ADMIN_EMAIL, "stale_count": len(stale)}},
        )

    async def _send_team_leader_alert(
        self,
        email: str,
        practices: list[dict[str, Any]],
    ) -> None:
        """
        Send a friendly, actionable email to a team leader listing their stale practices.
        Subject: ⏰ Pratiche in attesa — aggiornamento richiesto
        """
        import httpx

        subject = "\u23f0 Pratiche in attesa \u2014 aggiornamento richiesto"

        rows_html = ""
        for p in practices:
            crm_url = CRM_PRACTICE_URL.format(id=p["id"])
            _updated_str = _fmt_datetime(p.get("updated_at"))
            rows_html += (
                f"<tr>"
                f'<td style="{_TD}">'
                f'<a href="{crm_url}" style="color:#60a5fa;">#{p["id"]}</a></td>'
                f'<td style="{_TD}">{_esc(p["client_name"])}</td>'
                f'<td style="{_TD}">{_esc(p["practice_type_name"])}</td>'
                f'<td style="{_TD}">{_esc(p["status"])}</td>'
                f'<td style="{_TD};color:#f87171;font-weight:600;">'
                f'{p["days_stale"]} giorni</td>'
                f"</tr>\n"
            )

        body = f"""
        <html>
        <body style="font-family:Arial,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;">
          <div style="max-width:700px;margin:0 auto;">
            <h2 style="color:#f1f5f9;margin-bottom:4px;">
              Ciao! \ud83d\udc4b Alcune pratiche hanno bisogno della tua attenzione.
            </h2>
            <p style="color:#cbd5e1;line-height:1.6;">
              Alcune tue pratiche non hanno aggiornamenti da <strong>{STALE_DAYS}+ giorni</strong>.
              Puoi controllare lo stato e aggiungere una nota nel CRM?
              Basta un veloce aggiornamento per tenere tutto in ordine. \ud83d\ude4f
            </p>
            <table style="width:100%;border-collapse:collapse;margin-top:16px;">
              <thead>
                <tr style="background:#1e3a5f;">
                  <th style="{_TH}">ID</th>
                  <th style="{_TH}">Cliente</th>
                  <th style="{_TH}">Tipo pratica</th>
                  <th style="{_TH}">Status</th>
                  <th style="{_TH}">Giorni senza agg.</th>
                </tr>
              </thead>
              <tbody>
                {rows_html}
              </tbody>
            </table>
            <p style="margin-top:20px;color:#94a3b8;font-size:13px;">
              Clicca sull&rsquo;ID pratica per aprirla direttamente nel CRM.
            </p>
            <p style="margin-top:24px;font-size:13px;color:#64748b;">
              Grazie mille! \u2014 Zantara CRM
            </p>
          </div>
        </body>
        </html>
        """

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                _EMAIL_API_URL,
                headers={"X-API-Key": _EMAIL_API_KEY},
                json={"to": email, "subject": subject, "body": body},
            )
            response.raise_for_status()

        logger.info(
            "Team-leader alert sent",
            extra={"context": {"to": email, "practice_count": len(practices)}},
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TH = (
    "padding:8px 12px;text-align:left;font-size:12px;"
    "color:#93c5fd;font-weight:600;border-bottom:1px solid #334155;"
)
_TD = (
    "padding:7px 12px;font-size:13px;border-bottom:1px solid #1e293b;"
    "color:#cbd5e1;vertical-align:top;"
)


def _esc(value: Any) -> str:
    """Minimal HTML escaping for table cell content."""
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _fmt_datetime(value: Any) -> str:
    """Format a datetime or date value to a short readable string."""
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return str(value)


# ---------------------------------------------------------------------------
# Standalone task entry point (for autonomous scheduler / OpenClaw cron)
# ---------------------------------------------------------------------------


async def run_stale_practice_notifier_task(db_pool: asyncpg.Pool) -> dict[str, Any]:
    """
    Task function for autonomous scheduler.

    Args:
        db_pool: Active asyncpg connection pool.

    Returns:
        Result dict with stale_count, leaders_notified, admin_notified, errors.
    """
    service = StalePracticeNotifier(db_pool)
    return await service.check_and_notify()
