"""Tests for the observed-shell tier — Sprint 0 Track C2.

See ``backend/services/events/observed_shell.py`` and migration
``backend/db/migrations_v2/151_observed_shell_events.sql``.

Tests use mocked asyncpg pool/connection (AsyncMock) — same pattern as
``test_outbox.py``. No real DB.

Round-1 review feedback (4-LLM cross-review of PR #426):
- Add non-JSON-serializable payload test (reviewer-Claude/Gemini/DeepSeek/GPT-5.5)
- Add pool.acquire() raises test (reviewer-DeepSeek)
- Add JSONL fallback parent-dir creation test (reviewer-Claude)
- Add emit_one() convenience wrapper test (reviewer-Claude)
"""
from __future__ import annotations

import datetime as dt
import decimal
import json
from unittest.mock import AsyncMock, MagicMock

import asyncpg
import pytest

from backend.services.events import observed_shell
from backend.services.events.observed_shell import (
    ObservedShellBus,
    emit_one,
)


# ── happy path: pool valid, INSERT executes ───────────────────────────


@pytest.mark.asyncio
async def test_emit_happy_path_inserts_via_pool():
    """When db_pool is valid, emit() runs the INSERT statement."""
    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock()

    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(
        return_value=_async_ctx(fake_conn),
    )

    bus = ObservedShellBus(fake_pool)
    await bus.emit(
        "translate.hourly",
        "ok",
        {"duration_ms": 1234, "items": 42},
        trace_id="abc-123",
    )

    fake_conn.execute.assert_awaited_once()
    args = fake_conn.execute.await_args.args
    sql = args[0]
    # Insert into observed_shell_events with 4 positional binds
    assert "INSERT INTO observed_shell_events" in sql
    assert "automation_name, status, payload, trace_id" in sql
    assert args[1] == "translate.hourly"
    assert args[2] == "ok"
    payload_json = args[3]
    assert json.loads(payload_json) == {"duration_ms": 1234, "items": 42}
    assert args[4] == "abc-123"


# ── degraded path: pool=None falls back to JSONL ──────────────────────


@pytest.mark.asyncio
async def test_emit_with_no_pool_falls_back_to_jsonl(tmp_path, monkeypatch):
    """When db_pool is None, the record is appended to JSONL_FALLBACK."""
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    bus = ObservedShellBus(db_pool=None)
    await bus.emit("backup.daily", "ok", {"duration_ms": 99}, trace_id=None)

    assert fake_jsonl.exists()
    lines = fake_jsonl.read_text().strip().splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["automation_name"] == "backup.daily"
    assert record["status"] == "ok"
    # payload_json is pre-serialized — round-trip back to dict for assertion.
    assert json.loads(record["payload_json"]) == {"duration_ms": 99}
    assert record["_fallback_reason"] == "no db_pool"


# ── degraded path: PG error falls back to JSONL ───────────────────────


@pytest.mark.asyncio
async def test_emit_with_pg_error_falls_back_to_jsonl(tmp_path, monkeypatch):
    """When the INSERT raises PostgresError, the record lands in JSONL.

    The cell must NOT see the error — emit() returns cleanly so the
    parent automation continues."""
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    fake_conn = AsyncMock()
    fake_conn.execute = AsyncMock(side_effect=asyncpg.PostgresError("simulated failure"))

    fake_pool = MagicMock()
    fake_pool.acquire = MagicMock(return_value=_async_ctx(fake_conn))

    bus = ObservedShellBus(fake_pool)
    # Must not raise:
    await bus.emit("trans.batch", "error", {"err": "x"}, trace_id="t")

    assert fake_jsonl.exists()
    record = json.loads(fake_jsonl.read_text().strip().splitlines()[0])
    assert record["automation_name"] == "trans.batch"
    assert "db error" in record["_fallback_reason"]
    assert "simulated failure" in record["_fallback_reason"]


# ── invalid status coerces to "error" ─────────────────────────────────


