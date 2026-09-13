"""End-to-end tests for scripts/hooks/organism_alert_sessionstart.sh after the
2026-09-09 session-start injection diet.

Drives the REAL bash hook via subprocess against a throwaway sidecar dir
(ORGANISM_LAST_SEEN_DIR), a throwaway on-command allow-list
(ORGANISM_ON_COMMAND_FILE) and a throwaway delta state file
(ORGANISM_HEARTBEAT_STATE_FILE) — never the tracked ~/.organism/ state or the
repo's real infra/organism/on_command_organs.json.

Sibling of test_escalations_alert_sessionstart.py (same drive-the-real-script
style) and test_organism_heartbeat_brief.py (which covers the filtering unit
in isolation). This file proves the WIRING: the hook actually calls the
detector with --json, pipes it through the brief script, and emits (or stays
silent) exactly as designed.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK = _REPO_ROOT / "scripts" / "hooks" / "organism_alert_sessionstart.sh"


def _write_sidecar(d: Path, organ_id: str, ts_days_ago: float, status: str = "ok") -> None:
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{organ_id}.json"
    p.write_text(json.dumps({"ts": time.time() - ts_days_ago * 86400, "status": status}))


def _write_on_command(p: Path, patterns: list[str]) -> None:
    p.write_text(json.dumps({"patterns": patterns}))


def _run_hook(sidecar_dir: Path, on_command_file: Path, state_file: Path) -> dict | None:
    env = dict(os.environ)
    env["ORGANISM_LAST_SEEN_DIR"] = str(sidecar_dir)
    env["ORGANISM_ON_COMMAND_FILE"] = str(on_command_file)
    env["ORGANISM_HEARTBEAT_STATE_FILE"] = str(state_file)
    result = subprocess.run(
        ["bash", str(_HOOK)], env=env, capture_output=True, text=True, timeout=20,
    )
    assert result.returncode == 0, f"hook must always exit 0 (fail-open); stderr={result.stderr}"
    out = result.stdout.strip()
    return json.loads(out) if out else None


class TestWiring:
    def test_all_breathing_is_silent(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, [])
        sidecar.mkdir()
        _write_sidecar(sidecar, "custom.fresh", ts_days_ago=0.01)
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is None

    def test_guilt_wr2_organ_excluded_end_to_end(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, ["wr2.*"])
        _write_sidecar(sidecar, "wr2.supervisor", ts_days_ago=30)
        _write_sidecar(sidecar, "custom.real_issue", ts_days_ago=30)
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "wr2.supervisor" not in ctx
        assert "custom.real_issue" in ctx

    def test_missing_sidecar_dir_is_silent(self, tmp_path):
        sidecar = tmp_path / "does_not_exist"
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, [])
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is None

    def test_second_run_collapses_unchanged_end_to_end(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, [])
        state = tmp_path / "state.json"
        _write_sidecar(sidecar, "custom.stale_thing", ts_days_ago=30)

        out1 = _run_hook(sidecar, on_cmd, state)
        assert out1 is not None
        assert "custom.stale_thing" in out1["hookSpecificOutput"]["additionalContext"]

        out2 = _run_hook(sidecar, on_cmd, state)
        assert out2 is not None
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        assert "custom.stale_thing" not in ctx2
        assert "unchanged" in ctx2

    def test_output_stays_under_default_cap(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, [])
        for i in range(60):
            _write_sidecar(sidecar, f"custom.organ_{i}", ts_days_ago=30)
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is not None
        raw = json.dumps(out)
        assert len(raw.encode("utf-8")) <= 1500, f"got {len(raw.encode('utf-8'))} bytes"

    def test_malformed_sidecar_file_does_not_crash_the_hook(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        sidecar.mkdir()
        on_cmd = tmp_path / "on_command.json"
        _write_on_command(on_cmd, [])
        (sidecar / "custom.broken.json").write_text("{not valid json")
        # a corrupt sidecar is itself a legitimate finding (kind="corrupt"),
        # but the hook must still exit 0 and emit valid JSON, never crash.
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is not None
        assert "custom.broken" in out["hookSpecificOutput"]["additionalContext"]

    def test_missing_on_command_file_fails_open_shows_everything(self, tmp_path):
        sidecar = tmp_path / "last_seen"
        on_cmd = tmp_path / "does_not_exist.json"
        _write_sidecar(sidecar, "wr2.supervisor", ts_days_ago=30)
        out = _run_hook(sidecar, on_cmd, tmp_path / "state.json")
        assert out is not None
        assert "wr2.supervisor" in out["hookSpecificOutput"]["additionalContext"]
