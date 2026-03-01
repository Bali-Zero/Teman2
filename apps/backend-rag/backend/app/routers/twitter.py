"""X/Twitter Webhook Router — Account Activity API."""

import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

from backend.app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/twitter", tags=["twitter"])

# Webhook router for Account Activity API
webhook_router = APIRouter(prefix="/webhook/twitter", tags=["twitter"])


@router.get("/conversations")
async def get_tw_convs() -> list:
    return []


@router.get("/messages/{user_id}")
async def get_tw_msgs(user_id: str) -> list:
    return []


@webhook_router.get("")
async def verify_twitter_webhook(request: Request) -> PlainTextResponse:
    """CRC challenge for X Account Activity API registration."""
    crc_token = request.query_params.get("crc_token")
    if not crc_token or not settings.x_consumer_secret:
        logger.warning("X CRC challenge failed: missing crc_token or consumer_secret")
        return PlainTextResponse("Missing parameters", status_code=400)

    import base64

    sha256_hash = hmac.new(
        settings.x_consumer_secret.encode(),
        crc_token.encode(),
        hashlib.sha256,
    ).digest()
    response_token = f"sha256={base64.b64encode(sha256_hash).decode()}"

    logger.info("✅ X CRC challenge verified")
    return PlainTextResponse(
        content=json.dumps({"response_token": response_token}),
        status_code=200,
        media_type="application/json",
    )


@webhook_router.post("")
async def twitter_webhook(request: Request) -> dict:
    """Handle incoming X/Twitter DMs via Account Activity API."""
    try:
        raw_payload = await request.json()
    except Exception:
        return {"status": "ok"}

    # Only process direct_message_events
    dm_events = raw_payload.get("direct_message_events", [])
    if not dm_events:
        return {"status": "ok"}

    # Skip messages sent by our own account (echoes)
    for dm in dm_events:
        msg_create = dm.get("message_create", {})
        sender_id = msg_create.get("sender_id", "")
        # If sender is our bot account, skip
        target_recipient = msg_create.get("target", {}).get("recipient_id", "")

        logger.info(
            f"X DM received: sender={sender_id}, recipient={target_recipient}, "
            f"text_len={len(msg_create.get('message_data', {}).get('text', ''))}"
        )

    try:
        from backend.app.dependencies import get_channel_router

        channel_router = get_channel_router(request)
        await channel_router.route_message("twitter", raw_payload)

        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to route X DM: {e}")
        return {"status": "error", "detail": str(e)}
