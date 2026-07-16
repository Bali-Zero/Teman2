"""Tests for the per-draft lease CAS added to wr2_image_generator.py (B5,
2026-07-14 — overlap-prevention, audit cure-plan §10 item 5), PLUS the
stale-lease steal sweep added 2026-07-16 (`_reset_stale_image_leases`).

`wr2_image_generator.py` was the one WR2 lane with NO CAS/lease at all —
unlike the HTML-render and Canva-render lanes (`_pg.py`
`acquire_html_lease_and_fetch` / `acquire_lease_and_fetch`), which already
guard their fetch on `lease_owner IS NULL`. Two overlapping invocations
(a stuck run still mid-slide when the supervisor's reconcile sweep re-kicks
the same plist) could double-process the same draft and — sharper for the
detection fix in the same PR — race writes into the SAME shared
`~/.codex/generated_images/` tree that `_select_fresh_codex_png` scans.

The CAS lease itself had no stale-lease steal: a holder that crashed/was
SIGTERM'd before releasing left `lease_owner` set forever, starving the
draft on every subsequent run (live: draft a9e4e5d8-5afa-41ff-8c8a-
dad947701037 held by a dead PID for ~31h). `_reset_stale_image_leases`
mirrors the sibling lanes' watchdog-sweep convention (`_pg.py`
`reset_stale_leases` / `reset_stale_html_leases`): a separate sweep called
once at the top of `run()`, not baked into the CAS's WHERE clause.

DB-free: `asyncpg.Connection` is an AsyncMock, matching the style already
used in apps/backend-rag/backend/tests/unit/services/canva_renderer_v2/
test_pg.py for the sibling lanes.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
GEN_PATH = SCRIPTS_DIR / "wr2_image_generator.py"


@pytest.fixture
def wig(monkeypatch):
    sys.modules.pop("wr2_image_generator", None)
    sys.modules.pop("wr2_flowkit_client", None)
    monkeypatch.setenv("WR2_IMAGE_BACKEND", "auto")
    monkeypatch.setenv("WR2_IMAGE_VLM_VALIDATION", "false")
    spec = importlib.util.spec_from_file_location("wr2_image_generator", GEN_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_image_generator"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_lease_owner_id_identifies_host_and_pid(wig):
    owner = wig._lease_owner_id()
    assert owner.startswith("wr2-image-generator:")
    import os
    assert str(os.getpid()) in owner


@pytest.mark.asyncio
async def test_fetch_pending_unchanged_status_filter(wig):
    """Regression guard: adding the lease CAS must not touch the existing
    fetch-candidates query (which still just SELECTs, no CAS — the lease
    is acquired per-row afterward, in `run()`)."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    await wig._fetch_pending(conn, limit=2)
    sql = conn.fetch.call_args[0][0]
    assert "status IN ('drafts_checked', 'drafts')" in sql
    assert "lease_owner" not in sql  # unchanged — CAS lives in _acquire_image_lease


@pytest.mark.asyncio
async def test_acquire_image_lease_success_returns_true(wig):
    conn = AsyncMock()
    conn.fetchrow.return_value = {"id": "abc"}
    ok = await wig._acquire_image_lease(conn, "abc", "wr2-image-generator:host:123")
    assert ok is True
    sql, draft_id, owner = conn.fetchrow.call_args[0]
    assert "lease_owner = $2" in sql
    assert "lease_owner IS NULL" in sql
    assert "status IN ('drafts_checked', 'drafts')" in sql
    assert draft_id == "abc"
    assert owner == "wr2-image-generator:host:123"


@pytest.mark.asyncio
async def test_acquire_image_lease_loss_returns_false(wig):
    """INNOCENCE: a draft already leased by a concurrent invocation (the
    overlap case this fix exists for) is refused, not double-claimed."""
    conn = AsyncMock()
    conn.fetchrow.return_value = None
    ok = await wig._acquire_image_lease(conn, "abc", "wr2-image-generator:host:123")
    assert ok is False


@pytest.mark.asyncio
async def test_persist_imaged_clears_lease_guarded_by_owner(wig):
    conn = AsyncMock()
    await wig._persist_imaged(
        conn, "abc", [{"slide_number": 1}], {}, lease_owner="wr2-image-generator:host:123",
    )
    sql, *args = conn.execute.call_args[0]
    assert "status              = 'drafts_imaged'" in sql or "status" in sql and "'drafts_imaged'" in sql
    assert "lease_owner         = NULL" in sql or "lease_owner" in sql and "NULL" in sql
    assert args[-1] == "wr2-image-generator:host:123"


