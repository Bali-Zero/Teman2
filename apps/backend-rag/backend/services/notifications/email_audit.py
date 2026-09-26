"""Email audit trail + critical-failure Telegram alerts.

Every email the backend sends (Brevo direct, Brevo via internal_email, Zoho
fallback) writes a row to ``email_send_log`` (migration 126) before the
network call and updates it after. When a CRITICAL email type fails and
cannot be retried locally, the caller may call
:func:`notify_email_failure_critical` to page the owner via Telegram.

The single-writer principle — only this module touches ``email_send_log`` —
means the retry worker in ``email_health_monitor.py`` can reason about
state transitions deterministically.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from backend.core.secret_log_redaction import install_telegram_token_redaction
from backend.security.pii_log_identifier import redact_identifier_for_log

install_telegram_token_redaction()

if TYPE_CHECKING:
    import asyncpg

logger = logging.getLogger(__name__)

# Owner chat_id lives in CLAUDE.md §14 (TELEGRAM_OWNER_CHAT_ID=8847435604).
# We prefer the env var so tests can override with a stub chat_id.
_OWNER_CHAT_ID: str = os.getenv("TELEGRAM_OWNER_CHAT_ID", "8847435604")

# Email types treated as operationally critical. Failure on these triggers a
# Telegram alert immediately (bypassing the retry queue's 3-attempt wait).
CRITICAL_EMAIL_TYPES: frozenset[str] = frozenset(
    {
        "waiting_docs_client",
        "waiting_docs_team",
        "completion_client",
        "completion_team",
        "hr_bonus",
        "invoice_client",
        "welcome",
    }
)

# Email types whose body cannot be reconstructed at retry time
# (personalized HTML, document URLs, brochure attachments). The retry
# worker would produce a "[RETRY] original subject was X" stub — a
# confusing meta-email from the client's point of view. For these types,
# a first failure is escalated directly to the owner via Telegram and
# the row is marked `retry_after=NULL` so `check_and_retry_failed_emails`
# never touches it. `escalate_unrecoverable` picks it up on the next
# monitor pass. Team-facing and stateless notifications (hr_bonus,
# waiting_docs_team, completion_team, invoice_client, cron_*) are
# acceptable to retry because a resent plain notification still conveys
# the actionable content.
NON_RESURRECTABLE_EMAIL_TYPES: frozenset[str] = frozenset(
    {
        "waiting_docs_client",
        "completion_client",
        "welcome",
    }
)

# Retry schedule: 1h after first failure, 4h after second, escalate after third.
_RETRY_BACKOFF = (
    timedelta(hours=1),
    timedelta(hours=4),
)


async def log_email_attempt(
    pool: asyncpg.Pool,
    *,
    email_type: str,
    to_email: str,
    subject: str | None = None,
    practice_id: int | None = None,
    client_id: int | None = None,
    attempt_number: int = 1,
    payload_cache: dict[str, Any] | None = None,
) -> int | None:
    """Insert a 'sending' row immediately before the network call.

    Returns the row id; caller passes it back to :func:`record_email_result`.
    If DB insert fails, returns None and the caller proceeds without audit —
    the email attempt itself is not gated on audit success.
    """
    try:
        async with pool.acquire() as conn:
            row_id = await conn.fetchval(
                """
                INSERT INTO email_send_log
                    (email_type, practice_id, client_id, to_email,
                     subject, status, attempt_number, payload_cache)
                VALUES ($1, $2, $3, $4, $5, 'sending', $6, $7::jsonb)
                RETURNING id
                """,
                email_type,
                practice_id,
                client_id,
                to_email,
                (subject or "")[:500],
                attempt_number,
                json.dumps(payload_cache) if payload_cache is not None else None,
            )
            return int(row_id) if row_id is not None else None
    except Exception as exc:
        logger.warning("email_audit: log_email_attempt failed: %s", exc)
        return None


async def record_email_result(
    pool: asyncpg.Pool,
    row_id: int | None,
    *,
    status: str,
    provider: str | None = None,
    error_message: str | None = None,
) -> None:
    """Update the 'sending' row with terminal status.

    status ∈ {'sent','failed','skipped_idempotent'}. On 'failed', computes
    ``retry_after`` via :data:`_RETRY_BACKOFF`. If ``row_id`` is None
    (audit insert failed earlier), this is a no-op.
    """
    if row_id is None:
        return
    if status not in {"sent", "failed", "skipped_idempotent"}:
        logger.warning("email_audit: invalid status %r, coercing to failed", status)
        status = "failed"

    retry_after: datetime | None = None
    if status == "failed":
        # Read current attempt_number + email_type to decide next retry window.
        # Non-resurrectable types skip retry entirely — retry_after stays
        # None and escalate_unrecoverable() picks them up directly.
        try:
            async with pool.acquire() as conn:
                row = await conn.fetchrow(
                    "SELECT attempt_number, email_type FROM email_send_log WHERE id = $1",
                    row_id,
                )
                if row:
                    attempt_n = row["attempt_number"]
                    et = row["email_type"]
                    if et in NON_RESURRECTABLE_EMAIL_TYPES:
                        # leave retry_after=None → escalated on next monitor pass
                        pass
                    elif attempt_n and attempt_n <= len(_RETRY_BACKOFF):
                        retry_after = datetime.now(tz=timezone.utc) + _RETRY_BACKOFF[attempt_n - 1]
                        # attempt 3 = no more retries; retry_after stays None →
                        # escalate_unrecoverable() will pick it up.
        except Exception as exc:
            logger.warning("email_audit: could not resolve attempt_n for %d: %s", row_id, exc)

    # `status` travels twice, as $2 and $6. One shared parameter used to
    # feed both the `status` assignment (character varying) and the
    # `CASE WHEN ... = 'sent'` comparison (text): Postgres refuses to
    # PREPARE a parameter whose uses deduce two types ("inconsistent types
    # deduced for parameter $2 -- text versus character varying"), so this
    # UPDATE never ran and the except below swallowed it. Every audited
    # email therefore stayed 'sending' although it had been delivered;
    # check_stale_sendings then flipped it to failed, and the retry worker
    # mailed the recipient a "[RETRY] <subject>" notice for every
    # retry-safe type — measured on production 2026-09-21, over 30 days:
    # 91 hr_bonus, 97 invoice_client and 182 waiting_docs_team rows at
    # attempt 2, one per attempt-1 row, while every client-facing type
    # was escalated to the owner as undeliverable. Same defect, same cure
    # as `notifications/service.py` (notification_alerts, 2026-09-01).
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE email_send_log
                   SET status = $2,
                       provider = COALESCE($3, provider),
                       error_message = $4,
                       sent_at = CASE WHEN $6 = 'sent' THEN NOW() ELSE sent_at END,
                       retry_after = $5
                 WHERE id = $1
                """,
                row_id,
                status,
                provider,
                (error_message or "")[:4000] if error_message else None,
                retry_after,
                status,
            )
    except Exception as exc:
        logger.warning("email_audit: record_email_result failed for %d: %s", row_id, exc)


