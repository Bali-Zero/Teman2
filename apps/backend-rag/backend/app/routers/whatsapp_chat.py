"""
WhatsApp Chat Router
Handles incoming WhatsApp messages with intelligent triage (personal vs business).

Architecture:
- Webhook receives messages from Meta WhatsApp Cloud API
- Triage service decides: personal → human, business → AI RAG
- RAG responses use same streaming orchestrator as Telegram
- Notifications sent to admin via Telegram for personal messages

"""

import asyncio
import logging
import time
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database, get_orchestrator
from backend.services.integrations.messaging_identity_service import (
    get_messaging_identity_service,
)
from backend.services.integrations.telegram_bot_service import telegram_bot
from backend.services.integrations.whatsapp_service import whatsapp_service
from backend.services.integrations.whatsapp_triage_service import (
    TriageDecision,
    whatsapp_triage_service,
)
from backend.services.rag.agentic import AgenticRAGOrchestrator

logger = logging.getLogger(__name__)

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


async def notify_human_telegram(
    phone: str,
    message_text: str,
    sender_name: str | None = None,
    reason: str = "personal_contact",
):
    """
    Send Telegram notification to admin when message is escalated to human.

    Args:
        phone: Sender phone number
        message_text: Message content
        sender_name: Optional sender name
        reason: Escalation reason
    """
    if not settings.admin_telegram_chat_id:
        logger.warning("Admin Telegram chat ID not configured, skipping notification")
        return

    reason_emoji = {
        "personal_contact": "👤",
        "explicit_request": "🤚",
        "personal_context": "💬",
    }

    emoji = reason_emoji.get(reason, "📩")
    display_name = sender_name or "Unknown"

    notification_text = f"""{emoji} **Messaggio WhatsApp Personale**

**Da:** {display_name} ({phone})
**Motivo:** {reason.replace("_", " ").title()}

**Messaggio:**
{message_text}

---
Rispondi direttamente su WhatsApp!
"""

    try:
        await telegram_bot.send_message(
            chat_id=settings.admin_telegram_chat_id,
            text=notification_text,
            parse_mode="Markdown",
        )
        logger.info(f"Telegram notification sent for WhatsApp message from {phone}")
    except Exception as e:
        logger.error(f"Failed to send Telegram notification: {e}")


