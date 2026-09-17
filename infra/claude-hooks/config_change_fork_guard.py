#!/usr/bin/env python3
"""config_change_fork_guard.py — ConfigChange hook: arms superscar #1 at the
moment the drift is created instead of hours later.

WHY THIS EVENT. Scar #1 (HOME-fork drift) is cured today by a linter that runs
when someone remembers to run it: a hook edited in $HOME diverges from its
declared repo twin and nothing says so until `lint_home_fork.py --check` is
invoked. Claude Code fires `ConfigChange` when a config file is modified DURING a
session — which is exactly when a fork is born. This hook turns that moment into
a message the session can read.

CONSUMER (the Bites line for this file): the session itself. On a drifted pair it
returns `additionalContext` naming the file, so the session that just edited a
declared twin learns immediately, in its own context, that the repo copy no
longer matches. No cron, no future job.

CONTRACT. Advisory only: never blocks (ConfigChange can block, and this must not
— a config edit is not a policy violation). Exits 0 on every error path: a guard
that breaks sessions when it cannot run is worse than the drift it watches.
Bounded: only declared pairs whose live path was the file that changed, and the
comparison is a hash, never file content, so nothing from a settings file can
reach a log.
"""

from __future__ import annotations

import json
import hashlib
import os
import sys
from pathlib import Path

REPO = Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.home() / "nuzantara"))
PAIRS = REPO / "infra" / "home-fork" / "declared-pairs.json"


def sha(path: Path) -> str | None:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    changed = payload.get("file_path") or payload.get("path") or ""
    try:
        pairs = json.loads(PAIRS.read_text()).get("pairs", [])
    except Exception:
        return 0

    notes = []
    for pair in pairs:
        live = Path(os.path.expanduser(pair.get("live", "")))
        repo = REPO / pair.get("repo", "")
        # Only the pair that was just touched, and only if both sides exist.
        if changed and os.path.realpath(live) != os.path.realpath(changed):
            continue
        a, b = sha(live), sha(repo)
        if a and b and a != b:
            notes.append(
                f"[fork-guard] {pair['live']} no longer matches {pair['repo']} "
                f"(superscar #1). Cure the repo copy in the same change, or "
                f"`python3 scripts/lint_home_fork.py --check` will name it later."
            )
    if notes:
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "ConfigChange",
                        "additionalContext": " ".join(notes[:3]),
                    }
                }
            )
        )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        sys.exit(0)
