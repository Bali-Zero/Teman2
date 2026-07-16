"""Tests for the WA Meta Inbox outbox worker (process_outbox_once).

Covers (spec sezione 3 "Worker" + 2026-07-17 F1a hardening — zantara-wa-spec-v2
sections P2-P6/D2):
  - happy path: claim a pending human send → Graph send → ledger sent + wamid +
    apply staged status receipt → outbox done.
  - human_handling re-check abort for a bot reply, BOTH before generation
    (takeover already flagged when claimed) and AFTER generation (takeover
    flips mid-generation — P4 pre-send fence).
  - 24h window closed → ledger failed + outbox failed (no send).
  - send HTTP failure → backoff retry (attempts++, status back to pending).
  - bot-generation failure → backoff retry / terminal failure.
  - idle when no due row / when every due row's thread is already locked.
  - per-thread coalescing at claim (P2): a burst of pending bot-reply rows for
    the same thread is collapsed to one send, the rest marked superseded.
  - per-thread advisory lock (P3): a claim attempt skips a candidate whose
    thread is already locked and tries the next one.
  - lease reclaimer now also covers 'generating' rows (P5/P6).

The mock connection is scripted: fetch/fetchrow/fetchval return queued values
in call order (one independent queue per method — matches the worker calling
each method for a different SQL shape), execute records SQL. ALL FOUR methods
record into `executed` (uniform SQL/args audit trail) so fenced UPDATEs done
via `fetchrow(...RETURNING id)` are just as assertable as plain `execute()`
calls. transaction() is a no-op async CM. The pool exposes execute() (reclaim)
+ acquire() (the claim/work conn).
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.integrations import wa_outbox_worker
from backend.services.integrations.wa_outbox_worker import process_outbox_once


class ScriptedConn:
    def __init__(
        self,
        fetchrow_results: list[Any] | None = None,
        fetchval_results: list[Any] | None = None,
        fetch_results: list[Any] | None = None,
    ) -> None:
        self.executed: list[tuple[str, tuple[Any, ...]]] = []
        self._fetchrow = list(fetchrow_results or [])
        self._fetchval = list(fetchval_results or [])
        self._fetch = list(fetch_results or [])

    async def execute(self, sql: str, *args: Any) -> str:
        self.executed.append((sql, args))
        return "UPDATE 1"

    async def fetchrow(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        return self._fetchrow.pop(0) if self._fetchrow else None

    async def fetchval(self, sql: str, *args: Any) -> Any:
        self.executed.append((sql, args))
        return self._fetchval.pop(0) if self._fetchval else None

    async def fetch(self, sql: str, *args: Any) -> list[Any]:
        self.executed.append((sql, args))
        return self._fetch.pop(0) if self._fetch else []

    def transaction(self) -> Any:
        @asynccontextmanager
        async def _cm():
            yield

        return _cm()

    def sql_contains(self, needle: str) -> bool:
        return any(needle in sql for sql, _ in self.executed)

    def sql_with_args(self, needle: str) -> list[tuple[str, tuple[Any, ...]]]:
        return [(s, a) for s, a in self.executed if needle in s]


def _make_pool(conn: ScriptedConn) -> MagicMock:
    pool = MagicMock()
    pool.execute = AsyncMock(return_value="UPDATE 0")  # reclaim stale
    acquire_cm = MagicMock()
    acquire_cm.__aenter__ = AsyncMock(return_value=conn)
    acquire_cm.__aexit__ = AsyncMock(return_value=False)
    pool.acquire = MagicMock(return_value=acquire_cm)
    return pool


def _wa_service(send_result: dict[str, Any] | None = None, raise_exc: Exception | None = None):
    svc = MagicMock()
    if raise_exc is not None:
        svc.send_message = AsyncMock(side_effect=raise_exc)
    else:
        svc.send_message = AsyncMock(return_value=send_result or {})
    return svc


async def _bot_gen(_thread: Any) -> str:
    return "generated bot reply"


def _candidate(
    id_: int,
    thread_id: int = 7,
    message_id: int = 100,
    needs_generation: bool = False,
    attempts: int = 0,
) -> dict[str, Any]:
    return {
        "id": id_,
        "thread_id": thread_id,
        "message_id": message_id,
        "needs_generation": needs_generation,
        "attempts": attempts,
    }


def _thread_row(thread_id: int = 7, human_handling: bool = False) -> dict[str, Any]:
    return {
        "thread_id": thread_id,
        "counterpart_phone": "628111",
        "human_handling": human_handling,
        "last_customer_at": "x",
    }


# ── idle / reclaim scope ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_idle_when_no_due_row() -> None:
    conn = ScriptedConn(fetch_results=[[]])  # candidate scan → nothing
    pool = _make_pool(conn)
    result = await process_outbox_once(pool, _wa_service(), _bot_gen)
    assert result == "idle"
    # Reclaim stale always runs first.
    pool.execute.assert_awaited()


@pytest.mark.asyncio
async def test_reclaim_covers_generating_rows_too() -> None:
    """P5/P6: a crash mid bot-generation must not orphan the row forever —
    the reclaimer's WHERE clause must cover 'generating', not just 'claimed'."""
    conn = ScriptedConn(fetch_results=[[]])
    pool = _make_pool(conn)

    await process_outbox_once(pool, _wa_service(), _bot_gen)

    pool.execute.assert_awaited_once()
    reclaim_sql = pool.execute.call_args[0][0]
    assert "'claimed'" in reclaim_sql
    assert "'generating'" in reclaim_sql
    assert "claim_expires_at < NOW()" in reclaim_sql


