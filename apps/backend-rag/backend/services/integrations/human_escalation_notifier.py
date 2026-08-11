"""The one place that tells a human a WhatsApp conversation needs them.

Extracted from ``backend/app/routers/whatsapp_chat.py`` on 2026-08-11 with its
behaviour unchanged, so that a SECOND caller can reach it.

Why it had to move. `whatsapp_chat.py` is a FastAPI router; the other WhatsApp
surface — the inbox bot behind `wa_outbox_worker` — is a background service.
Today only the router escalates: it captures the persona's ``[ESCALATE]``
marker, strips it, sends the answer and then calls this function.
``wa_inbox_bot.py`` strips the same marker under a comment that says *"mirror
whatsapp_chat.py"* and calls nothing — it mirrored the FORM and not the EFFECT.
One notifier both paths import is the cure for that class; a second copy is how
the two paths drifted apart in the first place.

Measured before moving, so nobody defends this refactor with a breakage that
does not exist: a direct service→router import is **not** circular today
(importing `wa_inbox_bot` then `whatsapp_chat` in one interpreter succeeds).
The reason to extract is layering and drift, not an ImportError.

Two properties deliberately preserved rather than "improved" here, because a
no-behaviour-change extraction is only worth trusting if it changes nothing:

* **The phone is masked, the body is not.** The notification carries
  ``+{phone[:4]}***{phone[-2:]}`` but the client's full message and the last six
  conversation turns in cleartext. That is a live third-party exposure
  (CLAUDE.md §14); any NEW trigger routed here should pass a narrow payload
  rather than widen it, and that choice belongs to the PR that adds the trigger.
* **It fails silently.** The send is wrapped in ``except Exception`` and only
  logs, so a caller cannot tell "a human was told" from "the telling died" —
  for a lane whose whole purpose is the former, that is the disease itself.
  Fixing it changes behaviour and needs its own test; it is not smuggled in
  here.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.app.core.config import settings
from backend.services.integrations.telegram_bot_service import telegram_bot

logger = logging.getLogger(__name__)


async def notify_human_telegram(
    phone: str,
    message_text: str,
    sender_name: str | None = None,
    reason: str = "personal_contact",
    client_profile: dict | None = None,
    conversation_history: list[dict] | None = None,
) -> Any:
    """
    Send Telegram notification to admin with FULL context.

    Args:
        phone: Sender phone number
        message_text: Message content
        sender_name: Optional sender name
        reason: Escalation reason
        client_profile: Client profile dict (interests, language, etc.)
        conversation_history: Recent conversation messages
    """
    if not settings.admin_telegram_chat_id:
        logger.warning("Admin Telegram chat ID not configured, skipping notification")
        return

    reason_emoji = {
        "personal_contact": "👤",
        "explicit_request": "🤚",
        "personal_context": "💬",
        "ai_escalation": "🤖➡️👤",
    }

    emoji = reason_emoji.get(reason, "📩")
    display_name = sender_name or "Unknown"

    # Build profile summary
    profile_lines = []
    if client_profile:
        lang = client_profile.get("detected_language", "?")
        interests = client_profile.get("interests", [])
        visas = client_profile.get("visa_discussed", [])
        client_type = client_profile.get("client_type", "?")
        msg_count = client_profile.get("message_count", 0)
        first_contact = client_profile.get("first_contact", "?")

        profile_lines.append(f"🗣 Lingua: {lang}")
        if interests:
            profile_lines.append(f"💡 Interessi: {', '.join(interests)}")
        if visas:
            profile_lines.append(f"🛂 Visa discussi: {', '.join(visas)}")
        profile_lines.append(f"👤 Tipo: {client_type}")
        profile_lines.append(f"💬 Messaggi: {msg_count}")
        profile_lines.append(f"📅 Primo contatto: {first_contact}")

    profile_section = "\n".join(profile_lines) if profile_lines else "Nessun profilo salvato"

    # Build conversation summary (last 6 messages)
    convo_lines = []
    if conversation_history:
        recent = conversation_history[-6:]
        for msg in recent:
            role = "👤" if msg.get("role") == "user" else "🤖"
            content = msg.get("content", "")[:150]
            convo_lines.append(f"{role} {content}")

    convo_section = "\n".join(convo_lines) if convo_lines else "Nessuna storia"

    notification_text = f"""{emoji} **WhatsApp Escalation**

**Da:** {display_name} (+{phone[:4]}***{phone[-2:] if len(phone) > 4 else ""})
**Motivo:** {reason.replace("_", " ").title()}

**Messaggio:**
{message_text}

**Profilo Cliente:**
{profile_section}

**Ultimi messaggi:**
{convo_section}

---
Rispondi direttamente su WhatsApp!
"""

    try:
        await telegram_bot.send_message(
            chat_id=settings.admin_telegram_chat_id,
            text=notification_text,
            parse_mode="Markdown",
        )
        logger.info("Telegram notification sent for WhatsApp escalation from %s", phone)
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)


