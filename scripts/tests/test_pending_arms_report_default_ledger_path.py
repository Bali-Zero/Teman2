"""PENDING-ARMS L982 (opened 2026-08-08, closed 2026-09-24): the documented
escape hatch for a stale checkout -- copy this script to a scratch location
and run it from there (`git show origin/main:scripts/pending_arms_report.py >
/tmp/par_main.py && python3 /tmp/par_main.py --ref origin/main ...`, the same
move proprioception.py's own remedy prints) -- was UNEXECUTABLE: the default
ledger path was derived purely from `__file__`, so from `/tmp` its
`parent.parent` is `/` and the script exits 2 with "ledger not found:
/.claude/skills/modus/PENDING-ARMS.md". Measured, not reasoned: this is the
exact error text the ledger row quotes.

The fix mirrors proprioception.py:repo_root()'s NUZ_REPO_ROOT-first fallback.
This test copies the script to an out-of-repo tmp_path (same relocation the
banner's remedy performs) and asserts it fails without the env var and
succeeds with it pointed at the real repo root.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "pending_arms_report.py"


def _run_relocated(tmp_path: Path, *, repo_root_env: str | None) -> subprocess.CompletedProcess:
    relocated = tmp_path / "par_relocated.py"
    relocated.write_text(SCRIPT.read_text(encoding="utf-8"), encoding="utf-8")
    env: dict[str, str] = {"PATH": "/usr/bin:/bin"}
    if repo_root_env is not None:
        env["NUZ_REPO_ROOT"] = repo_root_env
    return subprocess.run(
        [sys.executable, str(relocated), "--ref", "HEAD"],
        capture_output=True, text=True, timeout=60,
        cwd=str(tmp_path), env=env,
    )


def test_guilt_relocated_copy_without_nuz_repo_root_reports_ledger_not_found(tmp_path):
    result = _run_relocated(tmp_path, repo_root_env=None)
    assert result.returncode != 0
    assert "ledger not found" in result.stderr, result.stderr


def test_innocence_relocated_copy_with_nuz_repo_root_finds_the_real_ledger(tmp_path):
    result = _run_relocated(tmp_path, repo_root_env=str(REPO))
    assert result.returncode == 0, result.stderr
    assert str(REPO / ".claude" / "skills" / "modus" / "PENDING-ARMS.md") in result.stdout
