#!/bin/bash
# install_subagent_stop_verify.sh — install the SubagentStop hook
# (subagent_stop_verify.py) into ~/.claude/hooks/ and register it in
# ~/.claude/settings.json under hooks.SubagentStop.
#
# Idempotent. Backs up any file it overwrites (.bak-pre-subagentstop-<ts>) and
# backs up settings.json before touching it. Self-verifies by running
# test_subagent_stop_verify.py against the just-installed copy; a red result
# rolls EVERYTHING back (hook file + settings.json) rather than leaving a
# broken guardian live (same discipline as install_worktree_hooks.sh).
#
# HOOK_STATE tri-state (P2-9 fix, cicatrix-superscar #2 "esiste != armato"):
#   new                    — no file pre-existed at $DST/$HOOK_NAME. On a
#                            failed self-verify, rollback REMOVES it (there
#                            was nothing there before this run).
#   backed_up              — a DIFFERENT file pre-existed. On a failed
#                            self-verify, rollback RESTORES the backup.
#   preexisting_identical  — a BYTE-IDENTICAL file pre-existed (the normal
#                            case on a fleet-sync re-run). On a failed
#                            self-verify, rollback LEAVES IT IN PLACE — it
#                            predates this run and this run changed nothing
#                            about its content; `rm -f`ing it here would
#                            destroy a live, healthy hook over what is most
#                            likely an environmental self-verify failure
#                            (not a content one), which is exactly the bug
#                            this fix closes.
#
# settings.json missing is FAIL-VISIBLE (P2-9 fix): registration silently not
# happening while the script still exits 0 is an "armamento sospeso" — the
# operator never sees that the hook is installed-but-NOT-registered. This now
# prints a clear FATAL and exits 1.
#
# Test hook: SUBAGENT_INSTALL_VERIFY_CMD overrides the self-verify command
# (default: `python3 "$SRC/test_subagent_stop_verify.py"`) so a test harness
# can force a self-verify failure deterministically and exercise the rollback
# branches above without depending on the real suite's pass/fail state.
#
# Run on each machine after merging:
#   bash infra/claude-hooks/install_subagent_stop_verify.sh
#
# Kill switches after install: SUBAGENT_STOP_VERIFY_OFF=1, or
# STOP_VERIFY_ALLOW_DIRTY=1 (shared with the Stop-hook sibling, T2.6).
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DST="$HOME/.claude/hooks"
SETTINGS="$HOME/.claude/settings.json"
TS="$(date +%Y%m%d-%H%M%S)"
HOOK_NAME="subagent_stop_verify.py"
HOOK_STATE="new"   # new | backed_up | preexisting_identical

mkdir -p "$DST"

echo "== installing $HOOK_NAME into $DST =="
if [ ! -f "$SRC/$HOOK_NAME" ]; then
    echo "  FATAL: $HOOK_NAME not found in repo dir $SRC"
    exit 1
fi
if [ -f "$DST/$HOOK_NAME" ]; then
    if diff -q "$SRC/$HOOK_NAME" "$DST/$HOOK_NAME" >/dev/null 2>&1; then
        HOOK_STATE="preexisting_identical"
        echo "  existing $HOOK_NAME is byte-identical to the repo copy — no backup needed"
    else
        cp "$DST/$HOOK_NAME" "$DST/$HOOK_NAME.bak-pre-subagentstop-$TS"
        HOOK_STATE="backed_up"
        echo "  backed up existing $HOOK_NAME -> $HOOK_NAME.bak-pre-subagentstop-$TS"
    fi
fi
cp "$SRC/$HOOK_NAME" "$DST/$HOOK_NAME"
chmod 700 "$DST/$HOOK_NAME"
echo "  installed $HOOK_NAME (state: $HOOK_STATE)"

echo "== registering SubagentStop in settings.json =="
SETTINGS_BACKED_UP=0
if [ ! -f "$SETTINGS" ]; then
    echo "  FATAL: $SETTINGS missing."
    echo "  $HOOK_NAME IS installed at $DST/$HOOK_NAME, but SubagentStop"
    echo "  registration did NOT happen — there is nothing to register it into."
    echo "  Create $SETTINGS first, then re-run this installer."
    exit 1
