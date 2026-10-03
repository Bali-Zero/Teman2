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

from mata_garuda.config import TG_BOT_TOKEN_ENV
from mata_garuda.registry import register_tool
from mata_garuda.tools.tg_tools import curl_send

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

    ok, reason = curl_send(
        token, channel, message,
        extra_fields={"parse_mode": "Markdown", "disable_web_page_preview": "false"},
    )
    if ok:
        logger.info("[tg-public] Sent to %s: %s", channel, message[:80])
        return f"[SUCCESS] Posted to public channel {channel}"
    return f"[ERROR] TG public send failed: {reason}"
