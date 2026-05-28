#!/usr/bin/env python3
"""Patch 7 regression test: cd+rm bypass + quoted/absolute $HOME.
Runs the static evaluator as a subprocess (real hook path) with crafted
Bash payloads. Asserts BLOCK on the new bypass forms + ALLOW on legit ops.
"""
import json
import os
import subprocess
import sys

# The hook lives in the user-global ~/.claude tree (gitignored, NOT in this repo).
# Override with GUARDRAILS_STATIC_HOOK for a different machine/CI path.
HOOK = os.environ.get(
    "GUARDRAILS_STATIC_HOOK",
    os.path.expanduser("~/.claude/hooks/guardrails-static.py"),
)


def run(command: str) -> str:
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    p = subprocess.run(
        [sys.executable, HOOK],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return p.stdout.strip()


# (command, expected_prefix)  — BLOCK or ALLOW
CASES = [
    # --- NEW Patch-7 bypasses that MUST now BLOCK ---
    ("cd ~/Projects && rm -rf nuzantara", "BLOCK"),                 # the real 2026-05-28 bypass
    ("cd ~ && rm -rf .git", "BLOCK"),                               # cd home + rm relative
    ("cd $HOME && rm -rf Teman2", "BLOCK"),
    ("cd ${HOME} && rm -rf something", "BLOCK"),
    ("cd /Users/nuzantara && rm -rf x", "BLOCK"),
    ("cd / && rm -rf etc", "BLOCK"),
    ("cd ~/Projects ; rm -rf nuzantara", "BLOCK"),                  # semicolon variant
    ('rm -rf "$HOME"', "BLOCK"),                                    # quoted $HOME
    ("rm -rf ${HOME}", "BLOCK"),                                    # braced $HOME
    ("rm -rf ${HOME}/Projects", "BLOCK"),
    ("rm -rf /Users/nuzantara", "BLOCK"),                           # pre-expanded absolute home
    ("rm -rf /Users/nuzantara/Desktop", "BLOCK"),

    # --- legacy Patch-6 cases that must STILL block ---
    ("rm -rf /", "BLOCK"),
    ("rm -rf $HOME", "BLOCK"),
    ("rm -rf ~", "BLOCK"),
    ("rm -rf ~/something", "BLOCK"),

    # --- legit ops that must STILL be ALLOWED (no false positives) ---
    ("rm -rf /tmp/scratch-dir", "ALLOW"),                          # /tmp is fine
    ("rm -rf .worktrees/dead-lane", "ALLOW"),                      # relative non-cd
    ("rm -f ~/.claude/state/operator-presence.flag", "ALLOW"),    # rm -f (non-recursive) home file
    ("rm -rf node_modules", "ALLOW"),                             # plain relative
    ("cd /tmp/work && rm -rf build", "ALLOW"),                    # cd into NON-protected then rm
    ("cd apps/mouth && npm run build", "ALLOW"),                  # cd + non-rm
    ("ls -la ~/Projects", "ALLOW"),                              # not an rm at all
    ("git status", "ALLOW"),
]


def main() -> int:
    if not os.path.exists(HOOK):
        # Hook is user-global infra, not shipped in the repo. On a machine/CI
        # without it, skip rather than fail (exit 0). Set GUARDRAILS_STATIC_HOOK
        # to point at the hook to actually run the regression.
        print(f"SKIP: guardrails hook not found at {HOOK} (user-global infra)")
        return 0
    fails = 0
    for cmd, want in CASES:
        got = run(cmd)
        ok = got.startswith(want)
        if not ok:
            fails += 1
            print(f"FAIL  want={want:5} got={got!r:40} cmd={cmd!r}")
        else:
            print(f"ok    {want:5} :: {cmd}")
    print(f"\n{len(CASES) - fails}/{len(CASES)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
