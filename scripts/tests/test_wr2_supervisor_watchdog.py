"""Unit tests for scripts/wr2_supervisor_watchdog.py (Sprint B B3 + C1 outcome probes).

Covers:
- Cooldown semantics (first stale fires, subsequent stale within 24h
  suppress, after 24h fires again).
- 7-day rolling success-rate computation, DB-derived (P-1 S10b re-key —
  the old telemetry-JSONL tests rotted silently when the module moved to
  _probe_success_rate_db; rewritten 2026-07-02 with the C1 PR).
- Tiered alert evaluation (P0 supervisor-down / P0 pipeline-frozen /
  P1 success-rate-low) given DB stubs that dispatch BY QUERY CONTENT,
  not by call order (order-pinned mocks broke on every new probe).
- Degrade-open behavior when wr2_supervisor_heartbeat is missing.
- C1 outcome probes (stale lease / state age / manifest gap / weekly
  silent): innocence AND guilt per probe (cicatrix #3).

DB calls are mocked. No network, no Telegram POST, no Drive.
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
# 7-day success rate, DB-derived (P-1 S10b)
# ─────────────────────────────────────────────────────────────────────────

def test_success_rate_db_no_data_never_reads_healthy(wd):
    """0 attempts in the window → no_data=True, rate None — NEVER a 100%
    (the old telemetry probe's degrade-open 100% went permanently blind)."""
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={"attempted": 0, "succeeded": 0})
    sr = asyncio.run(wd._probe_success_rate_db(conn))
    assert sr["no_data"] is True
    assert sr["rate_pct"] is None


def test_success_rate_db_computes_rate(wd):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value={"attempted": 4, "succeeded": 2})
    sr = asyncio.run(wd._probe_success_rate_db(conn))
    assert sr["no_data"] is False
    assert sr["rate_pct"] == 50.0
    assert sr["attempted"] == 4


def test_success_rate_db_null_row_is_no_data(wd):
    conn = MagicMock()
    conn.fetchrow = AsyncMock(return_value=None)
    sr = asyncio.run(wd._probe_success_rate_db(conn))
    assert sr["no_data"] is True


# ─────────────────────────────────────────────────────────────────────────
# evaluate_once tiered alerts — DB stub dispatches by QUERY CONTENT
# ─────────────────────────────────────────────────────────────────────────

def _make_conn(
    heartbeat_age=10.0,
    renderer_enabled=True,
    oldest_pending_hours=0.1,
    rendered_recent=3,
    attempted=5,
    succeeded=5,
    ledger_gap=0,
):
    """Mock asyncpg.Connection whose fetchval/fetchrow answer by matching the
    query text — immune to probe-order changes (the old order-pinned
    side_effect list silently fed the renderer-flag probe a float and
    disabled half the checks; 2026-07-02)."""
    conn = MagicMock()

    async def fetchval(query, *args):
        q = " ".join(query.split())
        if "wr2_supervisor_heartbeat" in q:
            return heartbeat_age
        if "system_settings" in q:
            return "true" if renderer_enabled else "false"
        if "MIN(updated_at)" in q:
            return oldest_pending_hours
        if "topic_type_log" in q:
            return ledger_gap
        if "status = 'rendered'" in q and "COUNT(*)" in q:
            return rendered_recent
        raise AssertionError(f"unmocked fetchval: {q[:120]}")

    async def fetchrow(query, *args):
        return {"attempted": attempted, "succeeded": succeeded}

    conn.fetchval = MagicMock(side_effect=fetchval)
    conn.fetchrow = MagicMock(side_effect=fetchrow)
    conn.fetch = AsyncMock(return_value=[])
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
    conn = _make_conn(attempted=6, succeeded=4)  # 66.7% < 80%
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert any("success rate LOW" in m for m in sent)


def test_evaluate_p1_silent_with_min_attempts_below_threshold(wd):
    """Below MIN_ATTEMPTS=5, the rate is too noisy — stay quiet even
    if rate looks bad (e.g. 0/1 = 0%)."""
    conn = _make_conn(attempted=1, succeeded=0)
    sent: list[str] = []
    with patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_once(conn))
    assert not any("success rate LOW" in m for m in sent)


def test_evaluate_silent_when_all_healthy(wd):
    """Heartbeat fresh, pipeline ok, success rate above threshold → no
    Telegram POST and no state mutation."""
    conn = _make_conn()
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
    conn = _make_conn()
    inner = conn.fetchval.side_effect

    async def fetchval(query, *args):
        if "wr2_supervisor_heartbeat" in query:
            raise asyncpg.UndefinedTableError("relation does not exist")
        return await inner(query, *args)

    conn.fetchval = MagicMock(side_effect=fetchval)
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