# `error`/`subject` are caller-supplied free text and can themselves carry
# the recipient's address (e.g. a provider bounce message quoting it back).
# Redacting only `to_email` below is not enough for this Telegram alert —
# it is an OUTPUT, not storage.
#
# Markdown delimiters are part of the TOKEN CLASS again (C1, PR #7385 gate
# follow-up — restores the round-1 shape): excluding them from the class
# (M5, round 2) fixed the `*Delivery to a@b*` case but broke any address
# that itself CONTAINS a delimiter — `first_last@x` matched only `last@x`
# (the `_` split the local part in two, and the stray `first_` before it
# never matched anything, so it survived unredacted); `x@sub_domain`
# matched only `x@sub` for the same reason on the domain side. Excluding
# `@`/whitespace/quotes/backtick/angle-brackets is enough to keep one
# match from spanning two addresses or leaking past a sentence boundary;
# `*_[]()` inside the span are the address's own characters until proven
# otherwise. What M5 actually needed is peeling, not exclusion — see
# `_redact` below: a LEADING/TRAILING run of delimiter chars right at the
# very edge of the match (never in the interior) still belongs to the
# surrounding Markdown, not the address, and goes back into the output
# unredacted, keeping `*Delivery to a@b*`'s closing `*` (and Telegram's
# parse_mode="Markdown" balance) intact.
_MD_DELIMS = "*_[]()"
_EMAIL_TOKEN_RE = re.compile(r"[^\s@<>\"'`]+@[^\s@<>\"'`]+")
#: Peeled off the START of a match — only `*_[]()` there is Markdown the
#: sentence opened before the address, never legitimate leading address
#: content (no valid local-part starts with one of these).
_LEADING_MD_DELIM_RE = re.compile(rf"^[{re.escape(_MD_DELIMS)}]+")
#: Peeled off the END of a match — Markdown delimiters AND trailing
#: sentence punctuation (`.,;:!?`) together, in whatever order the
#: sentence used them (e.g. `(a@b).` closes both the parenthetical and
#: the sentence). Excluding "." from the class above instead would also
#: refuse the dots inside a real domain, which the class must accept.
_TRAILING_MD_DELIM_PUNCT_RE = re.compile(rf"[{re.escape(_MD_DELIMS)}.,;:!?]+$")


