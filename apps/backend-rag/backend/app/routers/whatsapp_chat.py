"""
WhatsApp Chat Router
Handles incoming WhatsApp messages with intelligent triage (personal vs business).

Architecture:
- Webhook receives messages from Meta WhatsApp Cloud API
- Triage service decides: personal → human, business → AI RAG
- AI responses use Claude Sonnet 4.5 with dynamic persona + client memory
- Notifications sent to admin via Telegram for personal messages

v2: Upgraded brain — Sonnet 4.5, dynamic persona "Zan", client profile memory,
    context builder, proactive suggestions, human escalation with full context.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import re
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.channels.format import format_rich_text

# `notify_human_telegram` now lives in
# `backend/services/integrations/human_escalation_notifier.py` so the WhatsApp
# INBOX BOT (a background service) can reach the same notifier instead of
# growing a second copy — the two paths already drifted once, which is how
# `wa_inbox_bot.py` ended up stripping `[ESCALATE]` and telling nobody.
#
# Re-exported here under its original name, so the two call sites below and any
# `patch("backend.app.routers.whatsapp_chat.notify_human_telegram")` still work.
# What does NOT survive the move — measured, an earlier version of this comment
# claimed otherwise and the suite disproved it: the function now reads
# `settings` and `telegram_bot` from ITS OWN module, so patching THIS module's
# globals no longer reaches its dependencies. Patch
# `...human_escalation_notifier.settings` instead.
from backend.services.integrations.human_escalation_notifier import (
    notify_human_telegram,
)
from backend.services.integrations.openclaw_whatsapp_bridge import ask_openclaw_whatsapp
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.integrations.wa_outbox_worker import (
    META_INBOX_PHONE_NUMBER_IDS,
    _manners_enabled,
)
from backend.services.integrations.whatsapp_service import whatsapp_service
from backend.services.integrations.whatsapp_triage_service import (
    TriageDecision,
    whatsapp_triage_service,
)
from backend.services.whatsapp_kbli_guard import sanitize_whatsapp_kbli_reply
from backend.services.whatsapp_onboarding_detector import get_onboarding_detector

logger = logging.getLogger(__name__)

# NB: media downloads do NOT happen on Fly (Law 2 — PII stays on the Pro). The
# official-line media handoff publishes metadata only to events_outbox; the
# sovereign Pro worker (scripts/wa_media_pull_worker.py) owns the blob root.

# In-memory conversation history per phone number (fast fallback)
_conversation_cache: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_MESSAGES = 20

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])
WHATSAPP_FAST_PATH_RECOVERY_DELAY_SECONDS = 30

# Claimant names for the wa_reply_claims race gate (2026-08-25 double-reply
# scar, migration 281). One row per Meta wamid, written BEFORE either path
# generates or sends a reply — whichever path's INSERT lands first wins.
WAMID_CLAIMANT_META_INBOX = "meta_inbox"
WAMID_CLAIMANT_LEGACY = "legacy"


async def _claim_wamid_reply(conn: Any, wamid: str, claimant: str) -> bool:
    """Atomically claim ``wamid`` for ``claimant``; True iff this claimant owns it.

    ``ON CONFLICT (wamid) DO UPDATE SET wamid = EXCLUDED.wamid`` is a no-op
    write on the conflicting row's own primary key — deliberate, not
    decorative. ``DO NOTHING`` would return no row at all on conflict, which
    cannot distinguish "the OTHER path already claimed this wamid" from "I
    already claimed it, this is a legitimate retry of my own path" — the two
    need different handling (retry-safely proceed in the second case, never
    in the first). ``DO UPDATE`` always returns a row via ``RETURNING``, and
    because the update never touches ``claimed_by``, the value it returns on
    a conflict is the FIRST claimant's — untouched. So the caller compares
    the returned owner against its own claimant name: equal means either
    "I just won the claim" or "I already own it" (both safe to proceed —
    each path's own downstream inserts are independently idempotent);
    different means the other path already claimed it — log and discard.
    """
    owner = await conn.fetchval(
        """
        INSERT INTO wa_reply_claims (wamid, claimed_by)
        VALUES ($1, $2)
        ON CONFLICT (wamid) DO UPDATE SET wamid = EXCLUDED.wamid
        RETURNING claimed_by
        """,
        wamid,
        claimant,
    )
    return owner == claimant


class WhatsAppMessage(BaseModel):
    """WhatsApp message structure."""

    from_: str = Field(..., alias="from")  # Sender phone
    id: str  # Message ID
    timestamp: str
    type: str  # text, image, audio, etc.
    text: dict[str, Any] | None = None

    model_config = ConfigDict(populate_by_name=True)


class WhatsAppChange(BaseModel):
    """WhatsApp webhook change event."""

    field: str
    value: dict[str, Any]


class WhatsAppEntry(BaseModel):
    """WhatsApp webhook entry."""

    id: str
    changes: list[WhatsAppChange]


class WhatsAppWebhook(BaseModel):
    """WhatsApp webhook payload from Meta."""

    object: str  # Should be "whatsapp_business_account"
    entry: list[WhatsAppEntry]


async def notify_zero_conversation_log(
    phone: str,
    sender_name: str | None,
    client_message: str,
    bot_response: str,
    language: str | None = None,
) -> Any:
    """
    Log EVERY bot conversation to Zero via Telegram.

    Args:
        phone: Client phone
        sender_name: Client name
        client_message: What the client asked
        bot_response: What Zan replied
        language: Detected language
    """
    if not settings.admin_telegram_chat_id:
        return

    display_name = sender_name or "Unknown"
    lang_flag = {"it": "🇮🇹", "en": "🇬🇧", "de": "🇩🇪", "id": "🇮🇩"}.get(language or "?", "🌐")

    # Keep it short for Zero
    client_msg_preview = client_message[:200] + ("..." if len(client_message) > 200 else "")
    bot_response_preview = bot_response[:300] + ("..." if len(bot_response) > 300 else "")

    log_text = f"""💬 **WhatsApp Bot Conversation Log**

**Cliente:** {display_name} (+{phone[:4]}***{phone[-2:] if len(phone) > 4 else ""}) {lang_flag}

**Domanda:**
_{client_msg_preview}_

**Risposta Zan:**
_{bot_response_preview}_

---
_Log automatico - ogni conversazione viene tracciata_
"""

    try:
        await telegram_bot.send_message(
            chat_id=settings.admin_telegram_chat_id,
            text=log_text,
            parse_mode="Markdown",
            disable_notification=True,  # Silent notification
        )
    except Exception as e:
        logger.error("Failed to send conversation log to Zero: %s", e)


async def process_whatsapp_message(
    phone: str,
    message_text: str,
    sender_name: str | None,
    message_id: str,
    request: Request,
) -> Any:
    """
    Background task to process WhatsApp message.

    v2 Flow:
    1. Triage (personal vs business)
    2. Build rich context (history, profile, language)
    3. Generate dynamic system prompt
    4. Call Claude Sonnet 4.5
    5. Handle [ESCALATE] markers
    6. Save conversation + updated profile
    """
    try:
        # Mark message as read
        await whatsapp_service.mark_message_read(message_id)

        # 0. CROSS-PATH ATOMIC CLAIM (2026-08-25 double-reply scar, hardened).
        # The meta-inbox pipeline (wa_outbox_worker / _handle_meta_inbox_message)
        # and this legacy inline path are two concurrent BackgroundTasks. The
        # first fix here was a read-only SELECT against meta_inbox_messages —
        # best-effort, but racy: it can run BEFORE the meta-inbox path's own
        # write commits, so both paths can win the read and both reply (live
        # 04:03-04:04Z 2026-08-25: an English abstain from one path, an
        # Italian greeting from the other, same inbound message). Replaced
        # with a write-before-send atomic claim on the SAME wamid — whichever
        # path's INSERT lands first in wa_reply_claims wins and answers; the
        # loser logs and discards. Best-effort ONLY for the "DB unreachable"
        # case (a DB hiccup must never mute a genuinely legacy message) — once
        # the DB responds, the claim outcome is binding.
        dedup_db_pool = _get_db_pool(request)
        if dedup_db_pool is not None:
            try:
                async with dedup_db_pool.acquire() as dedup_conn:
                    won_claim = await _claim_wamid_reply(
                        dedup_conn, message_id, WAMID_CLAIMANT_LEGACY
                    )
                if not won_claim:
                    logger.info(
                        "Legacy WhatsApp path skipped — wamid=%s already claimed "
                        "by the meta-inbox pipeline",
                        message_id,
                    )
                    return
            except Exception:
                logger.exception(
                    "Cross-path claim failed (non-blocking) wamid=%s", message_id
                )

        # 0.5. ALLOWLIST CHECK: Silently ignore numbers not in whitelist
        if not whatsapp_triage_service.is_allowed(phone):
            logger.info("Ignored message from non-allowed number: %s", phone)
            return

        # 1. TRIAGE: Personal or Business?
        decision, reason = await whatsapp_triage_service.should_escalate(
            phone=phone,
            message_text=message_text,
            sender_name=sender_name,
        )

        logger.info("Triage decision for %s: %s (reason: %s)", phone, decision, reason)

        # 1.5. AUTO-DETECT NEW CLIENT ONBOARDING INTENT
        # Check if message indicates new client onboarding before processing
        try:
            onboarding_detector = get_onboarding_detector()
            onboarding_result = await onboarding_detector.detect_and_trigger(
                phone=phone,
                message_text=message_text,
                sender_name=sender_name,
            )
            if onboarding_result:
                logger.info(
                    "🎯 Auto-triggered onboarding chain for %s: %s", phone, onboarding_result
                )
                # Send confirmation message to client
                onboarding_confirm_msg = (
                    "Great! I've started your onboarding process. "
                    "You'll receive updates shortly! 🎉"
                )
                await whatsapp_service.send_message(
                    phone=phone,
                    text=onboarding_confirm_msg,
                    reply_to_message_id=message_id,
                )
                await _persist_audit_messages(
                    db_pool=_get_db_pool(request),
                    phone=phone,
                    session_id="",
                    message_text=message_text,
                    response_text=onboarding_confirm_msg,
                )
                # Notify admin via Telegram
                if settings.admin_telegram_chat_id:
                    await telegram_bot.send_message(
                        chat_id=settings.admin_telegram_chat_id,
                        text=f"🚀 **Auto-Onboarding Triggered**\n\nPhone: +{phone}\nName: {sender_name or 'Unknown'}\nChain: {onboarding_result.get('chain')}\nStatus: {onboarding_result.get('status')}",
                        parse_mode="Markdown",
                    )
                return
        except Exception as e:
            logger.error("Onboarding detection failed for %s: %s", phone, e, exc_info=True)
            # Continue with normal flow if detection fails

        # 2. ESCALATE TO HUMAN
        if decision in [
            TriageDecision.ESCALATE_PERSONAL,
            TriageDecision.ESCALATE_REQUEST,
            TriageDecision.ESCALATE_CONTEXT,
        ]:
            escalation_msg = whatsapp_triage_service.get_escalation_message(decision, sender_name)
            await whatsapp_service.send_message(
                phone=phone,
                text=escalation_msg,
                reply_to_message_id=message_id,
            )

            # Get context for richer Telegram notification
            db_pool = _get_db_pool(request)
            ctx = {}
            if db_pool:
                from backend.services.whatsapp_context_builder import build_context

                try:
                    ctx = await build_context(phone, sender_name, message_text, db_pool)
                except Exception as e:
                    logger.error("Error building context for WhatsApp: %s", e, exc_info=True)
                    ctx = None

            await notify_human_telegram(
                phone=phone,
                message_text=message_text,
                sender_name=sender_name,
                reason=reason,
                client_profile=ctx.get("client_profile"),
                conversation_history=ctx.get("conversation_history"),
            )

            await _persist_audit_messages(
                db_pool=db_pool,
                phone=phone,
                session_id="",
                message_text=message_text,
                response_text=escalation_msg,
            )
            logger.info("Message from %s escalated to human (reason: %s)", phone, reason)
            return

        # 3. OFFER CHOICE (ambiguous)
        if decision == TriageDecision.OFFER_CHOICE:
            welcome_msg = whatsapp_triage_service.get_welcome_message(sender_name)
            await whatsapp_service.send_message(
                phone=phone,
                text=welcome_msg,
                reply_to_message_id=message_id,
            )
            await _persist_audit_messages(
                db_pool=_get_db_pool(request),
                phone=phone,
                session_id="",
                message_text=message_text,
                response_text=welcome_msg,
            )
            logger.info("Welcome message sent to %s", phone)
            return

        # 4. AI CAN HANDLE — OpenClaw bridge first, then Gemini RAG fallback.
        from backend.services.whatsapp_context_builder import build_context

        db_pool = _get_db_pool(request)

        start_time = time.time()

        try:
            # Build rich context
            ctx = await build_context(phone, sender_name, message_text, db_pool)

            # Concierge ack: the AI path takes 10-50s wall-clock; on a
            # non-trivial question tell the user we're on it BEFORE the slow
            # call. Throttled per phone, kill-switch WHATSAPP_ACK_ENABLED.
            # Never let the ack break the main path.
            try:
                from backend.services.whatsapp_ack import (
                    ack_text,
                    mark_acked,
                    should_send_ack,
                )

                if should_send_ack(message_text, phone):
                    await whatsapp_service.send_message(
                        phone=phone,
                        text=ack_text(ctx.get("detected_language")),
                        reply_to_message_id=message_id,
                    )
                    mark_acked(phone)
                    logger.info("Concierge ack sent to %s", phone)
            except Exception:
                logger.exception("Concierge ack failed (non-blocking) phone=%s", phone)

            openclaw_response = await ask_openclaw_whatsapp(
                phone=phone,
                message_text=message_text,
                sender_name=sender_name,
                message_id=message_id,
                context={
                    "client_name": ctx.get("client_name"),
                    "client_profile": ctx.get("client_profile"),
                    "conversation_history": ctx.get("conversation_history"),
                    "detected_language": ctx.get("detected_language"),
                    "is_first_message": ctx.get("is_first_message"),
                    "sender_identity": ctx.get("sender_identity"),
                    "time_of_day": ctx.get("time_of_day"),
                },
            )

            if openclaw_response:
                guarded_openclaw_response = sanitize_whatsapp_kbli_reply(
                    message_text=message_text,
                    reply=openclaw_response,
                    detected_language=ctx.get("detected_language"),
                )
                if guarded_openclaw_response.corrected:
                    logger.warning(
                        "WhatsApp KBLI guard corrected OpenClaw reply "
                        "(phone=%s message_id=%s reason=%s)",
                        phone,
                        message_id,
                        guarded_openclaw_response.reason,
                    )
                openclaw_response = guarded_openclaw_response.reply

                # Channel boundary. `format_rich_text` converts the model's
                # generic markdown into what WhatsApp actually renders and
                # drops bare citation markers — measured on 2026-07-28, the
                # team beta: 18 of that day's 66 bot replies reached a reader
                # carrying raw `[1]`…`[8]`. The formatter was armed on
                # 2026-07-25 (#3118) and deployed well before that day, but
                # only inside `wa_inbox_bot.py`; this router — which is what
                # answers the webhook — never called it.
                #
                # BEFORE chunking, not per chunk: `chunk_message` splits on
                # length, so a boundary can land inside a `**bold**` pair and
                # leave each half unconvertible.
                #
                # AFTER `sanitize_whatsapp_kbli_reply`, so the KBLI guard keeps
                # seeing exactly the text it sees today.
                #
                # Only the model's answer is formatted, never the canned
                # messages this router also sends (`welcome_msg`,
                # `escalation_msg`, `ack_text(...)`, ...). Those are a
                # different entity: the citation strip removes `[<digits>]`,
                # which in a template can be a reference or invoice number
                # rather than a citation.
                openclaw_response = format_rich_text(openclaw_response, "whatsapp")

                chunks = whatsapp_service.chunk_message(openclaw_response, max_length=4000)

                for i, chunk in enumerate(chunks):
                    await whatsapp_service.send_message(
                        phone=phone,
                        text=chunk,
                        reply_to_message_id=message_id if i == 0 else None,
                    )
                    if i < len(chunks) - 1:
                        await asyncio.sleep(0.5)

                await notify_zero_conversation_log(
                    phone=phone,
                    sender_name=sender_name,
                    client_message=message_text,
                    bot_response=openclaw_response,
                    language=ctx.get("detected_language"),
                )

                await _save_conversation(
                    db_pool=db_pool,
                    wa_user_id=ctx["_wa_user_id"],
                    session_id=ctx["_session_id"],
                    existing_row_id=ctx["_existing_row_id"],
                    message_text=message_text,
                    response_text=openclaw_response,
                    client_profile=ctx["client_profile"],
                    sender_name=sender_name,
                    phone=phone,
                )

                _conversation_cache[phone].append({"role": "user", "content": message_text})
                _conversation_cache[phone].append(
                    {"role": "assistant", "content": openclaw_response}
                )
                if len(_conversation_cache[phone]) > MAX_HISTORY_MESSAGES:
                    _conversation_cache[phone] = _conversation_cache[phone][-MAX_HISTORY_MESSAGES:]

                total_duration = time.time() - start_time
                logger.info(
                    "✅ OpenClaw WA responded to %s in %.1fs (%d chars)",
                    phone,
                    total_duration,
                    len(openclaw_response),
                )
                return

            logger.info(
                "🚀 Processing query from %s with Gemini 3 Flash (RAG + Zan persona)",
                phone,
            )

            from backend.prompts.whatsapp_persona import (
                build_priming_turns,
                build_system_prompt,
            )

            # Build dynamic WhatsApp persona instructions
            whatsapp_persona_instructions = build_system_prompt(
                client_name=ctx["client_name"],
                client_profile=ctx["client_profile"],
                is_first_message=ctx["is_first_message"],
                detected_language=ctx["detected_language"],
                time_of_day=ctx["time_of_day"],
            )

            # --- DIRECT RAG: Query with Gemini 2.5 Flash ---
            from backend.app.dependencies import get_orchestrator

            # `get_orchestrator` is `async def` (backend/app/deps/orchestrator.py)
            # — it lazily builds the singleton under a lock. Without the await
            # this binds a coroutine and the next line dies on
            # `'coroutine' object has no attribute 'process_query'`.
            orchestrator = await get_orchestrator(request)
            wa_user_id = f"whatsapp_{phone}"
            session_id = f"wa_session_{phone}"

            # Inject WhatsApp persona at start of conversation history (system-like context)
            # This guides Zantara's base persona to be more WhatsApp-natural
            enhanced_history = []
            if ctx["is_first_message"]:
                # Add persona instructions as first "context" message.
                # The pair is built in the CLIENT'S language: both halves used
                # to be hardcoded Italian, including the assistant turn, so the
                # model's most recent precedent for how it speaks here was
                # Italian before the client had said a word — while the persona
                # itself is written four times over precisely so that never
                # happens. See build_priming_turns' docstring.
                enhanced_history.extend(
                    build_priming_turns(
                        whatsapp_persona_instructions,
                        ctx["detected_language"],
                    ),
                )

            enhanced_history.extend(ctx["conversation_history"])

            # Direct RAG query (Gemini will respond with Zantara + WhatsApp persona blend)
            # max_steps=2 (default 3): real-time channel, see
            # research/operations/2026-07-20-wa-bot-latency.md.
            rag_result = await orchestrator.process_query(
                query=message_text,
                user_id=wa_user_id,
                session_id=session_id,
                conversation_history=enhanced_history,
                max_steps=2,
            )

            # Extract response from RAG
            if rag_result and hasattr(rag_result, "answer") and rag_result.answer:
                response_text = rag_result.answer.strip()
            else:
                response_text = "Scusa, qualcosa è andato storto 😅 Riprova!"

            if not response_text:
                response_text = "Scusa, qualcosa è andato storto 😅 Riprova!"

            # Check for [ESCALATE] marker
            needs_escalation = "[ESCALATE]" in response_text
            if needs_escalation:
                # Remove the marker before sending to client
                response_text = response_text.replace("[ESCALATE]", "").strip()

            guarded_response = sanitize_whatsapp_kbli_reply(
                message_text=message_text,
                reply=response_text,
                detected_language=ctx.get("detected_language"),
            )
            if guarded_response.corrected:
                logger.warning(
                    "WhatsApp KBLI guard corrected fallback RAG reply "
                    "(phone=%s message_id=%s reason=%s)",
                    phone,
                    message_id,
                    guarded_response.reason,
                )
            response_text = guarded_response.reply

            # Channel boundary — same reasoning as the OpenClaw branch above
            # (format the model's answer before chunking, after the KBLI guard,
            # and never the canned messages).
            response_text = format_rich_text(response_text, "whatsapp")

            # Split into chunks if too long for WhatsApp
            chunks = whatsapp_service.chunk_message(response_text, max_length=4000)

            for i, chunk in enumerate(chunks):
                await whatsapp_service.send_message(
                    phone=phone,
                    text=chunk,
                    reply_to_message_id=message_id if i == 0 else None,
                )
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)

            # Log EVERY conversation to Zero (silent notification)
            await notify_zero_conversation_log(
                phone=phone,
                sender_name=sender_name,
                client_message=message_text,
                bot_response=response_text,
                language=ctx.get("detected_language"),
            )

            # If AI flagged escalation, notify team with full context
            if needs_escalation:
                await notify_human_telegram(
                    phone=phone,
                    message_text=message_text,
                    sender_name=sender_name,
                    reason="ai_escalation",
                    client_profile=ctx["client_profile"],
                    conversation_history=ctx["conversation_history"],
                )
                logger.info("🔔 AI escalation triggered for %s", phone)

            # Save conversation to PostgreSQL
            await _save_conversation(
                db_pool=db_pool,
                wa_user_id=ctx["_wa_user_id"],
                session_id=ctx["_session_id"],
                existing_row_id=ctx["_existing_row_id"],
                message_text=message_text,
                response_text=response_text,
                client_profile=ctx["client_profile"],
                sender_name=sender_name,
                phone=phone,
            )

            # Also keep in-memory cache as fast fallback
            _conversation_cache[phone].append({"role": "user", "content": message_text})
            _conversation_cache[phone].append({"role": "assistant", "content": response_text})
            if len(_conversation_cache[phone]) > MAX_HISTORY_MESSAGES:
                _conversation_cache[phone] = _conversation_cache[phone][-MAX_HISTORY_MESSAGES:]

            total_duration = time.time() - start_time
            logger.info(
                f"✅ Zan responded to {phone} in {total_duration:.1f}s "
                f"({len(response_text)} chars, lang={ctx['detected_language']}, "
                f"first={ctx['is_first_message']})",
            )

        except asyncio.TimeoutError:
            timeout_msg = "Un attimo, ci sto mettendo troppo 😅 Riprova tra poco!"
            await whatsapp_service.send_message(
                phone=phone,
                text=timeout_msg,
                reply_to_message_id=message_id,
            )
            await _persist_audit_messages(
                db_pool=_get_db_pool(request),
                phone=phone,
                session_id="",
                message_text=message_text,
                response_text=timeout_msg,
            )

    except Exception as e:
        logger.error("Error processing WhatsApp message from %s: %s", phone, e, exc_info=True)

        try:
            error_msg = "Ops, errore tecnico 😬 Riprova tra un attimo!"
            await whatsapp_service.send_message(
                phone=phone,
                text=error_msg,
                reply_to_message_id=message_id,
            )
            await _persist_audit_messages(
                db_pool=_get_db_pool(request),
                phone=phone,
                session_id="",
                message_text=message_text,
                response_text=error_msg,
            )
        except Exception as send_error:
            logger.error("Failed to send error message: %s", send_error)


async def process_whatsapp_message_and_mark_processed(
    phone: str,
    message_text: str,
    sender_name: str | None,
    message_id: str,
    request: Request,
) -> None:
    """Run WhatsApp fast-path processing and close the durable recovery row."""
    await process_whatsapp_message(
        phone=phone,
        message_text=message_text,
        sender_name=sender_name,
        message_id=message_id,
        request=request,
    )

    db_pool = _get_db_pool(request)
    if db_pool is None:
        return

    try:
        from backend.services.channels import inbound_webhook_repo

        await inbound_webhook_repo.mark_processed(
            db_pool,
            channel="whatsapp",
            dedup_key=message_id,
        )
    except Exception as exc:
        logger.warning(
            "WhatsApp webhook: failed to mark inbound row processed (message_id=%s): %s",
            message_id,
            exc,
        )


def _get_db_pool(request: Request) -> Any:
    """Get database pool safely."""
    try:
        from backend.app.dependencies import get_database

        return get_database(request)
    except Exception as e:
        logger.error("Error getting database for WhatsApp chat: %s", e, exc_info=True)
        return None


def _conversation_jsonb_text(value: Any) -> str:
    """Encode a Python value for explicit text-to-jsonb casting."""
    return json.dumps(value, ensure_ascii=False)


def _decode_conversation_messages(raw_messages: Any) -> list[dict[str, Any]]:
    """Return a normalized conversation message list from old or current JSONB shapes."""
    if not raw_messages:
        return []

    decoded = raw_messages
    for _ in range(2):
        if not isinstance(decoded, str):
            break
        try:
            decoded = json.loads(decoded)
        except (TypeError, json.JSONDecodeError):
            return []

    if not isinstance(decoded, list):
        return []

    return [item for item in decoded if isinstance(item, dict)]


async def _save_conversation(
    db_pool,
    wa_user_id: str,
    session_id: str,
    existing_row_id: int | None,
    message_text: str,
    response_text: str,
    client_profile: dict,
    sender_name: str | None,
    phone: str,
) -> Any:
    """Save conversation messages and updated profile to PostgreSQL."""
    if not db_pool:
        return

    try:
        conversation_msgs = [
            {"role": "user", "content": message_text},
            {"role": "assistant", "content": response_text},
        ]

        async with db_pool.acquire() as conn:
            if existing_row_id:
                # Append to existing session
                existing = await conn.fetchrow(
                    "SELECT messages FROM conversations WHERE id = $1",
                    existing_row_id,
                )
                old_msgs = []
                if existing and existing["messages"]:
                    old_msgs = _decode_conversation_messages(existing["messages"])

                all_msgs = (old_msgs or []) + conversation_msgs
                all_msgs = all_msgs[-MAX_HISTORY_MESSAGES:]

                await conn.execute(
                    "UPDATE conversations SET messages = $1::text::jsonb, metadata = $2::text::jsonb WHERE id = $3",
                    _conversation_jsonb_text(all_msgs),
                    _conversation_jsonb_text(client_profile),
                    existing_row_id,
                )
            else:
                # Create new conversation row
                await conn.execute(
                    "INSERT INTO conversations (user_id, session_id, messages, metadata, created_at) VALUES ($1, $2, $3::text::jsonb, $4::text::jsonb, NOW())",
                    wa_user_id,
                    session_id,
                    _conversation_jsonb_text(conversation_msgs),
                    _conversation_jsonb_text(client_profile),
                )

        logger.info("💾 Conversation saved for %s (session: %s)", phone, session_id)
    except Exception as e:
        logger.warning("Failed to save conversation for %s: %s", phone, e)

    # Unified audit trail (COS-LAW-013): the `conversations` JSONB above is a
    # truncated history buffer (MAX_HISTORY_MESSAGES), not an audit record.
    # Both directions land in conversation_messages like every ChannelRouter
    # channel, so the bot's reply is durable and replayable.
    await _persist_audit_messages(
        db_pool=db_pool,
        phone=phone,
        session_id=session_id,
        message_text=message_text,
        response_text=response_text,
    )


async def _persist_audit_messages(
    db_pool,
    phone: str,
    session_id: str,
    message_text: str,
    response_text: str,
) -> None:
    """Persist one inbound + one outbound row to conversation_messages.

    Non-blocking: failures are logged but never break the reply flow.
    """
    if not db_pool:
        return

    rows = [
        ("inbound", phone, message_text),
        ("outbound", "zantara", response_text),
    ]
    for direction, sender_id, content in rows:
        if not content:
            continue
        try:
            await db_pool.execute(
                """
                INSERT INTO conversation_messages (channel, direction, sender_id, content, metadata)
                VALUES ('whatsapp', $1, $2, $3, $4::text::jsonb)
                """,
                direction,
                sender_id,
                content[:10000],
                json.dumps({"phone": phone, "session_id": session_id}),
            )
        except Exception as e:
            logger.warning(
                "WA audit persist failed (direction=%s, session=%s): %s",
                direction,
                session_id,
                e,
            )


# ============================================================
# WA META INBOX — scoped persistence for phone_number_id=1104946272705747
# (read/write console; see backend/app/routers/wa_inbox.py + spec
#  docs/superpowers/specs/2026-06-03-wa-meta-inbox-design.md sezione 3).
# Only the target Business number flows through this ledger; all other
# numbers stay on the existing inline triage flow above — untouched.
# ============================================================

# Map Meta delivery-receipt status → ledger status. Only forward transitions
# are accepted (sent < delivered < read); failed is terminal and always wins.
_META_STATUS_RANK = {"sent": 1, "delivered": 2, "read": 3}


def _change_phone_number_id(change: WhatsAppChange) -> str | None:
    """Extract value.metadata.phone_number_id from a webhook change."""
    metadata = change.value.get("metadata") or {}
    pnid = metadata.get("phone_number_id")
    return str(pnid) if pnid is not None else None


# Digits-only comparator for phone numbers: "+62 821-3465-159", "62821-3465159"
# and "628213465159" must all compare equal, mirroring the normalisation
# already used for WA memory subjects (_memory_identity.py).
_WA_NON_DIGITS_RE = re.compile(r"\D+")


def _change_display_phone_number(change: WhatsAppChange) -> str | None:
    """Extract value.metadata.display_phone_number from a webhook change."""
    metadata = change.value.get("metadata") or {}
    dpn = metadata.get("display_phone_number")
    return str(dpn) if dpn is not None else None


def _is_meta_inbox_public_number(display_phone_number: str | None) -> bool:
    """True if display_phone_number is the bot's public WA number.

    Defense-in-depth (2026-08-25 double-reply scar): a Meta webhook
    re-registration can arm a SECOND subscription for the SAME underlying
    business number, delivered with a phone_number_id that
    META_INBOX_PHONE_NUMBER_IDS does not (yet) recognise. Such a delivery
    still carries the real, public display number, so this catches it even
    when the id-based check in META_INBOX_PHONE_NUMBER_IDS misses it —
    it must never fall through to the legacy inline reply path.
    """
    if not display_phone_number:
        return False
    try:
        public_number = settings.SUPPORT_WHATSAPP
    except AttributeError:
        return False
    if not isinstance(public_number, str):
        # Defensive: a test/mocked settings object without SUPPORT_WHATSAPP
        # configured must never crash webhook parsing over this optional
        # extra check — fail closed (not a match), the id-based check in
        # META_INBOX_PHONE_NUMBER_IDS still applies.
        return False
    return _WA_NON_DIGITS_RE.sub("", display_phone_number) == _WA_NON_DIGITS_RE.sub(
        "", public_number
    )


def _change_belongs_to_meta_inbox(change: WhatsAppChange) -> bool:
    """True if this webhook change targets the meta-inbox business number.

    Two independent signals, either sufficient (2026-08-25 double-reply
    scar — a Meta webhook re-registration armed a second subscription for
    the same underlying number, delivered with a phone_number_id nobody had
    listed, and its messages fell into the legacy inline reply path beside
    the meta-inbox pipeline's own answer):
      1. phone_number_id is a KNOWN meta-inbox id (META_INBOX_PHONE_NUMBER_IDS).
      2. display_phone_number matches the bot's public WA number — this
         catches a second subscription for the SAME visible number even
         when its phone_number_id has not been added to the set yet.
    """
    if _change_phone_number_id(change) in META_INBOX_PHONE_NUMBER_IDS:
        return True
    return _is_meta_inbox_public_number(_change_display_phone_number(change))


async def _apply_status_callback(conn: Any, status_obj: dict[str, Any]) -> None:
    """Apply one Meta status receipt to the ledger (or stage it if orphan).

    NEVER touches last_customer_at — status receipts are not customer activity
    and must not extend the Meta 24h window (data invariant, spec sezione 2).
    """
    wamid = status_obj.get("id")
    new_status = status_obj.get("status")
    if not wamid or new_status not in ("sent", "delivered", "read", "failed"):
        return

    error_text: str | None = None
    if new_status == "failed":
        errors = status_obj.get("errors") or []
        if errors and isinstance(errors[0], dict):
            error_text = errors[0].get("title") or errors[0].get("message")

    existing = await conn.fetchrow(
        "SELECT id, status FROM meta_inbox_messages WHERE meta_message_id = $1",
        wamid,
    )
    if existing is None:
        # Orphan receipt (status raced ahead of the send commit) → stage it.
        await conn.execute(
            """
            INSERT INTO wa_status_pending (meta_message_id, status, error)
            VALUES ($1, $2, $3)
            ON CONFLICT (meta_message_id) DO UPDATE
            SET status = EXCLUDED.status, error = EXCLUDED.error,
                received_at = NOW()
            """,
            wamid,
            new_status,
            error_text,
        )
        return

    if new_status == "failed":
        await conn.execute(
            "UPDATE meta_inbox_messages SET status = 'failed', error = $2 WHERE id = $1",
            existing["id"],
            error_text,
        )
        return

    # Only advance forward (never regress read → delivered → sent).
    current_rank = _META_STATUS_RANK.get(existing["status"], 0)
    if _META_STATUS_RANK[new_status] > current_rank:
        await conn.execute(
            "UPDATE meta_inbox_messages SET status = $2 WHERE id = $1",
            existing["id"],
            new_status,
        )


async def _handle_meta_inbox_message(
    conn: Any, msg: dict[str, Any], sender_name: str | None, webhook_id: int | None
) -> None:
    """Persist one inbound customer message into the meta-inbox ledger (1 TX).

    Upsert thread (last_customer_at = GREATEST), insert inbound ledger row with
    ON CONFLICT(meta_message_id) DO NOTHING; only if the row is NEW and the
    thread is bot-handled, enqueue a bot reply (queued ledger row + wa_outbox
    needs_generation). The bot text itself is generated by the worker, NOT here.

    After the transaction commits, best-effort mark the inbound message read
    (blue tick — item C5) — deliberately OUTSIDE the transaction: this is a
    Meta Graph API call, and the sub-200ms webhook-ack contract (this whole
    function already runs in a BackgroundTask, see process_meta_inbox_payload)
    must never be extended by holding a DB transaction open across network I/O.
    Only fires for a genuinely NEW inbound row — a duplicate (Meta retry) is
    already acked from the first delivery.

    Gated by ``_manners_enabled()`` (``WA_OUTBOX_MANNERS_ENABLED``, DEFAULT
    OFF) — the SAME dedicated kill-switch as C3/C4 in wa_outbox_worker.py
    (gate review 2026-07-25: this send has no ``whatsapp_ack.ack_enabled()``
    equivalent to AND against, it doesn't go through that module at all).
    Ships dark: unset in prod today.
    """
    wamid = msg.get("id")
    phone = msg.get("from")
    if not wamid or not phone:
        return

    body = ""
    media_type = msg.get("type")
    if media_type == "text":
        body = (msg.get("text") or {}).get("body", "")

    # Meta timestamp is unix seconds (string).
    ts_raw = msg.get("timestamp")
    try:
        meta_ts = datetime.fromtimestamp(int(ts_raw), tz=timezone.utc) if ts_raw else None
    except (TypeError, ValueError):
        meta_ts = None

    # CROSS-PATH ATOMIC CLAIM (2026-08-25 double-reply scar, migration 281).
    # Mirrors the legacy path's claim at the top of process_whatsapp_message —
    # whichever path's INSERT into wa_reply_claims lands first for this wamid
    # wins and proceeds; the loser logs and discards. A legitimate Meta retry
    # of this SAME delivery re-claims its own prior win (owner comparison, see
    # _claim_wamid_reply) and proceeds normally into the idempotent ledger
    # insert below. Best-effort ONLY for "DB unreachable" — a claim-query
    # failure must never mute a genuinely meta-inbox message.
    try:
        won_claim = await _claim_wamid_reply(conn, wamid, WAMID_CLAIMANT_META_INBOX)
    except Exception:
        logger.exception(
            "meta-inbox: cross-path claim failed (non-blocking) wamid=%s", wamid
        )
        won_claim = True
    if not won_claim:
        logger.info(
            "meta-inbox path skipped — wamid=%s already claimed by the legacy path",
            wamid,
        )
        return

    is_new_inbound = False
    async with conn.transaction():
        thread = await conn.fetchrow(
            """
            INSERT INTO meta_inbox_threads (
                counterpart_phone, counterpart_name, last_customer_at, last_message_at
            )
            VALUES ($1, $2, $3, $3)
            ON CONFLICT (counterpart_phone) DO UPDATE
            SET counterpart_name = COALESCE(EXCLUDED.counterpart_name,
                                            meta_inbox_threads.counterpart_name),
                last_customer_at = GREATEST(
                    meta_inbox_threads.last_customer_at,
                    EXCLUDED.last_customer_at
                ),
                last_message_at = GREATEST(
                    meta_inbox_threads.last_message_at,
                    EXCLUDED.last_message_at
                )
            RETURNING thread_id, human_handling
            """,
            phone,
            sender_name,
            meta_ts,
        )
        thread_id = thread["thread_id"]
        human_handling = thread["human_handling"]

        inbound = await conn.fetchrow(
            """
            INSERT INTO meta_inbox_messages (
                thread_id, meta_message_id, direction, sender_role, body,
                media_type, status, webhook_id
            )
            VALUES ($1, $2, 'inbound', 'customer', $3, $4, 'received', $5)
            ON CONFLICT (meta_message_id) WHERE meta_message_id IS NOT NULL
                DO NOTHING
            RETURNING id
            """,
            thread_id,
            wamid,
            body,
            media_type,
            webhook_id,
        )

        if inbound is not None:
            is_new_inbound = True

            # New inbound AND bot still owns the thread → enqueue a bot reply intent.
            if not human_handling:
                bot_row = await conn.fetchrow(
                    """
                    INSERT INTO meta_inbox_messages (
                        thread_id, direction, sender_role, status
                    )
                    VALUES ($1, 'outbound', 'bot', 'queued')
                    RETURNING id
                    """,
                    thread_id,
                )
                await conn.execute(
                    """
                    INSERT INTO wa_outbox (thread_id, message_id, needs_generation, status)
                    VALUES ($1, $2, true, 'pending')
                    ON CONFLICT (message_id) DO NOTHING
                    """,
                    thread_id,
                    bot_row["id"],
                )
        # else: duplicate inbound (Meta retry) → nothing more to do, transaction
        # commits as a no-op past this point.

    if is_new_inbound and _manners_enabled():
        try:
            await whatsapp_service.mark_message_read(wamid)
        except Exception:
            # Best-effort (C5): a failed read-receipt must never break
            # ingestion or the already-enqueued bot reply.
            logger.warning(
                "meta-inbox: mark_message_read failed for wamid=%s", wamid, exc_info=True
            )


async def _resolve_webhook_id(conn: Any, wamid: str) -> int | None:
    """Best-effort lookup of the inbound_webhooks row id for a wamid."""
    try:
        return await conn.fetchval(
            "SELECT id FROM inbound_webhooks WHERE channel = 'whatsapp' AND dedup_key = $1",
            wamid,
        )
    except Exception:
        return None


_WA_MEDIA_PENDING_CHANNEL = "whatsapp_media_pending"


async def _ingest_meta_inbox_media(raw_payload: dict[str, Any], request: Request) -> None:
    """Background task: hand off official-line media to the sovereign Pro worker.

    PULL architecture (Law 2 — PII never leaves the Pro): Fly does NOT download
    the media here. It enqueues a *metadata-only* hand-off row into
    ``events_outbox`` (channel ``whatsapp_media_pending``) — just the Meta
    ``media_id`` + provenance, never a single byte of the document. A worker on
    the Pro pulls these rows, downloads from Meta itself, and stores the blob on
    the Pro's local disk + local intake_queue. Fly ephemeral storage never
    touches client PII (passports, KTP, akta).

    Runs AFTER the 200 ACK like its sibling, so the webhook is never delayed.
    Best-effort: failures are logged, never raised (the webhook already ACKed;
    Meta will not be impacted — the outbox row, if written, is durable and the
    Pro worker is idempotent on the source_ref it derives).
    """
    # Cheap pre-check: only touch the DB if the payload actually carries media
    # on the official number.
    from backend.channels.whatsapp.media_webhook_parse import parse_media_webhook

    parsed = parse_media_webhook(raw_payload)
    official = [m for m in parsed.media if m.phone_number_id in META_INBOX_PHONE_NUMBER_IDS]
    if not official:
        return

    pool = _get_db_pool(request)
    if pool is None:
        logger.warning("meta-inbox media: no db pool, skipping %d media", len(official))
        return

    from backend.services.events import outbox

    published = 0
    try:
        async with pool.acquire() as conn:
            # One transaction for the whole batch: publish() is atomic with the
            # caller's tx (INSERT + NOTIFY both vanish on rollback). All-or-nothing
            # is fine here — the Pro worker reconciles whatever lands.
            async with conn.transaction():
                for media in official:
                    await outbox.publish(
                        conn,
                        _WA_MEDIA_PENDING_CHANNEL,
                        {
                            "media_id": media.media_id,
                            "mime_type": media.mime_type,
                            "message_type": media.message_type,
                            "filename": media.filename,
                            "declared_sha256": media.declared_sha256,
                            "wa_message_id": media.wa_message_id,
                            "from_phone": media.from_phone,
                            "phone_number_id": media.phone_number_id,
                            "sender_name": media.sender_name,
                        },
                    )
                    published += 1
        logger.info(
            "meta-inbox media handoff: found=%d published=%d (PULL: no download on Fly)",
            len(official),
            published,
        )
    except Exception as exc:
        logger.error("meta-inbox media handoff failed: %s", exc, exc_info=True)


async def process_meta_inbox_payload(raw_payload: dict[str, Any], request: Request) -> None:
    """Background task: drive the meta-inbox ledger for the target number only.

    Runs AFTER the webhook has persisted to inbound_webhooks and ACKed 200, so
    it never delays the Meta ACK. Scoped strictly to
    META_INBOX_PHONE_NUMBER_IDS (every phone_number_id known to route to this
    number, not just the canonical one); any other number is ignored here (it
    stays on the existing inline triage flow).
    """
    db_pool = _get_db_pool(request)
    if db_pool is None:
        return

    try:
        webhook = WhatsAppWebhook(**raw_payload)
    except Exception as exc:
        logger.warning("meta-inbox: payload parse failed: %s", exc)
        return

    try:
        async with db_pool.acquire() as conn:
            for entry in webhook.entry:
                for change in entry.changes:
                    if change.field != "messages":
                        continue
                    if not _change_belongs_to_meta_inbox(change):
                        continue

                    value = change.value

                    # STATUS branch (delivery receipts) — never touches window.
                    for status_obj in value.get("statuses", []):
                        await _apply_status_callback(conn, status_obj)

                    # MESSAGE branch (inbound customer messages).
                    contacts = value.get("contacts", [])
                    sender_name = None
                    if contacts:
                        sender_name = contacts[0].get("profile", {}).get("name")

                    for msg in value.get("messages", []):
                        wamid = msg.get("id")
                        webhook_id = await _resolve_webhook_id(conn, wamid) if wamid else None
                        await _handle_meta_inbox_message(conn, msg, sender_name, webhook_id)
    except Exception as exc:
        logger.error("meta-inbox: processing failed: %s", exc, exc_info=True)


@router.get("")
async def verify_webhook(request: Request) -> PlainTextResponse:
    """
    Verify webhook for Meta WhatsApp setup.

    Meta sends GET request with hub.mode, hub.verify_token, hub.challenge.
    We must return hub.challenge if verify_token matches.
    """
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info(f"Webhook verification request: mode={mode}, token={'***' if token else None}")

    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        logger.info("✅ Webhook verification successful")
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning("❌ Webhook verification failed: invalid token or mode")
    raise HTTPException(status_code=403, detail="Invalid verify token")


def _verify_whatsapp_signature(body: bytes, signature_header: str | None) -> bool:
    """Verify X-Hub-Signature-256 HMAC-SHA256 from Meta WhatsApp webhook.

    Args:
        body: Raw request body bytes
        signature_header: Value of X-Hub-Signature-256 header (format: "sha256=<hex>")

    Returns:
        True if signature is valid or verification is disabled (no app secret configured)
    """
    app_secret = settings.whatsapp_app_secret
    if not app_secret:
        # No app secret configured — skip verification (dev mode)
        return True

    if not signature_header:
        logger.warning("⚠️ WhatsApp webhook: missing X-Hub-Signature-256 header")
        return False

    if not signature_header.startswith("sha256="):
        logger.warning("⚠️ WhatsApp webhook: malformed signature header")
        return False

    expected_sig = signature_header[7:]  # Strip "sha256=" prefix
    computed_sig = hmac.new(
        app_secret.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(computed_sig, expected_sig)


@router.post("")
async def whatsapp_webhook(
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, Any]:
    """
    Handle incoming WhatsApp messages — ack-first pattern (P0-6 audit 2026-04-29).

    Meta sends POST requests with message events.
    Verifies X-Hub-Signature-256 HMAC if WHATSAPP_APP_SECRET is configured.

    Flow:
      1. Verify HMAC signature (synchronous, fast).
      2. Parse + persist payload to ``inbound_webhooks`` (idempotent on
         Meta message_id via UNIQUE(channel, dedup_key)).
      3. Schedule fast-path processing via FastAPI BackgroundTasks (existing
         behaviour).
      4. Return 200 OK in <200ms — guaranteed by virtue of (1)+(2)+(3) all
         being O(1) async DB ops.

    The WebhookProcessor (services/channels/webhook_processor.py) drains
    any rows that the fast path missed (Fly machine crash mid-handler,
    handler exception, etc.) so no inbound message is silently lost.
    """
    # HMAC-SHA256 signature verification
    body = await request.body()
    signature = request.headers.get("X-Hub-Signature-256")

    if not _verify_whatsapp_signature(body, signature):
        logger.warning(
            f"❌ WhatsApp webhook signature verification failed "
            f"(from {request.client.host if request.client else 'unknown'})"
        )
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse body into webhook model
    try:
        raw_payload = json.loads(body)
        webhook = WhatsAppWebhook(**raw_payload)
    except Exception as e:
        logger.error("❌ WhatsApp webhook body parse error: %s", e)
        raise HTTPException(status_code=400, detail="Invalid request body")

    logger.info(f"Webhook received: {webhook.object}, {len(webhook.entry)} entries")

    # ── Ack-first persistence (P0-6) ──
    # Persist the verified payload BEFORE any business processing so a Fly
    # machine crash mid-flight does not lose the webhook. Dedup key is the
    # Meta-provided message_id (one row per inbound DM, even if Meta retries
    # the webhook before our 200 OK lands).
    db_pool = _get_db_pool(request)
    persisted_message_inserted: dict[str, bool] = {}
    if db_pool is not None:
        for entry in webhook.entry:
            for change in entry.changes:
                if change.field != "messages":
                    continue
                for msg in change.value.get("messages", []):
                    msg_id = msg.get("id")
                    if not msg_id:
                        continue
                    try:
                        from backend.services.channels import inbound_webhook_repo

                        _, inserted = await inbound_webhook_repo.persist(
                            db_pool,
                            channel="whatsapp",
                            dedup_key=msg_id,
                            payload=raw_payload,
                            recovery_after_seconds=WHATSAPP_FAST_PATH_RECOVERY_DELAY_SECONDS,
                        )
                        persisted_message_inserted[msg_id] = inserted
                    except Exception as exc:
                        logger.warning(
                            "WhatsApp webhook: persist failed "
                            "(message_id=%s): %s — falling back to "
                            "BackgroundTasks-only path",
                            msg_id,
                            exc,
                        )

    # WA Meta Inbox: if any change targets the dedicated Business number, run
    # its ledger persistence in a single background task (after ACK, so the
    # 200 is never delayed). The target number does NOT use the inline triage
    # flow below — its bot replies are generated by the wa_outbox worker.
    meta_inbox_in_payload = any(
        change.field == "messages" and _change_belongs_to_meta_inbox(change)
        for entry in webhook.entry
        for change in entry.changes
    )
    if meta_inbox_in_payload:
        background_tasks.add_task(
            process_meta_inbox_payload,
            raw_payload=raw_payload,
            request=request,
        )
        # Anello 1: pull any media attachments on the official line into the
        # intake pipeline (download → enqueue). Separate task so a media
        # download never delays the ledger or the Meta ACK.
        background_tasks.add_task(
            _ingest_meta_inbox_media,
            raw_payload=raw_payload,
            request=request,
        )

    for entry in webhook.entry:
        for change in entry.changes:
            if change.field != "messages":
                logger.debug(f"Ignoring non-message change: {change.field}")
                continue

            # Target Business number → handled by the meta-inbox task above.
            # Do NOT run the inline triage flow for it (would double-reply).
            # _change_belongs_to_meta_inbox checks BOTH phone_number_id and
            # display_phone_number (2026-08-25 double-reply scar), so neither
            # an unlisted id nor a same-number resubscribe can re-arm this
            # legacy path.
            if _change_belongs_to_meta_inbox(change):
                continue

            value = change.value

            messages = value.get("messages", [])
            if not messages:
                logger.debug("No messages in webhook")
                continue

            contacts = value.get("contacts", [])
            sender_name = None
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name")

            for msg in messages:
                phone = msg.get("from")
                message_id = msg.get("id")
                message_type = msg.get("type")

                logger.info("Message from %s: type=%s, id=%s", phone, message_type, message_id)

                if message_type != "text":
                    logger.info("Ignoring non-text message type: %s", message_type)
                    continue

                text_obj = msg.get("text", {})
                text = text_obj.get("body", "")

                if not text:
                    logger.warning("Empty text body from %s", phone)
                    continue

                if persisted_message_inserted.get(message_id) is False:
                    logger.info(
                        "Duplicate WhatsApp webhook skipped: %s",
                        message_id,
                    )
                    continue

                background_tasks.add_task(
                    process_whatsapp_message_and_mark_processed,
                    phone=phone,
                    message_text=text,
                    sender_name=sender_name,
                    message_id=message_id,
                    request=request,
                )

                logger.info("Message from %s scheduled for processing", phone)

    # Record webhook metric
    try:
        from backend.app.metrics import metrics_collector

        metrics_collector.record_webhook_request(channel="whatsapp", status="success")
    except Exception:
        pass  # Metrics must never break webhook processing

    return {"status": "ok"}


@router.get("/status")
async def whatsapp_status() -> dict[str, Any]:
    """Check WhatsApp integration status."""
    configured = bool(settings.whatsapp_api_token and settings.whatsapp_phone_number_id)

    return {
        "configured": configured,
        "phone_number_id": settings.whatsapp_phone_number_id if configured else None,
        "triage_enabled": True,
        "personal_contacts_count": len(whatsapp_triage_service.personal_contacts),
        "ai_model": settings.whatsapp_openclaw_model,
        "ai_runtime": "openclaw_cli",
        "ai_thinking": settings.whatsapp_openclaw_thinking,
        "ai_persona": settings.whatsapp_openclaw_persona,
        "ai_autonomy_mode": settings.whatsapp_openclaw_autonomy_mode,
        "persona": settings.whatsapp_openclaw_persona,
    }


# ============================================================
# ALIAS ROUTER: /api/whatsapp/webhook (Meta Dashboard legacy URL)
# ============================================================
alias_router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@alias_router.get("/webhook")
async def verify_webhook_alias(request: Request) -> Any:
    """Alias for /webhook/whatsapp (GET) — Meta webhook verification."""
    return await verify_webhook(request)


@alias_router.post("/webhook")
async def whatsapp_webhook_alias(
    background_tasks: BackgroundTasks,
    request: Request,
) -> Any:
    """Alias for /webhook/whatsapp (POST) — Meta webhook messages."""
    return await whatsapp_webhook(background_tasks, request)
