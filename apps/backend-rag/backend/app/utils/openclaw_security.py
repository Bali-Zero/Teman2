"""
NUZANTARA PRIME - OpenClaw Webhook Security
HMAC signature verification for OpenClaw webhooks
"""

import hashlib
import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request

from backend.app.core.config import settings


async def verify_openclaw_signature(
    request: Request,
    x_openclaw_signature: Annotated[str | None, Header()] = None,
) -> None:
    """
    Verify OpenClaw webhook signature using HMAC SHA256.

    Args:
        request: FastAPI request object to access raw body
        x_openclaw_signature: Signature from X-OpenClaw-Signature header

    Raises:
        HTTPException: 401 if signature is missing or invalid
    """
    if not settings.openclaw_webhook_secret:
        raise HTTPException(
            status_code=500,
            detail="OpenClaw webhook secret not configured. Set OPENCLAW_WEBHOOK_SECRET env var.",
        )

    if not x_openclaw_signature:
        raise HTTPException(
            status_code=401,
            detail="Missing X-OpenClaw-Signature header",
        )

    # Get raw request body
    body = await request.body()

    # Calculate expected signature
    expected_signature = hmac.new(
        key=settings.openclaw_webhook_secret.encode("utf-8"),
        msg=body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    # Secure comparison to prevent timing attacks
    if not hmac.compare_digest(expected_signature, x_openclaw_signature):
        raise HTTPException(
            status_code=401,
            detail="Invalid webhook signature",
        )
