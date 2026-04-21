"""
Welcome Email Service — Trigger 1b
=====================================
Sends a welcome email 30 minutes after create_client.

Delay strategy: save pending record in activity_log, process via Air cron every 15 min.
This is resilient to auto_stop — the cron on Air calls /api/cron/notifiers/welcome-pending
which wakes the pod and processes all pending welcome emails.

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

from backend.app.core.config import settings
from backend.services.crm.birthday_notifier_service import NATIONALITY_LANGUAGE_MAP
from backend.services.crm.welcome.welcome_templates import WELCOME_EMAIL_SUBJECT
from backend.services.notifications.email_audit import (
    log_email_attempt,
    notify_email_failure_critical,
    record_email_result,
)

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ─── ACTIVATION GATE ─────────────────────────────────────
# True by default — email goes live on deploy.
# WhatsApp has its own separate gate.
_EMAIL_WELCOME_ACTIVE: bool = True

ACTIVITY_ACTION = "welcome_email_sent"
ACTIVITY_ACTION_PENDING = "welcome_email_pending"
WELCOME_DELAY_MINUTES = 30

# ─── EMAIL API (Brevo via internal endpoint) ─────────────
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "")

# ─── BROCHURE ────────────────────────────────────────────
# Served from Vercel (always available on Fly.io)
_BROCHURE_URL = "https://kita.balizero.com/static/brochure_balizero_en.pdf"
# Local path kept as fallback for dev/testing
_BROCHURE_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "data"
    / "assets"
    / "brochure_balizero_en.pdf"
)


async def schedule_client_welcome_email(client_id: int, db_pool: asyncpg.Pool) -> None:
    """
    Save a pending welcome email record in welcome_email_queue.
    The Air cron calls /api/cron/notifiers/welcome-pending every 15 min
    to process records whose scheduled_at has passed.

    This is resilient to Fly.io auto_stop — no in-process timer needed.
    """
    if not _EMAIL_WELCOME_ACTIVE:
        logger.debug("WelcomeEmail: inactive, skipping client %d", client_id)
        return

    try:
        send_at = datetime.now(timezone.utc) + timedelta(minutes=WELCOME_DELAY_MINUTES)

        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO welcome_email_queue (client_id, scheduled_at, created_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (client_id) DO NOTHING
                """,
                client_id,
                send_at,
            )
        logger.info(
            "WelcomeEmail: queued for client %d, will send at %s UTC",
            client_id,
            send_at.strftime("%H:%M"),
        )
    except Exception:
        logger.error("WelcomeEmail: failed to queue for client %d", client_id, exc_info=True)


