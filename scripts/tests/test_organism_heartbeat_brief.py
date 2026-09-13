"""Tests for organism_heartbeat_brief.py — the DIET layer over the heartbeat
receptor (2026-09-09, session-start injection diet).

Born from a measured Fable session where SessionStart injected ~49K tokens
before the first action; organism_alert_sessionstart.sh was the single
biggest offender because it printed EVERY open finding, unbounded, including
27 WR2 organs stale BY DECISION (Zero ruled 2026-09-01: "WR2 runs only on
command", memory decision_wr2_runs_only_on_command_2026_09_01).

Contract under test (guilt + innocence):
  - GUILT: an on-command organ (matches infra/organism/on_command_organs.json's
    patterns) is excluded from the emitted brief.
  - INNOCENCE: a real, non-on-command finding is never excluded.
  - GUILT: a finding identical (same kind+status) to the previous session's
    state collapses into the "unchanged" count, not a repeated line.
  - INNOCENCE: a finding that is NEW or whose (kind, status) CHANGED since
    the last session is always shown.
  - GUILT: empty or malformed findings JSON on stdin exits 0 with no output
    (fail-open — never crash, never block a session start).
  - the emitted payload never exceeds --max-bytes.
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from organism_heartbeat_brief import (  # noqa: E402
    is_on_command,
    load_on_command_patterns,
    partition_and_diff,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPT = _REPO_ROOT / "scripts" / "organism_heartbeat_brief.py"


def _finding(organ_id, kind="stale", status="ok", detail="stale 9.0d"):
    return {"organ_id": organ_id, "kind": kind, "age_days": 9.0, "status": status, "detail": detail}


def _write_on_command_file(path: Path, patterns: list[str]) -> None:
    path.write_text(json.dumps({"patterns": patterns}))


def _write_state(path: Path, organs: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"organs": organs}))


def _run_cli(findings, on_command_file: Path, state_file: Path, max_bytes: int = 1500):
    result = subprocess.run(
        [sys.executable, str(_SCRIPT),
         "--on-command-file", str(on_command_file),
         "--state-file", str(state_file),
         "--max-bytes", str(max_bytes)],
        input=json.dumps(findings),
        capture_output=True, text=True, timeout=15,
    )
    assert result.returncode == 0, f"must always exit 0 (fail-open); stderr={result.stderr}"
    out = result.stdout.strip()
    return json.loads(out) if out else None


class TestOnCommandExclusion:
    def test_guilt_pattern_match_excludes(self):
        patterns = ["wr2.*", "pro.wr2_*", "mata_garuda.wr2_bridge*"]
        assert is_on_command("wr2.supervisor", patterns) is True
        assert is_on_command("pro.wr2_worktree_gc", patterns) is True
        assert is_on_command("mata_garuda.wr2_bridge_hourly.pro", patterns) is True

    def test_innocence_non_matching_organ_not_excluded(self):
        patterns = ["wr2.*", "pro.wr2_*", "mata_garuda.wr2_bridge*"]
        assert is_on_command("pro.wa_mirror_freshness_liveness", patterns) is False
        assert is_on_command("mata_garuda.weekly_digest", patterns) is False

    def test_load_missing_file_returns_empty_not_crash(self, tmp_path):
        assert load_on_command_patterns(str(tmp_path / "does_not_exist.json")) == []

    def test_load_malformed_file_returns_empty_not_crash(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("{not valid json")
        assert load_on_command_patterns(str(p)) == []

    def test_end_to_end_excludes_from_cli_output(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, ["wr2.*"])
        state = tmp_path / "state.json"
        findings = [_finding("wr2.supervisor"), _finding("pro.wa_mirror_freshness_liveness")]
        out = _run_cli(findings, on_cmd, state)
        assert out is not None
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "wr2.supervisor" not in ctx
        assert "pro.wa_mirror_freshness_liveness" in ctx
        assert "1 on-command (excluded)" in ctx


class TestSessionDelta:
    def test_guilt_first_run_no_state_shows_as_new(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        findings = [_finding("pro.something")]
        out = _run_cli(findings, on_cmd, state)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "1 new/changed" in ctx
        assert "pro.something" in ctx

    def test_guilt_identical_second_run_collapses_to_unchanged_count(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        findings = [_finding("pro.something", kind="stale", status="ok")]

        out1 = _run_cli(findings, on_cmd, state)
        assert "pro.something" in out1["hookSpecificOutput"]["additionalContext"]

        out2 = _run_cli(findings, on_cmd, state)
        assert out2 is not None
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        assert "0 new/changed" in ctx2
        assert "+1 unchanged" in ctx2
        assert "pro.something" not in ctx2, (
            "an identical finding must collapse into the count, not repeat the line"
        )

    def test_innocence_changed_status_still_surfaces(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"

        out1 = _run_cli([_finding("pro.flaky", kind="stale", status="ok")], on_cmd, state)
        assert out1 is not None

        out2 = _run_cli([_finding("pro.flaky", kind="unhealthy", status="failed")], on_cmd, state)
        assert out2 is not None
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        assert "1 new/changed" in ctx2
        assert "pro.flaky" in ctx2, "a finding whose kind/status CHANGED must still surface"

    def test_innocence_cured_organ_drops_out_silently(self, tmp_path):
        """A finding present last session but ABSENT this session (organ
        healed) must not linger in state or output — SNAPSHOT contract."""
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"

        _run_cli([_finding("pro.temp_issue")], on_cmd, state)
        # second run: the organ healed, findings list no longer contains it,
        # and a different organ is now the only finding
        out2 = _run_cli([_finding("pro.other")], on_cmd, state)
        ctx2 = out2["hookSpecificOutput"]["additionalContext"]
        assert "pro.temp_issue" not in ctx2
        assert "pro.other" in ctx2

    def test_partition_and_diff_unit(self):
        findings = [_finding("wr2.x"), _finding("pro.y", kind="unhealthy", status="failed")]
        previous = {"pro.y": ["unhealthy", "failed"]}
        new_or_changed, unchanged, excluded, next_state = partition_and_diff(
            findings, ["wr2.*"], previous
        )
        assert excluded == 1
        assert unchanged == 1
        assert new_or_changed == []
        assert next_state == {"pro.y": ["unhealthy", "failed"]}


class TestFailOpen:
    def test_empty_stdin_exits_0_no_output(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        result = subprocess.run(
            [sys.executable, str(_SCRIPT),
             "--on-command-file", str(on_cmd), "--state-file", str(state)],
            input="", capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_malformed_stdin_exits_0_no_output(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        result = subprocess.run(
            [sys.executable, str(_SCRIPT),
             "--on-command-file", str(on_cmd), "--state-file", str(state)],
            input="{not valid json at all", capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert result.stdout.strip() == ""

    def test_all_breathing_empty_list_exits_0_no_output(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        out = _run_cli([], on_cmd, state)
        assert out is None

    def test_corrupt_state_file_does_not_crash(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text("{not valid json")
        out = _run_cli([_finding("pro.x")], on_cmd, state)
        assert out is not None
        assert "pro.x" in out["hookSpecificOutput"]["additionalContext"]

    def test_missing_on_command_file_does_not_crash(self, tmp_path):
        on_cmd = tmp_path / "does_not_exist.json"
        state = tmp_path / "state.json"
        out = _run_cli([_finding("pro.x")], on_cmd, state)
        assert out is not None
        assert "pro.x" in out["hookSpecificOutput"]["additionalContext"]


class TestOutputCap:
    def test_guilt_many_findings_stay_under_cap(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        findings = [
            _finding(f"pro.organ_{i}", detail="x" * 60) for i in range(80)
        ]
        result = subprocess.run(
            [sys.executable, str(_SCRIPT),
             "--on-command-file", str(on_cmd), "--state-file", str(state),
             "--max-bytes", "1500"],
            input=json.dumps(findings), capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        raw = result.stdout.strip()
        assert len(raw.encode("utf-8")) <= 1500, f"got {len(raw.encode('utf-8'))} bytes"
        out = json.loads(raw)
        ctx = out["hookSpecificOutput"]["additionalContext"]
        assert "new/changed" in ctx
        assert "full report" in ctx or "full-report" in ctx or "organism_stale_detector.py" in ctx

    def test_env_independent_max_bytes_flag_is_honored(self, tmp_path):
        on_cmd = tmp_path / "on_command.json"
        _write_on_command_file(on_cmd, [])
        state = tmp_path / "state.json"
        findings = [_finding(f"pro.organ_{i}", detail="y" * 60) for i in range(80)]
        result = subprocess.run(
            [sys.executable, str(_SCRIPT),
             "--on-command-file", str(on_cmd), "--state-file", str(state),
             "--max-bytes", "400"],
            input=json.dumps(findings), capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        raw = result.stdout.strip()
        assert len(raw.encode("utf-8")) <= 400, f"got {len(raw.encode('utf-8'))} bytes"
