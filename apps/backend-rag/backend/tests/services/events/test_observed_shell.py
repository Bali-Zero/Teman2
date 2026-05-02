"""Tests for the observed-shell tier — Sprint 0 Track C2.

See ``backend/services/events/observed_shell.py`` and migration
``backend/db/migrations_v2/151_observed_shell_events.sql``.

Tests use mocked asyncpg pool/connection (AsyncMock) — same pattern as
``test_outbox.py``. No real DB.
"""
from __future__ import annotations

import json
import pathlib
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from backend.services.events import observed_shell
from backend.services.events.observed_shell import (
    JSONL_FALLBACK,
    ObservedShellBus,
    VALID_STATUSES,
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
    assert record["payload"] == {"duration_ms": 99}
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


# ── helper: async context manager wrapper ──────────────────────────────


def _async_ctx(value):
    """Return a context-manager-shaped object that yields `value` on
    `async with`. Mocks asyncpg's pool.acquire() return shape."""
    cm = MagicMock()
    cm.__aenter__ = AsyncMock(return_value=value)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm
