# Kimi independent adversarial tests: serialized conversation persistence.
# Disposable PostgreSQL 17 only, synthetic data, no other databases.
# Tests assert observable behavior (ids, row contents, timing bounds),
# never SQL string structure. The shared fixture provides an isolated
# schema, a 30ms BEFORE INSERT/UPDATE delay trigger, a canonical JSON
# codec, max 10 connections, and a no-op cache invalidation patch.

from __future__ import annotations

import asyncio
import json
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest

from backend.db.repositories.conversation_repository import (
    ConversationRepository,
)
from backend.tests.db.test_universal_conversation_pg import (  # noqa: F401
    conversation_pool,
)

# Mirrors _CONVERSATION_LOCK_NAMESPACE in the implementation ('CVNS').
# A deliberate literal: if the implementation's namespace ever changes,
# the cross-writer contract breaks and these tests must fail.
_LOCK_NAMESPACE = 0x43564E53


def _repo(fixture):
    """Adapt the fixture whether it yields a pool or a repository."""
    if hasattr(fixture, "save_messages"):
        return fixture
    return ConversationRepository(fixture)


def _sid() -> str:
    return "kimi-" + uuid.uuid4().hex


def _as_list(value):
    if isinstance(value, str):
        return json.loads(value)
    return list(value)


def _as_dict(value):
    if isinstance(value, str):
        return json.loads(value)
    return dict(value)


@pytest.mark.asyncio
async def test_lock_wait_timeout_rolls_back_cleanly_and_recovers(conversation_pool):
    """A contender blocked past lock_timeout fails as None, leaves zero
    partial rows, and the session is writable once the holder releases."""
    repo = _repo(conversation_pool)
    session = _sid()
    payload = [{"role": "user", "content": "first", "ts": 1}]

    async with conversation_pool.acquire() as holder:
        # Session-level advisory lock occupies the same lock space the
        # implementation's transaction-scoped lock needs for this session.
        await holder.execute(
            "SELECT pg_advisory_lock($1::integer, hashtext($2::text))",
            _LOCK_NAMESPACE,
            session,
        )

        started = time.monotonic()
        result = await repo.save_messages(session, "u-timeout", payload, {})
        elapsed = time.monotonic() - started

        assert result is None, "blocked writer must fail closed with None"
        # Must have genuinely waited on the 5s lock_timeout (not failed
        # instantly for an unrelated reason) and must stay bounded.
        assert 3.0 <= elapsed <= 12.0, f"wait outside expected bounds: {elapsed:.2f}s"

        # Clean rollback: no partially inserted row may exist.
        rowcount = await holder.fetchval(
            "SELECT count(*) FROM conversations WHERE session_id = $1",
            session,
        )
        assert rowcount == 0

        await holder.execute(
            "SELECT pg_advisory_unlock($1::integer, hashtext($2::text))",
            _LOCK_NAMESPACE,
            session,
        )

    # Recovery: after release, the same session persists normally.
    recovered = await repo.save_messages(session, "u-timeout", payload, {})
    assert isinstance(recovered, int)
    async with conversation_pool.acquire() as conn:
        row = await conn.fetchrow("SELECT messages FROM conversations WHERE id = $1", recovered)
    assert [m["content"] for m in _as_list(row["messages"])] == ["first"]


