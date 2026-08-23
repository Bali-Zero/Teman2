#!/bin/bash
# install_mailbox_hook.sh — install mailbox_inject.py (PostToolUse/Stop) into
# ~/.claude/hooks/, register it in ~/.claude/settings.json, create the mailbox
# root dir, then SELF-VERIFY against the INSTALLED copy and roll back if red.
#
# Idempotent. Backs up any file it overwrites (settings.json included).
#
# Run on each machine:
#   bash infra/claude-hooks/install_mailbox_hook.sh
#
# Kill switch after install: NUZ_MAILBOX_OFF=1
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HOME/.claude/hooks"
TS="$(date +%Y%m%d-%H%M%S)"
HOOK_NAME="mailbox_inject.py"
MAILBOX_ROOT="$HOME/.nuzantara-mailbox"

mkdir -p "$DST"

BACKUP=""
NEW_FILE=0
DST_HOOK="$DST/$HOOK_NAME"
if [ -f "$DST_HOOK" ]; then
    if ! diff -q "$SRC/$HOOK_NAME" "$DST_HOOK" >/dev/null 2>&1; then
        cp -p "$DST_HOOK" "$DST_HOOK.bak-pre-mailbox-$TS"
        BACKUP="$DST_HOOK.bak-pre-mailbox-$TS"
        echo "  backed up existing $HOOK_NAME -> $HOOK_NAME.bak-pre-mailbox-$TS"
    fi
else
    NEW_FILE=1
fi

echo "== installing $HOOK_NAME into $DST =="
cp "$SRC/$HOOK_NAME" "$DST_HOOK"
chmod 700 "$DST_HOOK"
echo "  installed $HOOK_NAME"

echo "== creating mailbox root =="
mkdir -p "$MAILBOX_ROOT/broadcast"
chmod 700 "$MAILBOX_ROOT"
echo "  $MAILBOX_ROOT (mode 700, broadcast/ ready)"

echo "== registering PostToolUse + Stop in settings.json =="
python3 - <<'PY'
import json, os, pathlib, shutil, time
p = pathlib.Path.home() / ".claude" / "settings.json"
if not p.exists():
    print("  WARN: settings.json missing — skip mailbox registration")
    raise SystemExit(0)
s = json.loads(p.read_text())
cmd = "python3 ~/.claude/hooks/mailbox_inject.py"
changed = False
backed_up = False

def ensure(event, matcher_needed):
    global changed, backed_up
    group = s.setdefault("hooks", {}).setdefault(event, [])
    if any(cmd in hh.get("command", "") for g in group for hh in g.get("hooks", [])):
        print(f"  {event}: already registered")
        return
    if not backed_up:
        shutil.copy2(p, p.with_name(p.name + f".bak-pre-mailbox-{time.strftime('%Y%m%d-%H%M%S')}"))
        backed_up = True
    entry = {"hooks": [{"type": "command", "command": cmd, "timeout": 5}]}
    if matcher_needed:
        entry = {"matcher": "", **entry}
    group.append(entry)
    changed = True
    print(f"  {event}: registered")

ensure("PostToolUse", True)
ensure("Stop", False)
if changed:
    p.write_text(json.dumps(s, indent=2))
PY

echo "== self-verify: running the test suite against the INSTALLED copy =="
if MAILBOX_HOOK_PATH="$DST_HOOK" python3 "$SRC/test_mailbox_inject.py"; then
    echo "== VACCINE GREEN — mailbox_inject.py installed and proven. =="
    echo "   Reload hooks with /hooks (or restart the session)."
    echo "   Kill switch: NUZ_MAILBOX_OFF=1"
    exit 0
fi

echo "== VACCINE RED — rolling back =="
if [ -n "$BACKUP" ]; then
    cp -p "$BACKUP" "$DST_HOOK"
    echo "  restored $HOOK_NAME from backup"
elif [ "$NEW_FILE" -eq 1 ]; then
    rm -f "$DST_HOOK"
    echo "  removed newly-installed $HOOK_NAME (had no prior version to restore)"
fi
echo "== rollback complete. Investigate test_mailbox_inject.py failures before retrying. =="
exit 1