def test_send_telegram_falls_back_to_plain_on_markdown_400(wd, monkeypatch):
    """W-cicatrix 2026-06-13: parse_mode=Markdown made Telegram reject the
    alert with HTTP 400 (unbalanced * / _ entities in job names) and the
    watchdog DROPPED it — the WR2 alert channel was mute for 3 days. The
    fix must resend as plain text: delivery beats formatting."""
    import urllib.error

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    calls: list[dict] = []

    def fake_post(token, payload):
        calls.append(dict(payload))
        if "parse_mode" in payload:
            raise urllib.error.HTTPError("u", 400, "Bad Request", None, None)

    with patch.object(wd, "_post_telegram", fake_post):
        wd._send_telegram("🚨 *WR2* unbalanced_entity_name")

    assert len(calls) == 2, "must retry exactly once after Markdown 400"
    assert "parse_mode" in calls[0]
    assert "parse_mode" not in calls[1], "retry must be plain text"
    assert calls[1]["text"] == "🚨 *WR2* unbalanced_entity_name"


def test_send_telegram_no_plain_retry_on_non_400(wd, monkeypatch):
    """A 500/502 from Telegram is transient infra, not a formatting issue —
    no plain-text resend, just the best-effort warning."""
    import urllib.error

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    calls: list[dict] = []

    def fake_post(token, payload):
        calls.append(dict(payload))
        raise urllib.error.HTTPError("u", 502, "Bad Gateway", None, None)

    with patch.object(wd, "_post_telegram", fake_post):
        wd._send_telegram("hello")  # must not raise

    assert len(calls) == 1


# ─────────────────────────────────────────────────────────────────────────
# C1 outcome probes — innocence AND guilt per probe (cicatrix #3)
# ─────────────────────────────────────────────────────────────────────────

def _make_outcome_conn(stale_rows=(), age_rows=(), rendered_rows=(), renderer_enabled=True):
    """Mock conn for _evaluate_outcome_probes — dispatches by query text."""
    conn = MagicMock()

    async def fetch(query, *args):
        q = " ".join(query.split())
        if "lease_heartbeat_at" in q and "'rendering'" in q:
            return list(stale_rows)
        if "GROUP BY status" in q:
            return list(age_rows)
        if "drive_url IS NOT NULL" in q:
            return list(rendered_rows)
        raise AssertionError(f"unmocked fetch: {q[:120]}")

    async def fetchval(query, *args):
        if "system_settings" in query:
            return "true" if renderer_enabled else "false"
        raise AssertionError(f"unmocked fetchval: {query[:120]}")

    conn.fetch = MagicMock(side_effect=fetch)
    conn.fetchval = MagicMock(side_effect=fetchval)
    return conn


def _run_outcome(wd, conn):
    """Run _evaluate_outcome_probes with reflexion pinned healthy and the
    runtime-stale probe pinned empty (both have dedicated tests that exercise
    the real files) and Telegram captured."""
    sent: list[str] = []
    with patch.object(wd, "_probe_reflexion_age", lambda: ("ok", 1.0)), \
         patch.object(wd, "_probe_runtime_stale", lambda: []), \
         patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_outcome_probes(conn))
    return sent


def test_stale_lease_fires_on_dead_heartbeat(wd):
    conn = _make_outcome_conn(stale_rows=[
        {"draft_id": "d1", "lease_owner": "html-apply-1-ab", "hb_age_sec": 1200.0, "held_sec": 1300.0},
    ])
    sent = _run_outcome(wd, conn)
    assert any("stale render lease" in m for m in sent)
    assert wd._state_get("last_alert_stale_lease") is not None


def test_stale_lease_innocent_when_no_rows(wd):
    sent = _run_outcome(wd, _make_outcome_conn())
    assert sent == []


def test_state_age_fires_over_threshold(wd):
    conn = _make_outcome_conn(age_rows=[
        {"status": "drafts", "n": 2, "oldest_hours": 7.5},
    ])
    sent = _run_outcome(wd, conn)
    assert any("state-age" in m and "`drafts`" in m for m in sent)


def test_state_age_innocent_under_threshold(wd):
    conn = _make_outcome_conn(age_rows=[
        {"status": "drafts", "n": 2, "oldest_hours": 1.0},
    ])
    assert _run_outcome(wd, conn) == []


def test_state_age_unknown_state_always_flagged(wd):
    """A status outside the known machine is drift (cicatrix #9) — flagged
    even when young."""
    conn = _make_outcome_conn(age_rows=[
        {"status": "briefed_facted", "n": 1, "oldest_hours": 0.1},
    ])
    sent = _run_outcome(wd, conn)
    assert any("UNKNOWN states" in m for m in sent)


def test_state_age_checked_backlog_expected_when_renderer_off(wd):
    """Kill-switched renderer (W46): drafts_imaged_checked backlog is by
    design — no alert."""
    conn = _make_outcome_conn(
        age_rows=[{"status": "drafts_imaged_checked", "n": 5, "oldest_hours": 48.0}],
        renderer_enabled=False,
    )
    assert _run_outcome(wd, conn) == []


