"""Tests for scripts/docs_audit.py classification + inventory generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from datetime import date, timedelta
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
        # BLOCKER-2 (red-team 2026-07-18): aged_fixture is deliberately
        # git-less (exercises the stat-mtime fallback elsewhere) so it has
        # no origin/main --check can trust — an already-organ-archived doc
        # (ORPHAN_OLD.md, aged via os.utime) would legitimately "revert" to
        # LIVE under the new trusted-provenance read, unrelated to what this
        # test actually asserts (exit-code contract via a broken-link
        # mutation). Whitelisting it removes it from the orphan/flip
        # mechanism entirely so that unrelated behavior change can't leak in.
        "--whitelist",
        "docs/ORPHAN_OLD.md",
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
        # BLOCKER-2 (red-team 2026-07-18): see the identical comment in
        # test_check_flag_exit_codes — aged_fixture has no origin/main for
        # --check to trust, so ORPHAN_OLD.md's already-organ-archived state
        # would unrelatedly "revert" to LIVE; whitelist it out of the
        # orphan/flip mechanism, irrelevant to this test's actual assertion
        # (mtime_days-only drift must be masked).
        "--whitelist",
        "docs/ORPHAN_OLD.md",
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

    # P3-prime BLOCKER-2 (red-team 2026-07-18): wire a same-content `origin`
    # remote so --check's trusted-ref read (default origin/main) resolves in
    # tests exactly as it always does in real CI (a genuine actions/checkout
    # always has one) — self-referential by construction (origin/main ==
    # this repo's own current main) unless a test deliberately diverges the
    # two afterward, e.g. via a separate `git clone` + working-tree tamper
    # (see the BLOCKER-2 forgery tests below).
    origin_bare = repo.parent / f"{repo.name}-origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "main", str(origin_bare)],
        check=True,
        env=env,
    )
    subprocess.run(
        ["git", "remote", "add", "origin", str(origin_bare)],
        cwd=repo,
        check=True,
        env=env,
    )
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo, check=True, env=env)
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


# ============================================================================
# P3-prime — deterministic eligibility-date gate
# (research/operations/2026-07-17-push-pipeline-optimization-spec.md §P3).
#
# The disease: classify()'s orphan rule used to compare mtime_days (derived
# from `datetime.now()`) against orphan_days on EVERY run, including --check
# (the PR merge gate) — so an unrelated PR could go red the day a totally
# different, untouched doc's age silently crossed the 90-day mark (2x on
# #2509, again on #2592/#2613 area). The cure: --check (as_of=None) verifies
# only DETERMINISTIC per-tree facts (last_touched_date, orphan_eligible_on —
# pure functions of git history + orphan_days arithmetic) and NEVER decides
# the orphan time-crossing itself; only a write-mode call (the scheduled
# docs-inventory-refresh.yml organ) may stamp a fresh orphan_flipped_on.
#
# Tests below, by category:
#   GUILT      — dates inconsistent with git history -> red (P3A, P3B)
#   GUILT      — STATUS=ARCHIVED without organ provenance -> red (P3C)
#   INNOCENCE  — an unrelated doc crossing eligibility never flips --check on
#                its own, no matter how much real time has passed (P3D, the
#                direct #2509/#2592 regression test)
#   INNOCENCE  — strongest form: --check is provably immune to a MOCKED
#                datetime.now(), not just "happens to be" immune (P3E)
#   mechanism  — the organ's flip is stable/idempotent once made (P3F)
#   CLI rails  — --check+--as-of and malformed --as-of are rejected (P3G/P3H)
# ============================================================================


def _make_git_repo_with_old_doc(tmp_path, backdate_days: int = 200) -> Path:
    """A minimal, single-doc git repo (docs/OLD_DOC.md, zero inbound refs,
    never whitelisted), committed `backdate_days` days before real "today".

    Deliberately avoids the shared FIXTURE_REPO (which has cross-referencing
    docs) so refs_in is unambiguously 0 — the ONLY thing gating this doc's
    orphan eligibility is the calendar, which is exactly what these tests
    need to control precisely via --as-of.
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "OLD_DOC.md").write_text(
        "# Old doc\n\nNo relation to any other file in this fixture.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo, backdate_days=backdate_days)
    return repo


def _commit_and_push(repo: Path, message: str = "snapshot") -> None:
    """Commit the CURRENT working-tree state and push it to `repo`'s own
    `origin` (wired by _init_git_repo) — simulates "the organ committed and
    pushed this to main", making it visible to a LATER --check's trusted-ref
    read (BLOCKER-2, red-team 2026-07-18). Needed after any write-mode
    docs_audit.py call whose result a test then wants --check to see as
    prior/trusted state — --check reads provenance from origin/main, NEVER
    from the working tree, so a write-mode regen that is never committed+
    pushed is invisible to it BY DESIGN (that invisibility is the whole
    point of the fix).
    """
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", message], cwd=repo, check=True, env=env)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo, check=True, env=env)


def _row_cells(inventory_text: str, path: str) -> list[str]:
    """Split the `## Files` table row for `path` into raw `|`-delimited cells
    (including the leading/trailing empty strings from split), so a test can
    mutate a SPECIFIC column by index without hand-building a whole row.
    """
    for line in inventory_text.splitlines():
        if line.startswith(f"| {path} |"):
            return line.split("|")
    raise AssertionError(f"row for {path!r} not found in inventory:\n{inventory_text}")


def test_p3prime_check_never_invents_a_flip_no_matter_the_real_age(tmp_path):
    """INNOCENCE (core proof, direct regression test for #2509/#2592): a doc
    committed 200 real days ago — genuinely, structurally past the 90-day
    orphan threshold AS OF TODAY — whose last organ-regen baseline (dated,
    via --as-of, to BEFORE it was eligible) recorded it LIVE, must STAY LIVE
    under `--check` run at the real current date. --check must never
    independently decide "it's old enough now, archive it" — time passing
    alone must never flip the gate's verdict.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)

    # Non-mutating probe (--check never writes) to discover the tool's own
    # computed eligibility date — avoids hand-computing dates in the test
    # (which would be timezone-fragile) by reading ground truth from the
    # tool itself.
    probe = _run_audit(repo, "--orphan-days", "90", "--check", "--json")
    stats = json.loads(probe.stdout)
    files = {f["path"]: f for f in stats["files"]}
    eligible_on = date.fromisoformat(files["docs/OLD_DOC.md"]["orphan_eligible_on"])
    assert not (repo / "docs" / "DOCS_INVENTORY.md").exists(), "--check must never write"

    # Baseline: the organ regenerated well BEFORE eligibility (60 days early).
    early_as_of = (eligible_on - timedelta(days=60)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", early_as_of, "--json")
    baseline = json.loads(result.stdout)
    files = {f["path"]: f for f in baseline["files"]}
    assert files["docs/OLD_DOC.md"]["status"] == "LIVE"
    assert files["docs/OLD_DOC.md"]["orphan_flipped_on"] is None

    # --check at the REAL current date: the doc is genuinely well past
    # eligibility by now, yet nothing about the TREE changed since the
    # baseline was committed. Must stay GREEN.
    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 0, (
        "innocent: --check must not flip a doc to ARCHIVED on its own just "
        f"because real time passed. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_check_immune_to_mocked_wallclock(tmp_path, monkeypatch):
    """INNOCENCE, strongest form ('testalo con date mockate'): monkeypatch
    datetime.now() to a wildly different date in-process and prove
    classify(as_of=None, ...) — the exact call shape main() uses for --check —
    is byte-identical on every gate-relevant field regardless. This is a
    structural proof, not a coincidence: as_of=None makes the time-crossing
    branch unreachable (see classify()'s docstring), so mocking "now" cannot
    possibly matter to it — this test would catch a future refactor that
    accidentally reintroduces a datetime.now() read into that branch.

    mtime_days is deliberately excluded from the equality check: it is
    cosmetic/wall-clock-relative BY DESIGN (compute_mtime_days docstring) and
    is masked by strip_volatile() before any real --check comparison (see
    test_check_ignores_mtime_days_drift) — it is ALLOWED, expected even, to
    differ here.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    doc = repo / "docs" / "OLD_DOC.md"

    row_real = docs_audit.classify(
        doc, repo, 90, [], [], {}, as_of=None, prev_flipped={}
    )

    real_datetime = docs_audit.datetime

    class _FrozenFarFuture(real_datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2099, 1, 1, tzinfo=tz)

    monkeypatch.setattr(docs_audit, "datetime", _FrozenFarFuture)
    row_mocked = docs_audit.classify(
        doc, repo, 90, [], [], {}, as_of=None, prev_flipped={}
    )

    assert row_real.status == row_mocked.status == "LIVE"
    assert row_real.last_touched_date == row_mocked.last_touched_date
    assert row_real.orphan_eligible_on == row_mocked.orphan_eligible_on
    assert row_real.orphan_flipped_on is None
    assert row_mocked.orphan_flipped_on is None
    assert row_real.action == row_mocked.action
    # The one field ALLOWED (expected) to differ:
    assert row_mocked.mtime_days != row_real.mtime_days


def test_p3prime_organ_flip_then_check_stays_green_carried_forward(tmp_path):
    """Positive/mechanism path: once a write-mode (organ) run flips a doc
    (as_of >= orphan_eligible_on), a LATER --check must reproduce that exact
    ARCHIVED status — proving carry-forward works, not just "check never
    archives anything". Also proves the flip is idempotent (a second organ
    run past the same eligibility does not re-flip / does not report a
    'flip this run' again) and that the stderr 'advanced N flip(s)' log line
    fires exactly once, on the run that actually crosses the threshold.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )

    # Baseline: organ ran before eligibility — not yet archived, no flip.
    early_as_of = (eligible_on - timedelta(days=60)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", early_as_of)

    # Organ runs again, now past eligibility — should flip exactly once.
    late_as_of = (eligible_on + timedelta(days=10)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", late_as_of, "--json")
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/OLD_DOC.md"]["status"] == "ARCHIVED"
    assert files["docs/OLD_DOC.md"]["orphan_flipped_on"] == late_as_of
    assert stats["flips_this_run"] == 1
    assert "docs/OLD_DOC.md" in stats["flipped_paths"]
    assert "docs_audit: advanced 1 flip(s)" in result.stderr

    # BLOCKER-2 (red-team 2026-07-18): --check reads flip provenance from
    # origin/main, never the working tree — the organ run above must be
    # committed+pushed before a LATER --check can see it as trusted.
    _commit_and_push(repo, "organ flip")

    # --check afterwards must be GREEN — the flip carries forward exactly.
    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 0, result.stdout + result.stderr

    # A SECOND organ run at an even later as_of must NOT re-flip: the date
    # stays pinned to the FIRST flip, and flips_this_run must read 0.
    later_as_of = (eligible_on + timedelta(days=60)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", later_as_of, "--json")
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/OLD_DOC.md"]["orphan_flipped_on"] == late_as_of  # unchanged
    assert stats["flips_this_run"] == 0
    assert "advanced" not in result.stderr


# ============================================================================
# Footgun fix (2026-07-19, PR #2626 landing incident): a write-mode regen run
# with NO --as-of silently defaulted to real "today" for the orphan
# time-crossing decision. scripts/docs_inventory_regen.sh's own plain-usage
# instructions (no --as-of — that flag is documented as a deterministic-
# testing/organ knob) meant a PR-side contributor's own regen could commit
# fresh orphan_flipped_on stamps that --check (always as_of=None) then
# rejected as drift ON THE SAME PR. Structural fix: --gate-consistent, a new
# write-mode opt-in that reproduces --check's exact computation (as_of=None,
# trusted-ref provenance) but WRITES the file. docs_inventory_regen.sh now
# passes it by default; the scheduled organ opts OUT via its own --organ
# flag (--as-of "$(date -u +%Y-%m-%d)").
#
#   GUILT     — a dated write-mode regen (the footgun shape) committed on a
#               branch fails --check (P3I)
#   INNOCENCE — a --gate-consistent regen committed on a branch passes
#               --check cleanly (P3J)
# ============================================================================


def test_p3prime_guilt_dated_regen_committed_on_branch_fails_check(tmp_path):
    """GUILT (footgun repro, PR #2626 2026-07-19): a write-mode regen using a
    dated --as-of (the shape docs_inventory_regen.sh's OLD default silently
    produced) advances a fresh orphan flip that origin/main's trusted
    provenance never recorded. If that content is committed directly (never
    pushed through the organ), a LATER --check on the same branch must
    correctly flag it as drift — this is the exact failure that caught PR
    #2626's own landing attempt, reproduced here as a permanent regression
    proof that --check WOULD catch it (and did).
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    # origin/main has NO flip recorded for this doc at all (no organ run in
    # this repo's history) — the dated regen below invents one from nothing.
    dated_as_of = (eligible_on + timedelta(days=10)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", dated_as_of)
    assert result.returncode == 1  # "content changed" — expected for a write mode
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    row = _row_cells(inventory, "docs/OLD_DOC.md")
    assert row[2].strip() == "ARCHIVED", "sanity: the footgun shape must actually invent a flip"

    # Commit the dated regen's output directly on this branch — WITHOUT
    # pushing to origin/main first (origin/main still has no flip recorded),
    # simulating "a contributor ran the dated/organ-mode regen locally and
    # committed its output on their feature branch".
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "dated regen (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: a dated flip absent from trusted origin/main provenance must "
        f"be flagged as drift. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_innocence_gate_consistent_regen_committed_on_branch_passes_check(
    tmp_path,
):
    """INNOCENCE (the actual fix): the SAME scenario as the guilt test above
    — a doc genuinely past its orphan-eligibility threshold, origin/main has
    no flip recorded for it — but the write-mode regen uses --gate-consistent
    instead of a dated --as-of. Must produce content byte-identical to what
    --check itself independently verifies, and committing it on a branch
    must pass --check cleanly. This is exactly what
    scripts/docs_inventory_regen.sh's new default invokes.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)

    # Write mode always returns 1 on content change (docs/DOCS_INVENTORY.md
    # doesn't exist yet — creating it IS a change, same documented contract
    # every other write-mode call in this file follows; see
    # test_p3prime_organ_flip_then_check_stays_green_carried_forward's own
    # baseline call a few tests above, which asserts nothing on this return
    # code for the identical reason). What matters is the CONTENT below, and
    # the --check call after commit+push.
    result = _run_audit(repo, "--orphan-days", "90", "--gate-consistent")
    assert result.returncode in (0, 1), (
        f"unexpected crash: {result.stdout}{result.stderr}"
    )
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    row = _row_cells(inventory, "docs/OLD_DOC.md")
    assert row[2].strip() == "LIVE", (
        "innocence: --gate-consistent must NOT invent a fresh flip just "
        "because the doc is genuinely old by real wall-clock"
    )
    assert row[6].strip() == "—"  # orphan_flipped_on column stays empty

    _commit_and_push(repo, "gate-consistent regen (innocent)")

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 0, (
        "innocence: a --gate-consistent regen committed on a branch must "
        f"pass --check cleanly. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_gate_consistent_ignores_forged_local_flip_uses_trusted_ref(tmp_path):
    """GUILT/mechanism proof (R1 red-team, PR #2863, 2026-07-20): the two
    tests above prove --gate-consistent's END-TO-END round-trip (write then
    --check) is green, but neither one distinguishes "provenance came from
    origin/main" from "provenance came from the local working tree" — in
    both, local and trusted happened to already agree before the write
    ran, so a --gate-consistent that had REGRESSED to
    parse_prev_flipped(old_content) (the local file, exactly what --check's
    own BLOCKER-2 fix forbids) instead of read_trusted_prev_flipped(...)
    would have passed those tests for the wrong reason.

    This test forces local and trusted to DISAGREE: origin/main records a
    genuine organ flip (ARCHIVED), then a candidate checkout hand-forges
    its OWN local docs/DOCS_INVENTORY.md to delete that flip (status LIVE,
    orphan_flipped_on cleared) — the identical forge shape as
    test_redteam_blocker2_forged_candidate_deletes_flip_caught_red, just
    exercised against --gate-consistent's WRITE path instead of --check's
    read-only path. If --gate-consistent honors read_trusted_prev_flipped()
    like it's supposed to, the freshly written inventory must reproduce the
    TRUSTED (ARCHIVED, real flip date) state, overwriting the local forgery
    — never render the forged LIVE state back out.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    late_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", late_as_of)
    _commit_and_push(repo, "organ flip")  # this becomes the TRUSTED main

    candidate = _clone_origin(repo, tmp_path / "candidate")
    inv_path = candidate / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inv_path.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"
    trusted_flip_date = cells[6].strip()
    assert trusted_flip_date != "—", "test setup sanity failed: no flip date recorded"

    # Forge the candidate's LOCAL working tree only (never pushed): flip
    # removed, status reset to LIVE — same shape as the BLOCKER-2 forgery
    # test, but this time the forged file is what --gate-consistent's WRITE
    # step will see as "old_content" if it (incorrectly) reads local state.
    cells[2] = " LIVE "
    cells[6] = " — "
    cells[11] = " — "
    forged_row = "|".join(cells)
    lines = inv_path.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_audit(candidate, "--orphan-days", "90", "--gate-consistent")
    assert result.returncode in (0, 1), (
        f"unexpected crash: {result.stdout}{result.stderr}"
    )
    rewritten = (candidate / "docs" / "DOCS_INVENTORY.md").read_text()
    row = _row_cells(rewritten, "docs/OLD_DOC.md")
    assert row[2].strip() == "ARCHIVED", (
        "--gate-consistent must reproduce the TRUSTED (origin/main) "
        "ARCHIVED state, not the locally-forged LIVE state — a regression "
        "to local-file provenance would silently resurrect the doc: "
        + rewritten
    )
    assert row[6].strip() == trusted_flip_date, (
        "--gate-consistent must reproduce origin/main's ORIGINAL flip "
        f"date ({trusted_flip_date!r}), not invent a new one or keep the "
        f"forged blank: got {row[6].strip()!r}"
    )


def test_p3prime_guilt_last_touched_date_inconsistent_with_git_history(tmp_path):
    """GUILT ('date incoerenti con la storia git -> rosso'): hand-mutating
    last_touched_date to a value that disagrees with the actual git commit
    history must trip --check. --check recomputes this fact fresh from `git
    log` on every run, so any stored value that disagrees with the tree is,
    by construction, real drift.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    _run_audit(repo, "--orphan-days", "90")  # baseline (real today, not eligible)

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    lines = inventory.read_text().splitlines()
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            true_date = date.fromisoformat(parts[4].strip())
            parts[4] = f" {(true_date - timedelta(days=7)).isoformat()} "
            line = "|".join(parts)
        mutated_lines.append(line)
    assert found, "fixture assumption broken — OLD_DOC.md row not found"
    inventory.write_text("\n".join(mutated_lines) + "\n")

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilty: last_touched_date disagreeing with git history must fail "
        f"--check. stdout={result.stdout}"
    )


def test_p3prime_guilt_orphan_eligible_on_inconsistent(tmp_path):
    """GUILT: mutating ONLY orphan_eligible_on (leaving last_touched_date
    correct) must ALSO trip --check — it is re-derived fresh as
    last_touched_date + orphan_days on every run, so a stored value
    disagreeing with that arithmetic is inconsistent with the tree.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    _run_audit(repo, "--orphan-days", "90")

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    lines = inventory.read_text().splitlines()
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            true_eligible = date.fromisoformat(parts[5].strip())
            parts[5] = f" {(true_eligible + timedelta(days=1)).isoformat()} "
            line = "|".join(parts)
        mutated_lines.append(line)
    assert found, "fixture assumption broken — OLD_DOC.md row not found"
    inventory.write_text("\n".join(mutated_lines) + "\n")

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1


def test_p3prime_guilt_status_archived_without_organ_flip(tmp_path):
    """GUILT ('un doc flippato senza passare dall'organo -> rosso'): a row
    hand-edited to STATUS=ARCHIVED with orphan-style action text, but with
    NO real orphan_flipped_on provenance marker, must fail --check — the flip
    provenance is missing/absent, so --check must not just trust the STATUS
    column at face value.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    # Baseline generated BEFORE eligibility — legitimately LIVE, no flip.
    early_as_of = (eligible_on - timedelta(days=60)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", early_as_of)

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    lines = inventory.read_text().splitlines()
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            assert parts[2].strip() == "LIVE", parts
            assert parts[6].strip() == "—", parts  # orphan_flipped_on untouched
            parts[2] = " ARCHIVED "  # hand-edit STATUS only
            parts[-2] = " archive: orphan, mtime=200d, refs=0 "  # and action text
            line = "|".join(parts)
        mutated_lines.append(line)
    assert found, "fixture assumption broken — OLD_DOC.md row not found"
    inventory.write_text("\n".join(mutated_lines) + "\n")

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilty: STATUS=ARCHIVED without a real orphan_flipped_on marker must "
        f"fail --check. stdout={result.stdout}"
    )


def test_p3prime_time_crossing_boundary_is_strict_matches_pre_existing_threshold(
    tmp_path,
):
    """Exact-day boundary regression: the pre-P3-prime rule was
    `mtime_days > orphan_days` (STRICT — a doc exactly `orphan_days` old was
    NOT yet orphaned, only STRICTLY older). The refactored time-crossing
    check (`as_of > orphan_eligible_on`) must reproduce that exactly, not
    `>=` — otherwise this change would silently move every doc's real-world
    archive date one calendar day earlier than before, an unintended drift
    outside P3-prime's stated scope (determinism, not threshold redefinition).
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )

    # AT eligible_on exactly: must NOT flip (strict `>`, not `>=`).
    result = _run_audit(
        repo, "--orphan-days", "90", "--as-of", eligible_on.isoformat(), "--json"
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/OLD_DOC.md"]["status"] == "LIVE", (
        "a doc exactly orphan_days old must NOT be archived yet — the "
        "pre-P3-prime rule was strictly-greater-than, not greater-or-equal"
    )
    assert stats["flips_this_run"] == 0

    # ONE DAY past eligible_on: must flip.
    one_day_later = (eligible_on + timedelta(days=1)).isoformat()
    result = _run_audit(
        repo, "--orphan-days", "90", "--as-of", one_day_later, "--json"
    )
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/OLD_DOC.md"]["status"] == "ARCHIVED"
    assert stats["flips_this_run"] == 1


def test_p3prime_check_and_as_of_are_mutually_exclusive(tmp_path):
    """--check + --as-of is a contradiction: the merge gate must be
    STRUCTURALLY incapable of being handed a wall-clock override — enforced
    at argparse time, not left to classify()'s internal branching alone.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    result = _run_audit(repo, "--check", "--as-of", "2026-01-01")
    assert result.returncode != 0
    assert "mutually exclusive" in (result.stderr + result.stdout)


def test_p3prime_as_of_rejects_bad_format(tmp_path):
    """--as-of must be YYYY-MM-DD; garbage input fails loud, not silently."""
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    result = _run_audit(repo, "--as-of", "not-a-date")
    assert result.returncode != 0
    assert "YYYY-MM-DD" in (result.stderr + result.stdout)


def test_p3prime_check_and_gate_consistent_are_mutually_exclusive(tmp_path):
    """--check + --gate-consistent is a contradiction: --check already IS the
    gate-consistent computation (as_of=None, trusted-ref provenance) — the
    combination is redundant-to-the-point-of-meaningless, refused at
    argparse time rather than silently accepted as a no-op alias.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    result = _run_audit(repo, "--check", "--gate-consistent")
    assert result.returncode != 0
    assert "mutually exclusive" in (result.stderr + result.stdout)


def test_p3prime_as_of_and_gate_consistent_are_mutually_exclusive(tmp_path):
    """--as-of + --gate-consistent is a contradiction: 'invent a flip from
    this specific date' and 'never invent one, carry forward from
    --trusted-ref' cannot both be the instruction for the same run.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=10)
    result = _run_audit(repo, "--as-of", "2026-01-01", "--gate-consistent")
    assert result.returncode != 0
    assert "mutually exclusive" in (result.stderr + result.stdout)


def test_p3prime_parse_prev_flipped_handles_missing_table(tmp_path):
    """parse_prev_flipped() must degrade to {} (never crash) on an empty or
    malformed table — the deliberately fail-closed bootstrap: no doc is
    archived-via-orphan until the organ has actually said so at least once.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    assert docs_audit.parse_prev_flipped("") == {}
    assert docs_audit.parse_prev_flipped("not a table at all\njust prose") == {}


def test_p3prime_flips_this_run_never_rendered_into_committed_inventory(tmp_path):
    """The 'N flips this run' count is deliberately EPHEMERAL/session-relative
    (stderr + --json only) and must NEVER be baked into docs/DOCS_INVENTORY.md
    itself. If it were, --check would compare a persisted "N flips happened
    THAT run" against a freshly-regenerated "0 flips happen during --check"
    (--check never flips) and flap red on every PR forever after any real
    organ flip — reintroducing exactly the instability P3-prime removes.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    late_as_of = (eligible_on + timedelta(days=10)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", late_as_of, "--json")
    stats = json.loads(result.stdout)
    assert stats["flips_this_run"] == 1  # sanity: a flip really happened

    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    # Precise phrase checks, NOT a bare "flip" substring ban — the per-doc
    # `orphan_flipped_on` PROVENANCE COLUMN is legitimate and expected to
    # appear (it's a stable, deterministic fact); what must never appear is
    # the session-relative COUNTER/log phrasing (a bare substring check here
    # would itself be the guard-over-match bug this repo's cicatrix rules
    # warn about — it would false-positive on "orphan_flipped_on").
    assert "flips_this_run" not in inventory, (
        "the ephemeral flip COUNTER leaked into the committed artifact — this "
        "would make --check unstable across runs (see docstring)."
    )
    assert "advanced" not in inventory.lower(), (
        "the stderr-only 'advanced N flip(s)' log phrasing leaked into the "
        "committed artifact."
    )
    assert "orphan_flipped_on" in inventory, (
        "sanity: the legitimate per-doc provenance column must still be present"
    )

    # BLOCKER-2 (red-team 2026-07-18): --check reads flip provenance from
    # origin/main, never the working tree — commit+push before checking.
    _commit_and_push(repo, "organ flip")

    # And the direct proof: --check right after a real flip must be green.
    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 0, result.stdout + result.stderr


# ============================================================================
# Red-team round 1 fixes (2026-07-18): PR #2626, io + Codex Sol xhigh,
# generator != grader. 4 BLOCKER + 4 MAJOR. MAJOR-8 (common-mode scheduler
# risk) is documentation + PENDING-ARMS only, no code, so no test here — see
# .github/workflows/docs-inventory-refresh-liveness.yml's header comment and
# .claude/skills/modus/PENDING-ARMS.md.
# ============================================================================


def _clone_origin(repo: Path, dest: Path) -> Path:
    """Clone `repo`'s own origin (wired by _init_git_repo) into `dest` — a
    genuine PR-candidate-style checkout, independent of `repo`'s own working
    tree, so a test can diverge the two exactly like a malicious/careless PR
    diff would.
    """
    origin_bare = repo.parent / f"{repo.name}-origin.git"
    subprocess.run(["git", "clone", "-q", str(origin_bare), str(dest)], check=True)
    return dest


def test_redteam_blocker2_forged_candidate_deletes_flip_caught_red(tmp_path):
    """GUILT (red-team 2026-07-18 BLOCKER-2, exact prescribed shape:
    "inventory del candidato falsificato (flip rimosso + status LIVE) ->
    check ROSSO"). A PR candidate hand-edits its OWN docs/DOCS_INVENTORY.md
    to delete an organ-flip (silently resurrecting an ARCHIVED doc to LIVE)
    — this is the exact gate-gameable shape: the candidate's own working
    tree is now perfectly SELF-consistent (a fresh regen sourcing provenance
    from that same tampered file would reproduce the forged LIVE state
    exactly — precisely how the pre-fix gate passed). --check must instead
    re-derive provenance from origin/main (still showing the REAL flip) and
    go RED.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    late_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", late_as_of)
    _commit_and_push(repo, "organ flip")  # this becomes the TRUSTED main

    candidate = _clone_origin(repo, tmp_path / "candidate")
    inv_path = candidate / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inv_path.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"

    # Forge: flip removed (column 6, orphan_flipped_on) + status set to LIVE
    # (column 2) — a PR author's hand-edit / bad merge-conflict resolution,
    # never touching the working tree's OLD_DOC.md itself.
    cells[2] = " LIVE "
    cells[6] = " — "
    cells[11] = " — "
    forged_row = "|".join(cells)
    lines = inv_path.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_audit(candidate, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "a candidate that forged its own inventory (flip deleted, status "
        "LIVE) must be caught RED by --check, not silently pass: "
        + result.stdout
        + result.stderr
    )
    assert "docs/OLD_DOC.md" in result.stderr


def test_redteam_blocker2_untampered_candidate_clone_stays_green(tmp_path):
    """INNOCENCE (BLOCKER-2 fix must not break the ordinary case): a PR
    candidate that clones the SAME trusted origin and changes NOTHING in
    docs/DOCS_INVENTORY.md must still pass --check cleanly — the
    trusted-ref read must reproduce exactly what's already on disk when
    nothing was forged.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    late_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", late_as_of)
    _commit_and_push(repo, "organ flip")

    candidate = _clone_origin(repo, tmp_path / "candidate")
    result = _run_audit(candidate, "--orphan-days", "90", "--check")
    assert result.returncode == 0, (
        "an untampered candidate clone must stay green: " + result.stdout + result.stderr
    )


def test_redteam_blocker2_unresolvable_trusted_ref_fails_closed(tmp_path):
    """FAIL-CLOSED (red-team 2026-07-18 BLOCKER-2, explicit requirement:
    "base illeggibile -> errore esplicito, non pass silenzioso"). A real git
    repo whose `origin` remote cannot be resolved (removed/misconfigured)
    must NOT silently treat --check as if there were no prior state (which
    would let Rule 2 fall through and resurrect any already-organ-archived
    doc) — it must fail LOUD and distinctly (exit 2, "could not determine"),
    never exit 0 or 1.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    subprocess.run(["git", "remote", "remove", "origin"], cwd=repo, check=True)

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 2, (
        f"an unresolvable trusted ref must exit 2 (could-not-determine), "
        f"not silently pass or report ordinary drift: got {result.returncode}, "
        + result.stdout
        + result.stderr
    )
    assert "trusted ref" in (result.stdout + result.stderr).lower()


def test_redteam_major5_doc_touched_after_flip_resurrects_to_live(tmp_path):
    """INNOCENCE (red-team 2026-07-18 MAJOR-5, exact prescribed shape: "doc
    toccato post-flip -> LIVE"). A doc archived via a genuine organ flip,
    then RE-TOUCHED (edited + re-committed) after that flip date, must not
    stay ARCHIVED forever on a stale provenance marker: last_touched_date
    moving past orphan_flipped_on invalidates the carried flip (pure tree
    fact, zero wall-clock — the comparison uses only already-computed
    dates), and the doc falls through to LIVE based on current tree state
    (still zero inbound refs here).
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    flip_as_of = (eligible_on + timedelta(days=10)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", flip_as_of, "--json")
    stats = json.loads(result.stdout)
    files = {f["path"]: f for f in stats["files"]}
    assert files["docs/OLD_DOC.md"]["status"] == "ARCHIVED"  # sanity
    _commit_and_push(repo, "organ flip")

    # Re-touch the doc AFTER the flip date, with a LATER commit date
    # (compute_last_commit_date reads git log, so the backdate matters).
    doc = repo / "docs" / "OLD_DOC.md"
    doc.write_text(doc.read_text() + "\nEdited after archival.\n", encoding="utf-8")
    touch_date = (date.fromisoformat(flip_as_of) + timedelta(days=5)).isoformat()
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": f"{touch_date}T00:00:00",
        "GIT_COMMITTER_DATE": f"{touch_date}T00:00:00",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "edit after archival", "--date", env["GIT_AUTHOR_DATE"]],
        cwd=repo,
        check=True,
        env=env,
    )
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=repo, check=True, env=env)

    # --check (as_of=None, no wall-clock at all) must independently resurrect
    # the doc to LIVE purely from tree facts (last_touched > carried flip).
    result = _run_audit(repo, "--orphan-days", "90", "--check", "--json")
    stats2 = json.loads(result.stdout)
    files2 = {f["path"]: f for f in stats2["files"]}
    assert files2["docs/OLD_DOC.md"]["status"] == "LIVE", (
        f"a doc touched after its flip must resurrect to LIVE under --check: "
        f"{files2['docs/OLD_DOC.md']}"
    )
    assert files2["docs/OLD_DOC.md"]["orphan_flipped_on"] is None


def test_redteam_major7_pipe_in_doc_path_rejected_loud(tmp_path):
    """GUILT (red-team 2026-07-18 MAJOR-7, exact prescribed shape:
    "roundtrip test with docs/a|b.md"). A doc path containing a literal '|'
    would corrupt the Markdown table (an extra cell) and silently vanish
    from the NEXT parse (_parse_inventory_table's cell-count guard drops
    mismatched rows) — permanently red for that doc thereafter, since its
    orphan-flip provenance can never again be carried forward. Refused LOUD
    at generation instead: docs_audit.py must exit non-zero with a clear
    message naming the offending path, and critically must never write
    docs/DOCS_INVENTORY.md at all in that run (no half-corrupted table).
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "a|b.md").write_text("# Pipe path\n", encoding="utf-8")
    _init_git_repo(repo)

    result = _run_audit(repo, "--orphan-days", "90")
    assert result.returncode != 0, "a doc path containing '|' must be refused"
    assert "a|b.md" in (result.stdout + result.stderr)
    assert not (repo / "docs" / "DOCS_INVENTORY.md").exists(), (
        "no inventory file should be written when generation is refused"
    )


def test_redteam_major7_normal_paths_render_unaffected(tmp_path):
    """INNOCENCE: the MAJOR-7 guard must not trip on ordinary doc paths
    (none of which legitimately contain '|')."""
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=1)
    result = _run_audit(repo, "--orphan-days", "90")
    assert result.returncode in (0, 1)  # normal write-mode outcomes only
    assert (repo / "docs" / "DOCS_INVENTORY.md").exists()


def _load_docs_audit_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location("docs_audit", AUDIT_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_redteam_blocker3_crash_maps_to_exit_2():
    """GUILT (red-team 2026-07-18 BLOCKER-3, Python half): a genuine
    uncaught exception must map to exit 2 — a code main() itself never
    returns — so a caller distinguishing "1 = expected drift" from "2 =
    crashed" (scripts/docs_inventory_regen.sh, same red-team round) can
    actually tell them apart.
    """
    docs_audit = _load_docs_audit_module()

    def _boom():
        raise RuntimeError("synthetic crash for BLOCKER-3 test")

    rc = docs_audit._run_and_map_exit_code(_boom)
    assert rc == 2


def test_redteam_blocker3_normal_returns_pass_through_unmapped():
    """INNOCENCE: main()'s own ordinary 0/1 return values must pass through
    _run_and_map_exit_code unchanged — the crash-boundary must not remap
    codes main() itself legitimately returns."""
    docs_audit = _load_docs_audit_module()
    assert docs_audit._run_and_map_exit_code(lambda: 0) == 0
    assert docs_audit._run_and_map_exit_code(lambda: 1) == 1


def test_redteam_blocker3_systemexit_reraised_unchanged():
    """INNOCENCE: a deliberate SystemExit (parse_args()'s usage-error path,
    e.g. a malformed --cluster spec) must propagate UNCHANGED — never
    remapped to exit 2, which would hide a clear usage-error message behind
    a generic 'CRASHED' one."""
    docs_audit = _load_docs_audit_module()

    def _usage_error():
        raise SystemExit("bad args, deliberately")

    with pytest.raises(SystemExit, match="bad args, deliberately"):
        docs_audit._run_and_map_exit_code(_usage_error)
