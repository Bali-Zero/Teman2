"""
Instagram Conversations API - Ultra-Safe Version
"""

import json
import logging
from typing import Any

from asyncpg import Pool
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from backend.app.core.config import settings
from backend.app.dependencies import get_database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/instagram", tags=["instagram"])


# Instagram Webhook Models (Meta Standard — lenient to accept all event types)
class InstagramMessage(BaseModel):
    mid: str = ""
    text: str = ""
    is_echo: bool = False


class InstagramMessaging(BaseModel):
    sender: dict[str, str]
    recipient: dict[str, str]
    timestamp: int
    message: InstagramMessage | None = None
    read: dict | None = None
    delivery: dict | None = None


class InstagramEntry(BaseModel):
    id: str
    time: int
    messaging: list[InstagramMessaging]


class InstagramWebhook(BaseModel):
    object: str
    entry: list[InstagramEntry]


@router.get("/conversations")
async def get_instagram_conversations(
    limit: int = 50, offset: int = 0, db: Pool = Depends(get_database),
) -> Any:
    try:
        async with db.acquire() as conn:
            rows = await conn.fetch(
                "SELECT id, session_id, user_id, messages, metadata, created_at FROM conversations "
                "WHERE session_id LIKE 'ig_session_%' OR user_id LIKE 'instagram_%' "
                "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit,
                offset,
            )
            conversations = []
            for row in rows:
                session_id = row["session_id"] or ""
                user_id = session_id.replace("ig_session_", "")

                messages_raw = row["messages"]
                last_msg_text = "Click to view Instagram messages"
                try:
                    msgs = (
                        json.loads(messages_raw) if isinstance(messages_raw, str) else messages_raw
                    )
                    if msgs and isinstance(msgs, list):
                        last_msg_text = msgs[-1].get("content", "")[:100]
                except Exception as e:
                    logger.error(f"Failed to parse Instagram messages: {e}")
                    pass

                metadata_raw = row["metadata"]
                client_name = f"IG: {user_id}"
                try:
                    meta = (
                        json.loads(metadata_raw) if isinstance(metadata_raw, str) else metadata_raw
                    )
                    client_name = meta.get("sender_name") or meta.get("client_name") or client_name
                except Exception as e:
                    logger.error(f"Failed to parse Instagram metadata: {e}")
                    pass

                conversations.append(
                    {
                        "id": row["id"],
                        "user_id": user_id,
                        "client_name": client_name,
                        "last_message": last_msg_text,
                        "last_message_date": row["created_at"].isoformat(),
                        "session_id": session_id,
                    },
                )
            return conversations
    except Exception as e:
        logger.error(f"IG FAIL: {e}")
        return []


@router.get("/messages/{user_id}")
async def get_instagram_messages(
    user_id: str, limit: int = 100, db: Pool = Depends(get_database),
) -> Any:

    try:
        async with db.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT id, messages, created_at FROM conversations WHERE session_id = $1 ORDER BY created_at DESC LIMIT 1",
                f"ig_session_{user_id}",
            )
            if not row:
                return []
            msgs = (
                json.loads(row["messages"]) if isinstance(row["messages"], str) else row["messages"]
            )
            result = []
            for i, m in enumerate(msgs[-limit:]):
                if not isinstance(m, dict):
                    continue
                result.append(
                    {
                        "id": f"{row['id']}_{i}",
                        "message_text": m.get("content", ""),
                        "direction": "inbound" if m.get("role") == "user" else "outbound",
                        "timestamp": row["created_at"].isoformat(),
                    },
                )
            return result
    except Exception as e:
        logger.error(f"Failed to get Instagram messages: {e}")
        return []


# ============================================================
# INSTAGRAM WEBHOOK ROUTER
# ============================================================
webhook_router = APIRouter(prefix="/webhook/instagram", tags=["instagram"])


@webhook_router.get("")
async def verify_instagram_webhook(request: Request) -> PlainTextResponse:
    """Verify Instagram webhook for Meta setup."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge")

    logger.info(f"IG Webhook verify: mode={mode}, token={'***' if token else None}")

    if mode == "subscribe" and token == settings.instagram_verify_token:
        logger.info("✅ IG Webhook verified")
        return PlainTextResponse(content=challenge, status_code=200)

    logger.warning("❌ IG Webhook verify failed")
    raise HTTPException(status_code=403, detail="Invalid verify token")


@webhook_router.post("")
async def instagram_webhook(request: Request) -> dict[str, Any]:
    """Handle incoming Instagram DMs via ChannelRouter."""
    try:
        raw_payload = await request.json()
        webhook = InstagramWebhook(**raw_payload)
    except Exception:
        return {"status": "ok"}

    obj = webhook.object
    entries = webhook.entry
    logger.info(f"IG Webhook received: {obj}, {len(entries)} entries")

    # Only process actual messages (skip read receipts, delivery, echoes)
    has_message = False
    for entry in entries:
        for messaging in entry.messaging:
            msg = messaging.message
            if msg and msg.text and not msg.is_echo:
                has_message = True
                break

    if not has_message:
        logger.info("IG Webhook: no text message found, skipping")
        return {"status": "ok"}

    for entry in webhook.entry:
        for messaging in entry.messaging:
            # Filter read receipts and delivery confirmations
            if messaging.message is None:
                logger.info("IG Webhook: skipping non-message event (read/delivery)")
                return {"status": "ok"}

            # Filter echo messages (sent by the bot itself)
            if messaging.message.is_echo:
                logger.info("IG Webhook: skipping echo message")
                return {"status": "ok"}

            # Filter messages without text (reactions, attachments-only, etc.)
            if not messaging.message.text:
                logger.info("IG Webhook: skipping non-text message")
                return {"status": "ok"}

    try:
        from backend.app.dependencies import get_channel_router

        channel_router = get_channel_router(request)
        await channel_router.route_message("instagram", raw_payload)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to route IG message: {e}")
        return {"status": "error", "detail": str(e)}
