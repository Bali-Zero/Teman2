"""Tests for scripts/docs_audit.py classification + inventory generation."""

from __future__ import annotations

import json
import os
import re
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
    _age_file(
        tmp_repo / "docs" / "DUP_V1.md", days=30
    )  # recent, still STALE via cluster
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


def test_inventory_has_no_extra_blank_line_at_eof(aged_fixture):
    _run_audit(
        aged_fixture,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    )
    inventory = aged_fixture / "docs" / "DOCS_INVENTORY.md"
    content = inventory.read_text()
    assert content.endswith("\n")
    assert not content.endswith("\n\n")


def test_idempotent(aged_fixture):
    """Two successive runs produce byte-identical inventory."""
    common = [
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
    ]
    _run_audit(aged_fixture, *common)
    first = (aged_fixture / "docs" / "DOCS_INVENTORY.md").read_text()
    # Strip timestamp line; body must be identical
    first_body = "\n".join(
        line for line in first.splitlines() if "Last run:" not in line
    )
    _run_audit(aged_fixture, *common)
    second = (aged_fixture / "docs" / "DOCS_INVENTORY.md").read_text()
    second_body = "\n".join(
        line for line in second.splitlines() if "Last run:" not in line
    )
    assert first_body == second_body


def test_check_flag_exit_codes(aged_fixture):
    """--check exits 1 if inventory is stale, 0 if in sync."""
    common = [
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
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
    assert "docs_audit: docs/DOCS_INVENTORY.md is out of date" in result.stderr
    assert "--- committed/" in result.stderr
    assert "+++ generated/" in result.stderr


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
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
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
        line = re.sub(
            r"mtime=(\d+)d",
            lambda match: f"mtime={int(match.group(1)) + 1}d",
            line,
        )
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
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
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
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=tmp_repo, check=True, env=env
    )
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
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days",
        "90",
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


