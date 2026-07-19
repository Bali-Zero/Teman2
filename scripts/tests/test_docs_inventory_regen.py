"""Tests for scripts/docs_inventory_regen.sh — the SSOT wrapper the
docs-inventory-refresh.yml organ calls (BLOCKER-3, red-team 2026-07-18).

The REAL wrapper script is copied verbatim into a fake repo alongside STUB
scripts/docs_sync.py and scripts/docs_audit.py (both real, controllable
Python scripts, not mocks) — since docs_inventory_regen.sh computes its own
SCRIPT_DIR from `${BASH_SOURCE[0]}` and invokes `python3 scripts/<tool>.py`
relative to that, a copy in a fresh directory naturally picks up the stubs
placed alongside it. This exercises the REAL bash control-flow (the
exit-code distinguishing logic), not a hand-copied duplicate of it.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REAL_REGEN_SH = REPO_ROOT / "scripts" / "docs_inventory_regen.sh"

_STUB_SYNC_OK = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"
_STUB_AUDIT_OK = "#!/usr/bin/env python3\nimport sys\nsys.exit(0)\n"


def _make_fake_repo(tmp_path: Path, *, sync_exit: str, audit_exit: str) -> Path:
    """`sync_exit`/`audit_exit` are full Python script bodies (not just exit
    codes) so a test can also emit stderr text or simulate a real traceback,
    not only `sys.exit(N)`.
    """
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    shutil.copy(REAL_REGEN_SH, scripts_dir / "docs_inventory_regen.sh")
    (scripts_dir / "docs_sync.py").write_text(sync_exit, encoding="utf-8")
    (scripts_dir / "docs_audit.py").write_text(audit_exit, encoding="utf-8")
    return tmp_path


def _run_regen(fake_repo: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(fake_repo / "scripts" / "docs_inventory_regen.sh")],
        cwd=fake_repo,
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_clean_run_both_tools_exit_0(tmp_path):
    """INNOCENCE baseline: both tools succeed cleanly -> wrapper exits 0."""
    fake_repo = _make_fake_repo(
        tmp_path, sync_exit=_STUB_SYNC_OK, audit_exit=_STUB_AUDIT_OK
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, result.stdout + result.stderr


def test_docs_audit_expected_drift_exit_1_is_swallowed(tmp_path):
    """INNOCENCE: docs_audit.py returning 1 ('content changed', intentional
    per its own documented contract) must NOT fail the wrapper — that is the
    pre-existing, correct behavior BLOCKER-3 must not regress.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit="#!/usr/bin/env python3\nimport sys\nsys.exit(1)\n",
    )
    result = _run_regen(fake_repo)
    assert result.returncode == 0, (
        f"expected drift (exit 1) must be swallowed: {result.stdout}{result.stderr}"
    )


def test_docs_audit_crash_exit_2_propagates(tmp_path):
    """GUILT (red-team 2026-07-18 BLOCKER-3): docs_audit.py CRASHING (its own
    dedicated exit 2, P3-prime __main__ crash boundary) must FAIL this
    wrapper for real — the old `|| true` swallowed 1 and 2 identically,
    making a genuine crash silently indistinguishable from 'nothing
    changed' on an apparently-green run.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('docs_audit: CRASHED — RuntimeError: synthetic', file=sys.stderr)\n"
            "sys.exit(2)\n"
        ),
    )
    result = _run_regen(fake_repo)
    assert result.returncode != 0, (
        f"a docs_audit.py crash (exit 2) must fail the wrapper, not be "
        f"silently absorbed: got exit {result.returncode}"
    )
    assert "CRASHED" in (result.stdout + result.stderr) or result.returncode == 2


def test_docs_sync_crash_propagates(tmp_path):
    """GUILT: docs_sync.py (write mode, no --check/--diff) legitimately
    ALWAYS returns 0 — the ONLY way it returns non-zero here is a genuine
    crash. That must fail the wrapper too, not be swallowed by a blanket
    `|| true` (the old behavior).
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('boom', file=sys.stderr)\n"
            "sys.exit(1)\n"
        ),
        audit_exit=_STUB_AUDIT_OK,
    )
    result = _run_regen(fake_repo)
    assert result.returncode != 0, (
        "a docs_sync.py crash must fail the wrapper, not be silently absorbed"
    )
    # And the wrapper must not even attempt the docs_audit.py step afterward
    # (fail fast, don't paper over one crash by racing ahead to the next tool).
    assert "regenerating docs/DOCS_INVENTORY.md" not in result.stderr


def test_docs_audit_stats_json_path_still_used_on_clean_run(tmp_path):
    """Sanity: the DOCS_AUDIT_STATS_JSON capture path (added earlier the same
    day for the flip-count surfacing feature) still works after the
    BLOCKER-3 exit-code rework — not a red-team-mandated test, but cheap
    insurance against a regression in an adjacent code path this same PR
    touches.
    """
    fake_repo = _make_fake_repo(
        tmp_path,
        sync_exit=_STUB_SYNC_OK,
        audit_exit=(
            "#!/usr/bin/env python3\n"
            "import sys\n"
            "print('{\"flips_this_run\": 0}')\n"
            "sys.exit(0)\n"
        ),
    )
    stats_path = tmp_path / "stats.json"
    import os

    env = {**os.environ, "DOCS_AUDIT_STATS_JSON": str(stats_path)}
    result = _run_regen(fake_repo, env=env)
    assert result.returncode == 0, result.stdout + result.stderr
    assert stats_path.exists()
    assert '"flips_this_run": 0' in stats_path.read_text()
