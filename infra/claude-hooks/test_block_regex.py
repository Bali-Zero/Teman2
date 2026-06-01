#!/usr/bin/env python3
"""Regression test for worktree_isolation BLOCKED_SUBCMD_RE.

Imports the regex from the reference copy in this dir and asserts the
block/allow contract. Run after any edit to the regex:

    python3 infra/claude-hooks/test_block_regex.py

Exit 0 = all pass, exit 1 = at least one mismatch.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent


def _load_regex():
    spec = importlib.util.spec_from_file_location(
        "wi", str(HERE / "worktree_isolation.py")
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.BLOCKED_SUBCMD_RE


CASES = {
    # must BLOCK
    "git commit -a": True,
    'git commit -am "x"': True,
    'git commit -a -m "x"': True,
    'git commit --all -m "x"': True,
    "git add .": True,
    "git add -A": True,
    "git add --all": True,
    "git checkout main": True,
    "git stash": True,
    "git reset --hard": True,
    # must ALLOW
    'git commit -m "x"': False,
    'git commit -m "add a feature"': False,
    'git commit -m "amend the docs"': False,
    "git commit --amend": False,
    "git add path/to/file.py": False,
    "git add src/main.py README.md": False,
    "git status": False,
    "git log --oneline": False,
    "git diff HEAD": False,
    "git push origin feature": False,
}


def main() -> int:
    rx = _load_regex()
    fails = 0
    for cmd, expect in CASES.items():
        got = bool(rx.search(cmd))
        if got != expect:
            fails += 1
            print(f"  [FAIL] block={got!s:5} expect={expect!s:5}  {cmd}")
    if fails:
        print(f"\n=== {fails} FAIL ===")
        return 1
    print(f"=== ALL {len(CASES)} PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
