"""
Mata Garuda — Telegram tools via curl subprocess.

Send alerts and digests to Zero's private TG chat.
CLI-only: no python-telegram-bot dependency.
"""
from __future__ import annotations

import logging
import os
import subprocess

from mata_garuda.config import TG_BOT_TOKEN_ENV, TG_ZERO_CHAT_ID
from mata_garuda.registry import register_tool

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

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        result = subprocess.run(
            [
                "curl", "-sL", "-X", "POST", url,
                "-d", f"chat_id={TG_ZERO_CHAT_ID}",
                "-d", f"text={message}",
                "-d", "parse_mode=Markdown",
                "--connect-timeout", "10",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if '"ok":true' in result.stdout:
            logger.info(f"[tg] Alert sent to Zero: {message[:60]}...")
            return "[SUCCESS] Alert sent to Zero"
        else:
            return f"[ERROR] TG API response: {result.stdout[:200]}"
    except subprocess.TimeoutExpired:
        return "[ERROR] TG API timeout"
    except Exception as e:
        return f"[ERROR] TG send failed: {e}"
