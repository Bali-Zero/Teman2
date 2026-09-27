"""
Mata Garuda — Telegram tools via curl subprocess.

Send alerts and digests to Zero's private TG chat.
CLI-only: no python-telegram-bot dependency.
"""
from __future__ import annotations

import logging
import os

from mata_garuda.config import TG_BOT_TOKEN_ENV, TG_ZERO_CHAT_ID
from mata_garuda.registry import register_tool
from mata_garuda.tg_curl import curl_send

logger = logging.getLogger("mata_garuda.tools")


def _get_bot_token() -> str | None:
    """Get bot token from environment."""
    return os.environ.get(TG_BOT_TOKEN_ENV)


@register_tool(name="send_tg_alert")
def send_tg_alert(
    message: str,
    context_variables: dict | None = None,
) -> str:
    """Send a Telegram message to Zero's private chat.

    Args:
        message: Message text (Markdown supported)
    """
    token = _get_bot_token()
    if not token:
        return f"[ERROR] {TG_BOT_TOKEN_ENV} not set in environment"

    ok, reason = curl_send(token, TG_ZERO_CHAT_ID, message, extra_fields={"parse_mode": "Markdown"})
    if ok:
        logger.info(f"[tg] Alert sent to Zero: {message[:60]}...")
        return "[SUCCESS] Alert sent to Zero"
    return f"[ERROR] TG send failed: {reason}"
