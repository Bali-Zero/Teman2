"""Real-Postgres tests for ``_load_bound_thread_context`` (B2.5 PR-1,
migration 316).

Deliberately real DB, not a mock: the function's whole job is a SQL
predicate (COALESCE the column anchor with a legacy derive that must never
pick a message newer than the row's own stub) — a mock connection can only
echo back whatever the test hands it, which would prove nothing about the
predicate itself. Fixture pattern copied from
``test_wa_outbox_worker_carrier.py`` (``db_pool``): ``TEST_DATABASE_URL``
env var, default ``postgresql://nuzantara@localhost:5432/nuzantara_test``.
Skips cleanly (does not fail) when the DB is unreachable or migration 316
has not been applied to the test DB.

All phone numbers and message bodies are synthetic.
"""

from __future__ import annotations

import os
import uuid

import asyncpg
import pytest
import pytest_asyncio

from backend.services.integrations.wa_inbox_bot import (
    _HISTORY_TURNS,
    _load_bound_thread_context,
)

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
        pytest.skip(f"bound-context tests: DB unreachable ({exc})")
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
                    skip_reason = f"bound-context tests: required table '{table}' missing"
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
                            f"bound-context tests: {table}.{column} missing "
                            "(migration 316 not applied to the test DB)"
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
    async with db_pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE TABLE wa_outbox, meta_inbox_messages, meta_inbox_threads "
            "RESTART IDENTITY CASCADE"
        )


async def _seed_thread(pool: asyncpg.Pool) -> int:
    phone = f"+000000{uuid.uuid4().int % 10**7:07d}"
    async with pool.acquire() as conn:
        return await conn.fetchval(
            "INSERT INTO meta_inbox_threads (counterpart_phone) VALUES ($1) "
            "RETURNING thread_id",
            phone,
        )


async def _insert_message(
    pool: asyncpg.Pool,
    *,
    thread_id: int,
    direction: str,
    sender_role: str,
    body: str | None,
) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO meta_inbox_messages (thread_id, direction, sender_role, body, status)
            VALUES ($1, $2, $3, $4, 'received')
            RETURNING id
            """,
            thread_id,
            direction,
            sender_role,
            body,
        )


async def _insert_outbox(
    pool: asyncpg.Pool,
    *,
    thread_id: int,
    stub_message_id: int,
    inbound_message_id: int | None,
) -> int:
    async with pool.acquire() as conn:
        return await conn.fetchval(
            """
            INSERT INTO wa_outbox (thread_id, message_id, needs_generation, status, inbound_message_id)
            VALUES ($1, $2, true, 'pending', $3)
            RETURNING id
            """,
            thread_id,
            stub_message_id,
            inbound_message_id,
        )


@pytest.mark.asyncio
async def test_column_anchor_used_when_present(db_pool: asyncpg.Pool) -> None:
    """Guilt: a row carrying ``inbound_message_id`` anchors to it directly,
    never the thread's latest — even when a NEWER inbound exists."""
    thread_id = await _seed_thread(db_pool)
    inbound_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="synthetic question one",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=inbound_id,
    )
    # A NEWER inbound arrives after this row's own binding was already set.
    await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="synthetic question two — arrived later",
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.inbound_message_id == inbound_id
    assert bound.query == "synthetic question one"


@pytest.mark.asyncio
async def test_legacy_row_derives_the_older_inbound_never_a_newer_one(
    db_pool: asyncpg.Pool,
) -> None:
    """Guilt+innocence (D1's exact shape): a legacy row (inbound_message_id
    NULL) must derive the LATEST inbound that existed BEFORE its own stub —
    never one inserted afterwards, which is exactly the belief that let a
    retry answer a newer customer message than the one its row was for."""
    thread_id = await _seed_thread(db_pool)
    older_inbound_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="synthetic older question",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=None,
    )
    # Arrives AFTER the stub — the legacy derive must never pick this one.
    await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="synthetic NEWER question that must never be answered by this row",
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.inbound_message_id == older_inbound_id
    assert bound.query == "synthetic older question"


@pytest.mark.asyncio
async def test_no_anchor_found_returns_empty_context(db_pool: asyncpg.Pool) -> None:
    """A legacy row with no PRIOR inbound at all (defensive-only shape) —
    never raises, mirrors ``_load_thread_context``'s own 'no query' outcome."""
    thread_id = await _seed_thread(db_pool)
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=None,
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.inbound_message_id is None
    assert bound.query == ""
    assert bound.history == []


@pytest.mark.asyncio
async def test_history_excludes_anything_at_or_after_the_anchor(
    db_pool: asyncpg.Pool,
) -> None:
    """History is strictly OLDER than the anchor, oldest -> newest, and
    never includes the anchor itself as a history entry."""
    thread_id = await _seed_thread(db_pool)
    await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="turn 1",
    )
    await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot",
        body="turn 2 reply",
    )
    anchor_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="turn 3 — the anchor",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=anchor_id,
    )
    # Arrives AFTER the anchor — must never leak into history (id >= anchor).
    await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="turn 4 — after the anchor, must not appear",
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.query == "turn 3 — the anchor"
    assert bound.history == [
        {"role": "user", "content": "turn 1"},
        {"role": "assistant", "content": "turn 2 reply"},
    ]
    assert all("turn 4" not in h["content"] for h in bound.history)


