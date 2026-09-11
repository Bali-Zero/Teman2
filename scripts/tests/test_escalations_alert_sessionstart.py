"""Board-honesty cure (2026-07-16) — net-pending counting in the ESCALATIONS
BOARD SessionStart receptor (scripts/hooks/escalations_alert_sessionstart.sh).

sentinel_lib.escalations.mark_resolved() is append-only: a recovered job's
resolution is a NEW {"status": "resolved", ...} line, the original pending
line is never rewritten (immutable log, D2.3). The receptor's old per-line
status filter only skipped the resolution marker itself — the original
pending line still read status=="pending" forever, so a healed job kept
shouting on every SessionStart (alert-fatigue, scar-family #2 Esiste≠Armato).

These tests drive the real bash script via subprocess with
ESCALATIONS_FILE_OVERRIDE pointed at a throwaway JSONL (never the tracked
shared/escalations_pro.jsonl), verifying:
  - guilt: a pending entry with NO resolution still surfaces (board stays
    honest about real open items).
  - innocence: a pending entry with a LATER resolution for the same job
    vanishes (net-pending, not raw-pending).
  - recurring job: escalate -> resolve -> escalate again correctly reports
    exactly the newer, still-open pending entry.
  - a resolution marker is never itself listed as a board item.

Run:
    cd ~/nuzantara/.worktrees/ops-board-honesty
    bash -n scripts/hooks/escalations_alert_sessionstart.sh   # syntax check
    python -m pytest scripts/tests/test_escalations_alert_sessionstart.py -v
"""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "hooks" / "escalations_alert_sessionstart.sh"


