"""Unit tests for the persist race in scripts/wr2_canva_apply.py.

Empirical bug captured 2026-05-07 23:53 → 00:26 UTC for draft 0e8e1cf5:
the asyncpg connection opened in `run()` is held open for the duration of
the synchronous `subprocess.run([claude, -p, ...])` call inside
`invoke_claude_apply()`. After 24-32 minutes the Fly Postgres tunnel /
wireguard proxy closes the idle TCP socket. When `_apply_one_draft` then
calls `_persist_canva_result(conn, ...)`, asyncpg raises
`ConnectionDoesNotExistError`. Two empirical occurrences in
~/logs/wr2_canva_apply.launchd.err.log; both at the persist call site.

Pre-fix bug: `_log_run_telemetry(success)` runs BEFORE the persist, so
telemetry JSONL records "success" while the DB still has
`canva_design_id IS NULL`. The B0 instrumentation thus over-reports
the success rate.

Tests:
1. When `_persist_canva_result` raises (e.g. ConnectionDoesNotExistError),
   telemetry MUST NOT contain a "success" row for the attempt — only
   "persist_failed" with the exception text.
2. When the `conn` arg passed in is dead and a DSN is available, persist
   MUST re-open a fresh connection and complete the UPDATE successfully.
3. Happy path: telemetry "success" is written exactly once, AFTER persist
   has completed.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
APPLY_PATH = SCRIPTS_DIR / "wr2_canva_apply.py"


@pytest.fixture
def apply_mod(tmp_path, monkeypatch):
    """Load wr2_canva_apply with TELEMETRY_PATH redirected to tmp_path."""
    sys.modules.pop("wr2_canva_apply", None)
    spec = importlib.util.spec_from_file_location("wr2_canva_apply", APPLY_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_canva_apply"] = mod
    spec.loader.exec_module(mod)
    # Redirect telemetry to tmp so tests can assert on file contents.
    telemetry_file = tmp_path / "telemetry.jsonl"
    mod.TELEMETRY_PATH = telemetry_file
    # Pin pending dir to tmp so the .write_text in _apply_one_draft is harmless.
    pending_dir = tmp_path / "pending"
    mod.PENDING_PROD_DIR = pending_dir
    mod.PENDING_PROD_FILE = pending_dir / "canva_pending.json"
    return mod


def _make_row(draft_id: uuid.UUID) -> dict:
    return {
        "id": draft_id,
        "topic": "Indonesia Cracks Down on Sham Investor Visas",
        "tone": "pedagogico",
        "slides_json": {
            "slides": [
                {"index": 1, "title": "T1", "body": "B1"},
                {"index": 2, "title": "T2", "body": "B2"},
                {"index": 3, "title": "T3", "body": "B3"},
            ],
        },
    }


def _read_telemetry(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_persist_failure_does_not_log_telemetry_success(apply_mod):
    """When _persist_canva_result raises, telemetry must NOT have an outcome=success row.

    This reproduces the empirical 2026-05-07 23:53 bug: telemetry recorded
    "success" while the DB persist crashed with ConnectionDoesNotExistError.
    """
    draft_id = uuid.uuid4()
    row = _make_row(draft_id)

    fake_result = apply_mod.CanvaApplyResult(
        design_id="DAHITEST123",
        edit_url="https://www.canva.com/d/abc",
        view_url="https://www.canva.com/d/xyz",
        stdout_tail="ok",
        duration_sec=1943.4,
    )

    # invoke_claude_apply succeeds.
    invoke_mock = MagicMock(return_value=fake_result)

    # _persist_canva_result raises (simulating the dead-conn crash).
    class _ConnDead(Exception):
        pass

    persist_mock = AsyncMock(side_effect=_ConnDead("connection was closed in the middle of operation"))

    with patch.object(apply_mod, "invoke_claude_apply", invoke_mock), \
         patch.object(apply_mod, "_persist_canva_result", persist_mock), \
         patch.object(apply_mod, "_send_telegram", lambda *_a, **_kw: None), \
         patch.object(apply_mod, "build_canva_pending", lambda **_kw: {"slides": []}):
        ok = asyncio.run(apply_mod._apply_one_draft(MagicMock(), row, dsn="postgres://stub"))

    # Bug: persist failed → return False expected.
    assert ok is False, "Persist failure must propagate as False (not silent success)"

    # CORE ASSERTION: no "success" row in telemetry — only the persist failure.
    rows = _read_telemetry(apply_mod.TELEMETRY_PATH)
    success_rows = [r for r in rows if r.get("outcome") == "success"]
    assert success_rows == [], (
        f"Telemetry must NOT contain success when persist failed. "
        f"Got: {success_rows}"
    )

    # POSITIVE: there IS a row recording the persist failure.
    persist_failed_rows = [r for r in rows if r.get("outcome") == "persist_failed"]
    assert len(persist_failed_rows) == 1, (
        f"Expected exactly 1 persist_failed telemetry row, got {persist_failed_rows}"
    )
    assert "connection was closed" in persist_failed_rows[0].get("exc_head", "")
    assert persist_failed_rows[0]["draft_id"] == str(draft_id)


def test_persist_reopens_dead_connection(apply_mod, monkeypatch):
    """If the conn passed into _persist_canva_result is dead, the helper must
    re-open a fresh connection from DSN and complete the UPDATE.

    This is the runtime resilience: the existing `conn` was opened in run()
    before the long subprocess call; if the wireguard tunnel timed it out
    during the 32-min invoke_claude_apply, persist needs to reconnect.
    """
    draft_id = uuid.uuid4()

    # Simulated dead conn: is_closed() returns True.
    dead_conn = MagicMock()
    dead_conn.is_closed = MagicMock(return_value=True)
    dead_conn.execute = AsyncMock(side_effect=AssertionError("dead conn must NOT be used"))

    # Fresh conn the helper should reach for via asyncpg.connect.
    fresh_conn = MagicMock()
    fresh_conn.execute = AsyncMock(return_value="UPDATE 1")
    fresh_conn.close = AsyncMock()

    connect_mock = AsyncMock(return_value=fresh_conn)
    monkeypatch.setattr(apply_mod.asyncpg, "connect", connect_mock)

    fake_result = apply_mod.CanvaApplyResult(
        design_id="DAHITEST123",
        edit_url="https://www.canva.com/d/abc",
        view_url="https://www.canva.com/d/xyz",
        stdout_tail="ok",
        duration_sec=10.0,
    )

    asyncio.run(
        apply_mod._persist_canva_result(
            dead_conn, draft_id, fake_result, dsn="postgres://stub"
        )
    )

    # Dead conn must NOT have been used.
    dead_conn.execute.assert_not_called()
    # asyncpg.connect must have been invoked with the DSN.
    connect_mock.assert_awaited_once()
    args, kwargs = connect_mock.call_args
    # asyncpg.connect accepts dsn as first positional or as `dsn=` kwarg
    assert (args and args[0] == "postgres://stub") or kwargs.get("dsn") == "postgres://stub"
    # Fresh conn ran the UPDATE.
    fresh_conn.execute.assert_awaited_once()
    fresh_conn.close.assert_awaited_once()


def test_persist_uses_existing_conn_when_alive(apply_mod, monkeypatch):
    """Happy path: the existing conn is alive, no reconnect needed."""
    draft_id = uuid.uuid4()

    live_conn = MagicMock()
    live_conn.is_closed = MagicMock(return_value=False)
    live_conn.execute = AsyncMock(return_value="UPDATE 1")

    # asyncpg.connect MUST NOT be called.
    connect_mock = AsyncMock(side_effect=AssertionError("should not reconnect when conn alive"))
    monkeypatch.setattr(apply_mod.asyncpg, "connect", connect_mock)

    fake_result = apply_mod.CanvaApplyResult(
        design_id="DAHITEST123",
        edit_url="https://www.canva.com/d/abc",
        view_url="https://www.canva.com/d/xyz",
        stdout_tail="ok",
        duration_sec=10.0,
    )

    asyncio.run(
        apply_mod._persist_canva_result(
            live_conn, draft_id, fake_result, dsn="postgres://stub"
        )
    )

    live_conn.execute.assert_awaited_once()
    connect_mock.assert_not_awaited()


def test_happy_path_logs_success_after_persist(apply_mod):
    """End-to-end happy path: telemetry success row is written AFTER persist
    completes (i.e. exactly once, with the design_id surviving in DB).
    """
    draft_id = uuid.uuid4()
    row = _make_row(draft_id)

    fake_result = apply_mod.CanvaApplyResult(
        design_id="DAHITEST123",
        edit_url="https://www.canva.com/d/abc",
        view_url="https://www.canva.com/d/xyz",
        stdout_tail="ok",
        duration_sec=120.0,
    )

    # Ordered events list to verify ordering.
    events: list[str] = []

    def _fake_invoke(_path):
        events.append("invoke")
        return fake_result

    async def _fake_persist(_conn, _draft_id, _result, dsn=None):
        events.append("persist")

    # Wrap _log_run_telemetry to record call order.
    original_log = apply_mod._log_run_telemetry

    def _spy_log(*args, **kwargs):
        events.append(f"telemetry:{args[2]}")  # outcome is positional arg 2
        return original_log(*args, **kwargs)

    with patch.object(apply_mod, "invoke_claude_apply", _fake_invoke), \
         patch.object(apply_mod, "_persist_canva_result", _fake_persist), \
         patch.object(apply_mod, "_log_run_telemetry", _spy_log), \
         patch.object(apply_mod, "_send_telegram", lambda *_a, **_kw: None), \
         patch.object(apply_mod, "build_canva_pending", lambda **_kw: {"slides": []}):
        ok = asyncio.run(apply_mod._apply_one_draft(MagicMock(), row, dsn="postgres://stub"))

    assert ok is True
    # Order MUST be: invoke → persist → telemetry:success.
    # The bug was: invoke → telemetry:success → persist (race).
    assert events == ["invoke", "persist", "telemetry:success"], (
        f"Wrong ordering: {events}. Telemetry success must come AFTER persist."
    )
