"""Tiny Telegram sender with no external deps.

Uses urllib stdlib. Returns bool (success). Never raises -- caller decides
how to handle a failed send (see spec §7.2).
"""
from __future__ import annotations

import logging
import urllib.parse
import urllib.request

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_S = 5


def send_telegram(
    bot_token: str,
    chat_id: str,
    text: str,
    timeout: int = DEFAULT_TIMEOUT_S,
) -> bool:
    """POST to Telegram bot API. Returns True on 2xx response, False otherwise."""
    if not bot_token or not chat_id:
        logger.warning("telegram_send: empty bot_token or chat_id, skipping")
        return False
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": text, "disable_web_page_preview": "true"}
    ).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            if 200 <= status < 300:
                return True
            logger.warning("telegram_send: non-2xx status %s", status)
            return False
    except Exception as e:
        logger.warning("telegram_send: %s", e)
        return False
