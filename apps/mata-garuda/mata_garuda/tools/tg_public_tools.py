"""
Mata Garuda — Telegram Public Channel tools.

Wrapper per invio a canale pubblico Bali Zero (clienti), distinto dal
tg_tools.py che invia al chat privato di Zero.

Safe default: se TELEGRAM_PUBLIC_CHANNEL_ID non è configurato, modalità
DRY-RUN (logga ma non invia). Richiede azione Zero per abilitare pubblicazione
reale (creare canale TG + configurare env).

CLI-only: no python-telegram-bot dependency.
"""
from __future__ import annotations

import logging
import os
import subprocess

from mata_garuda.config import TG_BOT_TOKEN_ENV
from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools.tg_public")

TG_PUBLIC_CHANNEL_ENV = "TELEGRAM_PUBLIC_CHANNEL_ID"


def _get_bot_token() -> str | None:
    return os.environ.get(TG_BOT_TOKEN_ENV)


def _get_public_channel_id() -> str | None:
    raw = os.environ.get(TG_PUBLIC_CHANNEL_ENV)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def is_public_channel_configured() -> bool:
    """True iff both bot token and public channel id are available."""
    return bool(_get_bot_token()) and bool(_get_public_channel_id())


@register_tool(name="send_tg_public_post")
def send_tg_public_post(
    message: str,
    context_variables: dict | None = None,
) -> str:
    """Send a post to the Bali Zero public TG channel.

    Dry-run safe: if TELEGRAM_PUBLIC_CHANNEL_ID is not configured, logs the
    would-be post and returns a DRY-RUN status instead of failing. Real
    publishing requires Zero to create the channel and set the env var.

    Args:
        message: Post text (Markdown supported)
    """
    token = _get_bot_token()
    channel = _get_public_channel_id()

    if not token:
        return f"[ERROR] {TG_BOT_TOKEN_ENV} not set in environment"

    if not channel:
        logger.info(
            "[tg-public DRY-RUN] would post to public channel: %s",
            message[:120],
        )
        return (
            "[DRY-RUN] TELEGRAM_PUBLIC_CHANNEL_ID not configured — "
            "logged instead of sent. Zero must create channel + set env."
        )

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    try:
        result = subprocess.run(
            [
                "curl", "-sL", "-X", "POST", url,
                "-d", f"chat_id={channel}",
                "--data-urlencode", f"text={message}",
                "-d", "parse_mode=Markdown",
                "-d", "disable_web_page_preview=false",
                "--connect-timeout", "10",
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if '"ok":true' in result.stdout:
            logger.info("[tg-public] Sent to %s: %s", channel, message[:80])
            return f"[SUCCESS] Posted to public channel {channel}"
        return f"[ERROR] TG API response: {result.stdout[:200]}"
    except subprocess.TimeoutExpired:
        return "[ERROR] TG API timeout"
    except Exception as e:  # noqa: BLE001
        return f"[ERROR] TG public send failed: {e}"
