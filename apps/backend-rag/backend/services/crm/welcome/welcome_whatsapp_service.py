"""
Welcome WhatsApp Service — Trigger 1a
======================================
Sends a WhatsApp welcome message immediately after create_client.

Activation gate: _WHATSAPP_WELCOME_ACTIVE = False
Flip to True ONLY after Meta template approval in Business Manager.
Template names: balizero_welcome_en/it/ru/uk/id

Guard conditions (skip silently if any fail):
    - client.phone is not NULL and not empty
    - No existing activity_log with action=welcome_whatsapp_sent for this client
    - WHATSAPP_PHONE_NUMBER_ID is configured
    - _WHATSAPP_WELCOME_ACTIVE is True
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import httpx

from backend.services.crm.birthday_notifier_service import NATIONALITY_LANGUAGE_MAP
from backend.services.crm.welcome.welcome_templates import (
    ADVISOR_FALLBACK,
    WELCOME_WHATSAPP,
)

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# ─── ACTIVATION GATE ─────────────────────────────────────
# Keep False until Meta Business Manager approves all 5 templates.
_WHATSAPP_WELCOME_ACTIVE: bool = False

ACTIVITY_ACTION = "welcome_whatsapp_sent"


async def send_client_welcome(client_id: int, db_pool: asyncpg.Pool) -> None:
    """
    Send welcome WhatsApp to a newly created client.
    Non-blocking — called via BackgroundTasks. Never raises.
    """
    if not _WHATSAPP_WELCOME_ACTIVE:
        logger.debug(
            "WelcomeWhatsApp: inactive (template approval pending), skipping client %d", client_id,
        )
        return

    try:
        await _send_client_welcome_impl(client_id, db_pool)
    except Exception:
        logger.error("WelcomeWhatsApp: unhandled error for client %d", client_id, exc_info=True)


async def _send_client_welcome_impl(client_id: int, db_pool: asyncpg.Pool) -> None:
    phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
    access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")

    if not phone_number_id or not access_token:
        logger.warning(
            "WelcomeWhatsApp: WHATSAPP_PHONE_NUMBER_ID or ACCESS_TOKEN not set, skipping",
        )
        return

    async with db_pool.acquire() as conn:
        # Load client
        client = await conn.fetchrow(
            "SELECT id, full_name, phone, nationality, assigned_to FROM clients WHERE id = $1",
            client_id,
        )
        if not client:
            logger.warning("WelcomeWhatsApp: client %d not found", client_id)
            return

        phone = (client["phone"] or "").strip()
        if not phone:
            logger.info("WelcomeWhatsApp: client %d has no phone, skipping", client_id)
            return

        # Idempotency check
        already_sent = await conn.fetchval(
            "SELECT id FROM activity_log WHERE client_id = $1 AND action = $2 LIMIT 1",
            client_id,
            ACTIVITY_ACTION,
        )
        if already_sent:
            logger.info("WelcomeWhatsApp: already sent for client %d, skipping", client_id)
            return

    # Language resolution
    nationality = client["nationality"] or ""
    lang = NATIONALITY_LANGUAGE_MAP.get(nationality, "en")

    # Variable resolution
    first_name = (client["full_name"] or "").split()[0] if client["full_name"] else ""
    assigned_to = client["assigned_to"] or ""
    if assigned_to:
        # Use first name of email (e.g. "damar@balizero.com" → "Damar")
        advisor_name = assigned_to.split("@")[0].capitalize()
    else:
        advisor_name = ADVISOR_FALLBACK.get(lang, "our team")

    template_body = WELCOME_WHATSAPP[lang]
    message_text = template_body.format(first_name=first_name, advisor_name=advisor_name)

    # Phone format: strip +
    clean_phone = phone.lstrip("+")

    # Send via Meta Cloud API
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
        # Log activity for idempotency
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO activity_log (client_id, action, details, created_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT DO NOTHING
                """,
                client_id,
                ACTIVITY_ACTION,
                f"lang={lang} phone={clean_phone}",
            )
        logger.info("WelcomeWhatsApp: sent to client %d (lang=%s)", client_id, lang)
    else:
        logger.error(
            "WelcomeWhatsApp: Meta API error for client %d: %d %s",
            client_id,
            resp.status_code,
            resp.text[:200],
        )