# ── human send happy path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_human_send_happy_path_applies_staged_status() -> None:
    candidate = _candidate(1, thread_id=7, message_id=100, needs_generation=False)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=True),  # thread load (human_handling irrelevant to human send)
            {"body": "ciao dal team"},  # ledger body load
            {"id": 1},  # pre-send fence RETURNING
            {"id": 1},  # final commit RETURNING
            {"status": "delivered", "error": None},  # staged receipt exists
        ],
        fetchval_results=[
            True,  # advisory lock acquired for thread 7
            True,  # window_open
        ],
        fetch_results=[[candidate]],  # candidate scan
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.SENT.1"}]})

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    svc.send_message.assert_awaited_once()
    assert any(
        "status = 'sent'" in s and "wamid.SENT.1" in str(a) for s, a in conn.executed
    )
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'done'")
    assert any(
        "UPDATE meta_inbox_messages" in s and "delivered" in str(a) for s, a in conn.executed
    )
    assert conn.sql_contains("DELETE FROM wa_status_pending")
    # advisory lock taken + released for the winning thread
    assert conn.sql_contains("pg_try_advisory_lock")
    assert any(7 in a for _, a in conn.sql_with_args("pg_advisory_unlock"))


@pytest.mark.asyncio
async def test_bot_reply_aborts_on_human_takeover_before_generation() -> None:
    candidate = _candidate(2, thread_id=7, message_id=200, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=True),  # already taken over at claim time
            {"id": 2},  # fenced pre-generation abort RETURNING
        ],
        fetchval_results=[True],  # advisory lock
        fetch_results=[
            [candidate],  # candidate scan
            [],  # coalesce sweep — nothing else pending for this thread
        ],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "aborted_human"
    svc.send_message.assert_not_awaited()
    assert any("aborted_human_takeover" in s for s, _ in conn.executed)
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed'")


@pytest.mark.asyncio
async def test_window_closed_fails_without_send() -> None:
    candidate = _candidate(3, thread_id=7, message_id=300, needs_generation=False)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=True),
            {"body": "late reply"},
            {"id": 3},  # pre-send fence RETURNING
            {"id": 3},  # window-closed fenced fail RETURNING
        ],
        fetchval_results=[
            True,  # advisory lock
            False,  # window_open = False (>24h)
        ],
        fetch_results=[[candidate]],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "window_closed"
    svc.send_message.assert_not_awaited()
    assert any("24h_window_closed" in s for s, _ in conn.executed)


@pytest.mark.asyncio
async def test_send_failure_retries_with_backoff() -> None:
    candidate = _candidate(4, thread_id=7, message_id=400, needs_generation=False)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=True),
            {"body": "retry me"},
            {"id": 4},  # pre-send fence RETURNING
            {"id": 4},  # retry-requeue fenced RETURNING
        ],
        fetchval_results=[True, True],  # advisory lock, window_open
        fetch_results=[[candidate]],
    )
    pool = _make_pool(conn)
    svc = _wa_service(raise_exc=RuntimeError("graph 500"))

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "retry"
    retry_updates = conn.sql_with_args("status = 'pending'")
    assert retry_updates, "expected an UPDATE back to pending for retry"
    assert any("next_retry_at" in s for s, _ in retry_updates)
    assert any(1 in a for _, a in retry_updates)  # attempts == 1


