"""Unit tests for scripts/wr2_supervisor.py.

Covers:
- Transition resolution (exact + wildcard + unknown)
- Per-draft serialisation lock
- Per-(draft, target) dedup
- Stale payload re-read fallback to current DB status
- DRY-RUN mode skips kickstart
- launchctl rc=113 treated as benign no-op
- Reconciliation kicks stalled drafts and respects dedup
- Telegram alert on rendered / fact_check_failed
- UnboundLocalError protection (conn=None init)

All DB calls are mocked. No network, no subprocess actually runs.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Load the supervisor module from scripts/ (it's not on PYTHONPATH).
SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SUPERVISOR_PATH = SCRIPTS_DIR / "wr2_supervisor.py"


@pytest.fixture
def sup(monkeypatch):
    """Fresh import of wr2_supervisor with clean module-level state."""
    # Remove cached version if present so dedup set / locks reset between tests.
    sys.modules.pop("wr2_supervisor", None)
    spec = importlib.util.spec_from_file_location("wr2_supervisor", SUPERVISOR_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_supervisor"] = mod
    # Stub asyncpg so the import doesn't hit a real DB.
    monkeypatch.setattr(os, "getuid", lambda: 501)
    spec.loader.exec_module(mod)
    # Reset module-level state to avoid cross-test pollution.
    mod._recently_dispatched.clear()
    mod._draft_locks.clear()
    mod._handler_tasks.clear()
    mod._shutdown_event = asyncio.Event()
    return mod


# ─────────────────────────────────────────────────────────────────────────
# _resolve_transition
# ─────────────────────────────────────────────────────────────────────────

def test_resolve_exact_match(sup):
    target = sup._resolve_transition("briefed", "drafts")
    assert target == "com.balizero.wr2.image-generator"


def test_resolve_wildcard_old_status(sup):
    """('*', 'briefed') matches any prior status, including None (INSERT)."""
    assert sup._resolve_transition(None, "briefed") == "com.balizero.wr2.draft-generator"
    assert sup._resolve_transition("rejected", "briefed") == "com.balizero.wr2.draft-generator"


def test_resolve_alert_only(sup):
    """rendered / fact_check_failed map to None (alert only, no kickstart)."""
    assert sup._resolve_transition("drafts_imaged_checked", "rendered") is None
    assert sup._resolve_transition(None, "fact_check_failed") is None
    assert sup._resolve_transition("anything", "rejected") is None


def test_resolve_unknown_returns_sentinel(sup):
    target = sup._resolve_transition("weird_status", "weirder_status")
    assert target is sup._SENTINEL_UNKNOWN


# ─────────────────────────────────────────────────────────────────────────
# _kickstart
# ─────────────────────────────────────────────────────────────────────────

def test_kickstart_no_dash_k_flag(sup):
    """The supervisor must NEVER pass -k (would kill running stages)."""
    with patch.object(subprocess, "run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        sup._kickstart("com.balizero.wr2.fact-extractor")
        args = mock_run.call_args[0][0]
        assert "kickstart" in args
        assert "-k" not in args, "kickstart must not use -k"


def test_kickstart_rc_113_treated_as_noop(sup, caplog):
    """rc 113 (service busy) is benign — log DEBUG, don't alert."""
    err = subprocess.CalledProcessError(returncode=113, cmd=["launchctl"], stderr="busy")
    with patch.object(subprocess, "run", side_effect=err):
        with caplog.at_level("DEBUG"):
            sup._kickstart("com.balizero.wr2.fact-checker")
    assert any("no-op" in r.message and "113" in r.message for r in caplog.records)


def test_kickstart_dry_run_skips_subprocess(sup, monkeypatch):
    monkeypatch.setenv("WR2_SUPERVISOR_DRY_RUN", "true")
    with patch.object(subprocess, "run") as mock_run:
        sup._kickstart("com.balizero.wr2.fact-extractor")
    assert mock_run.call_count == 0