@pytest.mark.asyncio
async def test_emit_invalid_status_coerces_to_error(tmp_path, monkeypatch):
    """Non-allowlisted statuses get coerced to 'error' (defensive)."""
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    bus = ObservedShellBus(db_pool=None)  # forces JSONL path
    await bus.emit("trans.run", "totally-bogus", {})

    record = json.loads(fake_jsonl.read_text().strip().splitlines()[0])
    assert record["status"] == "error"


# ── round-2 review fixes: non-serializable payload, pool.acquire raise, ──
# ── parent-dir creation, emit_one() wrapper ──────────────────────────────


@pytest.mark.asyncio
async def test_emit_with_non_serializable_payload_does_not_raise(
    tmp_path, monkeypatch
):
    """Round-1 review (4/4 LLMs flagged): a payload with datetime / Decimal /
    asyncpg.Record objects must NOT crash emit() and must NOT crash the
    JSONL fallback either. Both paths use ``default=str`` so the type is
    coerced to its string repr.
    """
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    payload_with_unfriendly_types = {
        "when": dt.datetime(2026, 5, 2, 17, 0, tzinfo=dt.timezone.utc),
        "amount": decimal.Decimal("1234.56"),
        "ratio": float("nan"),  # also non-strict-JSON
    }

    bus = ObservedShellBus(db_pool=None)
    # Must not raise:
    await bus.emit("paymentsync", "ok", payload_with_unfriendly_types)

    assert fake_jsonl.exists()
    record = json.loads(fake_jsonl.read_text().strip().splitlines()[0])
    # payload_json round-trips to a dict whose values are stringified versions
    payload_round = json.loads(record["payload_json"])
    assert "2026-05-02" in payload_round["when"]
    assert payload_round["amount"] == "1234.56"


@pytest.mark.asyncio
async def test_emit_with_pool_acquire_raising_falls_back(tmp_path, monkeypatch):
    """Round-2 review (DeepSeek): if pool.acquire() itself raises (e.g.
    PoolClosedError) — not just the .execute() — the bus must still degrade
    gracefully and route to JSONL.
    """
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    fake_pool = MagicMock()
    # acquire() raises immediately when entered.
    bad_ctx = MagicMock()
    bad_ctx.__aenter__ = AsyncMock(
        side_effect=asyncpg.InterfaceError("pool closed")
    )
    bad_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_pool.acquire = MagicMock(return_value=bad_ctx)

    bus = ObservedShellBus(fake_pool)
    # Must not raise:
    await bus.emit("translate.hourly", "ok", {"x": 1})

    assert fake_jsonl.exists()
    record = json.loads(fake_jsonl.read_text().strip().splitlines()[0])
    assert record["automation_name"] == "translate.hourly"
    # InterfaceError is a PostgresError subclass -> "db error" branch.
    assert "db error" in record["_fallback_reason"] or \
           "unexpected" in record["_fallback_reason"]


@pytest.mark.asyncio
async def test_emit_creates_parent_directory_for_jsonl(tmp_path, monkeypatch):
    """Round-2 review (Claude): on a fresh host where ~/logs/ doesn't yet
    exist, the first emit() must create it, not crash.
    """
    fake_jsonl = tmp_path / "subdir" / "missing" / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    bus = ObservedShellBus(db_pool=None)
    await bus.emit("backup.daily", "ok", {"x": 1})

    assert fake_jsonl.parent.is_dir()
    assert fake_jsonl.exists()


@pytest.mark.asyncio
async def test_emit_one_convenience_wrapper(tmp_path, monkeypatch):
    """Round-2 review (Claude): emit_one() is in __all__ but had no test."""
    fake_jsonl = tmp_path / "observed-shell.jsonl"
    monkeypatch.setattr(observed_shell, "JSONL_FALLBACK", fake_jsonl)

    await emit_one(None, "trans.run", "ok", {"items": 5})

    assert fake_jsonl.exists()
    record = json.loads(fake_jsonl.read_text().strip().splitlines()[0])
    assert record["automation_name"] == "trans.run"


# ── helper: async context manager wrapper ──────────────────────────────


def _async_ctx(value):
    """Return a context-manager-shaped object that yields `value` on
    `async with`. Mocks asyncpg's pool.acquire() return shape."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm
