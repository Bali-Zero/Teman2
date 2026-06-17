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
    wt_root = (main_checkout / ".worktrees").resolve()
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
            # mirror the real logic: anything under REPO_ROOT/.worktrees/<x> is allowed
            return p.is_relative_to(worktree.resolve()) or p.is_relative_to(wt_root)
        except Exception:
            return False
    mod._is_path_in_allowed_worktree = _fake_allowed

    M = str(main_checkout)
    W = str(worktree)
    HOME = str(tmp / "home")

    # (command, cwd, expect_block) — full trap table (/tmp/w79_trap_cases.md)
    CASES = [
        # MUST BLOCK — write lands in main checkout
        (f'echo x > {M}/apps/f.py', M, True),
        ('echo x >> CLAUDE.md', M, True),                       # relative → cwd=main
        (f'echo x | tee {M}/CLAUDE.md', M, True),
        ("sed -i 's/a/b/' apps/f.py", M, True),                 # relative → cwd=main
        ('cp /tmp/src apps/dest.py', M, True),
        ('dd if=/tmp/x of=apps/img', M, True),
        # MUST ALLOW — the false positives I actually hit (heredoc body + quoted msg)
        ("cat > /tmp/msg.txt <<'EOF'\nfix: _is_path_in_allowed_worktree > nothing\nredirect > file mention\nEOF", M, False),
        ('git commit -m "fix: _is_path_in_allowed_worktree > nothing"', M, False),
        ('git commit -m "redirect > file in the text"', M, False),
        ('echo "a > b" > /tmp/f', M, False),                    # > inside quotes is noise; real target /tmp
        ('grep ">" file.txt', M, False),                        # > is an arg to grep
        # MUST ALLOW — write outside repo / into scratch / sinks
        ('echo x > /tmp/scratch', "/tmp", False),
        (f'echo x > {HOME}/notes.md', M, False),
        (f'echo x > {M}/.worktrees/lane/f.py', M, False),       # scratch worktree
        ('python x.py 2>&1 | tail', M, False),                  # fd-dup
        ('echo ok > /dev/null', M, False),                      # sink
        # MUST ALLOW — no write at all
        ('cat apps/f.py', M, False),
        ('diff <(cat a) <(cat b)', M, False),                   # process substitution
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
