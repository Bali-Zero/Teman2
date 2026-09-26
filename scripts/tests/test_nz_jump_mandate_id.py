"""nz-jump.sh must carry the parent's NUZANTARA_MANDATE_ID into the successor.

PENDING-ARMS L2027: a fresh window opened by nz-jump never inherits its
parent's environment, so `child_workflow.py`'s `mandate_id()` — which returns
`NUZANTARA_MANDATE_ID` when set, else falls back to a session_id-derived key —
silently keyed the jumped-to window under a DIFFERENT budget subject than its
parent. `context_window_guard.py._write_pending_jump` now carries the parent's
`NUZANTARA_MANDATE_ID` (read from ITS OWN environment, where it IS set) into
the pending-jump file as `mandate_id`; this pins that nz-jump.sh reads it back
and would re-export it (or warns instead of proceeding silently).

  GUILT     (mandate_id present in the jump file): the dry-run seam reports
            the SAME value, and no unresolved-mandate warning fires.
  INNOCENCE (mandate_id absent/empty): the dry-run seam reports an empty
            value, and the run emits an explicit unresolved-mandate warning
            on stderr — never a silent fallback.

Seam: NZ_JUMP_DRY=1 exits before `exec claude`, one line after the argv
lines report `mandate_id=<value>` — mirroring test_nz_jump_model_alias.py's
own seam for the model-suffix fix.
"""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "claude-hooks" / "nz-jump.sh"


def _run(tmp_path: Path, mandate_id: str | None) -> subprocess.CompletedProcess[str]:
    home = tmp_path / "home"
    (home / ".organism" / "context-guard").mkdir(parents=True)
    (home / ".claude").mkdir()
    cwd = tmp_path / "repo"
    cwd.mkdir()
    pending = {"model": "", "cwd": str(cwd), "hops": 1, "permission_mode": ""}
    if mandate_id is not None:
        pending["mandate_id"] = mandate_id
    (home / ".organism" / "context-guard" / "pending-jump-sess-1.json").write_text(json.dumps(pending))
    env = {k: v for k, v in os.environ.items() if k not in {"CLAUDE_CONFIG_DIR", "NZ_JUMP_FROM", "NUZANTARA_MANDATE_ID"}}
    env.update({"HOME": str(home), "NZ_JUMP_DRY": "1"})
    return subprocess.run(["bash", str(SCRIPT), "sess-1"], env=env, capture_output=True, text=True, timeout=60)


def _dry_run_mandate_id(stdout: str) -> str:
    for line in stdout.splitlines():
        if line.startswith("nz-jump: dry-run mandate_id="):
            return line.removeprefix("nz-jump: dry-run mandate_id=")
    raise AssertionError(f"no dry-run mandate_id line in: {stdout!r}")


def test_guilt_mandate_id_present_is_carried_through_and_silent(tmp_path):
    r = _run(tmp_path, "mandate-abc-123")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _dry_run_mandate_id(r.stdout) == "mandate-abc-123"
    assert "WARNING" not in r.stderr, r.stderr


def test_innocence_missing_mandate_id_reports_empty_and_warns(tmp_path):
    r = _run(tmp_path, None)
    assert r.returncode == 0, r.stdout + r.stderr
    assert _dry_run_mandate_id(r.stdout) == ""
    assert "parent mandate id unresolved" in r.stderr, r.stderr


def test_innocence_blank_mandate_id_reports_empty_and_warns(tmp_path):
    r = _run(tmp_path, "")
    assert r.returncode == 0, r.stdout + r.stderr
    assert _dry_run_mandate_id(r.stdout) == ""
    assert "parent mandate id unresolved" in r.stderr, r.stderr