@pytest.mark.asyncio
async def test_persist_imaged_lease_owner_none_is_a_noop_guard(wig):
    """dry-run / no-lease callers pass lease_owner=None — the SQL's own
    `$4::text IS NULL OR lease_owner = $4` clause makes that an unconditional
    clear (back-compat with any caller that never acquired a lease)."""
    conn = AsyncMock()
    await wig._persist_imaged(conn, "abc", [], {}, lease_owner=None)
    args = conn.execute.call_args[0]
    assert args[-1] is None


@pytest.mark.asyncio
async def test_reset_stale_image_leases_default_ttl_is_40min(wig):
    assert wig.IMAGE_LEASE_STALE_MINUTES == 40


@pytest.mark.asyncio
async def test_reset_stale_image_leases_sql_scopes_by_staleness_and_status(wig):
    """GUILT: the sweep's WHERE clause is staleness-scoped (owner set AND
    lease_acquired_at older than the TTL), not a blanket clear-all — matching
    the sibling lanes' `reset_stale_leases`/`reset_stale_html_leases` shape."""
    conn = AsyncMock()
    conn.fetch.return_value = [{"id": "abc"}]
    ids = await wig._reset_stale_image_leases(conn, stale_after_minutes=40)
    assert ids == ["abc"]
    sql, ttl_arg = conn.fetch.call_args[0]
    assert "lease_owner IS NOT NULL" in sql
    assert "lease_acquired_at < NOW()" in sql
    assert "status IN ('drafts_checked', 'drafts')" in sql
    assert ttl_arg == "40"


@pytest.mark.asyncio
async def test_reset_stale_image_leases_no_op_when_nothing_stale(wig):
    """INNOCENCE: a fresh lease (or no lease at all) is never swept — the SQL
    predicate does the filtering; an empty result from the (mocked) DB round
    trip must propagate as an empty list, not synthesize a false reclaim."""
    conn = AsyncMock()
    conn.fetch.return_value = []
    ids = await wig._reset_stale_image_leases(conn)
    assert ids == []


@pytest.mark.asyncio
async def test_run_sweeps_stale_leases_before_fetch_unless_dry_run(wig, monkeypatch):
    """The sweep runs once at the top of `run()`, before any fetch — mirrors
    `orchestrator.py::run()` (Canva) and `wr2_html_render_apply.py::run()`
    (HTML), and must NOT fire during --dry-run (no DB mutation on a dry pass)."""
    calls: list[bool] = []

    async def _fake_reset(conn, stale_after_minutes=wig.IMAGE_LEASE_STALE_MINUTES):
        calls.append(True)
        return []

    monkeypatch.setattr(wig, "_reset_stale_image_leases", _fake_reset)
    monkeypatch.setenv("DATABASE_URL", "postgresql://fake/fake")

    class _FakeConn:
        async def fetch(self, *a, **kw):
            return []

    class _FakeAcquireCtx:
        async def __aenter__(self):
            return _FakeConn()

        async def __aexit__(self, *exc):
            return False

    class _FakePool:
        def acquire(self):
            return _FakeAcquireCtx()

        async def close(self):
            return None

    async def _fake_create_pool(*a, **kw):
        return _FakePool()

    monkeypatch.setattr(wig.asyncpg, "create_pool", _fake_create_pool)

    await wig.run(dry_run=True)
    assert calls == []  # dry-run: sweep skipped

    await wig.run(dry_run=False)
    assert calls == [True]  # live run: sweep fired exactly once


@pytest.mark.asyncio
async def test_mark_image_failed_clears_lease_guarded_by_owner(wig):
    conn = AsyncMock()
    await wig._mark_image_failed(
        conn, "abc", "all_images_failed: [...]", lease_owner="wr2-image-generator:host:123",
    )
    sql, *args = conn.execute.call_args[0]
    assert "status" in sql and "'image_failed'" in sql
    assert "lease_owner" in sql and "NULL" in sql
    assert args[-1] == "wr2-image-generator:host:123"


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