def _scrub_email_tokens(text: str) -> str:
    """Replace every email-shaped token in ``text`` with its log-safe digest.

    A leading/trailing run of Markdown delimiters (and, trailing only,
    sentence punctuation) is peeled off the match first and reattached to
    the output verbatim — it belongs to the surrounding text, not the
    address — so it is never fed to the redactor and never dropped. Any
    delimiter INSIDE the match (e.g. `first_last@x`'s `_`) is part of the
    address as far as this function is concerned and is consumed into the
    digest like any other character, so no fragment of it survives.
    """

    def _redact(match: re.Match[str]) -> str:
        token = match.group(0)
        leading = _LEADING_MD_DELIM_RE.match(token)
        prefix = leading.group(0) if leading else ""
        core = token[len(prefix) :]
        trailing = _TRAILING_MD_DELIM_PUNCT_RE.search(core)
        suffix = trailing.group(0) if trailing else ""
        core = core[: len(core) - len(suffix)] if suffix else core
        return prefix + redact_identifier_for_log(core) + suffix

    return _EMAIL_TOKEN_RE.sub(_redact, text)


#: A truncation cut can land mid-token (e.g. right after `@`, or inside a
#: domain) and leave a fragment `_scrub_email_tokens` cannot match — its
#: regex needs at least one character on BOTH sides of `@`. `leak.probe@`
#: with nothing after `@` never matches, so it would survive truncation
#: unredacted. This strips a trailing PARTIAL token — the same case is
#: reachable whether or not `@` is actually present in it.
def _strip_trailing_partial_token(text: str) -> str:
    """Drop the trailing run of non-whitespace chars — same result as
    ``re.sub(r"\\S+$", "", text)``, replaced (C6, CodeQL alert 9192,
    ``py/polynomial-redos``) because that pattern is genuinely polynomial:
    fed 20k chars directly it measured ~2.0s, even though its only caller
    (`_bounded_scrub`) already bounds every call to its own 120/400-char
    ``limit`` (~1.4ms there) and the shape is unreachable at the size that
    made it slow. A right-to-left linear scan for the last whitespace
    character has the same worst case on any input size — it walks the
    string once, never backtracks.
    """
    i = len(text)
    while i > 0 and not text[i - 1].isspace():
        i -= 1
    return text[:i]


def _bounded_scrub(text: str, limit: int) -> str:
    """Truncate to ``limit`` chars, drop a trailing partial token, then scrub.

    Order matters (M4, PR #7385 round 2). Scrubbing BEFORE truncating would
    run the regex over unbounded caller-supplied text — measured quadratic
    on a long non-matching run (20k chars ~= 1.05s) — so truncation happens
    first, bounding every call to this function's own ``limit``. But
    truncating first can cut an address mid-token; if the cut did not land
    on a whitespace boundary, the trailing partial token is dropped entirely
    before scrubbing runs, rather than left for the regex to (fail to) catch.

    Only applied when the cut is actually mid-token: both `text[limit - 1]`
    (the last kept char) AND `text[limit]` (the first dropped char) must be
    non-whitespace (C3, PR #7385 gate follow-up). Checking only the first
    of those — the pre-fix shape — could not tell "cut mid-token" apart
    from "cut landed exactly on a token boundary", and dropped a COMPLETE
    last token whenever the very next original character happened to be
    whitespace (e.g. `limit=3` on `"abc def"`: `text[3]` is a space, `"abc"`
    is whole, but the old check saw `"abc"[-1]` was not whitespace and
    stripped it to `""` anyway). A single token longer than `limit` with no
    whitespace at all in it — the shape this function exists to bound —
    still collapses to an empty field either way: there is no boundary to
    keep any of it on.
    """
    was_truncated = len(text) > limit
    truncated = text[:limit]
    if (
        was_truncated
        and truncated
        and not truncated[-1].isspace()
        and not text[limit].isspace()
    ):
        truncated = _strip_trailing_partial_token(truncated).rstrip()
    return _scrub_email_tokens(truncated)


