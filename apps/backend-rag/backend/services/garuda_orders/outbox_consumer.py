"""Drains `garuda_order_outbox` — the queue that has never had a consumer.

`journal.enqueue_outbox` has ten callers in `repository.py` (checkout_ready_email,
payment_paid_email, payment_failed_email, refund_email, practice_release and the
five staff_page_* jobs). Nothing anywhere in this repository has ever SELECTed
that table outside a test. Every row written since the table shipped is still
sitting there with `dispatched_at IS NULL`: a customer who pays today receives no
confirmation, because there is no code that could send one. This module is the
missing half.

WHY THE LOCK IS HELD ACROSS THE HANDLER (the one design decision that matters).
`UNIQUE (journal_event_id, job_type)` makes "email once" structural on the WRITE
side; nothing makes it structural on the DISPATCH side. If this consumer bumped
`attempts`, committed, and only then ran the handler, the row would be unlocked
while the email was in flight and a second worker could claim and send it again.
So one job = one transaction, and the transaction spans the handler. The cost is
paid honestly: a handler that raises has its `attempts` bump committed (the
`except` is INSIDE the transaction, so the bump survives), while a hard process
crash mid-send rolls the bump back and the job is retried. Duplicate-send is the
worse failure for a customer-facing email, so it is the one we exclude.

WHAT THIS MODULE REFUSES TO DO SILENTLY (superscar #2 / W81b — the DLQ corpses
nobody ever cleaned, and W53 — the missing TERMINAL gate). A job that exhausts
`max_attempts` is NOT deleted, NOT marked dispatched, and NOT quietly filtered
out of existence. It stops being claimed, and `count_undrained` reports it under
`exhausted` so a probe can go red. The same holds for a job whose `job_type` has
no registered handler: it is counted as `unroutable` and logged by name, never
consumed. An outbox that empties itself by forgetting is worse than one that
never ran, because the first looks healthy.

WHY THERE IS NO AGE-BASED DROP. The house pattern next door
(`war_room/wr2_outbox_consumer.py`) filters `created_at > NOW() - INTERVAL '72
hours'`, which means a job older than three days silently ceases to exist while
the stats call it `skipped_stale`. For a customer's payment confirmation that is
a lost email with a green log line. Age here only ever *reports* (see
`count_undrained`); it never excludes.

ARMED STATE. `is_consumer_enabled()` fails closed: anything but the literal
string "true" leaves this disarmed, matching the frontend's
`isGarudaVoaPublicEnabled`. Nothing schedules this module yet — wiring a worker
or a cron to it is a separate, deliberate act. Built is not armed.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import asyncpg

logger = logging.getLogger("garuda.orders.outbox_consumer")

OUTBOX_TABLE = "garuda_order_outbox"

DEFAULT_BATCH_SIZE = 20
DEFAULT_MAX_ATTEMPTS = 5

KILL_SWITCH_ENV = "GARUDA_OUTBOX_CONSUMER_ENABLED"


def is_consumer_enabled(env: dict[str, str] | None = None) -> bool:
    """True only for the exact string "true" — every other value disarms.

    Fail-closed on purpose: an unset variable, a typo, "1", "yes" and "TRUE"
    all leave the consumer off. A queue that starts draining because someone
    exported a truthy-looking string is not a queue anyone controls.
    """

    source = os.environ if env is None else env
    return source.get(KILL_SWITCH_ENV) == "true"


@dataclass(frozen=True, slots=True)
class OutboxJob:
    """One claimed row, decoded. `attempts` is the value AFTER this claim's bump."""

    id: int
    order_id: str
    journal_event_id: str
    job_type: str
    payload: dict[str, Any]
    attempts: int


Handler = Callable[["OutboxJob"], Awaitable[None]]
"""A handler signals success by returning and failure by RAISING.

There is deliberately no boolean return channel. `return False` makes "I did
nothing" and "I failed" indistinguishable at the call site, and the neighbouring
WR2 consumer shows where that leads: a handler that quietly returns a falsy
value is counted as `failed` with no exception, no traceback and no reason in
the log. Raise, and the reason is recorded.
"""


class _Rollback(Exception):
    """Internal: abort one job's transaction without failing the drain pass."""