fi
REG_OUT="$(python3 - "$SETTINGS" "$TS" <<'PY'
import json, pathlib, shutil, sys, time

p = pathlib.Path(sys.argv[1])
ts = sys.argv[2]
s = json.loads(p.read_text())
group = s.setdefault("hooks", {}).setdefault("SubagentStop", [])
cmd = "python3 ~/.claude/hooks/subagent_stop_verify.py"

already = any(cmd in hh.get("command", "") for g in group for hh in g.get("hooks", []))
if already:
    print("ALREADY")
else:
    backup = p.with_name(p.name + f".bak-pre-subagentstop-{ts}")
    shutil.copy2(p, backup)
    group.append({"hooks": [{"type": "command", "command": cmd, "timeout": 10000}]})
    p.write_text(json.dumps(s, indent=2))
    print(f"REGISTERED:{backup}")
PY
)"
case "$REG_OUT" in
    ALREADY)
        echo "  SubagentStop already registered — no change"
        ;;
    REGISTERED:*)
        SETTINGS_BACKUP="${REG_OUT#REGISTERED:}"
        SETTINGS_BACKED_UP=1
        echo "  registered SubagentStop hook (backup: $SETTINGS_BACKUP)"
        ;;
    *)
        echo "  FATAL: settings.json registration failed: $REG_OUT"
        exit 1
        ;;
esac

echo "== self-verify: running test_subagent_stop_verify.py against the installed hook =="
# The suite invokes $SRC/subagent_stop_verify.py (the repo copy we just proved
# byte-identical to $DST/subagent_stop_verify.py above), so a green result here
# is a green result for what is now live in $DST.
SELF_VERIFY_OK=0
if [ -n "${SUBAGENT_INSTALL_VERIFY_CMD:-}" ]; then
    echo "  (SUBAGENT_INSTALL_VERIFY_CMD override in effect — using it instead of the real suite)"
    if bash -c "$SUBAGENT_INSTALL_VERIFY_CMD"; then
        SELF_VERIFY_OK=1
    fi
else
    if python3 "$SRC/test_subagent_stop_verify.py"; then
        SELF_VERIFY_OK=1
    fi
fi

if [ "$SELF_VERIFY_OK" = "1" ]; then
    echo "== SELF-VERIFY GREEN — hook installed and proven to bite only the guilty. =="
    echo "   Reload with /hooks (or restart the session)."
    echo "   Kill switches: SUBAGENT_STOP_VERIFY_OFF=1 / STOP_VERIFY_ALLOW_DIRTY=1"
    exit 0
fi

echo "== SELF-VERIFY RED — rolling back to avoid leaving a broken hook live =="
case "$HOOK_STATE" in
    backed_up)
        cp "$DST/$HOOK_NAME.bak-pre-subagentstop-$TS" "$DST/$HOOK_NAME"
        echo "  restored $DST/$HOOK_NAME from backup"
        ;;
    preexisting_identical)
        echo "  leaving pre-existing (byte-identical) $DST/$HOOK_NAME IN PLACE."
        echo "  It predates this run and this run changed nothing about its"
        echo "  content — removing it would destroy a live, healthy hook over"
        echo "  what is most likely an environmental self-verify failure, not"
        echo "  a content one."
        ;;
    new)
        rm -f "$DST/$HOOK_NAME"
        echo "  removed newly-installed $DST/$HOOK_NAME (there was nothing to restore)"
        ;;
esac
if [ "$SETTINGS_BACKED_UP" = "1" ] && [ -f "$SETTINGS_BACKUP" ]; then
    cp "$SETTINGS_BACKUP" "$SETTINGS"
    echo "  restored $SETTINGS from backup"
fi
echo "== rollback complete. Investigate test_subagent_stop_verify.py failures before retrying. =="
exit 1
