"""Shared secret-redaction helper for any script that talks to Telegram.

Mythos-P3 (2026-06-14). The recurring leak class on this machine is
"secret-in-URL-path + a library that access-logs the URL at INFO": the
Telegram API *requires* the bot token in the URL path
(`https://api.telegram.org/bot<TOKEN>/sendMessage`), and httpx (directly,
or via python-telegram-bot) emits an INFO access-log line containing that
full URL. With the root logger at INFO and httpx not silenced, the token
rides into the log on every request — 26,410 lines in one observed case,
amplified by a 409-Conflict fast-spin poll loop.

Two layers of defence, both cheap and dependency-free:

1. `silence_http_access_logs()` — drop httpx/httpcore (and python-telegram-bot)
   access logs below WARNING so the URL is never logged in the first place.
2. `RedactingFilter` — a belt-and-suspenders root-logger filter that scrubs
   any bot-token-shaped substring out of every record that still slips
   through (e.g. an exception string that embeds the URL).

Usage (right after `logging.basicConfig(...)`):

    from _log_redact import install_secret_redaction
    install_secret_redaction()

Import is path-tolerant: scripts run from the repo `scripts/` dir, so a
bare `import _log_redact` works; callers elsewhere can
`sys.path.insert(0, "<repo>/scripts")` first.
"""
from __future__ import annotations

import logging
import re

# bot<digits>:<35-ish token>  and the bare <digits>:<token> shape.
_TOKEN_RE = re.compile(r"(bot)?\d{6,12}:[A-Za-z0-9_-]{30,45}")
_REDACTED = r"\1<REDACTED_BOT_TOKEN>"

# httpx/httpcore emit the request URL at INFO; python-telegram-bot wraps
# httpx; aiogram uses aiohttp. Silence the access logs that carry the URL.
_NOISY_HTTP_LOGGERS = ("httpx", "httpcore", "telegram", "aiogram", "aiohttp.access")


def _scrub(text: str) -> str:
    return _TOKEN_RE.sub(_REDACTED, text)


class RedactingFilter(logging.Filter):
    """Scrub bot-token-shaped substrings from a log record's message + args."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            if isinstance(record.msg, str) and ("bot" in record.msg or ":" in record.msg):
                record.msg = _scrub(record.msg)
            if record.args:
                if isinstance(record.args, dict):
                    record.args = {
                        k: _scrub(v) if isinstance(v, str) else v
                        for k, v in record.args.items()
                    }
                else:
                    record.args = tuple(
                        _scrub(a) if isinstance(a, str) else a for a in record.args
                    )
        except Exception:  # noqa: BLE001 — redaction must never break logging
            pass
        return True


def silence_http_access_logs(level: int = logging.WARNING) -> None:
    """Raise the floor of HTTP-client access loggers above INFO."""
    for name in _NOISY_HTTP_LOGGERS:
        logging.getLogger(name).setLevel(level)


def install_secret_redaction(http_level: int = logging.WARNING) -> None:
    """One-call hardening: silence HTTP access logs + install the scrub filter.

    Idempotent — safe to call more than once. Call AFTER logging.basicConfig.
    """
    silence_http_access_logs(http_level)
    root = logging.getLogger()
    if not any(isinstance(f, RedactingFilter) for f in root.filters):
        root.addFilter(RedactingFilter())
    # Filters on the root *logger* don't apply to records emitted by child
    # loggers that propagate, so also attach to each root handler.
    for handler in root.handlers:
        if not any(isinstance(f, RedactingFilter) for f in handler.filters):
            handler.addFilter(RedactingFilter())
