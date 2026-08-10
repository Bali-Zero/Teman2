#!/usr/bin/env python3
"""Prove that the INSTALLED hook — not the repo copy — actually bites.

WHY THIS EXISTS (and why CI cannot do its job)
----------------------------------------------
Every suite under this directory tests the file in the REPOSITORY. The file that
decides anything is `~/.claude/hooks/worktree_isolation.py`, a REAL FILE that
`install_worktree_hooks.sh` copies there. So a merged cure and an armed cure are
two different states (W81), and the gap is per-machine and invisible: on
2026-08-10 Pro's live copy already matched merged main while M5's was 55 commits
behind on that file and had zero occurrences of the new channel.

`lint_home_fork.py` answers "do the two copies differ?" — which is necessary and
not sufficient: two copies can agree on a version whose guard never fires. This
script answers the only question that matters after an install: fed the real
PreToolUse payload, does the installed file BLOCK the guilty and SPARE the door?

WHY IT FEEDS PAYLOADS INSTEAD OF RUNNING THE COMMANDS
-----------------------------------------------------
The canonical W117 case is `ssh pro 'cd ~/nuzantara && git reset --hard'`. Running
it "to see whether the guard stops it" makes the probe the second injury on every
machine where the guard is missing — which is precisely the population this script
exists to find. So it never executes a git command: it invokes the hook the way
Claude Code does (JSON on stdin, non-zero exit = block) and reads the verdict.

Run after every install, on the machine you just installed:
    python3 infra/claude-hooks/prove_live_installed_hook.py
Optionally: ... <hook-path> <main-checkout>

Exit 0 = armed and proven. Exit 1 = the installed file disagrees with its corpus.
Exit 2 = there is no installed file to judge (absence is not innocence, W84).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

DEFAULT_HOOK = os.path.expanduser("~/.claude/hooks/worktree_isolation.py")
DEFAULT_MAIN = os.path.expanduser("~/nuzantara")

# (command, must_block, label)
CASES: list[tuple[str, bool, str]] = [
    # ── W117: the ssh-dispatched discard of a MAIN checkout (the gesture that
    #    destroyed 159 dedup entries + 24 escalations before this channel existed)
    ("ssh pro 'cd {main} && git reset --hard origin/main'", True, "W117 the exact gesture"),
    ("ssh pro 'cd ~/nuzantara && git reset --hard origin/main'", True, "W117 tilde spelling"),
    ('ssh mini "cd ~/nuzantara && git checkout -- ."', True, "W117 checkout -- ."),
    ("ssh pro 'cd ~/nuzantara && git clean -fdx'", True, "W117 clean -fdx"),
    ("ssh pro 'git -C ~/nuzantara restore .'", True, "W117 git -C restore"),
    ("ssh pro 'cd ~/nuzantara && git stash'", True, "W117 mutating stash"),
    # ── the LEGITIMATE door: this is how a fleet checkout is realigned. A guard
    #    annoying enough to be disarmed turns a #3 into a #2, so innocence here
    #    is load-bearing, not politeness.
    ("ssh pro 'cd ~/nuzantara && git pull --ff-only'", False, "innocence: ff-only pull"),
    ("ssh pro 'cd ~/nuzantara && bash scripts/pro/pro-git-pull.sh'", False, "innocence: sanctioned puller"),
    ("ssh pro 'cd ~/nuzantara && git status --porcelain'", False, "innocence: status"),
    ("ssh pro 'cd ~/nuzantara && git stash list'", False, "innocence: stash list (W85)"),
    ("ssh pro 'cd {main}/.worktrees/ops-x && git reset --hard origin/main'", False,
     "innocence: discarding inside a WORKTREE is the agent's own business"),
    # ── the local class: `clean`/`restore` were never in the blocklist, so five
    #    shapes of the same damage passed in the main checkout. Both letter tests
    #    read the flag CLUSTER: `-fdn` IS a dry run.
    ("git clean -fd", True, "local: clean -fd"),
    ("git clean --force", True, "local: clean --force"),
    ("git restore apps/", True, "local: restore"),
    ("git clean -n", False, "local innocence: -n"),
    ("git clean -fdn", False, "local innocence: -fdn is a dry run"),
    ("git clean --dry-run", False, "local innocence: --dry-run"),
]


def verdict(hook: str, main: str, cmd: str) -> tuple[bool, str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": main})
    p = subprocess.run([sys.executable, hook], input=payload, capture_output=True, text=True)
    lines = (p.stderr or "").strip().splitlines()
    return p.returncode != 0, (lines[0] if lines else "")


def main() -> int:
    hook = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_HOOK
    checkout = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_MAIN

    if not os.path.isfile(hook):
        print(f"✗ no installed hook at {hook} — NOT armed on this machine.", file=sys.stderr)
        print("  Install it: bash infra/claude-hooks/install_worktree_hooks.sh", file=sys.stderr)
        return 2
    if os.environ.get("AGENT_WORKTREE_ENFORCEMENT", "").lower() == "false":
        # The kill switch makes every case pass; reporting that as green would be
        # the cleanest possible lie about an unarmed machine.
        print("✗ AGENT_WORKTREE_ENFORCEMENT=false is set: the hook exits 0 on everything.",
              file=sys.stderr)
        print("  Unset it before proving anything.", file=sys.stderr)
        return 2

    print(f"hook:     {hook}")
    print(f"checkout: {checkout}\n")
    fails = 0
    for template, must_block, label in CASES:
        cmd = template.format(main=checkout)
        blocked, why = verdict(hook, checkout, cmd)
        ok = blocked == must_block
        fails += 0 if ok else 1
        print(f"  [{'ok  ' if ok else 'FAIL'}] want={'BLOCK' if must_block else 'pass ' } "
              f"got={'BLOCK' if blocked else 'pass '}  {label}")
        if not ok:
            print(f"         cmd: {cmd}")
            print(f"         hook said: {why or '(silent)'}")

    print()
    if fails:
        print(f"=== {fails}/{len(CASES)} FAIL — the INSTALLED hook is not the cure this repo ships. ===",
              file=sys.stderr)
        print("Re-run: bash infra/claude-hooks/install_worktree_hooks.sh (from a checkout at origin/main)",
              file=sys.stderr)
        return 1
    print(f"=== ALL {len(CASES)} OK — installed hook bites the ssh-dispatched discard, spares the door. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
