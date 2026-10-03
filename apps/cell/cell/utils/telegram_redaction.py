"""Keep CELL's Telegram bot token out of its own logs.

Measured 2026-09-27: `organism.stderr.log` carried the bot token in the clear,
35 times. `TelegramAlerter.send()` (`cell/effectors/telegram.py`) posts via the
shared `httpx.AsyncClient`, and Telegram puts the bot token in the URL PATH —
there is no header form. `cell/main.py` runs
`logging.basicConfig(level=logging.INFO)` before anything else, and httpx logs
every request's full URL at INFO (``HTTP Request: POST <url> "..."``) via its
own ``httpx``/``httpcore.*`` loggers — so every alert, successful or not, put
the token in the log. The alerter's own ``except Exception as e:
logger.error(f"...: {e}")`` is a second path: an ``httpx.HTTPStatusError``'s
``str()`` also embeds the request URL.

Same mechanism, same fix shape as
``apps/backend-rag/backend/core/secret_log_redaction.py`` — duplicated here
rather than cross-imported, since `apps/cell` does not depend on backend-rag.

**Matched by SHAPE, never by value**: the pattern is Telegram's own token
shape (``bot<digits>:<secret>``), not this bot's specific token, so it covers
the token that replaces this one too.
"""
from __future__ import annotations

import logging
import re

_TOKEN_RE = re.compile(r"(bot\d{5,}):[A-Za-z0-9_-]{20,}")
_REDACTED = r"\1:<redacted>"
_MARKER = "_cell_telegram_token_redaction"

# httpx logs the request line on "httpx"; httpcore logs it on its per-transport
# children, not on "httpcore" itself (a logger's filters run only for records
# it originates, not ones propagating from children).
_URL_EMITTING_LOGGERS = (
    "httpx",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
)


class _TelegramTokenRedactionFilter(logging.Filter):
    """Rewrite any record whose rendered message carries a Telegram token.

    Always returns True — it edits a record, it never drops one. Dropping
    would be the silencing this module exists to avoid.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        except Exception:  # fail OPEN: a broken redactor must not take down logging
            return True
        if "bot" not in rendered:
            return True
        redacted = _TOKEN_RE.sub(_REDACTED, rendered)
        if redacted != rendered:
            record.msg = redacted
            record.args = ()
        return True


def _new_filter() -> _TelegramTokenRedactionFilter:
    filt = _TelegramTokenRedactionFilter()
    setattr(filt, _MARKER, True)
    return filt


def _already_filtered(holder: logging.Logger | logging.Handler) -> bool:
    return any(getattr(f, _MARKER, False) for f in holder.filters)


def install_telegram_token_redaction() -> None:
    """Attach the filter on the known URL-emitting loggers AND on root
    handlers (the general backstop — covers `TelegramAlerter`'s own
    `logger.error(f"...: {e}")` regardless of which exception embeds the URL).
    Idempotent. Call once, after `logging.basicConfig()` has created the root
    handler(s).
    """
    for name in _URL_EMITTING_LOGGERS:
        target = logging.getLogger(name)
        if not _already_filtered(target):
            target.addFilter(_new_filter())

    for handler in logging.getLogger().handlers:
        if not _already_filtered(handler):
            handler.addFilter(_new_filter())
