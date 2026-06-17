#!/usr/bin/env python3
"""W83 regression test — remote-dispatch + cd-into-worktree over-match fix.

Superscar #3 (guard-over-match). Before W83 the worktree-isolation hook produced
three live false BLOCKs in one session:

  1. `ssh pro git pull`     — a git op carried to ANOTHER host; this checkout is
                              never touched, yet the bare `git pull` tripped the
                              block.
  2. `cd <worktree> && git checkout -b x` — legitimate (the cd retargets to a
                              worktree) but Bash resets cwd to the main checkout
                              before running, so the effective target fell back
                              to main → false block.
  3. a git verb appearing only inside a quoted string / heredoc body (text, not a
                              real command).

W83 adds: `_is_remote_dispatch` (ssh/scp/rsync short-circuit to ALLOW), and runs
the existing `_strip_noise` (heredoc + quote stripping) BEFORE the git scan and
target resolution so quoted/heredoc git-verbs are not seen as commands. The
mirror duty (W79's `_write_hits_main`) is unchanged.

This test exercises the W83 units machine-independently (REPO_ROOT + the worktree
resolver are monkeypatched to a temp layout, like test_w79_shell_write.py).

    python3 infra/claude-hooks/test_w83_remote_dispatch.py

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
    worktree.mkdir(parents=True)
    mod.REPO_ROOT = str(main_checkout)

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
            return p.is_relative_to(wt_root)
        except Exception:
            return False

    mod._is_path_in_allowed_worktree = _fake_allowed

    M = str(main_checkout)
    W = str(worktree)
    fails = 0

    # --- Unit 1: _is_remote_dispatch — recognise ssh/scp/rsync carriers ---
    # (command, expect_remote)
    REMOTE_CASES = [
        # GUILT (real off-box dispatch → must be detected, hook ALLOWs)
        ("ssh pro git pull", True),
        ("ssh pro 'git reset --hard'", True),
        ("scp file pro:/tmp/x", True),
        ("rsync -a ./a pro:/b", True),
        ("foo | ssh pro git pull", True),          # ssh STARTS the post-pipe segment
        # INNOCENCE (local git op → must NOT be exempted, hook proceeds to block)
        ("git pull", False),                       # local — not a dispatch
        ("cd /x && git reset --hard", False),      # local
        ("echo ssh is mentioned here", False),     # 'ssh' only a word arg to echo
        ("mysshscript run", False),                # 'ssh' inside a longer token
        # THE DANGEROUS over-match this fix closes: a destructive LOCAL git op in
        # the same line as a mention of ssh must NOT be exempted off-box.
        ("echo ssh && git reset --hard", False),
        ("echo via ssh; git checkout main", False),
    ]
    for cmd, expect in REMOTE_CASES:
        got = mod._is_remote_dispatch(mod._strip_noise(cmd))
        if got != expect:
            fails += 1
            print(f"  [FAIL] remote={got!s:5} expect={expect!s:5}  {cmd}")

    # --- Unit 2: _strip_noise — git verbs inside quotes/heredoc are not commands ---
    # After stripping, the blocked-subcmd regex must NOT match a quoted git verb.
    NOISE_CASES = [
        # (command, expect_blocked_subcmd_present_after_strip)
        # `git commit -m "..."` (no -a/-am/--all) is NOT a blocked subcmd — only
        # commit -a / -am / --all is. After stripping the quoted message it stays
        # a plain `git commit`, so BLOCKED_SUBCMD_RE correctly does NOT match.
        ('git commit -m "rebase the docs later"', False),
        ('git commit -am "wip"', True),                    # -am IS blocked, survives strip
        ('git reset --hard', True),                        # real blocked subcmd survives
        ('echo "git reset --hard is dangerous"', False),   # quoted → stripped
        ("printf 'git checkout main'", False),             # quoted → stripped
        ('grep "git pull" docs/', False),                  # quoted arg → stripped
    ]
    for cmd, expect in NOISE_CASES:
        scrubbed = mod._strip_noise(cmd)
        got = bool(mod.BLOCKED_SUBCMD_RE.search(scrubbed))
        if got != expect:
            fails += 1
            print(f"  [FAIL] subcmd-after-strip={got!s:5} expect={expect!s:5}  {cmd}  -> {scrubbed!r}")

    # --- Unit 3: _effective_git_target — cd <worktree> retargets off main ---
    # (command, default_cwd, expect_target_is_main)
    TARGET_CASES = [
        (f"cd {W} && git checkout -b x", M, False),   # cd into worktree → NOT main
        (f"cd {M} && git checkout -b x", M, True),    # cd into main → main
        ("git status", M, True),                      # no cd → default cwd (main)
        (f"git -C {W} reset --hard", M, False),       # -C worktree → NOT main
    ]
    for cmd, cwd, expect_main in TARGET_CASES:
        target = mod._effective_git_target(cmd, cwd)
        try:
            is_main = pathlib.Path(target).resolve() == main_checkout.resolve()
        except Exception:
            is_main = target == M
        if is_main != expect_main:
            fails += 1
            print(f"  [FAIL] target={target} is_main={is_main} expect_main={expect_main}  {cmd}")

    total = len(REMOTE_CASES) + len(NOISE_CASES) + len(TARGET_CASES)
    if fails:
        print(f"\n=== {fails}/{total} FAIL ===")
        return 1
    print(f"=== ALL {total} PASS ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
