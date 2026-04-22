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

import os
import re
from typing import Any

import sentry_sdk

PII_REDACTION_PLACEHOLDER = "[REDACTED]"

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
)

# Keys redacted on exact match only (case-insensitive). These are bare
# identity fields whose literal name is PII but whose substring appears in
# innocuous debug keys (e.g. "name" in "filename", "username" would match
# "name" as a substring).
_PII_EXACT_KEYS: frozenset[str] = frozenset({"name", "username"})

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

def _is_pii_key(key: Any) -> bool:
    if not isinstance(key, str):
        return False
    k = key.lower()
    if k in _PII_EXACT_KEYS:
        return True
    return any(s in k for s in _PII_KEY_SUBSTRINGS)


def _redact_string(s: str) -> str:
    """Mask emails and Bali Zero client_id patterns in free-text."""
    s = _EMAIL_RE.sub(PII_REDACTION_PLACEHOLDER, s)
    s = _CLIENT_ID_RE.sub(PII_REDACTION_PLACEHOLDER, s)
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


def _before_send_impl(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Inner implementation. Scrubs PII, returns scrubbed event.

    NOTE: cron/deploy alert deduplication was removed from this PR's scope
    (review #168/B2). No code in the repo currently tags events with
    `source=cron|deploy`, so a dedup filter here was a no-op. Tagging needs
    to be added at cron entrypoints (`cron-wrapper.sh`, `auto_sentinel.sh`,
    `cron_notifiers.py`) in a follow-up before a dedup filter can land here.
    """
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
    except Exception as exc:  # noqa: BLE001 — intentional catch-all
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
        return {
            "level": event.get("level"),
            "exception": event.get("exception"),
            "tags": {"sentry_hook_error": "true"},
        }


def init_sentry() -> None:
    """
    Initialize Sentry only when configured.

    Notes:
    - Avoids initializing during tests unless explicitly desired.
    - Default behavior is opt-in via SENTRY_DSN.
    - `traces_sample_rate` defaults to 0.0 in production (APM is opt-in).
    - `before_send` strips PII before anything leaves the process.
    """
    if os.getenv("SKIP_SENTRY_INIT"):
        return

    dsn = os.getenv("SENTRY_DSN", "")
    if not dsn:
        return

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
    )
