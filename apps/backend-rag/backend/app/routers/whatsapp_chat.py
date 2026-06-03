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
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field

from backend.app.core.config import settings
from backend.services.integrations.openclaw_whatsapp_bridge import ask_openclaw_whatsapp
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.integrations.wa_outbox_worker import META_INBOX_PHONE_NUMBER_ID
from backend.services.integrations.whatsapp_service import whatsapp_service
from backend.services.integrations.whatsapp_triage_service import (
    TriageDecision,
    whatsapp_triage_service,
)
from backend.services.whatsapp_kbli_guard import sanitize_whatsapp_kbli_reply
from backend.services.whatsapp_onboarding_detector import get_onboarding_detector

logger = logging.getLogger(__name__)

# In-memory conversation history per phone number (fast fallback)
_conversation_cache: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_MESSAGES = 20

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])
WHATSAPP_FAST_PATH_RECOVERY_DELAY_SECONDS = 30


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

        # 0. ALLOWLIST CHECK: Silently ignore numbers not in whitelist
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
                await whatsapp_service.send_message(
                    phone=phone,
                    text="Great! I've started your onboarding process. You'll receive updates shortly! 🎉",
                    reply_to_message_id=message_id,
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
            logger.info("Welcome message sent to %s", phone)
            return

        # 4. AI CAN HANDLE — OpenClaw bridge first, then Gemini RAG fallback.
        from backend.services.whatsapp_context_builder import build_context

        db_pool = _get_db_pool(request)

        start_time = time.time()

        try:
            # Build rich context
            ctx = await build_context(phone, sender_name, message_text, db_pool)

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

            from backend.prompts.whatsapp_persona import build_system_prompt

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

            orchestrator = get_orchestrator(request)
            wa_user_id = f"whatsapp_{phone}"
            session_id = f"wa_session_{phone}"

            # Inject WhatsApp persona at start of conversation history (system-like context)
            # This guides Zantara's base persona to be more WhatsApp-natural
            enhanced_history = []
            if ctx["is_first_message"]:
                # Add persona instructions as first "context" message
                enhanced_history.append(
                    {
                        "role": "user",
                        "content": f"[CONTESTO WHATSAPP]\n{whatsapp_persona_instructions}\n\nRispondi sempre come Zan di Bali Zero, naturalmente su WhatsApp (no markdown, tono umano).",
                    },
                )
                enhanced_history.append(
                    {
                        "role": "assistant",
                        "content": "Capito, rispondo come Zan su WhatsApp - tono naturale, niente markdown, focus su visa e business a Bali.",
                    },
                )

            enhanced_history.extend(ctx["conversation_history"])

            # Direct RAG query (Gemini will respond with Zantara + WhatsApp persona blend)
            rag_result = await orchestrator.process_query(
                query=message_text,
                user_id=wa_user_id,
                session_id=session_id,
                conversation_history=enhanced_history,
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
            await whatsapp_service.send_message(
                phone=phone,
                text="Un attimo, ci sto mettendo troppo 😅 Riprova tra poco!",
                reply_to_message_id=message_id,
            )

    except Exception as e:
        logger.error("Error processing WhatsApp message from %s: %s", phone, e, exc_info=True)

        try:
            await whatsapp_service.send_message(
                phone=phone,
                text="Ops, errore tecnico 😬 Riprova tra un attimo!",
                reply_to_message_id=message_id,
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
            "WhatsApp webhook: failed to mark inbound row processed "
            "(message_id=%s): %s",
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

        # Duplicate inbound (Meta retry) → nothing more to do.
        if inbound is None:
            return

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


async def _resolve_webhook_id(conn: Any, wamid: str) -> int | None:
    """Best-effort lookup of the inbound_webhooks row id for a wamid."""
    try:
        return await conn.fetchval(
            "SELECT id FROM inbound_webhooks WHERE channel = 'whatsapp' AND dedup_key = $1",
            wamid,
        )
    except Exception:
        return None


async def process_meta_inbox_payload(raw_payload: dict[str, Any], request: Request) -> None:
    """Background task: drive the meta-inbox ledger for the target number only.

    Runs AFTER the webhook has persisted to inbound_webhooks and ACKed 200, so
    it never delays the Meta ACK. Scoped strictly to
    META_INBOX_PHONE_NUMBER_ID; any other number is ignored here (it stays on
    the existing inline triage flow).
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
                    if _change_phone_number_id(change) != META_INBOX_PHONE_NUMBER_ID:
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
        change.field == "messages"
        and _change_phone_number_id(change) == META_INBOX_PHONE_NUMBER_ID
        for entry in webhook.entry
        for change in entry.changes
    )
    if meta_inbox_in_payload:
        background_tasks.add_task(
            process_meta_inbox_payload,
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
            if _change_phone_number_id(change) == META_INBOX_PHONE_NUMBER_ID:
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