def test_extract_folder_id():
    sys.modules.pop("wr2_supervisor_watchdog", None)
    spec = importlib.util.spec_from_file_location("wr2_supervisor_watchdog", WATCHDOG_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    ok = mod._extract_folder_id("https://drive.google.com/drive/folders/1aB_c-9?usp=drive_link")
    assert ok == "1aB_c-9"
    assert mod._extract_folder_id("https://drive.google.com/file/d/xyz/view") is None
    assert mod._extract_folder_id("") is None


def test_manifest_probe_kill_switch_skips(wd):
    wd.MANIFEST_PROBE_ENABLED = False
    conn = _make_outcome_conn(rendered_rows=[{"draft_id": "dX", "drive_url": "u"}])
    result = asyncio.run(wd._probe_manifest_gaps(conn))
    assert result is None


def test_manifest_probe_throttles_within_interval(wd):
    conn = _make_outcome_conn()
    first = asyncio.run(wd._probe_manifest_gaps(conn))
    second = asyncio.run(wd._probe_manifest_gaps(conn))
    assert first is not None
    assert second is None  # hourly throttle


def test_manifest_gap_fires_when_manifest_missing(wd):
    conn = _make_outcome_conn(rendered_rows=[
        {"draft_id": "d7", "drive_url": "https://drive.google.com/drive/folders/FOLD7"},
    ])
    with patch.object(wd, "_drive_list_names_sync", lambda fid: {"01.png", "02.png"}):
        sent = _run_outcome(wd, conn)
    assert any("rendered-without-manifest" in m and "d7" in m for m in sent)


def test_manifest_innocent_when_manifest_present(wd):
    conn = _make_outcome_conn(rendered_rows=[
        {"draft_id": "d8", "drive_url": "https://drive.google.com/drive/folders/FOLD8"},
    ])
    with patch.object(wd, "_drive_list_names_sync", lambda fid: {"01.png", "manifest.json"}):
        sent = _run_outcome(wd, conn)
    assert sent == []
    assert (wd._state_get("manifest_probe_fail_streak") or 0) == 0


def test_manifest_unparseable_url_reported_not_skipped(wd):
    conn = _make_outcome_conn(rendered_rows=[
        {"draft_id": "d9", "drive_url": "https://example.com/not-a-folder"},
    ])
    sent = _run_outcome(wd, conn)
    assert any("unparseable" in m and "d9" in m for m in sent)


def test_manifest_drive_failure_degrades_open_but_counts_streak(wd):
    conn = _make_outcome_conn(rendered_rows=[
        {"draft_id": "dA", "drive_url": "https://drive.google.com/drive/folders/FOLDA"},
    ])

    def boom(fid):
        raise RuntimeError("Drive down")

    with patch.object(wd, "_drive_list_names_sync", boom):
        sent = _run_outcome(wd, conn)
    assert sent == []  # degrade-open: no false gap alert
    assert wd._state_get("manifest_probe_fail_streak") == 1


def test_manifest_probe_broken_fires_at_streak_threshold(wd):
    wd._state_set("manifest_probe_fail_streak", wd.MANIFEST_FAIL_STREAK - 1)
    conn = _make_outcome_conn(rendered_rows=[
        {"draft_id": "dB", "drive_url": "https://drive.google.com/drive/folders/FOLDB"},
    ])

    def boom(fid):
        raise RuntimeError("Drive down")

    with patch.object(wd, "_drive_list_names_sync", boom):
        sent = _run_outcome(wd, conn)
    assert any("manifest probe BROKEN" in m for m in sent)


def test_reflexion_missing_file_is_alert_state(wd, tmp_path, monkeypatch):
    """Missing ledger = the never-armed weekly cron (W81) — alert, not skip."""
    monkeypatch.setenv("WR2_SKILL_DIR", str(tmp_path / "nowhere"))
    state, age = wd._probe_reflexion_age()
    assert state == "missing"
    assert age is None


def test_reflexion_fresh_run_ok(wd, tmp_path, monkeypatch):
    from datetime import datetime, timezone
    monkeypatch.setenv("WR2_SKILL_DIR", str(tmp_path))
    (tmp_path / "_reflexion-state.json").write_text(json.dumps([
        {"run_at": datetime.now(timezone.utc).isoformat(), "loop": "wr2", "status": "NO_INPUT"},
    ]))
    state, age = wd._probe_reflexion_age()
    assert state == "ok"
    assert age is not None and age < 1


def test_reflexion_stale_run_flagged(wd, tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    monkeypatch.setenv("WR2_SKILL_DIR", str(tmp_path))
    (tmp_path / "_reflexion-state.json").write_text(json.dumps([
        {"run_at": (datetime.now(timezone.utc) - timedelta(days=12)).isoformat(), "loop": "wr2"},
    ]))
    state, age = wd._probe_reflexion_age()
    assert state == "stale"
    assert age > 8


def test_reflexion_malformed_ledger_flagged(wd, tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_SKILL_DIR", str(tmp_path))
    (tmp_path / "_reflexion-state.json").write_text("{not json")
    state, _age = wd._probe_reflexion_age()
    assert state == "malformed"


def test_weekly_silent_alert_via_evaluate(wd, tmp_path, monkeypatch):
    monkeypatch.setenv("WR2_SKILL_DIR", str(tmp_path / "nowhere"))
    conn = _make_outcome_conn()
    sent: list[str] = []
    with patch.object(wd, "_probe_runtime_stale", lambda: []), \
         patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_outcome_probes(conn))
    assert any("weekly reflexion SILENT" in m and "MISSING" in m for m in sent)


# ─────────────────────────────────────────────────────────────────────────
# C2 RUNTIME_STALE probe — provenance stamps vs checkout on disk
# ─────────────────────────────────────────────────────────────────────────

def _write_stamp(home: Path, organ: str, **fields):
    d = home / ".organism" / "last_seen"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{organ}.runtime.json").write_text(json.dumps(fields))


def test_runtime_stale_missing_stamps_degrade_open(wd, tmp_path, monkeypatch):
    monkeypatch.setattr(wd.Path, "home", classmethod(lambda cls: tmp_path))
    assert wd._probe_runtime_stale() == []


def test_runtime_stale_dirty_checkout_flags_even_with_dead_pid(wd, tmp_path, monkeypatch):
    """dirty/stale-modules are CHECKOUT diseases — the process being gone
    does not cure the mutated code on disk."""
    monkeypatch.setattr(wd.Path, "home", classmethod(lambda cls: tmp_path))
    _write_stamp(tmp_path, "wr2.html_apply",
                 head_sha="a" * 40, dirty=True, stale_modules=[],
                 checkout=str(tmp_path), pid=99999999, ts="t")
    findings = wd._probe_runtime_stale()
    assert len(findings) == 1
    assert "dirty-checkout" in findings[0]["problems"][0]


def test_runtime_stale_head_moved_with_live_pid_flags(wd, tmp_path, monkeypatch):
    monkeypatch.setattr(wd.Path, "home", classmethod(lambda cls: tmp_path))
    _write_stamp(tmp_path, "wr2.supervisor",
                 head_sha="a" * 40, dirty=False, stale_modules=[],
                 checkout="/fake/checkout", pid=os.getpid(), ts="t")
    with patch.object(wd, "_git_head", lambda c: "b" * 40):
        findings = wd._probe_runtime_stale()
    assert len(findings) == 1
    assert any(p.startswith("head-moved:") for p in findings[0]["problems"])


def test_runtime_stale_head_moved_dead_pid_is_normal(wd, tmp_path, monkeypatch):
    """A one-shot worker's stamp outliving its process while the checkout
    advances is the NORMAL case — no alert (innocence, cicatrix #3)."""
    monkeypatch.setattr(wd.Path, "home", classmethod(lambda cls: tmp_path))
    _write_stamp(tmp_path, "wr2.html_apply",
                 head_sha="a" * 40, dirty=False, stale_modules=[],
                 checkout="/fake/checkout", pid=99999999, ts="t")
    with patch.object(wd, "_git_head", lambda c: "b" * 40):
        assert wd._probe_runtime_stale() == []


def test_runtime_stale_clean_stamp_innocent(wd, tmp_path, monkeypatch):
    monkeypatch.setattr(wd.Path, "home", classmethod(lambda cls: tmp_path))
    _write_stamp(tmp_path, "wr2.supervisor",
                 head_sha="a" * 40, dirty=False, stale_modules=[],
                 checkout="/fake/checkout", pid=os.getpid(), ts="t")
    with patch.object(wd, "_git_head", lambda c: "a" * 40):
        assert wd._probe_runtime_stale() == []


def test_runtime_stale_alert_via_evaluate(wd):
    conn = _make_outcome_conn()
    sent: list[str] = []
    finding = [{"organ": "wr2.supervisor", "problems": ["head-moved:a->b (live pid 1 on old code)"], "ts": "t"}]
    with patch.object(wd, "_probe_reflexion_age", lambda: ("ok", 1.0)), \
         patch.object(wd, "_probe_runtime_stale", lambda: finding), \
         patch.object(wd, "_send_telegram", lambda text: sent.append(text)):
        asyncio.run(wd._evaluate_outcome_probes(conn))
    assert any("runtime provenance" in m and "wr2.supervisor" in m for m in sent)
    assert wd._state_get("last_alert_runtime_stale") is not None
