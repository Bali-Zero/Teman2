#!/usr/bin/env python3
"""ff-only pull exception — guilt+innocence (2026-07-06, Zero directive).

The worktree_isolation hook blocks every mutating git op in the MAIN checkout
(superscar #5 sibling-race antidote). Zero's directive 2026-07-06: sessions must
be able to self-align the fleet's main checkouts without waiting for the
operator. The narrow exception: `git pull --ff-only` targeting main is allowed
IFF the main tree is clean of TRACKED modifications — the one mutating git op
that cannot race a sibling (HEAD moves forward only; git aborts the ff itself
if a tracked file would collide).

  GUILT     (the guard still bites): bare `git pull`, `pull --rebase`,
            compound `pull --ff-only && git checkout`, --ff-only hidden in a
            quoted literal, checkout/merge/stash — none open the exception;
            a tracked-dirty main keeps it shut; a failed probe keeps it shut
            (fail-closed: loosening on uncertainty would invert the guard).
  INNOCENCE (the exception opens): `git pull --ff-only [origin main]` and
            `git -C <main> pull --ff-only` on a tracked-clean tree pass;
            untracked files (scratch/) do not gate it.

    python3 infra/claude-hooks/test_ffonly_pull_exception.py
Exit 0 = exception opens only for the sibling-race-free op. Exit 1 = regression.

Reference: cicatrix-superscar.md #3/#5 · registry: infra/guard-conformance/registry.json
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def _load_module():
    spec = importlib.util.spec_from_file_location("wi_ffonly", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _git(repo: pathlib.Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True, capture_output=True, text=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
             "HOME": str(repo), "PATH": "/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"},
    )


def main() -> int:
    mod = _load_module()
    strip = mod._strip_noise
    only_pull = mod._only_ffonly_pull
    failures: list[str] = []

    # ---- GUILT: commands that must NOT open the exception -------------------
    guilty = [
        "git pull",                                            # no --ff-only
        "git pull origin main",                                # no --ff-only
        "git pull --rebase",                                   # rebase
        "git pull --rebase --ff-only",                         # rebase wins
        "git pull --ff-only && git checkout main",             # compound: checkout
        "git checkout feature && git pull --ff-only",          # compound: checkout
        "git merge origin/main",                               # not a pull at all
        "git stash && git pull --ff-only",                     # compound: stash push
        'echo "--ff-only" && git pull',                        # flag only in a quoted literal
        "git checkout x",                                      # no pull
        # 2026-07-06 live guilt-probe: a shell COMMENT mentioning --ff-only opened
        # the first version of this exception for a BARE pull (4th over-match of
        # this same guard, after W83/W84/W85). The flag must be a pull ARGUMENT.
        "# GUILT: pull nudo (senza --ff-only) test\ngit pull origin main",
        "git pull origin main  # next time use --ff-only",
        "echo done && git pull # --ff-only",
        "git pull; echo --ff-only",                            # flag in a LATER segment
        "git pull --ff-onlyx",                                 # (?!\\S): not the real flag
    ]
    for cmd in guilty:
        if only_pull(strip(cmd)):
            failures.append(f"GUILT: exception wrongly opens for: {cmd!r}")

    # ---- INNOCENCE: commands that must open the (command-side) exception ----
    innocent = [
        "git pull --ff-only",
        "git pull --ff-only origin main",
        "git pull origin main --ff-only",
        "git -C /Users/x/nuzantara pull --ff-only origin main",
        "cd /Users/x/nuzantara && git pull --ff-only",
        # comment elsewhere must not disqualify a REAL ff-only pull
        "git pull --ff-only origin main  # fleet self-align",
        "# align main\ngit pull --ff-only origin main",
    ]
    for cmd in innocent:
        if not only_pull(strip(cmd)):
            failures.append(f"INNOCENCE: exception fails to open for: {cmd!r}")

    # ---- tree-clean probe on a fixture repo ---------------------------------
    with tempfile.TemporaryDirectory() as td:
        repo = pathlib.Path(td) / "fixture"
        repo.mkdir()
        _git(repo, "init", "-q")
        (repo / "a.txt").write_text("one\n")
        _git(repo, "add", "a.txt")
        _git(repo, "commit", "-qm", "init")

        mod.REPO_ROOT = str(repo)  # point the probe at the fixture

        # clean tree → probe True (innocence)
        if not mod._main_tree_tracked_clean():
            failures.append("INNOCENCE: clean fixture tree reported dirty")

        # untracked file must NOT gate the exception (innocence)
        (repo / "scratch.txt").write_text("untracked\n")
        if not mod._main_tree_tracked_clean():
            failures.append("INNOCENCE: untracked file wrongly gates the probe")

        # tracked modification MUST gate it (guilt)
        (repo / "a.txt").write_text("two\n")
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: tracked-dirty tree reported clean")

        # probe failure → shut (guilt / fail-closed): nonexistent repo root
        mod.REPO_ROOT = str(pathlib.Path(td) / "does-not-exist")
        if mod._main_tree_tracked_clean():
            failures.append("GUILT: probe failure wrongly opens the exception")

    if failures:
        print("FAIL — ff-only pull exception regressions:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK — exception opens only for ff-only pull on a tracked-clean main "
          f"({len(guilty)} guilt + {len(innocent)} innocence + 4 probe cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
