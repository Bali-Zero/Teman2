"""Telegram CRITICAL alerts for GARUDA system."""
import logging
import os

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"


async def send_critical_alert(message: str) -> None:
    """Send CRITICAL alert to Telegram owner chat. Never raises — log and swallow on failure."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_OWNER_CHAT_ID", "1125336968")

    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — cannot send alert: %s", message)
        return

    url = TELEGRAM_API_URL.format(token=token)
    payload = {
        "chat_id": chat_id,
        "text": f"🚨 GARUDA CRITICAL\n\n{message}",
        "parse_mode": "HTML",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            if response.status_code != 200:
                logger.error("Telegram alert failed: %s %s", response.status_code, response.text)
    except Exception as e:
        logger.error("Failed to send Telegram alert: %s", e)
        # Never raise — alerts should never crash the indexer
