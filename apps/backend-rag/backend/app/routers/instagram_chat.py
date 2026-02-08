"""
Instagram Chat Router
Handles incoming Instagram DMs with AI auto-reply via RAG pipeline.

Architecture:
- Webhook receives messages from Meta Instagram Graph API
- All messages → AI RAG (no triage for v1, simplify)
- RAG responses use same Claude Direct pipeline as WhatsApp
- Notifications sent to admin via Telegram for errors

Differences from WhatsApp:
- API base: graph.instagram.com (not graph.facebook.com)
- Sender ID: IGSID (not phone number)
- Payload: entry[].messaging[].message.text (not entry[].changes[].value.messages[])
- Char limit: 1000 (not 4096)
"""

import asyncio
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from asyncpg import Pool
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse

from backend.app.core.config import settings
from backend.app.dependencies import get_current_user, get_database
from backend.services.integrations.instagram_service import instagram_service
from backend.services.integrations.telegram_bot_service import telegram_bot

logger = logging.getLogger(__name__)

# In-memory conversation history per IGSID (last N messages)
# Format: {igsid: [{"role": "user"/"assistant", "content": "..."}]}
_conversation_cache: dict[str, list[dict]] = defaultdict(list)
MAX_HISTORY_MESSAGES = 20

router = APIRouter(prefix="/api/instagram", tags=["instagram"])