@dataclass(frozen=True, slots=True)
class DrainStats:
    """Outcome of one drain pass. Every claimed job lands in exactly one bucket."""

    claimed: int = 0
    dispatched: int = 0
    failed: int = 0
    unroutable: int = 0
    unroutable_types: frozenset[str] = field(default_factory=frozenset)

    @property
    def accounted(self) -> int:
        return self.dispatched + self.failed + self.unroutable


async def _claim_one(
    conn: asyncpg.Connection, *, max_attempts: int, exclude_ids: list[int]
) -> asyncpg.Record | None:
    """Claim the oldest undispatched, non-exhausted row and bump its attempt count.

    `FOR UPDATE SKIP LOCKED` is what makes more than one worker safe: a row another
    transaction already holds is stepped over rather than waited on. `LIMIT 1` is
    not a throughput oversight — batching several rows into one transaction would
    let a single poison job roll back its innocent siblings.

    `exclude_ids` carries the rows this drain pass has already touched, and it is
    load-bearing rather than an optimisation. A failed job stays `dispatched_at
    IS NULL` and an unroutable one has its attempt bump rolled back, so without
    this filter both are immediately eligible again on the very next iteration:
    one poisoned job would burn its whole `max_attempts` budget inside a single
    pass in milliseconds (destroying the point of a retry limit, which is to
    spread attempts over TIME), and one unroutable job would be re-claimed for
    every slot in the batch, starving every other job behind it. Measured on the
    first run of this module's own suite: 5 attempts consumed in 0.03s, and 20
    claims of one unroutable row in a batch of 20.
    """

    return await conn.fetchrow(
        f"""
        UPDATE {OUTBOX_TABLE} AS o
           SET attempts = o.attempts + 1
         WHERE o.id = (
                SELECT c.id
                  FROM {OUTBOX_TABLE} AS c
                 WHERE c.dispatched_at IS NULL
                   AND c.attempts < $1
                   AND NOT (c.id = ANY($2::bigint[]))
                 ORDER BY c.created_at ASC, c.id ASC
                 LIMIT 1
                 FOR UPDATE SKIP LOCKED
               )
     RETURNING o.id, o.order_id, o.journal_event_id, o.job_type,
               o.payload, o.attempts
        """,
        max_attempts,
        exclude_ids,
    )


def _decode(row: asyncpg.Record) -> OutboxJob:
    raw = row["payload"]
    payload = json.loads(raw) if isinstance(raw, str) else (raw or {})
    return OutboxJob(
        id=row["id"],
        order_id=row["order_id"],
        journal_event_id=row["journal_event_id"],
        job_type=row["job_type"],
        payload=payload,
        attempts=row["attempts"],
    )


