"""X/Twitter Webhook Router — Account Activity API."""

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/twitter", tags=["twitter"])

# Webhook router for Account Activity API
webhook_router = APIRouter(prefix="/webhook/twitter", tags=["twitter"])


def _compute_crc_response(crc_token: str, consumer_secret: str) -> str:
    """Compute HMAC-SHA256 CRC response token for X webhook verification.

    Args:
        crc_token: The CRC token from Twitter's challenge request.
        consumer_secret: The app's consumer secret (API Secret Key).

    Returns:
        The response token in format ``sha256=BASE64HASH``.
    """
    sha256_hash = hmac.new(
        consumer_secret.encode("utf-8"),
        crc_token.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return f"sha256={base64.b64encode(sha256_hash).decode('ascii')}"


def _verify_webhook_signature(
    payload_body: bytes, signature_header: str | None, consumer_secret: str
) -> bool:
    """Verify the X-Twitter-Webhooks-Signature header on POST requests.

    Args:
        payload_body: Raw request body bytes.
        signature_header: Value of X-Twitter-Webhooks-Signature header.
        consumer_secret: The app's consumer secret.

    Returns:
        True if signature is valid, False otherwise.
    """
    if not signature_header:
        return False
    expected = _compute_crc_response(
        payload_body.decode("utf-8", errors="replace"), consumer_secret
    )
    return hmac.compare_digest(f"sha256={signature_header.removeprefix('sha256=')}", expected)


@router.get("/conversations")
async def get_tw_convs() -> list:
    return []


@router.get("/messages/{user_id}")
async def get_tw_msgs(user_id: str) -> list:
    return []


@webhook_router.get("")
async def verify_twitter_webhook(request: Request) -> JSONResponse:
    """CRC challenge for X Account Activity API registration.

    Twitter sends GET with ``?crc_token=TOKEN``.  We must respond within 3 s
    with ``{"response_token": "sha256=<HMAC-SHA256(crc_token, consumer_secret)>"}``
    and Content-Type: application/json.
    """
    crc_token = request.query_params.get("crc_token")
    if not crc_token:
        logger.warning("X CRC challenge: missing crc_token param")
        return JSONResponse({"error": "missing crc_token"}, status_code=400)

    consumer_secret = settings.x_consumer_secret
    if not consumer_secret:
        logger.error("X CRC challenge: X_CONSUMER_SECRET not configured")
        return JSONResponse({"error": "server misconfigured"}, status_code=500)

    response_token = _compute_crc_response(crc_token, consumer_secret)
    logger.info("X CRC challenge verified successfully")
    return JSONResponse({"response_token": response_token}, status_code=200)


@webhook_router.post("")
async def twitter_webhook(request: Request) -> dict:
    """Handle incoming X/Twitter DMs via Account Activity API."""
    # Verify webhook signature if consumer_secret is configured
    if settings.x_consumer_secret:
        body = await request.body()
        signature = request.headers.get("X-Twitter-Webhooks-Signature")
        if not _verify_webhook_signature(body, signature, settings.x_consumer_secret):
            logger.warning("X webhook: invalid signature — rejecting request")
            return {"status": "error", "detail": "invalid signature"}

    try:
        raw_payload = await request.json()
    except Exception:
        return {"status": "ok"}

    # Only process direct_message_events
    dm_events = raw_payload.get("direct_message_events", [])
    if not dm_events:
        return {"status": "ok"}

    # for_user_id identifies our bot account in the webhook payload
    bot_user_id = raw_payload.get("for_user_id", "")

    # Filter out echo messages (sent by our own bot account)
    has_inbound = False
    for dm in dm_events:
        msg_create = dm.get("message_create", {})
        sender_id = msg_create.get("sender_id", "")
        target_recipient = msg_create.get("target", {}).get("recipient_id", "")
        text_len = len(msg_create.get("message_data", {}).get("text", ""))

        logger.info(
            "X DM received: sender=%s, recipient=%s, text_len=%d, bot_id=%s",
            sender_id,
            target_recipient,
            text_len,
            bot_user_id,
        )

        # Skip messages sent by our own bot account
        if sender_id and sender_id == bot_user_id:
            logger.info("X DM: skipping echo (sent by bot)")
            continue
        if text_len > 0:
            has_inbound = True

    if not has_inbound:
        logger.info("X DM: no inbound messages to process")
        return {"status": "ok"}

    try:
        from backend.app.dependencies import get_channel_router

        channel_router = get_channel_router(request)
        await channel_router.route_message("twitter", raw_payload)

        return {"status": "ok"}
    except Exception as e:
        logger.error("Failed to route X DM: %s", e)
        return {"status": "error", "detail": str(e)}
