"""
Practice Kickoff Service — Trigger 2
=====================================
Sends WhatsApp + email immediately after create_practice.

WhatsApp activation gate: _WHATSAPP_PRACTICE_ACTIVE = False
Flip to True after Meta template approval.
Template name: balizero_practice_kickoff (single template, all languages)

Email activation gate: _EMAIL_PRACTICE_ACTIVE = True
Email goes live on deploy.

Guard conditions (skip silently if any fail):
    - client.phone / email is not NULL
    - No existing activity_log with the respective action for this practice
    - Respective _*_ACTIVE flag is True
"""

from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from backend.services.crm.birthday_notifier_service import NATIONALITY_LANGUAGE_MAP
from backend.services.crm.welcome.welcome_templates import (
    ADVISOR_FALLBACK,
    PRACTICE_DOCUMENT_CHECKLISTS,
    PRACTICE_EMAIL_SUBJECT,
    PRACTICE_KICKOFF_WHATSAPP,
    PRACTICE_TIMELINES,
    get_service_name,
)

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ─── ACTIVATION GATES ────────────────────────────────────
_WHATSAPP_PRACTICE_ACTIVE: bool = False  # pending Meta template approval
_EMAIL_PRACTICE_ACTIVE: bool = True  # goes live on deploy

ACTIVITY_ACTION_WA = "practice_kickoff_whatsapp_sent"
ACTIVITY_ACTION_EMAIL = "practice_kickoff_email_sent"

# ─── EMAIL API (Brevo via internal endpoint) ─────────────
_EMAIL_API_URL = os.getenv(
    "INTERNAL_EMAIL_API_URL",
    "https://nuzantara-rag.fly.dev/api/notifications/send-email",
)
_EMAIL_API_KEY = os.getenv("NUZANTARA_API_KEY", "zantara-secret-2024")

# ─── BROCHURE PATH ───────────────────────────────────────
_BROCHURE_PATH = (
    Path(__file__).parent.parent.parent.parent.parent
    / "data"
    / "assets"
    / "brochure_balizero_en.pdf"
)


# ─────────────────────────────────────────────────────────
# PUBLIC ENTRY POINT
# ─────────────────────────────────────────────────────────


async def send_practice_kickoff(
    practice_id: int,
    client_id: int,
    practice_type_code: str,
    db_pool: asyncpg.Pool,
) -> None:
    """
    Send WhatsApp + email kickoff for a newly created practice.
    Non-blocking — called via BackgroundTasks. Never raises.
    """
    try:
        await _send_practice_kickoff_impl(practice_id, client_id, practice_type_code, db_pool)
    except Exception:
        logger.error(
            "PracticeKickoff: unhandled error for practice %d (client %d)",
            practice_id,
            client_id,
            exc_info=True,
        )


# ─────────────────────────────────────────────────────────
# IMPLEMENTATION
# ─────────────────────────────────────────────────────────


async def _send_practice_kickoff_impl(
    practice_id: int,
    client_id: int,
    practice_type_code: str,
    db_pool: asyncpg.Pool,
) -> None:
    async with db_pool.acquire() as conn:
        client = await conn.fetchrow(
            "SELECT id, full_name, email, phone, nationality, assigned_to FROM clients WHERE id = $1",
            client_id,
        )
        if not client:
            logger.warning("PracticeKickoff: client %d not found", client_id)
            return

    # Shared variable resolution
    nationality = client["nationality"] or ""
    lang = NATIONALITY_LANGUAGE_MAP.get(nationality, "en")
    first_name = (client["full_name"] or "").split()[0] if client["full_name"] else ""
    assigned_to = client["assigned_to"] or ""
    advisor_name = (
        assigned_to.split("@")[0].capitalize()
        if assigned_to
        else ADVISOR_FALLBACK.get(lang, "our team")
    )
    service_name = get_service_name(practice_type_code, lang)

    # Run both channels (each checks its own gate + idempotency)
    await _send_whatsapp(
        practice_id=practice_id,
        client_id=client_id,
        client=client,
        lang=lang,
        first_name=first_name,
        advisor_name=advisor_name,
        service_name=service_name,
        db_pool=db_pool,
    )
    await _send_email(
        practice_id=practice_id,
        client_id=client_id,
        client=client,
        lang=lang,
        first_name=first_name,
        advisor_name=advisor_name,
        advisor_email=assigned_to,
        practice_type_code=practice_type_code,
        service_name=service_name,
        db_pool=db_pool,
    )


# ─────────────────────────────────────────────────────────
# WHATSAPP
# ─────────────────────────────────────────────────────────


