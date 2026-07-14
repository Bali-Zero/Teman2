"""Tests for wr2_image_requeue.py — the image-lane requeue verb (2026-07-14).

Sibling of test_wr2_rerender_requeue.py (HTML render lane). This one covers
the DB-leg function `requeue_image_failed_draft` (GUILT: only `image_failed`
rows are touched, and land exactly on `drafts` — the sole pre-image status
any producer in this codebase actually writes) plus the CLI's `_run` dispatch
(status filter + dry-run + not-found handling). No real DB — asyncpg mocked.
"""
from __future__ import annotations

import asyncio
import importlib.util
import sys
import uuid
from pathlib import Path
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock

import pytest

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


req = _load("wr2_image_requeue")


# ─────────────────────────────────────────────────────────────────────────
# requeue_image_failed_draft — DB-leg guard
# ─────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_requeue_image_failed_lands_on_drafts_with_guard():
    """GUILT: the UPDATE targets status='drafts' (the only pre-image status
    any current producer writes), gated on source status='image_failed', and
    leaves a trace note in rejection_reason."""
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": "abc"}
    draft_id = uuid.uuid4()
    ok = await req.requeue_image_failed_draft(conn, draft_id)
    assert ok is True
    call = conn.fetchrow.call_args
    sql = call[0][0]
    params = call[0][1:]
    assert "SET status" in sql
    assert "WHERE id = $1" in sql
    assert "AND status = $4" in sql
    # positional params: draft_id, target_status, note, source_status
    assert params[0] == draft_id
    assert params[1] == "drafts"
    assert "2026-07-14" in params[2]
    assert params[3] == "image_failed"


@pytest.mark.asyncio
async def test_requeue_refused_when_not_image_failed():
    """INNOCENCE: 0 rows matched (wrong status, or already moved on) ->
    False, never a silent no-op success."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    assert await req.requeue_image_failed_draft(conn, "abc") is False


# ─────────────────────────────────────────────────────────────────────────
# CLI _run — status filter + dry-run + not-found
# ─────────────────────────────────────────────────────────────────────────


def _fake_conn(status_by_id: dict):
    """Build an AsyncMock asyncpg-like connection.

    fetchrow: first call per draft_id (status probe) returns {"status": ...}
    or None; subsequent calls (the actual requeue UPDATE) return {"id": ...}
    when the row's status is 'image_failed', else None (mirrors the real
    WHERE status = $4 CAS never matching a wrong status).
    """
    conn = AsyncMock()

    async def fetchrow(sql, *params):
        if "SELECT status" in sql:
            draft_id = params[0]
            status = status_by_id.get(draft_id)
            return {"status": status} if status is not None else None
        # the requeue UPDATE ... RETURNING id
        draft_id = params[0]
        source_status = params[3]
        if status_by_id.get(draft_id) == source_status:
            return {"id": draft_id}
        return None

    conn.fetchrow = fetchrow
    conn.close = AsyncMock()
    return conn


def test_run_requeues_only_image_failed_drafts(monkeypatch):
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    conn = _fake_conn({d1: "image_failed", d2: "drafts_imaged"})
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(req.asyncpg, "connect", AsyncMock(return_value=conn))

    rc = asyncio.run(req._run([d1, d2], dry_run=False))
    assert rc == 1  # d2 refused → overall failure exit code


def test_run_all_succeed_returns_zero(monkeypatch):
    d1 = uuid.uuid4()
    conn = _fake_conn({d1: "image_failed"})
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(req.asyncpg, "connect", AsyncMock(return_value=conn))

    rc = asyncio.run(req._run([d1], dry_run=False))
    assert rc == 0


def test_run_not_found_is_a_failure(monkeypatch):
    d1 = uuid.uuid4()
    conn = _fake_conn({})  # nothing exists
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(req.asyncpg, "connect", AsyncMock(return_value=conn))

    rc = asyncio.run(req._run([d1], dry_run=False))
    assert rc == 1


def test_run_dry_run_never_calls_update(monkeypatch):
    d1 = uuid.uuid4()
    calls = []

    conn = AsyncMock()

    async def fetchrow(sql, *params):
        calls.append(sql)
        if "SELECT status" in sql:
            return {"status": "image_failed"}
        raise AssertionError("dry-run must never execute the UPDATE")

    conn.fetchrow = fetchrow
    conn.close = AsyncMock()
    monkeypatch.setenv("DATABASE_URL", "postgres://fake")
    monkeypatch.setattr(req.asyncpg, "connect", AsyncMock(return_value=conn))

    rc = asyncio.run(req._run([d1], dry_run=True))
    assert rc == 0
    assert all("SELECT status" in c for c in calls)


def test_run_missing_dsn_returns_2(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    rc = asyncio.run(req._run([uuid.uuid4()], dry_run=False))
    assert rc == 2


def test_main_rejects_invalid_uuid():
    rc = req.main(["not-a-uuid"])
    assert rc == 2


if __name__ == "__main__":
    import pytest as _pytest

    raise SystemExit(_pytest.main([__file__, "-q"]))
