"""
Welcome Email Service — Trigger 1b
=====================================
Sends a welcome email 30 minutes after create_client.

Delay: scheduled via APScheduler run_date=now+30min (scheduler already running).
Attachment: data/assets/brochure_balizero_en.pdf (base64 encoded).
Sending: POST /api/notifications/send-email with X-API-Key (Brevo).

Guard conditions (skip silently if any fail):
    - client.email is not NULL
    - No existing activity_log with action=welcome_email_sent for this client
    - _EMAIL_WELCOME_ACTIVE is True (default: True — email goes live on deploy)
"""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from backend.services.crm.birthday_notifier_service import NATIONALITY_LANGUAGE_MAP
from backend.services.crm.welcome.welcome_templates import (
    ADVISOR_FALLBACK,
    WELCOME_EMAIL_CTA,
    WELCOME_EMAIL_OPENING,
    WELCOME_EMAIL_SUBJECT,
    WELCOME_EMAIL_TEAM_ASSIGNED,
    WELCOME_EMAIL_TEAM_UNASSIGNED,
    WELCOME_EMAIL_WHO_WE_ARE,
)

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ─── ACTIVATION GATE ─────────────────────────────────────
# True by default — email goes live on deploy.
# WhatsApp has its own separate gate.
_EMAIL_WELCOME_ACTIVE: bool = True

ACTIVITY_ACTION = "welcome_email_sent"

# ─── EMAIL API (Brevo via internal endpoint) ─────────────
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "REDACTED-ROTATED-KEY")

# ─── BROCHURE PATH ───────────────────────────────────────
_BROCHURE_PATH = Path(__file__).parent.parent.parent.parent.parent / "data" / "assets" / "brochure_balizero_en.pdf"


def schedule_client_welcome_email(client_id: int, db_pool: "asyncpg.Pool") -> None:
    """
    Schedule the welcome email to be sent 30 minutes from now.
    Called from BackgroundTasks in the clients router.
    Uses the global APScheduler instance.
    """
    if not _EMAIL_WELCOME_ACTIVE:
        logger.debug("WelcomeEmail: inactive, skipping client %d", client_id)
        return

    try:
        from backend.app.modules.notifications.scheduler import get_scheduler

        scheduler = get_scheduler()
        if not scheduler or not scheduler.scheduler:
            logger.warning("WelcomeEmail: scheduler not available, falling back to asyncio.sleep pattern")
            import asyncio
            asyncio.create_task(_send_with_delay(client_id, db_pool))
            return

        run_at = datetime.now(timezone.utc) + timedelta(minutes=30)
        job_id = f"welcome_email_{client_id}"

        scheduler.scheduler.add_job(
            _send_client_welcome_now,
            "date",
            run_date=run_at,
            args=[client_id, db_pool],
            id=job_id,
            replace_existing=True,
            misfire_grace_time=300,  # up to 5min late is OK
        )
        logger.info("WelcomeEmail: scheduled for client %d at %s", client_id, run_at.strftime("%H:%M UTC"))

    except Exception:
        logger.error("WelcomeEmail: failed to schedule for client %d", client_id, exc_info=True)


async def _send_with_delay(client_id: int, db_pool: "asyncpg.Pool") -> None:
    """Fallback: asyncio.sleep(1800) if scheduler unavailable."""
    import asyncio
    await asyncio.sleep(1800)
    await _send_client_welcome_now(client_id, db_pool)


async def _send_client_welcome_now(client_id: int, db_pool: "asyncpg.Pool") -> None:
    """Execute the actual email send. Called by APScheduler after the 30-min delay."""
    try:
        await _send_client_welcome_impl(client_id, db_pool)
    except Exception:
        logger.error("WelcomeEmail: unhandled error for client %d", client_id, exc_info=True)


