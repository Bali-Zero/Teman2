#!/usr/bin/env python3
"""Regression test for the 7th over-match of worktree_isolation.py (2026-09-09).

TRAUMA: an agent's read-only `git diff $(git merge-base origin/main $h) ...`
was blocked in the main checkout with "WORKTREE ISOLATION VIOLATION (Bash git
op in main)". MECHANISM: BLOCKED_SUBCMD_RE's `merge` alternative had no
trailing-hyphen guard (the sibling `stash` alternative already carries one,
W85) — `\\bmerge\\b` is satisfied by the word-to-punctuation transition into
"-base"/"-file"/"-tree", so those distinct, read-only-or-informational git
subcommands were judged as `git merge` on a shared prefix alone (superscar
#3: guard-over-match). Read-only git verbs cannot race with another agent, so
blocking them forced a worktree just to READ.

CURE, widened in the same PR (Zero ruling 2026-09-09): an explicit read-only
allowlist for diff/log/show/status/rev-parse/merge-base/cat-file/ls-files/
ls-tree/blame/describe/rev-list/name-rev/branch(read forms)/remote -v/tag
(listing)/shortlog/grep/for-each-ref/config --get|--list/fetch/worktree list/
stash list/reflog — none of which were ever in BLOCKED_SUBCMD_RE, so BOTH
their read and write forms were silently allowed before this PR. Opening the
read forms without giving each verb's WRITE form its own block would have
widened a hole while documenting it as a feature: BRANCH_WRITE_RE,
TAG_INVOCATION_RE + `_tag_is_write`, CONFIG_SET_RE and DIFF_OUTPUT_RE (all in
worktree_isolation.py) close that, folded into `_git_verb_verdict`'s existing
`blocked_matches` list via `_extra_write_verdicts` — no new decision path.

This file unit-tests the PURE functions directly (fast, no subprocess); the
full hook-as-subprocess contract for the same shapes is also pinned in
test_hook_innocence.py (CASES["worktree_isolation.py"]) and the regex-only
view in test_block_regex.py (BLOCKED_SUBCMD_RE). guard_fuzz_harness.py's
445-case corpus is unaffected by this change (0 unexplained mismatches,
verified before this PR shipped).

Run:  python3 infra/claude-hooks/test_readonly_git_verbs.py
      pytest infra/claude-hooks/test_readonly_git_verbs.py -q
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_wi():
    spec = importlib.util.spec_from_file_location(
        "wi_readonly_test", str(HERE / "worktree_isolation.py")
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    mod.REPO_ROOT = "/synthetic-main"  # never resolved on disk in these cases
    return mod


MOD = _load_wi()


# ---------------------------------------------------------------------------
# _git_verb_verdict: the exact reported command + the read-only allowlist.
# Every case here resolves the effective target to REPO_ROOT itself (no -C,
# no cd), so "no_blocked_verb" IS the innocence signal and "block" IS guilt.
# ---------------------------------------------------------------------------
INNOCENCE_VERDICT_CASES = {
    # the exact command reported blocked 2026-09-09
    "git diff $(git merge-base origin/main HEAD) HEAD -- infra/claude-hooks/worktree_isolation.py": True,
    "git merge-base origin/main HEAD": True,
    "git merge-file a b c": True,
    "git merge-tree base a b": True,
    "git diff HEAD": True,
    "git log --oneline -5": True,
    "git show HEAD~1": True,
    "git status": True,
    "git rev-parse --show-toplevel": True,
    "git cat-file -p HEAD": True,
    "git ls-files": True,
    "git ls-tree HEAD": True,
    "git blame README.md": True,
    "git describe --tags": True,
    "git rev-list --count HEAD": True,
    "git name-rev HEAD": True,
    "git branch --list": True,
    "git branch": True,
    "git branch -a": True,
    "git branch -r": True,
    "git branch --show-current": True,
    "git remote -v": True,
    "git tag": True,
    "git tag -l": True,
    "git tag -l 'v1.*'": True,
    "git shortlog -sn": True,
    "git grep TODO": True,
    "git for-each-ref": True,
    "git config --get user.name": True,
    "git config --list": True,
    "git config -l": True,
    "git fetch origin": True,
    "git worktree list": True,
    "git stash list": True,
    "git stash show": True,
    "git reflog": True,
    # compound: only read-only gits anywhere in the command → allowed
    "git log --oneline; git diff --stat $(git merge-base main HEAD)": True,
}

GUILT_VERDICT_CASES = {
    # pre-existing blocked verbs must be untouched by this PR
    "git merge origin/main": False,
    "git merge --no-ff feature": False,
    "git checkout main": False,
    "git reset --hard": False,
    "git stash": False,
    # newly-blocked writing siblings of the newly-opened read verbs
    "git branch -d old-feature": False,
    "git branch -D old-feature": False,
    "git branch -m old new": False,
    "git branch -M old new": False,
    "git branch --delete old-feature": False,
    "git branch --move old new": False,
    "git tag v1.2.3": False,
    "git tag -d v1.2.3": False,
    "git config user.email x@balizero.com": False,
    "git config --unset user.email": False,
    "git diff --output=/tmp/x.patch HEAD": False,
    "git diff HEAD --output=/tmp/x.patch": False,
    "git diff --output /tmp/x.patch HEAD": False,
    # compound: a read-only git chained with a blocked one still blocks
    "git log --oneline && git branch -d stale": False,
    "git status; git tag v9.9.9": False,
    "git diff HEAD && git config user.email x@balizero.com": False,
}


def _run_verdict_cases(cases: dict[str, bool], expect_allow: bool) -> list[str]:
    failures = []
    for cmd, _ in cases.items():
        v = MOD._git_verb_verdict(cmd, MOD.REPO_ROOT)
        allowed = v.decision != "block"
        if allowed != expect_allow:
            failures.append(
                f"expected {'ALLOW' if expect_allow else 'BLOCK'}, "
                f"got decision={v.decision!r} for: {cmd}"
            )
    return failures


def test_readonly_verbs_are_allowed_including_the_reported_command():
    failures = _run_verdict_cases(INNOCENCE_VERDICT_CASES, expect_allow=True)
    assert not failures, "\n".join(failures)


def test_writing_siblings_and_preexisting_verbs_still_block():
    failures = _run_verdict_cases(GUILT_VERDICT_CASES, expect_allow=False)
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# _tag_is_write: the stateful helper CONFIG_SET_RE/BRANCH_WRITE_RE don't need
# (tag's -l/--list takes a glob-PATTERN positional that looks identical to a
# create-target positional — a plain regex can't tell them apart).
# ---------------------------------------------------------------------------
def test_tag_is_write_distinguishes_listing_from_create_and_delete():
    assert MOD._tag_is_write("") is False                      # bare `git tag`
    assert MOD._tag_is_write(" -l") is False                   # `-l` alone
    assert MOD._tag_is_write(" -l ''") is False                # `-l` + stripped glob pattern
    assert MOD._tag_is_write(" --list") is False
    assert MOD._tag_is_write(" v1.2.3") is True                 # create
    assert MOD._tag_is_write(" -d v1.2.3") is True              # delete
    assert MOD._tag_is_write(" --delete v1.2.3") is True


if __name__ == "__main__":
    fails = []
    fails += _run_verdict_cases(INNOCENCE_VERDICT_CASES, expect_allow=True)
    fails += _run_verdict_cases(GUILT_VERDICT_CASES, expect_allow=False)
    try:
        test_tag_is_write_distinguishes_listing_from_create_and_delete()
    except AssertionError as e:
        fails.append(f"_tag_is_write: {e}")
    total = len(INNOCENCE_VERDICT_CASES) + len(GUILT_VERDICT_CASES) + 1
    if fails:
        print(f"=== {len(fails)}/{total} FAIL ===")
        for f in fails:
            print("  [FAIL] " + f)
        sys.exit(1)
    print(f"=== ALL {total} PASS ===")
    sys.exit(0)
