"""Non-reversible log-safe digest for messaging identifiers (phone / Telegram chat id).

WHY (F7, 2026-08-25)
--------------------
``messaging_identity_service.py`` logged the caller's raw WhatsApp phone
number in cleartext (e.g. ``logger.info(f"Found user mapping for phone
{normalized_phone}...")``) — a client PII value under UU PDP and this repo's
Law-2 output frontier (``SYMBIOSIS.md`` Law 2 / ``CLAUDE.md`` §14): no log,
memory, report, alert or shared artifact may carry client PII in cleartext.
The I DUE BOT mandate froze this as gate F7 (``docs/plans/2026-08-25-due-bot-
live/MANDATE.md``): "Raw phone never in logs — extend
``messaging_identity_service.py`` but fix its raw-phone logging first."

A bare ``sha256(phone)`` is NOT a redaction: the Indonesian mobile number
space is small enough to enumerate in minutes, so an unkeyed digest is
reversible by brute force from the log alone — it is the phone number
wearing a hat. That reasoning is already established in this repo for a
much higher-stakes case, ``backend/services/rag/agentic/_memory_identity.py``
(``derive_wa_memory_subject``), whose digest is an ACTIVE identity key that
gates long-term-memory read/write and is therefore trust-gated (requires a
proven bot key) and fails closed to ``None`` when unconfigured — the safe
default there is "no memory", which is fine because memory anchoring is
opt-in and additive.

A log-line correlator has no such stakes, but a different, harder one: it
must NEVER fail back to printing the raw value, because F7 is a hard
invariant, not a best-effort one. So this module fails closed the OTHER
way — to a RANDOM, non-source-derivable per-process salt (see
``_unconfigured_fallback_salt`` below) — when no server secret is
configured, and is keyed by ITS OWN salt (``LOG_PII_HMAC_SALT``, distinct
from ``WA_MEMORY_SUBJECT_SALT``) so that rotating one does not silently
change the other: memory-subject rotation is a deliberate memory-wipe
product decision, log-digest rotation is routine hygiene, and the two must
be free to happen independently (same reasoning ``_memory_identity.py``
already gives for not borrowing ``wa_inbox_bot_profile_key`` — see that
module's docstring, point 4).

Design:
- Normalize to bare digits first ("+62 821-3465-159", "628213465159" and
  "08213465159" must collapse to the same digest, or the same client gets a
  fresh-looking identifier every time upstream formatting shifts). A
  Telegram numeric chat id is already all-digits, so the same normalization
  is a no-op for it — one function covers both identifier shapes safely.
- HMAC-SHA256, keyed by ``LOG_PII_HMAC_SALT`` (env, read at call time — not
  at import time — so tests can set/clear it per-case). Unset → a random
  per-process fallback salt (never a literal in this file — see
  ``_unconfigured_fallback_salt``), so the ONE invariant that must never
  break (no raw identifier in a log line, AND no digest reproducible by
  anyone holding only this source tree) holds even when the operational
  secret has not been provisioned; provisioning the real salt in production
  is what makes the digest correlate across process restarts.
- Short (12 hex = 48 bits): enough to distinguish clients in any plausible
  client book without practical collision, short enough to stay legible
  next to a log message (cf. the memory-subject digest's 32 hex, which
  anchors stored rows and needs the extra headroom this does not).

Importable by both the client-bot and the team-bot identity paths — this is
shared plumbing (``backend/utils/``), not private to
``messaging_identity_service.py``.
"""

from __future__ import annotations

import hmac
import logging
import os
import re
import secrets
import threading
from hashlib import sha256

logger = logging.getLogger(__name__)

#: Everything that is not a digit is noise: "+62 821-3465-159",
#: "62821-3465159" and "+628213465159" must all produce the SAME digest.
#: A Telegram chat id (already digits-only) passes through unchanged.
_NON_DIGITS_RE = re.compile(r"\D+")

#: Read at call time, never cached at import time, so a test can set or
#: clear this env var per-case without needing to reload this module.
_SALT_ENV_VAR = "LOG_PII_HMAC_SALT"

