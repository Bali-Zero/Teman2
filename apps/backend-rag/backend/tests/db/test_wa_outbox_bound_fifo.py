"""B2.5 PR-1 — real-Postgres proof: one outbox row, one message, a burst
served each row in order (design evidence/2026-09/.../B2-5-design.md,
rulings a/b).

REPLACES ``test_wa_outbox_coalescing_spares_started_rows.py``:
``_coalesce_thread_bursts`` is gone (B2.5 folds nothing). What used to be
proven against a real Postgres — "a burst sibling is never superseded" — is
proven here instead, plus the two properties a mocked connection cannot
demonstrate:

  1. the claim SELECT's FIFO-per-thread predicate (migration 318's partial
     index) actually orders a real scan: an OLDER ``needs_generation`` row
     still pending/claimed/generating blocks a newer same-thread row from
     being claimed at all — a human send is neither blocked by it nor
     blocks it.
  2. every row is bound to its OWN inbound message
     (``wa_inbox_bot._load_bound_thread_context``), including the legacy
     derive picking the OLDER inbound even when a newer one exists.

Runs the REAL ``process_outbox_once`` claim/process loop against a
disposable Postgres, with the codex leg replaced by a fake that records
which inbound each attempt was bound to and returns synthetic text — no
network, no real generation, no client PII (synthetic phones/bodies only).
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import asyncpg
import pytest
import pytest_asyncio

from backend.services.integrations import wa_codex_leg, wa_outbox_worker
from backend.services.integrations.wa_inbox_bot import _load_bound_thread_context
from backend.services.integrations.wa_outbox_worker import process_outbox_once

_DEFAULT_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://nuzantara@localhost:5432/nuzantara_test",
)

_REQUIRED_TABLES = ("wa_outbox", "meta_inbox_threads", "meta_inbox_messages")
_REQUIRED_COLUMNS = (("wa_outbox", "inbound_message_id"),)


@pytest_asyncio.fixture(scope="function")
async def db_pool() -> asyncpg.Pool:
    try:
        pool = await asyncpg.create_pool(_DEFAULT_DB_URL, min_size=1, max_size=5)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"wa_outbox bound-FIFO tests: DB unreachable ({exc})")
        return  # help static analyzers see pool is unbound on this path

    skip_reason: str | None = None
    try:
        async with pool.acquire() as conn:
            for table in _REQUIRED_TABLES:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                    "WHERE table_schema='public' AND table_name=$1)",
                    table,
                )
                if not exists:
                    skip_reason = f"wa_outbox bound-FIFO tests: required table '{table}' missing"
                    break
            if skip_reason is None:
                for table, column in _REQUIRED_COLUMNS:
                    exists = await conn.fetchval(
                        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
                        "WHERE table_schema='public' AND table_name=$1 "
                        "AND column_name=$2)",
                        table,
                        column,
                    )
                    if not exists:
                        skip_reason = (
                            f"wa_outbox bound-FIFO tests: {table}.{column} missing "
                            "(migration 318 not applied to the test DB)"
                        )
                        break
        if skip_reason is None:
            yield pool
    finally:
        await pool.close()
    if skip_reason:
        pytest.skip(skip_reason)


@pytest_asyncio.fixture(autouse=True)
async def _clean_slate(db_pool: asyncpg.Pool) -> None:
    """Truncate before every test — see test_wa_outbox_worker_carrier.py's
    identical fixture for why (process_outbox_once claims whichever due row
    sorts first SYSTEM-WIDE)."""
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE wa_outbox, meta_inbox_messages, meta_inbox_threads "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture(autouse=True)
def _no_terminal_apology(monkeypatch: pytest.MonkeyPatch) -> None:
    """Never let a terminal-failure case reach Telegram."""
    monkeypatch.setenv("WA_OUTBOX_TERMINAL_APOLOGY_ENABLED", "false")


@pytest.fixture(autouse=True)
def _codex_provider_armed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wa_codex_leg, "provider_is_codex", lambda: True)


class _StubWhatsApp:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def send_message(
        self, *, phone: str, text: str, reply_to_message_id: str | None = None
    ) -> dict[str, Any]:
        self.calls.append({"phone": phone, "text": text})
        return {"messages": [{"id": f"wamid.synthetic.{uuid.uuid4().hex[:8]}"}]}


async def _never_bot_gen(_thread: Any) -> str:
    raise AssertionError(
        "bot_generate_fn (Gemini back-compat shape) must never be invoked "
        "post Gemini-cut — the codex leg is the only generation path"
    )


def _binding_recorder_leg():
    """Replaces ``wa_codex_leg.attempt``: loads the REAL bound context (the
    thing under test) and records (outbox_id, bound_inbound_id) in call
    order, then returns synthetic served text — no network, no real
    generation."""
    recorded: list[tuple[int, int | None]] = []

    async def _fake(
        pool: asyncpg.Pool,
        *,
        outbox_id: int,
        thread_id: int,
        message_id: int,
        claim_token: uuid.UUID,
        outbox_expected_status: str,
        thread: Any,
    ) -> wa_codex_leg.CodexLegResult:
        bound = await _load_bound_thread_context(pool, thread_id=thread_id, outbox_id=outbox_id)
        recorded.append((outbox_id, bound.inbound_message_id))
        return wa_codex_leg.CodexLegResult(text=f"synthetic answer for outbox {outbox_id}", served_by="codex")

    _fake.recorded = recorded  # type: ignore[attr-defined]
    return _fake


async def _seed_thread(pool: asyncpg.Pool) -> int:
    phone = f"+000000{uuid.uuid4().int % 10**7:07d}"
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO meta_inbox_threads
                (counterpart_phone, human_handling, handling_version,
                 last_customer_at, last_message_at)
            VALUES ($1, false, 0, NOW(), NOW())
            RETURNING thread_id
            """,
            phone,
        )


