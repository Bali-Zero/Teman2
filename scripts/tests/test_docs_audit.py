"""Tests for scripts/docs_audit.py classification + inventory generation."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_SCRIPT = REPO_ROOT / "scripts" / "docs_audit.py"
FIXTURE_REPO = REPO_ROOT / "scripts" / "tests" / "fixtures" / "docs_audit" / "repo"


def _age_file(path: Path, days: int) -> None:
    """Make a file appear `days` days old via os.utime."""
    now = time.time()
    atime = mtime = now - days * 86400
    os.utime(path, (atime, mtime))


@pytest.fixture
def aged_fixture(tmp_path):
    """Copy fixture repo into tmp_path, age the ORPHAN_OLD + WHITELIST_KEEPER.

    Returns the tmp repo root.
    """
    import shutil

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    _age_file(tmp_repo / "docs" / "ORPHAN_OLD.md", days=120)
    _age_file(tmp_repo / "docs" / "WHITELIST_KEEPER.md", days=120)
    _age_file(tmp_repo / "docs" / "DUP_V1.md", days=30)  # recent, still STALE via cluster
    return tmp_repo


def _run_audit(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke docs_audit.py with --repo pointing to the fixture."""
    cmd = [sys.executable, str(AUDIT_SCRIPT), "--repo", str(repo), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_classify_live_doc(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--json",
    )
    assert result.returncode in (0, 1), result.stderr
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/LIVE_DOC.md"]["status"] == "LIVE"


def test_classify_stale_drift(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--docsync-key",
        "TEST_KEY:42",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/STALE_DRIFT.md"]["status"] == "STALE"
    assert files["docs/STALE_DRIFT.md"]["drift"] is True


def test_classify_orphan_archived(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days",
        "90",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/ORPHAN_OLD.md"]["status"] == "ARCHIVED"
    assert "orphan" in files["docs/ORPHAN_OLD.md"]["action"]


def test_whitelist_keeps_live(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days",
        "90",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/WHITELIST_KEEPER.md"]["status"] == "LIVE"


def test_broken_link_marks_stale(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/BROKEN_LINK.md"]["status"] == "STALE"
    assert files["docs/BROKEN_LINK.md"]["broken"] >= 1


def test_duplicate_cluster_marks_stale(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/DUP_V1.md"]["status"] == "STALE"
    assert files["docs/DUP_V1.md"]["cluster"] == "test-dup"
    assert files["docs/DUP_V2.md"]["cluster"] == "test-dup"
    # Canonical (V2) is STALE too because it's in the cluster, but action says "keep"
    assert "keep" in files["docs/DUP_V2.md"]["action"].lower()
    assert "archive" in files["docs/DUP_V1.md"]["action"].lower()


def test_already_archived(aged_fixture):
    result = _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/archive/OLD_ARCHIVED.md"]["status"] == "ARCHIVED"


def test_inventory_file_written(aged_fixture):
    _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    )
    inventory = aged_fixture / "docs" / "DOCS_INVENTORY.md"
    assert inventory.exists()
    content = inventory.read_text()
    assert "# Documentation Inventory" in content
    assert "## Summary" in content
    assert "## Files" in content


def test_idempotent(aged_fixture):
    """Two successive runs produce byte-identical inventory."""
    common = [
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    ]
    _run_audit(aged_fixture, *common)
    first = (aged_fixture / "docs" / "DOCS_INVENTORY.md").read_text()
    # Strip timestamp line; body must be identical
    first_body = "\n".join(l for l in first.splitlines() if "Last run:" not in l)
    _run_audit(aged_fixture, *common)
    second = (aged_fixture / "docs" / "DOCS_INVENTORY.md").read_text()
    second_body = "\n".join(l for l in second.splitlines() if "Last run:" not in l)
    assert first_body == second_body


def test_check_flag_exit_codes(aged_fixture):
    """--check exits 1 if inventory is stale, 0 if in sync."""
    common = [
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    ]
    # First: generate inventory (no --check)
    _run_audit(aged_fixture, *common)
    # Now --check should pass
    result = _run_audit(aged_fixture, *common, "--check")
    assert result.returncode == 0
    # Mutate a doc: add a broken link to LIVE_DOC → next --check should fail
    live_doc = aged_fixture / "docs" / "LIVE_DOC.md"
    live_doc.write_text(live_doc.read_text() + "\n[missing](nope.md)\n")
    result = _run_audit(aged_fixture, *common, "--check")
    assert result.returncode == 1


def test_git_mtime_beats_stat_mtime(tmp_path):
    """When the file is in a git repo, the audit must use `git log` for mtime,
    not `os.stat().st_mtime`. This protects against git-checkout resetting
    filesystem mtime (worktree or CI `actions/checkout`).

    Setup:
      - Fresh git repo
      - Commit a doc with backdated commit date (>90 days old)
      - `os.stat()` of the doc reports "now" (just written)
      - Expected: classify as ARCHIVED (orphan), because git says it's old
    """
    import shutil

    # Seed a minimal repo from the existing fixture
    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)

    # Initialize git, backdate an orphan doc
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_repo, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=tmp_repo, check=True, env=env)
    # Commit with a timestamp 200 days in the past
    backdated = time.time() - 200 * 86400
    iso = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(backdated))
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial", "--date", iso],
        cwd=tmp_repo,
        check=True,
        env={**env, "GIT_COMMITTER_DATE": iso},
    )

    # Now touch ORPHAN_OLD to force stat mtime = "now" (simulates worktree checkout)
    orphan = tmp_repo / "docs" / "ORPHAN_OLD.md"
    os.utime(orphan, None)  # defaults to now
    # Confirm: stat says recent, git log says 200d ago
    stat_mtime_days = int((time.time() - orphan.stat().st_mtime) / 86400)
    assert stat_mtime_days < 1  # stat reports "now" (≤ 1 day)

    result = _run_audit(
        tmp_repo,
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days", "90",
        "--json",
    )
    assert result.returncode in (0, 1), result.stderr
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}

    # If the audit uses stat(), ORPHAN_OLD would be LIVE (mtime=0d). If it uses
    # git, it's ARCHIVED (orphan, 200d old). We require the git path.
    assert files["docs/ORPHAN_OLD.md"]["mtime_days"] >= 90, (
        f"Expected git-based mtime ≥90d, got {files['docs/ORPHAN_OLD.md']['mtime_days']}. "
        "The audit is likely still using os.stat() which is reset by git checkout."
    )
    assert files["docs/ORPHAN_OLD.md"]["status"] == "ARCHIVED"
    assert "orphan" in files["docs/ORPHAN_OLD.md"]["action"]


def test_stat_fallback_for_untracked_files(tmp_path):
    """If a file is not in git history (untracked), fall back to os.stat().
    An untracked file with recent os.stat() mtime should be classified based
    on its stat mtime (recent → not orphan).
    """
    import shutil

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T", "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T", "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=tmp_repo, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=tmp_repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial"],
        cwd=tmp_repo,
        check=True,
        env=env,
    )

    # Add a new untracked doc with recent mtime
    untracked = tmp_repo / "docs" / "UNTRACKED_NEW.md"
    untracked.write_text("# New\nRecent untracked.\n")

    result = _run_audit(
        tmp_repo,
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days", "90",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    # Untracked → stat fallback → mtime ≈ 0 → LIVE
    assert files["docs/UNTRACKED_NEW.md"]["status"] == "LIVE"
    assert files["docs/UNTRACKED_NEW.md"]["mtime_days"] < 1
