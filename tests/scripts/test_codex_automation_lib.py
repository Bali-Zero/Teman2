"""Tests for the Codex automation shell helper library."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
LIB = REPO_ROOT / "scripts" / "codex_automation_lib.sh"


def _run_bash(script: str, *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/bash", "-lc", script],
        cwd=cwd,
        text=True,
        capture_output=True,
        timeout=30,
    )


def _init_git_repo(path: Path) -> None:
    path.mkdir(parents=True)
    _run_bash("git init -q", cwd=path).check_returncode()
    _run_bash("git config user.email codex-test@example.test", cwd=path).check_returncode()
    _run_bash("git config user.name 'Codex Test'", cwd=path).check_returncode()
    (path / "README.md").write_text("hello\n", encoding="utf-8")
    _run_bash("git add README.md && git commit -qm init", cwd=path).check_returncode()


def test_create_run_worktree_uses_separate_clean_checkout(tmp_path: Path) -> None:
    source_repo = tmp_path / "source"
    worktrees_root = tmp_path / "worktrees"
    _init_git_repo(source_repo)

    script = f"""
        set -euo pipefail
        source {LIB}
        worktree=$(codex_auto_create_run_worktree {source_repo} {worktrees_root} codex/test-autonomy HEAD)
        test "$worktree" != "{source_repo}"
        test -d "$worktree/.git" -o -f "$worktree/.git"
        git -C "$worktree" status --porcelain
        git -C "$worktree" rev-parse --abbrev-ref HEAD
    """
    result = _run_bash(script)

    assert result.returncode == 0, result.stderr
    assert "codex/test-autonomy" in result.stdout
    assert (worktrees_root / "codex-test-autonomy").exists()


def test_write_state_records_actionable_outcome(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    script = f"""
        set -euo pipefail
        source {LIB}
        export CODEX_AUTOMATION_STATE_DIR={state_dir}
        codex_auto_write_state com.nuzantara.codex-coverage-improver action pr_opened "PR opened" branch-1 /tmp/wt
    """
    result = _run_bash(script)

    assert result.returncode == 0, result.stderr
    state_path = state_dir / "codex_com_nuzantara_codex_coverage_improver.state.json"
    data = json.loads(state_path.read_text(encoding="utf-8"))
    assert data["job"] == "com.nuzantara.codex-coverage-improver"
    assert data["outcome"] == "action"
    assert data["action"] == "pr_opened"
    assert data["message"] == "PR opened"
    assert data["branch"] == "branch-1"
    assert data["worktree"] == "/tmp/wt"
    assert isinstance(data["ts"], float)