@pytest.mark.asyncio
async def test_tied_created_at_selects_highest_id_and_preserves_older(conversation_pool):
    """Legacy rows with identical created_at resolve deterministically to
    the highest id; the older row remains byte-identical."""
    repo = _repo(conversation_pool)
    session = _sid()
    tie = datetime(2026, 1, 1, tzinfo=timezone.utc)

    async with conversation_pool.acquire() as conn:
        older_id = await conn.fetchval(
            "INSERT INTO conversations (session_id, user_id, messages, metadata, created_at)"
            " VALUES ($1, $2, $3::jsonb, $4::jsonb, $5) RETURNING id",
            session,
            "u-legacy",
            [{"role": "user", "content": "older"}],
            {},
            tie,
        )
        newer_id = await conn.fetchval(
            "INSERT INTO conversations (session_id, user_id, messages, metadata, created_at)"
            " VALUES ($1, $2, $3::jsonb, $4::jsonb, $5) RETURNING id",
            session,
            "u-legacy",
            [{"role": "user", "content": "newer"}],
            {},
            tie,
        )
    assert newer_id > older_id

    appended = [{"role": "assistant", "content": "appended", "ts": 2}]
    result = await repo.save_messages(session, "u-legacy", appended, {})
    assert result == newer_id, "tie must resolve to the highest id"

    async with conversation_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, messages FROM conversations WHERE session_id = $1 ORDER BY id",
            session,
        )
    by_id = {r["id"]: _as_list(r["messages"]) for r in rows}
    assert [m["content"] for m in by_id[older_id]] == ["older"]
    assert [m["content"] for m in by_id[newer_id]] == ["newer", "appended"]


@pytest.mark.asyncio
async def test_legacy_multiple_rows_keep_ids_and_stay_untouched(conversation_pool):
    """Pre-existing multi-row history keeps its ids; repeated saves land
    only on the latest row; older rows are never rewritten or merged."""
    repo = _repo(conversation_pool)
    session = _sid()
    base = datetime(2026, 2, 1, tzinfo=timezone.utc)
    ids = []
    async with conversation_pool.acquire() as conn:
        for idx in range(3):
            row_id = await conn.fetchval(
                "INSERT INTO conversations (session_id, user_id, messages, metadata, created_at)"
                " VALUES ($1, $2, $3::jsonb, $4::jsonb, $5) RETURNING id",
                session,
                "u-legacy",
                [{"role": "user", "content": f"legacy-{idx}"}],
                {},
                base + timedelta(seconds=idx),
            )
            ids.append(row_id)

    first = await repo.save_messages(
        session, "u-legacy", [{"role": "assistant", "content": "batch-1"}], {}
    )
    second = await repo.save_messages(
        session, "u-legacy", [{"role": "user", "content": "batch-2"}], {}
    )
    assert first == ids[-1] == second, "every save must target the same latest row id"

    async with conversation_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, messages FROM conversations WHERE session_id = $1 ORDER BY id",
            session,
        )
    by_id = {r["id"]: _as_list(r["messages"]) for r in rows}
    assert set(by_id) == set(ids), "no row may be created or deleted by saves"
    for idx, row_id in enumerate(ids[:-1]):
        assert [m["content"] for m in by_id[row_id]] == [f"legacy-{idx}"]
    assert [m["content"] for m in by_id[ids[-1]]] == [
        "legacy-2",
        "batch-1",
        "batch-2",
    ]


@pytest.mark.asyncio
async def test_concurrent_metadata_writers_union_and_lose_no_messages(conversation_pool):
    """Pins the metadata contract under serialization: two racing writers
    with disjoint metadata keys must both be reflected, with no message
    loss. If the implementation is last-writer-wins for metadata, this
    test fails and that failure is the contract gap to resolve (R2)."""
    repo = _repo(conversation_pool)
    session = _sid()
    msg_a = [{"role": "user", "content": "from-a", "ts": 1}]
    msg_b = [{"role": "assistant", "content": "from-b", "ts": 2}]

    id_a, id_b = await asyncio.gather(
        repo.save_messages(session, "u-meta", msg_a, {"origin": "a"}),
        repo.save_messages(session, "u-meta", msg_b, {"marker": "b"}),
    )
    assert isinstance(id_a, int) and id_a == id_b, (
        "racing first writes on one session must converge to one row id"
    )

    async with conversation_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT messages, metadata FROM conversations WHERE id = $1", id_a
        )
    contents = sorted(m["content"] for m in _as_list(row["messages"]))
    assert contents == ["from-a", "from-b"], "no message may be lost"
    metadata = _as_dict(row["metadata"])
    assert metadata.get("origin") == "a"
    assert metadata.get("marker") == "b"
