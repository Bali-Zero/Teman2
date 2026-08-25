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

Three things the WA-inbox trigger added on 2026-08-11, each because the lane is
only worth having if the caller can tell what actually happened:

* **It returns whether Telegram ACCEPTED the message.** The send used to be
  wrapped in ``except Exception`` returning ``None``, so a caller could not tell
  "a human was told" from "the telling died". The boolean is named for what it
  proves and no more: **``True`` means Telegram accepted a message**, not that a
  person is on shift, has read it, or owns it. Client-facing copy may say the
  request was flagged; it may never promise a reply on this boolean.
* **The body can be withheld.** ``message_text=None`` sends the masked phone,
  the reason and the thread reference, and says the body was deliberately left
  out — the WA-inbox trigger uses it, because routing a new trigger through the
  cleartext payload would widen exactly the third-party exposure CLAUDE.md §14
  constrains. The router keeps passing the body; that behaviour is unchanged and
  pinned by a test.
* **One notification per thread per window.** Without it a client sending ten
  out-of-domain messages produces ten alerts. In-process TTL map, and it fails
  **open** — a duplicate alert is a nuisance, a suppressed one is the disease.
  Declared limit: the API runs on more than one Fly machine, so the real bound
  is one-per-process-per-window, not exactly one.

Still deliberately unchanged: the phone is masked but the ROUTER's payload still
carries the client's full message and last six turns in cleartext.
"""

from __future__ import annotations

import logging
import time

from backend.app.core.config import settings
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.utils.pii_log_identifier import redact_identifier_for_log

logger = logging.getLogger(__name__)

#: How long a thread stays "already escalated" for dedup purposes.
ESCALATION_DEDUP_WINDOW_S = 30 * 60

#: thread_ref -> monotonic timestamp of the last accepted notification.
#: Bounded by _prune_dedup below so a long-lived process cannot grow it forever.
_recent_escalations: dict[str, float] = {}
_DEDUP_MAX_ENTRIES = 2048


def _prune_dedup(now: float) -> None:
    """Drop entries older than the window; hard-cap the map as a backstop."""
    stale = [k for k, ts in _recent_escalations.items() if now - ts >= ESCALATION_DEDUP_WINDOW_S]
    for k in stale:
        _recent_escalations.pop(k, None)
    if len(_recent_escalations) > _DEDUP_MAX_ENTRIES:
        # Oldest-first eviction. Reaching this means the window is mis-sized or
        # traffic exploded; either way, dropping the oldest is the safe side —
        # it can only cause an EXTRA alert, never a suppressed one.
        for k, _ in sorted(_recent_escalations.items(), key=lambda kv: kv[1])[:512]:
            _recent_escalations.pop(k, None)


def _already_escalated(thread_ref: str | None) -> bool:
    """True if this thread was notified inside the window.

    Fails OPEN on any surprise: an exception here must never be the reason a
    human was not told.
    """
    if not thread_ref:
        return False
    try:
        now = time.monotonic()
        _prune_dedup(now)
        last = _recent_escalations.get(thread_ref)
        return last is not None and (now - last) < ESCALATION_DEDUP_WINDOW_S
    # Broad on purpose: dedup is a convenience, and no failure of it may ever be
    # the reason a human was not told.
    except Exception as exc:
        logger.warning("escalation dedup check failed, notifying anyway: %s", exc)
        return False


async def notify_human_telegram(
    phone: str,
    message_text: str | None,
    sender_name: str | None = None,
    reason: str = "personal_contact",
    client_profile: dict | None = None,
    conversation_history: list[dict] | None = None,
    thread_ref: str | None = None,
) -> bool:
    """
    Tell a human that a WhatsApp conversation needs them.

    Args:
        phone: Sender phone number
        message_text: Message content, or None to withhold the body on purpose
        sender_name: Optional sender name
        reason: Escalation reason
        client_profile: Client profile dict (interests, language, etc.)
        conversation_history: Recent conversation messages
        thread_ref: Meta-inbox thread id — enables per-thread dedup and gives
            the recipient something to open when the body is withheld

    Returns:
        True if Telegram ACCEPTED the message on THIS call. Not evidence that a
        human read it, owns it, or will reply — see the module docstring.
        A dedup-suppressed call returns False even though the thread was
        notified minutes ago: the value answers "did this call send", and a
        caller that phrases client copy from it then says nothing about
        flagging on the follow-up message, which is the safe way to be wrong.
    """
    if not settings.admin_telegram_chat_id:
        logger.warning("Admin Telegram chat ID not configured, skipping notification")
        return False

    if _already_escalated(thread_ref):
        logger.info(
            "escalation for thread %s suppressed: already notified within %ss",
            thread_ref,
            ESCALATION_DEDUP_WINDOW_S,
        )
        return False

    reason_emoji = {
        "personal_contact": "👤",
        "explicit_request": "🤚",
        "personal_context": "💬",
        "ai_escalation": "🤖➡️👤",
        "rag_abstain": "🚫📚",
        "persona_escalate_marker": "🙋",
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

    # The body is withheld, not missing: say so, and give the recipient the one
    # thing that makes the omission workable — which thread to open.
    if message_text is None:
        message_section = (
            "_(testo del cliente non incluso di proposito — apri il thread "
            f"{thread_ref or '?'} nella console WA Meta)_"
        )
    else:
        message_section = message_text

    thread_line = f"\n**Thread:** {thread_ref}" if thread_ref else ""

    notification_text = f"""{emoji} **WhatsApp Escalation**

**Da:** {display_name} (+{phone[:4]}***{phone[-2:] if len(phone) > 4 else ""})
**Motivo:** {reason.replace("_", " ").title()}{thread_line}

**Messaggio:**
{message_section}

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
        logger.info(
            "Telegram notification sent for WhatsApp escalation from %s",
            redact_identifier_for_log(phone),
        )
    except Exception as e:
        logger.error("Failed to send Telegram notification: %s", e)
        return False

    if thread_ref:
        # Recorded only AFTER an accepted send, so a failed attempt does not
        # start a window that suppresses the retry.
        _recent_escalations[thread_ref] = time.monotonic()
    return True
