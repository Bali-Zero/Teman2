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
    # Legacy behavioral tests intentionally exercise the historical tracked
    # path. Production callers use docs_audit.py's new artifact-only default.
    cmd = [
        sys.executable,
        str(AUDIT_SCRIPT),
        "--repo",
        str(repo),
        "--output",
        "docs/DOCS_INVENTORY.md",
        *args,
    ]
    return subprocess.run(cmd, capture_output=True, text=True)


def _col(inventory_text: str, name: str) -> int:
    """Index into `line.split("|")` for the inventory column called `name`.

    Resolved from the rendered header, never hardcoded. The tests below hand-
    edit individual cells to manufacture guilt, and they used to address them
    by literal index. When #3405's churn fix removed the `mtime_days` column,
    every one of those indices silently pointed one cell to the left. Three of
    them happened to fail loudly (`date.fromisoformat('—')`); the rest would
    have quietly asserted about the wrong column — a guilt test that mutates
    the wrong cell still goes red, for the wrong reason, and an innocence test
    that reads the wrong cell can go green while the property it names is
    broken.

    `split("|")` on `| a | b |` yields ['', ' a ', ' b ', ''], so the header's
    Nth column is index N+1.
    """
    header = next(
        ln for ln in inventory_text.splitlines() if ln.startswith("| File | Status |")
    )
    names = [h.strip() for h in header.strip().strip("|").split("|")]
    assert name in names, f"column {name!r} is not in the inventory header: {names}"
    return names.index(name) + 1


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
    assert "docs_audit: generated output differs from" in result.stderr
    assert "--- committed/" in result.stderr
    assert "+++ generated/" in result.stderr


def test_the_inventory_has_no_clock_derived_cell_for_a_day_to_change(aged_fixture):
    """END-TO-END: a day passing cannot move this file, because nothing in it
    is derived from the clock.

    HISTORY, and why this test was rewritten rather than left alone. It used to
    be `test_check_ignores_mtime_days_drift`: it hand-incremented every
    `mtime_days` cell and asserted `--check` still exited 0, protecting the
    2026-05-01 / PR #401 incident where a 1-day drift on every row failed
    `inventory-check` for PRs that had changed nothing.

    That protection was masking, and masking only silenced the GATE. The FILE
    still changed every day, which is the half that hurt: measured on #3405,
    633 of 699 changed rows (90.6%) differed ONLY in that integer, the
    twice-daily refresh opened a churn PR on every run because it decides with
    `git diff --quiet` on the raw file, and any two branches that regenerated
    collided on those 633 lines.

    The column is now gone (render_inventory emits absolute `last_touched_date`
    instead), so the old body had nothing left to increment: its loop looked for
    a `mtime_days` header, never found one, mutated nothing, and asserted that
    an unmodified file passes `--check`. It PASSED, vacuously, and would have
    kept passing if the cure were reverted. A test that can no longer fail is
    worse than no test — it reports coverage it does not have.

    So the assertion is now the stronger, source-level one, still driven
    end-to-end through the real script.
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
    inventory = aged_fixture / "docs" / "DOCS_INVENTORY.md"
    text = inventory.read_text()

    # NON-VACUITY FIRST. Everything below is "X is absent", and an empty or
    # table-less file satisfies all of it. This is the exact trap the previous
    # version of this test fell into.
    header = [ln for ln in text.splitlines() if ln.startswith("| File | Status |")]
    assert len(header) == 1, f"expected exactly one file-table header, got {len(header)}"
    doc_rows = [ln for ln in text.splitlines() if ln.startswith("| docs/")]
    assert doc_rows, "no doc rows in the generated table — the assertions below would be vacuous"

    # No cell may be an AGE. Absolute dates are fine (a date is a tree fact and
    # does not change on its own); a days-ago count is not.
    ages = re.findall(r"mtime=\d+d|\(mtime[^)]*\)|\b\d+ days ago\b", text)
    assert not ages, (
        f"the inventory renders age tokens {ages[:5]} — these increment daily "
        "and are what made this generated-but-tracked file rewrite itself "
        "nightly (#3405: 633/699 rows changed by nothing but the clock)"
    )
    assert "mtime_days" not in header[0], (
        "the mtime_days column is back in the table header. It is redundant "
        "with last_touched_date beside it, and it is the churn source."
    )

    # And the gate agrees with the file it just wrote.
    result = _run_audit(aged_fixture, *common, "--check")
    assert result.returncode == 0, result.stdout + result.stderr

    # Regeneration is idempotent: a second write must not move a byte.
    _run_audit(aged_fixture, *common)
    assert inventory.read_text() == text, "regenerating twice produced different bytes"


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


# The column order every `cells[N]` index in this file is written against.
# `split("|")` on `| a | b |` yields ['', ' a ', ' b ', ''], so column K here is
# index K+1 there:
#   1=File  2=Status  3=last_touched_date  4=orphan_eligible_on
#   5=orphan_flipped_on  6=refs_in  7=broken  8=drift  9=cluster  10=action
_EXPECTED_LAYOUT = [
    "File",
    "Status",
    "last_touched_date",
    "orphan_eligible_on",
    "orphan_flipped_on",
    "refs_in",
    "broken",
    "drift",
    "cluster",
    "action",
]


def _row_cells(inventory_text: str, path: str) -> list[str]:
    """Split the `## Files` table row for `path` into raw `|`-delimited cells
    (including the leading/trailing empty strings from split), so a test can
    mutate a SPECIFIC column by index without hand-building a whole row.

    Every caller addresses cells by literal index, and ~20 of them do. When
    #3405's churn fix removed the `mtime_days` column, every one of those
    indices silently pointed one cell to the left: a guilt test forged the
    wrong column (red for the wrong reason), and an innocence test read the
    wrong column (green while the property it names was untested). Only the
    two that happened to feed `date.fromisoformat()` failed loudly.

    So the layout is asserted HERE, once, instead of being re-derived at
    twenty call sites: the next column change fails immediately with the two
    layouts printed side by side, rather than producing twenty quiet lies.
    """
    header = next(
        (ln for ln in inventory_text.splitlines() if ln.startswith("| File | Status |")),
        None,
    )
    assert header is not None, f"no file-table header in inventory:\n{inventory_text[:400]}"
    names = [h.strip() for h in header.strip().strip("|").split("|")]
    assert names == _EXPECTED_LAYOUT, (
        "the inventory column layout changed, so every cells[N] index in this "
        "file now addresses the wrong column.\n"
        f"  expected: {_EXPECTED_LAYOUT}\n"
        f"  rendered: {names}\n"
        "Update _EXPECTED_LAYOUT *and* the indices together — a silent shift "
        "here is how a guilt test starts forging the wrong cell."
    )
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


def test_p3prime_1a_innocence_earned_unlanded_flip_passes_check(tmp_path):
    """INNOCENCE (option 1a-surgical, 2026-07-25 — this is the ENTIRE POINT
    of the change). Originally this test was named
    `test_p3prime_guilt_dated_regen_committed_on_branch_fails_check` and
    asserted returncode == 1 for exactly this shape: a write-mode regen using
    a dated --as-of advances a fresh orphan flip that origin/main's trusted
    provenance never recorded, committed directly on a branch without going
    through the organ. That was the correct, and only possible, verdict from
    2026-07-19 (PR #2626 footgun repro) through 2026-07-24: --check had no
    way to distinguish "a genuinely earned, plausible new flip" from
    forgery, so it rejected EVERY unlanded flip categorically — including
    honest ones. PR #3126 (2026-07-25) hit exactly this wall running the
    organ's own sanctioned `--organ` regen path: structurally legitimate,
    provably not forgery, and still red, because rejection was categorical
    rather than evidence-based (see
    research/operations/2026-07-25-docs-inventory-check-blocker2-structural-cure.md).

    The surgical fix (`_tolerated_orphan_flip_paths` in docs_audit.py) makes
    --check evidence-based instead: a claimed flip is tolerated ONLY when (1)
    trusted-ref has no entry for the path (so nothing is being hidden or
    resurrected), (2) the doc is structurally eligible right now (refs_in==0,
    freshly computed — never trust the committed claim), (3) the claimed
    orphan_flipped_on is bounded on BOTH sides — not before orphan_eligible_on
    (not premature) and not after the PR's own inventory-commit date (not
    future-dated), and (4) the committed refs_in claim agrees with reality.
    This exact scenario satisfies all four, so it must now PASS. Both forgery
    directions this could have reopened remain independently guarded and
    tested — see the test_p3prime_1a_guilt_* family below, plus the
    pre-existing test_redteam_blocker2_* family (unaffected: trusted-ref HAS
    an entry there, so tolerance condition 1 excludes them by construction).
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    # origin/main has NO flip recorded for this doc at all (no organ run in
    # this repo's history) — the dated regen below invents one from nothing,
    # but plausibly: the claimed date is well past eligibility and nothing
    # is being hidden.
    dated_as_of = (eligible_on + timedelta(days=10)).isoformat()
    result = _run_audit(repo, "--orphan-days", "90", "--as-of", dated_as_of)
    assert result.returncode == 1  # "content changed" — expected for a write mode
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    row = _row_cells(inventory, "docs/OLD_DOC.md")
    assert row[2].strip() == "ARCHIVED", "sanity: the shape must actually produce a flip"

    # Commit the dated regen's output directly on this branch — WITHOUT
    # pushing to origin/main first (origin/main still has no flip recorded),
    # simulating "a contributor ran the organ/dated-mode regen locally and
    # committed its output on their feature branch" — the exact PR #3126
    # shape.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "dated regen (earned, unlanded)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 0, (
        "innocent: a genuinely-earned, date-bounded, non-hiding orphan flip "
        "absent only because the organ hasn't landed it yet must be "
        f"tolerated by --check. stdout={result.stdout} stderr={result.stderr}"
    )


