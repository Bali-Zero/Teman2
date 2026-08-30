"""
Sentry Configuration Module

Handles Sentry initialization for error monitoring.
Avoids initializing during tests unless explicitly desired.

PII policy (UU PDP compliance):
    Nuzantara handles NPWP, NIB, passport numbers, client emails/phones,
    names and client identifiers. NONE of those may reach Sentry cloud.
    The `_before_send` hook below runs on every event and:
      - redacts known PII keys (case-insensitive) anywhere in the payload,
      - masks email-shaped strings and Bali Zero client_id patterns
        (`CL-\\d{3,}`) in free text,
      - is wrapped in try/except so a bug in the scrubber can't silently
        drop events; the fallback preserves `level`/`exception` so the
        diagnosis signal survives.

    NOT in scope for this file: cron/deploy alert deduplication. Those
    pipelines already page Telegram, but no code currently tags events
    with `source=cron|deploy`, so filtering here would be a no-op.
    Follow-up issue will add the tagging at cron entrypoints before we
    re-introduce the filter.

Quota policy (Sentry free tier = 5k events/month shared error+transaction):
    `traces_sample_rate` defaults to **0.0** in production — APM is opt-in
    via an explicit `SENTRY_TRACES_SAMPLE_RATE` env var. Any value > 0.02
    in production will be flagged by `scripts/sentry-quota-check.sh`.
"""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import Any

PII_REDACTION_PLACEHOLDER = "[REDACTED]"
logger = logging.getLogger("zantara.backend")
_SENTRY_INIT_LOCK = threading.Lock()
_SENTRY_INIT_STARTED = False

# Keys whose *value* must always be redacted, regardless of nesting depth.
# Match is case-insensitive and also catches common suffixed variants (e.g.
# `client_email`, `user_phone`, `primary_surname`).
#
# IMPORTANT: bare "name" is NOT in this list. Substring-matching "name" would
# also redact legitimate debug fields like `filename`, `function_name`,
# `module_name`, `transaction_name`, `hostname` — making the stacktrace
# unreadable and Sentry less useful than no Sentry at all. PII name fields
# are matched via `_PII_EXACT_KEYS` below plus the explicit `*_name` suffixes
# enumerated here.
_PII_KEY_SUBSTRINGS: tuple[str, ...] = (
    "npwp",
    "nib",
    "tax_id",
    "passport",
    "email",
    "phone",
    "client_id",
    "surname",
    "client_name",
    "first_name",
    "last_name",
    "full_name",
    "contact_name",
    # Added 2026-08-25 (GARUDA VOA L4 magic-link auth, CodeQL
    # py/clear-text-storage-sensitive-data #8755 review): covers
    # `account_session_secret` / `result_session_secret` / any future
    # `*_secret` field. Substring is safe here — unlike "token" below, no
    # legitimate non-PII field in this codebase's debug/breadcrumb data is
    # named with a "secret" substring; every hit IS a credential.
    "secret",
)

# Keys redacted on exact match only (case-insensitive). These are bare
# identity fields whose literal name is PII but whose substring appears in
# innocuous debug keys (e.g. "name" in "filename", "username" would match
# "name" as a substring).
#
# "token" added 2026-08-25 (same review as "secret" above) for the magic-link
# bearer (`MagicLinkExchange.token`). It is EXACT-match, deliberately not a
# substring: this codebase logs `max_tokens`, `token_count`, `tokenizer`,
# `input_tokens`/`output_tokens` constantly for LLM call debugging (see
# `backend/llm/genai_client.py`, `generate_structured` callers) — substring
# `"token"` would redact every one of those and make Sentry useless for LLM
# diagnosis. This does NOT cover `access_token`/`refresh_token`/`csrf_token`
# (Drive OAuth, auth cookies) — those are a pre-existing gap, out of scope
# for the L4 PR that added this line; tracked separately, not fixed here.
_PII_EXACT_KEYS: frozenset[str] = frozenset({"name", "username", "token"})

# Keys to treat as "query-string-ish" — the value is a URL-encoded param
# blob that we redact by key rather than parsing.
_QUERY_KEYS: tuple[str, ...] = ("query_string", "query", "QUERY_STRING")

# Email regex — mirrors the brief. Used both to mask stray emails in strings
# and to scrub the URL path itself.
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[\w.-]+")

# Bali Zero client_id pattern (e.g. "CL-000142"). These IDs are used as keys
# into CRM/Drive so they're treated as identity PII even when the field name
# upstream is a generic `id`.
_CLIENT_ID_RE = re.compile(r"\bCL-\d{3,}\b")

