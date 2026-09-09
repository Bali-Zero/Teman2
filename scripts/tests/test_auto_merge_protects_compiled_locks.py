#!/usr/bin/env python3
"""The two uv-compiled locks are never AUTO-MERGE eligible (guilt + innocence).

WHY THIS IS A SEPARATE FILE FROM test_auto_merge_whitelist.py, which already
owns the harness these tests reuse: that file is named by NO workflow, so it
does not execute in CI (`grep -rn test_auto_merge_whitelist .github/` returns
nothing), and 26 of its tests are red on origin/main for an unrelated reason —
Tier-1 CODEOWNERS paths that the PROTECTED list does not cover. Appending here
would have meant either arming a suite that is already red, or leaving these
assertions unarmed in a file nothing runs. Both are the same disease from
opposite ends. This file is wired into the REQUIRED `antidotes` job by the
same PR that adds it, and it starts green.

WHY THE CONTROL IS AUTO-MERGE ELIGIBILITY AND NOT A BLOCKING CHECK. #5556 made
Dependabot stop PROPOSING edits to the compiled locks via `exclude-paths`. That
option has NO effect on Dependabot SECURITY updates (dependabot-core #14408,
OPEN), so a lock-editing PR can still be opened on the one path that matters
most. The first attempt at a cure was a REQUIRED check that failed such a PR
outright; two cross-family reviewers (codex-gpt-5.6-sol and tp1-qwen3.8-max)
independently returned BLOCKING on it, for two reasons that both hold:

  (a) a genuine transitive security fix legitimately touches ONLY the lock, so
      a hard fail turns every real security PR permanently red — and a check
      that is always red is a check nobody reads (superscar #2);
  (b) it keyed on filename CO-PRESENCE, which a whitespace line in the paired
      manifest defeats — a control that can be satisfied without doing the
      thing it is asking for.

The danger .github/dependabot.yml actually names is narrower than "such a PR
exists": line 1 of that file declares an auto-merge-patch posture, and THAT is
what turns a green lock-only PR into a merged one nobody read. So the precise
control is to withdraw AUTO-MERGE ELIGIBILITY: nothing goes red, the PR simply
waits for a human, and bringing the manifest along buys nothing. Both
objections dissolve rather than being argued with.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
_HARNESS_PATH = REPO_ROOT / "scripts" / "tests" / "test_auto_merge_whitelist.py"

# Reuse the sibling's harness — it runs the REAL bash from the workflow with a
# fake `gh`, so these assertions test the shipped script, not a paraphrase of
# it. Loaded by path rather than imported by name because scripts/tests is not
# a package.
_spec = importlib.util.spec_from_file_location("_auto_merge_whitelist_harness", _HARNESS_PATH)
assert _spec and _spec.loader
_harness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_harness)
_evaluate_paths = _harness._evaluate_paths

COMPILED_LOCKS = [
    "apps/backend-rag/requirements.lock.txt",
    "apps/backend-rag/requirements-prod.lock.txt",
]


def test_the_locks_this_guard_protects_actually_exist() -> None:
    """A guard whose subject vanished passes for free. If a lock is renamed or
    deleted, this names it instead of letting the file go quietly green."""
    for lock in COMPILED_LOCKS:
        assert (REPO_ROOT / lock).is_file(), f"missing: {lock}"


# ------------------------------------------------------------------- GUILT
@pytest.mark.parametrize("lock", COMPILED_LOCKS)
def test_a_compiled_uv_lock_is_never_auto_merge_eligible(tmp_path: Path, lock: str) -> None:
    result, output = _evaluate_paths(tmp_path, expected_count=1, files=[lock])
    assert result.returncode == 0, result.stderr
    assert output == "match=false", f"{lock} must not be auto-mergeable"
    assert lock in result.stdout


def test_bringing_the_paired_manifest_does_NOT_buy_eligibility_back(tmp_path: Path) -> None:
    """The refutation that killed the first design, kept as a test: the
    criterion is 'does this PR touch a compiled lock at all', never 'did some
    manifest change too'. A cosmetic edit to requirements.txt must not restore
    auto-merge."""
    files = ["apps/backend-rag/requirements.lock.txt", "apps/backend-rag/requirements.txt"]
    result, output = _evaluate_paths(tmp_path, expected_count=2, files=files)
    assert result.returncode == 0, result.stderr
    assert output == "match=false"


def test_a_lock_hidden_among_many_safe_files_still_blocks(tmp_path: Path) -> None:
    """The realistic grouped-update shape: one lock among a crowd. A guard that
    judged the PR by its majority would wave this through."""
    files = [f"docs/generated/safe-{i:03}.md" for i in range(20)]
    files.insert(11, "apps/backend-rag/requirements-prod.lock.txt")
    result, output = _evaluate_paths(tmp_path, expected_count=len(files), files=files)
    assert result.returncode == 0, result.stderr
    assert output == "match=false"


# --------------------------------------------------------------- INNOCENCE
@pytest.mark.parametrize(
    "innocent",
    [
        "apps/backend-rag/requirements.txt",
        "apps/backend-rag/requirements-prod.txt",
        "apps/backend-rag/requirements-test.txt",
        "package-lock.json",
        "apps/mouth/package-lock.json",
        "apps/backend-rag/nested/requirements.lock.txt",
        "docs/how-we-compile-the-lock.txt.md",
    ],
)
def test_the_lock_pattern_does_not_over_match(tmp_path: Path, innocent: str) -> None:
    """Anchored at both ends. A source manifest, an npm lockfile (guarded by
    npm-lock-sync, not by this list), a nested path, and a doc that merely talks
    about locks must all stay eligible — a pattern that swallowed them would
    disarm auto-merge repo-wide while looking like a fix (superscar #3, the
    over-match side)."""
    result, output = _evaluate_paths(tmp_path, expected_count=1, files=[innocent])
    assert result.returncode == 0, result.stderr
    assert output == "match=true", f"{innocent} must remain auto-merge eligible"
