"""Guilt+innocence for the codex-nightly-autofix-ci.sh eligibility filter.

Recursion bite 2026-07-06: the generator chased its own codex/auto-fix-ci-*
branches — each failed fix PR became the next cycle's target (#2063 -> #2064
-> #2065, hourly, bounded only by the daily cap). Root of the chain was a
failing dependabot mega-bump, whose branch is force-push mutable and thus a
fragile base for a fix PR.

The filter must never select:
  - its own output branches (codex/auto-fix-ci-*)  [recursion brake]
  - dependabot/* branches (mutable base)           [fragile-base guard]
and must still select a genuine feature-branch failure (innocence).

Runs the REAL script in CODEX_AUTOFIX_DRY_RUN=1 with injected failed-runs
JSON — no gh, no codex, no network, no git mutations (dry-run exits before
any checkout).
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

SCRIPT = (
    Path(__file__).resolve().parent.parent / "codex" / "codex-nightly-autofix-ci.sh"
)


def _mkrun(run_id: int, branch: str, name: str = "Tests & Coverage") -> dict:
    return {
        "databaseId": run_id,
        "name": name,
        "headBranch": branch,
        "headSha": "a" * 40,
        "displayTitle": f"run on {branch}",
        "createdAt": "2026-07-06T17:00:00Z",
    }


def _run(tmp_path: Path, runs: list[dict]) -> subprocess.CompletedProcess:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "CODEX_AUTOFIX_DRY_RUN": "1",
            "CODEX_AUTOFIX_FAILED_RUNS_JSON": json.dumps(runs),
            "CODEX_AUTOFIX_STATE_DIR": str(tmp_path / "state"),
            "CODEX_AUTOFIX_LOG_DIR": str(tmp_path / "logs"),
            "CODEX_AUTOFIX_REPO_ROOT": str(repo_root),
            # Point at a nonexistent lib so the HOME automation lib is never sourced.
            "CODEX_AUTOMATION_LIB": str(tmp_path / "no-such-lib.sh"),
        }
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_guilt_own_autofix_branch_never_selected(tmp_path):
    """A failure on codex/auto-fix-ci-* must be invisible (recursion brake)."""
    proc = _run(tmp_path, [_mkrun(111, "codex/auto-fix-ci-99999")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout
    assert "selected run_id" not in proc.stdout


def test_guilt_dependabot_branch_never_selected(tmp_path):
    """A failure on dependabot/* must be invisible (mutable fix base)."""
    proc = _run(
        tmp_path, [_mkrun(222, "dependabot/pip/apps/backend-rag/minor-and-patch-x")]
    )
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_guilt_main_branch_never_selected(tmp_path):
    """Pre-existing guard pinned: main failures are not auto-fix targets."""
    proc = _run(tmp_path, [_mkrun(233, "main")])
    assert proc.returncode == 0, proc.stderr
    assert "No eligible failures" in proc.stdout


def test_innocence_feature_branch_selected(tmp_path):
    """A genuine feature-branch failure must still be selected."""
    proc = _run(tmp_path, [_mkrun(333, "agent/air-m5/feature/x")])
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=333" in proc.stdout


def test_innocence_real_failure_behind_own_branch_selected(tmp_path):
    """Own-branch noise ahead in the list must not shadow a real failure."""
    proc = _run(
        tmp_path,
        [
            _mkrun(444, "codex/auto-fix-ci-123"),
            _mkrun(555, "feature/real-work"),
        ],
    )
    assert proc.returncode == 0, proc.stderr
    assert "[dry-run] selected run_id=555" in proc.stdout