# --------------------------------------------------------------------------- #
# Free-text identifiers.
#
# Everything above this line redacts by KEY, which is exact when the payload is
# structured — and blind when it is a sentence. A formatted log message has no
# keys: `logger.info(f"OCR done: {passport}")` reaches Sentry as one string, and
# the LoggingIntegration is a DEFAULT integration (level=INFO -> breadcrumb,
# event_level=ERROR -> event), so every log line in the process is a candidate.
# Until 2026-08-02 free text was covered by email + `CL-\d{3,}` ONLY, which is
# why this module's own docstring — promising that NPWP, NIB, passport and phone
# never reach Sentry — was true of dicts and false of sentences.
#
# Two tiers, deliberately:
#   SHAPE-anchored — the format is distinctive enough to stand alone.
#   LABEL-anchored — bare digits are NOT distinctive (a 13-digit NIB is
#     indistinguishable from an epoch-ms timestamp, which logs are full of), so
#     these redact only when the field names itself nearby. Matching them
#     unconditionally would eat every timestamp in every breadcrumb: an
#     over-match here does not just add noise, it destroys the diagnostic value
#     the event exists for.
#
# WHAT THIS STILL CANNOT DO — do not read the list above as full cover:
#   * a personal NAME in free text ("Created client 7: Jane Doe") is not a
#     regex-recognisable shape at all; it needs NER (see
#     `backend/middleware/pii_scanner.py`, Presidio) and is out of scope for a
#     hook that must stay fast and dependency-free on the error path;
#   * an UNLABELLED passport (`"...: X1234567"`) has no anchor to catch.
# Both are pinned as known-gap tests. The only real fix for them is not logging
# the value — this hook is defence in depth, never a licence to log PII.
# --------------------------------------------------------------------------- #

# SHAPE-anchored: formatted Indonesian NPWP, e.g. "01.234.567.8-901.000".
_NPWP_RE = re.compile(r"\b\d{2}\.\d{3}\.\d{3}\.\d-\d{3}\.\d{3}\b")

# SHAPE-anchored: international phone, e.g. "+62 812 3456 7890", "+6281234567890",
# "+62 (812) 3456-7890". Two forms, deliberately separate:
#   FMT — a country code followed by a SEPARATOR. A signed integer is never
#         written "+62 (812)", so the separator is the discriminator.
#   RUN — a contiguous run of 11+ digits after the "+". Shorter contiguous runs
#         are left alone: "+12345678" is equally a rupiah delta and
#         "+1234567890" a byte offset, and in a repo whose logs carry revenue
#         and byte counts that is the likelier reading. 11 is not a threshold
#         tuned to the fixtures: an E.164 number CARRYING its country code is
#         11-15 digits (+1 and ten national digits, +62 and nine to eleven), so
#         it sits where real phone numbers begin and leaves the 10-digit band
#         below it to the counters.
# `.` is deliberately NOT a separator: with it, a signed float in a metrics line
# (`latency +12.345678901`) matches and gets redacted. Dot-separated phone numbers
# are the rarer shape and WhatsApp never emits them.
# Both are bounded repetitions of a single class — no nested quantifier, hence no
# catastrophic backtracking (the ReDoS shape cured in core/legal/constants.py).
_PHONE_INTL_FMT_RE = re.compile(r"\+\d{1,3}[\s()-]{1,3}\d[\d\s()-]{5,16}\d")
_PHONE_INTL_RUN_RE = re.compile(r"\+\d{11,15}\b")

# SHAPE-anchored: Indonesian mobile in local (`08…`) form, with or without the
# separators people actually type ("0812 3456 7890", "0812-3456-7890"). The
# LEADING ZERO is the discriminator: a count is never written 0812…
# The first draft matched contiguous digits only, so the separated forms — how a
# human types the number into the CRM field these messages quote — walked through.
_PHONE_LOCAL_RE = re.compile(r"\b08\d{1,2}[\s.-]?\d{3,4}[\s.-]?\d{3,5}\b")

# SHAPE-anchored: WhatsApp-JID form (`62…`). Kept DELIBERATELY WIDE, and its
# collateral accepted on evidence rather than preference: the dominant real shape
# in this codebase is `logger.info("... %s", phone)` — measured across
# backend/app/routers/whatsapp_chat.py — which renders the number BARE, with no
# adjacent label and no @s.whatsapp.net suffix. Label-anchoring it would miss the
# leak that actually happens.
# ACCEPTED COLLATERAL, stated because it is real: an 11-14 digit integer starting
# with 62 — a token count, a byte total — reads [REDACTED]. Under UU PDP the safe
# direction is to over-redact, and no shape separates the two.
# (An earlier comment here defended this pattern against EPOCHS, which start with
# 1 and never collide. That was the wrong adversary: the collision is with COUNTS,
# and two reviewers from different model families found it independently.)
_PHONE_ID_RE = re.compile(r"\b62\d{9,12}\b")