def _write_jsonl(path: Path, records: list[dict]) -> None:
    with path.open("w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _run_hook(esc_file: Path, tasks_dir: Path, extra_env: dict | None = None) -> dict | None:
    env = dict(os.environ)
    env["ESCALATIONS_FILE_OVERRIDE"] = str(esc_file)
    env["CLAUDE_TASKS_DIR"] = str(tasks_dir)
    env["ESCALATIONS_RECEPTOR_ENABLED"] = "true"
    if extra_env:
        env.update(extra_env)
    result = subprocess.run(
        ["bash", str(_SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, f"hook must always exit 0 (fail-open); stderr={result.stderr}"
    out = result.stdout.strip()
    if not out:
        return None
    return json.loads(out)


@pytest.fixture()
def tasks_dir(tmp_path) -> Path:
    d = tmp_path / "claude_tasks"
    d.mkdir()
    return d


class TestNetPending:
    def test_guilt_unresolved_pending_still_surfaces(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "fly_backup", "status": "pending", "priority": "HIGH",
             "error_summary": "exit 1", "ts": 100},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is not None, "a genuinely-open HIGH item must not go silent"
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "1 HIGH-priority open" in ctx
        assert "fly_backup" in ctx

    def test_string_ts_line_neither_silences_the_board_nor_breaks_net_pending(self, tmp_path, tasks_dir):
        """One writer emitting a string ts (W54 ISO-8601, #6012 str(now)) must
        not TypeError the net-pending comparisons and silence the WHOLE board
        at SessionStart: the open HIGH item still surfaces, and an ISO-stamped
        resolution still nets out the float-stamped pending it follows."""
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "healed_job", "status": "pending", "priority": "HIGH",
             "error_summary": "exit 1", "ts": 100},
            {"job": "healed_job", "status": "resolved",
             "resolved_at": "1970-01-01T00:03:20Z", "ts": "1970-01-01T00:03:20Z"},
            {"job": "still_open", "status": "pending", "priority": "HIGH",
             "error_summary": "boom", "ts": "150.0"},
            {"job": "junk_ts", "status": "pending", "priority": "HIGH",
             "error_summary": "no clock", "ts": "yesterday"},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is not None, "a string ts must not silence the board"
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "2 HIGH-priority open" in ctx, ctx
        assert "still_open" in ctx and "junk_ts" in ctx
        assert "healed_job" not in ctx, "ISO-stamped resolution must still net out the pending"

    def test_innocence_resolved_pending_vanishes(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "run_gap_scanner_layer_a", "status": "pending", "priority": "HIGH",
             "error_summary": "boom", "ts": 100},
            {"job": "run_gap_scanner_layer_a", "status": "resolved",
             "resolved_at": 200, "ts": 200},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is None, "a net-resolved job must not re-alert every session"

    def test_recurring_job_reports_only_the_newer_open_pending(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "nightly_autofix_ci", "status": "pending", "priority": "HIGH",
             "error_summary": "first failure", "ts": 100},
            {"job": "nightly_autofix_ci", "status": "resolved",
             "resolved_at": 150, "ts": 150},
            {"job": "nightly_autofix_ci", "status": "pending", "priority": "HIGH",
             "error_summary": "second failure", "ts": 200},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "1 HIGH-priority open" in ctx
        assert "second failure" in ctx
        assert "first failure" not in ctx

    def test_resolution_marker_never_listed_as_board_item(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "smoketest", "status": "resolved", "resolved_at": 50, "ts": 50},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is None, "a lone resolution marker (no prior pending) must never alert"

    def test_normal_priority_net_resolved_not_counted(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "qdrant_snapshot", "status": "pending", "priority": "NORMAL",
             "error_summary": "", "ts": 100},
            {"job": "qdrant_snapshot", "status": "resolved", "resolved_at": 200, "ts": 200},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is None, "a resolved NORMAL entry must not inflate normal_pending"

    def test_normal_priority_still_pending_counted(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "qdrant_snapshot", "status": "pending", "priority": "NORMAL",
             "error_summary": "", "ts": 100},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "1 NORMAL pending" in ctx


class TestCauseGrouping:
    """Dedupe/grouping by (source, normalized cause) — 2026-09-09 session-start
    injection diet. Measured live: healer_pro_tick escalating the SAME "N dead
    organs ... none curable" condition once per tick produced 14 distinct HIGH
    items (exact-tuple dedupe never collapsed them, because the count/timestamp
    baked into error_summary differed on every tick). Normalization strips
    digits/ISO-timestamps/shas before grouping so the same underlying cause
    collapses into one line, "(×N, latest <date>)"."""

    def test_guilt_same_job_same_cause_different_count_and_ts_collapses(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "healer_pro_tick", "status": "pending", "priority": "HIGH",
             "error_summary": "3 dead organs none curable", "ts": 100},
            {"job": "healer_pro_tick", "status": "pending", "priority": "HIGH",
             "error_summary": "5 dead organs none curable", "ts": 400},
            {"job": "healer_pro_tick", "status": "pending", "priority": "HIGH",
             "error_summary": "7 dead organs none curable", "ts": 700},
        ])
        out = _run_hook(esc, tasks_dir)
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "3 HIGH-priority open across 1 group(s)" in ctx, ctx
        assert "×3" in ctx, "the repeat count must be visible"
        assert ctx.count("healer_pro_tick") == 1, (
            f"same cause repeated must render ONCE with a count, not N times:\n{ctx}"
        )

    def test_innocence_different_cause_same_job_stays_separate_groups(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "nightly_autofix_ci", "status": "pending", "priority": "HIGH",
             "error_summary": "pytest failure in test_a", "ts": 100},
            {"job": "nightly_autofix_ci", "status": "pending", "priority": "HIGH",
             "error_summary": "lint failure in module_b", "ts": 200},
        ])
        out = _run_hook(esc, tasks_dir)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "2 HIGH-priority open across 2 group(s)" in ctx, ctx
        assert "pytest failure in test_a" in ctx
        assert "lint failure in module_b" in ctx

    def test_innocence_different_job_same_cause_stays_separate_groups(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "job_a", "status": "pending", "priority": "HIGH",
             "error_summary": "connection refused", "ts": 100},
            {"job": "job_b", "status": "pending", "priority": "HIGH",
             "error_summary": "connection refused", "ts": 200},
        ])
        out = _run_hook(esc, tasks_dir)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "2 HIGH-priority open across 2 group(s)" in ctx, ctx

    def test_guilt_group_cap_at_six(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        records = [
            {"job": f"distinct_job_{i}", "status": "pending", "priority": "HIGH",
             "error_summary": f"unique cause {i}", "ts": 100 + i}
            for i in range(10)
        ]
        _write_jsonl(esc, records)
        out = _run_hook(esc, tasks_dir)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "across 10 group(s)" in ctx, ctx
        shown = sum(1 for i in range(10) if f"distinct_job_{i}" in ctx)
        assert shown <= 6, f"expected at most 6 groups rendered, got {shown}:\n{ctx}"
        assert "more HIGH group" in ctx

    def test_guilt_latest_date_reflects_most_recent_ts(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        recent_ts = 1_800_000_000  # 2027-01-15ish, far newer than the old one below
        old_ts = 100
        _write_jsonl(esc, [
            {"job": "flaky_job", "status": "pending", "priority": "HIGH",
             "error_summary": "same cause", "ts": old_ts},
            {"job": "flaky_job", "status": "pending", "priority": "HIGH",
             "error_summary": "same cause", "ts": recent_ts},
        ])
        out = _run_hook(esc, tasks_dir)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        expected_date = time.strftime("%Y-%m-%d", time.gmtime(recent_ts))
        assert expected_date in ctx, ctx
        old_date = time.strftime("%Y-%m-%d", time.gmtime(old_ts))
        assert old_date not in ctx, "only the LATEST date should be shown, not the oldest"


class TestOutputCap:
    """Output cap (2026-09-04): this receptor injects into EVERY session start
    on every machine, so a board carrying dozens of HIGH items must not itself
    become the noise CLAUDE.md §2/§14 asked it to cut through. The cap is on
    the WHOLE stdout (JSON envelope included, since that is what the harness
    actually injects), default 1500 bytes, overridable via
    SESSIONSTART_HOOK_MAX_BYTES. Priority: HIGH count + HIGH items survive
    first; the long explanatory paragraph is the first thing dropped; the
    /escalations pointer survives every stage."""

    def _raw_payload_bytes(self, esc_file: Path, tasks_dir: Path, extra_env=None) -> tuple[bytes, dict | None]:
        env = dict(os.environ)
        env["ESCALATIONS_FILE_OVERRIDE"] = str(esc_file)
        env["CLAUDE_TASKS_DIR"] = str(tasks_dir)
        env["ESCALATIONS_RECEPTOR_ENABLED"] = "true"
        if extra_env:
            env.update(extra_env)
        result = subprocess.run(
            ["bash", str(_SCRIPT)], env=env, capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0, f"hook must always exit 0; stderr={result.stderr}"
        raw = result.stdout.strip()
        parsed = json.loads(raw) if raw else None
        return raw.encode("utf-8"), parsed

    def test_guilt_oversized_board_stays_under_cap_and_keeps_high_and_pointer(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        records = [
            {"job": f"job_{i}", "status": "pending", "priority": "HIGH",
             "error_summary": "x" * 78, "ts": 100 + i}
            for i in range(60)
        ]
        _write_jsonl(esc, records)
        raw, out = self._raw_payload_bytes(esc, tasks_dir)
        assert len(raw) <= 1500, f"payload must fit the default cap, got {len(raw)} bytes"
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "HIGH-priority open" in ctx, "HIGH count line must survive the cap"
        assert "🔴" in ctx, "at least one HIGH item must survive the cap"
        assert "/escalations" in ctx, "the /escalations pointer must survive every cap stage"

    def test_innocence_small_board_is_not_over_trimmed(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        _write_jsonl(esc, [
            {"job": "fly_backup", "status": "pending", "priority": "HIGH",
             "error_summary": "exit 1", "ts": 100},
        ])
        raw, out = self._raw_payload_bytes(esc, tasks_dir)
        assert len(raw) <= 1500
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "the receptor is read-only" in ctx, (
            "a board well under budget must keep the full explanation — the "
            "cap must not trim content that already fits"
        )

    def test_env_override_shrinks_the_cap(self, tmp_path, tasks_dir):
        esc = tmp_path / "escalations_pro.jsonl"
        records = [
            {"job": f"job_{i}", "status": "pending", "priority": "HIGH",
             "error_summary": "y" * 78, "ts": 100 + i}
            for i in range(60)
        ]
        _write_jsonl(esc, records)
        raw, out = self._raw_payload_bytes(esc, tasks_dir, extra_env={"SESSIONSTART_HOOK_MAX_BYTES": "500"})
        assert len(raw) <= 500, f"SESSIONSTART_HOOK_MAX_BYTES=500 must be honored, got {len(raw)} bytes"
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "HIGH-priority open" in ctx
