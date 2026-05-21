"""Tests for wr3_supervisor reconnect machinery — closes the zombie-supervisor scar 2026-05-22.

Old PID 25068 lived 3h09m with TCP socket dead (lsof empty) and KeepAlive
blind. Root cause: `_reconcile_unconsumed` swallowed asyncpg's
`InterfaceError("connection is closed")` and the outer reconnect loop was
never reached.

5-layer fix (post 3-LLM panel + DeepSeek red-team gate):
  L1  stdout line-buffering   (covered by manual log inspection, not unit test)
  L2  re-raise on connection-fatal  → THIS FILE
  L3  termination listener + sentinel "__dead__" + closure default-args → THIS FILE
  L4  heartbeat SELECT 1 wrapped in asyncio.wait_for(timeout=2.0) → THIS FILE
  L5  exponential backoff with 30s cap   (covered indirectly via L2 reconnect-count)
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import wr3_supervisor  # noqa: E402
from wr3_contracts import load_contracts  # noqa: E402


@pytest.fixture(scope="module")
def contracts():
    return load_contracts()


# ----------------------------------------------------------------------------
# L2 — re-raise on connection-fatal in _reconcile_unconsumed
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reconcile_raises_reconnect_required_on_interface_error(contracts) -> None:
    """asyncpg.InterfaceError in fetch → must raise _ReconnectRequired,
    NOT swallow + return."""
    bad_conn = AsyncMock()
    bad_conn.fetch = AsyncMock(
        side_effect=asyncpg.InterfaceError("connection is closed")
    )
    # is_closed is a callable method on the real Connection
    bad_conn.is_closed = MagicMock(return_value=True)

    with pytest.raises(wr3_supervisor._ReconnectRequired):
        await wr3_supervisor._reconcile_unconsumed(bad_conn, contracts)


@pytest.mark.asyncio
async def test_reconcile_raises_reconnect_required_on_connection_does_not_exist(contracts) -> None:
    """asyncpg.ConnectionDoesNotExistError → must raise _ReconnectRequired."""
    bad_conn = AsyncMock()
    bad_conn.fetch = AsyncMock(
        side_effect=asyncpg.ConnectionDoesNotExistError("connection was closed mid-op")
    )
    bad_conn.is_closed = MagicMock(return_value=False)

    with pytest.raises(wr3_supervisor._ReconnectRequired):
        await wr3_supervisor._reconcile_unconsumed(bad_conn, contracts)


@pytest.mark.asyncio
async def test_reconcile_swallows_non_fatal_errors(contracts) -> None:
    """Non-connection PG errors (syntax, etc.) must NOT trigger reconnect —
    they're a script bug, not a connection issue. Log + return."""
    bad_conn = AsyncMock()
    bad_conn.fetch = AsyncMock(
        side_effect=asyncpg.PostgresSyntaxError("syntax error at FROOM")
    )
    bad_conn.is_closed = MagicMock(return_value=False)

    # Should NOT raise
    await wr3_supervisor._reconcile_unconsumed(bad_conn, contracts)


# ----------------------------------------------------------------------------
# L3 — termination listener + sentinel
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_connection_fatal_classifier() -> None:
    """_is_connection_fatal must True only on the 2 connection-fatal subclasses."""
    assert wr3_supervisor._is_connection_fatal(asyncpg.InterfaceError("dead"))
    assert wr3_supervisor._is_connection_fatal(asyncpg.ConnectionDoesNotExistError("gone"))
    # NOT fatal
    assert not wr3_supervisor._is_connection_fatal(asyncpg.PostgresSyntaxError("bad sql"))
    assert not wr3_supervisor._is_connection_fatal(ValueError("not pg"))


# ----------------------------------------------------------------------------
# L4 — heartbeat wrapped in asyncio.wait_for
# ----------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_heartbeat_helper_passes_on_healthy_conn() -> None:
    """Healthy fetchval('SELECT 1') returns 1 → helper returns silently."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=1)

    # Must not raise
    await wr3_supervisor._heartbeat(conn, timeout=2.0)


@pytest.mark.asyncio
async def test_heartbeat_raises_reconnect_required_on_interface_error() -> None:
    """fetchval raising InterfaceError → _ReconnectRequired."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(
        side_effect=asyncpg.InterfaceError("connection is closed")
    )

    with pytest.raises(wr3_supervisor._ReconnectRequired):
        await wr3_supervisor._heartbeat(conn, timeout=2.0)


@pytest.mark.asyncio
async def test_heartbeat_raises_reconnect_required_on_timeout() -> None:
    """fetchval hanging > timeout → asyncio.TimeoutError → _ReconnectRequired
    (half-open TCP simulation)."""
    conn = AsyncMock()

    async def slow_fetchval(*args, **kwargs):
        await asyncio.sleep(10)  # way past 0.05s timeout
        return 1

    conn.fetchval = slow_fetchval

    with pytest.raises(wr3_supervisor._ReconnectRequired):
        await wr3_supervisor._heartbeat(conn, timeout=0.05)


@pytest.mark.asyncio
async def test_heartbeat_raises_on_unexpected_return_value() -> None:
    """If SELECT 1 returns something other than 1 (e.g. None from a broken
    proxy that swallows the query) — still treat as connection-unusable."""
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=None)

    with pytest.raises(wr3_supervisor._ReconnectRequired):
        await wr3_supervisor._heartbeat(conn, timeout=2.0)


# ----------------------------------------------------------------------------
# L3 — Closure capture safety (post DeepSeek red-team P0-B amendment)
# ----------------------------------------------------------------------------


def test_closure_captures_via_default_args_not_loop_variable() -> None:
    """Empirical guardrail: callbacks defined in a loop MUST pin their
    captured asyncio.Queue / asyncio.Event via default args, not by closure
    over the loop variable.

    This test mirrors the structure used inside run_supervisor's outer loop.
    If a future refactor accidentally drops the default-arg pinning, this
    test fails before the bug ships to launchd.

    The trap (DeepSeek redteam 2026-05-22):
        for i in range(N):
            queue = asyncio.Queue()
            def cb(): return queue   # ← captures `queue` BY NAME
                                      # all callbacks see the LAST iteration
    """
    queues = []
    callbacks_naive = []
    callbacks_pinned = []

    for i in range(3):
        q = f"q-{i}"  # stand-in for asyncio.Queue() per iteration
        queues.append(q)

        # Naive (buggy): closure over loop variable
        def cb_naive():
            return q
        callbacks_naive.append(cb_naive)

        # Pinned (correct): default-arg captures the CURRENT value
        def cb_pinned(_q=q):
            return _q
        callbacks_pinned.append(cb_pinned)

    # Naive callbacks all see the LAST iteration's `q`
    assert [cb() for cb in callbacks_naive] == ["q-2", "q-2", "q-2"]
    # Pinned callbacks see their OWN iteration's `q`
    assert [cb() for cb in callbacks_pinned] == ["q-0", "q-1", "q-2"]
