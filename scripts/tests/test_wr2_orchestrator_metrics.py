"""Guilt+innocence tests for wr2_orchestrator_metrics (B11).

Migration 203 created `wr2_orchestrator_metrics` with zero production writer
(research/operations/2026-07-14-wr2-deep-audit.md §1/§8). These tests cover
the module's two hard contracts:

  1. record_step() / resolve_carousel_id() are FAIL-OPEN-LOUD — a DB error
     (dead connection, FK violation, whatever) is caught, logged, and never
     propagates to the caller. A metrics failure must never kill a render.
  2. A healthy write (fake connection that succeeds) actually reaches
     conn.execute() with the right SQL shape and values — the innocence
     case: fail-open must not become "never actually writes".

No real Postgres — a minimal fake asyncpg.Connection stands in.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str) -> ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    assert spec and spec.loader, f"cannot load {name}"
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


wom = _load("wr2_orchestrator_metrics")


class _FakeConn:
    """Records every execute()/fetchrow() call; can be told to fail."""

    def __init__(self, *, fail: bool = False, fetchrow_result: dict | None = None):
        self.fail = fail
        self.fetchrow_result = fetchrow_result
        self.executed: list[tuple[str, tuple]] = []
        self.fetchrow_calls: list[tuple[str, tuple]] = []
        self.closed = False

    async def execute(self, sql: str, *args):
        if self.fail:
            raise RuntimeError("simulated DB failure")
        self.executed.append((sql, args))
        return "INSERT 0 1"

    async def fetchrow(self, sql: str, *args):
        if self.fail:
            raise RuntimeError("simulated DB failure")
        self.fetchrow_calls.append((sql, args))
        return self.fetchrow_result

    async def close(self):
        self.closed = True


# ── record_step: guilt (must fail open, never raise) ────────────────────────


def test_record_step_db_failure_does_not_raise():
    import asyncio

    conn = _FakeConn(fail=True)

    async def go():
        return await wom.record_step(
            carousel_id="11111111-1111-1111-1111-111111111111",
            step_name="brief_interpreter",
            step_index=1,
            success=True,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is False  # reported failure, but did NOT raise


def test_record_step_none_carousel_id_is_a_noop_not_a_crash():
    import asyncio

    conn = _FakeConn()

    async def go():
        return await wom.record_step(
            carousel_id=None,
            step_name="brief_interpreter",
            step_index=1,
            success=True,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is False
    assert conn.executed == []  # never even attempted the FK-doomed insert


def test_record_step_unknown_step_name_is_a_noop():
    import asyncio

    conn = _FakeConn()

    async def go():
        return await wom.record_step(
            carousel_id="11111111-1111-1111-1111-111111111111",
            step_name="not_a_real_step",
            step_index=1,
            success=True,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is False
    assert conn.executed == []


def test_resolve_carousel_id_db_failure_returns_none_not_raise():
    import asyncio

    conn = _FakeConn(fail=True)

    async def go():
        return await wom.resolve_carousel_id(
            conn, topic="some topic", session_id="test-session"
        )

    result = asyncio.run(go())
    assert result is None


# ── innocence: a healthy write actually reaches conn.execute() ──────────────


def test_record_step_healthy_write_reaches_execute_with_right_shape():
    import asyncio

    conn = _FakeConn()

    async def go():
        return await wom.record_step(
            carousel_id="11111111-1111-1111-1111-111111111111",
            step_name="ig_publisher",
            step_index=8,
            model="ig-graph-api",
            tier=1,
            latency_ms=1234,
            retry_count=0,
            cost_usd_figurative=0.0,
            success=True,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is True
    assert len(conn.executed) == 1
    sql, args = conn.executed[0]
    assert "INSERT INTO wr2_orchestrator_metrics" in sql
    assert args[0] == "11111111-1111-1111-1111-111111111111"  # carousel_id
    assert args[1] == "ig_publisher"  # step_name
    assert args[2] == 8  # step_index
    assert args[10] is True  # success


def test_record_step_failure_row_carries_error_class_and_truncated_message():
    import asyncio

    conn = _FakeConn()
    long_msg = "x" * 5000

    async def go():
        return await wom.record_step(
            carousel_id="11111111-1111-1111-1111-111111111111",
            step_name="image_prompt_author",
            step_index=3,
            success=False,
            error_class="all_images_failed",
            error_message=long_msg,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is True
    sql, args = conn.executed[0]
    assert args[10] is False  # success
    assert args[11] == "all_images_failed"  # error_class
    assert len(args[12]) <= 2000  # error_message truncated


def test_resolve_carousel_id_finds_existing_row_by_topic():
    import asyncio

    conn = _FakeConn(fetchrow_result={"carousel_id": "22222222-2222-2222-2222-222222222222"})

    async def go():
        return await wom.resolve_carousel_id(
            conn, topic="existing topic", session_id="test-session"
        )

    result = asyncio.run(go())
    assert result == "22222222-2222-2222-2222-222222222222"
    assert len(conn.fetchrow_calls) == 1
    sql, args = conn.fetchrow_calls[0]
    assert "SELECT carousel_id FROM wr2_carousel_runs" in sql
    assert args[0] == "existing topic"


def test_resolve_carousel_id_rejects_empty_topic_without_touching_db():
    import asyncio

    conn = _FakeConn()

    async def go():
        return await wom.resolve_carousel_id(conn, topic="   ", session_id="x")

    result = asyncio.run(go())
    assert result is None
    assert conn.fetchrow_calls == []


def test_record_step_tier_out_of_range_is_a_noop():
    import asyncio

    conn = _FakeConn()

    async def go():
        return await wom.record_step(
            carousel_id="11111111-1111-1111-1111-111111111111",
            step_name="critic",
            step_index=5,
            tier=99,
            success=True,
            conn=conn,
        )

    result = asyncio.run(go())
    assert result is False
    assert conn.executed == []