# ============================================================================
# option 1a-surgical guilt family (2026-07-25, cross-family red-team on the
# design before any code landed — 3 refinements, each with its own guilt
# test below): tolerance for an unlanded orphan flip must NOT reopen either
# BLOCKER-2 forgery direction. See _tolerated_orphan_flip_paths()'s 4-way
# gate in docs_audit.py. Guilt tests here prove each gate condition is load-
# bearing BY ITSELF — every scenario below satisfies every OTHER condition
# and violates exactly one.
# ============================================================================


def test_p3prime_1a_guilt_premature_flip_claim_rejected(tmp_path):
    """GUILT (option-1a-surgical, BLOCKER-2 direction (a) — premature-
    archival forgery): a PR claims an orphan flip with a plausible-looking
    STATUS=ARCHIVED + action text, but the claimed orphan_flipped_on
    predates the doc's own orphan_eligible_on — i.e. it claims the doc was
    archived before it was even structurally eligible to be. Tolerance
    requires `orphan_eligible_on <= claimed_flipped_on`; this claim violates
    that lower bound, so --check must still reject it even though
    trusted-ref (origin/main) has no entry for this doc at all — which is
    otherwise the condition that makes tolerance available in the first
    place.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    # A genuinely-shaped dated regen (structurally valid on its own) —
    # produces ARCHIVED with orphan_flipped_on = eligible_on + 10.
    dated_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", dated_as_of)

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inventory.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"
    premature = (eligible_on - timedelta(days=5)).isoformat()
    cells[5] = f" {premature} "  # forge: claimed flip predates eligibility
    forged_row = "|".join(cells)
    lines = inventory.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "premature flip claim (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: a claimed orphan_flipped_on before orphan_eligible_on must "
        f"never be tolerated. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_1a_guilt_future_dated_flip_claim_rejected_refinement1(tmp_path):
    """GUILT (option-1a-surgical, Refinement 1 — restore the upper bound on
    the claimed flip date): a claimed orphan_flipped_on set to a wildly
    future date (well past the PR's own inventory-commit date) must be
    rejected even though it is >= orphan_eligible_on. Without this upper
    bound, a PR could claim ANY future date (e.g. 2099-01-01) and slip
    through tolerance on the lower-bound check alone — this is exactly the
    gap the first surgical draft left open before red-team review caught it.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    dated_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", dated_as_of)

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inventory.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"
    cells[5] = " 2099-01-01 "  # wildly future — past any real commit date
    forged_row = "|".join(cells)
    lines = inventory.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "future-dated flip claim (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: a claimed orphan_flipped_on after the PR's own inventory "
        f"commit date must never be tolerated. stdout={result.stdout} "
        f"stderr={result.stderr}"
    )


def test_p3prime_1a_guilt_refs_in_nonzero_forged_archive_rejected_refinement2(
    tmp_path,
):
    """GUILT (option-1a-surgical, Refinement 2 — orphan_eligible_on must be
    present, non-empty, and already past, BY CONSTRUCTION): a doc with a REAL
    inbound reference (refs_in > 0, computed FRESH from the current tree —
    such a doc is never an orphan candidate in the first place, so its own
    orphan_eligible_on stays empty) has its committed row hand-forged to
    STATUS=ARCHIVED with a plausible-looking orphan_flipped_on AND a lying
    refs_in="0" claim in the committed table. Tolerance must never engage for
    a doc that isn't structurally eligible — this is what stops a doc from
    sliding through on a forged claim just because the other 3 conditions
    happen to look satisfiable, and it must be checked against the FRESH
    recomputed refs_in, never the candidate's own claimed value (that's
    Refinement 3's job, tested separately below).
    """
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "OLD_DOC.md").write_text(
        "# Old doc\n\nReferenced by REFERRER.md.\n", encoding="utf-8"
    )
    # A REAL markdown link, not a bare prose mention: refs_in is now
    # reference-anchored (compute_refs_in / _has_bare_delimited_mention,
    # docs_audit.py) rather than a `basename in text` substring scan, so a
    # bare "See OLD_DOC.md for details." no longer counts as an inbound
    # reference — the guilt this test exists to prove requires a doc that
    # genuinely IS referenced.
    (repo / "docs" / "REFERRER.md").write_text(
        "# Referrer\n\nSee [OLD_DOC.md](OLD_DOC.md) for details.\n", encoding="utf-8"
    )
    _init_git_repo(repo, backdate_days=200)

    result = _run_audit(repo, "--orphan-days", "90", "--regen-only")
    assert result.returncode in (0, 1), result.stderr
    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inventory.read_text(), "docs/OLD_DOC.md")
    assert cells[6].strip() != "0", (
        "test setup sanity failed: OLD_DOC.md must have a real inbound "
        f"reference from REFERRER.md — refs_in cell: {cells}"
    )
    # Forge: STATUS=ARCHIVED, a plausible flip date, action text, AND lie
    # about refs_in in the committed table (claim 0 despite the real
    # inbound reference) — refinement 2 must catch this on the FRESH
    # (recomputed) refs_in, not the candidate's own claimed value.
    plausible_flip = (date.today() - timedelta(days=1)).isoformat()
    cells[2] = " ARCHIVED "
    cells[5] = f" {plausible_flip} "
    cells[6] = " 0 "
    cells[10] = " archive: orphan, last_touched=2026-01-01, refs=0 "
    forged_row = "|".join(cells)
    lines = inventory.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "forged archive on referenced doc (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: a doc with real inbound references must never be tolerated "
        f"into ARCHIVED. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_1a_guilt_row_deletion_hides_flip_still_rejected_refinement3(
    tmp_path,
):
    """GUILT (option-1a-surgical, Refinement 3 — verify row-SET equality on
    disk, direction: deletion). A PR candidate deletes the ENTIRE row for an
    already-organ-flipped doc from its own docs/DOCS_INVENTORY.md (rather
    than editing its fields, as
    test_redteam_blocker2_forged_candidate_deletes_flip_caught_red does) —
    hiding the flip by omission instead of falsification. The tolerant gate
    must still catch this: the freshly-regenerated table (which always
    includes every real doc, tolerated or not) will contain a row the
    candidate's own committed table is missing, so the whole-table string
    comparison must still differ regardless of any per-path tolerance logic
    — tolerance only ever MASKS specific columns of a row that's present in
    both sides, it never manufactures a missing row's absence into a match.
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
    _commit_and_push(repo, "organ flip")  # trusted main now has the flip

    candidate = _clone_origin(repo, tmp_path / "candidate")
    inv_path = candidate / "docs" / "DOCS_INVENTORY.md"
    lines = inv_path.read_text().splitlines()
    before_len = len(lines)
    lines = [line for line in lines if not line.startswith("| docs/OLD_DOC.md |")]
    assert len(lines) == before_len - 1, "test setup sanity failed: row not removed"
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_audit(candidate, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: deleting a row to hide an already-flipped doc must still be "
        f"caught red. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_1a_guilt_fabricated_row_for_nonexistent_path_rejected_refinement3(
    tmp_path,
):
    """GUILT (option-1a-surgical, Refinement 3 — verify row-SET equality on
    disk, direction: addition). A PR candidate APPENDS a fabricated row for a
    path that does not exist on disk at all — classify() never walks it, so
    the freshly-regenerated table never mentions it — while the candidate's
    own committed table claims it as a plausible-looking, structurally
    eligible, date-bounded ARCHIVED orphan flip (every condition an attacker
    might try to satisfy at once). Tolerance operates on paths present in the
    FRESH classify() output (see `_tolerated_orphan_flip_paths` iterating
    `rows`, never the committed table alone) — a phantom row for a
    nonexistent file can never be a member of that set, so the whole-table
    string comparison must still catch the extra line and go red.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    result = _run_audit(repo, "--orphan-days", "90", "--regen-only")
    assert result.returncode in (0, 1), result.stderr

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    lines = inventory.read_text().splitlines()
    real_row = next(
        line for line in lines if line.startswith("| docs/OLD_DOC.md |")
    )
    cells = real_row.split("|")
    cells[1] = " docs/GHOST_DOC.md "  # path that never existed on disk
    cells[2] = " ARCHIVED "
    cells[4] = f" {(date.today() - timedelta(days=91)).isoformat()} "  # eligible_on
    cells[5] = f" {(date.today() - timedelta(days=1)).isoformat()} "  # flipped_on
    cells[6] = " 0 "
    cells[10] = " archive: orphan, last_touched=2026-01-01, refs=0 "
    fabricated_row = "|".join(cells)
    lines.append(fabricated_row)
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "fabricated row for nonexistent path (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: a fabricated row for a path that does not exist on disk must "
        f"still be caught red. stdout={result.stdout} stderr={result.stderr}"
    )


