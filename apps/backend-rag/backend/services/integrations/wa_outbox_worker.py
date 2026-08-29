"""WA Meta Inbox outbox worker.

Drains the ``wa_outbox`` send-intent queue for the Meta WhatsApp Business
number +62 821-3465-159 (``phone_number_id`` = ``META_INBOX_PHONE_NUMBER_ID``).

Design (panel-approved spec 2026-06-03, sezione 3 "Worker"; hardened by the
2026-07-17 F1a adversarial pass — see docs/superpowers/specs (zantara-wa-spec-v2)
sections P2-P6/D2):

1. Reclaim stale claims (``claim_expires_at < now()``) for BOTH ``claimed`` and
   ``generating`` rows → back to ``pending``. A crashed worker (mid-send OR
   mid-generation) must not park a send forever (P5).
2. Claim one due ``pending`` row. Candidates are scanned with
   ``FOR UPDATE SKIP LOCKED`` (row-level single-flight), but a candidate is
   only actually claimed after this worker wins a **per-thread advisory lock**
   (P3) — this is what stops two workers from concurrently processing two
   *different* pending rows of the *same* thread (SKIP LOCKED alone only
   dedupes the same row).
3. Coalescing (P2): once a bot-reply row is claimed, every OTHER pending
   bot-reply row for the same thread is superseded (marked failed,
   ``error='superseded_by_coalescing'``) — the generator always answers the
   *latest* thread message, so one send covers a whole burst.
4. If the row needs bot generation, re-check ``human_handling`` (the operator
   may have taken over since the webhook enqueued it) → if true, ABORT and
   drop the outbox row (bot must stay silent on a human-handled thread). A
   lease-heartbeat renews ``claim_expires_at`` every ~60s while generation is
   in flight (P6 — CLAIM_LEASE_SECONDS=300 must outlive a slow RAG call), and
   an immediately-pre-send fenced re-check of ``human_handling`` catches a
   takeover that happened *during* generation (P4) — a late/lost race aborts
   silently ("fenced") rather than sending.
5. Enforce the Meta 24h customer-care window — if the last inbound customer
   message is older than 24h, fail the ledger row (free-text send not
   allowed).
6. Send via the existing ``whatsapp_service`` (hardcodes the target
   ``phone_number_id`` from settings — already the correct number), record the
   Meta ``wamid`` on the ledger row, apply any orphan ``wa_status_pending``
   receipt for that wamid, and mark the outbox row done. On HTTP failure,
   backoff with ``next_retry_at``; after ``MAX_ATTEMPTS`` mark ``failed``.

Concurrency-control fencing (P4, applies to every state-changing UPDATE on
``wa_outbox`` after the initial claim): each UPDATE is scoped
``WHERE id = $1 AND claim_token = $2 AND status = $3`` and uses
``RETURNING id`` to detect whether it actually matched. Zero rows means this
worker's lease was reclaimed (or the row was superseded) since the last
checkpoint — abort processing silently and return ``"fenced"``. The one
exception is the *final* success commit: by the time we reach it the Graph
send has *already happened* (an irreversible external side-effect), so losing
the fence there cannot un-send the message — we log loudly (residual
double-send window, see the comment at the bottom of ``_process_claimed_row``)
and still report ``"sent"``, we do not swallow the fact that a message went
out.

Per-thread advisory lock (P3, design deviation from the literal spec text —
documented inline at the call site): the spec text says
``pg_try_advisory_xact_lock`` taken "inside the claim transaction". This
worker's claim transaction is intentionally short (it commits immediately
after marking the row 'claimed'); an *xact*-scoped lock would therefore
release the instant that transaction commits — i.e. before generation even
starts, defeating the purpose. This implementation uses the **session**-scoped
``pg_try_advisory_lock`` / ``pg_advisory_unlock`` pair instead, held for the
entire lifetime of ``_process_claimed_row`` (claim → generate → send →
commit) on the same pooled connection, and *always* released in a
``finally`` before the connection returns to the pool (a leaked session-scoped
lock would otherwise permanently wedge that thread on every future connection
reuse — see the docstring on ``process_outbox_once``).

This module exposes a single callable, :func:`process_outbox_once`, which
processes at most one outbox row per call. ``main_api.py`` spawns
``WA_OUTBOX_WORKERS`` (default 2) concurrent scheduler loops calling this in
a tight cycle (P9) — safe because of the per-thread advisory lock above.

"Manners" additions (2026-07-25, spec item C3/C4/C5 — a concierge ack, a
terminal apology, and the read-receipt wired into the meta-inbox webhook
router): a best-effort concierge ack (:func:`_maybe_send_ack`) fires once
generation starts, a best-effort apology (:func:`_maybe_send_apology`) fires
once either terminal-failure branch exhausts ``MAX_ATTEMPTS``, and a
best-effort read receipt (``whatsapp_chat._handle_meta_inbox_message``)
fires on genuinely new inbound messages. The ack/apology pair is idempotent
per outbox row via the durable ``ack_sent_at``/``apology_sent_at`` columns
(migration 260 — an in-memory flag would not survive the crash-and-reclaim
scenarios this worker is built to tolerate), takeover-aware, 24h-window-aware,
and swallow their own exceptions — neither can ever break generation, the
send, or the failure handling they piggyback on. The ack is gated by
``_manners_enabled()`` (``WA_OUTBOX_MANNERS_ENABLED``, DEFAULT OFF) — a
dedicated kill-switch distinct from ``WHATSAPP_ACK_ENABLED`` (which stays
Path-A's flag, default ON, untouched semantics; the ack ANDs both). Ships
dark: the deploy alone changes nothing observable until this is armed
deliberately post-verify.

The apology is a SEPARATE decision as of the Gemini-cut PR (2026-08-27, Zero:
"spegni gemini e collega chatgpt"): it is gated by its OWN
``_terminal_apology_enabled()`` (``WA_OUTBOX_TERMINAL_APOLOGY_ENABLED``,
DEFAULT **ON**), not by ``_manners_enabled()`` — with Gemini retired from this
worker (see the generation section of :func:`_process_claimed_row`), a
terminal failure or a codex-not-armed standing condition is now the FIRST
point where a client could be left in total silence, so the net that answers
that must not itself need arming. It also now tells a human
(:func:`wa_inbox_bot._tell_a_human`, Telegram) every time it fires, once per
row (the notifier's own 30-minute per-thread dedup applies) — the apology
copy says the conversation was flagged for the team, never that someone WILL
reply "shortly" (``human_escalation_notifier``'s own docstring: the boolean
this returns proves Telegram accepted a message, never that a person is on
shift or will act on it).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from typing import Any

import asyncpg

from backend.services.integrations import wa_codex_leg
from backend.services.integrations.wa_bot_outcomes import (
    BotStandingCondition,
    SilentStandingCondition,
)

logger = logging.getLogger(__name__)

# Verified ground truth: the Meta WhatsApp Business number this inbox manages.
# settings.whatsapp_phone_number_id == this value == the send number, so the
# existing whatsapp_service sends from the correct number without parametrising.
META_INBOX_PHONE_NUMBER_ID = "1104946272705747"

# 2026-08-25 double-reply scar: a Meta webhook re-registration can arm a
# SECOND subscription for the same underlying business number, delivered
# with a DIFFERENT phone_number_id. Every consumer that gates on
# "is this the meta-inbox number" must check membership in this set, never
# equality against the single canonical id above — an unrecognised id falls
# through to the legacy inline reply path in whatsapp_chat.py, which then
# answers a message the meta-inbox pipeline already answered.
# Extra ids come from META_INBOX_PHONE_NUMBER_IDS (comma-separated); the
# canonical id is always included even if the env var is unset or empty.
META_INBOX_PHONE_NUMBER_IDS: frozenset[str] = frozenset(
    {META_INBOX_PHONE_NUMBER_ID}
    | {
        pid.strip()
        for pid in os.environ.get("META_INBOX_PHONE_NUMBER_IDS", "").split(",")
        if pid.strip()
    }
)

# Lease window for a claimed outbox row. P6 (spec 2026-07-17): the previous
# 120s == the RAG read-timeout (120s in wa_inbox_bot._get_rag_client), so a
# slow-but-legitimate generation could outlive its own lease and get reclaimed
# out from under it. 300s gives headroom; the heartbeat below (renewed every
# ~60s during generation) keeps it fresh well before it would ever expire.
CLAIM_LEASE_SECONDS = 300

# How often the lease is renewed while bot_generate_fn is in flight. Module
# level (not a local constant) so tests can monkeypatch it to a tiny value
# instead of waiting out a real 60s interval.
LEASE_HEARTBEAT_INTERVAL_SECONDS = 60

# How many due-pending candidates to consider per claim attempt before giving
# up as idle. Only relevant when multiple candidates' threads are already
# locked by other in-flight workers (P3) — this is a background poller, not a
# hot path, so a modest scan window is fine.
CLAIM_CANDIDATE_LIMIT = 20

# Send retry policy.
MAX_ATTEMPTS = 5
RETRY_BACKOFF_BASE_SECONDS = 30

# wa_codex_leg._attempt() fall-off reasons that are STANDING CONDITIONS in
# disguise, not failed attempts: the leg deliberately steps aside on these
# two (its own docstring says so) trusting the Gemini leg to raise the
# IDENTICAL BotStandingCondition as ITS first statement (`is_bot_autoreply_
# enabled()` / "no customer message in the loaded window"). With Gemini
# retired from this worker (2026-08-27, "spegni gemini e collega chatgpt"),
# this module raises that BotStandingCondition itself instead of losing the
# distinction — see the generation section of `_process_claimed_row`.
_CODEX_LEG_STANDING_REASONS = frozenset({"autoreply_disabled", "no_customer_message"})

# Meta free-text customer-care window.
CUSTOMER_WINDOW_HOURS = 24

# Type alias for the injected bot text generator. Given a thread row mapping it
# returns the reply text to send (or raises). Kept injectable so the worker has
# no hard dependency on the RAG orchestrator (and is trivially testable).
BotGenerateFn = Callable[[asyncpg.Record], Awaitable[str]]

# Reused by both the advisory-lock TRY and its matching UNLOCK — must stay
# identical so the two calls hash to the same lock key for a given thread_id.
_THREAD_LOCK_KEY_SQL = "hashtext('wa_outbox_thread_' || $1::text)"

# Dedicated kill-switch for the C3/C4 "manners" auto-sends on this (Path B,
# LIVE-client) worker — DEFAULT OFF. Gate review 2026-07-25 (architect, not
# self-authored): whatsapp_ack.ack_enabled() (WHATSAPP_ACK_ENABLED) defaults
# to enabled, which was safe only because Path A (its only prior caller) is
# dead — this PR is what makes it load-bearing on a LIVE surface for the
# first time, so it must NOT inherit that default by accident. This flag is
# the primary gate for BOTH sends; whatsapp_ack.ack_enabled() stays a
# SEPARATE additional AND-condition on the ack specifically (defense in
# depth, unchanged semantics/default — never repurposed, per the review).
# Arm deliberately after a dark deploy is verified live:
#   fly secrets set WA_OUTBOX_MANNERS_ENABLED=true -a nuzantara-rag
def _manners_enabled() -> bool:
    return os.getenv("WA_OUTBOX_MANNERS_ENABLED", "false").strip().lower() in (
        "true",
        "1",
        "yes",
        "on",
    )


# Dedicated enablement for the terminal apology ONLY (item C4) — SEPARATE
# from `_manners_enabled()` and DEFAULT **ON**, as of the Gemini-cut PR
# (2026-08-27, Zero: "spegni gemini e collega chatgpt"). Before that PR a
# terminal failure was rare (Gemini answered almost everything in-claim);
# after it, a codex-not-armed standing condition or a genuine codex fall-off
# reaches this exhaustion path on EVERY message until WA_GENERATION_PROVIDER
# is armed — so the net that keeps the client from pure silence must not
# itself need a secret set. No variable needs arming for this to be live —
# deploying this PR alone turns it on. Kill-switch, if ever needed:
#   fly secrets set WA_OUTBOX_TERMINAL_APOLOGY_ENABLED=false -a nuzantara-rag
def _terminal_apology_enabled() -> bool:
    return os.getenv("WA_OUTBOX_TERMINAL_APOLOGY_ENABLED", "true").strip().lower() not in (
        "false",
        "0",
        "no",
        "off",
    )


# Terminal-failure apology (item C4). Short, neutral, non-technical — never
# leaks the underlying exception. Same language keys `detect_language()`
# returns (backend.services.communication.language_detector); "auto"/unknown
# falls back to English via the .get(..., default) below, mirroring
# whatsapp_ack.ack_text()'s pattern. Deliberately NOT a new translation
# subsystem: five short strings, same shape as _ACK_TEXTS.
#
# Corrected 2026-08-27 (Gemini-cut PR, first pass): the previous EN/IT copy
# promised "a member of our team will follow up with you shortly" while no
# code path ever told a human anything.
#
# Corrected AGAIN 2026-08-27, same day (Kimi K3 adversarial review,
# coordinator-weighted MAGGIORE): the first pass above only REWORDED the
# promise instead of removing it — "someone will get back to you as soon
# as they can" (EN), "akan segera ditindaklanjuti" (ID, literally "will
# soon be followed up"), "che ti risponderà appena possibile" (IT), "как
# только смогут"/"щойно зможуть" (RU/UK) are all still timed-reply
# promises in 4 of 5 languages, and the regression test meant to catch
# this only checked the English word "shortly" — vacuous, since that word
# could never appear in the other four languages regardless of whether the
# promise was removed. `_tell_a_human`'s own docstring is the actual
# contract: the boolean it returns proves Telegram ACCEPTED the alert,
# never that a person is on shift or will act on it AT ALL, let alone on a
# timescale ("shortly" / "segera" / "appena possibile" / etc.) nobody can
# guarantee. The copy below states only what is TRUE right now — the
# message was received and flagged — and commits to nothing about when or
# whether a human replies. See `test_apology_texts_never_promise_a_timed_reply`
# (derived from a real per-language promise-word list, not one English
# token) for the regression this now actually catches.
_APOLOGY_TEXTS = {
    "en": "Sorry — we're having a technical hiccup on our end. We've received your message and flagged this conversation for our team.",
    "id": "Maaf, sistem kami sedang mengalami kendala teknis. Pesan Anda sudah kami terima dan percakapan ini sudah kami tandai untuk tim kami.",
    "it": "Ci scusiamo — abbiamo un problema tecnico momentaneo. Abbiamo ricevuto il tuo messaggio e segnalato questa conversazione al nostro team.",
    "ru": "Извините — у нас временные технические неполадки. Мы получили ваше сообщение и передали этот разговор нашей команде.",
    "uk": "Вибачте — у нас тимчасові технічні проблеми. Ми отримали ваше повідомлення і передали цю розмову нашій команді.",
}


def _apology_text(detected_language: str | None) -> str:
    return _APOLOGY_TEXTS.get((detected_language or "en").lower(), _APOLOGY_TEXTS["en"])


def _window_open_locally(thread: asyncpg.Record) -> bool:
    """Same Meta 24h customer-care rule as the SQL check in step 6, evaluated
    in Python against a `thread` row already in hand — avoids a redundant
    DB round-trip for the ack/apology's own window check. Pure/no I/O
    (unlike the rest of this module's helpers, deliberately NOT async)."""
    last_customer_at = thread["last_customer_at"]
    if last_customer_at is None:
        return False
    return datetime.now(timezone.utc) - last_customer_at < timedelta(
        hours=CUSTOMER_WINDOW_HOURS
    )


async def _latest_inbound_text(conn: asyncpg.Connection, thread_id: int) -> str:
    """The most recent CUSTOMER message body for this thread — used only to
    drive should_send_ack's triviality filter and detect_language. Filters
    on direction='inbound' because the bot's own outbound ledger row for
    this very reply already exists (created by _handle_meta_inbox_message)
    with body=NULL at this point — an unfiltered "latest row" query would
    pick that empty row up instead of the customer's actual text."""
    body = await conn.fetchval(
        """
        SELECT body FROM meta_inbox_messages
        WHERE thread_id = $1 AND direction = 'inbound'
        ORDER BY created_at DESC LIMIT 1
        """,
        thread_id,
    )
    return body or ""


async def _maybe_send_ack(
    conn: asyncpg.Connection,
    outbox_id: int,
    claim_token: uuid.UUID,
    thread: asyncpg.Record,
    whatsapp_service: Any,
) -> None:
    """Best-effort "checking…" pre-message so the client isn't staring at
    silence for the 10-50s the RAG loop can take (item C3). Fires right
    after the row transitions to 'generating', BEFORE bot_generate_fn is
    awaited.

    Armed by ``_manners_enabled()`` (``WA_OUTBOX_MANNERS_ENABLED``, default
    OFF) AND-ed with the pre-existing ``whatsapp_ack.ack_enabled()`` — see
    both docstrings above the constants. Ships dark: unset in prod today.

    Idempotent via the durable ``ack_sent_at`` column on the SAME outbox
    row (migration 260): a retry (bot_generate_fn failed once, this row is
    reclaimed and reprocessed) or a worker crash-and-reclaim both re-enter
    this function against the *same* row id, and the fenced UPDATE below
    only ever matches once — ``ack_sent_at`` is set BEFORE the network send
    is attempted, so a second attempt sees it already non-NULL and skips
    (prefers a rare missed ack over any risk of a duplicate one — this
    sends a real WhatsApp message, so idempotency beats completeness).

    Takeover-aware: relies on the caller's already-fresh `thread` (loaded
    at the top of _process_claimed_row and re-verified human_handling=false
    immediately before the 'generating' transition — no new DB read here,
    the race window between that check and this call is a handful of
    already-awaited statements, not a genuine takeover opportunity).

    Window-aware: skips if the Meta 24h customer-care window is closed —
    checked locally (thread['last_customer_at'] is already in hand).

    Never raises: any failure here must not break generation or the send.

    Detecting a fast cache-hit path to skip acking it is NOT implemented —
    bot_generate_fn is an opaque injected callable (wa_inbox_bot.generate_
    bot_reply in prod) with no cheap, safe way to predict its latency
    before calling it; duplicating its cache-lookup here would be a
    fragile heuristic prone to drift. Per spec: prefer always-ack.
    """
    try:
        from backend.services import whatsapp_ack
        from backend.services.communication import detect_language

        if not _manners_enabled():
            return
        if not whatsapp_ack.ack_enabled():
            return
        if not _window_open_locally(thread):
            return

        phone = thread["counterpart_phone"]
        latest_inbound = await _latest_inbound_text(conn, thread["thread_id"])
        if not whatsapp_ack.should_send_ack(latest_inbound, phone):
            return

        claimed = await conn.fetchrow(
            """
            UPDATE wa_outbox SET ack_sent_at = NOW()
            WHERE id = $1 AND claim_token = $2 AND status = 'generating'
              AND ack_sent_at IS NULL
            RETURNING id
            """,
            outbox_id,
            claim_token,
        )
        if claimed is None:
            return  # already acked (retry) or lease already lost

        detected_language = detect_language(latest_inbound)
        await whatsapp_service.send_message(
            phone=phone,
            text=whatsapp_ack.ack_text(detected_language),
        )
        whatsapp_ack.mark_acked(phone)
        logger.info(
            "wa_outbox: concierge ack sent (outbox=%s thread=%s)",
            outbox_id,
            thread["thread_id"],
        )
    except Exception:
        logger.exception(
            "wa_outbox: concierge ack failed (non-blocking, outbox=%s)", outbox_id
        )


async def _maybe_send_apology(
    conn: asyncpg.Connection,
    outbox_id: int,
    thread: asyncpg.Record,
    whatsapp_service: Any,
    *,
    reason: str = "terminal_failure",
) -> None:
    """Best-effort apology when a row is permanently failed after exhausting
    retries (item C4) — tells the client the conversation was flagged for
    the team instead of leaving them in silence, and ACTUALLY flags it.
    Called from BOTH terminal-failure branches (bot-generation exhausted,
    Graph-send exhausted) AFTER the caller has already recorded the real
    failure on wa_outbox/meta_inbox_messages — this function's own failure
    is swallowed and logged, never allowed to mask or replace that
    recording (checked by the caller unconditionally proceeding to
    `return "failed"` regardless of what happens here). ``reason`` is a
    short caller-supplied label (e.g. "bot_generation_exhausted",
    "graph_send_exhausted") — forwarded to the Telegram notification only,
    never to the client-facing text.

    Idempotent via the durable ``apology_sent_at`` column (migration 260):
    'failed' is a terminal wa_outbox status no other code path resets back
    to 'pending' (the stale-claim reclaimer only touches 'claimed'/
    'generating'; coalescing only touches 'pending'), so in practice this
    can only be entered once per row. As of 2026-08-27 (Kimi K3 adversarial
    finding, minore) the durable claim is taken AFTER a successful
    client-facing send, not before — a read-only
    ``SELECT apology_sent_at`` guards against re-sending, and the post-send
    ``WHERE apology_sent_at IS NULL`` update is kept as defense-in-depth
    against a genuine concurrent re-entry, not because one is expected in
    practice. The human notification (`_tell_a_human`) is NOT gated by this
    column at all — it is independent of the client-send claim, and relies
    entirely on its own 30-minute per-thread dedup, which also covers the
    case where MULTIPLE rows in the same thread all exhaust retries.

    Takeover-aware: does a FRESH human_handling read (unlike the ack, which
    reuses the caller's just-verified value) — a terminal failure can be
    reached long after the original human_handling check (bot generation
    can run for minutes, and Graph-send retries backoff for several more),
    so the value the caller loaded at claim time may be stale. If a human
    now owns the thread, they are already the one following up — skip (this
    gates BOTH the human alert and the client apology).

    Window-aware for the CLIENT SEND ONLY (2026-08-27 Kimi K3 adversarial
    finding, MAGGIORE): the Meta 24h window governs what can be sent TO the
    client, not the internal Telegram alert — see the call-site comment on
    `_tell_a_human` below for why that call now happens BEFORE this check.

    Armed by ``_terminal_apology_enabled()`` (``WA_OUTBOX_TERMINAL_APOLOGY_ENABLED``,
    default **ON**, 2026-08-27) — a DEDICATED flag, deliberately NOT
    ``_manners_enabled()`` (which stays the ack's flag, default OFF,
    unchanged). See that function's own docstring for why the default
    flipped: Gemini is retired from this worker as of the same PR, so a
    terminal failure or a codex-not-armed standing condition is the first
    thing that can leave a client in total silence, and the net that
    answers that must not itself need arming.
    """
    try:
        from backend.services.communication import detect_language
        from backend.services.integrations.wa_inbox_bot import _tell_a_human

        if not _terminal_apology_enabled():
            return

        human_handling_now = await conn.fetchval(
            "SELECT human_handling FROM meta_inbox_threads WHERE thread_id = $1",
            thread["thread_id"],
        )
        if human_handling_now:
            return

        # Tell a human BEFORE the Meta-window check (2026-08-27 Kimi K3
        # adversarial finding, MAGGIORE): Telegram is an internal alert, not
        # a WhatsApp send — it is not bound by the 24h customer-care window
        # at all. The previous ordering put this call after the window
        # check, so a row that sat unanswered long enough to exhaust its
        # retries AND close the window got no client apology (unavoidable —
        # nothing can be sent) AND no human alert (avoidable, and exactly
        # the case a human is needed most: nobody else will ever see it).
        # _tell_a_human never raises and carries its own 30-min per-thread
        # dedup, so calling it here — independent of the client-send claim
        # below — is safe even across multiple rows in the same thread.
        await _tell_a_human(
            phone=thread["counterpart_phone"],
            reason=f"terminal_apology:{reason}",
            thread_id=thread["thread_id"],
        )

        if not _window_open_locally(thread):
            return

        already_sent = await conn.fetchval(
            "SELECT apology_sent_at FROM wa_outbox WHERE id = $1", outbox_id
        )
        if already_sent is not None:
            return  # already apologized

        latest_inbound = await _latest_inbound_text(conn, thread["thread_id"])
        detected_language = detect_language(latest_inbound)
        await whatsapp_service.send_message(
            phone=thread["counterpart_phone"],
            text=_apology_text(detected_language),
        )

        # Claim ONLY after a successful send (2026-08-27 Kimi K3 adversarial
        # finding, minore): claiming apology_sent_at before attempting the
        # send meant a failed send was swallowed by the except-Exception
        # below while the durable flag was already set — permanently
        # suppressing every future apology attempt for this row, with no
        # recovery path (unlike the retry ladder for generation). The
        # `WHERE apology_sent_at IS NULL` guard is kept as defense-in-depth
        # against a genuine concurrent re-entry, not because one is expected
        # in practice (see this function's own docstring on why this is
        # normally entered once per row).
        await conn.execute(
            """
            UPDATE wa_outbox SET apology_sent_at = NOW()
            WHERE id = $1 AND apology_sent_at IS NULL
            """,
            outbox_id,
        )
        logger.info(
            "wa_outbox: apology sent (outbox=%s thread=%s reason=%s)",
            outbox_id,
            thread["thread_id"],
            reason,
        )
    except Exception:
        logger.exception(
            "wa_outbox: apology send failed (non-blocking, outbox=%s) — the "
            "original failure was already recorded and is unaffected",
            outbox_id,
        )


def _extract_wamid(send_result: dict[str, Any] | None) -> str | None:
    """Pull the Meta message id (wamid) from a Graph send response."""
    if not isinstance(send_result, dict):
        return None
    messages = send_result.get("messages")
    if isinstance(messages, list) and messages:
        first = messages[0]
        if isinstance(first, dict):
            wamid = first.get("id")
            if isinstance(wamid, str) and wamid:
                return wamid
    return None


async def _apply_pending_status(conn: asyncpg.Connection, wamid: str) -> None:
    """Apply (and consume) an orphan status receipt that arrived before send.

    A delivered/read callback can land before the outbound row has its wamid
    committed (sezione 3). We stage those in ``wa_status_pending``; once the
    send commits the wamid, fold the staged status into the ledger row.
    """
    pending = await conn.fetchrow(
        "SELECT status, error FROM wa_status_pending WHERE meta_message_id = $1",
        wamid,
    )
    if pending is None:
        return

    await conn.execute(
        """
        UPDATE meta_inbox_messages
        SET status = $2,
            error = COALESCE($3, error)
        WHERE meta_message_id = $1
        """,
        wamid,
        pending["status"],
        pending["error"],
    )
    await conn.execute(
        "DELETE FROM wa_status_pending WHERE meta_message_id = $1",
        wamid,
    )
    logger.info("wa_outbox: applied staged status %s for wamid=%s", pending["status"], wamid)


async def _coalesce_thread_bursts(
    conn: asyncpg.Connection, thread_id: int, outbox_id: int
) -> int:
    """Supersede other NOT-YET-STARTED pending bot-reply rows of the same thread (P2).

    The generator always answers the *latest* thread message (see
    ``wa_inbox_bot._load_thread_context``), so whichever row of a same-thread
    burst gets claimed first, its generated reply already covers the whole
    burst — the other pending bot-reply rows would just be redundant sends.
    Only ``needs_generation`` rows are touched: a pending HUMAN send must
    never be silently dropped.

    ``attempts = 0`` is what makes "redundant" TRUE, and it is not decorative
    (2026-08-28, measured in production, thread 394 / row 363). Without it
    this sweep also killed rows that had already generated real text. That
    row's answer was produced by ChatGPT three times — every broker job
    ``consumed_ok``, 9711/10137/8521 ms — and rejected three times by the
    finalize safety pipeline; it sat at attempts 3 of MAX_ATTEMPTS waiting
    for its 4th try when a follow-up message arrived 3m27s later and this
    UPDATE marked it ``failed``. Silently: the sweep writes only ``status``,
    never a fall-off reason, and never reaches ``_maybe_send_apology`` (which
    is called ONLY from the two ladder-exhaustion branches). The client got
    no answer and no apology, and nothing alerted.

    A row with ``attempts > 0`` is not a burst duplicate — it is a question
    somebody is still owed an answer to. Left alone, its ladder ends one of
    only two ways: the answer is delivered, or the apology is sent. Never
    silence. It may then reply after the newer row does; a second, later
    message is a far smaller harm than a question answered by nothing, and
    its own context load already includes the follow-up.
    """
    async with conn.transaction():
        superseded = await conn.fetch(
            """
            UPDATE wa_outbox
            SET status = 'failed'
            WHERE thread_id = $1
              AND status = 'pending'
              AND needs_generation = true
              AND attempts = 0
              AND id <> $2
            RETURNING id, message_id
            """,
            thread_id,
            outbox_id,
        )
        for row in superseded:
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = 'superseded_by_coalescing'
                WHERE id = $1
                """,
                row["message_id"],
            )
    if superseded:
        logger.info(
            "wa_outbox: coalesced %d pending bot reply(ies) for thread %s into outbox %s",
            len(superseded),
            thread_id,
            outbox_id,
        )
    return len(superseded)


async def _lease_heartbeat_loop(
    conn: asyncpg.Connection, outbox_id: int, claim_token: uuid.UUID
) -> None:
    """Renew the claim lease every ~60s while bot_generate_fn is in flight.

    Fenced by claim_token + status='generating' — a best-effort renewal, not
    a correctness gate (the pre-send fence after generation is the actual
    gate). If this worker's row was already reclaimed, the UPDATE simply
    matches zero rows and the next tick tries again harmlessly.
    """
    try:
        while True:
            await asyncio.sleep(LEASE_HEARTBEAT_INTERVAL_SECONDS)
            await conn.execute(
                """
                UPDATE wa_outbox
                SET claim_expires_at = NOW() + ($3 * INTERVAL '1 second')
                WHERE id = $1 AND claim_token = $2 AND status = 'generating'
                """,
                outbox_id,
                claim_token,
                CLAIM_LEASE_SECONDS,
            )
    except asyncio.CancelledError:
        raise


async def process_outbox_once(
    pool: asyncpg.Pool,
    whatsapp_service: Any,
    bot_generate_fn: BotGenerateFn,
) -> str:
    """Process at most one ``wa_outbox`` row.

    Args:
        pool: asyncpg pool.
        whatsapp_service: object exposing ``async send_message(phone, text,
            reply_to_message_id=None)`` returning the Graph API response dict.
        bot_generate_fn: accepted for signature/back-compat only — NEVER
            invoked as of the Gemini-cut PR (2026-08-27, "spegni gemini e
            collega chatgpt"). Generation now runs exclusively through the
            codex broker leg (``wa_codex_leg.attempt``); see
            ``_process_claimed_row``'s docstring.

    Returns:
        A short status string describing what happened (for logging/metrics):
        ``"idle"`` (no due row, or every due row's thread is locked by
        another worker), ``"sent"``, ``"aborted_human"``, ``"window_closed"``,
        ``"retry"``, ``"failed"``, ``"fenced"`` (lease lost mid-flight —
        aborted before any externally-visible action).
    """
    # 1. Reclaim stale claims (best-effort, outside the claim TX). Covers both
    #    'claimed' (crash before/at send) and 'generating' (crash mid bot
    #    generation, P5) — a live worker's row never hits this because the
    #    heartbeat keeps claim_expires_at fresh during generation.
    await pool.execute(
        """
        UPDATE wa_outbox
        SET status = 'pending', claim_token = NULL, claimed_at = NULL,
            claim_expires_at = NULL
        WHERE status IN ('claimed', 'generating') AND claim_expires_at < NOW()
        """,
    )

    claim_token = uuid.uuid4()

    async with pool.acquire() as conn:
        # 2. Claim one due pending row whose thread is not already owned by
        #    another worker. FOR UPDATE SKIP LOCKED gives row-level
        #    single-flight over the candidate scan; the per-thread advisory
        #    lock (P3) gives single-flight over the *thread* across different
        #    rows — see module docstring for why this is session-scoped
        #    (pg_try_advisory_lock), not xact-scoped.
        claimed_row: asyncpg.Record | None = None
        thread_id_for_lock: int | None = None
        async with conn.transaction():
            candidates = await conn.fetch(
                """
                SELECT id, thread_id, message_id, needs_generation, attempts
                FROM wa_outbox
                WHERE status = 'pending' AND next_retry_at <= NOW()
                ORDER BY next_retry_at, id
                FOR UPDATE SKIP LOCKED
                LIMIT $1
                """,
                CLAIM_CANDIDATE_LIMIT,
            )
            for candidate in candidates:
                # $1 is typed TEXT by the || concat — asyncpg refuses int (P0 2026-07-19)
                acquired = await conn.fetchval(
                    f"SELECT pg_try_advisory_lock({_THREAD_LOCK_KEY_SQL})",
                    str(candidate["thread_id"]),
                )
                if not acquired:
                    # Another worker already owns this thread — leave the row
                    # pending (SKIP LOCKED already released it at TX end) and
                    # try the next candidate.
                    continue
                await conn.execute(
                    """
                    UPDATE wa_outbox
                    SET status = 'claimed', claim_token = $2, claimed_at = NOW(),
                        claim_expires_at = NOW() + ($3 * INTERVAL '1 second')
                    WHERE id = $1
                    """,
                    candidate["id"],
                    claim_token,
                    CLAIM_LEASE_SECONDS,
                )
                claimed_row = candidate
                thread_id_for_lock = candidate["thread_id"]
                break

        if claimed_row is None:
            return "idle"

        try:
            return await _process_claimed_row(
                conn,
                claimed_row,
                claim_token,
                whatsapp_service,
                bot_generate_fn,
                pool=pool,
            )
        finally:
            # MUST always run: this is a session-scoped advisory lock on a
            # POOLED connection. If we don't release it here, the lock stays
            # held by that Postgres backend session for as long as the
            # connection lives in the pool — silently wedging every future
            # claim attempt on this thread from ANY worker that happens to
            # reuse this connection. (family #2 "esiste ≠ armato" shape: a
            # missing finally here would be invisible until threads mysteriously
            # stop getting replies.)
            try:
                # $1 is typed TEXT by the || concat — asyncpg refuses int (P0 2026-07-19)
                await conn.execute(
                    f"SELECT pg_advisory_unlock({_THREAD_LOCK_KEY_SQL})",
                    str(thread_id_for_lock),
                )
            except Exception:
                logger.exception(
                    "wa_outbox: failed to release advisory lock for thread %s "
                    "(connection likely unusable; will not be reused)",
                    thread_id_for_lock,
                )


async def _process_claimed_row(
    conn: asyncpg.Connection,
    row: asyncpg.Record,
    claim_token: uuid.UUID,
    whatsapp_service: Any,
    _bot_generate_fn: BotGenerateFn,
    *,
    pool: asyncpg.Pool,
) -> str:
    """Everything after a row is claimed and its thread lock is held.

    ``pool`` is needed by the codex broker leg only (``wait_for_job`` runs
    its deadline CAS on its own acquired connections; the thread-context
    loader acquires its own too) — everything else on this path stays on
    ``conn`` under the advisory lock.

    ``_bot_generate_fn`` (Gemini, ``wa_inbox_bot.generate_bot_reply`` in
    prod) is accepted but deliberately NEVER CALLED as of the Gemini-cut PR
    (2026-08-27, Zero: "spegni gemini e collega chatgpt") — kept as a
    parameter only so ``process_outbox_once``'s public signature and every
    existing test/caller shape stay unchanged. See the generation section
    below for what runs instead.
    """
    outbox_id = row["id"]
    thread_id = row["thread_id"]
    message_id = row["message_id"]
    needs_generation = row["needs_generation"]
    attempts = row["attempts"]

    # ``expected_status`` tracks wa_outbox.status as WE believe it to be after
    # our own last successful fenced transition — every subsequent fenced
    # UPDATE checks against it, and is updated only after that UPDATE itself
    # confirms (via RETURNING) that it actually matched.
    expected_status = "claimed"

    # 3. Coalescing (P2) — before doing anything else, drop redundant pending
    #    bot-reply rows of this thread. Safe from races: we hold the
    #    per-thread advisory lock, so no other worker can claim a same-thread
    #    row out from under this sweep.
    if needs_generation:
        await _coalesce_thread_bursts(conn, thread_id, outbox_id)

    # Load the thread (human_handling gate + 24h window source;
    # handling_version = the epoch the codex leg fences its offer against).
    thread = await conn.fetchrow(
        """
        SELECT thread_id, counterpart_phone, human_handling,
               last_customer_at, handling_version
        FROM meta_inbox_threads
        WHERE thread_id = $1
        """,
        thread_id,
    )
    if thread is None:
        # Should not happen (FK), but never park the row.
        fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox SET status = 'failed'
            WHERE id = $1 AND claim_token = $2 AND status = $3
            RETURNING id
            """,
            outbox_id,
            claim_token,
            expected_status,
        )
        if fenced is None:
            logger.warning("wa_outbox: fence lost before thread-missing failure (outbox=%s)", outbox_id)
            return "fenced"
        await conn.execute(
            """
            UPDATE meta_inbox_messages
            SET status = 'failed', error = 'thread_missing'
            WHERE id = $1
            """,
            message_id,
        )
        logger.error("wa_outbox: thread %s missing for outbox %s", thread_id, outbox_id)
        return "failed"

    # 4. Bot replies: re-check human_handling (takeover may have flipped it
    #    since the webhook enqueued this row).
    body_text: str
    if needs_generation:
        if thread["human_handling"]:
            fenced = await conn.fetchrow(
                """
                UPDATE wa_outbox SET status = 'failed'
                WHERE id = $1 AND claim_token = $2 AND status = $3
                RETURNING id
                """,
                outbox_id,
                claim_token,
                expected_status,
            )
            if fenced is None:
                logger.warning(
                    "wa_outbox: fence lost before pre-generation takeover abort (outbox=%s)",
                    outbox_id,
                )
                return "fenced"
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = 'aborted_human_takeover'
                WHERE id = $1
                """,
                message_id,
            )
            logger.info(
                "wa_outbox: aborted bot send for thread %s (human_handling=true)",
                thread_id,
            )
            return "aborted_human"

        fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox SET status = 'generating'
            WHERE id = $1 AND claim_token = $2 AND status = $3
            RETURNING id
            """,
            outbox_id,
            claim_token,
            expected_status,
        )
        if fenced is None:
            logger.warning("wa_outbox: fence lost before generating transition (outbox=%s)", outbox_id)
            return "fenced"
        expected_status = "generating"
        await conn.execute(
            "UPDATE meta_inbox_messages SET status = 'generating' WHERE id = $1",
            message_id,
        )

        # Concierge ack (C3) — fire right as generation starts, before the
        # potentially slow codex-leg call below. Fully self-contained
        # (idempotent, takeover/window-aware, never raises) — see docstring.
        await _maybe_send_ack(conn, outbox_id, claim_token, thread, whatsapp_service)

        # The generation step below may raise (transient RAG/broker error,
        # a standing condition, or — with Gemini cut — a fall-off/fail from
        # the codex leg). Without this guard the exception bubbles to the
        # scheduler and the row is left ORPHANED in 'generating' (reclaim
        # only resets 'claimed' rows), so it is never retried nor surfaced.
        # Mirror the send retry/backoff policy: retry with backoff up to
        # MAX_ATTEMPTS, then mark failed.
        #
        # P5/P6: the heartbeat below renews claim_expires_at every ~60s for
        # the duration of this await so a slow (but alive) generation is
        # never reclaimed out from under this worker. It runs on the SAME
        # connection as the rest of this function; that is only safe because
        # generation does not touch this connection while it runs —
        # wa_codex_leg.attempt is pool-only BY CONTRACT (it is not even
        # handed this connection; asyncpg allows one operation in flight per
        # connection, so sharing it would race the heartbeat into
        # InterfaceError). The heartbeat is always cancelled and
        # awaited-to-completion in `finally`, BEFORE the exception/success
        # handling below touches `conn` again, so there is never a
        # concurrent query in flight on this connection.
        heartbeat_task = asyncio.create_task(
            _lease_heartbeat_loop(conn, outbox_id, claim_token)
        )
        gen_exc: Exception | None = None
        codex_stand_down = False
        try:
            # Codex broker leg (BOT-V4 S2 PR-5) — the ONLY generation path
            # left on this worker (2026-08-27, Zero: "spegni gemini e
            # collega chatgpt" — the WhatsApp channel no longer generates
            # with Gemini, full stop; `bot_generate_fn`/`generate_bot_reply`
            # is retained as an injected parameter for test/back-compat
            # shape only and is never called from here). attempt() never
            # raises and answers in one of four shapes (its module
            # docstring is the contract): text (send it) · stand_down
            # (drift verdict — the leg already terminalized the row
            # atomically, NO generation may replace it) · fall-off (a
            # CERTAIN pre-durable outcome — gates, build, offer admission)
            # · fail (an UNCERTAIN outcome at/after a durable boundary).
            # Historically fall-off "cost zero retry attempts" because
            # Gemini answered in the same claim; with Gemini cut there is
            # no second generator to hand it to, so BOTH fall-off and fail
            # now take the SAME retry ladder below — except the two
            # fall-off reasons that are standing conditions in disguise
            # (see `_CODEX_LEG_STANDING_REASONS`), which raise
            # BotStandingCondition instead, exactly as the Gemini leg used
            # to. #5093 (dependency of this change, see the PR body) gives
            # `offer_job` a real retry budget — REATTACHED/fresh-OFFERED
            # instead of an eternal ALREADY_SPENT — so a retried claim can
            # make actual progress on the codex route instead of spinning
            # on the same fall-off every attempt.
            body_text = ""
            if not wa_codex_leg.provider_is_codex():
                # WA_GENERATION_PROVIDER is the owner's switch alone (bot
                # corner doctrine — the S4 cutover). Unset, or anything
                # other than "codex", now means "generate nothing this
                # attempt", never "fall back to Gemini". A standing
                # condition, not an incident: the env is re-read live on
                # every claim, so arming the switch mid-backoff rescues the
                # row on the very next attempt — same recovery shape as the
                # WA_INBOX_BOT_AUTOREPLY flag below.
                #
                # This is the ONE fall-off condition the codex leg itself
                # never sees (the leg is not even called), so it is the
                # one place outside wa_codex_leg.attempt() that must record
                # its own durable reason (migration 290) — best-effort,
                # same as every reason attempt() records internally.
                await wa_codex_leg.record_fall_off_reason(
                    pool, outbox_id=outbox_id, raw_reason="provider_not_codex"
                )
                raise BotStandingCondition(
                    "wa-inbox bot: gemini generation retired for whatsapp "
                    "(WA_GENERATION_PROVIDER != 'codex')"
                )
            leg = await wa_codex_leg.attempt(
                pool,
                outbox_id=outbox_id,
                thread_id=thread_id,
                message_id=message_id,
                claim_token=claim_token,
                outbox_expected_status=expected_status,
                thread=thread,
            )
            if leg.stand_down:
                codex_stand_down = True
            elif leg.fail:
                raise RuntimeError(f"codex_leg_failure:{leg.fail}")
            elif leg.text is not None:
                body_text = leg.text
                logger.info(
                    "wa_outbox: codex leg served outbox=%s", outbox_id
                )
            elif leg.reason in _CODEX_LEG_STANDING_REASONS:
                # SilentStandingCondition, not the plain BotStandingCondition:
                # these two mirror the Gemini leg's OWN silent exits (flag off /
                # no customer message) — must notify NOBODY, client or human
                # (2026-08-27 Kimi K3 adversarial finding, BLOCCANTE).
                raise SilentStandingCondition(
                    f"wa-inbox bot: codex leg standing ({leg.reason})"
                )
            else:
                raise RuntimeError(f"codex_leg_fell_off:{leg.reason}")
        except Exception as exc:  # deliberately broad — see the retry/failed handling below
            gen_exc = exc
            body_text = ""
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

        if codex_stand_down:
            # The leg ALREADY terminalized the row: its drift verdict runs
            # the fenced wa_outbox abort, the completion discard and the
            # 'aborted_human_takeover_codex_drift' ledger sentinel in ONE
            # transaction (Codex r2 finding 3 — two separate commits left
            # a crash window where the reclaimer would requeue a row whose
            # verdict said never-regenerate). Nothing to mutate here; the
            # sentinel keeps this abort class distinguishable from the
            # pre-generation and pre-send takeover aborts.
            logger.info(
                "wa_outbox: aborted codex row for thread %s "
                "(takeover/epoch drift during broker exec)",
                thread_id,
            )
            return "aborted_human"

        if gen_exc is not None:
            # A STANDING condition — auto-reply switched off, or no customer
            # message in the loaded window — is a statement about system state,
            # not about this attempt. The retry ladder is DELIBERATELY UNCHANGED
            # for it: `WA_INBOX_BOT_AUTOREPLY` is read from the environment on
            # every call, so a rollout that flips it ON mid-backoff still
            # rescues the row, and ~7 minutes is well inside a reasonable
            # WhatsApp reply window. Only the LEDGER TEXT differs.
            #
            # Measured 2026-07-27: of 52 give-ups ever recorded, 44 were the
            # flag being off for two weeks in June and 5 were "no customer
            # message" — all filed under the same sentinel as a genuine crash,
            # which is what made the ledger unreadable. This is a diagnostic
            # fix, not a cost one: the flag check is the first statement of
            # generate_bot_reply, so those retries burned zero generations.
            standing = isinstance(gen_exc, BotStandingCondition)
            attempts += 1
            if attempts >= MAX_ATTEMPTS:
                fenced = await conn.fetchrow(
                    """
                    UPDATE wa_outbox SET status = 'failed', attempts = $2
                    WHERE id = $1 AND claim_token = $3 AND status = $4
                    RETURNING id
                    """,
                    outbox_id,
                    attempts,
                    claim_token,
                    expected_status,
                )
                if fenced is None:
                    logger.warning(
                        "wa_outbox: fence lost before terminal gen-failure (outbox=%s)", outbox_id
                    )
                    return "fenced"
                await conn.execute(
                    """
                    UPDATE meta_inbox_messages
                    SET status = 'failed', error = $2
                    WHERE id = $1
                    """,
                    message_id,
                    (
                        f"bot_standing_condition_after_{attempts}_attempts: {gen_exc}"
                        if standing
                        else f"bot_generate_failed_after_{attempts}_attempts: {gen_exc}"
                    ),
                )
                if standing:
                    # INFO, not ERROR: "the bot is switched off" is a
                    # configuration state, and paging on it is what trained
                    # everyone to ignore this log line during the June window.
                    logger.info(
                        "wa_outbox: bot generation gave up on a standing "
                        "condition (outbox=%s thread=%s): %s",
                        outbox_id,
                        thread_id,
                        gen_exc,
                    )
                else:
                    logger.error(
                        "wa_outbox: bot generation failed permanently "
                        "(outbox=%s thread=%s): %s",
                        outbox_id,
                        thread_id,
                        gen_exc,
                    )
                # Apology (C4) — best-effort, never masks the failure above
                # (already recorded on both ledgers by this point). A real
                # failure, or `provider_not_codex` (WA_GENERATION_PROVIDER
                # unarmed — a misconfiguration that needs fixing regardless),
                # DOES get the apology + human alert. A `SilentStandingCondition`
                # (`autoreply_disabled` / `no_customer_message`) explicitly does
                # NOT — those two mirror wa_inbox_bot.generate_bot_reply's own
                # two silent exits, which by pre-existing, documented contract
                # notify nobody (see `_tell_a_human`'s docstring and
                # `SilentStandingCondition`'s own): "the bot is intentionally
                # off right now" or "nothing to answer" is not an incident, and
                # an apology/Telegram alert firing for it would invert that
                # contract — a "switch it off" flag that produces client-facing
                # messages is not a switch (2026-08-27 Kimi K3 adversarial
                # review, coordinator-weighted BLOCCANTE — the first draft of
                # this change fired the apology for every standing condition,
                # which is exactly the regression this comment used to defend).
                if not isinstance(gen_exc, SilentStandingCondition):
                    await _maybe_send_apology(
                        conn, outbox_id, thread, whatsapp_service,
                        reason="bot_standing_condition" if standing else "bot_generation_exhausted",
                    )
                return "failed"

            backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
            fenced = await conn.fetchrow(
                """
                UPDATE wa_outbox
                SET status = 'pending', attempts = $2,
                    next_retry_at = NOW() + ($3 * INTERVAL '1 second'),
                    claim_token = NULL, claimed_at = NULL, claim_expires_at = NULL
                WHERE id = $1 AND claim_token = $4 AND status = $5
                RETURNING id
                """,
                outbox_id,
                attempts,
                backoff,
                claim_token,
                expected_status,
            )
            if fenced is None:
                logger.warning(
                    "wa_outbox: fence lost before gen-failure retry requeue (outbox=%s)", outbox_id
                )
                return "fenced"
            await conn.execute(
                "UPDATE meta_inbox_messages SET status = 'queued' WHERE id = $1",
                message_id,
            )
            logger.warning(
                "wa_outbox: bot generation failed (attempt %d/%d), retry in %ds "
                "(outbox=%s): %s",
                attempts,
                MAX_ATTEMPTS,
                backoff,
                outbox_id,
                gen_exc,
            )
            return "retry"

        await conn.execute(
            "UPDATE meta_inbox_messages SET body = $2 WHERE id = $1",
            message_id,
            body_text,
        )
    else:
        # Human send: the body is already on the ledger row.
        ledger = await conn.fetchrow(
            "SELECT body FROM meta_inbox_messages WHERE id = $1",
            message_id,
        )
        body_text = (ledger["body"] if ledger else None) or ""

    # 5. Pre-send fence (P4): re-confirm this worker still owns the lease
    #    RIGHT before the irreversible Graph send, in the same transaction as
    #    a fresh read of human_handling. This is what actually closes the
    #    takeover-during-generation race — the earlier pre-generation check
    #    (step 4 above) only catches a takeover that happened BEFORE
    #    generation started.
    async with conn.transaction():
        fence_row = await conn.fetchrow(
            """
            UPDATE wa_outbox
            SET claim_expires_at = NOW() + ($4 * INTERVAL '1 second')
            WHERE id = $1 AND claim_token = $2 AND status = $3
            RETURNING id
            """,
            outbox_id,
            claim_token,
            expected_status,
            CLAIM_LEASE_SECONDS,
        )
        human_handling_now = False
        if fence_row is not None and needs_generation:
            human_handling_now = bool(
                await conn.fetchval(
                    "SELECT human_handling FROM meta_inbox_threads WHERE thread_id = $1",
                    thread_id,
                )
            )

    if fence_row is None:
        logger.warning("wa_outbox: pre-send fence lost (outbox=%s status=%s)", outbox_id, expected_status)
        return "fenced"

    if needs_generation and human_handling_now:
        # Operator took over WHILE we were generating — the reply we just
        # produced must NEVER be sent.
        await conn.execute(
            """
            UPDATE wa_outbox SET status = 'failed'
            WHERE id = $1 AND claim_token = $2 AND status = $3
            """,
            outbox_id,
            claim_token,
            expected_status,
        )
        await conn.execute(
            """
            UPDATE meta_inbox_messages
            SET status = 'failed', error = 'aborted_human_takeover_pre_send'
            WHERE id = $1
            """,
            message_id,
        )
        logger.info(
            "wa_outbox: aborted pre-send for thread %s (human_handling flipped true during generation)",
            thread_id,
        )
        return "aborted_human"

    # 6. Enforce the Meta 24h customer-care window.
    window_open = await conn.fetchval(
        """
        SELECT last_customer_at IS NOT NULL
           AND NOW() - last_customer_at < ($2 * INTERVAL '1 hour')
        FROM meta_inbox_threads
        WHERE thread_id = $1
        """,
        thread_id,
        CUSTOMER_WINDOW_HOURS,
    )
    if not window_open:
        fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox SET status = 'failed'
            WHERE id = $1 AND claim_token = $2 AND status = $3
            RETURNING id
            """,
            outbox_id,
            claim_token,
            expected_status,
        )
        if fenced is None:
            logger.warning("wa_outbox: fence lost before window-closed failure (outbox=%s)", outbox_id)
            return "fenced"
        await conn.execute(
            """
            UPDATE meta_inbox_messages
            SET status = 'failed', error = '24h_window_closed'
            WHERE id = $1
            """,
            message_id,
        )
        logger.info("wa_outbox: 24h window closed for thread %s", thread_id)
        return "window_closed"

    # 7. Send via Graph (whatsapp_service hardcodes the target number).
    await conn.execute(
        "UPDATE meta_inbox_messages SET status = 'sending' WHERE id = $1",
        message_id,
    )
    try:
        send_result = await whatsapp_service.send_message(
            phone=thread["counterpart_phone"],
            text=body_text,
            reply_to_message_id=None,
        )
    except Exception as exc:
        attempts += 1
        if attempts >= MAX_ATTEMPTS:
            fenced = await conn.fetchrow(
                """
                UPDATE wa_outbox SET status = 'failed', attempts = $2
                WHERE id = $1 AND claim_token = $3 AND status = $4
                RETURNING id
                """,
                outbox_id,
                attempts,
                claim_token,
                expected_status,
            )
            if fenced is None:
                logger.warning("wa_outbox: fence lost before terminal send-failure (outbox=%s)", outbox_id)
                return "fenced"
            await conn.execute(
                """
                UPDATE meta_inbox_messages
                SET status = 'failed', error = $2
                WHERE id = $1
                """,
                message_id,
                f"send_failed_after_{attempts}_attempts: {exc}",
            )
            logger.error(
                "wa_outbox: send failed permanently (outbox=%s thread=%s): %s",
                outbox_id,
                thread_id,
                exc,
            )
            # Apology (C4) — best-effort. Note the Graph API itself is what
            # just failed, so this attempt may also fail; that's fine, it's
            # swallowed by _maybe_send_apology and never masks the failure
            # already recorded above.
            await _maybe_send_apology(
                conn, outbox_id, thread, whatsapp_service, reason="graph_send_exhausted"
            )
            return "failed"

        backoff = RETRY_BACKOFF_BASE_SECONDS * (2 ** (attempts - 1))
        fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox
            SET status = 'pending', attempts = $2,
                next_retry_at = NOW() + ($3 * INTERVAL '1 second'),
                claim_token = NULL, claimed_at = NULL, claim_expires_at = NULL
            WHERE id = $1 AND claim_token = $4 AND status = $5
            RETURNING id
            """,
            outbox_id,
            attempts,
            backoff,
            claim_token,
            expected_status,
        )
        if fenced is None:
            logger.warning("wa_outbox: fence lost before send-failure retry requeue (outbox=%s)", outbox_id)
            return "fenced"
        logger.warning(
            "wa_outbox: send failed (attempt %d/%d), retry in %ds (outbox=%s): %s",
            attempts,
            MAX_ATTEMPTS,
            backoff,
            outbox_id,
            exc,
        )
        return "retry"

    # 8. The Graph send has now IRREVERSIBLY happened. Everything below is
    #    best-effort bookkeeping — if the fenced commit below loses the race
    #    (lease reclaimed in the tiny window between the pre-send fence and
    #    here), we do NOT report "fenced" (that would imply nothing happened
    #    externally, which is false: a message was sent). This is the
    #    documented residual double-send window (spec P5): a crash or a lost
    #    fence exactly here can leave the ledger unable to record 'sent',
    #    and a reclaimer could hand the row to a second worker that sends
    #    again. We do not implement reconciliation for this — the idea
    #    (spec P5) is a periodic job that folds a matching wamid status
    #    receipt into any 'sending'-stuck row older than N minutes; that is
    #    out of scope for F1a.
    wamid = _extract_wamid(send_result)
    async with conn.transaction():
        commit_fenced = await conn.fetchrow(
            """
            UPDATE wa_outbox SET status = 'done'
            WHERE id = $1 AND claim_token = $2 AND status = $3
            RETURNING id
            """,
            outbox_id,
            claim_token,
            expected_status,
        )
        await conn.execute(
            """
            UPDATE meta_inbox_messages
            SET status = 'sent', meta_message_id = $2, sent_at = NOW()
            WHERE id = $1
            """,
            message_id,
            wamid,
        )
        # Fold any status receipt that raced ahead of the send commit.
        if wamid:
            await _apply_pending_status(conn, wamid)

    if commit_fenced is None:
        logger.error(
            "wa_outbox: RESIDUAL DOUBLE-SEND WINDOW hit — message was sent (wamid=%s) "
            "but the lease for outbox=%s was already lost by commit time; the ledger "
            "row was still updated to 'sent' above. thread=%s",
            wamid,
            outbox_id,
            thread_id,
        )

    logger.info(
        "wa_outbox: sent (outbox=%s thread=%s wamid=%s)",
        outbox_id,
        thread_id,
        wamid,
    )
    return "sent"
