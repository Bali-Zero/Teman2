"""Keep secrets that ride inside URLs out of logs that end up somewhere public.

Two shapes are cured today, by one mechanism: Telegram bot tokens (token in the URL
path) and Redis connection strings (password in the URL userinfo). The second was
found 2026-10-09: `crm_hgt_handlers` logged the full Upstash `REDIS_URL` at INFO, and
Fly's log shipper archived it on a fleet machine. The cure is the channel, not the
call site, so the call site was left as it was.

TELEGRAM, the original autopsy follows.

WHY THIS EXISTS (2026-08-12, measured on a live CI run, not hypothesised).
`cron-llm-credit-sentinel.yml` runs hourly. On 2026-08-11 at 22:05Z its log —
in `Bali-Zero/Teman2`, whose visibility is **PUBLIC**, so its Actions logs are
world-readable — contained this line, emitted by httpx at INFO:

    HTTP Request: POST https://api.telegram.org/bot<ID>:<SECRET>/sendMessage "..."

Three things had to line up, and they are all ordinary:

1. Telegram puts the bot token **in the URL path**. There is no header form.
2. `llm_credit_sentinel_cli.py` calls `logging.basicConfig(level=logging.INFO)`,
   which raises the ROOT logger — and with it httpx's request logging, which
   prints `request.url` verbatim.
3. The job runs **over SSH on a fleet machine**, so the token comes from that
   machine's environment. GitHub only masks values it knows are secrets in that
   run, so it never masked this one.

The bot is `@Balizerobot`, whose live token is already known to sit in 25 commits
of this repo's public history with the @BotFather rotation still pending. So this
is not a new secret — it is a **second leak channel for an open one**, and that
is exactly why it must be closed FIRST: rotating the token without this fix
republishes the new one within the hour.

**Redact, do not silence.** Setting the httpx logger to WARNING would also work
and would throw away every request line for every other host — observability
paid to fix a formatting problem. This filter keeps the line and removes the
secret half of the token.

**Matched by SHAPE, never by value.** The pattern knows what a Telegram token
looks like, not what ours is, so it covers the token that replaces this one and
any other bot the fleet ever talks to. Nothing here reads, stores or compares a
secret.
"""

from __future__ import annotations

import logging
import re

# `bot<digits>:<35ish url-safe chars>` — Telegram's own shape. The id half is
# kept: it identifies WHICH bot in a debug session and authenticates nothing.
TELEGRAM_TOKEN_RE = re.compile(r"(bot\d{5,}):[A-Za-z0-9_-]{20,}")
REDACTED = r"\1:<redacted>"

# `redis[s]://[user]:<password>@host...` — scheme, username and host are kept (they
# say WHICH instance and authenticate nothing); only the password goes. The password
# runs greedily to the last `@` of the whitespace-free token, so an unescaped `@`
# inside it cannot leave a tail behind. MEASURED LIMIT of that greed: a credential-free
# URL survives byte-identical alone (`redis://localhost:6379`) and when followed by
# whitespace — the two shapes a log actually carries, both pinned by tests — but glue a
# later `@` on with no space (`redis://h:6379,a@x.com`) and the span IS rewritten.
# Over-redacting a log line is the cheaper error, so the greed stays; "no credential,
# no match" holds for real log shapes, not for every string.
REDIS_URL_RE = re.compile(r"(rediss?://[^:/@\s]*):[^\s]+@", re.IGNORECASE)
REDIS_URL_REDACTED = r"\1:<redacted>@"

# (cheap lowercase needle, pattern, replacement). The needle is a pre-filter only:
# a line is scanned when ANY needle is present, and the regex alone decides.
_REDACTIONS = (
    ("bot", TELEGRAM_TOKEN_RE, REDACTED),
    ("redis", REDIS_URL_RE, REDIS_URL_REDACTED),
)

# Loggers that print request URLs, BY THEIR EXACT NAME — measured, not guessed.
# A logger's filters run only for records that ORIGINATE on it; they do NOT run
# for records propagating up from children. So `"httpcore"` alone would have been
# decorative: httpx 0.28.1 logs on `"httpx"` (covered), but httpcore logs on
# `httpcore.http11` / `.http2` / `.proxy` / `.socks` — children, every one.
_URL_EMITTING_LOGGERS = (
    "httpx",
    "httpcore.http11",
    "httpcore.http2",
    "httpcore.proxy",
    "httpcore.socks",
    "urllib3.connectionpool",
)

_FILTER_MARKER = "_nuzantara_secret_log_redaction"


class SecretRedactionFilter(logging.Filter):
    """Rewrite any record whose rendered message carries a known URL-borne secret.

    A logging Filter that returns True always: it never drops a record, it only
    edits one. Dropping would be the silencing this module exists to avoid.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
        # Fail OPEN, deliberately: a redactor that raises takes down the logging
        # of the process it was added to protect, which is a worse outcome than
        # the line it failed to inspect.
        except Exception:
            return True

        lowered = rendered.lower()
        # cheap reject for the overwhelming majority: skip unless SOME pattern could match
        if not any(needle in lowered for needle, _, _ in _REDACTIONS):
            return True

        redacted = rendered
        for _, pattern, replacement in _REDACTIONS:
            redacted = pattern.sub(replacement, redacted)
        if redacted != rendered:
            # Collapse to a literal message: the secret may sit in msg OR in args
            # (%-formatting), and rewriting only one leaves the other to be
            # re-rendered by the handler with the secret intact.
            record.msg = redacted
            record.args = ()
        return True


# Historical names. COUNTED, not estimated: 16 production modules import
# `install_telegram_token_redaction`, plus the census test and a lint. Renaming them
# would be a 16-file diff for no behaviour change, so the old names stay as aliases.
TelegramTokenRedactionFilter = SecretRedactionFilter


def _new_filter() -> SecretRedactionFilter:
    redactor = SecretRedactionFilter()
    setattr(redactor, _FILTER_MARKER, True)
    return redactor


def _already_filtered(holder: logging.Logger | logging.Handler) -> bool:
    return any(getattr(f, _FILTER_MARKER, False) for f in holder.filters)


def install_secret_log_redaction() -> None:
    """Attach the filter on two levels, because neither alone is enough. Idempotent.

    **Named loggers** catch the emitters we have measured, at the point the record
    is created. **Root handlers** are the general backstop: a handler runs its own
    filters on every record that reaches it, including records propagated from
    loggers this module has never heard of — which is what makes this a cure for
    the class rather than for httpx.

    Called at import time by each module that can send to Telegram, so a process
    able to leak the token is by construction a process that redacts it;
    ``test_telegram_token_never_reaches_a_log.py`` enforces that census.

    DECLARED LIMIT: a handler added to root *after* this call is not covered by
    the handler half (the named-logger half still covers the known emitters). That
    limit is real, not theoretical: `configure_logging()` CLEARS root's handlers, so
    any install that ran before it is silently discarded. The api/rag app therefore
    calls this at the end of `configure_logging()`, after the handlers exist. A caller
    that reconfigures logging late should call this again; it is idempotent.
    """
    for name in _URL_EMITTING_LOGGERS:
        target = logging.getLogger(name)
        if not _already_filtered(target):
            target.addFilter(_new_filter())

    for handler in logging.getLogger().handlers:
        if not _already_filtered(handler):
            handler.addFilter(_new_filter())


# Historical name — every Telegram sender calls it at import time and the census test
# looks for this exact call; both keep working, and both now also cure Redis URLs.
install_telegram_token_redaction = install_secret_log_redaction