@pytest.mark.asyncio
async def test_bot_generate_failure_retries_not_orphaned() -> None:
    # Panel 2026-06-04 (Codex): a raising bot_generate_fn must NOT leave the row
    # orphaned in 'generating' — it must retry with backoff (the v1 sentinel
    # raises NotImplementedError, and a transient RAG error in B must retry too).
    candidate = _candidate(6, thread_id=7, message_id=600, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            {"id": 6},  # generating-transition fenced RETURNING
            {"id": 6},  # gen-failure retry-requeue fenced RETURNING
        ],
        fetchval_results=[True],  # advisory lock
        fetch_results=[
            [candidate],
            [],  # coalesce sweep — nothing else pending
        ],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    async def _bot_raises(_thread: Any) -> str:
        raise NotImplementedError("bot not wired in v1")

    result = await process_outbox_once(pool, svc, _bot_raises)

    assert result == "retry"
    svc.send_message.assert_not_awaited()
    retry_updates = conn.sql_with_args("status = 'pending'")
    assert retry_updates, "bot-gen failure must re-queue, never orphan in generating"
    assert any("next_retry_at" in s for s, _ in retry_updates)
    assert any(1 in a for _, a in retry_updates)  # attempts == 1


@pytest.mark.asyncio
async def test_bot_generate_failure_terminal_after_max_attempts() -> None:
    candidate = _candidate(
        7, thread_id=7, message_id=700, needs_generation=True,
        attempts=wa_outbox_worker.MAX_ATTEMPTS - 1,
    )
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            {"id": 7},  # generating-transition fenced RETURNING
            {"id": 7},  # terminal-failure fenced RETURNING
        ],
        fetchval_results=[True],
        fetch_results=[[candidate], []],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    async def _bot_raises(_thread: Any) -> str:
        raise NotImplementedError("bot not wired in v1")

    result = await process_outbox_once(pool, svc, _bot_raises)

    assert result == "failed"
    svc.send_message.assert_not_awaited()
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed', attempts")
    assert any("bot_generate_failed_after_" in str(a) for _, a in conn.executed)


@pytest.mark.asyncio
async def test_send_failure_terminal_after_max_attempts() -> None:
    candidate = _candidate(
        5, thread_id=7, message_id=500, needs_generation=False,
        attempts=wa_outbox_worker.MAX_ATTEMPTS - 1,
    )
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=True),
            {"body": "last try"},
            {"id": 5},  # pre-send fence RETURNING
            {"id": 5},  # terminal send-failure fenced RETURNING
        ],
        fetchval_results=[True, True],
        fetch_results=[[candidate]],
    )
    pool = _make_pool(conn)
    svc = _wa_service(raise_exc=RuntimeError("graph 500"))

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "failed"
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed', attempts")
    assert any("send_failed_after_" in str(a) for _, a in conn.executed)


# ── P2: per-thread coalescing at claim ─────────────────────────────────────


@pytest.mark.asyncio
async def test_coalescing_supersedes_other_pending_bot_replies_same_thread() -> None:
    """2 pending bot-reply rows for the same thread → claim one, supersede the
    other, send exactly one reply."""
    winner = _candidate(10, thread_id=7, message_id=1000, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            {"id": 10},  # generating-transition fenced RETURNING
            {"id": 10},  # pre-send fence RETURNING
            {"id": 10},  # final commit RETURNING
            None,  # no staged status receipt
        ],
        fetchval_results=[
            True,  # advisory lock
            False,  # human_handling re-read at pre-send (no takeover)
            True,  # window_open
        ],
        fetch_results=[
            [winner],  # candidate scan claims outbox id=10
            [{"id": 11, "message_id": 1001}],  # coalesce sweep supersedes id=11
        ],
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.BURST.1"}]})

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    svc.send_message.assert_awaited_once()  # exactly ONE reply for the burst
    # the superseded row (id=11 / message 1001) was marked failed with the
    # coalescing marker, never touched by a send
    assert any(
        "needs_generation = true" in s and (7, 10) == a for s, a in conn.executed
    )
    assert any(
        "superseded_by_coalescing" in s and 1001 in a for s, a in conn.executed
    )


@pytest.mark.asyncio
async def test_coalescing_does_not_touch_pending_human_sends() -> None:
    """Coalescing must only ever supersede needs_generation=true rows — a
    pending HUMAN send for the same thread must survive untouched (the SQL
    filter itself enforces this; assert the coalesce query carries the
    needs_generation=true predicate)."""
    winner = _candidate(12, thread_id=7, message_id=1200, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            {"id": 12},
            {"id": 12},
            {"id": 12},
            None,
        ],
        fetchval_results=[True, False, True],
        fetch_results=[
            [winner],
            [],  # nothing superseded (the only other pending row is human-send, filtered out)
        ],
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.X"}]})

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    coalesce_calls = conn.sql_with_args("needs_generation = true")
    assert coalesce_calls, "coalesce query must filter on needs_generation = true"


