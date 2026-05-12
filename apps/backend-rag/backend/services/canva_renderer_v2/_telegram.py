"""Best-effort Telegram notify. Failures are swallowed (no raise).

Reads TELEGRAM_BOT_TOKEN + TELEGRAM_OWNER_CHAT_ID env vars.
If TELEGRAM_BOT_TOKEN absent, silently no-op.
"""
from __future__ import annotations

import logging
import os
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)


def send_telegram(text: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_OWNER_CHAT_ID", "1125336968")
    if not token:
        return
    try:
        data = urllib.parse.urlencode(
            {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(  # noqa: S310 — known URL
            f"https://api.telegram.org/bot{token}/sendMessage",
            data,
            timeout=10,
        )
    except Exception as e:  # noqa: BLE001 — best-effort
        logger.warning("Telegram send failed (swallowed): %s", e)