async def drain_once(
    conn: asyncpg.Connection,
    handlers: dict[str, Handler],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
) -> DrainStats:
    """Claim and dispatch up to `batch_size` jobs, one transaction each.

    Returns without touching the database when the kill switch is off — an
    explicitly disarmed consumer must not hold connections or take locks.

    A job whose `job_type` is absent from `handlers` is left exactly as found:
    not dispatched, and its attempt bump rolled back, so registering the handler
    later picks it up with a full attempt budget rather than one already spent
    down by passes that never even tried to deliver it.

    `batch_size` costs more than linear WHEN JOBS FAIL, and this is worth
    stating precisely because the obvious reading is wrong. The per-pass
    exclusion list (see `_claim_one`) is an unindexable `NOT (id = ANY(...))`,
    but a job that DISPATCHES gets `dispatched_at` set and thereby leaves
    `idx_garuda_order_outbox_undispatched` — a partial index on `(created_at)
    WHERE dispatched_at IS NULL` — so the happy path stays linear and the
    exclusion list never has to be walked for it. What the list actually pays
    for are the rows this pass touched and LEFT undispatched (failed and
    unroutable ones): each remains in the index, so every later claim in the
    same pass scans past all of them. The cost is therefore
    O(batch_size * undispatched_touched), i.e. quadratic only in a pass that
    is failing wholesale. At the default of 20 even the worst case is a few
    hundred comparisons; a caller passing thousands into a failing queue is
    the one shape where this bites, and should call `drain_once` repeatedly
    instead. No ceiling is enforced because the right one depends on the
    deployment.

    CANCELLATION IS NOT A HANDLER FAILURE. The `except Exception` around the
    handler deliberately does not catch `BaseException`, so an
    `asyncio.CancelledError` (worker shutdown, task cancellation) propagates
    out of the transaction — rolling back that job's attempt bump — and then
    out of `drain_once` itself, abandoning the rest of the batch. That is the
    intended behaviour: a cancelled worker must stop, not quietly continue
    delivering customer email, and the interrupted job must not be charged an
    attempt for work nobody asked it to finish.
    """

    if not is_consumer_enabled():
        logger.debug("outbox consumer disarmed (%s != 'true')", KILL_SWITCH_ENV)
        return DrainStats()

    claimed = dispatched = failed = unroutable = 0
    unroutable_types: set[str] = set()
    # Every row this pass has already touched. See `_claim_one`: a failed or
    # unroutable row is still eligible the instant its transaction ends, so
    # without this list one job monopolises the batch and spends its whole
    # retry budget in a single pass.
    touched_ids: list[int] = []
    # Log each unroutable job_type once per pass rather than once per row.
    logged_types: set[str] = set()

    for _ in range(batch_size):
        try:
            async with conn.transaction():
                row = await _claim_one(conn, max_attempts=max_attempts, exclude_ids=touched_ids)
                if row is None:
                    break
                job = _decode(row)
                claimed += 1
                touched_ids.append(job.id)

                handler = handlers.get(job.job_type)
                if handler is None:
                    unroutable += 1
                    unroutable_types.add(job.job_type)
                    if job.job_type not in logged_types:
                        logged_types.add(job.job_type)
                        logger.error(
                            "outbox job_type=%s has no registered handler; "
                            "job id=%s order_id=%s left undispatched",
                            job.job_type,
                            job.id,
                            job.order_id,
                        )
                    raise _Rollback  # undo the attempt bump: nothing was tried

                try:
                    await handler(job)
                except Exception:
                    # Caught INSIDE the transaction on purpose: the attempt bump
                    # must survive a handled failure, or a job that always fails
                    # would never reach `max_attempts` and never become visible.
                    failed += 1
                    logger.exception(
                        "outbox handler failed job_type=%s id=%s order_id=%s attempt=%s/%s",
                        job.job_type,
                        job.id,
                        job.order_id,
                        job.attempts,
                        max_attempts,
                    )
                else:
                    await conn.execute(
                        f"UPDATE {OUTBOX_TABLE} "
                        "SET dispatched_at = statement_timestamp() WHERE id = $1",
                        job.id,
                    )
                    dispatched += 1
        except _Rollback:
            continue

    return DrainStats(
        claimed=claimed,
        dispatched=dispatched,
        failed=failed,
        unroutable=unroutable,
        unroutable_types=frozenset(unroutable_types),
    )


async def count_undrained(
    conn: asyncpg.Connection, *, max_attempts: int = DEFAULT_MAX_ATTEMPTS
) -> dict[str, int]:
    """The numbers a probe needs to go red. Reports; never deletes, never hides.

    `exhausted` is the one that matters: those rows will never be claimed again
    by `drain_once`, so without this count they are invisible — which is exactly
    how fourteen DLQ corpses once sat unnoticed (W81b).
    """

    row = await conn.fetchrow(
        f"""
        SELECT
            count(*) FILTER (WHERE dispatched_at IS NULL)             AS undispatched,
            count(*) FILTER (WHERE dispatched_at IS NULL
                               AND attempts >= $1)                     AS exhausted,
            count(*) FILTER (WHERE dispatched_at IS NULL
                               AND created_at < statement_timestamp()
                                                - INTERVAL '1 hour')   AS older_than_1h,
            count(*) FILTER (WHERE dispatched_at IS NULL
                               AND created_at < statement_timestamp()
                                                - INTERVAL '24 hours') AS older_than_24h
          FROM {OUTBOX_TABLE}
        """,
        max_attempts,
    )
    if row is None:
        # A bare aggregate SELECT always returns exactly one row, so this is
        # unreachable — which is precisely why it must not be an `assert`.
        # `python -O` strips asserts, and the stripped version would fall
        # through to `dict(None)` and raise a bare TypeError instead of saying
        # what happened. An explicit raise survives every invocation mode.
        raise RuntimeError(
            f"aggregate SELECT over {OUTBOX_TABLE} returned no row; "
            "the database did not answer a query that cannot be empty"
        )
    return {k: int(v) for k, v in dict(row).items()}


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_MAX_ATTEMPTS",
    "KILL_SWITCH_ENV",
    "OUTBOX_TABLE",
    "DrainStats",
    "Handler",
    "OutboxJob",
    "count_undrained",
    "drain_once",
    "is_consumer_enabled",
]
