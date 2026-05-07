"""Unit tests for scripts/wr2_supervisor_watchdog.py (Sprint B B3).

Covers:
- Cooldown semantics (first stale fires, subsequent stale within 24h
  suppress, after 24h fires again).
- 7-day rolling success-rate computation from telemetry JSONL.
- Tiered alert evaluation (P0 supervisor-down / P0 pipeline-frozen /
  P1 success-rate-low) given DB + telemetry stubs.
- Degrade-open behavior when wr2_supervisor_heartbeat is missing.

DB calls are mocked. No network, no Telegram POST.
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg  # noqa: F401 — needed for monkeypatching attribute
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
WATCHDOG_PATH = SCRIPTS_DIR / "wr2_supervisor_watchdog.py"


@pytest.fixture
def wd(tmp_path, monkeypatch):
    """Fresh import of wr2_supervisor_watchdog with state/telemetry redirected to tmp."""
    sys.modules.pop("wr2_supervisor_watchdog", None)
    spec = importlib.util.spec_from_file_location("wr2_supervisor_watchdog", WATCHDOG_PATH)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["wr2_supervisor_watchdog"] = mod
    spec.loader.exec_module(mod)
    # Redirect persistent paths into the tmp sandbox.
    mod.STATE_PATH = tmp_path / "state.txt"
    mod.TELEMETRY_PATH = tmp_path / "telemetry.jsonl"
    return mod


# ─────────────────────────────────────────────────────────────────────────
# State + cooldown
# ─────────────────────────────────────────────────────────────────────────

def test_state_set_and_get_round_trip(wd):
    wd._state_set("last_alert_supervisor_down", 1234567890)
    assert wd._state_get("last_alert_supervisor_down") == 1234567890


def test_state_set_does_not_clobber_other_keys(wd):
    wd._state_set("a", 1)
    wd._state_set("b", 2)
    wd._state_set("a", 99)  # overwrite a
    assert wd._state_get("a") == 99
    assert wd._state_get("b") == 2


def test_alert_due_first_time(wd):
    """First alert (no prior state) is always due."""
    assert wd._alert_due("supervisor_down", now_epoch=1000) is True


def test_alert_due_within_cooldown(wd):
    wd._state_set("last_alert_supervisor_down", 1000)
    # 1h after last alert, cooldown is 24h → suppressed.
    assert wd._alert_due("supervisor_down", now_epoch=1000 + 3600) is False


def test_alert_due_after_cooldown(wd):
    wd._state_set("last_alert_supervisor_down", 1000)
    # 25h after last alert → fire again.
    assert wd._alert_due("supervisor_down", now_epoch=1000 + 25 * 3600) is True


# ─────────────────────────────────────────────────────────────────────────
# 7-day success rate from telemetry JSONL
# ─────────────────────────────────────────────────────────────────────────

def _write_telemetry(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


def test_success_rate_empty_file_returns_100pct(wd):
    """Empty/missing telemetry → degrade-open (no false alert)."""
    sr = wd._probe_success_rate_telemetry()
    assert sr["attempted"] == 0
    assert sr["rate_pct"] == 100.0


def test_success_rate_counts_only_window(wd):
    """Rows older than 7 days are excluded; only fresh rows count."""
    from datetime import datetime, timedelta, timezone
    now = datetime.now(timezone.utc)
    rows = [
        # 10 days ago — excluded
        {"ts": (now - timedelta(days=10)).isoformat(), "outcome": "success"},
        # Last week — included
        {"ts": (now - timedelta(days=2)).isoformat(), "outcome": "success"},
        {"ts": (now - timedelta(days=1)).isoformat(), "outcome": "other"},
    ]
    _write_telemetry(wd.TELEMETRY_PATH, rows)
    sr = wd._probe_success_rate_telemetry()
    assert sr["attempted"] == 2
    assert sr["succeeded"] == 1
    assert sr["rate_pct"] == 50.0


def test_success_rate_handles_malformed_lines(wd):
    """Garbage lines + missing ts/outcome are silently skipped."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    path = wd.TELEMETRY_PATH
    path.write_text(
        "not json at all\n"
        '{"no_ts": "skipped"}\n'
        f'{{"ts": "{now.isoformat()}", "outcome": "success"}}\n'
        f'{{"ts": "{now.isoformat()}", "outcome": "other"}}\n'
        "\n"  # blank line
    )
    sr = wd._probe_success_rate_telemetry()
    assert sr["attempted"] == 2
    assert sr["succeeded"] == 1
    assert sr["rate_pct"] == 50.0


# ─────────────────────────────────────────────────────────────────────────
# evaluate_once tiered alerts
# ─────────────────────────────────────────────────────────────────────────