# ============================================================================
# Cross-family red-team round 2 (Kimi K3, 2026-07-25) against the FIRST
# version of option 1a-surgical above. Verdict: FAIL. One real bypass
# (Finding 1, fixed by anchoring the upper bound to max(trusted-ref-tip,
# real "now") instead of the PR's own commit metadata) plus two test-
# integrity gaps proven by live mutation (Findings 2 and 3 — the shipped
# CODE was already correct on both, only the TEST COVERAGE was thin).
# Tests below close all three permanently.
# ============================================================================


def test_p3prime_1a_guilt_forged_committer_date_cannot_defeat_ceiling_refinement1(
    tmp_path,
):
    """GUILT (Finding 1 — the real bypass, Kimi K3, 2026-07-25). The FIRST
    version of Refinement 1's upper bound was anchored to
    `compute_last_commit_date(repo, inventory_path)` — `git log -1
    --format=%ct` against the PR's OWN checked-out branch. `GIT_COMMITTER_
    DATE` is fully attacker-controlled, so a PR could forge BOTH the
    claimed `orphan_flipped_on` and the commit's own committer date to the
    same far-future value. Demonstrated live: claim
    `orphan_flipped_on=2099-01-01`, commit the forged inventory with
    `GIT_COMMITTER_DATE=2099-06-01` (comfortably after the claim) —
    `--check` went GREEN outright, and Kimi chained the harm further:
    after "merge" (push to origin), the 2099 flip became trusted
    provenance, and an honest edit with a REAL 2026-07-25 commit date did
    NOT resurrect the doc — `_flip_is_still_valid()` has no upper bound,
    so the forged flip pinned the doc ARCHIVED for 73 years, immune to
    MAJOR-5's resurrection guarantee, with the organ's `--apply` ready to
    physically `git mv` an actively-edited doc into `docs/archive/` on the
    strength of it.

    The fix anchors the ceiling to `max(trusted-ref-tip-date, real "now"
    at check-time)` instead — see `main()`'s comment block above
    `_tolerated_orphan_flip_paths(...)` for why using real "now" here does
    NOT reintroduce the wall-clock dependence P3-prime eliminates (it is
    monotonic-safe: a claim already `<= now` stays tolerated forever as
    real time advances, and this can only ever turn a rejection into a
    tolerance later — never the reverse, which is the only direction
    P3-prime actually forbids). This test reproduces Kimi's exact exploit
    shape and proves it is now rejected: the PR's own committer date on
    its own commit no longer has ANY influence on the ceiling at all.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    probe = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    eligible_on = date.fromisoformat(
        {f["path"]: f for f in probe["files"]}["docs/OLD_DOC.md"]["orphan_eligible_on"]
    )
    dated_as_of = (eligible_on + timedelta(days=10)).isoformat()
    _run_audit(repo, "--orphan-days", "90", "--as-of", dated_as_of)

    inventory = repo / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inventory.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"
    cells[5] = " 2099-01-01 "  # the far-future claim refinement 1 names as its example
    forged_row = "|".join(cells)
    lines = inventory.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inventory.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # The exploit itself: forge the COMMIT's own committer/author date to
    # comfortably exceed the claim — this is what defeated the FIRST
    # version of the upper bound. Explicit UTC offset (not bare
    # "2099-01-01T00:00:00") — Kimi's first attempt without one landed on
    # 2098-12-31 after local-tz conversion, which is a fixture-precision
    # footgun, not evidence the bound holds; being explicit here avoids it.
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "T",
        "GIT_AUTHOR_EMAIL": "t@t",
        "GIT_COMMITTER_NAME": "T",
        "GIT_COMMITTER_EMAIL": "t@t",
        "GIT_AUTHOR_DATE": "2099-06-01T00:00:00+00:00",
        "GIT_COMMITTER_DATE": "2099-06-01T00:00:00+00:00",
    }
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, env=env)
    subprocess.run(
        ["git", "commit", "-q", "-m", "forged committer date (guilty)"],
        cwd=repo,
        check=True,
        env=env,
    )

    result = _run_audit(repo, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: forging the commit's OWN committer date must not defeat "
        "the upper bound — the ceiling must be anchored to something the "
        f"PR branch does not control. stdout={result.stdout} stderr={result.stderr}"
    )

    # Team-lead (2026-07-25, endorsing the fix): asserting only --check's
    # exit code proves the GATE is red, not that the HARM is blocked — the
    # same shape as Finding 2, where a test measured a correlated proxy
    # instead of the thing it named. The actual damage Kimi chained was two
    # steps past the gate: the doc gets pinned ARCHIVED, and --apply
    # physically moves it. Assert both directly, on this SAME forged tree.
    #
    # (1) The gate's OWN fresh computation (the --json payload, built from
    # `rows` — the STRICT, non-tolerant classify() output) must show the
    # doc as LIVE, not just report a nonzero exit code that some OTHER
    # unrelated mismatch could also have produced.
    probe_after_forgery = json.loads(
        _run_audit(repo, "--orphan-days", "90", "--check", "--json").stdout
    )
    fresh_status = {f["path"]: f for f in probe_after_forgery["files"]}[
        "docs/OLD_DOC.md"
    ]["status"]
    assert fresh_status == "LIVE", (
        "the fresh (non-tolerant) computation must show the doc LIVE even "
        f"with the forged claim sitting in the committed table, got {fresh_status!r}"
    )

    # (2) --apply must leave the file exactly where it is. Use
    # --gate-consistent (not plain --apply): plain write-mode trusts the
    # LOCAL working tree's own content by design (parse_prev_flipped on
    # old_content) — that trust model assumes the caller is always the
    # organ's own fresh checkout of trusted main, never a hostile forged
    # branch, so plain --apply on THIS tree would be fooled by design, not
    # by a bug in this fix. --gate-consistent is the write-mode twin that
    # re-derives provenance from trusted-ref instead (the same safe source
    # --check itself uses) — this is the actually-safe write path, and the
    # one docs_inventory_regen.sh uses by default.
    result = _run_audit(repo, "--orphan-days", "90", "--gate-consistent", "--apply")
    assert (repo / "docs" / "OLD_DOC.md").exists(), (
        "--gate-consistent --apply must leave the doc at its original path — "
        f"a forged claim must never cause a physical git mv. stdout={result.stdout} "
        f"stderr={result.stderr}"
    )
    assert not list((repo / "docs" / "archive").rglob("OLD_DOC.md")), (
        "the doc must not have been archived under docs/archive/ on the "
        "strength of the forged claim"
    )


def test_p3prime_1a_guilt_date_creep_on_recorded_flip_rejected(tmp_path):
    """GUILT (Finding 3 — real coverage gap on EXISTING logic, Kimi K3,
    2026-07-25). Condition 1 (`r.path in prev_flipped: continue`) is the
    ONLY defense against "date-creep" on an already-recorded flip: a PR
    that leaves a trusted flip in place but nudges its claimed date a few
    days later — still in-window (>= orphan_eligible_on, <= the ceiling),
    nothing deleted, nothing future-dated relative to real time. The
    pre-existing BLOCKER-2 family only tests flip DELETION (cell -> "—"),
    caught by the `claimed_raw in ("", "—")` skip plus the strict diff —
    never by condition 1 itself. Kimi proved this gap by live mutation:
    removing conditions 1+2 together left ALL 10 pre-existing + new
    p3prime tests green, so no test in the suite would notice condition
    1's removal; a dedicated date-creep repro then confirmed mutated=green
    (creep tolerated), restored=red (blocked) — condition 1 is genuinely
    load-bearing, just untested until now. This test closes that gap.
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
    _commit_and_push(repo, "organ flip")  # trusted main now records flip = late_as_of

    candidate = _clone_origin(repo, tmp_path / "candidate")
    inv_path = candidate / "docs" / "DOCS_INVENTORY.md"
    cells = _row_cells(inv_path.read_text(), "docs/OLD_DOC.md")
    assert cells[2].strip() == "ARCHIVED", f"test setup sanity failed: {cells}"
    assert cells[5].strip() == late_as_of, "test setup sanity failed: unexpected flip date"

    # Nudge the RECORDED flip's date forward 5 days — still in-window
    # (>= eligible_on, <= real today), row still present, refs_in claim
    # untouched. Only condition 1 (trusted-ref already has this path) can
    # catch this — every other condition is satisfied by construction.
    crept = (date.fromisoformat(late_as_of) + timedelta(days=5)).isoformat()
    cells[5] = f" {crept} "
    forged_row = "|".join(cells)
    lines = inv_path.read_text().splitlines()
    lines = [
        forged_row if line.startswith("| docs/OLD_DOC.md |") else line
        for line in lines
    ]
    inv_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    result = _run_audit(candidate, "--orphan-days", "90", "--check")
    assert result.returncode == 1, (
        "guilt: nudging an ALREADY-recorded flip's date forward, in-window, "
        "without deleting it, must still be rejected — trusted-ref's own "
        f"record must be untouchable. stdout={result.stdout} stderr={result.stderr}"
    )


