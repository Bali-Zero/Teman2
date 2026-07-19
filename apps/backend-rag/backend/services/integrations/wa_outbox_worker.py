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
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# Verified ground truth: the Meta WhatsApp Business number this inbox manages.
# settings.whatsapp_phone_number_id == this value == the send number, so the
# existing whatsapp_service sends from the correct number without parametrising.
META_INBOX_PHONE_NUMBER_ID = "1104946272705747"

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

# Meta free-text customer-care window.
CUSTOMER_WINDOW_HOURS = 24

# Type alias for the injected bot text generator. Given a thread row mapping it
# returns the reply text to send (or raises). Kept injectable so the worker has
# no hard dependency on the RAG orchestrator (and is trivially testable).
BotGenerateFn = Callable[[asyncpg.Record], Awaitable[str]]

# Reused by both the advisory-lock TRY and its matching UNLOCK — must stay
# identical so the two calls hash to the same lock key for a given thread_id.
_THREAD_LOCK_KEY_SQL = "hashtext('wa_outbox_thread_' || $1::text)"


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
    """Supersede other pending bot-reply rows of the same thread (P2).

    The generator always answers the *latest* thread message (see
    ``wa_inbox_bot._load_thread_context``), so whichever row of a same-thread
    burst gets claimed first, its generated reply already covers the whole
    burst — the other pending bot-reply rows would just be redundant sends.
    Only ``needs_generation`` rows are touched: a pending HUMAN send must
    never be silently dropped.
    """
    async with conn.transaction():
        superseded = await conn.fetch(
            """
            UPDATE wa_outbox
            SET status = 'failed'
            WHERE thread_id = $1
              AND status = 'pending'
              AND needs_generation = true
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
        bot_generate_fn: async callable producing the bot reply text for a
            thread (only invoked when ``needs_generation`` is true).

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
                conn, claimed_row, claim_token, whatsapp_service, bot_generate_fn
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
    bot_generate_fn: BotGenerateFn,
) -> str:
    """Everything after a row is claimed and its thread lock is held."""
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

    # Load the thread (human_handling gate + 24h window source).
    thread = await conn.fetchrow(
        """
        SELECT thread_id, counterpart_phone, human_handling,
               last_customer_at
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

        # bot_generate_fn may raise (transient RAG error, or — in the
        # human-send-only v1 — a NotImplementedError sentinel). Without this
        # guard the exception bubbles to the scheduler and the row is left
        # ORPHANED in 'generating' (reclaim only resets 'claimed' rows), so
        # it is never retried nor surfaced. Mirror the send retry/backoff
        # policy: retry with backoff up to MAX_ATTEMPTS, then mark failed.
        #
        # P5/P6: the heartbeat below renews claim_expires_at every ~60s for
        # the duration of this await so a slow (but alive) generation is
        # never reclaimed out from under this worker. It runs on the SAME
        # connection as the rest of this function; that is only safe because
        # bot_generate_fn (wa_inbox_bot.generate_bot_reply) never touches
        # this connection — it acquires its own from the pool internally and
        # talks to the RAG process over HTTP. The heartbeat is always
        # cancelled and awaited-to-completion in `finally`, BEFORE the
        # exception/success handling below touches `conn` again, so there is
        # never a concurrent query in flight on this connection.
        heartbeat_task = asyncio.create_task(
            _lease_heartbeat_loop(conn, outbox_id, claim_token)
        )
        gen_exc: Exception | None = None
        try:
            body_text = await bot_generate_fn(thread)
        except Exception as exc:  # deliberately broad — see the retry/failed handling below
            gen_exc = exc
            body_text = ""
        finally:
            heartbeat_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat_task

        if gen_exc is not None:
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
                    f"bot_generate_failed_after_{attempts}_attempts: {gen_exc}",
                )
                logger.error(
                    "wa_outbox: bot generation failed permanently "
                    "(outbox=%s thread=%s): %s",
                    outbox_id,
                    thread_id,
                    gen_exc,
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