def _make_conn(heartbeat_age, oldest_pending_hours, rendered_recent):
    """Build a mock asyncpg.Connection with the 3 fetchval responses."""
    conn = MagicMock()
    conn.fetchval = AsyncMock(side_effect=[
        heartbeat_age,
        oldest_pending_hours,
        rendered_recent,
    ])
    return conn


def test_evaluate_p0_supervisor_down_fires_when_heartbeat_stale(wd):
    """Heartbeat row > 5 min old → P0 SUPERVISOR_DOWN."""
    conn = _make_conn(heartbeat_age=400, oldest_pending_hours=0.1, rendered_recent=3)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert any("Supervisor DOWN" in m for m in sent)
    # Cooldown timestamp recorded.
    assert wd._state_get("last_alert_supervisor_down") is not None


def test_evaluate_p0_supervisor_down_silenced_within_cooldown(wd):
    """Second tick within 24h does not fire again."""
    # Pre-seed last alert 1h ago.
    import time as _time
    wd._state_set("last_alert_supervisor_down", int(_time.time()) - 3600)
    conn = _make_conn(heartbeat_age=400, oldest_pending_hours=0.1, rendered_recent=3)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert not any("Supervisor DOWN" in m for m in sent)


def test_evaluate_pipeline_frozen_requires_both_conditions(wd):
    """PIPELINE_FROZEN fires only when oldest_pending > 2h AND rendered=0
    in 24h — either condition alone is silent."""
    # Only oldest_pending high, but rendered_recent > 0 → no alert.
    conn1 = _make_conn(heartbeat_age=10, oldest_pending_hours=5.0, rendered_recent=2)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn1))
    assert not any("Pipeline FROZEN" in m for m in sent)

    # Both conditions met → alert.
    sent.clear()
    conn2 = _make_conn(heartbeat_age=10, oldest_pending_hours=5.0, rendered_recent=0)
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn2))
    assert any("Pipeline FROZEN" in m for m in sent)


def test_evaluate_p1_success_rate_below_threshold(wd):
    """Success rate < 80% over 7d (with ≥5 attempts) fires P1."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = (
        # 6 attempts, 4 success → 66.7% (< 80%)
        [{"ts": now.isoformat(), "outcome": "success"} for _ in range(4)]
        + [{"ts": now.isoformat(), "outcome": "other"} for _ in range(2)]
    )
    _write_telemetry(wd.TELEMETRY_PATH, rows)
    conn = _make_conn(heartbeat_age=10, oldest_pending_hours=0.1, rendered_recent=3)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert any("success rate LOW" in m for m in sent)


def test_evaluate_p1_silent_with_min_attempts_below_threshold(wd):
    """Below MIN_ATTEMPTS=5, the rate is too noisy — stay quiet even
    if rate looks bad (e.g. 0/1 = 0%)."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = [{"ts": now.isoformat(), "outcome": "other"}]
    _write_telemetry(wd.TELEMETRY_PATH, rows)
    conn = _make_conn(heartbeat_age=10, oldest_pending_hours=0.1, rendered_recent=3)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert not any("success rate LOW" in m for m in sent)


def test_evaluate_silent_when_all_healthy(wd):
    """Heartbeat fresh, pipeline ok, success rate above threshold → no
    Telegram POST and no state mutation."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    rows = [{"ts": now.isoformat(), "outcome": "success"} for _ in range(5)]
    _write_telemetry(wd.TELEMETRY_PATH, rows)
    conn = _make_conn(heartbeat_age=30, oldest_pending_hours=0.1, rendered_recent=3)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert sent == []
    assert wd._state_get("last_alert_supervisor_down") is None
    assert wd._state_get("last_alert_pipeline_frozen") is None
    assert wd._state_get("last_alert_success_rate_low") is None


def test_evaluate_degrades_open_on_missing_heartbeat_table(wd):
    """If wr2_supervisor_heartbeat does not exist (migration 161 not yet
    applied), _probe_heartbeat_age returns None → no false P0 alert."""
    conn = MagicMock()
    # First call (heartbeat probe) raises UndefinedTableError; subsequent
    # calls (pipeline) return safe values.
    conn.fetchval = AsyncMock(side_effect=[
        asyncpg.UndefinedTableError("relation does not exist"),
        0.1,  # oldest_pending_hours
        3,  # rendered_recent
    ])
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert not any("Supervisor DOWN" in m for m in sent)


def test_success_rate_window_uses_7_days_not_24h():
    """Source code regression-guard: the design review explicitly
    rejected 24h in favour of a 7-day rolling window. Future agents
    must not 'simplify' back to 24h.
    """
    src = WATCHDOG_PATH.read_text()
    # Default value embedded in the env-overridable constant.
    assert 'WR2_WATCHDOG_SUCCESS_WINDOW_DAYS", "7"' in src
    # And the 80% threshold confirmed by the review.
    assert 'WR2_WATCHDOG_SUCCESS_THRESHOLD_PCT", "80"' in src