def test_kickstart_real_failure_alerts(sup):
    """Non-113 failures trigger Telegram (synchronously via _telegram_sync)."""
    err = subprocess.CalledProcessError(returncode=1, cmd=["launchctl"], stderr="boom")
    with patch.object(subprocess, "run", side_effect=err):
        with patch.object(sup, "_telegram_sync") as mock_tg:
            sup._kickstart("com.balizero.wr2.fact-extractor")
    assert mock_tg.call_count == 1
    assert "rc=1" in mock_tg.call_args[0][0]


# ─────────────────────────────────────────────────────────────────────────
# _handle_payload — per-draft lock + re-read + dedup
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handle_payload_kickstarts_next_stage(sup):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="drafts")  # current status matches payload

    with patch.object(sup, "_kickstart") as mock_ks:
        # _kickstart runs in executor — patch it so we can assert sync.
        await sup._handle_payload(
            {"draft_id": "11111111-1111-1111-1111-111111111111",
             "old_status": "briefed", "new_status": "drafts"},
            conn,
        )
    # Wait for the executor task to settle.
    for _ in range(10):
        if mock_ks.call_count > 0:
            break
        await asyncio.sleep(0.05)
    mock_ks.assert_called_once_with("com.balizero.wr2.image-generator")


@pytest.mark.asyncio
async def test_handle_payload_uses_current_status_when_payload_stale(sup):
    """Payload says new=briefed, DB says current=drafts → use current.

    The supervisor must consult the DB before kickstarting because the
    payload may be stale (multiple updates landed between LISTEN and
    handler dispatch). Here, payload (None → briefed) maps to draft-
    generator, but the row is already at 'drafts' — we must kick
    image-generator instead.
    """
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="drafts")

    with patch.object(sup, "_kickstart") as mock_ks:
        await sup._handle_payload(
            {"draft_id": "22222222-2222-2222-2222-222222222222",
             "old_status": "briefed", "new_status": "briefed"},
            conn,
        )
    for _ in range(10):
        if mock_ks.call_count > 0:
            break
        await asyncio.sleep(0.05)
    # Should have kicked image-generator (briefed→drafts), NOT draft-generator
    mock_ks.assert_called_once_with("com.balizero.wr2.image-generator")


@pytest.mark.asyncio
async def test_handle_payload_skips_deleted_draft(sup, caplog):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value=None)  # draft deleted

    with patch.object(sup, "_kickstart") as mock_ks:
        with caplog.at_level("WARNING"):
            await sup._handle_payload(
                {"draft_id": "33333333-3333-3333-3333-333333333333",
                 "old_status": "drafts", "new_status": "drafts_imaged"},
                conn,
            )
    assert mock_ks.call_count == 0
    assert any("no longer exists" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_per_draft_dedup_blocks_second_call(sup):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="drafts")
    payload = {
        "draft_id": "44444444-4444-4444-4444-444444444444",
        "old_status": "briefed", "new_status": "drafts",
    }

    with patch.object(sup, "_kickstart") as mock_ks:
        await sup._handle_payload(payload, conn)
        await sup._handle_payload(payload, conn)  # exact duplicate
    for _ in range(10):
        await asyncio.sleep(0.05)
    assert mock_ks.call_count == 1, "second exact-duplicate call must be deduped"


@pytest.mark.asyncio
async def test_dedup_does_not_block_different_draft(sup):
    """The killer fix: per-(draft, target) dedup, NOT per-target.

    Two DIFFERENT drafts both transition to status=drafts → both must be
    kicked (the v1 cooldown bug skipped the second one).
    """
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="drafts")

    with patch.object(sup, "_kickstart") as mock_ks:
        await sup._handle_payload(
            {"draft_id": "55555555-5555-5555-5555-555555555555",
             "old_status": "briefed", "new_status": "drafts"},
            conn,
        )
        await sup._handle_payload(
            {"draft_id": "66666666-6666-6666-6666-666666666666",
             "old_status": "briefed", "new_status": "drafts"},
            conn,
        )
    for _ in range(20):
        if mock_ks.call_count >= 2:
            break
        await asyncio.sleep(0.05)
    assert mock_ks.call_count == 2, "different drafts must NOT share a dedup slot"


