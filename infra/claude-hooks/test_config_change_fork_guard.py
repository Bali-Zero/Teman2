#!/usr/bin/env python3
"""Guilt + innocence for config_change_fork_guard.py (superscar #1 arming hook).

GUILT: a declared pair whose live copy differs from its repo copy must be NAMED.
INNOCENCE: an aligned pair must produce no output at all — silence here means
"no drift", so a hook that speaks on an aligned pair would train the session to
ignore it (the failure mode that made the linter useless in the first place).

Everything runs inside a temporary repo root handed to the hook through
CLAUDE_PROJECT_DIR: no real declared pair, no real $HOME file, nothing on this
machine is read or written.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HOOK = Path(__file__).resolve().parent / "config_change_fork_guard.py"


def run_hook(repo_root: Path, changed: str) -> str:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(repo_root))
    res = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"file_path": changed}),
        capture_output=True,
        text=True,
        env=env,
    )
    assert res.returncode == 0, f"advisory hook must always exit 0, got {res.returncode}"
    return res.stdout.strip()


def build(tmp: Path, live_body: str, repo_body: str) -> tuple[Path, Path]:
    live = tmp / "live_copy.sh"
    repo_rel = "infra/claude-hooks/twin_copy.sh"
    repo_file = tmp / repo_rel
    repo_file.parent.mkdir(parents=True, exist_ok=True)
    live.write_text(live_body)
    repo_file.write_text(repo_body)
    pairs = tmp / "infra" / "home-fork" / "declared-pairs.json"
    pairs.parent.mkdir(parents=True, exist_ok=True)
    pairs.write_text(json.dumps({"pairs": [{"live": str(live), "repo": repo_rel}]}))
    return live, repo_file


def test_guilt_drifted_pair_is_named() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        live, _ = build(tmp, "echo live\n# edited in HOME only\n", "echo live\n")
        out = run_hook(tmp, str(live))
        assert out, "GUILT FAILED: a drifted declared pair produced no output"
        payload = json.loads(out)["hookSpecificOutput"]
        assert payload["hookEventName"] == "ConfigChange"
        assert "twin_copy.sh" in payload["additionalContext"]


def test_innocence_aligned_pair_is_silent() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        live, _ = build(tmp, "echo live\n", "echo live\n")
        assert run_hook(tmp, str(live)) == "", "INNOCENCE FAILED: aligned pair spoke"


def test_innocence_unrelated_file_is_silent() -> None:
    """A ConfigChange on a file that is not a declared pair must say nothing,
    even while another pair on the machine is drifted."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        live, _ = build(tmp, "echo live\n# drifted\n", "echo live\n")
        other = tmp / "some_other_file.json"
        other.write_text("{}")
        assert run_hook(tmp, str(other)) == "", "INNOCENCE FAILED: spoke about an unrelated file"


def test_malformed_input_never_breaks_a_session() -> None:
    env = dict(os.environ, CLAUDE_PROJECT_DIR="/nonexistent-repo-root")
    res = subprocess.run(
        [sys.executable, str(HOOK)], input="not json", capture_output=True, text=True, env=env
    )
    assert res.returncode == 0 and res.stdout.strip() == ""


if __name__ == "__main__":
    test_guilt_drifted_pair_is_named()
    test_innocence_aligned_pair_is_silent()
    test_innocence_unrelated_file_is_silent()
    test_malformed_input_never_breaks_a_session()
    print("config_change_fork_guard: guilt + 3 innocence cases pass")
