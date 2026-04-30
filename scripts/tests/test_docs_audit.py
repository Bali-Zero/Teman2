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


def test_check_ignores_mtime_days_drift(aged_fixture):
    """`--check` must NOT fail when the only delta is mtime_days incrementing.

    Calendar time advances every day; if `--check` flagged that, every PR
    touching `docs/**` would fail Docs Guardian on the day after the last
    inventory regen — making the gate noise instead of signal. Regression
    for the 2026-05-01 incident on PR #401, where the `inventory-check`
    job in `.github/workflows/docs-guardian.yml` flagged a 1-day
    mtime_days drift on every row even though no doc was actually stale.
    """
    common = [
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    ]
    # Generate inventory at the fixture's current "today".
    _run_audit(aged_fixture, *common)

    # Bump every mtime_days by 1 to simulate "the next calendar day".
    inventory = aged_fixture / "docs" / "DOCS_INVENTORY.md"
    bumped: list[str] = []
    in_table = False
    for line in inventory.read_text().splitlines():
        if line.startswith("|") and "mtime_days" in line:
            in_table = True
            bumped.append(line)
            continue
        if in_table and line.startswith("| ") and "---" not in line:
            parts = line.split("|")
            # | path | STATUS | mtime_days | refs_in | broken | drift | …
            if len(parts) >= 9:
                try:
                    parts[3] = f" {int(parts[3].strip()) + 1} "
                    line = "|".join(parts)
                except ValueError:
                    pass
        bumped.append(line)
    inventory.write_text("\n".join(bumped) + "\n")

    # Drift is mtime-only → the fix in render_inventory's strip_volatile
    # must mask it, so --check must still exit 0.
    result = _run_audit(aged_fixture, *common, "--check")
    assert result.returncode == 0, result.stdout + result.stderr

    # Sanity: re-running without --check must rewrite the file with the
    # real (smaller) mtime values, restoring byte-identical state.
    _run_audit(aged_fixture, *common)
    result = _run_audit(aged_fixture, *common, "--check")
    assert result.returncode == 0


def test_check_still_catches_real_drift(aged_fixture):
    """Counterpart to the mtime-drift mask: a real status change must trip --check.

    Without this guarantee, the strip_volatile mask could over-strip and
    silently hide actual drift (e.g. a doc going LIVE → STALE).
    """
    common = [
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    ]
    _run_audit(aged_fixture, *common)
    inventory = aged_fixture / "docs" / "DOCS_INVENTORY.md"
    content = inventory.read_text()
    # Flip first LIVE row to STALE.
    mutated = content.replace("| LIVE |", "| STALE |", 1)
    assert mutated != content, "fixture has no LIVE rows — adjust"
    inventory.write_text(mutated)

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


def test_broken_link_inside_code_fence_is_ignored(aged_fixture):
    """Links inside ``` fenced code blocks AND inline `...` spans are examples,
    not real markdown links. They should NOT count as broken.
    """
    doc = aged_fixture / "docs" / "LIVE_DOC.md"
    doc.write_text(
        "# Live\n\n"
        "Real: [missing](real-missing.md)\n\n"
        "Example in fenced block:\n"
        "```markdown\n"
        "[fake](fake-inside-fence.md)\n"
        "```\n\n"
        "Example inline backticks: `[inline](inline-fake.md)` — should be skipped.\n"
    )
    result = _run_audit(
        aged_fixture,
        "--whitelist", "docs/WHITELIST_KEEPER.md",
        "--cluster", "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--json",
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    # Only the real one outside code regions should count → broken == 1
    assert files["docs/LIVE_DOC.md"]["broken"] == 1


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