def test_shallow_boundary_mtime_is_not_trusted(tmp_path):
    """A shallow boundary commit must not make old docs look freshly edited.

    Regression for PR #1644: the local Air checkout was shallow and contained
    a recent boundary commit. `git log -- docs/foo.md` reported that boundary
    as the last path change for many untouched docs, while GitHub's full
    history correctly classified them as old orphans.
    """
    import shutil

    source_repo = tmp_path / "source"
    shutil.copytree(FIXTURE_REPO, source_repo)
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=source_repo, check=True, env=env
    )
    subprocess.run(["git", "add", "."], cwd=source_repo, check=True, env=env)
    old_date = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 200 * 86400))
    subprocess.run(
        ["git", "commit", "-q", "-m", "initial", "--date", old_date],
        cwd=source_repo,
        check=True,
        env={**env, "GIT_COMMITTER_DATE": old_date},
    )
    (source_repo / "README.md").write_text("# Recent unrelated change\n")
    subprocess.run(["git", "add", "README.md"], cwd=source_repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "recent unrelated"],
        cwd=source_repo,
        check=True,
        env=env,
    )

    shallow_repo = tmp_path / "shallow"
    subprocess.run(
        ["git", "clone", "--depth", "1", f"file://{source_repo}", str(shallow_repo)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert (shallow_repo / ".git" / "shallow").exists()

    raw_log = subprocess.run(
        ["git", "log", "-1", "--format=%s", "--", "docs/ORPHAN_OLD.md"],
        cwd=shallow_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    assert raw_log == "recent unrelated"

    result = _run_audit(
        shallow_repo,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
        "--orphan-days",
        "90",
        "--json",
    )
    assert result.returncode in (0, 1), result.stderr
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}

    assert files["docs/ORPHAN_OLD.md"]["mtime_days"] >= 90
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
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--cluster",
        "test-dup:docs/DUP_V1.md,docs/DUP_V2.md:docs/DUP_V2.md",
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
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(
        ["git", "init", "-q", "-b", "main"], cwd=tmp_repo, check=True, env=env
    )
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
    # Untracked → stat fallback → mtime ≈ 0 → LIVE
    assert files["docs/UNTRACKED_NEW.md"]["status"] == "LIVE"
    assert files["docs/UNTRACKED_NEW.md"]["mtime_days"] < 1


def _init_git_repo(repo: Path, backdate_days: int = 0) -> dict:
    """git-init `repo` in place and commit its current contents. Returns env.

    `backdate_days` > 0 sets the commit's authored+committed date in the
    past, so `git log -1 --format=%ct` (which docs_audit.py trusts over
    `os.stat()`) reports the file as genuinely old — matching how orphan
    aging must be done in a git-mtime-aware fixture (see
    test_git_mtime_beats_stat_mtime for the same pattern).
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    if backdate_days:
        iso = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - backdate_days * 86400)
        )
        env["GIT_AUTHOR_DATE"] = iso
        env["GIT_COMMITTER_DATE"] = iso
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    commit_cmd = ["git", "commit", "-q", "-m", "initial"]
    if backdate_days:
        commit_cmd += ["--date", env["GIT_AUTHOR_DATE"]]
    subprocess.run(commit_cmd, cwd=repo, check=True, env=env)
    return env


def test_apply_batches_single_git_mv_call(tmp_path, monkeypatch):
    """`apply_moves` must issue exactly ONE `git mv` subprocess call for all
    orphans, not one call per file.

    Regression for the 2026-07-07 near-miss (commit e6c5526696): a per-file
    subprocess loop left an interruption window between files, and a killed
    mid-loop run left some `git mv` calls applied and the rest not — the
    partial state was later staged as 37 byte-duplicate copies under
    docs/archive/ instead of clean moves. Batching into one call means the
    move is effectively all-or-nothing at the git-mv step.
    """
    import shutil

    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    _init_git_repo(tmp_repo, backdate_days=120)

    calls: list[list[str]] = []
    real_run = subprocess.run

    def spy_run(cmd, *args, **kwargs):
        if isinstance(cmd, list) and "mv" in cmd:
            calls.append(cmd)
        return real_run(cmd, *args, **kwargs)

    monkeypatch.setattr(docs_audit.subprocess, "run", spy_run)

    docs = docs_audit.walk_docs(tmp_repo)
    rows = [
        docs_audit.classify(d, tmp_repo, 90, ["docs/WHITELIST_KEEPER.md"], [], {})
        for d in docs
    ]
    moved = docs_audit.apply_moves(tmp_repo, rows, use_git=True)

    git_mv_calls = [c for c in calls if c[:2] == ["git", "-C"] and "mv" in c]
    assert len(git_mv_calls) == 1, (
        f"Expected exactly one batched `git mv` call, got {len(git_mv_calls)}: "
        f"{git_mv_calls}"
    )
    assert moved >= 1

    # No duplicate: the orphan must exist ONLY at its new archive path, never
    # at both the old canonical path and the new one simultaneously.
    old_path = tmp_repo / "docs" / "ORPHAN_OLD.md"
    assert not old_path.exists()
    archived = list((tmp_repo / "docs" / "archive").rglob("ORPHAN_OLD.md"))
    assert len(archived) == 1


def test_apply_preserves_subdirs_on_basename_collision(tmp_path):
    """Two orphans sharing a basename in different docs/ subdirectories must
    both move cleanly, preserving their original subpath under the archive
    slug — not collide on a single flat destination directory.

    Regression for #2309: docs_audit.py::apply_moves() previously batched
    ALL orphan sources into one flat docs/archive/<slug>/ directory. `git mv
    docs/ORPHAN_OLD.md docs/collide/ORPHAN_OLD.md docs/archive/<slug>/`
    fatally collides on the shared basename ("fatal: fonti multiple per la
    stessa destinazione" / "multiple sources for the same target"). The fix
    groups sources by their subdirectory under docs/ and preserves that
    subpath under the archive slug, so same-basename orphans from different
    subdirectories land at distinct paths.
    """
    import shutil

    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)

    # NOTE: content must not mention the shared basename anywhere — refs_in
    # is a basename-substring scan across all other docs (see
    # compute_refs_in), so spelling out the filename here would count as a
    # false inbound reference and disqualify the *other* same-named orphan.
    collide_dir = tmp_repo / "docs" / "collide"
    collide_dir.mkdir()
    (collide_dir / "ORPHAN_OLD.md").write_text(
        "# Unrelated subdir doc\n\nNo relation to any other file in this fixture.\n",
        encoding="utf-8",
    )

    _init_git_repo(tmp_repo, backdate_days=120)

    docs = docs_audit.walk_docs(tmp_repo)
    rows = [
        docs_audit.classify(d, tmp_repo, 90, ["docs/WHITELIST_KEEPER.md"], [], {})
        for d in docs
    ]
    orphan_paths = {r.path for r in rows if r.action.startswith("archive: orphan")}
    assert "docs/ORPHAN_OLD.md" in orphan_paths
    assert "docs/collide/ORPHAN_OLD.md" in orphan_paths

    moved = docs_audit.apply_moves(tmp_repo, rows, use_git=True)
    assert moved == len(orphan_paths)

    archive_root = tmp_repo / "docs" / "archive"
    root_hits = list(archive_root.glob("*-orphans/ORPHAN_OLD.md"))
    sub_hits = list(archive_root.glob("*-orphans/collide/ORPHAN_OLD.md"))
    assert len(root_hits) == 1
    assert len(sub_hits) == 1

    # Both originals are gone, neither move overwrote or dropped the other.
    assert not (tmp_repo / "docs" / "ORPHAN_OLD.md").exists()
    assert not (tmp_repo / "docs" / "collide" / "ORPHAN_OLD.md").exists()
    assert root_hits[0].read_text(encoding="utf-8") != sub_hits[0].read_text(
        encoding="utf-8"
    )


def test_regen_only_flag_never_moves_files(tmp_path):
    """`--regen-only` must rewrite DOCS_INVENTORY.md but never touch docs/archive/."""
    import shutil

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    _init_git_repo(tmp_repo, backdate_days=120)

    before = sorted(p.name for p in (tmp_repo / "docs" / "archive").rglob("*.md"))

    result = _run_audit(
        tmp_repo,
        "--whitelist",
        "docs/WHITELIST_KEEPER.md",
        "--orphan-days",
        "90",
        "--regen-only",
    )
    assert result.returncode in (0, 1), result.stderr

    after = sorted(p.name for p in (tmp_repo / "docs" / "archive").rglob("*.md"))
    assert before == after, "‑‑regen-only must not move any file into docs/archive/"
    assert (tmp_repo / "docs" / "ORPHAN_OLD.md").exists(), (
        "orphan candidate must remain at its canonical path under --regen-only"
    )
    inventory = tmp_repo / "docs" / "DOCS_INVENTORY.md"
    assert inventory.exists()
    assert "ORPHAN_OLD.md" in inventory.read_text()


def test_regen_only_rejects_apply(tmp_path):
    """--regen-only + --apply is a contradiction; must exit non-zero, not silently pick one."""
    import shutil

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    result = _run_audit(tmp_repo, "--regen-only", "--apply")
    assert result.returncode != 0
    assert "mutually exclusive" in (result.stderr + result.stdout)


def test_regen_only_rejects_check(tmp_path):
    """--regen-only + --check is a contradiction (one always writes, one never does)."""
    import shutil

    tmp_repo = tmp_path / "repo"
    shutil.copytree(FIXTURE_REPO, tmp_repo)
    result = _run_audit(tmp_repo, "--regen-only", "--check")
    assert result.returncode != 0
    assert "mutually exclusive" in (result.stderr + result.stdout)
