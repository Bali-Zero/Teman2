"""
Mata Garuda — Telegram tools via curl subprocess.

Send alerts and digests to Zero's private TG chat.
CLI-only: no python-telegram-bot dependency.

`curl_send` (below) is the ONE curl-based Telegram sender for the whole
mata-garuda app — every other agent/tool imports it from here rather than
building its own curl argv. This file was already grandfathered by
scripts/lint_tg_direct_senders.py (it always built the URL directly), so
centralizing the sender here needs no lint/allowlist change: the direct
senders it replaces literally stop existing (see the sibling
research_sentinel.py-style prune), and this file's own grandfathered entry
already covers the one place the URL is still built.

`curl_send` was extracted 2026-09-27 out of `daily_briefing_agent.py` and
`regulation_alert_agent.py`, which each had their own copy of the same bug:
curl's argv carried `f"https://api.telegram.org/bot{token}/sendMessage"` as a
literal, and a broad `except Exception as e: logger.error(f"...: {e}")`
around the subprocess call. A `subprocess.TimeoutExpired`'s own `str()`
embeds the full argv it was constructed with, so a slow curl — no HTTP
round-trip needed — put the token in daily-briefing.error.log (2026-09-26)
and, 48x more often on its 30-minute schedule, in reg-alert.error.log. The
token now goes into a private `-K` config file (0600, unlinked in `finally`)
instead of the URL literal, so it is absent from argv entirely — closing the
exception-string leak and the `ps`/`/proc` argv exposure at once.
`mask_tg_token` is a second, independent net over any text a caller still
logs.
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile

from mata_garuda.config import TG_BOT_TOKEN_ENV, TG_ZERO_CHAT_ID, mask_tg_token
from mata_garuda.registry import register_tool

logger = logging.getLogger("mata_garuda.tools")

CREDENTIAL_REJECTED_STATUSES = frozenset({"401", "403"})


def curl_send(
    token: str,
    chat_id: str,
    text: str,
    *,
    timeout: float = 15,
    extra_fields: dict[str, str] | None = None,
) -> tuple[bool, str]:
    """POST one sendMessage via curl. Never raises.

    ``extra_fields`` adds plain ``-d`` fields (e.g. ``{"parse_mode": "Markdown"}``)
    — callers relying on Telegram options beyond chat_id/text keep that
    behavior instead of silently losing it.

    Returns ``(ok, reason)`` — ``reason`` is ``""`` on success,
    ``"credential_rejected (<code>)"`` on 401/403 (judged by status code, never
    by a substring of Telegram's free-text body — same shape as backend-rag's
    ``CREDENTIAL_REJECTED_STATUSES``), or a token-masked failure body/exception
    string otherwise.
    """
    cfg_path: str | None = None
    try:
        cfg_fd, cfg_path = tempfile.mkstemp(prefix="tg-send-", suffix=".curlcfg")
        # mkstemp already creates the file 0600 (POSIX) — no separate chmod needed.
        with os.fdopen(cfg_fd, "w") as fh:
            fh.write(f'url = "https://api.telegram.org/bot{token}/sendMessage"\n')
        argv = ["curl", "-s", "-K", cfg_path, "-w", "\n%{http_code}", "-d", f"chat_id={chat_id}"]
        for key, value in (extra_fields or {}).items():
            argv += ["-d", f"{key}={value}"]
        argv += ["--data-urlencode", f"text={text}"]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        body, _, code = (result.stdout or "").rpartition("\n")
        if code in CREDENTIAL_REJECTED_STATUSES:
            return False, f"credential_rejected ({code})"
        if '"ok":true' not in body:
            return False, mask_tg_token(body[:200])
        return True, ""
    except Exception as e:
        return False, mask_tg_token(str(e))
    finally:
        if cfg_path is not None:
            try:
                os.unlink(cfg_path)
            except OSError:
                pass


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
