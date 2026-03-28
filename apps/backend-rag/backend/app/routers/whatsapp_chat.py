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
import json
import logging
import time
from collections import defaultdict
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.integrations.whatsapp_service import whatsapp_service
from backend.services.integrations.whatsapp_triage_service import (
    TriageDecision,
    whatsapp_triage_service,
)
from backend.services.whatsapp_onboarding_detector import get_onboarding_detector

logger = logging.getLogger(__name__)

# In-memory conversation history per phone number (fast fallback)
_conversation_cache: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_MESSAGES = 20

router = APIRouter(prefix="/webhook/whatsapp", tags=["whatsapp"])


class WhatsAppMessage(BaseModel):
    """WhatsApp message structure."""

    from_: str  # Sender phone
    id: str  # Message ID
    timestamp: str
    type: str  # text, image, audio, etc.
    text: dict[str, Any] | None = None

    class Config:
        fields = {"from_": "from"}


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

**Cliente:** {display_name} (+{phone}) {lang_flag}

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
        logger.error(f"Failed to send conversation log to Zero: {e}")


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

**Da:** {display_name} (+{phone})
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
        logger.info(f"Telegram notification sent for WhatsApp escalation from {phone}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


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
            logger.info(f"Ignored message from non-allowed number: {phone}")
            return

        # 1. TRIAGE: Personal or Business?
        decision, reason = await whatsapp_triage_service.should_escalate(
            phone=phone,
            message_text=message_text,
            sender_name=sender_name,
        )

        logger.info(f"Triage decision for {phone}: {decision} (reason: {reason})")

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
                logger.info(f"🎯 Auto-triggered onboarding chain for {phone}: {onboarding_result}")
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
            logger.error(f"Onboarding detection failed for {phone}: {e}", exc_info=True)
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
                    logger.error(f"Error building context for WhatsApp: {e}", exc_info=True)
                    ctx = None

            await notify_human_telegram(
                phone=phone,
                message_text=message_text,
                sender_name=sender_name,
                reason=reason,
                client_profile=ctx.get("client_profile"),
                conversation_history=ctx.get("conversation_history"),
            )

            logger.info(f"Message from {phone} escalated to human (reason: {reason})")
            return

        # 3. OFFER CHOICE (ambiguous)
        if decision == TriageDecision.OFFER_CHOICE:
            welcome_msg = whatsapp_triage_service.get_welcome_message(sender_name)
            await whatsapp_service.send_message(
                phone=phone,
                text=welcome_msg,
                reply_to_message_id=message_id,
            )
            logger.info(f"Welcome message sent to {phone}")
            return

        # 4. AI CAN HANDLE — Gemini 3 Flash with RAG (direct response, no Claude)
        from backend.prompts.whatsapp_persona import build_system_prompt
        from backend.services.whatsapp_context_builder import build_context

        db_pool = _get_db_pool(request)

        logger.info(f"🚀 Processing query from {phone} with Gemini 3 Flash (RAG + Zan persona)")

        start_time = time.time()

        try:
            # Build rich context
            ctx = await build_context(phone, sender_name, message_text, db_pool)

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
                logger.info(f"🔔 AI escalation triggered for {phone}")

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
        logger.error(f"Error processing WhatsApp message from {phone}: {e}", exc_info=True)

        try:
            await whatsapp_service.send_message(
                phone=phone,
                text="Ops, errore tecnico 😬 Riprova tra un attimo!",
                reply_to_message_id=message_id,
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")


def _get_db_pool(request: Request) -> Any:
    """Get database pool safely."""
    try:
        from backend.app.dependencies import get_database

        return get_database(request)
    except Exception as e:
        logger.error(f"Error getting database for WhatsApp chat: {e}", exc_info=True)
        return None


async def _save_conversation(
    db_pool,
    wa_user_id: str,
    session_id: str,
    existing_row_id: int | None,
    message_text: str,
    response_text: str,
    client_profile: dict,
    sender_name: str | None,  # noqa: ARG001
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
                    old_msgs = existing["messages"]
                    if isinstance(old_msgs, str):
                        old_msgs = json.loads(old_msgs)

                all_msgs = (old_msgs or []) + conversation_msgs
                all_msgs = all_msgs[-MAX_HISTORY_MESSAGES:]

                await conn.execute(
                    "UPDATE conversations SET messages = $1::jsonb, metadata = $2::jsonb WHERE id = $3",
                    json.dumps(all_msgs),
                    json.dumps(client_profile),
                    existing_row_id,
                )
            else:
                # Create new conversation row
                await conn.execute(
                    "INSERT INTO conversations (user_id, session_id, messages, metadata, created_at) VALUES ($1, $2, $3::jsonb, $4::jsonb, NOW())",
                    wa_user_id,
                    session_id,
                    json.dumps(conversation_msgs),
                    json.dumps(client_profile),
                )

        logger.info(f"💾 Conversation saved for {phone} (session: {session_id})")
    except Exception as e:
        logger.warning(f"Failed to save conversation for {phone}: {e}")


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


@router.post("")
async def whatsapp_webhook(
    webhook: WhatsAppWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, Any]:
    """
    Handle incoming WhatsApp messages.

    Meta sends POST requests with message events.
    We process in background and return 200 immediately.
    """
    logger.info(f"Webhook received: {webhook.object}, {len(webhook.entry)} entries")

    for entry in webhook.entry:
        for change in entry.changes:
            if change.field != "messages":
                logger.debug(f"Ignoring non-message change: {change.field}")
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

                logger.info(f"Message from {phone}: type={message_type}, id={message_id}")

                if message_type != "text":
                    logger.info(f"Ignoring non-text message type: {message_type}")
                    continue

                text_obj = msg.get("text", {})
                text = text_obj.get("body", "")

                if not text:
                    logger.warning(f"Empty text body from {phone}")
                    continue

                background_tasks.add_task(
                    process_whatsapp_message,
                    phone=phone,
                    message_text=text,
                    sender_name=sender_name,
                    message_id=message_id,
                    request=request,
                )

                logger.info(f"Message from {phone} scheduled for processing")

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
        "ai_model": "gemini-3-flash",
        "persona": "zan_v2",
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
    webhook: WhatsAppWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
) -> Any:
    """Alias for /webhook/whatsapp (POST) — Meta webhook messages."""
    return await whatsapp_webhook(webhook, background_tasks, request)
