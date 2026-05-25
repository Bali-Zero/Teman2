#!/usr/bin/env python3
"""Idempotently add the repomap-inject hook to ~/.claude/settings.json.

Adds a SessionStart hook (matcher="") that cats ~/.nuzantara-repomap.txt
when it exists AND is <30min old.

Rerun-safe: if the hook is already present (matched by a unique marker
string in the command body), it is left untouched.
"""
import json
import os
import shutil
import sys

SETTINGS = os.path.expanduser("~/.claude/settings.json")
MARKER = "# repomap-inject SOTA L4 2026-05-24"

HOOK_CMD = """# repomap-inject SOTA L4 2026-05-24
if [[ -f ~/.nuzantara-repomap.txt ]]; then
    REPOMAP_AGE_S=$(( $(date +%s) - $(stat -f %m ~/.nuzantara-repomap.txt 2>/dev/null || echo 0) ))
    if (( REPOMAP_AGE_S < 1800 )); then
        echo ''
        echo "## Repo map (auto-injected, ${REPOMAP_AGE_S}s old)"
        cat ~/.nuzantara-repomap.txt
    fi
fi"""

with open(SETTINGS) as f:
    data = json.load(f)

hooks = data.setdefault("hooks", {})
session_start = hooks.setdefault("SessionStart", [])

# Locate the bucket with matcher="" (the catch-all)
target_bucket = None
for entry in session_start:
    if entry.get("matcher", None) == "":
        target_bucket = entry
        break

if target_bucket is None:
    # Create new catch-all bucket
    target_bucket = {"matcher": "", "hooks": []}
    session_start.append(target_bucket)

hook_list = target_bucket.setdefault("hooks", [])

# Idempotency: skip if marker already present
already_installed = any(
    isinstance(h, dict) and MARKER in h.get("command", "")
    for h in hook_list
)

if already_installed:
    print("[add_repomap_hook] hook already present — no change")
    sys.exit(0)

# Append our hook entry
hook_list.append({
    "type": "command",
    "command": HOOK_CMD,
    "statusMessage": "Injecting repo map (SOTA L4)...",
    "async": False
})

# Atomic write via tmp + rename
tmp = SETTINGS + ".tmp.repomap"
with open(tmp, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
shutil.move(tmp, SETTINGS)
print(f"[add_repomap_hook] installed hook into {SETTINGS}")
