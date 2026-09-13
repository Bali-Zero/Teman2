#!/usr/bin/env python3
"""install_hook_diet.py — idempotent installer for the per-call hook diet.

PROBLEM (measured 2026-09-09, Pro): every Bash tool call fired a double-digit
number of PreToolUse+PostToolUse hook processes, three of them separate
inline PostToolUse Bash/'' loggers doing overlapping I/O — one appending
~/.claude/command-history.log, one building a {cmd,cwd} JSON piped into
~/.claude/scripts/hotfix-notify.sh, one rewriting ~/.claude/live-status.json
on every tool call — plus a SessionStart inline that cats ~20KB of
~/.nuzantara-repomap.txt into every session regardless of whether the
session needs it.

This installer, run once per machine (`python3 infra/claude-hooks/install_hook_diet.py`):

  1. Backs up ~/.claude/settings.json to `<name>.bak-hookdiet-<ts>`.
  2. Removes the three inline PostToolUse loggers and registers ONE
     `bash ~/.claude/hooks/bash_call_log.sh` on PostToolUse matcher "Bash"
     instead — that script does all three jobs in one process (see its own
     header for exactly what changes and what stays byte-identical).
  3. Removes the SessionStart "repomap-inject" inline. No replacement is
     registered: the repomap stays on disk at ~/.nuzantara-repomap.txt,
     read on demand (`cat ~/.nuzantara-repomap.txt`) instead of injected
     into every session.
  4. Copies bash_call_log.sh + redact_secrets.py into ~/.claude/hooks/
     (mode 0700).
  5. Prints a before/after count of hooks that fire per Bash tool call:
     every PreToolUse+PostToolUse group whose matcher is "", "*", or
     contains "Bash".

Idempotent: step 2/3's marker search finds nothing left to remove on a
second run, step 2's registration check finds the new command already
present, so a second run reports "already installed" and does not touch
settings.json again (no new backup, no rewrite). The hook-file copy step
always re-runs (copying an identical file is a no-op in effect).

Usage:
    python3 infra/claude-hooks/install_hook_diet.py [--dry-run]
    python3 infra/claude-hooks/install_hook_diet.py --settings PATH --hooks-dir DIR   # testing

--dry-run prints the plan and the before/after count without writing
anything (no backup, no settings.json edit, no file copy).
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

DEFAULT_SETTINGS = Path.home() / ".claude" / "settings.json"
DEFAULT_HOOKS_DIR = Path.home() / ".claude" / "hooks"
_THIS_DIR = Path(__file__).resolve().parent
SCRIPT_SRC = _THIS_DIR / "bash_call_log.sh"
REDACT_SRC = _THIS_DIR / "redact_secrets.py"
REPOMAP_PATH = Path.home() / ".nuzantara-repomap.txt"

NEW_COMMAND = "bash ~/.claude/hooks/bash_call_log.sh"

COMMAND_HISTORY_MARKER = "command-history.log"
HOTFIX_MARKER = "hotfix-notify.sh"
LIVE_STATUS_MARKER = "live-status.json"
REPOMAP_MARKER = "repomap-inject"


def _matches_bash(matcher: str | None) -> bool:
    matcher = matcher or ""
    return matcher == "" or matcher == "*" or "Bash" in matcher


def count_bash_hooks(hooks: dict) -> int:
    """Hooks that fire per Bash tool call: PreToolUse+PostToolUse groups
    whose matcher is '', '*', or contains 'Bash' (substring, e.g.
    'Bash|Edit|Write')."""
    total = 0
    for event in ("PreToolUse", "PostToolUse"):
        for group in hooks.get(event, []):
            if _matches_bash(group.get("matcher")):
                total += len(group.get("hooks", []))
    return total


def _already_installed(hooks: dict) -> bool:
    for group in hooks.get("PostToolUse", []):
        if group.get("matcher") == "Bash":
            for h in group.get("hooks", []):
                if NEW_COMMAND in h.get("command", ""):
                    return True
    return False


def strip_inline_loggers(hooks: dict) -> list[str]:
    """Remove the 3 inline PostToolUse loggers; drop any group left empty.

    Returns the labels of what was actually removed (empty on a no-op run).
    """
    removed: list[str] = []
    kept_groups = []
    for group in hooks.get("PostToolUse", []):
        kept_hooks = []
        for h in group.get("hooks", []):
            cmd = h.get("command", "")
            if COMMAND_HISTORY_MARKER in cmd and ">>" in cmd:
                removed.append("command-history-logger")
                continue
            if HOTFIX_MARKER in cmd:
                removed.append("hotfix-jsonl-builder")
                continue
            if LIVE_STATUS_MARKER in cmd and "printf" in cmd:
                removed.append("live-status-logger")
                continue
            kept_hooks.append(h)
        if kept_hooks:
            new_group = dict(group)
            new_group["hooks"] = kept_hooks
            kept_groups.append(new_group)
    hooks["PostToolUse"] = kept_groups
    return removed


def strip_repomap_inline(hooks: dict) -> bool:
    """Remove the SessionStart repomap-inject inline. Returns True if found."""
    removed = False
    for group in hooks.get("SessionStart", []):
        kept_hooks = []
        for h in group.get("hooks", []):
            if REPOMAP_MARKER in h.get("command", ""):
                removed = True
                continue
            kept_hooks.append(h)
        group["hooks"] = kept_hooks
    return removed


def register_bash_call_log(hooks: dict) -> bool:
    """Append the single consolidated registration. Returns True if added."""
    if _already_installed(hooks):
        return False
    hooks.setdefault("PostToolUse", []).append(
        {"matcher": "Bash", "hooks": [{"type": "command", "command": NEW_COMMAND}]}
    )
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="print the plan, write nothing")
    ap.add_argument("--settings", type=Path, default=DEFAULT_SETTINGS)
    ap.add_argument("--hooks-dir", type=Path, default=DEFAULT_HOOKS_DIR)
    args = ap.parse_args()

    settings_path: Path = args.settings
    if not settings_path.exists():
        print(f"ERROR: settings file not found: {settings_path}")
        raise SystemExit(1)

    data = json.loads(settings_path.read_text())
    hooks = data.setdefault("hooks", {})

    before_count = count_bash_hooks(hooks)

    removed = strip_inline_loggers(hooks)
    repomap_removed = strip_repomap_inline(hooks)
    added = register_bash_call_log(hooks)

    after_count = count_bash_hooks(hooks)
    already_clean = not removed and not repomap_removed and not added

    print("== per-call hook diet ==")
    if removed:
        print(f"  - remove inline PostToolUse loggers: {', '.join(sorted(set(removed)))}")
    if repomap_removed:
        print("  - remove SessionStart repomap-inject")
    if added:
        print(f"  - register PostToolUse matcher=Bash -> {NEW_COMMAND}")
    if already_clean:
        print("  - (no-op — already installed)")
    print(f"  hooks firing per Bash call: {before_count} -> {after_count}")
    print(f"  repomap on demand: cat {REPOMAP_PATH}  (no longer auto-injected at SessionStart)")

    if args.dry_run:
        print("  (dry-run: no files written)")
        return

    if not already_clean:
        ts = time.strftime("%Y%m%d-%H%M%S")
        backup_path = settings_path.with_name(settings_path.name + f".bak-hookdiet-{ts}")
        shutil.copy2(settings_path, backup_path)
        settings_path.write_text(json.dumps(data, indent=2) + "\n")
        print(f"  backup: {backup_path}")
    else:
        print("  settings.json unchanged (already installed)")

    args.hooks_dir.mkdir(parents=True, exist_ok=True)
    for src in (SCRIPT_SRC, REDACT_SRC):
        dst = args.hooks_dir / src.name
        shutil.copy2(src, dst)
        dst.chmod(0o700)
        print(f"  installed {dst}")


if __name__ == "__main__":
    main()
