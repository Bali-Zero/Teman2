"""Coalescing must not silently kill a row that already generated an answer.

Measured in production 2026-08-28 (thread 394, `wa_outbox` row 363): ChatGPT
produced an answer THREE times — every broker job `consumed_ok`, 9711/10137/
8521 ms — the finalize pipeline rejected all three, and the row sat at
attempts 3 of MAX_ATTEMPTS waiting for its 4th try. A follow-up message
arrived 3m27s later and `_coalesce_thread_bursts` marked the row `failed`.
No answer, no apology (that sweep never reaches `_maybe_send_apology`), no
alert.

This runs the REAL sweep against a REAL Postgres rather than asserting on SQL
text: a predicate is only worth what the database does with it, and a text
assertion would keep passing if someone rewrote the query.
"""

from __future__ import annotations

import asyncpg
import pytest

from backend.services.integrations.wa_outbox_worker import _coalesce_thread_bursts


async def _seed(db_tx: asyncpg.Connection) -> tuple[int, dict[str, int]]:
    """A thread with three pending bot-reply rows, one per shape under test."""
    thread_id = await db_tx.fetchval(
        "INSERT INTO meta_inbox_threads (counterpart_phone) VALUES ($1) "
        "RETURNING thread_id",
        "+000000000000",  # synthetic, never a real number
    )
    ids: dict[str, int] = {}
    for label, attempts, needs_generation in (
        ("winner", 0, True),
        ("fresh_burst", 0, True),
        ("already_generated", 3, True),
        ("human_send", 0, False),
    ):
        message_id = await db_tx.fetchval(
            "INSERT INTO meta_inbox_messages (thread_id, direction, sender_role) "
            "VALUES ($1, 'inbound', 'customer') RETURNING id",
            thread_id,
        )
        ids[label] = await db_tx.fetchval(
            "INSERT INTO wa_outbox (thread_id, message_id, needs_generation, "
            "status, attempts) VALUES ($1, $2, $3, 'pending', $4) RETURNING id",
            thread_id,
            message_id,
            needs_generation,
            attempts,
        )
    return thread_id, ids


@pytest.mark.asyncio
async def test_coalescing_spares_a_row_that_already_generated(
    db_tx: asyncpg.Connection,
) -> None:
    thread_id, ids = await _seed(db_tx)

    superseded = await _coalesce_thread_bursts(db_tx, thread_id, ids["winner"])

    status = {
        label: await db_tx.fetchval(
            "SELECT status FROM wa_outbox WHERE id = $1", outbox_id
        )
        for label, outbox_id in ids.items()
    }

    # The one this test exists for: attempts > 0 means real work already
    # happened, so the row keeps its ladder and will end in an answer or an
    # apology — never in silence.
    assert status["already_generated"] == "pending"

    # Unchanged behaviour, asserted so this guard cannot be "satisfied" by
    # disabling coalescing altogether.
    assert status["fresh_burst"] == "failed"
    assert status["winner"] == "pending"
    assert status["human_send"] == "pending"
    assert superseded == 1


@pytest.mark.asyncio
async def test_coalescing_still_supersedes_a_true_burst(
    db_tx: asyncpg.Connection,
) -> None:
    """Innocence: the normal case — several messages seconds apart, none of
    them started — must still collapse to a single reply."""
    thread_id = await db_tx.fetchval(
        "INSERT INTO meta_inbox_threads (counterpart_phone) VALUES ($1) "
        "RETURNING thread_id",
        "+000000000001",
    )
    outbox_ids: list[int] = []
    for _ in range(3):
        message_id = await db_tx.fetchval(
            "INSERT INTO meta_inbox_messages (thread_id, direction, sender_role) "
            "VALUES ($1, 'inbound', 'customer') RETURNING id",
            thread_id,
        )
        outbox_ids.append(
            await db_tx.fetchval(
                "INSERT INTO wa_outbox (thread_id, message_id, needs_generation, "
                "status, attempts) VALUES ($1, $2, true, 'pending', 0) RETURNING id",
                thread_id,
                message_id,
            )
        )

    superseded = await _coalesce_thread_bursts(db_tx, thread_id, outbox_ids[0])

    assert superseded == 2
    remaining = await db_tx.fetchval(
        "SELECT count(*) FROM wa_outbox WHERE thread_id = $1 AND status = 'pending'",
        thread_id,
    )
    assert remaining == 1