async def process_whatsapp_message(
    phone: str,
    message_text: str,
    sender_name: str | None,
    message_id: str,
    request: Request,
):
    """
    Background task to process WhatsApp message.

    This is executed async so webhook can return 200 immediately to Meta.

    Args:
        phone: Sender phone number
        message_text: Message content
        sender_name: Optional sender name from WhatsApp profile
        message_id: WhatsApp message ID (for reply context)
        request: FastAPI request (for dependencies)
    """
    try:
        # Mark message as read
        await whatsapp_service.mark_message_read(message_id)

        # 1. TRIAGE: Personal or Business?
        decision, reason = await whatsapp_triage_service.should_escalate(
            phone=phone,
            message_text=message_text,
            sender_name=sender_name,
        )

        logger.info(f"Triage decision for {phone}: {decision} (reason: {reason})")

        # 2. ESCALATE TO HUMAN
        if decision in [
            TriageDecision.ESCALATE_PERSONAL,
            TriageDecision.ESCALATE_REQUEST,
            TriageDecision.ESCALATE_CONTEXT,
        ]:
            # Send escalation message to user
            escalation_msg = whatsapp_triage_service.get_escalation_message(decision, sender_name)
            await whatsapp_service.send_message(
                phone=phone,
                text=escalation_msg,
                reply_to_message_id=message_id,
            )

            # Notify admin via Telegram
            await notify_human_telegram(
                phone=phone,
                message_text=message_text,
                sender_name=sender_name,
                reason=reason,
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

        # 4. AI CAN HANDLE - Process with RAG
        orchestrator: AgenticRAGOrchestrator = get_orchestrator(request)

        # Get database pool for identity lookup
        db_pool = get_database(request)
        identity_service = get_messaging_identity_service(db_pool)

        # Check if phone is mapped to a user (team member or portal client)
        mapping = await identity_service.get_user_by_phone(phone)

        if mapping:
            # Use user ID for unified cross-channel conversation
            whatsapp_user_id = str(mapping["user_id"])
            session_id = f"unified_session_{whatsapp_user_id}"

            # Update last message timestamp
            await identity_service.update_last_message(phone=phone)

            logger.info(
                f"🔗 Phone {phone} mapped to user {whatsapp_user_id} "
                f"(verified: {mapping['verified']})"
            )
        else:
            # Fallback: channel-specific user_id (original behavior)
            whatsapp_user_id = f"whatsapp_{phone}"
            session_id = f"whatsapp_session_{phone}"
            logger.info(f"📱 Phone {phone} NOT mapped, using channel-specific ID")

        logger.info(
            f"🚀 [FASE 2.1] Processing business query from {phone} with RAG and status updates",
            extra={
                "phone": phone,
                "session_id": session_id,
                "user_id": whatsapp_user_id,
                "message_length": len(message_text),
                "feature": "whatsapp_status_updates",
            },
        )

        # Stream query with status updates and timeout (WhatsApp doesn't support message editing)
        accumulated_text = ""
        start_time = time.time()
        last_status_time = time.time()
        status_update_interval = 10.0  # Send status update every 10 seconds
        current_phase = None
        phases_seen = set()
        status_updates_sent = 0

        # Phase emoji mapping
        phase_emoji = {
            "processing": "🔍",
            "searching": "📚",
            "analyzing": "🧠",
            "thinking": "💭",
            "reasoning": "🤔",
            "generating": "✍️",
        }

        try:
            # Wrap streaming in 45-second timeout
            async with asyncio.timeout(45):
                async for event in orchestrator.stream_query(
                    query=message_text,
                    user_id=whatsapp_user_id,
                    session_id=session_id,
                ):
                    event_type = event.get("type")

                    # Track status/phase changes
                    if event_type == "status":
                        status_data = event.get("data", {})
                        if isinstance(status_data, dict):
                            new_phase = status_data.get("status")
                            if new_phase and new_phase != current_phase:
                                current_phase = new_phase
                                phases_seen.add(new_phase)

                    # Accumulate text tokens
                    if event_type == "token":
                        accumulated_text += event.get("data", "")

                    # Send periodic status updates (every 10 seconds)
                    current_time = time.time()
                    if (
                        current_phase
                        and (current_time - last_status_time) >= status_update_interval
                    ):
                        # Only send if we haven't sent this phase before
                        emoji = phase_emoji.get(current_phase, "⏳")
                        status_msg = f"{emoji} {current_phase.replace('_', ' ').title()}..."

                        try:
                            await whatsapp_service.send_message(
                                phone=phone,
                                text=status_msg,
                                reply_to_message_id=message_id,
                            )
                            status_updates_sent += 1
                            elapsed = current_time - start_time
                            logger.info(
                                f"✅ [FASE 2.1] WhatsApp status update #{status_updates_sent} sent: {status_msg}",
                                extra={
                                    "phone": phone,
                                    "phase": current_phase,
                                    "elapsed_seconds": round(elapsed, 1),
                                    "update_number": status_updates_sent,
                                },
                            )
                        except Exception as status_error:
                            logger.warning(
                                f"❌ [FASE 2.1] Failed status update to {phone}: {status_error}",
                                extra={"phone": phone, "phase": current_phase},
                            )

                        last_status_time = current_time

        except asyncio.TimeoutError:
            # Send timeout message to user
            timeout_duration = time.time() - start_time
            logger.warning(
                f"⏱️ [FASE 2.2] WhatsApp query TIMEOUT after {timeout_duration:.1f}s from {phone}",
                extra={
                    "phone": phone,
                    "timeout_seconds": 45,
                    "actual_elapsed": round(timeout_duration, 1),
                    "status_updates_sent": status_updates_sent,
                    "phases_seen": list(phases_seen),
                    "feature": "whatsapp_timeout_handling",
                },
            )
            await whatsapp_service.send_message(
                phone=phone,
                text="Un attimo, ci sto mettendo troppo 😅 Riprova tra poco!",
                reply_to_message_id=message_id,
            )
            return

        # Send final accumulated response
        if not accumulated_text:
            accumulated_text = (
                "Scusa, qualcosa è andato storto 😅 Riprova!"
            )

        # Split into chunks if too long (WhatsApp limit: 4096 chars)
        chunks = whatsapp_service.chunk_message(accumulated_text, max_length=4000)

        for i, chunk in enumerate(chunks):
            await whatsapp_service.send_message(
                phone=phone,
                text=chunk,
                reply_to_message_id=message_id if i == 0 else None,
            )

            # Small delay between chunks to avoid rate limiting
            if i < len(chunks) - 1:
                await asyncio.sleep(0.5)

        total_duration = time.time() - start_time
        logger.info(
            f"✅ [FASE 2] WhatsApp RAG response completed for {phone}",
            extra={
                "phone": phone,
                "total_duration_seconds": round(total_duration, 2),
                "chunks_sent": len(chunks),
                "response_chars": len(accumulated_text),
                "status_updates_sent": status_updates_sent,
                "phases_count": len(phases_seen),
                "timed_out": False,
                "feature": "whatsapp_complete",
            },
        )

    except Exception as e:
        logger.error(f"Error processing WhatsApp message from {phone}: {e}")

        # Send error message to user
        try:
            await whatsapp_service.send_message(
                phone=phone,
                text="Ops, errore tecnico 😬 Riprova tra un attimo!",
                reply_to_message_id=message_id,
            )
        except Exception as send_error:
            logger.error(f"Failed to send error message: {send_error}")


@router.get("")
async def verify_webhook(request: Request):
    """
    Verify webhook for Meta WhatsApp setup.

    Meta sends GET request with hub.mode, hub.verify_token, hub.challenge.
    We must return hub.challenge if verify_token matches.

    This is called during initial webhook setup in Meta Business Manager.
    """
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info(f"Webhook verification request: mode={mode}, token={'***' if token else None}")

    # Verify token matches our configured secret
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        logger.info("✅ Webhook verification successful")
        # Return challenge as integer (Meta requirement)
        return int(challenge)

    logger.warning("❌ Webhook verification failed: invalid token or mode")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("")
async def whatsapp_webhook(
    webhook: WhatsAppWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """
    Handle incoming WhatsApp messages.

    Meta sends POST requests with message events.
    We process in background and return 200 immediately.

    Flow:
    1. Parse webhook payload
    2. Extract message details
    3. Process in background (triage + RAG)
    4. Return 200 to Meta (within 5s)
    """

    logger.info(f"Webhook received: {webhook.object}, {len(webhook.entry)} entries")

    # Iterate through entries (usually 1)
    for entry in webhook.entry:
        # Iterate through changes (usually 1)
        for change in entry.changes:
            # Only handle "messages" field
            if change.field != "messages":
                logger.debug(f"Ignoring non-message change: {change.field}")
                continue

            value = change.value

            # Extract messages array
            messages = value.get("messages", [])
            if not messages:
                logger.debug("No messages in webhook")
                continue

            # Extract contacts (sender profile info)
            contacts = value.get("contacts", [])
            sender_name = None
            if contacts:
                sender_name = contacts[0].get("profile", {}).get("name")

            # Process each message (usually 1)
            for msg in messages:
                phone = msg.get("from")
                message_id = msg.get("id")
                message_type = msg.get("type")

                logger.info(f"Message from {phone}: type={message_type}, id={message_id}")

                # Only handle text messages for now
                if message_type != "text":
                    logger.info(f"Ignoring non-text message type: {message_type}")
                    # Could add image/audio support later
                    continue

                text_obj = msg.get("text", {})
                text = text_obj.get("body", "")

                if not text:
                    logger.warning(f"Empty text body from {phone}")
                    continue

                # Schedule background processing
                background_tasks.add_task(
                    process_whatsapp_message,
                    phone=phone,
                    message_text=text,
                    sender_name=sender_name,
                    message_id=message_id,
                    request=request,
                )

                logger.info(f"Message from {phone} scheduled for processing")

    # Return 200 immediately to Meta
    return {"status": "ok"}


@router.get("/status")
async def whatsapp_status():
    """
    Check WhatsApp integration status.

    Public endpoint for health monitoring.
    """
    configured = bool(settings.whatsapp_api_token and settings.whatsapp_phone_number_id)

    return {
        "configured": configured,
        "phone_number_id": settings.whatsapp_phone_number_id if configured else None,
        "triage_enabled": True,
        "personal_contacts_count": len(whatsapp_triage_service.personal_contacts),
    }


# ============================================================
# ALIAS ROUTER: /api/whatsapp/webhook (Meta Dashboard legacy URL)
# ============================================================
alias_router = APIRouter(prefix="/api/whatsapp", tags=["whatsapp"])


@alias_router.get("/webhook")
async def verify_webhook_alias(request: Request):
    """Alias for /webhook/whatsapp (GET) — Meta webhook verification."""
    return await verify_webhook(request)


@alias_router.post("/webhook")
async def whatsapp_webhook_alias(
    webhook: WhatsAppWebhook,
    background_tasks: BackgroundTasks,
    request: Request,
):
    """Alias for /webhook/whatsapp (POST) — Meta webhook messages."""
    return await whatsapp_webhook(webhook, background_tasks, request)