async def process_pending_welcome_emails(db_pool: asyncpg.Pool) -> dict[str, int]:
    """
    Process all pending welcome emails whose scheduled_at has passed.
    Called by /api/cron/notifiers/welcome-pending endpoint every 15 min from Air.

    Returns: {"processed": N, "sent": N, "skipped": N, "failed": N}
    """
    stats = {"processed": 0, "sent": 0, "skipped": 0, "failed": 0}
    now = datetime.now(timezone.utc)

    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, client_id, scheduled_at
            FROM welcome_email_queue
            WHERE scheduled_at <= $1
            ORDER BY scheduled_at ASC
            LIMIT 50
            """,
            now,
        )

    for row in rows:
        stats["processed"] += 1
        client_id = row["client_id"]
        row_id = row["id"]

        # Atomic claim: delete the row to prevent duplicate processing
        async with db_pool.acquire() as conn:
            deleted = await conn.fetchval(
                "DELETE FROM welcome_email_queue WHERE id = $1 RETURNING id",
                row_id,
            )
        if not deleted:
            stats["skipped"] += 1
            continue  # Already processed by another worker

        try:
            await _send_client_welcome_impl(client_id, db_pool)
            stats["sent"] += 1
        except Exception:
            logger.error("WelcomeEmail: send failed for client %d", client_id, exc_info=True)
            stats["failed"] += 1

    return stats


async def _send_client_welcome_impl(client_id: int, db_pool: asyncpg.Pool) -> None:
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

        # Idempotency check: verify not already in sent log
        already_sent = await conn.fetchval(
            """
            SELECT 1 FROM notification_alerts
            WHERE client_id = $1 AND alert_type = $2
            LIMIT 1
            """,
            client_id,
            ACTIVITY_ACTION,
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

    # Resolve advisor WhatsApp from team_members table
    advisor_wa: str | None = None
    if assigned_to:
        async with db_pool.acquire() as conn:
            advisor_wa = await conn.fetchval(
                "SELECT whatsapp FROM team_members WHERE email = $1",
                assigned_to,
            )

    # Build HTML email
    subject = "[CLIENT] " + WELCOME_EMAIL_SUBJECT[lang]
    html_body = _build_html(lang, first_name, advisor_first, assigned_to, advisor_wa)

    # Build payload with CC (team leader) and BCC (admin)
    payload: dict = {
        "to": email,
        "subject": subject,
        "body": html_body,
        "bcc": settings.admin_notification_email,
    }
    # CC the assigned team leader if present and different from recipient
    if assigned_to and assigned_to != email:
        payload["cc"] = assigned_to

    # Attach brochure — fetch from public URL (works on Fly.io), fallback to local file in dev
    try:
        async with httpx.AsyncClient(timeout=20.0) as fetch:
            br = await fetch.get(_BROCHURE_URL)
        br.raise_for_status()
        brochure_b64 = base64.b64encode(br.content).decode()
        payload["attachments"] = [
            {
                "name": "Bali_Zero_Introduction.pdf",
                "content": brochure_b64,
                "contentType": "application/pdf",
            },
        ]
        logger.info("WelcomeEmail: brochure attached from URL (%d bytes)", len(br.content))
    except Exception:
        # Fallback: try local file (dev only)
        if _BROCHURE_PATH.exists():
            try:
                with open(_BROCHURE_PATH, "rb") as f:
                    brochure_b64 = base64.b64encode(f.read()).decode()
                payload["attachments"] = [
                    {
                        "name": "Bali_Zero_Introduction.pdf",
                        "content": brochure_b64,
                        "contentType": "application/pdf",
                    },
                ]
                logger.info("WelcomeEmail: brochure attached from local file")
            except Exception:
                logger.warning("WelcomeEmail: could not attach brochure for client %d", client_id, exc_info=True)
        else:
            logger.warning("WelcomeEmail: brochure unavailable for client %d", client_id)

    # Audit row — written before network call so a crash mid-send is visible.
    audit_row_id = await log_email_attempt(
        db_pool,
        email_type="welcome",
        to_email=email,
        subject=subject,
        client_id=client_id,
    )

    # Send — wrapped so an exception is captured into the audit trail
    # instead of propagating up and being counted as a permanent failure
    # (the welcome_email_queue row was already DELETEd, so losing it here
    # means the email is gone forever without this audit).
    send_error: str | None = None
    status_code = 0
    try:
        async with httpx.AsyncClient(timeout=30.0) as http:
            resp = await http.post(
                _EMAIL_API_URL,
                json=payload,
                headers={"X-API-Key": _EMAIL_API_KEY},
            )
        status_code = resp.status_code
        if status_code != 200:
            send_error = f"status={status_code} body={resp.text[:200]}"
    except Exception as e:
        send_error = f"exception: {e}"

    if send_error is None:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO notification_alerts (client_id, alert_type, status, message, sent_at)
                VALUES ($1, $2, 'sent', $3, NOW())
                ON CONFLICT (client_id, alert_type, created_date) DO NOTHING
                """,
                client_id,
                ACTIVITY_ACTION,
                f"lang={lang} email={email}",
            )
        await record_email_result(
            db_pool, audit_row_id, status="sent", provider="brevo",
        )
        logger.info("WelcomeEmail: sent to client %d (lang=%s, email=%s)", client_id, lang, email)
    else:
        logger.error(
            "WelcomeEmail: send failed for client %d: %s",
            client_id,
            send_error,
        )
        await record_email_result(
            db_pool, audit_row_id, status="failed", provider="brevo",
            error_message=send_error,
        )
        notify_email_failure_critical(
            email_type="welcome",
            to_email=email,
            subject=subject,
            practice_id=None,
            error=send_error,
        )