async def _seed_bound_row(
    pool: asyncpg.Pool, *, thread_id: int, body: str, due: bool = True
) -> dict[str, int]:
    """Mirror whatsapp_chat.py's real insert order: inbound, then the
    outbound stub, then the outbox row bound to the inbound (migration 318)."""
    async with pool.acquire() as conn:
        inbound_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, status)
            VALUES ($1, 'inbound', 'customer', $2, 'received')
            RETURNING id
            """,
            thread_id,
            body,
        )
        stub_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, status)
            VALUES ($1, 'outbound', 'bot', 'queued')
            RETURNING id
            """,
            thread_id,
        )
        next_retry = "NOW() - INTERVAL '1 second'" if due else "NOW() + INTERVAL '1 hour'"
        outbox_id = await conn.fetchval(
            f"""
            INSERT INTO wa_outbox
                (thread_id, message_id, needs_generation, status, attempts,
                 next_retry_at, inbound_message_id)
            VALUES ($1, $2, true, 'pending', 0, {next_retry}, $3)
            RETURNING id
            """,
            thread_id,
            stub_id,
            inbound_id,
        )
    return {"inbound_id": inbound_id, "stub_id": stub_id, "outbox_id": outbox_id}


async def _seed_human_send(pool: asyncpg.Pool, *, thread_id: int, body: str) -> int:
    async with pool.acquire() as conn:
        message_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, status)
            VALUES ($1, 'outbound', 'human', $2, 'queued')
            RETURNING id
            """,
            thread_id,
            body,
        )
        return await conn.fetchval(
            """
            INSERT INTO wa_outbox
                (thread_id, message_id, needs_generation, status, attempts, next_retry_at)
            VALUES ($1, $2, false, 'pending', 0, NOW() - INTERVAL '1 second')
            RETURNING id
            """,
            thread_id,
            message_id,
        )


async def _set_status(pool: asyncpg.Pool, outbox_id: int, status: str) -> None:
    async with pool.acquire() as conn:
        await conn.execute("UPDATE wa_outbox SET status = $2 WHERE id = $1", outbox_id, status)


@pytest.mark.asyncio
async def test_burst_served_strictly_fifo_each_bound_to_its_own_inbound(
    monkeypatch: pytest.MonkeyPatch, db_pool: asyncpg.Pool
) -> None:
    """Innocence + the headline property: 3 messages in ONE thread, all due
    at once (the real burst shape) — served strictly in creation order, each
    one bound to its OWN inbound, nothing failed, nothing left with a NULL
    reason."""
    thread_id = await _seed_thread(db_pool)
    rows = [
        await _seed_bound_row(db_pool, thread_id=thread_id, body=f"synthetic burst question {i}")
        for i in range(3)
    ]
    leg = _binding_recorder_leg()
    monkeypatch.setattr(wa_outbox_worker.wa_codex_leg, "attempt", leg)
    svc = _StubWhatsApp()

    results = [await process_outbox_once(db_pool, svc, _never_bot_gen) for _ in range(3)]

    assert results == ["sent", "sent", "sent"]
    claimed_order = [outbox_id for outbox_id, _ in leg.recorded]  # type: ignore[attr-defined]
    assert claimed_order == [r["outbox_id"] for r in rows], "must claim oldest-first"
    for outbox_id, bound_inbound_id in leg.recorded:  # type: ignore[attr-defined]
        expected = next(r["inbound_id"] for r in rows if r["outbox_id"] == outbox_id)
        assert bound_inbound_id == expected, "each row must be bound to ITS OWN inbound"

    async with db_pool.acquire() as conn:
        failed = await conn.fetch(
            "SELECT id, generation_fall_off_reason FROM wa_outbox "
            "WHERE thread_id = $1 AND status = 'failed'",
            thread_id,
        )
    assert not failed, f"no row of a normal burst should end failed: {list(failed)}"


@pytest.mark.parametrize("blocking_status", ["pending", "claimed", "generating"])
@pytest.mark.asyncio
async def test_claim_skips_a_row_while_an_older_same_thread_row_is_in_flight(
    db_pool: asyncpg.Pool, blocking_status: str
) -> None:
    """Guilt: row 2 must NOT be claimable while row 1 (older, same thread,
    needs_generation) is pending/claimed/generating — even if row 1 itself
    is not currently due (simulating a mid-backoff retry, the exact D1/D2
    shape: an older row's retry timer being in the future must not let a
    newer message jump the queue)."""
    thread_id = await _seed_thread(db_pool)
    older = await _seed_bound_row(
        db_pool, thread_id=thread_id, body="synthetic older question", due=False
    )
    await _set_status(db_pool, older["outbox_id"], blocking_status)
    newer = await _seed_bound_row(
        db_pool, thread_id=thread_id, body="synthetic newer question", due=True
    )

    svc = _StubWhatsApp()
    result = await process_outbox_once(db_pool, svc, _never_bot_gen)

    assert result == "idle", (
        f"the newer row must not be claimable while the older one is "
        f"{blocking_status!r}"
    )
    async with db_pool.acquire() as conn:
        newer_status = await conn.fetchval(
            "SELECT status FROM wa_outbox WHERE id = $1", newer["outbox_id"]
        )
    assert newer_status == "pending"


@pytest.mark.asyncio
async def test_claim_never_blocks_or_is_blocked_by_a_human_send(
    monkeypatch: pytest.MonkeyPatch, db_pool: asyncpg.Pool
) -> None:
    """Innocence: a human send (needs_generation = false) is claimed
    immediately even with an older, still-pending bot-reply row in the SAME
    thread — and does not itself block that bot-reply row once due."""
    thread_id = await _seed_thread(db_pool)
    bot_row = await _seed_bound_row(
        db_pool, thread_id=thread_id, body="synthetic bot-bound question", due=False
    )
    human_outbox_id = await _seed_human_send(
        db_pool, thread_id=thread_id, body="synthetic human reply"
    )
    leg = _binding_recorder_leg()
    monkeypatch.setattr(wa_outbox_worker.wa_codex_leg, "attempt", leg)
    svc = _StubWhatsApp()

    result = await process_outbox_once(db_pool, svc, _never_bot_gen)

    assert result == "sent"
    async with db_pool.acquire() as conn:
        human_status = await conn.fetchval(
            "SELECT status FROM wa_outbox WHERE id = $1", human_outbox_id
        )
        bot_status = await conn.fetchval(
            "SELECT status FROM wa_outbox WHERE id = $1", bot_row["outbox_id"]
        )
    assert human_status == "done", "the human send must not wait behind the bot-reply row"
    assert bot_status == "pending", "the bot-reply row must be untouched by the human send"


@pytest.mark.asyncio
async def test_legacy_row_binds_to_the_older_inbound_never_a_newer_one(
    monkeypatch: pytest.MonkeyPatch, db_pool: asyncpg.Pool
) -> None:
    """A pre-316 row (inbound_message_id NULL) with a NEWER inbound inserted
    into the thread AFTER its own stub — the bound context must still use
    the OLDER inbound (D1's exact defect, proven end-to-end through the
    real worker, not just the loader in isolation)."""
    thread_id = await _seed_thread(db_pool)
    async with db_pool.acquire() as conn:
        older_inbound_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, status)
            VALUES ($1, 'inbound', 'customer', $2, 'received')
            RETURNING id
            """,
            thread_id,
            "synthetic older legacy question",
        )
        stub_id = await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, status)
            VALUES ($1, 'outbound', 'bot', 'queued')
            RETURNING id
            """,
            thread_id,
        )
        outbox_id = await conn.fetchval(
            """
            INSERT INTO wa_outbox
                (thread_id, message_id, needs_generation, status, attempts, next_retry_at)
            VALUES ($1, $2, true, 'pending', 0, NOW() - INTERVAL '1 second')
            RETURNING id
            """,
            thread_id,
            stub_id,
        )
        # Arrives AFTER the stub — must never be picked by the legacy derive.
        await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, status)
            VALUES ($1, 'inbound', 'customer', $2, 'received')
            RETURNING id
            """,
            thread_id,
            "synthetic NEWER question inserted after the stub",
        )

    leg = _binding_recorder_leg()
    monkeypatch.setattr(wa_outbox_worker.wa_codex_leg, "attempt", leg)
    svc = _StubWhatsApp()

    result = await process_outbox_once(db_pool, svc, _never_bot_gen)

    assert result == "sent"
    assert leg.recorded == [(outbox_id, older_inbound_id)]  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_every_failed_path_this_worker_exercises_records_a_reason(
    monkeypatch: pytest.MonkeyPatch, db_pool: asyncpg.Pool
) -> None:
    """Ruling (a): a customer message is never dropped without a loud,
    recorded reason. Drives one row through thread_missing (FK-impossible
    in practice, but wa_outbox itself has no FK to a live thread row after
    a manual delete) is out of scope here — this proves the two paths this
    module can trivially reach for real: pre-generation takeover and a
    closed 24h window."""
    thread_id = await _seed_thread(db_pool)
    row = await _seed_bound_row(db_pool, thread_id=thread_id, body="synthetic takeover question")
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE meta_inbox_threads SET human_handling = true WHERE thread_id = $1",
            thread_id,
        )
    svc = _StubWhatsApp()

    result = await process_outbox_once(db_pool, svc, _never_bot_gen)

    assert result == "aborted_human"
    async with db_pool.acquire() as conn:
        reason = await conn.fetchval(
            "SELECT generation_fall_off_reason FROM wa_outbox WHERE id = $1",
            row["outbox_id"],
        )
    assert reason == "aborted_human_takeover"