async def _send_client_welcome_impl(client_id: int, db_pool: "asyncpg.Pool") -> None:
    async with db_pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT id, full_name, email, nationality, assigned_to FROM clients WHERE id = $1",
            client_id,
        )
        if not client:
            logger.warning("WelcomeEmail: client %d not found", client_id)
            return

        email = (client["email"] or "").strip()
        if not email:
            logger.info("WelcomeEmail: client %d has no email, skipping", client_id)
            return

        # Idempotency check
        already_sent = await conn.fetchval(
            "SELECT id FROM activity_log WHERE client_id = $1 AND action = $2 LIMIT 1",
            client_id, ACTIVITY_ACTION,
        )
        if already_sent:
            logger.info("WelcomeEmail: already sent for client %d, skipping", client_id)
            return

    # Language resolution
    nationality = client["nationality"] or ""
    lang = NATIONALITY_LANGUAGE_MAP.get(nationality, "en")

    # Variable resolution
    first_name = (client["full_name"] or "").split()[0] if client["full_name"] else ""
    assigned_to = client["assigned_to"] or ""
    advisor_first = assigned_to.split("@")[0].capitalize() if assigned_to else ""

    # Build HTML email
    subject = WELCOME_EMAIL_SUBJECT[lang]
    html_body = _build_html(lang, first_name, advisor_first, assigned_to)

    # Build payload
    payload: dict = {
        "to": email,
        "subject": subject,
        "body": html_body,
    }

    # Attach brochure if available
    if _BROCHURE_PATH.exists():
        try:
            with open(_BROCHURE_PATH, "rb") as f:
                brochure_b64 = base64.b64encode(f.read()).decode()
            payload["attachments"] = [
                {
                    "name": "Bali_Zero_Introduction.pdf",
                    "content": brochure_b64,
                    "contentType": "application/pdf",
                }
            ]
        except Exception:
            logger.warning("WelcomeEmail: could not read brochure for client %d", client_id, exc_info=True)
    else:
        logger.warning("WelcomeEmail: brochure not found at %s", _BROCHURE_PATH)

    # Send
    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            _EMAIL_API_URL,
            json=payload,
            headers={"X-API-Key": _EMAIL_API_KEY},
        )

    if resp.status_code == 200:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (client_id, action, details, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT DO NOTHING
                """,
                client_id, ACTIVITY_ACTION, f"lang={lang} email={email}",
            )
        logger.info("WelcomeEmail: sent to client %d (lang=%s, email=%s)", client_id, lang, email)
    else:
        logger.error(
            "WelcomeEmail: send failed for client %d: %d %s",
            client_id, resp.status_code, resp.text[:200],
        )


# ─────────────────────────────────────────────────────────
# HTML BUILDER
# ─────────────────────────────────────────────────────────

def _build_html(lang: str, first_name: str, advisor_first: str, advisor_email: str) -> str:
    """Assemble the 7-block welcome HTML email."""

    # Block 1 — Emotional opening
    opening = WELCOME_EMAIL_OPENING[lang].format(first_name=first_name)

    # Block 2 — Who we are
    who_we_are = WELCOME_EMAIL_WHO_WE_ARE[lang]

    # Block 5 — Your team
    if advisor_email:
        team_line = WELCOME_EMAIL_TEAM_ASSIGNED[lang].format(advisor_name=advisor_first)
    else:
        team_line = WELCOME_EMAIL_TEAM_UNASSIGNED[lang]

    # Block 6 — CTA
    cta = WELCOME_EMAIL_CTA[lang]

    # Deterministic system table rows (same in all languages for readability)
    table_rows = [
        ("Prices from a verified database", "Strategy and judgment"),
        ("Deadlines from a legal calendar", "Client relationships"),
        ("Documents from official registries", "Complex negotiations"),
        ("Status tracking and alerts", "Problem solving"),
    ]
    table_html = "\n".join(
        f"""
        <tr>
            <td style="padding:10px 16px;border-bottom:1px solid #2a2a30;font-size:13px;color:#edeae4;">{a}</td>
            <td style="padding:10px 16px;border-bottom:1px solid #2a2a30;font-size:13px;color:#edeae4;">{b}</td>
        </tr>"""
        for a, b in table_rows
    )

    # Service cards (same 4 in all languages)
    services = [
        ("Immigration", "Visas, KITAS, KITAP, retirement visa"),
        ("Business Setup", "PT PMA, virtual office, NIB, OSS"),
        ("Tax &amp; Compliance", "NPWP, SPT, LKPM, withholding"),
        ("Property", "Land structure, Hak Pakai, leasehold"),
    ]
    cards_html = ""
    for svc_title, svc_desc in services:
        cards_html += f"""
        <td style="width:25%;padding:0 6px;">
            <div style="background:#1c1c22;border-radius:6px;padding:14px 12px;text-align:center;">
                <div style="font-size:12px;font-weight:700;color:#d4845a;margin-bottom:6px;">{svc_title}</div>
                <div style="font-size:11px;color:#9e9b95;line-height:1.4;">{svc_desc}</div>
            </div>
        </td>"""

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#0c0c0e;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
<div style="max-width:600px;margin:0 auto;padding:20px 0;">

  <!-- HEADER -->
  <div style="background:#0c0c0e;border-bottom:2px solid #d4845a;padding:32px 32px 24px;">
    <div style="font-size:22px;font-weight:700;color:#edeae4;letter-spacing:1px;">BALI ZERO</div>
    <div style="font-size:12px;color:#c9a96e;margin-top:4px;font-style:italic;">Guided by humans. Powered by AI.</div>
  </div>

  <!-- BLOCK 1: Emotional opening -->
  <div style="background:#111115;padding:28px 32px;">
    <div style="font-size:15px;line-height:1.7;color:#edeae4;">{opening}</div>
  </div>

  <!-- BLOCK 2: Who we are -->
  <div style="background:#0c0c0e;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:12px;">WHO WE ARE</div>
    <div style="width:40px;height:2px;background:#d4845a;margin-bottom:16px;"></div>
    <div style="font-size:13.5px;line-height:1.75;color:#edeae4;">{who_we_are}</div>
  </div>

  <!-- BLOCK 3: How it works — 2-column table -->
  <div style="background:#111115;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:16px;">HOW IT WORKS</div>
    <table style="width:100%;border-collapse:collapse;border:1px solid #2a2a30;border-radius:6px;overflow:hidden;">
      <tr style="background:#1c1c22;">
        <th style="padding:10px 16px;text-align:left;font-size:11px;font-weight:700;color:#c9a96e;text-transform:uppercase;letter-spacing:1px;">Deterministic System</th>
        <th style="padding:10px 16px;text-align:left;font-size:11px;font-weight:700;color:#c9a96e;text-transform:uppercase;letter-spacing:1px;">Human Intelligence</th>
      </tr>
      {table_html}
    </table>
  </div>

  <!-- BLOCK 4: Our services — 4 cards -->
  <div style="background:#0c0c0e;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:16px;">OUR SERVICES</div>
    <table style="width:100%;border-collapse:collapse;">
      <tr>{cards_html}</tr>
    </table>
  </div>

  <!-- BLOCK 5: Your team -->
  <div style="background:#111115;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:12px;">YOUR TEAM</div>
    <div style="font-size:13.5px;line-height:1.7;color:#edeae4;">{team_line}</div>
  </div>

  <!-- BLOCK 6: CTA -->
  <div style="background:#d4845a;padding:24px 32px;text-align:center;">
    <div style="font-size:15px;font-weight:700;color:#0c0c0e;">{cta}</div>
  </div>

  <!-- BLOCK 7: Footer -->
  <div style="background:#0c0c0e;padding:20px 32px;border-top:1px solid #2a2a30;">
    <div style="font-size:11px;color:#9e9b95;text-align:center;line-height:1.8;">
      zantara@balizero.com &nbsp;·&nbsp;
      wa.me/6281338051876 &nbsp;·&nbsp;
      <a href="https://www.balizero.com" style="color:#c9a96e;text-decoration:none;">www.balizero.com</a>
      &nbsp;·&nbsp; Canggu, Bali
    </div>
    <div style="font-size:10px;color:#3a3a40;text-align:center;margin-top:8px;">
      You received this email because you recently became a client of Bali Zero.
    </div>
  </div>

</div>
</body>
</html>"""
