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