# ── P3: per-thread advisory lock excludes concurrent claim of a locked thread ──


@pytest.mark.asyncio
async def test_advisory_lock_skips_candidate_whose_thread_is_locked() -> None:
    """Two candidates come back from the FOR UPDATE SKIP LOCKED scan: the
    first belongs to a thread another worker already owns (lock try fails),
    the second's thread is free. The worker must skip the first and claim the
    second — never process two rows of a thread another worker holds."""
    locked = _candidate(30, thread_id=99, message_id=3000, needs_generation=False)
    free = _candidate(31, thread_id=7, message_id=3001, needs_generation=False)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(thread_id=7, human_handling=False),
            {"body": "hi"},
            {"id": 31},  # pre-send fence RETURNING
            {"id": 31},  # final commit RETURNING
            None,  # no staged receipt
        ],
        fetchval_results=[
            False,  # advisory lock TRY for thread 99 → fails, already owned
            True,  # advisory lock TRY for thread 7 → succeeds
            True,  # window_open
        ],
        fetch_results=[[locked, free]],
    )
    pool = _make_pool(conn)
    svc = _wa_service(send_result={"messages": [{"id": "wamid.FREE.1"}]})

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "sent"
    # exactly two lock-try attempts, for both candidate threads in order
    lock_tries = conn.sql_with_args("pg_try_advisory_lock")
    assert len(lock_tries) == 2
    assert lock_tries[0][1] == (99,)
    assert lock_tries[1][1] == (7,)
    # the row that actually got claimed is id=31 (thread 7), never id=30
    claim_updates = conn.sql_with_args("SET status = 'claimed'")
    assert len(claim_updates) == 1
    assert claim_updates[0][1][0] == 31
    # released the WON thread's lock (7), not the skipped one (99)
    unlock_calls = conn.sql_with_args("pg_advisory_unlock")
    assert len(unlock_calls) == 1
    assert unlock_calls[0][1] == (7,)


@pytest.mark.asyncio
async def test_idle_when_every_candidate_thread_is_locked() -> None:
    locked_a = _candidate(40, thread_id=101, needs_generation=False)
    locked_b = _candidate(41, thread_id=102, needs_generation=False)
    conn = ScriptedConn(
        fetchval_results=[False, False],  # both candidates' threads owned elsewhere
        fetch_results=[[locked_a, locked_b]],
    )
    pool = _make_pool(conn)

    result = await process_outbox_once(pool, _wa_service(), _bot_gen)

    assert result == "idle"
    # no claim UPDATE happened, and (since claimed_row stayed None) no unlock
    # call was made either — the lock was never acquired for anything.
    assert not conn.sql_with_args("SET status = 'claimed'")
    assert not conn.sql_with_args("pg_advisory_unlock")


# ── P4: fencing abort — takeover mid-generation must result in NO send ─────


@pytest.mark.asyncio
async def test_fencing_aborts_send_when_takeover_happens_during_generation() -> None:
    """human_handling is FALSE when the row is claimed (generation proceeds)
    but flips to TRUE by the time we re-read it in the pre-send fence — the
    reply that was just generated must never be sent, and the row must not
    end up 'done'."""
    candidate = _candidate(20, thread_id=7, message_id=2000, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),  # NOT taken over yet at claim time
            {"id": 20},  # generating-transition fenced RETURNING
            {"id": 20},  # pre-send fence RETURNING (lease still ours)
        ],
        fetchval_results=[
            True,  # advisory lock
            True,  # human_handling re-read at pre-send → TRUE (takeover mid-gen)
        ],
        fetch_results=[[candidate], []],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "aborted_human"
    svc.send_message.assert_not_awaited()
    assert not conn.sql_contains("UPDATE wa_outbox SET status = 'done'")
    assert conn.sql_contains("aborted_human_takeover_pre_send")
    assert conn.sql_contains("UPDATE wa_outbox SET status = 'failed'")