@router.get("/conversations")
async def get_instagram_conversations(
    limit: int = 50,
    offset: int = 0,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Get Instagram conversations from Zan's sessions.
    Format compatible with frontend InstagramConversation type.
    """
    try:
        async with db.acquire() as conn:
            # Query conversations table where session_id starts with 'ig_session_'
            rows = await conn.fetch(
                """
                SELECT 
                    c.id,
                    c.session_id,
                    c.user_id,
                    c.messages,
                    c.metadata,
                    c.created_at,
                    c.created_at as updated_at,
                    REGEXP_REPLACE(c.user_id, '^instagram_', '') as instagram_user_id,
                    NULL as client_id,
                    NULL as client_name
                FROM conversations c
                WHERE c.session_id LIKE 'ig_session_%' OR c.user_id LIKE 'instagram_%'
                ORDER BY c.created_at DESC
                LIMIT $1 OFFSET $2
                """,
                limit,
                offset,
            )

            conversations = []
            for row in rows:
                messages_raw = row["messages"]
                messages = []
                if isinstance(messages_raw, str):
                    try:
                        import json
                        messages = json.loads(messages_raw)
                    except:
                        messages = []
                else:
                    messages = messages_raw or []

                last_message = ""
                unread_count = 0

                if messages:
                    last_msg = messages[-1] if messages else {}
                    if isinstance(last_msg, dict):
                        last_message = last_msg.get("content", "")[:200]
                    else:
                        last_message = str(last_msg)[:200]

                    # Simple unread logic: count user messages after last assistant message
                    last_assistant_idx = -1
                    for i in range(len(messages) - 1, -1, -1):
                        msg = messages[i]
                        if isinstance(msg, dict) and msg.get("role") == "assistant":
                            last_assistant_idx = i
                            break

                    if last_assistant_idx >= 0:
                        unread_count = sum(
                            1
                            for msg in messages[last_assistant_idx + 1 :]
                            if isinstance(msg, dict) and msg.get("role") == "user"
                        )
                    else:
                        unread_count = len(messages)

                metadata = row["metadata"]
                if isinstance(metadata, str):
                    try:
                        metadata = json.loads(metadata)
                    except:
                        metadata = {}
                metadata = metadata or {}

                client_name = (
                    row["client_name"]
                    or metadata.get("client_name")
                    or metadata.get("sender_name")
                    or f"IG User {row['instagram_user_id']}"
                )

                conversations.append(
                    {
                        "id": row["id"],
                        "instagram_user_id": row["instagram_user_id"],
                        "username": metadata.get("username") or metadata.get("instagram_username"),
                        "client_id": row["client_id"],
                        "client_name": client_name,
                        "last_message": last_message,
                        "last_message_date": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "unread_count": unread_count,
                        "interaction_count": len(messages),
                    }
                )

            return conversations
    except Exception as e:
        logger.error(f"Failed to fetch Instagram conversations: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch conversations")


@router.get("/messages/{instagram_user_id}")
async def get_instagram_messages(
    instagram_user_id: str,
    limit: int = 100,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Get messages for a specific Instagram user.
    """
    try:
        user_id = f"instagram_{instagram_user_id}"
        session_id = f"ig_session_{instagram_user_id}"

        async with db.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, messages, metadata, created_at, created_at as updated_at
                FROM conversations
                WHERE user_id = $1 OR session_id = $2
                ORDER BY created_at DESC
                LIMIT 1
                """,
                user_id,
                session_id,
            )

            if not row:
                return []

            messages = row["messages"] or []
            result = []
            for i, msg in enumerate(messages[-limit:]):
                role = msg.get("role", "user")

                # Try to extract media info if it exists in message
                media_url = msg.get("media_url")
                media_type = msg.get("media_type")

                result.append(
                    {
                        "id": i,
                        "interaction_id": row["id"],
                        "instagram_user_id": instagram_user_id,
                        "message_text": msg.get("content", ""),
                        "direction": "inbound" if role == "user" else "outbound",
                        "timestamp": row["updated_at"].isoformat()
                        if row["updated_at"]
                        else row["created_at"].isoformat(),
                        "status": "read",
                        "media_url": media_url,
                        "media_type": media_type,
                    }
                )
            return result
    except Exception as e:
        logger.error(f"Failed to fetch Instagram messages for {instagram_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch messages")


@router.post("/send")
async def send_instagram_message(
    request: Request,
    db: Pool = Depends(get_database),
    current_user: dict = Depends(get_current_user),
):
    """
    Send Instagram message from omnichannel dashboard.
    Body: { "instagram_user_id": "12345", "text": "message" }
    """
    try:
        body = await request.json()
        recipient_id = body.get("instagram_user_id")
        text = body.get("text")

        if not recipient_id or not text:
            raise HTTPException(status_code=400, detail="Missing instagram_user_id or text")

        # Send via Instagram service
        await instagram_service.send_message(
            recipient_id=recipient_id,
            text=text,
        )

        # Save to conversation history
        user_id = f"instagram_{recipient_id}"
        session_id = f"ig_session_{recipient_id}"

        async with db.acquire() as conn:
            existing = await conn.fetchrow(
                "SELECT id, messages FROM conversations WHERE session_id = $1", session_id
            )

            new_msg = {"role": "assistant", "content": text}

            if existing:
                messages = existing["messages"] or []
                messages.append(new_msg)
                await conn.execute(
                    "UPDATE conversations SET messages = $1::jsonb WHERE id = $2",
                    json.dumps(messages),
                    existing["id"],
                )
            else:
                await conn.execute(
                    "INSERT INTO conversations (user_id, session_id, messages, created_at) VALUES ($1, $2, $3::jsonb, NOW())",
                    user_id,
                    session_id,
                    json.dumps([new_msg]),
                )

        return {"success": True}
    except Exception as e:
        logger.error(f"Failed to send Instagram message: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message")


async def notify_admin_error(
    sender_id: str,
    message_text: str,
    error: str,
):
    """
    Send Telegram notification to admin when Instagram processing fails.

    Args:
        sender_id: Instagram IGSID of the sender
        message_text: Original message content
        error: Error description
    """
    if not settings.admin_telegram_chat_id:
        logger.warning("Admin Telegram chat ID not configured, skipping error notification")
        return

    notification_text = f"""Instagram DM Error

From: IGSID {sender_id}
Error: {error}

Message:
{message_text[:500]}

---
Check backend logs for details.
"""

    try:
        await telegram_bot.send_message(
            chat_id=settings.admin_telegram_chat_id,
            text=notification_text,
            parse_mode="Markdown",
        )
        logger.info(f"Telegram error notification sent for Instagram message from {sender_id}")
    except Exception as e:
        logger.error(f"Failed to send Telegram error notification: {e}")


async def process_instagram_message(
    sender_id: str,
    message_text: str,
    message_id: str,
    request: Request,
):
    """
    Background task to process Instagram DM.

    This is executed async so webhook can return 200 immediately to Meta.

    Args:
        sender_id: Instagram IGSID of the sender
        message_text: Message content
        message_id: Instagram message ID
        request: FastAPI request (for dependencies)
    """
    try:
        # Mark message as seen
        await instagram_service.mark_message_seen(sender_id)

        # Process with Claude Direct + client profile (same pipeline as WhatsApp)
        from backend.app.dependencies import get_database
        from backend.llm.providers.anthropic_direct import anthropic_provider
        from backend.prompts.whatsapp_persona import build_system_prompt

        logger.info(f"Processing Instagram DM from {sender_id} with Claude Direct")

        ig_user_id = f"instagram_{sender_id}"
        session_id = f"ig_session_{sender_id}"

        start_time = time.time()

        try:
            # Load conversation history + client profile from PostgreSQL
            history = []
            client_profile = {}
            is_first_message = True
            existing_row_id = None

            try:
                db_pool = get_database(request)
                if db_pool:
                    async with db_pool.acquire() as conn:
                        row = await conn.fetchrow(
                            "SELECT id, messages, metadata FROM conversations WHERE user_id = $1 AND session_id = $2 ORDER BY created_at DESC LIMIT 1",
                            ig_user_id,
                            session_id,
                        )
                        if row:
                            existing_row_id = row["id"]
                            msgs = row["messages"]
                            if isinstance(msgs, str):
                                msgs = json.loads(msgs)
                            if msgs:
                                history = msgs[-MAX_HISTORY_MESSAGES:]
                                is_first_message = False
                            meta = row["metadata"]
                            if isinstance(meta, str):
                                meta = json.loads(meta)
                            if meta:
                                client_profile = meta
                            logger.info(
                                f"Loaded {len(history)} messages from DB for IG {sender_id}"
                            )
            except Exception as hist_err:
                logger.warning(f"Failed to load history for IG {sender_id}: {hist_err}")
                history = _conversation_cache.get(sender_id, [])[-MAX_HISTORY_MESSAGES:]

            # Build/update client profile incrementally
            if not client_profile.get("channel"):
                client_profile["channel"] = "instagram"
            if not client_profile.get("sender_id"):
                client_profile["sender_id"] = sender_id
            if not client_profile.get("first_contact"):
                client_profile["first_contact"] = datetime.now(timezone.utc).isoformat()

            detected_language = detect_language(message_text, history)
            client_profile["detected_language"] = detected_language
            client_profile["message_count"] = client_profile.get("message_count", 0) + 1

            new_visas = extract_visa_mentions(message_text)
            existing_visas = set(client_profile.get("visa_discussed", []))
            existing_visas.update(new_visas)
            if existing_visas:
                client_profile["visa_discussed"] = sorted(existing_visas)

            new_interests = extract_interests(message_text)
            existing_interests = set(client_profile.get("interests", []))
            existing_interests.update(new_interests)
            if existing_interests:
                client_profile["interests"] = sorted(existing_interests)

            client_profile["client_type"] = infer_client_type(client_profile)

            # Build dynamic system prompt with client context
            system_prompt = build_system_prompt(
                client_name=None,  # Instagram doesn't provide sender name
                client_profile=client_profile,
                is_first_message=is_first_message,
                detected_language=detected_language,
                time_of_day=get_time_of_day(),
            )

            messages = history + [{"role": "user", "content": message_text}]

            response_text = await anthropic_provider.generate(
                system_prompt=system_prompt,
                messages=messages,
                temperature=0.7,
                max_tokens=512,
            )

            if not response_text:
                response_text = "Sorry, something went wrong. Please try again!"

            # Split into chunks for Instagram's 1000 char limit
            chunks = instagram_service.chunk_message(response_text, max_length=950)

            for i, chunk in enumerate(chunks):
                await instagram_service.send_message(
                    recipient_id=sender_id,
                    text=chunk,
                )
                if i < len(chunks) - 1:
                    await asyncio.sleep(0.5)

            # Save conversation + client profile to PostgreSQL
            try:
                db_pool = get_database(request)
                if db_pool:
                    conversation_msgs = [
                        {"role": "user", "content": message_text},
                        {"role": "assistant", "content": response_text},
                    ]
                    async with db_pool.acquire() as conn:
                        if existing_row_id:
                            old_msgs = history  # Already loaded above
                            all_msgs = old_msgs + conversation_msgs
                            all_msgs = all_msgs[-MAX_HISTORY_MESSAGES:]
                            await conn.execute(
                                "UPDATE conversations SET messages = $1::jsonb, metadata = $2::jsonb WHERE id = $3",
                                json.dumps(all_msgs),
                                json.dumps(client_profile),
                                existing_row_id,
                            )
                        else:
                            await conn.execute(
                                "INSERT INTO conversations (user_id, session_id, messages, metadata, created_at) VALUES ($1, $2, $3::jsonb, $4::jsonb, NOW())",
                                ig_user_id,
                                session_id,
                                json.dumps(conversation_msgs),
                                json.dumps(client_profile),
                            )
                    logger.info(
                        f"Conversation + profile saved for IG {sender_id} (session: {session_id})"
                    )
            except Exception as save_err:
                logger.warning(f"Failed to save conversation for IG {sender_id}: {save_err}")

            # Also keep in-memory cache as fast fallback
            _conversation_cache[sender_id].append({"role": "user", "content": message_text})
            _conversation_cache[sender_id].append({"role": "assistant", "content": response_text})
            if len(_conversation_cache[sender_id]) > MAX_HISTORY_MESSAGES:
                _conversation_cache[sender_id] = _conversation_cache[sender_id][
                    -MAX_HISTORY_MESSAGES:
                ]

            total_duration = time.time() - start_time
            logger.info(
                f"Zantara responded to IG {sender_id} in {total_duration:.1f}s ({len(response_text)} chars, lang={detected_language})"
            )

        except asyncio.TimeoutError:
            await instagram_service.send_message(
                recipient_id=sender_id,
                text="Hold on, I'm taking too long. Please try again shortly!",
            )

    except Exception as e:
        logger.error(f"Error processing Instagram message from {sender_id}: {e}", exc_info=True)

        # Send error message to user
        try:
            await instagram_service.send_message(
                recipient_id=sender_id,
                text="Oops, technical error. Please try again in a moment!",
            )
        except Exception as send_error:
            logger.error(f"Failed to send Instagram error message: {send_error}")

        # Notify admin via Telegram
        await notify_admin_error(
            sender_id=sender_id,
            message_text=message_text,
            error=str(e),
        )


@router.get("")
async def verify_webhook(request: Request):
    """
    Verify webhook for Meta Instagram setup.

    Meta sends GET request with hub.mode, hub.verify_token, hub.challenge.
    We must return hub.challenge if verify_token matches.
    """
    params = request.query_params

    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info(f"Instagram webhook verification: mode={mode}, token={'***' if token else None}")

    if mode == "subscribe" and token == settings.instagram_verify_token:
        logger.info("Instagram webhook verification successful")
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning("Instagram webhook verification failed: invalid token or mode")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@router.post("")
async def instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Handle incoming Instagram DMs.

    Meta sends POST requests with message events.
    We process in background and return 200 immediately.

    Instagram webhook payload structure:
    {
      "object": "instagram",
      "entry": [{
        "id": "<PAGE_ID>",
        "time": 1234567890,
        "messaging": [{
          "sender": {"id": "<IGSID>"},
          "recipient": {"id": "<PAGE_ID>"},
          "timestamp": 1234567890,
          "message": {
            "mid": "<MESSAGE_ID>",
            "text": "Hello!"
          }
        }]
      }]
    }
    """
    body: dict[str, Any] = await request.json()

    obj = body.get("object")
    if obj != "instagram":
        logger.debug(f"Ignoring non-instagram webhook object: {obj}")
        return {"status": "ok"}

    entries = body.get("entry", [])
    logger.info(f"Instagram webhook received: {len(entries)} entries")

    for entry in entries:
        messaging_events = entry.get("messaging", [])

        # Instagram Business API may use changes[] format instead of messaging[]
        if not messaging_events:
            changes = entry.get("changes", [])
            for change in changes:
                if change.get("field") == "messages" and isinstance(change.get("value"), dict):
                    messaging_events.append(change["value"])

        for event in messaging_events:
            sender = event.get("sender", {})
            sender_id = sender.get("id")
            message = event.get("message", {})
            message_id = message.get("mid")
            text = message.get("text")

            # Skip non-text messages (stickers, images, etc.)
            if not text:
                logger.debug(f"Ignoring non-text Instagram message from {sender_id}")
                continue

            # Skip echo messages (sent by us)
            if message.get("is_echo"):
                logger.debug(f"Ignoring echo message {message_id}")
                continue

            logger.info(f"Instagram DM from {sender_id}: mid={message_id}, len={len(text)}")

            background_tasks.add_task(
                process_instagram_message,
                sender_id=sender_id,
                message_text=text,
                message_id=message_id,
                request=request,
            )

            logger.info(f"Instagram message from {sender_id} scheduled for processing")

    return {"status": "ok"}


@router.get("/status")
async def instagram_status():
    """
    Check Instagram integration status.

    Public endpoint for health monitoring and frontend display.
    """
    configured = bool(settings.instagram_access_token and settings.instagram_account_id)

    return {
        "configured": configured,
        "account_id": settings.instagram_account_id if configured else None,
    }


@router.get("/profile")
async def instagram_profile():
    """
    Get connected Instagram account profile info.

    Public endpoint for frontend to display connected account details.
    Returns username, profile picture, and follower count.
    """
    if not settings.instagram_access_token:
        raise HTTPException(status_code=503, detail="Instagram not configured")

    try:
        profile = await instagram_service.get_profile()
        return profile
    except ValueError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to get Instagram profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve Instagram profile")