async def _send_whatsapp(
    practice_id: int,
    client_id: int,
    client: asyncpg.Record,
    lang: str,
    first_name: str,
    advisor_name: str,
    service_name: str,
    db_pool: asyncpg.Pool,
) -> None:
    if not _WHATSAPP_PRACTICE_ACTIVE:
        logger.debug("PracticeKickoff WA: inactive, skipping practice %d", practice_id)
        return

    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
    if not phone_number_id or not access_token:
        logger.warning("PracticeKickoff WA: WHATSAPP_PHONE_NUMBER_ID or ACCESS_TOKEN not set")
        return

    phone = (client["phone"] or "").strip()
    if not phone:
        logger.info("PracticeKickoff WA: client %d has no phone, skipping", client_id)
        return

    async with db_pool.acquire() as conn:
        already_sent = await conn.fetchval(
            "SELECT id FROM activity_log WHERE client_id = $1 AND action = $2 AND details LIKE $3 LIMIT 1",
            client_id,
            ACTIVITY_ACTION_WA,
            f"%practice_id={practice_id}%",
        )
    if already_sent:
        logger.info("PracticeKickoff WA: already sent for practice %d, skipping", practice_id)
        return

    message_text = PRACTICE_KICKOFF_WHATSAPP.format(
        first_name=first_name,
        service_name=service_name,
        practice_id=practice_id,
        advisor_name=advisor_name,
    )
    clean_phone = phone.lstrip("+")

    url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": clean_phone,
        "type": "text",
        "text": {"body": message_text},
    }

    async with httpx.AsyncClient(timeout=30.0) as http:
        resp = await http.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if resp.status_code == 200:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (client_id, action, details, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT DO NOTHING
                """,
                client_id,
                ACTIVITY_ACTION_WA,
                f"lang={lang} phone={clean_phone} practice_id={practice_id}",
            )
        logger.info(
            "PracticeKickoff WA: sent to client %d practice %d (lang=%s)",
            client_id,
            practice_id,
            lang,
        )
    else:
        logger.error(
            "PracticeKickoff WA: Meta API error for practice %d: %d %s",
            practice_id,
            resp.status_code,
            resp.text[:200],
        )


# ─────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────


async def _send_email(
    practice_id: int,
    client_id: int,
    client: asyncpg.Record,
    lang: str,
    first_name: str,
    advisor_name: str,
    advisor_email: str,
    practice_type_code: str,
    service_name: str,
    db_pool: asyncpg.Pool,
) -> None:
    if not _EMAIL_PRACTICE_ACTIVE:
        logger.debug("PracticeKickoff Email: inactive, skipping practice %d", practice_id)
        return

    email = (client["email"] or "").strip()
    if not email:
        logger.info("PracticeKickoff Email: client %d has no email, skipping", client_id)
        return

    async with db_pool.acquire() as conn:
        already_sent = await conn.fetchval(
            "SELECT id FROM activity_log WHERE client_id = $1 AND action = $2 AND details LIKE $3 LIMIT 1",
            client_id,
            ACTIVITY_ACTION_EMAIL,
            f"%practice_id={practice_id}%",
        )
    if already_sent:
        logger.info("PracticeKickoff Email: already sent for practice %d, skipping", practice_id)
        return

    subject_tmpl = PRACTICE_EMAIL_SUBJECT[lang]
    subject = subject_tmpl.format(service_name=service_name)
    html_body = _build_html(
        lang=lang,
        first_name=first_name,
        advisor_name=advisor_name,
        advisor_email=advisor_email,
        practice_id=practice_id,
        practice_type_code=practice_type_code,
        service_name=service_name,
    )

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
            logger.warning(
                "PracticeKickoff Email: could not read brochure for practice %d",
                practice_id,
                exc_info=True,
            )

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
                client_id,
                ACTIVITY_ACTION_EMAIL,
                f"lang={lang} email={email} practice_id={practice_id}",
            )
        logger.info(
            "PracticeKickoff Email: sent to client %d practice %d (lang=%s)",
            client_id,
            practice_id,
            lang,
        )
    else:
        logger.error(
            "PracticeKickoff Email: send failed for practice %d: %d %s",
            practice_id,
            resp.status_code,
            resp.text[:200],
        )


# ─────────────────────────────────────────────────────────
# HTML BUILDER
# ─────────────────────────────────────────────────────────


def _build_html(
    lang: str,
    first_name: str,
    advisor_name: str,
    advisor_email: str,
    practice_id: int,
    practice_type_code: str,
    service_name: str,
) -> str:
    """Build the practice kickoff HTML email."""
    checklist = PRACTICE_DOCUMENT_CHECKLISTS.get(practice_type_code.upper(), [])
    timeline = PRACTICE_TIMELINES.get(practice_type_code.upper(), "")

    checklist_html = "\n".join(
        f'<li style="padding:6px 0;color:#edeae4;font-size:13px;">{item}</li>' for item in checklist
    )

    timeline_block = ""
    if timeline:
        timeline_block = f"""
  <div style="background:#1c1c22;border-radius:6px;padding:16px 20px;margin-top:16px;">
    <div style="font-size:11px;font-weight:700;color:#c9a96e;letter-spacing:1.5px;margin-bottom:6px;">TYPICAL TIMELINE</div>
    <div style="font-size:13px;color:#edeae4;">{timeline}</div>
  </div>"""

    # Greeting lines per language
    greetings = {
        "en": f"Hi {first_name},",
        "it": f"Ciao {first_name},",
        "ru": f"Здравствуйте, {first_name},",
        "uk": f"Вітаємо, {first_name},",
        "id": f"Halo {first_name},",
    }
    greeting = greetings.get(lang, f"Hi {first_name},")

    # Opening body per language
    openings = {
        "en": (
            f"Your <strong>{service_name}</strong> case is now open (Case ID: #{practice_id}). "
            f"{advisor_name} is your dedicated case handler and will be in touch today."
        ),
        "it": (
            f"La tua pratica <strong>{service_name}</strong> è ora aperta (ID: #{practice_id}). "
            f"{advisor_name} è il responsabile del tuo caso e ti contatterà oggi."
        ),
        "ru": (
            f"Ваше дело <strong>{service_name}</strong> открыто (ID: #{practice_id}). "
            f"{advisor_name} — ваш персональный ведущий и свяжется с вами сегодня."
        ),
        "uk": (
            f"Ваша справа <strong>{service_name}</strong> відкрита (ID: #{practice_id}). "
            f"{advisor_name} — ваш особистий відповідальний і зв'яжеться з вами сьогодні."
        ),
        "id": (
            f"Kasus <strong>{service_name}</strong> Anda telah dibuka (ID: #{practice_id}). "
            f"{advisor_name} adalah penanganan kasus Anda dan akan menghubungi Anda hari ini."
        ),
    }
    opening_body = openings.get(lang, openings["en"])

    # Section headers per language
    checklist_headers = {
        "en": "DOCUMENTS NEEDED",
        "it": "DOCUMENTI NECESSARI",
        "ru": "НЕОБХОДИМЫЕ ДОКУМЕНТЫ",
        "uk": "НЕОБХІДНІ ДОКУМЕНТИ",
        "id": "DOKUMEN YANG DIPERLUKAN",
    }
    checklist_header = checklist_headers.get(lang, "DOCUMENTS NEEDED")

    # CTA per language
    ctas = {
        "en": "Reply to this email — we'll take it from here.",
        "it": "Rispondi a questa email — pensiamo a tutto noi.",
        "ru": "Ответьте на это письмо — мы позаботимся обо всём.",
        "uk": "Відповідайте на цей лист — ми подбаємо про все.",
        "id": "Balas email ini — kami akan mengurus semuanya.",
    }
    cta = ctas.get(lang, ctas["en"])

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

  <!-- GREETING + CASE OPEN -->
  <div style="background:#111115;padding:28px 32px;">
    <div style="font-size:15px;font-weight:700;color:#edeae4;margin-bottom:10px;">{greeting}</div>
    <div style="font-size:13.5px;line-height:1.75;color:#edeae4;">{opening_body}</div>
  </div>

  <!-- CASE BADGE -->
  <div style="background:#0c0c0e;padding:20px 32px;">
    <div style="display:inline-block;background:#1c1c22;border:1px solid #d4845a;border-radius:6px;padding:12px 20px;">
      <span style="font-size:11px;color:#c9a96e;text-transform:uppercase;letter-spacing:1.5px;">Case</span>
      <span style="font-size:18px;font-weight:700;color:#d4845a;margin-left:10px;">#{practice_id}</span>
      <span style="font-size:12px;color:#9e9b95;margin-left:10px;">·</span>
      <span style="font-size:12px;color:#edeae4;margin-left:10px;">{service_name}</span>
    </div>
  </div>

  <!-- DOCUMENT CHECKLIST -->
  <div style="background:#111115;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:12px;">{checklist_header}</div>
    <div style="width:40px;height:2px;background:#d4845a;margin-bottom:16px;"></div>
    <ul style="margin:0;padding-left:20px;list-style:disc;">
      {checklist_html}
    </ul>
    {timeline_block}
  </div>

  <!-- NEXT STEP -->
  <div style="background:#0c0c0e;padding:28px 32px;">
    <div style="font-size:11px;font-weight:700;color:#d4845a;letter-spacing:2px;margin-bottom:12px;">NEXT STEP</div>
    <div style="font-size:13.5px;color:#edeae4;line-height:1.7;">
      Send us your documents and we'll begin immediately.
      {f'<br><br><span style="color:#c9a96e;">Your advisor: <strong>{advisor_name}</strong></span>' if advisor_email else ""}
    </div>
  </div>

  <!-- CTA -->
  <div style="background:#d4845a;padding:24px 32px;text-align:center;">
    <div style="font-size:15px;font-weight:700;color:#0c0c0e;">{cta}</div>
  </div>

  <!-- FOOTER -->
  <div style="background:#0c0c0e;padding:20px 32px;border-top:1px solid #2a2a30;">
    <div style="font-size:11px;color:#9e9b95;text-align:center;line-height:1.8;">
      zantara@balizero.com &nbsp;·&nbsp;
      wa.me/6281338051876 &nbsp;·&nbsp;
      <a href="https://www.balizero.com" style="color:#c9a96e;text-decoration:none;">www.balizero.com</a>
      &nbsp;·&nbsp; Canggu, Bali
    </div>
    <div style="font-size:10px;color:#3a3a40;text-align:center;margin-top:8px;">
      Case #{practice_id} · You received this because you are a Bali Zero client.
    </div>
  </div>

</div>
</body>
</html>"""