# LABEL-anchored: the value carries no distinctive shape, so the field must name
# itself. Covers NIB/NIK/KTP/NPWP-16-digit and passport/paspor numbers.
_LABELLED_ID_RE = re.compile(
    r"(?i)\b(nib|nik|ktp|npwp|no[_\s.]?ktp|passport(?:[_\s.]?(?:number|no))?|paspor)"
    r"\b[\s:=#]*([A-Z]{0,2}[\d][\d.\s-]{4,18}\d)"
)


def _is_pii_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    k = key.lower()
    if k in _PII_EXACT_KEYS:
        return True
    return any(s in k for s in _PII_KEY_SUBSTRINGS)


def _redact_string(s: str) -> str:
    """Mask identifiers in free text: emails, client_id, phones, NPWP, labelled IDs.

    See the free-text block above for the two tiers and for what this still
    cannot reach (bare personal names, unlabelled passport numbers).
    """
    s = _EMAIL_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _CLIENT_ID_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _NPWP_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _PHONE_INTL_FMT_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _PHONE_INTL_RUN_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _PHONE_LOCAL_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _PHONE_ID_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    # Keep the label, drop the value: "NIB 1234567890123" -> "NIB [REDACTED]".
    # The label is what makes the breadcrumb still worth reading.
    s = _LABELLED_ID_RE.sub(lambda m: f"{m.group(1)} {PII_REDACTION_PLACEHOLDER}", s)
    return s


def _redact_query_string(s: str) -> str:
    """Rewrite `a=1&email=x&nib=y` with PII values masked."""
    if "=" not in s:
        return _redact_string(s)
    pairs = s.split("&")
    out: list[str] = []
    for pair in pairs:
        if "=" in pair:
            k, _, _v = pair.partition("=")
            if _is_pii_key(k):
                out.append(f"{k}={PII_REDACTION_PLACEHOLDER}")
            else:
                out.append(pair)
        else:
            out.append(pair)
    return _redact_string("&".join(out))


def _scrub(obj: Any, parent_key: str | None = None) -> Any:
    """Recursively redact PII values and email substrings in any JSON-like blob."""
    if isinstance(obj, dict):
        scrubbed: dict[Any, Any] = {}
        for k, v in obj.items():
            if _is_pii_key(k):
                scrubbed[k] = PII_REDACTION_PLACEHOLDER
            elif isinstance(k, str) and k in _QUERY_KEYS and isinstance(v, str):
                scrubbed[k] = _redact_query_string(v)
            else:
                scrubbed[k] = _scrub(v, parent_key=k if isinstance(k, str) else None)
        return scrubbed
    if isinstance(obj, list):
        return [_scrub(v, parent_key=parent_key) for v in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(v, parent_key=parent_key) for v in obj)
    if isinstance(obj, str):
        if parent_key and parent_key in _QUERY_KEYS:
            return _redact_query_string(obj)
        return _redact_string(obj)
    return obj


# Transactions Sentry should not be paying for. Measured on `bali-zero-7p` over
# 7 days (2026-08-28): 1,952 errors accepted against 753 rate_limited — 28% of
# production errors dropped for quota, chosen by arrival order rather than by
# importance. A dropped event is indistinguishable from one that never happened.
#
# ONLY TRANSACTIONS, and that distinction is the whole safety of this filter. A
# health check that 200s every 15 seconds is a metronome; a health check that
# 500s is one of the most important errors this system can produce (the
# 2026-04-29 outage was exactly that, and /health answering 200 while the worker
# was dead is its own scar). Dropping by URL would delete the second along with
# the first. `event.get("type") == "transaction"` is what separates them.
_HEALTH_TRANSACTIONS = (
    "/health",
    "/healthz",
    "/readyz",
    "/livez",
    "/api/health",
)


def _is_health_transaction(event: dict[str, Any]) -> bool:
    """True only for a TRANSACTION on a health path. Never for an error.

    Never raises: this runs inside `before_send`, and Sentry drops an event
    silently when that hook throws — a bug here would delete real errors rather
    than metronome ticks.
    """
    try:
        if event.get("type") != "transaction":
            return False
        name = event.get("transaction")
        if not isinstance(name, str):
            return False
        # Exact match or a path segment, never a substring: `/healthcheck-audit`
        # and `/api/health-report` are real endpoints, not metronomes.
        for path in _HEALTH_TRANSACTIONS:
            if name == path or name.startswith(path + "/") or name.endswith(" " + path):
                return True
        return False
    except Exception:
        return False