def notify_email_failure_critical(
    *,
    email_type: str,
    to_email: str,
    subject: str | None,
    practice_id: int | None,
    error: str,
) -> None:
    """Synchronous Telegram page for a critical-email failure.

    Uses urllib (not httpx) because callers are already deep in the send path
    and shouldn't spawn an async client. Errors are swallowed — a failed
    Telegram ping must not cascade into the caller's retry logic.
    """
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        logger.warning(
            "email_audit: TELEGRAM_BOT_TOKEN not set; skipping alert for %s → %s",
            email_type,
            redact_identifier_for_log(to_email),
        )
        return

    practice_fragment = f" (practice #{practice_id})" if practice_id else ""
    short_subj = _bounded_scrub((subject or "").strip(), 120)
    short_err = _bounded_scrub(error.strip().replace("\n", " "), 400)

    # Tell the operator whether to wait for retry or act immediately.
    # Non-resurrectable types (personalized HTML / attachments) bypass the
    # retry queue — a stub "[RETRY] original subject was X" email would
    # confuse the client, so record_email_result leaves retry_after=None
    # and escalate_unrecoverable pages again on the next monitor pass.
    if email_type in NON_RESURRECTABLE_EMAIL_TYPES:
        footer = "Not queued for retry (personalized body) — manual recovery required."
    else:
        footer = "Queued for retry. Check `email_send_log` if it escalates."

    text = (
        "🚨 *Email delivery failure* — critical path\n\n"
        f"*Type:* `{email_type}`{practice_fragment}\n"
        f"*To:* `{redact_identifier_for_log(to_email)}`\n"
        f"*Subject:* {short_subj}\n"
        f"*Error:* `{short_err}`\n\n"
        f"{footer}"
    )

    try:
        data = urllib.parse.urlencode(
            {"chat_id": _OWNER_CHAT_ID, "text": text, "parse_mode": "Markdown"},
        ).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data,
            timeout=10,
        )
    except (urllib.error.URLError, OSError, ValueError) as exc:
        logger.warning("email_audit: Telegram alert failed: %s", exc)


def is_critical(email_type: str) -> bool:
    """Return True iff a failure of ``email_type`` should page immediately."""
    return email_type in CRITICAL_EMAIL_TYPES


def format_send_error(exc: BaseException) -> str:
    """Return a non-empty diagnostic string for ``exc``.

    Some httpx low-level exceptions (``RemoteProtocolError``,
    ``ConnectError`` with no message, transient SSL drops) carry
    ``str(exc) == ''``. Persisting an empty ``error_message`` in
    ``email_send_log`` makes the failure undiagnosable from the
    dashboard. This helper falls back through ``str`` →
    HTTPStatusError-aware status+text → ``repr`` → class name so
    the field always holds at least the exception type.
    """
    msg = str(exc).strip()
    try:
        import httpx  # local import — keep email_audit dep-light
        if isinstance(exc, httpx.HTTPStatusError):
            resp = exc.response
            body = (resp.text or "").strip()[:500]
            status_line = f"HTTP {resp.status_code} from {resp.request.url}"
            return f"{status_line}: {body}" if body else status_line
    except Exception:
        # diagnostic helper must never raise
        pass
    if msg:
        return msg
    r = repr(exc).strip()
    if r and r != "Exception()":
        return r
    return type(exc).__name__ or "UnknownError"