@pytest.mark.asyncio
async def test_fencing_returns_fenced_when_lease_lost_before_generating_transition() -> None:
    """The generating-transition UPDATE is fenced by claim_token+status; if it
    matches zero rows (lease already reclaimed) the worker aborts silently
    with 'fenced' rather than plowing ahead with generation on a row it no
    longer owns."""
    candidate = _candidate(21, thread_id=7, message_id=2100, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            None,  # generating-transition fence RETURNING → 0 rows matched
        ],
        fetchval_results=[True],
        fetch_results=[[candidate], []],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "fenced"
    svc.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_fencing_returns_fenced_at_pre_send_when_lease_lost() -> None:
    """Lease lost between the generating-transition and the pre-send fence
    (e.g. a reclaimer beat the heartbeat) — abort before the Graph send."""
    candidate = _candidate(22, thread_id=7, message_id=2200, needs_generation=True)
    conn = ScriptedConn(
        fetchrow_results=[
            _thread_row(human_handling=False),
            {"id": 22},  # generating-transition fenced RETURNING → ok
            None,  # pre-send fence RETURNING → 0 rows, lease lost
        ],
        fetchval_results=[True],
        fetch_results=[[candidate], []],
    )
    pool = _make_pool(conn)
    svc = _wa_service()

    result = await process_outbox_once(pool, svc, _bot_gen)

    assert result == "fenced"
    svc.send_message.assert_not_awaited()


# ── P5/P6: lease heartbeat during generation ────────────────────────────────


@pytest.mark.asyncio
async def test_lease_heartbeat_loop_renews_and_stops_on_cancel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Direct, timing-independent test of the heartbeat loop itself: each
    sleep tick renews claim_expires_at fenced by claim_token+status, and a
    CancelledError (task.cancel()) propagates rather than being swallowed."""
    conn = ScriptedConn()
    real_sleep = asyncio.sleep
    tick_count = 0

    async def _fast_sleep(_seconds: float) -> None:
        nonlocal tick_count
        tick_count += 1
        if tick_count > 2:
            raise asyncio.CancelledError
        await real_sleep(0)

    monkeypatch.setattr(wa_outbox_worker.asyncio, "sleep", _fast_sleep)

    claim_token = uuid.uuid4()
    with pytest.raises(asyncio.CancelledError):
        await wa_outbox_worker._lease_heartbeat_loop(conn, 99, claim_token)

    renewals = [
        (s, a)
        for s, a in conn.executed
        if "claim_expires_at" in s and "status = 'generating'" in s
    ]
    assert len(renewals) == 2  # ticks 1 and 2 renewed; tick 3 raised before renewing
    assert all(a[0] == 99 and a[1] == claim_token for _, a in renewals)


@pytest.mark.asyncio
async def test_heartbeat_started_during_generation_and_cancelled_after() -> None:
    """The heartbeat task must be created before bot_generate_fn is awaited
    and reliably cancelled+awaited-to-completion once it returns, regardless
    of how long generation actually took."""
    events: list[str] = []

    async def _fake_heartbeat_loop(
        _conn: Any, _outbox_id: int, _claim_token: uuid.UUID
    ) -> None:
        events.append("started")
        try:
            await asyncio.sleep(1000)  # would hang the test if never cancelled
        except asyncio.CancelledError:
            events.append("cancelled")
            raise

    # bot_generate_fn must actually yield to the event loop at least once for
    # the concurrently-created heartbeat task to ever get a scheduling slice
    # before we cancel it — a non-yielding stub (module-level `_bot_gen`, used
    # everywhere else in this file) runs to completion in the same tick with
    # zero awaits inside it, so `heartbeat_task.cancel()` would fire before
    # asyncio ever ran the task even once. In production this is a non-issue:
    # the real bot_generate_fn (wa_inbox_bot.generate_bot_reply) always awaits
    # a real httpx call.
    async def _yielding_bot_gen(_thread: Any) -> str:
        await asyncio.sleep(0)
        return "generated bot reply"

    original = wa_outbox_worker._lease_heartbeat_loop
    wa_outbox_worker._lease_heartbeat_loop = _fake_heartbeat_loop
    try:
        candidate = _candidate(60, thread_id=7, message_id=6000, needs_generation=True)
        conn = ScriptedConn(
            fetchrow_results=[
                _thread_row(human_handling=False),
                {"id": 60},  # generating-transition fenced RETURNING
                {"id": 60},  # pre-send fence RETURNING
                {"id": 60},  # final commit RETURNING
                None,  # no staged receipt
            ],
            fetchval_results=[True, False, True],
            fetch_results=[[candidate], []],
        )
        pool = _make_pool(conn)
        svc = _wa_service(send_result={"messages": [{"id": "wamid.HB2"}]})

        result = await process_outbox_once(pool, svc, _yielding_bot_gen)
    finally:
        wa_outbox_worker._lease_heartbeat_loop = original

    assert result == "sent"
    assert events == ["started", "cancelled"]
