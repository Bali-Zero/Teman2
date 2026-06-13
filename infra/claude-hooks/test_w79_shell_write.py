#!/usr/bin/env python3
"""W79 regression test — shell file-write into main checkout detection.

Tests worktree_isolation._write_hits_main against realistic commands. We monkeypatch
REPO_ROOT and the worktree resolver to a controlled temp layout so the test is
machine-independent.

    python3 infra/claude-hooks/test_w79_shell_write.py

Exit 0 = all pass, exit 1 = at least one mismatch.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent


def _load_mod():
    spec = importlib.util.spec_from_file_location("wi", str(HERE / "worktree_isolation.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = _load_mod()
    tmp = pathlib.Path(tempfile.mkdtemp())
    main_checkout = tmp / "nuzantara"
    worktree = main_checkout / ".worktrees" / "lane-x"
    (main_checkout / "apps").mkdir(parents=True)
    worktree.mkdir(parents=True)

    # point the hook at our fake layout
    mod.REPO_ROOT = str(main_checkout)
    # worktree resolver: only paths under the .worktrees dir are "allowed"
    def _fake_allowed(path_str: str) -> bool:
        if not path_str:
            return False
        try:
            p = pathlib.Path(mod.os.path.expanduser(path_str))
            if not p.is_absolute():
                return False
            p = p.resolve()
        except Exception:
            return False
        try:
            return p.is_relative_to(worktree.resolve())
        except Exception:
            return False
    mod._is_path_in_allowed_worktree = _fake_allowed

    M = str(main_checkout)
    W = str(worktree)
    HOME = str(tmp / "home")

    # (command, cwd, expect_block)
    CASES = [
        # MUST BLOCK — write lands in main checkout
        (f'echo "x" > {M}/apps/f.py', M, True),
        (f'echo "x" >> {M}/CLAUDE.md', "/tmp", True),
        (f'tee {M}/apps/g.py', M, True),
        (f'sed -i "s/a/b/" {M}/apps/f.py', M, True),
        (f'cp /tmp/src {M}/apps/dest.py', M, True),
        (f'mv /tmp/src {M}/apps/dest.py', M, True),
        (f'dd if=/tmp/x of={M}/apps/img', M, True),
        # relative target resolved against cwd=main
        ('echo "x" > apps/f.py', M, True),
        # MUST ALLOW — write lands in a worktree (the whole point of phase-free work)
        (f'echo "x" > {W}/apps/f.py', W, False),
        ('echo "x" > apps/f.py', W, False),
        (f'sed -i "s/a/b/" {W}/file.py', W, False),
        # MUST ALLOW — write outside the repo entirely
        ('echo "x" > /tmp/scratch.txt', "/tmp", False),
        (f'echo "x" > {HOME}/notes.md', HOME, False),
        ('echo "ok" > /dev/null', M, False),       # /dev/null sink
        ('cat f.py | grep x > /dev/null 2>&1', M, False),
        # MUST ALLOW — no write at all
        ("cat apps/f.py", M, False),
        ("grep -rn foo apps/", M, False),
        ("ls -la", M, False),
        # redirect of stderr/fd must not be a target
        ("python x.py 2>&1 | tail", M, False),
    ]

    fails = 0
    for cmd, cwd, expect in CASES:
        got = mod._write_hits_main(cmd, cwd) is not None
        status = "OK  " if got == expect else "FAIL"
        if got != expect:
            fails += 1
            print(f"  [{status}] block={got!s:5} expect={expect!s:5}  cwd={cwd[:18]:18}  {cmd}")

    # --- W79 path-allowlist: the REAL _is_path_in_allowed_worktree (NOT monkeypatched)
    # must allow REPO_ROOT/.worktrees/<x> even if not a git-registered worktree.
    mod2 = _load_mod()
    mod2.REPO_ROOT = str(main_checkout)
    wt_path = f"{main_checkout}/.worktrees/lane-y/apps/f.py"
    main_path = f"{main_checkout}/apps/f.py"
    REAL_CASES = [
        ("real-allowlist .worktrees", mod2._is_path_in_allowed_worktree(wt_path), True),
        ("real-allowlist main file",  mod2._is_path_in_allowed_worktree(main_path), False),
    ]
    for name, got, expect in REAL_CASES:
        if got != expect:
            fails += 1
            print(f"  [FAIL] got={got!s:5} expect={expect!s:5}  {name}")

    total = len(CASES) + len(REAL_CASES)
    if fails:
        print(f"\n=== {fails}/{total} FAIL ===")
        return 1
    print(f"=== ALL {total} PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