#: 12 hex = 48 bits. A log correlator, not a stored identity key — see
#: module docstring for why this deliberately does not match the 32-hex
#: memory-subject digest.
_DIGEST_HEX_LEN = 12

#: Returned for ``None`` or an identifier that carries no digits at all
#: (empty string, whitespace-only). Distinguishable at a glance from a real
#: digest, which always starts with ``id:``.
MISSING_IDENTIFIER_MARKER = "<none>"

_fallback_salt_lock = threading.Lock()
_fallback_salt: str | None = None
_fallback_warning_emitted = False


def _unconfigured_fallback_salt() -> str:
    """Random, non-reproducible-from-source HMAC key used only when
    ``LOG_PII_HMAC_SALT`` is unset.

    MUST NEVER be a literal in this file. A public repo means a fixed
    string constant used as an HMAC key is not a secret at all: anyone
    holding only the source can recompute every digest by enumerating the
    small phone-number space and hashing each candidate with the known
    constant (verified against the previous fallback design — the digest
    for a synthetic phone was reproduced exactly from the source-visible
    constant alone). A random per-process salt closes that hole by
    construction: it is generated once, held only in process memory, and
    never written anywhere.

    Trade-off, made deliberately and loudly (not silently): the digest for
    the SAME phone will differ across a process restart while unconfigured
    (this module has no way to persist a secret it was never given) — but
    within one running process, every call still gets the SAME salt, so
    log-line correlation holds for the lifetime of that process. The
    invariant this module exists to protect (no raw identifier in a log
    line, and no digest an attacker can recompute from source) is never
    traded away; only the *convenience* of cross-restart correlation is,
    and only when the operator has not provisioned the real salt.
    """
    global _fallback_salt, _fallback_warning_emitted
    with _fallback_salt_lock:
        if _fallback_salt is None:
            _fallback_salt = secrets.token_hex(32)
        if not _fallback_warning_emitted:
            logger.warning(
                "%s is not set — log-line phone/chat-id digests are keyed "
                "by a random per-process salt. They will NOT correlate "
                "across a process restart, and this warning means the "
                "operational secret has not been provisioned. Set %s in "
                "this environment so digests stay stable across restarts.",
                _SALT_ENV_VAR,
                _SALT_ENV_VAR,
            )
            _fallback_warning_emitted = True
        return _fallback_salt


def _resolve_salt() -> str:
    return os.getenv(_SALT_ENV_VAR) or _unconfigured_fallback_salt()


def _reset_fallback_salt_state_for_tests() -> None:
    """Test-only: clear the cached random fallback salt and the
    warn-once flag, so a test can simulate "a fresh process" (a NEW random
    salt gets generated on the next unconfigured call) without actually
    spawning one. Never called from production code."""
    global _fallback_salt, _fallback_warning_emitted
    with _fallback_salt_lock:
        _fallback_salt = None
        _fallback_warning_emitted = False


def redact_identifier_for_log(value: str | int | None) -> str:
    """Stable, non-reversible-without-the-salt stand-in for a phone number or
    Telegram chat id, safe to put in a log line.

    Same input (any formatting) -> same digest, always, so an operator can
    still follow one conversation across many log lines. Different input ->
    a different digest.

    Args:
        value: A phone number in any formatting ("+62...", "62...", "0...")
            or a Telegram numeric chat id. ``None``-safe.

    Returns:
        ``"id:<12 hex>"``, or :data:`MISSING_IDENTIFIER_MARKER` if ``value``
        is ``None`` or carries no digits.
    """
    if value is None:
        return MISSING_IDENTIFIER_MARKER

    digits = _NON_DIGITS_RE.sub("", str(value))
    if not digits:
        return MISSING_IDENTIFIER_MARKER

    key = _resolve_salt().encode("utf-8")
    digest = hmac.new(key, digits.encode("utf-8"), sha256).hexdigest()[:_DIGEST_HEX_LEN]
    return f"id:{digest}"