def _before_send_impl(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Inner implementation. Drops health-check transactions, scrubs PII.

    NOTE: cron/deploy alert deduplication was removed from this PR's scope
    (review #168/B2). No code in the repo currently tags events with
    `source=cron|deploy`, so a dedup filter here was a no-op. Tagging needs
    to be added at cron entrypoints (`cron-wrapper.sh`, `auto_sentinel.sh`,
    `cron_notifiers.py`) in a follow-up before a dedup filter can land here.
    """
    if _is_health_transaction(event):
        return None
    return _scrub(event)


def _before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Sentry `before_send` hook with exception-safe wrapper.

    Sentry drops events silently if `before_send` raises. `_scrub` walks
    arbitrary event payloads (frame locals, breadcrumb data, contexts),
    which can contain non-UTF-8 bytes, numpy arrays, or circular refs that
    break naive recursion. When that happens we return a minimal event so
    the diagnosis signal survives even if the scrubber failed — but we
    strip everything else (incl. potentially-unscrubbed data) defensively.
    """
    try:
        return _before_send_impl(event, hint)
    except Exception as exc:
        # Use stderr (→ fly logs) rather than `logger`: if the hook is
        # being triggered by a logging-related exception, `logger` itself
        # may be the thing that's broken. This is the documented escape
        # hatch for Golden Rule #8 — noqa prevents the compliance test
        # from flagging it.
        import sys

        print(  # noqa: T201 — see comment above; logger is unsafe here
            f"[sentry_config] _before_send raised {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        # `exception` is the one field this fallback keeps, and it is exactly
        # where a formatted message with PII lives (`exception.values[].value`,
        # frame vars). Returning it raw made the docstring above — "we strip
        # everything else (incl. potentially-unscrubbed data)" — false for the
        # only field it does not strip. Two independent reviewers, different
        # model families, found this path on the same diff. So scrub it on its
        # own: whatever broke the full walk is usually in `extra`/locals.
        try:
            safe_exception = _scrub(event.get("exception"))
        except Exception:
            # Second failure: drop the exception entirely. Losing the stack is a
            # diagnosis cost; shipping unredacted PII is a UU PDP breach, and the
            # tag below still tells the reader an event was suppressed here.
            safe_exception = None
        return {
            "level": event.get("level"),
            "exception": safe_exception,
            "tags": {
                "sentry_hook_error": "true",
                "sentry_exception_dropped": "true" if safe_exception is None else "false",
            },
        }


def _init_sentry_blocking(dsn: str) -> None:
    """Run the actual SDK import/init outside the API startup critical path."""
    import sentry_sdk

    send_pii = os.getenv("SENTRY_SEND_DEFAULT_PII", "").strip().lower() in {"1", "true", "yes"}
    env = os.getenv("ENVIRONMENT", "development")
    # Quota safety: production defaults to 0.0 (error-only). Any APM usage
    # requires an explicit SENTRY_TRACES_SAMPLE_RATE env var.
    default_traces = "0.0" if env == "production" else "1.0"
    traces_sample_rate = float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", default_traces))
    profiles_sample_rate = float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0"))

    sentry_sdk.init(
        dsn=dsn,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        send_default_pii=send_pii,
        environment=env,
        release=os.getenv("SENTRY_RELEASE", "nuzantara-backend@1.0.0"),
        before_send=_before_send,
        # `_before_send`/`_scrub` above only ever see the JSON-shaped event
        # payload. The SDK's logging integration attaches raw frame-LOCAL
        # values to `stacktrace.frames[].vars` at capture time, before
        # `before_send` runs, whenever this is left at its default (`True`,
        # historically named `with_locals`). A value that exists only as a
        # bare local (e.g. `garuda_result_session` / `result_session_secret`
        # in garuda_portal_auth.py) would leak regardless of how complete
        # `_PII_KEY_SUBSTRINGS` is — key-based redaction cannot reach it.
        include_local_variables=False,
    )


def init_sentry() -> None:
    """
    Initialize Sentry only when configured.

    Notes:
    - Avoids initializing during tests unless explicitly desired.
    - Default behavior is opt-in via SENTRY_DSN.
    - `traces_sample_rate` defaults to 0.0 in production (APM is opt-in).
    - `before_send` strips PII before anything leaves the process.
    - SDK import/init runs in a daemon thread by default so Sentry cannot
      block Fly.io health checks before the HTTP socket is bound.
    """
    if os.getenv("SKIP_SENTRY_INIT"):
        return

    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return

    if os.getenv("SENTRY_INIT_SYNC", "").strip().lower() in {"1", "true", "yes"}:
        _init_sentry_blocking(dsn)
        return

    def _background_init() -> None:
        try:
            _init_sentry_blocking(dsn)
        except Exception as exc:
            logger.warning("Sentry init skipped after startup: %s", exc)

    global _SENTRY_INIT_STARTED
    with _SENTRY_INIT_LOCK:
        if _SENTRY_INIT_STARTED:
            return
        _SENTRY_INIT_STARTED = True
        thread = threading.Thread(
            target=_background_init,
            name="sentry-init",
            daemon=True,
        )
        thread.start()