# ─────────────────────────────────────────────────────────
# HTML BUILDER
# ─────────────────────────────────────────────────────────


# SVG icons (base64) for service cards — from reference design
_SVG_IMMIGRATION = "PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIgMkw0IDV2Ni4wOWMwIDUuMDUgMy40MSA5Ljc2IDggMTAuOTEgNC41OS0xLjE1IDgtNS44NiA4LTEwLjkxVjVsLTgtM3oiIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjxwYXRoIGQ9Ik05IDEybDIgMiA0LTQiIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg=="
_SVG_BUSINESS = "PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cmVjdCB4PSIzIiB5PSIzIiB3aWR0aD0iMTgiIGhlaWdodD0iMTgiIHJ4PSIyIiBzdHJva2U9IiNmOWNhNTUiIHN0cm9rZS13aWR0aD0iMS41Ii8+PHBhdGggZD0iTTMgOWgxOE03IDN2MTgiIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIxLjUiLz48L3N2Zz4="
_SVG_TAX = "PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMTIgMnYyME0xNyA1SDkuNWExLjUgMS41IDAgMDAwIDNIMTVhMS41IDEuNSAwIDAxMCAzSDciIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjwvc3ZnPg=="
_SVG_PROPERTY = "PHN2ZyB3aWR0aD0iMjAiIGhlaWdodD0iMjAiIHZpZXdCb3g9IjAgMCAyNCAyNCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj48cGF0aCBkPSJNMyAyMWgxOE05IDIxVjNINXYxOE0xNSAyMVY4aDR2MTMiIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIxLjUiIHN0cm9rZS1saW5lY2FwPSJyb3VuZCIgc3Ryb2tlLWxpbmVqb2luPSJyb3VuZCIvPjxwYXRoIGQ9Ik03IDdoLjAxTTcgMTFoLjAxTTcgMTVoLjAxTTE3IDEyaC4wMU0xNyAxNmguMDEiIHN0cm9rZT0iI2Y5Y2E1NSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz48L3N2Zz4="

# Default WhatsApp for Bali Zero (used when no per-advisor number available)
_BZ_WHATSAPP = "628213107363"


