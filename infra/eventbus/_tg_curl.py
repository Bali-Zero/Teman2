"""Shared low-level "send one Telegram message via curl" helper for eventbus.

`meta_dispatcher.py` and `research_sentinel.py` each had their own copy of
the same bug as apps/mata-garuda's daily-briefing/reg-alert senders: curl's
argv carried the bot token as a URL literal, and a broad `except Exception as
e:` logged it via `log.warning("...: %s", e)`. A `subprocess.TimeoutExpired`'s
own `str()` (rendered into the log line by `%`-formatting, same as an f-string
for this purpose) embeds the full argv it was constructed with.

Same fix shape as `apps/mata-garuda/mata_garuda/tg_curl.py`, duplicated here
rather than imported — this package (eventbus) does not depend on the
mata-garuda app, and each is independently deployable.
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile

_TOKEN_RE = re.compile(r"(bot\d{5,}):[A-Za-z0-9_-]{20,}")


def mask_tg_token(text: str) -> str:
    """Redact a Telegram bot token (`bot<digits>:<secret>`) from arbitrary text."""
    if not text:
        return text
    return _TOKEN_RE.sub(r"\1:<redacted>", text)


def curl_send(token: str, chat_id: str, text: str, *, timeout: float = 15) -> bool:
    """POST one sendMessage via curl. Never raises. Returns success only —
    eventbus's own callers are best-effort fire-and-forget and never branched
    on the failure reason before this fix either."""
    cfg_path: str | None = None
    try:
        cfg_fd, cfg_path = tempfile.mkstemp(prefix="tg-send-", suffix=".curlcfg")
        with os.fdopen(cfg_fd, "w") as fh:
            fh.write(f'url = "https://api.telegram.org/bot{token}/sendMessage"\n')
        result = subprocess.run(
            [
                "curl", "-sf", "-K", cfg_path,
                "-d", f"chat_id={chat_id}",
                "-d", f"text={text[:4000]}",
                "-d", "disable_web_page_preview=true",
            ],
            capture_output=True, text=True, timeout=timeout,
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        if cfg_path is not None:
            try:
                os.unlink(cfg_path)
            except OSError:
                pass
