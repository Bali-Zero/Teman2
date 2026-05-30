"""OpenClaw bridge client for Meta WhatsApp replies."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.app.core.config import settings

logger = logging.getLogger(__name__)


def _normalize_bridge_url(url: str) -> str:
    """Return the bridge URL without duplicate trailing slashes."""
    return url.rstrip("/")


def _bridge_secret() -> str | None:
    """Return the WhatsApp bridge secret, with legacy fallback."""
    return settings.whatsapp_openclaw_bridge_secret or settings.openclaw_webhook_secret


def is_openclaw_whatsapp_configured() -> bool:
    """Return True when the WhatsApp OpenClaw bridge can be called."""
    return bool(settings.whatsapp_openclaw_bridge_url and _bridge_secret())


async def ask_openclaw_whatsapp(
    *,
    phone: str,
    message_text: str,
    sender_name: str | None,
    message_id: str,
    context: dict[str, Any] | None = None,
) -> str | None:
    """Ask the local OpenClaw WhatsApp bridge for a reply.

    Returns None when the bridge is not configured, rejects the request, or
    returns no usable reply. The caller should then continue with its normal
    fallback path.
    """
    if not is_openclaw_whatsapp_configured():
        return None

    bridge_url = _normalize_bridge_url(str(settings.whatsapp_openclaw_bridge_url))
    secret = str(_bridge_secret())
    timeout_seconds = max(float(settings.whatsapp_openclaw_timeout_seconds or 90.0), 1.0)
    payload: dict[str, Any] = {
        "agent": settings.whatsapp_openclaw_agent or "wa",
        "model": settings.whatsapp_openclaw_model,
        "thinking": settings.whatsapp_openclaw_thinking,
        "persona": settings.whatsapp_openclaw_persona,
        "autonomy_mode": settings.whatsapp_openclaw_autonomy_mode,
        "channel": "whatsapp",
        "phone": phone,
        "sender_name": sender_name,
        "message_id": message_id,
        "text": message_text,
        "context": context or {},
    }
    headers = {
        "Authorization": f"Bearer {secret}",
        "X-OpenClaw-Webhook-Secret": secret,
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout_seconds, connect=10.0)) as client:
            response = await client.post(bridge_url, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("OpenClaw WhatsApp bridge call failed: %s", exc)
        return None

    if response.status_code >= 400:
        logger.warning(
            "OpenClaw WhatsApp bridge rejected request: status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        return None

    try:
        body = response.json()
    except ValueError:
        logger.warning("OpenClaw WhatsApp bridge returned non-JSON response")
        return None

    reply = body.get("reply") or body.get("text") or body.get("message")
    if not isinstance(reply, str):
        logger.warning("OpenClaw WhatsApp bridge response had no text reply")
        return None

    reply = reply.strip()
    return reply or None