def _build_html(
    _lang: str,
    first_name: str,
    advisor_first: str,
    _advisor_email: str,
    advisor_wa: str | None = None,
) -> str:
    """Assemble the welcome HTML email — dark premium design."""
    advisor_name = advisor_first if advisor_first else "our team"
    wa_num = (advisor_wa or _BZ_WHATSAPP).lstrip("+")
    cta_label = f"Chat with {advisor_name} on WhatsApp"

    # BG constants — all inline style, no separate bgcolor attr (Zoho strips bgcolor)
    BG = "background-color:#0c0d0f;"
    BG2 = "background-color:#101215;"
    BG3 = "background-color:#161a1e;"
    BG4 = "background-color:#1a1914;"
    BGDIV = "background-color:#2a2520;"
    BGGOLD = "background-color:#f9ca55;"

    divider = (
        f'<tr><td style="padding:0 40px;{BG}">'
        '<table cellspacing="0" cellpadding="0" border="0" width="100%"><tr>'
        '<td style="height:1px;background-color:#2a2520;font-size:1px;line-height:1px;">&nbsp;</td>'
        '</tr></table></td></tr>'
    )

    return f"""<!DOCTYPE html>
<html lang="en" xmlns="http://www.w3.org/1999/xhtml">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta http-equiv="X-UA-Compatible" content="IE=edge">
  <title>Welcome to Bali Zero</title>
  <style>
    body,table,td,a{{-webkit-text-size-adjust:100%;-ms-text-size-adjust:100%;}}
    table,td{{mso-table-lspace:0pt;mso-table-rspace:0pt;border-collapse:collapse;}}
    img{{border:0;height:auto;outline:none;text-decoration:none;-ms-interpolation-mode:bicubic;}}
    a[x-apple-data-detectors]{{color:inherit!important;text-decoration:none!important;}}
    @media only screen and (max-width:600px){{
      .wrap{{width:100%!important;}}
      .pad{{padding-left:24px!important;padding-right:24px!important;}}
      .hh{{font-size:34px!important;line-height:40px!important;}}
      .card{{display:block!important;width:100%!important;padding-right:0!important;padding-left:0!important;padding-bottom:10px!important;}}
    }}
  </style>
</head>
<body style="margin:0;padding:0;{BG}">

  <div style="display:none;max-height:0;overflow:hidden;font-size:1px;color:#0c0d0f;">We handle the bureaucracy. You focus on Bali.</div>

  <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;{BG}">
    <tr>
      <td align="center" style="padding:32px 16px 48px;{BG}">
        <table cellspacing="0" cellpadding="0" border="0" width="580" class="wrap" style="max-width:580px;border-collapse:collapse;">

          <!-- ══ HERO ══ -->
          <tr>
            <td style="padding:44px 40px 40px;{BG}border-radius:14px 14px 0 0;border:1px solid #1e1c18;border-bottom:none;" class="pad">
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr>
                  <td align="left" style="padding-bottom:36px;">
                    <table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr>
                      <td width="112" height="112" style="border-radius:50%;{BG}">
                        <img src="https://kita.balizero.com/static/balizero-logo-clean.png" width="112" height="112" alt="Bali Zero" style="display:block;border-radius:50%;{BG}" />
                      </td>
                    </tr></table>
                  </td>
                </tr>
                <tr>
                  <td class="hh" style="font-family:Arial,Helvetica,sans-serif;font-size:42px;line-height:48px;font-weight:900;color:#ffffff;letter-spacing:-1.5px;text-transform:uppercase;">
                    Welcome,<br><span style="color:#f9ca55;">{first_name}.</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding:20px 0 0;">
                    <table cellspacing="0" cellpadding="0" border="0"><tr><td width="48" height="2" style="{BGGOLD}font-size:1px;line-height:1px;">&nbsp;</td></tr></table>
                  </td>
                </tr>
                <tr>
                  <td style="padding-top:18px;font-family:Arial,Helvetica,sans-serif;font-size:16px;line-height:27px;color:#8a7a6a;font-weight:400;">
                    You just made the smartest move for your life in Indonesia.<br>
                    <span style="color:#f9ca55;font-weight:700;">We&#39;ll take it from here.</span>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ══ WHAT HAPPENS NEXT ══ -->
          <tr>
            <td style="padding:36px 40px 32px;{BG2}border-left:1px solid #1e1c18;border-right:1px solid #1e1c18;" class="pad">
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr><td style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#f9ca55;text-transform:uppercase;letter-spacing:4px;padding-bottom:28px;">What happens next</td></tr>
              </table>
              <!-- step 1 -->
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr>
                  <td width="52" valign="top" style="padding-right:16px;padding-bottom:20px;">
                    <table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr>
                      <td width="44" height="44" align="center" valign="middle" style="{BG4}border-radius:10px;border:1px solid #2e2b22;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:900;color:#f9ca55;text-align:center;vertical-align:middle;">01</td>
                    </tr></table>
                  </td>
                  <td valign="middle" style="padding-bottom:20px;">
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#ffffff;line-height:20px;">{advisor_name} will reach out</div>
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#8a7a6a;line-height:19px;padding-top:3px;">Quick intro call to understand your situation</div>
                  </td>
                </tr>
                <tr><td colspan="2" style="padding:0 0 20px 20px;"><table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr><td width="1" height="20" style="{BGDIV}font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td></tr>
              </table>
              <!-- step 2 -->
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr>
                  <td width="52" valign="top" style="padding-right:16px;padding-bottom:20px;">
                    <table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr>
                      <td width="44" height="44" align="center" valign="middle" style="{BG4}border-radius:10px;border:1px solid #2e2b22;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:900;color:#c8a040;text-align:center;vertical-align:middle;">02</td>
                    </tr></table>
                  </td>
                  <td valign="middle" style="padding-bottom:20px;">
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#ffffff;line-height:20px;">We build your roadmap</div>
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#8a7a6a;line-height:19px;padding-top:3px;">Clear timeline, pricing, documents needed</div>
                  </td>
                </tr>
                <tr><td colspan="2" style="padding:0 0 20px 20px;"><table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr><td width="1" height="20" style="{BGDIV}font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td></tr>
              </table>
              <!-- step 3 -->
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr>
                  <td width="52" valign="top" style="padding-right:16px;">
                    <table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr>
                      <td width="44" height="44" align="center" valign="middle" style="{BG4}border-radius:10px;border:1px solid #2e2b22;font-family:Arial,Helvetica,sans-serif;font-size:14px;font-weight:900;color:#9a7828;text-align:center;vertical-align:middle;">03</td>
                    </tr></table>
                  </td>
                  <td valign="middle">
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:15px;font-weight:700;color:#ffffff;line-height:20px;">We handle everything</div>
                    <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;color:#8a7a6a;line-height:19px;padding-top:3px;">You focus on Bali. We handle the bureaucracy.</div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          {divider}

          <!-- ══ SERVICES ══ -->
          <tr>
            <td style="padding:36px 40px 28px;{BG2}border-left:1px solid #1e1c18;border-right:1px solid #1e1c18;" class="pad">
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr><td style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#f9ca55;text-transform:uppercase;letter-spacing:4px;padding-bottom:20px;">How we help</td></tr>
              </table>
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr>
                  <td class="card" width="50%" valign="top" style="padding:0 5px 10px 0;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                      <tr><td style="padding:20px 16px;{BG3}border-radius:10px;border:1px solid #252320;">
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;margin-bottom:10px;">&#127250;</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:#ffffff;">Immigration</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8a7a6a;padding-top:5px;line-height:17px;">KITAS &middot; KITAP &middot; D12 &middot; E33G<br>Retirement &middot; Second Home</div>
                      </td></tr>
                    </table>
                  </td>
                  <td class="card" width="50%" valign="top" style="padding:0 0 10px 5px;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                      <tr><td style="padding:20px 16px;{BG3}border-radius:10px;border:1px solid #252320;">
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;margin-bottom:10px;">&#127970;</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:#ffffff;">Business</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8a7a6a;padding-top:5px;line-height:17px;">PT PMA &middot; OSS &middot; NIB<br>Virtual Office &middot; Licenses</div>
                      </td></tr>
                    </table>
                  </td>
                </tr>
                <tr>
                  <td class="card" width="50%" valign="top" style="padding:0 5px 10px 0;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                      <tr><td style="padding:20px 16px;{BG3}border-radius:10px;border:1px solid #252320;">
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;margin-bottom:10px;">&#128203;</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:#ffffff;">Tax &amp; Compliance</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8a7a6a;padding-top:5px;line-height:17px;">NPWP &middot; SPT &middot; LKPM<br>Withholding &middot; Reporting</div>
                      </td></tr>
                    </table>
                  </td>
                  <td class="card" width="50%" valign="top" style="padding:0 0 10px 5px;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                      <tr><td style="padding:20px 16px;{BG3}border-radius:10px;border:1px solid #252320;">
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:22px;line-height:26px;margin-bottom:10px;">&#127968;</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:700;color:#ffffff;">Property</div>
                        <div style="font-family:Arial,Helvetica,sans-serif;font-size:11px;color:#8a7a6a;padding-top:5px;line-height:17px;">Hak Pakai &middot; Leasehold<br>Due Diligence &middot; Structure</div>
                      </td></tr>
                    </table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ══ SOCIAL PROOF ══ -->
          <tr>
            <td style="padding:36px 40px;{BG}border-left:1px solid #1e1c18;border-right:1px solid #1e1c18;" class="pad" align="center">
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:54px;font-weight:900;color:#f9ca55;letter-spacing:-2px;line-height:54px;">10,800<span style="font-size:26px;vertical-align:super;color:#5a4a18;">+</span></div>
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#4a3a28;text-transform:uppercase;letter-spacing:4px;padding-top:10px;">Expats served since 2019</div>
            </td>
          </tr>

          {divider}

          <!-- ══ WHY US ══ -->
          <tr>
            <td style="padding:36px 40px 32px;{BG2}border-left:1px solid #1e1c18;border-right:1px solid #1e1c18;" class="pad">
              <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;">
                <tr><td style="font-family:Arial,Helvetica,sans-serif;font-size:10px;font-weight:700;color:#f9ca55;text-transform:uppercase;letter-spacing:4px;padding-bottom:22px;">Why Bali Zero</td></tr>
                <tr>
                  <td style="padding-bottom:16px;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;"><tr>
                      <td width="14" valign="top" style="padding-right:12px;padding-top:6px;"><table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr><td width="6" height="6" style="{BGGOLD}border-radius:3px;font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td>
                      <td style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#8a7a6a;"><strong style="color:#ffffff;font-weight:700;">AI-powered tracking.</strong> Every deadline, document, and regulation change monitored &mdash; nothing falls through the cracks.</td>
                    </tr></table>
                  </td>
                </tr>
                <tr>
                  <td style="padding-bottom:16px;">
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;"><tr>
                      <td width="14" valign="top" style="padding-right:12px;padding-top:6px;"><table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr><td width="6" height="6" style="{BGGOLD}border-radius:3px;font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td>
                      <td style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#8a7a6a;"><strong style="color:#ffffff;font-weight:700;">Based in Kerobokan.</strong> Real office, real team. We meet you in person and handle government offices directly.</td>
                    </tr></table>
                  </td>
                </tr>
                <tr>
                  <td>
                    <table cellspacing="0" cellpadding="0" border="0" width="100%" style="border-collapse:collapse;"><tr>
                      <td width="14" valign="top" style="padding-right:12px;padding-top:6px;"><table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;"><tr><td width="6" height="6" style="{BGGOLD}border-radius:3px;font-size:1px;line-height:1px;">&nbsp;</td></tr></table></td>
                      <td style="font-family:Arial,Helvetica,sans-serif;font-size:14px;line-height:22px;color:#8a7a6a;"><strong style="color:#ffffff;font-weight:700;">One team, everything.</strong> Immigration, company, tax, property &mdash; all under one roof.</td>
                    </tr></table>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- ══ CTA ══ -->
          <tr>
            <td style="padding:36px 40px 44px;{BG}border-radius:0 0 14px 14px;border:1px solid #1e1c18;border-top:none;" class="pad" align="center">
              <table cellspacing="0" cellpadding="0" border="0" style="border-collapse:collapse;">
                <tr>
                  <td style="{BGGOLD}border-radius:10px;">
                    <a href="https://wa.me/{wa_num}?text=Hi%20Bali%20Zero%2C%20I%20just%20signed%20up" target="_blank" style="display:inline-block;padding:16px 44px;font-family:Arial,Helvetica,sans-serif;font-size:13px;font-weight:900;color:#0c0d0f;text-decoration:none;text-transform:uppercase;letter-spacing:1.5px;">{cta_label}</a>
                  </td>
                </tr>
              </table>
              <div style="padding-top:14px;font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#4a3a28;">or reply directly to this email</div>
            </td>
          </tr>

          <!-- ══ FOOTER ══ -->
          <tr>
            <td align="center" style="padding:28px 40px 0;{BG}" class="pad">
              <div style="font-family:Arial,Helvetica,sans-serif;font-size:12px;color:#4a3a28;line-height:20px;">
                <strong style="color:#5a4a18;">Bali Zero</strong> &middot; Kerobokan, Bali, Indonesia<br>
                <a href="https://www.balizero.com" style="color:#c8a040;text-decoration:none;">balizero.com</a>
                &nbsp;&middot;&nbsp;
                <a href="https://www.instagram.com/balizero" style="color:#c8a040;text-decoration:none;">Instagram</a>
                &nbsp;&middot;&nbsp;
                <a href="https://wa.me/{wa_num}" style="color:#c8a040;text-decoration:none;">WhatsApp</a>
              </div>
              <div style="padding-top:12px;font-family:Arial,Helvetica,sans-serif;font-size:10px;color:#2a2520;letter-spacing:2px;text-transform:uppercase;">
                Powered by humans, fueled by a thinking engine.
              </div>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>

</body>
</html>"""
