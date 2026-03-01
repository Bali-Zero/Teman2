"""
Telegram Webhook Router - Multi-Channel Architecture.

Handles incoming Telegram Bot API updates using ChannelRouter.

Author: Claude Sonnet 4.5
Date: 2026-02-10
"""

import logging
import os

from fastapi import APIRouter, Depends, Request

from backend.app.dependencies import get_channel_router
from backend.channels.router import ChannelRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["telegram"])


@router.post("/telegram")
async def telegram_webhook(
    request: Request,
    channel_router: ChannelRouter = Depends(get_channel_router),


) -> dict[str, Any]:
    """
    Telegram Bot API webhook endpoint.

    Receives updates from Telegram and routes them through the multi-channel architecture.

    Expected update structure:
    {
        "update_id": 12345,
        "message": {
            "message_id": 789,
            "from": {"id": 123, "first_name": "John", "username": "john_doe"},
            "chat": {"id": 123, "type": "private"},
            "date": 1234567890,
            "text": "Hello bot!"
        }
    }

    Returns:
        Success confirmation (Telegram expects 200 OK)
    """
    try:
        # Parse request body
        update = await request.json()

        # Validate update_id
        update_id = update.get("update_id")
        if not update_id:
            logger.warning("Received Telegram update without update_id")
            return {"ok": False, "error": "Missing update_id"}

        # Log incoming update
        message = update.get("message", {})
        chat = message.get("chat", {})
        chat_id = chat.get("id")
        text = message.get("text", "")

        logger.info(f"📨 Telegram update {update_id}: chat_id={chat_id}, text={text[:50]}...")

        # Route message through ChannelRouter
        await channel_router.route_message("telegram", update)

        # Return 200 OK (Telegram requires this)
        return {"ok": True, "update_id": update_id}

    except Exception as e:
        logger.error(f"Failed to process Telegram webhook: {e}", exc_info=True)

        # Return 200 OK even on error (to prevent Telegram from retrying)
        # Telegram will retry if we return 500, which can cause duplicates
        return {"ok": False, "error": str(e)}


@router.get("/telegram/health")
async def telegram_health() -> dict[str, Any]:
    """Health check for Telegram webhook."""
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")

    return {
        "status": "healthy",
        "channel": "telegram",
        "webhook_configured": bool(telegram_token),
    }