@pytest.mark.asyncio
async def test_no_failed_row_anywhere_carries_a_null_reason(
    monkeypatch: pytest.MonkeyPatch, db_pool: asyncpg.Pool
) -> None:
    """Cross-cutting proof: after running the takeover case and the window-
    closed case in the SAME suite run, zero 'failed' rows carry a NULL
    reason — the property ruling (a) actually cares about."""
    thread_id_a = await _seed_thread(db_pool)
    row_a = await _seed_bound_row(db_pool, thread_id=thread_id_a, body="synthetic q a")
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE meta_inbox_threads SET human_handling = true WHERE thread_id = $1",
            thread_id_a,
        )

    # A human send (needs_generation=false) skips generation entirely and
    # reaches the window check directly — the cleanest real path to
    # 'window_closed_24h' without touching the codex leg at all.
    thread_id_b = await _seed_thread(db_pool)
    row_b_outbox_id = await _seed_human_send(db_pool, thread_id=thread_id_b, body="synthetic q b")
    async with db_pool.acquire() as conn:
        await conn.execute(
            "UPDATE meta_inbox_threads SET last_customer_at = NOW() - INTERVAL '25 hours' "
            "WHERE thread_id = $1",
            thread_id_b,
        )

    svc = _StubWhatsApp()
    await process_outbox_once(db_pool, svc, _never_bot_gen)
    await process_outbox_once(db_pool, svc, _never_bot_gen)

    async with db_pool.acquire() as conn:
        null_reason_failures = await conn.fetch(
            "SELECT id FROM wa_outbox WHERE status = 'failed' AND generation_fall_off_reason IS NULL"
        )
    assert not null_reason_failures, f"failed with no reason: {list(null_reason_failures)}"
    async with db_pool.acquire() as conn:
        both = await conn.fetch(
            "SELECT id, generation_fall_off_reason FROM wa_outbox WHERE id = ANY($1) AND status = 'failed'",
            [row_a["outbox_id"], row_b_outbox_id],
        )
    reasons = {r["id"]: r["generation_fall_off_reason"] for r in both}
    assert reasons.get(row_a["outbox_id"]) == "aborted_human_takeover"
    assert reasons.get(row_b_outbox_id) == "window_closed_24h"