def test_p3prime_1a_unit_tolerated_paths_excludes_refs_in_nonzero_refinement2(
    tmp_path,
):
    """UNIT (Finding 2 — test vacuity, Kimi K3, 2026-07-25). The CLI-level
    guilt test for refinement 2
    (`test_p3prime_1a_guilt_refs_in_nonzero_forged_archive_rejected_refinement2`)
    passes even with condition 2 deleted from `_tolerated_orphan_flip_paths`
    — proven by live mutation. The red verdict in that scenario actually
    comes from `classify()`'s own structural gate independently
    backstopping in the tolerant re-render (a referenced doc's carry-
    forward branch never fires), not from condition 2 itself. That CLI
    test still earns its keep — it proves the END-TO-END property holds —
    but it cannot prove condition 2 is load-bearing IN ISOLATION. This
    unit test calls `_tolerated_orphan_flip_paths()` directly, bypassing
    classify()'s backstop entirely, so a future removal of condition 2 is
    caught here even if some later refactor stops re-deriving through
    classify().
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    row = docs_audit.DocRow(
        path="docs/REFERENCED.md",
        status="LIVE",
        mtime_days=200,
        refs_in=3,  # genuinely referenced — never orphan-eligible
        orphan_eligible_on="2026-01-01",
        orphan_flipped_on=None,
    )
    committed_claims = {
        "docs/REFERENCED.md": {"orphan_flipped_on": "2026-06-01", "refs_in": "0"},
    }
    tolerated = docs_audit._tolerated_orphan_flip_paths(
        rows=[row],
        prev_flipped={},
        committed_claims=committed_claims,
        trusted_ref_ceiling_date=date(2026, 7, 1),
    )
    assert tolerated == set(), (
        "a doc with real inbound references (refs_in != 0) must never be "
        "admitted to the tolerated set, regardless of what the committed "
        f"table claims. got={tolerated}"
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
    assert row[5].strip() == "—"  # orphan_flipped_on column stays empty

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
    trusted_flip_date = cells[5].strip()
    assert trusted_flip_date != "—", "test setup sanity failed: no flip date recorded"

    # Forge the candidate's LOCAL working tree only (never pushed): flip
    # removed, status reset to LIVE — same shape as the BLOCKER-2 forgery
    # test, but this time the forged file is what --gate-consistent's WRITE
    # step will see as "old_content" if it (incorrectly) reads local state.
    cells[2] = " LIVE "
    cells[5] = " — "
    cells[10] = " — "
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
    assert row[5].strip() == trusted_flip_date, (
        "--gate-consistent must reproduce origin/main's ORIGINAL flip "
        f"date ({trusted_flip_date!r}), not invent a new one or keep the "
        f"forged blank: got {row[5].strip()!r}"
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
    raw = inventory.read_text()
    lines = raw.splitlines()
    touched_i = _col(raw, "last_touched_date")
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            true_date = date.fromisoformat(parts[touched_i].strip())
            parts[touched_i] = f" {(true_date - timedelta(days=7)).isoformat()} "
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
    raw = inventory.read_text()
    lines = raw.splitlines()
    eligible_i = _col(raw, "orphan_eligible_on")
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            true_eligible = date.fromisoformat(parts[eligible_i].strip())
            parts[eligible_i] = f" {(true_eligible + timedelta(days=1)).isoformat()} "
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
    raw = inventory.read_text()
    lines = raw.splitlines()
    status_i = _col(raw, "Status")
    flipped_i = _col(raw, "orphan_flipped_on")
    touched_i = _col(raw, "last_touched_date")
    mutated_lines = []
    found = False
    for line in lines:
        if line.startswith("| docs/OLD_DOC.md |"):
            found = True
            parts = line.split("|")
            assert parts[status_i].strip() == "LIVE", parts
            assert parts[flipped_i].strip() == "—", parts  # orphan_flipped_on untouched
            parts[status_i] = " ARCHIVED "  # hand-edit STATUS only
            # …and the action text, in the CURRENT rendered format. A forgery
            # written in a stale format would be rejected for looking wrong
            # rather than for being unbacked by an organ flip — the test would
            # go green while proving something else.
            parts[-2] = (
                f" archive: orphan, last_touched={parts[touched_i].strip()}, refs=0 "
            )
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
    cells[5] = " — "
    cells[10] = " — "
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


def test_trusted_ref_tip_date_treats_failed_fetch_as_unresolved(tmp_path):
    """GUILT (W106b layer 4, 2026-07-30 ledger entry: "`_trusted_ref_tip_
    date` ignores its `git fetch` return code, so a failed fetch silently
    supplies a possibly-stale CEILING"). A repo whose local tracking ref
    `refs/remotes/origin/main` already resolves to a real (old) commit —
    from a PRIOR successful fetch — but whose `origin` remote is now
    broken must NOT fold that leftover local ref into the ceiling as if
    freshly verified: the fetch itself fails, and `_trusted_ref_tip_date`
    must return None (the same degrade-to-"now" path an unresolvable ref
    already takes), not the stale local ref's commit date.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    # Prime the local tracking ref with a real, resolvable, OLD commit —
    # simulates "this machine fetched origin/main successfully at some
    # point in the past" (the ordinary case: every prior run's fetch
    # left this ref exactly where BLOCKER-2's own fixture wiring does).
    subprocess.run(["git", "fetch", "-q", "origin", "main"], cwd=repo, check=True)
    resolve_before = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", "origin/main^{commit}"],
        capture_output=True,
        text=True,
    )
    assert resolve_before.returncode == 0, "fixture setup: origin/main must resolve pre-break"

    # Break the remote so any FUTURE fetch fails, while the already-primed
    # local tracking ref above stays intact and still resolvable — this is
    # exactly the shape a real network flap or a revoked/removed remote
    # produces: fetch fails, but stale local refs are still readable.
    subprocess.run(
        ["git", "remote", "set-url", "origin", str(tmp_path / "nonexistent-origin.git")],
        cwd=repo,
        check=True,
    )

    result = docs_audit._trusted_ref_tip_date(repo, "origin/main")
    assert result is None, (
        "a failed fetch must degrade to None (same as an unresolvable ref), "
        f"not silently supply the stale local tracking ref's date: got {result}"
    )


def test_trusted_ref_tip_date_succeeds_when_fetch_succeeds(tmp_path):
    """INNOCENCE — the ordinary path (working `origin`, fetch succeeds)
    must still resolve to a real date, unaffected by the guilt fix above.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    result = docs_audit._trusted_ref_tip_date(repo, "origin/main")
    assert result is not None, "a healthy origin + successful fetch must resolve a tip date"
    assert result == date.today() - timedelta(days=200)


# ---------------------------------------------------------------------------
# Severed provenance channel (2026-08-17). read_trusted_prev_flipped()'s
# docstring knows exactly two ways to reach {}: the ref will not resolve
# (raise) or the file is absent on it (legitimate bootstrap). PR #4233 created
# a THIRD: the file is present and is a pointer document with no table, so {}
# is returned forever while reading exactly like a first-ever run.
#
# The signal is a WARNING, never a behaviour change — these tests pin the
# signal AND pin that the two legitimate {}-producing states stay silent, so
# an unconditional "always warn" (which would pass guilt alone) fails here.
# ---------------------------------------------------------------------------

_SEVERED = "SEVERED"


def _trusted_prev_flipped_stderr(repo, capsys):
    """Call the real function; return (result, stderr) with stderr captured."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    capsys.readouterr()  # drop anything buffered by fixture setup
    result = docs_audit.read_trusted_prev_flipped(repo, "origin/main")
    return result, capsys.readouterr().err


def test_severed_channel_tableless_trusted_inventory_warns(tmp_path, capsys):
    """GUILT: a trusted inventory that EXISTS but carries no parseable table
    must name itself as a severed channel. This is the post-#4233 state of
    origin/main: an 11-line pointer document. Without this, the break is
    indistinguishable from a first-ever run in every log the organism keeps.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    (repo / "docs" / "DOCS_INVENTORY.md").write_text(
        "# Documentation Inventory\n\n"
        "Derived state now lives in `.artifacts/docs-derived-state/`.\n",
        encoding="utf-8",
    )
    _commit_and_push(repo, "replace inventory with a pointer")

    result, err = _trusted_prev_flipped_stderr(repo, capsys)

    assert result == {}, "contract unchanged: a tableless trusted inventory still yields {}"
    assert _SEVERED in err, (
        "a present-but-tableless trusted inventory is NOT the bootstrap case and "
        f"must say so; stderr was: {err!r}"
    )


def test_real_trusted_table_does_not_warn(tmp_path, capsys):
    """INNOCENCE 1: a healthy trusted inventory with real provenance must
    return it and stay silent. An unconditional warning would fail here.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    (repo / "docs" / "DOCS_INVENTORY.md").write_text(
        "# Documentation Inventory\n\n"
        "## Files\n\n"
        "| File | Status | orphan_flipped_on |\n"
        "|------|--------|--------------------|\n"
        "| docs/OLD_DOC.md | ARCHIVED | 2026-07-19 |\n",
        encoding="utf-8",
    )
    _commit_and_push(repo, "inventory with a real flip")

    result, err = _trusted_prev_flipped_stderr(repo, capsys)

    assert result == {"docs/OLD_DOC.md": "2026-07-19"}, (
        f"a real trusted table must still be read verbatim: got {result}"
    )
    assert _SEVERED not in err, f"a healthy table must not be called severed; stderr: {err!r}"


def test_absent_trusted_inventory_stays_a_silent_bootstrap(tmp_path, capsys):
    """INNOCENCE 2: the ORIGINAL {}-producing state — no docs/DOCS_INVENTORY.md
    on the trusted ref at all — is a legitimate bootstrap and must remain
    silent. Warning here would cry severed-channel at every genuinely fresh
    repo, which is how a real signal gets trained into noise.
    """
    repo = _make_git_repo_with_old_doc(tmp_path, backdate_days=200)
    assert not (repo / "docs" / "DOCS_INVENTORY.md").exists(), "fixture: file must be absent"

    result, err = _trusted_prev_flipped_stderr(repo, capsys)

    assert result == {}, "bootstrap still yields {}"
    assert _SEVERED not in err, (
        f"an ABSENT trusted inventory is the bootstrap case, not a severed "
        f"channel; stderr: {err!r}"
    )


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


# --- compute_refs_in: reference-anchored matching, not `basename in text` ---
#
# guard-over-match family #3 (cicatrix-superscar.md §3): compute_refs_in()
# used to be a bare `basename in text` substring scan, which credited a doc
# with an inbound reference whenever ANOTHER doc's text merely happened to
# END with its basename — including as a suffix of a longer basename
# (ANTHROPIC_API_REFERENCE.md crediting API_REFERENCE.md) or of an ordinary
# prose word. Every guard in that family needs both a GUILT corpus (the
# substring trap must not fire) and an INNOCENCE corpus (a real citation
# must still count) — see docs_audit.py's compute_refs_in /
# _has_bare_delimited_mention docstrings for the exact anchoring rule.
#
# 0 hits for `compute_refs_in(` existed in this file before this section —
# every prior refs_in test exercised it only indirectly through the full
# classify()/--regen-only pipeline. These call the function directly.


def test_refs_in_markdown_link_counts_as_reference(tmp_path):
    """GUILT-complement / basic case: a real `[text](target)` markdown link
    that resolves to the target IS a reference."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "API_REFERENCE.md"
    target.write_text("# API Reference\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text("See [the API reference](docs/API_REFERENCE.md).\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_backticked_full_relative_path_counts(tmp_path):
    """INNOCENCE (documented broadening, decision pinned here): a backticked
    FULL relative path — not inside `[text](...)` link syntax — still
    counts as a citation."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "API_REFERENCE.md"
    target.write_text("# API Reference\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text("Full path: `docs/API_REFERENCE.md` explained.\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_unlinked_backticked_bare_basename_counts(tmp_path):
    """INNOCENCE (documented broadening, decision pinned here): an unlinked
    backticked BARE filename (no path, no markdown-link syntax) still
    counts, when it resolves sibling-style against the citing file's own
    directory — the deliberate broadening beyond strict link-only/path-only
    anchoring. Measured impact of NOT making this choice (i.e. disabling
    the whole bare-no-path branch — backtick, "(", box-drawing, and
    enclosed-paren alike — keeping only markdown links and full-path
    mentions): re-measured 2026-08-07 against THIS implementation, same
    948-row universe as compute_refs_in's docstring — 69 rows currently at
    refs_in>0 would drop to refs_in==0, ZERO would gain one. (The original
    #3737 commit's docstring here claimed "28 real citations lost vs. 0
    under this rule" for the narrower pre-review shape of this same
    broadening — a number never re-measured after review found the
    broadening itself was partly an over-match; corrected rather than
    reused, per this repo's discipline of re-deriving a stale number
    instead of copying it forward.)"""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "API_REFERENCE.md"
    target.write_text("# API Reference\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text("`API_REFERENCE.md` documents this.\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_basename_inside_longer_basename_rejected(tmp_path):
    """GUILT (the bug this fix exists for): docs/API_REFERENCE.md must NOT
    be credited by a doc that only ever writes
    docs/ANTHROPIC_API_REFERENCE.md — a longer basename that happens to END
    in the target's basename is not a citation of the target. Regression
    for the live false-attribution measured 2026-08-07:
    docs/CLAUDE-archive-2026-04-06.md only ever writes
    `docs/ANTHROPIC_API_REFERENCE.md` and was crediting API_REFERENCE.md
    under the old substring scan."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "API_REFERENCE.md"
    target.write_text("# API Reference\n", encoding="utf-8")
    (repo / "docs" / "ANTHROPIC_API_REFERENCE.md").write_text(
        "# Anthropic API reference\n", encoding="utf-8"
    )
    citer = repo / "docs" / "citer.md"
    citer.write_text(
        "See `docs/ANTHROPIC_API_REFERENCE.md` for the Anthropic-specific patterns.\n",
        encoding="utf-8",
    )

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_plan_md_basename_collisions_rejected(tmp_path):
    """GUILT: regression for the live false attribution measured
    2026-08-07 — docs/X_PREMIUM_BLITZ_BATTLE_PLAN.md mentions
    BLOG_100_ARTICLES_PLAN.md and ACTIVATION_PLAN.md, neither of which is a
    citation of any docs/**/PLAN.md target; both basenames merely END in
    "PLAN.md"."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "design").mkdir(parents=True)
    target = repo / "docs" / "design" / "PLAN.md"
    target.write_text("# Plan\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text(
        "- 100+ articoli pianificati (BLOG_100_ARTICLES_PLAN.md)\n"
        "- see also ACTIVATION_PLAN.md for rollout\n",
        encoding="utf-8",
    )

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_bare_undelimited_prose_mention_rejected(tmp_path):
    """GUILT: the one shape this fix exists to kill — a bare, undelimited
    prose mention of a basename ("the file X.md is...") is not a
    citation."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "README.md"
    target.write_text("# Readme\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text("the file README.md is a common convention\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_cross_directory_readme_basename_collision_rejected(tmp_path):
    """GUILT: two different docs/**/README.md files must not credit each
    other purely because both end in "README.md" preceded by a slash — the
    "/" fallback branch requires the captured path to actually RESOLVE to
    the target (repo-root-relative or citing-file-relative), never a raw
    trailing-segment guess."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "sub").mkdir(parents=True)
    (repo / "docs" / "other").mkdir(parents=True)
    target = repo / "docs" / "sub" / "README.md"
    target.write_text("# Sub readme\n", encoding="utf-8")
    (repo / "docs" / "other" / "README.md").write_text(
        "# Other readme\n", encoding="utf-8"
    )
    citer = repo / "docs" / "citer.md"
    citer.write_text("See other/README.md for the unrelated area.\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_sibling_relative_markdown_link_counts(tmp_path):
    """INNOCENCE: a genuine sibling-relative markdown link
    `[x](../other/README.md)` still counts — real link resolution must
    survive the reference-anchoring rewrite unchanged."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "sub").mkdir(parents=True)
    (repo / "docs" / "other").mkdir(parents=True)
    target = repo / "docs" / "other" / "README.md"
    target.write_text("# Other readme\n", encoding="utf-8")
    citer = repo / "docs" / "sub" / "citer.md"
    citer.write_text("See [x](../other/README.md) for details.\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_backticked_relative_parent_path_counts(tmp_path):
    """INNOCENCE — regression pin for a real bug caught by re-measuring this
    fix against the live tree (2026-08-07): docs/crm/reports-2026-04-20/
    README.md cites its sibling via a BACKTICKED (non-link) relative path,
    `` `../assignment-mismatches-2026-04-20.md` ``. A naive trailing-
    segment string match (the first cut of this fix) does not understand
    ".." and silently dropped this exact live citation, which would have
    made a genuinely-referenced doc newly orphan-eligible as a side effect
    of the bugfix. The fallback must resolve the captured token against the
    CITING file's own directory (exactly like a real markdown link), not
    just compare trailing path segments."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "crm").mkdir(parents=True)
    (repo / "docs" / "crm" / "reports-2026-04-20").mkdir(parents=True)
    target = repo / "docs" / "crm" / "assignment-mismatches-2026-04-20.md"
    target.write_text("# Assignment mismatches\n", encoding="utf-8")
    citer = repo / "docs" / "crm" / "reports-2026-04-20" / "README.md"
    citer.write_text(
        "`assigned_to` != `client.assigned_to`.\n"
        "See `../assignment-mismatches-2026-04-20.md` for the full list.\n",
        encoding="utf-8",
    )

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_trailing_word_boundary_rejects_longer_extension(tmp_path):
    """GUILT: a target basename must not be credited by a longer filename
    that merely starts with it (README.mdx, README.md.bak) — the trailing-
    boundary check, the other half of the anchoring rule alongside the
    leading-delimiter check."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    target = repo / "docs" / "README.md"
    target.write_text("# Readme\n", encoding="utf-8")
    citer = repo / "docs" / "citer.md"
    citer.write_text("`README.mdx` and `README.md.bak` are unrelated files.\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_real_inbound_link_keeps_doc_off_the_orphan_path(tmp_path):
    """INNOCENCE, end-to-end: a doc with a REAL inbound markdown link, aged
    well past orphan_days, must NOT be classified as a structurally-
    eligible orphan — refs_in>0 must still gate archival through the full
    classify()/--regen-only pipeline, not just the unit function. Without
    this assertion, a compute_refs_in() that returns 0 for everything would
    still pass every GUILT-only test above."""
    repo = tmp_path / "repo"
    (repo / "docs").mkdir(parents=True)
    (repo / "docs" / "TARGET.md").write_text("# Target doc\n", encoding="utf-8")
    (repo / "docs" / "CITER.md").write_text(
        "See [the target](TARGET.md) for details.\n", encoding="utf-8"
    )
    _init_git_repo(repo, backdate_days=200)

    result = _run_audit(repo, "--orphan-days", "90", "--regen-only")
    assert result.returncode in (0, 1), result.stderr
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    cells = _row_cells(inventory, "docs/TARGET.md")
    refs_in_col = _col(inventory, "refs_in")
    action_col = _col(inventory, "action")
    assert cells[refs_in_col].strip() != "0", (
        "test setup sanity failed: TARGET.md must have a real inbound "
        f"reference from CITER.md — cells: {cells}"
    )
    assert not cells[action_col].strip().startswith("archive: orphan"), (
        "a doc with a real inbound link must never be orphan-eligible — "
        f"cells: {cells}"
    )


# ---------------------------------------------------------------------------
# Post-#3737 follow-up (2026-08-07): the bare-mention broadening in the
# original fix accepted a backtick/"("-preceded BARE basename with NO
# further check — an over-match found live: a `` `README.md` `` mention
# anywhere in the repo, about ANY README, credited EVERY docs/**/README.md
# target regardless of directory. It also missed three real citation shapes:
# a fully-qualified `~/...` home path, a "(see X.md)"/"(vedi X.md)" sibling
# mention, and a name inside a fenced ASCII-tree diagram. Both classes are
# fixed by requiring a bare basename to resolve SIBLING-style (against the
# CITING file's own directory) instead of being accepted blind — see
# _has_bare_delimited_mention's docstring.
# ---------------------------------------------------------------------------


def test_refs_in_link_syntax_non_resolving_paren_does_not_leak_into_bare_fallback(
    tmp_path,
):
    """GUILT — the exact Defect A repro: a real markdown link `[text](README.md)`
    that resolves to docs/a/README.md must NOT ALSO be picked up by the bare-
    mention fallback for an unrelated docs/b/README.md, just because the raw
    link text "(README.md)" is a literal substring match for the fallback's
    "(" delimiter. The original #3737 fallback blind-accepted ANY basename
    preceded by "(" — including the "(" that opens a markdown link's OWN
    target syntax, even after `_resolve_link_target` had already correctly
    said that link does not point at this target."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "a").mkdir(parents=True)
    (repo / "docs" / "b").mkdir(parents=True)
    (repo / "docs" / "a" / "citer.md").write_text(
        "[the a readme](README.md)\n", encoding="utf-8"
    )
    (repo / "docs" / "a" / "README.md").write_text("# A readme\n", encoding="utf-8")
    target_b = repo / "docs" / "b" / "README.md"
    target_b.write_text("# B readme\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target_b) == 0
    # Innocence, same fixture: the link DOES still count for its real target.
    assert docs_audit.compute_refs_in(repo, repo / "docs" / "a" / "README.md") == 1


def test_refs_in_bare_backtick_mention_requires_sibling_directory(tmp_path):
    """GUILT — live regression pin (2026-08-07): a `` `README.md` `` bare
    mention in docs/x/citer.md, about the readme IN docs/x/, must not credit
    an unrelated docs/y/README.md just because both basenames match. This is
    the exact shape measured live: docs/DOCSYNC_SENTINEL.md mentions
    `` `README.md` `` meaning the repo-root README, and under the #3737
    original that blindly credited docs/wr3/README.md and 13 other unrelated
    docs/**/README.md files.

    FIXTURE NOTE (2026-08-07, re-derived): the citing directory must carry its
    OWN README.md. Without it this repo has exactly one README.md, the mention
    is unambiguous, and the uniqueness escape in `_basename_is_unique` accepts
    it — correctly. Ambiguity is the thing this test exists to protect against,
    so the fixture has to contain some: the earlier version asserted the strict
    rule on a corpus that had nothing to be strict about."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "x").mkdir(parents=True)
    (repo / "docs" / "y").mkdir(parents=True)
    (repo / "docs" / "x" / "citer.md").write_text(
        "`README.md` refers to the project readme.\n", encoding="utf-8"
    )
    (repo / "docs" / "x" / "README.md").write_text("# X readme\n", encoding="utf-8")
    target_y = repo / "docs" / "y" / "README.md"
    target_y.write_text("# Y readme\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target_y) == 0


def test_refs_in_bare_backtick_mention_same_directory_counts(tmp_path):
    """INNOCENCE, twin of the above: the SAME bare mention, when the target
    actually IS in the citing file's own directory, still counts — the
    sibling-resolution fix narrows the over-match, it does not kill the
    broadening itself."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "x").mkdir(parents=True)
    (repo / "docs" / "x" / "citer.md").write_text(
        "`README.md` refers to the project readme.\n", encoding="utf-8"
    )
    target_x = repo / "docs" / "x" / "README.md"
    target_x.write_text("# X readme\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target_x) == 1


def test_refs_in_ascii_tree_sibling_child_counts(tmp_path):
    """INNOCENCE — live regression pin: docs/wr3/README.md lists its sibling
    docs/wr3/runbook-supervisor.md inside a fenced ASCII-tree diagram
    ("├── runbook-supervisor.md"). Box-drawing characters (├ └ │ ─) must be
    recognised as a leading anchor for a bare, sibling-resolved mention."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "wr3").mkdir(parents=True)
    (repo / "docs" / "wr3" / "README.md").write_text(
        "# WR3\n\n```\ndocs/wr3/\n"
        "├── README.md                # this file\n"
        "└── runbook-supervisor.md    # supervisor procedures\n"
        "```\n",
        encoding="utf-8",
    )
    target = repo / "docs" / "wr3" / "runbook-supervisor.md"
    target.write_text("# Runbook\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_ascii_tree_wrong_directory_rejected(tmp_path):
    """GUILT, twin of the above: the identical tree LINE ("├── SIBLING.md")
    living in a citing file whose own directory does NOT contain the real
    target must not credit a same-basename file that lives elsewhere — the
    ASCII-tree anchor is sibling-scoped like every other bare-mention shape,
    not a blanket accept — WHEN the basename is ambiguous.

    FIXTURE NOTE (2026-08-07, re-derived): docs/other/ carries its own
    SIBLING.md, so the tree line refers to that one and the target in
    docs/real/ genuinely could not be meant. Without the second file the name
    is unique corpus-wide and `_basename_is_unique` accepts the mention on
    purpose — a tree listing that names the only SIBLING.md in the repo IS
    citing it, wherever it was written."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "other").mkdir(parents=True)
    (repo / "docs" / "real").mkdir(parents=True)
    (repo / "docs" / "other" / "README.md").write_text(
        "```\n├── SIBLING.md    # some unrelated file\n```\n", encoding="utf-8"
    )
    (repo / "docs" / "other" / "SIBLING.md").write_text("# Other\n", encoding="utf-8")
    target = repo / "docs" / "real" / "SIBLING.md"
    target.write_text("# Sibling\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_see_paren_sibling_mention_counts(tmp_path):
    """INNOCENCE — live regression pin: docs/superpowers/reviews/2026-04-21-
    partners-v1/POST-MERGE-deploy-runbook.md cites its sibling via
    "(see ASYA-withholding-rates-runbook.md)". The character immediately
    before the basename is a plain space (from "see "), not "(" — this
    requires the enclosed-open-paren check, not the immediate-adjacency one."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "p").mkdir(parents=True)
    (repo / "docs" / "p" / "citer.md").write_text(
        "Prerequisite confirmed (see SIBLING.md).\n", encoding="utf-8"
    )
    target = repo / "docs" / "p" / "SIBLING.md"
    target.write_text("# Sibling\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_vedi_paren_sibling_mention_counts(tmp_path):
    """INNOCENCE — live regression pin, different lead-in word: docs/
    superpowers/sessions/2026-04-17-strategic-8/MERGE-STRATEGY.md cites its
    sibling via "(vedi DOCKER-CLAUDE-CLI.md)". Proves the enclosed-paren
    check is a STRUCTURAL anchor (an actual open "("), not a hardcoded
    "see"/"vedi" phrase list — cicatrix-superscar.md family #3 calls out a
    fragile phrase list as its own recurring disease."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "p").mkdir(parents=True)
    (repo / "docs" / "p" / "citer.md").write_text(
        "Bloccato da Dockerfile update (vedi OTHER.md).\n", encoding="utf-8"
    )
    target = repo / "docs" / "p" / "OTHER.md"
    target.write_text("# Other\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_paren_mention_wrong_directory_rejected(tmp_path):
    """GUILT, twin of the two above: "(see SIBLING.md)" must not credit a
    same-basename file living OUTSIDE the citing file's own directory — when
    the basename is ambiguous.

    FIXTURE NOTE (2026-08-07, re-derived): docs/p/ carries its own SIBLING.md,
    which is what makes "(see SIBLING.md)" ambiguous with respect to
    docs/q/SIBLING.md. With a single SIBLING.md in the corpus the mention has
    exactly one possible referent and `_basename_is_unique` accepts it."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "p").mkdir(parents=True)
    (repo / "docs" / "q").mkdir(parents=True)
    (repo / "docs" / "p" / "citer.md").write_text(
        "Prerequisite confirmed (see SIBLING.md).\n", encoding="utf-8"
    )
    (repo / "docs" / "p" / "SIBLING.md").write_text("# P sibling\n", encoding="utf-8")
    target = repo / "docs" / "q" / "SIBLING.md"
    target.write_text("# Sibling\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_unique_basename_cross_directory_counts(tmp_path):
    """INNOCENCE for the uniqueness escape — live regression pin (2026-08-07).

    Shape measured on the real corpus at
    docs/archive/2026-07-orphans/NOTEBOOKLM_NOTEBOOK_ARCHITECTURE.md:4:
        > Dipende da: `NOTEBOOKLM_STRATEGY_4LLM_BRAINSTORM.md`
    A DECLARED dependency, backtick-anchored, naming a file in another
    directory. Under sibling-only resolution this and 14 other LIVE documents
    fell to refs_in==0, which is half of orphan eligibility — and
    scripts/docs_guardian.sh physically `git mv`s those on its weekly run. A
    name that exists exactly once in the corpus has exactly one referent."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "a").mkdir(parents=True)
    (repo / "docs" / "b").mkdir(parents=True)
    (repo / "docs" / "a" / "citer.md").write_text(
        "> Dipende da: `ONLY_ONE_OF_THESE.md`\n", encoding="utf-8"
    )
    target = repo / "docs" / "b" / "ONLY_ONE_OF_THESE.md"
    target.write_text("# The only one\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_unique_basename_still_requires_an_anchor(tmp_path):
    """GUILT — the uniqueness escape does NOT dissolve the anchor requirement.

    An undelimited prose mention ("the file X.md is a common convention") is
    the one shape this whole guard exists to kill, and it stays killed even
    when the basename is unique. Uniqueness answers "which file could this
    mean"; the anchor answers "is this a citation at all". Both must hold."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "a").mkdir(parents=True)
    (repo / "docs" / "b").mkdir(parents=True)
    (repo / "docs" / "a" / "citer.md").write_text(
        "Historically the file ONLY_ONE_OF_THESE.md was written by hand.\n",
        encoding="utf-8",
    )
    target = repo / "docs" / "b" / "ONLY_ONE_OF_THESE.md"
    target.write_text("# The only one\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_closed_paren_before_bare_mention_rejected(tmp_path):
    """GUILT: the enclosed-paren anchor requires the "(" to still be OPEN
    (unclosed) at the point of the match. A paren that already closed
    earlier on the same line is not an anchor for a later, unrelated bare
    mention — otherwise ANY parenthetical anywhere on a line would license
    crediting any basename appearing later on it."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "p").mkdir(parents=True)
    (repo / "docs" / "p" / "citer.md").write_text(
        "(unrelated aside) then casually mentions SIBLING.md later.\n",
        encoding="utf-8",
    )
    target = repo / "docs" / "p" / "SIBLING.md"
    target.write_text("# Sibling\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_home_prefixed_desktop_path_counts(tmp_path):
    """INNOCENCE — live regression pin: docs/audits/2026-05-02-cell-openclaw-
    brainstorm/00b_briefing_v2.md cites its 3 sibling response files by a
    fully-qualified `` `~/Desktop/nuzantara/docs/audits/.../NN_x.md` `` path.
    Neither the repo-root-relative nor citing-file-relative resolution
    recognised a leading "~" before this fix — pathlib's "/" operator
    silently discards `citing_file.parent` for an absolute-looking RHS."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "h").mkdir(parents=True)
    (repo / "docs" / "h" / "citer.md").write_text(
        "- `~/Desktop/nuzantara/docs/h/TARGET.md` (round 1)\n", encoding="utf-8"
    )
    target = repo / "docs" / "h" / "TARGET.md"
    target.write_text("# Target\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_home_prefixed_no_desktop_path_counts(tmp_path):
    """INNOCENCE — a different machine's home layout (no "Desktop/" segment,
    e.g. `~/nuzantara/...` on M5) must resolve the same way: the marker
    search is for "nuzantara/" itself, not a fixed "Desktop/nuzantara/"
    prefix."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "h").mkdir(parents=True)
    (repo / "docs" / "h" / "citer.md").write_text(
        "- `~/nuzantara/docs/h/TARGET2.md` (round 1)\n", encoding="utf-8"
    )
    target = repo / "docs" / "h" / "TARGET2.md"
    target.write_text("# Target 2\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_home_prefixed_wrong_subpath_rejected(tmp_path):
    """GUILT, twin of the two above: a home-prefixed path whose SUFFIX (the
    part after the "nuzantara/" marker) does not match the target's actual
    repo-relative path must not credit it — the marker recovers a real
    repo-relative path, it does not blanket-accept any "~/...nuzantara/..."
    mention."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "h").mkdir(parents=True)
    (repo / "docs" / "other").mkdir(parents=True)
    (repo / "docs" / "h" / "citer.md").write_text(
        "- `~/Desktop/nuzantara/docs/other/TARGET.md` (round 1)\n",
        encoding="utf-8",
    )
    target = repo / "docs" / "h" / "TARGET.md"
    target.write_text("# Target\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


def test_refs_in_sentence_final_period_after_bare_path_counts(tmp_path):
    """INNOCENCE — Defect C fix: a bare (non-backticked) repo-relative-path
    mention ending a sentence ("...docs/a/TARGET.md.") must count — the
    period there ends the SENTENCE, not the filename. Before this fix, the
    trailing-boundary check rejected ANY char-after-match "." unconditionally,
    so this exact shape returned 0 while the backticked form
    (`` `docs/a/TARGET.md` ``, where a backtick supplies the boundary instead
    of a period) returned 1 — an asymmetry with no basis in the citation
    itself."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "a").mkdir(parents=True)
    (repo / "docs" / "a" / "citer.md").write_text(
        "The plan lives at docs/a/TARGET.md.\n", encoding="utf-8"
    )
    target = repo / "docs" / "a" / "TARGET.md"
    target.write_text("# Target\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 1


def test_refs_in_bare_path_dotbak_extension_still_rejected(tmp_path):
    """GUILT, twin of the above: a bare (non-backticked) repo-relative-path
    mention where the "." is followed by MORE word characters
    ("docs/a/TARGET.md.bak" — a real, different file) must still be
    rejected. Only a period that ends the match with nothing-alnum
    following it is treated as a sentence-final period."""
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    repo = tmp_path / "repo"
    (repo / "docs" / "a").mkdir(parents=True)
    (repo / "docs" / "a" / "citer.md").write_text(
        "The backup lives at docs/a/TARGET.md.bak now.\n", encoding="utf-8"
    )
    target = repo / "docs" / "a" / "TARGET.md"
    target.write_text("# Target\n", encoding="utf-8")

    assert docs_audit.compute_refs_in(repo, target) == 0


# ---------------------------------------------------------------------------
# Directory-index exemption (2026-08-07). Closing the bare-mention hole above
# removes an ACCIDENTAL protection: before it, any prose token `README.md`
# credited every README in the tree. Measured on the live corpus the moment
# the hole closed, 13 docs (11 `README.md`, 2 `00_README.md`) became newly
# orphan-eligible. A README is reachable by its LOCATION, so refs_in == 0 is
# its normal state — the orphan PREDICATE is wrong for the class, not the
# counter. See _is_directory_index for the rule and its declared limits.
# ---------------------------------------------------------------------------


def test_directory_index_with_zero_refs_is_never_orphan_archived(tmp_path):
    """GUILT, end-to-end through the real pipeline: a README nothing links to,
    aged far past orphan_days, must survive — and must SAY why, so a reader of
    the inventory is not left guessing whether refs_in is broken.

    Both spellings, because they are one rule: plain `README.md` and the
    numeric-ordering `00_README.md` that the wave directories use (their
    siblings are `01_*`, `02_*`; the index sorts first by carrying `00_`).
    """
    repo = tmp_path / "repo"
    (repo / "docs" / "topic").mkdir(parents=True)
    (repo / "docs" / "topic" / "README.md").write_text(
        "# Topic\n\nIndex of this folder.\n", encoding="utf-8"
    )
    (repo / "docs" / "topic" / "00_README.md").write_text(
        "# Wave index\n\nIndex of this folder.\n", encoding="utf-8"
    )
    _init_git_repo(repo, backdate_days=200)

    result = _run_audit(repo, "--orphan-days", "90", "--regen-only")
    assert result.returncode in (0, 1), result.stderr
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    refs_in_col = _col(inventory, "refs_in")
    action_col = _col(inventory, "action")
    for rel in ("docs/topic/README.md", "docs/topic/00_README.md"):
        cells = _row_cells(inventory, rel)
        assert cells[refs_in_col].strip() == "0", (
            "test setup sanity failed: the fixture must give this doc ZERO "
            f"inbound refs, or it proves nothing about the exemption — {cells}"
        )
        assert not cells[action_col].strip().startswith("archive: orphan"), (
            f"a directory index must never be orphan-archived — {rel}: {cells}"
        )
        assert cells[action_col].strip() == "keep (directory index)", (
            f"the row must name the reason it survived — {rel}: {cells}"
        )


def test_non_index_doc_with_zero_refs_is_still_orphan_archived(tmp_path):
    """INNOCENCE, sharing the guilt test's mechanism exactly — same repo shape,
    same age, same zero refs; only the BASENAME differs.

    Without this, a `_is_directory_index` that returned True for everything
    would pass the guilt test while silently disabling orphan archival for the
    whole corpus — the exemption would have eaten the organ.

    `INDEX.md` and `READMEISH.md` are the DECLARED LIMITS of the rule (only
    README, only with a numeric ordering prefix). Pinning them here means a
    future widening — to other index-ish names, or to any name CONTAINING
    "README" — cannot land without a test going red and being argued for.
    """
    repo = tmp_path / "repo"
    (repo / "docs" / "topic").mkdir(parents=True)
    for name in ("GUIDE.md", "INDEX.md", "READMEISH.md"):
        (repo / "docs" / "topic" / name).write_text(
            f"# {name}\n\nBody.\n", encoding="utf-8"
        )
    _init_git_repo(repo, backdate_days=200)

    result = _run_audit(repo, "--orphan-days", "90", "--regen-only")
    assert result.returncode in (0, 1), result.stderr
    inventory = (repo / "docs" / "DOCS_INVENTORY.md").read_text()
    action_col = _col(inventory, "action")
    for name in ("GUIDE.md", "INDEX.md", "READMEISH.md"):
        cells = _row_cells(inventory, f"docs/topic/{name}")
        assert cells[action_col].strip().startswith("archive: orphan"), (
            "an unreferenced non-index doc must still be orphan-eligible — "
            f"{name}: {cells}"
        )


def test_refs_in_uniqueness_counts_root_files_not_just_docs(tmp_path):
    """GUILT — the `docs/ai/GEMINI.md` shape, found while reviewing the
    uniqueness escape and fixed before it shipped.

    A basename that is unique WITHIN docs/** but also exists as a root
    reference file is NOT unique: a reader writing `` `GEMINI.md` `` from
    another directory most likely means the root one. Counting only
    `walk_docs` made the docs copy measure as the sole bearer of the name, so
    the escape credited it for a mention that was never about it.

    The fixture reproduces exactly that: root `GEMINI.md` exists, `docs/ai/
    GEMINI.md` exists, and the citer sits in a THIRD directory so the sibling
    rule cannot rescue the credit either. The escape must decline, leaving
    refs_in at 0 for the docs copy.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    docs_audit._BASENAME_COUNTS.clear()
    docs_audit._UNIVERSE_CACHE.clear()
    repo = tmp_path / "repo"
    (repo / "docs" / "ai").mkdir(parents=True)
    (repo / "docs" / "other").mkdir(parents=True)
    (repo / "GEMINI.md").write_text("# Root Gemini doc\n", encoding="utf-8")
    target = repo / "docs" / "ai" / "GEMINI.md"
    target.write_text("# Docs Gemini doc\n", encoding="utf-8")
    (repo / "docs" / "other" / "citer.md").write_text(
        "The arsenal notes live in `GEMINI.md` at the repo root.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo, backdate_days=5)

    assert docs_audit.compute_refs_in(repo, target) == 0, (
        "a bare mention that means the ROOT file must not credit the docs "
        "copy of the same basename"
    )


def test_refs_in_uniqueness_still_fires_for_a_truly_unique_name(tmp_path):
    """INNOCENCE, sharing the mechanism above — identical repo shape, identical
    citer wording and directory; only the basename differs, and this one exists
    NOWHERE else, not even at the root.

    Without it, a `reference_universe` that returned every `.md` in the world
    (or a `_basename_is_unique` hardwired to False) would pass the guilt test
    while silently disabling the escape the change exists to add.
    """
    sys.path.insert(0, str(AUDIT_SCRIPT.parent))
    import docs_audit  # noqa: E402

    docs_audit._BASENAME_COUNTS.clear()
    docs_audit._UNIVERSE_CACHE.clear()
    repo = tmp_path / "repo"
    (repo / "docs" / "ai").mkdir(parents=True)
    (repo / "docs" / "other").mkdir(parents=True)
    (repo / "GEMINI.md").write_text("# Root Gemini doc\n", encoding="utf-8")
    target = repo / "docs" / "ai" / "SOLE_TENANT.md"
    target.write_text("# The only one\n", encoding="utf-8")
    (repo / "docs" / "other" / "citer.md").write_text(
        "The arsenal notes live in `SOLE_TENANT.md` at the repo root.\n",
        encoding="utf-8",
    )
    _init_git_repo(repo, backdate_days=5)

    assert docs_audit.compute_refs_in(repo, target) == 1, (
        "an anchored mention of a name that exists exactly once must still "
        "count, from any directory — that is the escape's whole purpose"
    )