@pytest.mark.asyncio
async def test_unknown_transition_skipped_silently(sup, caplog):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="weird")

    with patch.object(sup, "_kickstart") as mock_ks:
        with caplog.at_level("DEBUG"):
            await sup._handle_payload(
                {"draft_id": "77777777-7777-7777-7777-777777777777",
                 "old_status": "alien", "new_status": "weird"},
                conn,
            )
    assert mock_ks.call_count == 0
    assert any("no transition mapped" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_telegram_alert_on_rendered(sup):
    conn = MagicMock()
    conn.fetchval = AsyncMock(return_value="rendered")

    with patch.object(sup, "_telegram", new=AsyncMock()) as mock_tg:
        with patch.object(sup, "_kickstart"):
            await sup._handle_payload(
                {"draft_id": "88888888-8888-8888-8888-888888888888",
                 "old_status": "drafts_imaged_checked", "new_status": "rendered"},
                conn,
            )
    assert mock_tg.call_count >= 1
    assert "rendered" in mock_tg.call_args[0][0].lower()


@pytest.mark.asyncio
async def test_malformed_payload_skipped(sup):
    conn = MagicMock()
    with patch.object(sup, "_kickstart") as mock_ks:
        await sup._handle_payload({}, conn)
        await sup._handle_payload({"draft_id": "x"}, conn)
        await sup._handle_payload({"new_status": "drafts"}, conn)
    assert mock_ks.call_count == 0


# ─────────────────────────────────────────────────────────────────────────
# Reconciliation
# ─────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reconcile_kicks_stalled(sup):
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[
        {"draft_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
         "status": "drafts_imaged", "updated_at": "2026-04-25 00:00:00"},
        {"draft_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
         "status": "briefed", "updated_at": "2026-04-25 00:00:00"},
    ])
    with patch.object(sup, "_kickstart") as mock_ks:
        n = await sup._reconcile_once(conn)
    for _ in range(20):
        if mock_ks.call_count >= 2:
            break
        await asyncio.sleep(0.05)
    assert n == 2
    targets = {c[0][0] for c in mock_ks.call_args_list}
    assert "com.balizero.wr2.fact-extractor" in targets   # drafts_imaged → fact-extractor
    assert "com.balizero.wr2.draft-generator" in targets  # briefed → draft-generator


@pytest.mark.asyncio
async def test_reconcile_respects_dedup(sup):
    """Reconcile must not re-kick a draft that was already dispatched recently."""
    conn = MagicMock()
    conn.fetch = AsyncMock(return_value=[
        {"draft_id": "cccccccc-cccc-cccc-cccc-cccccccccccc",
         "status": "drafts", "updated_at": "2026-04-25 00:00:00"},
    ])
    # Pre-populate dedup as if this draft was already kicked
    sup._recently_dispatched.add(("cccccccc-cccc-cccc-cccc-cccccccccccc",
                                  "com.balizero.wr2.image-generator"))
    with patch.object(sup, "_kickstart") as mock_ks:
        n = await sup._reconcile_once(conn)
    assert n == 0
    assert mock_ks.call_count == 0


# ─────────────────────────────────────────────────────────────────────────
# Resilience / setup
# ─────────────────────────────────────────────────────────────────────────

def test_dedup_set_size_is_bounded(sup):
    """Trim runs when set exceeds max — no unbounded memory growth."""
    sup._RECENTLY_DISPATCHED_MAX = 100  # smaller cap for the test
    for i in range(150):
        sup._recently_dispatched.add((f"draft-{i}", "target"))
        sup._trim_dedup()
    # After trimming, size should never exceed cap by much.
    assert len(sup._recently_dispatched) <= 110


def test_run_loop_no_unbound_local_on_early_connect_failure(sup, monkeypatch):
    """Before fix, asyncpg.connect raising on the first try would trigger
    UnboundLocalError on `conn.close()` in the finally block. After fix,
    `conn = None` is the initial value, so finally is a no-op.
    """
    monkeypatch.setenv("DATABASE_URL", "postgresql://invalid:invalid@nowhere/db")
    # We don't actually run the loop — just assert that the source code
    # initialises `conn = None` before the try.
    src = SUPERVISOR_PATH.read_text()
    assert "conn: asyncpg.Connection | None = None" in src
