#!/usr/bin/env python3
"""W85 — BLOCKED_SUBCMD_RE stash guilt+innocence (over-match FIXED 2026-07-06).

W85 (cicatrix-scars.md, superscar #3): `BLOCKED_SUBCMD_RE` carried a bare
`stash`, so read-only `git stash list` / `git stash show` were blocked exactly
like the mutating `stash push` / `stash pop` — the third consecutive over-match
of the SAME guard in two days (after W83, W84).

HISTORY OF THIS FILE: it was born as a W82-style TRIPWIRE that PINNED the
documented-broken contract (green while the bug was present and captured,
failing loudly when the fix landed). The fix landed 2026-07-06 with operator
GO, folded into the repo copy AND the live ~/.claude/hooks copy in the same
operation (superscar #1, W83 GOTCHA-d: patch BOTH or neither). Per the pin's
own instructions it is now a plain guilt+innocence test:

  GUILT     (guard catches real danger): bare `git stash` (= stash push),
            `stash push/pop/apply/drop/clear/create/store/branch` ARE blocked.
  INNOCENCE (adjacent-legit passes): `git stash list` / `git stash show`
            (incl. flags/args) are NOT blocked; `stashes` as a word is not
            a token match.

    python3 infra/claude-hooks/test_w85_stash_readonly.py
Exit 0 = guard matches on intent (mutating) and spares read-only queries.
Exit 1 = regression on either side (went blind on guilt, or re-over-matches).

Reference: cicatrix-superscar.md #3 · registry: infra/guard-conformance/registry.json
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_regex():
    spec = importlib.util.spec_from_file_location("wi_w85", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod.BLOCKED_SUBCMD_RE


def main() -> int:
    regex = _load_regex()
    failures: list[str] = []

    # GUILT — every mutating stash form must still be blocked.
    for cmd in (
        "git stash",
        "git stash push",
        "git stash push -m wip",
        "git stash pop",
        "git stash apply",
        "git stash drop",
        "git stash clear",
        "git stash create",
        "git stash store abc123",
        "git stash branch fix/x",
        "git -C /tmp/repo stash pop",
    ):
        if not regex.search(cmd):
            failures.append(f"GUILT MISS: `{cmd}` no longer blocked — guard went blind")

    # INNOCENCE — read-only stash queries (the W85 hole, now fixed) must pass.
    for cmd in (
        "git stash list",
        "git stash list --stat",
        "git stash show",
        "git stash show -p stash@{0}",
    ):
        if regex.search(cmd):
            failures.append(f"INNOCENT BITTEN: `{cmd}` blocked — W85 over-match regressed")

    # INNOCENCE — token adjacency: 'stashes' is not the stash subcommand.
    if regex.search("echo git stashes are neat"):
        failures.append("INNOCENT BITTEN: substring `stashes` matched — word-boundary broken")

    if failures:
        print("W85 FAILED:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("OK (W85) — mutating stash blocked, read-only stash list/show pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