@pytest.mark.asyncio
async def test_history_caps_at_history_turns_and_skips_blank_bodies(
    db_pool: asyncpg.Pool,
) -> None:
    """Empty/NULL-body messages never count as history turns (mirrors
    ``_load_thread_context``'s own body filter), and the anchor's own body
    may be blank without excluding the row from the result."""
    thread_id = await _seed_thread(db_pool)
    for i in range(_HISTORY_TURNS + 2):
        await _insert_message(
            db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
            body=f"history turn {i}",
        )
    # A blank-body row in between — must not consume a history slot as a
    # non-empty turn, and must not appear in the returned history.
    await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body="",
    )
    anchor_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer", body="",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=anchor_id,
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.query == ""  # blank anchor body -> "" per contract, never excluded
    assert len(bound.history) <= _HISTORY_TURNS
    assert all(h["content"] for h in bound.history)  # never a blank entry


@pytest.mark.asyncio
async def test_a_whitespace_only_message_does_not_displace_a_real_older_message(
    db_pool: asyncpg.Pool,
) -> None:
    """A body of pure whitespace ("   ") carries no content, so it must not
    occupy one of the ``_HISTORY_TURNS + 1`` LIMIT slots. Before the fix, the
    history-window filter rejected only ``body <> ''`` — a whitespace-only
    body passed straight through, consumed a slot, and silently displaced
    the oldest real message out of the window."""
    thread_id = await _seed_thread(db_pool)
    oldest_body = "synthetic oldest real message — must survive the window"
    await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body=oldest_body,
    )
    for i in range(_HISTORY_TURNS - 1):
        await _insert_message(
            db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
            body=f"synthetic filler {i}",
        )
    # Whitespace-only — must not consume a history slot.
    await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot",
        body="   ",
    )
    anchor_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="the anchor question",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=anchor_id,
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    contents = [h["content"] for h in bound.history]
    assert oldest_body in contents, (
        "the whitespace-only row displaced the oldest real message from the "
        f"history window: {contents!r}"
    )
    assert all(c.strip() for c in contents), "a whitespace-only body leaked into history"


@pytest.mark.asyncio
async def test_a_whitespace_only_anchor_yields_an_empty_query(
    db_pool: asyncpg.Pool,
) -> None:
    """A body of pure whitespace must reach the caller as ``query == ""`` —
    the SAME empty-string outcome the docstring already promises for
    NULL/empty — never as literal spaces, which would slip past the
    downstream ``if not query:`` guard in ``wa_codex_leg.py`` and hand the
    generator a query of spaces."""
    thread_id = await _seed_thread(db_pool)
    anchor_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="inbound", sender_role="customer",
        body="   ",
    )
    stub_id = await _insert_message(
        db_pool, thread_id=thread_id, direction="outbound", sender_role="bot", body=None,
    )
    outbox_id = await _insert_outbox(
        db_pool, thread_id=thread_id, stub_message_id=stub_id, inbound_message_id=anchor_id,
    )

    bound = await _load_bound_thread_context(db_pool, thread_id=thread_id, outbox_id=outbox_id)

    assert bound.query == ""


def test_legacy_anchor_derive_depends_on_the_thread_upsert_serializing_webhooks() -> None:
    """Guard the derive's SOURCE — a wrong anchor means the client gets an
    answer to a DIFFERENT message.

    The COALESCE subquery above (latest customer inbound with
    ``m.id < wo.message_id``) is only correct because two webhooks for the
    SAME thread can never interleave their ids. That holds ONLY because
    ``whatsapp_chat.py``'s ``_handle_meta_inbox_message`` opens its
    transaction with ``INSERT INTO meta_inbox_threads ... ON CONFLICT
    (counterpart_phone) DO UPDATE ... RETURNING``, whose ``DO UPDATE`` takes
    a row-level lock on the thread row held until COMMIT — so a concurrent
    webhook for the same phone serializes behind it, and ids always come out
    inbound1 < stub1 < inbound2 < stub2. Nothing else states this anywhere.
    The day someone changes that upsert to ``DO NOTHING`` (no row lock on a
    no-op), or moves the inbound insert out of that transaction, this
    guarantee disappears silently and the legacy derive starts picking a
    NEWER inbound than the row's real cause.

    Reads the real source (AST, in the spirit of
    ``test_the_persona_builder_accepts_every_keyword_the_router_passes``) —
    a mock connection could only echo back what the test itself asserts.
    """
    import ast
    from pathlib import Path

    import backend.app.routers.whatsapp_chat as mod

    assert mod.__file__ is not None
    source = Path(mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    def _string_literals(node: ast.AST) -> list[str]:
        return [
            n.value
            for n in ast.walk(node)
            if isinstance(n, ast.Constant) and isinstance(n.value, str)
        ]

    tx_blocks = [
        n
        for n in ast.walk(tree)
        if isinstance(n, ast.AsyncWith)
        and any(
            isinstance(item.context_expr, ast.Call)
            and isinstance(item.context_expr.func, ast.Attribute)
            and item.context_expr.func.attr == "transaction"
            for item in n.items
        )
    ]
    assert tx_blocks, "no `async with conn.transaction():` block found — retarget this guard"

    found = False
    for block in tx_blocks:
        literals = _string_literals(block)
        has_thread_upsert = any(
            "INSERT INTO meta_inbox_threads" in s
            and "ON CONFLICT (counterpart_phone) DO UPDATE" in s
            for s in literals
        )
        has_inbound_insert = any(
            "INSERT INTO meta_inbox_messages" in s and "'inbound'" in s for s in literals
        )
        has_outbox_insert = any("INSERT INTO wa_outbox" in s for s in literals)
        if has_thread_upsert and has_inbound_insert and has_outbox_insert:
            found = True
            break

    assert found, (
        "the thread upsert (ON CONFLICT (counterpart_phone) DO UPDATE), the "
        "customer inbound insert and the wa_outbox insert are no longer all "
        "inside the SAME `async with conn.transaction():` block in "
        "whatsapp_chat.py — the serialization the legacy anchor derive in "
        "wa_inbox_bot.py depends on is gone, and a wrong anchor means the "
        "client gets an answer to a different message."
    )
