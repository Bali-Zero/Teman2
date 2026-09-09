#!/bin/bash
# window_jump.sh — the GESTURE of the window jump (macOS + Ghostty only).
#
# Spawned detached by context_window_guard.py the first time a session trips its
# context threshold (Ruling Zero 2026-09-09: "arrivati al contesto, scrivi
# l'handoff, incollalo in una finestra nuova e chiudi la tua" — automatic, no
# human). The CLI has no way to open a window or end a session from a hook
# (research/operations/2026-09-09-window-jump-automatic-handoff-it.md §2), so
# this script does both from outside: System Events for the window, and for the
# old session `/exit` typed into its window FIRST, then — measured 2026-09-09
# 12:53 on the live probe: three `/exit` keystrokes left the probe claude alive,
# two SIGINTs ended it — a SIGINT×2 fallback on the old claude PID (the guard's
# own parent, carried in the jump file as `from_pid`).
#
# v2 (Ruling Zero 2026-09-09 19:40, after the manual recovery of session
# a60e0124): the old gesture pressed ⌘N, slept a FIXED 1.2s and read
# `name of window 1`. Ghostty on Pro took longer than that, so the script
# declared "front window changed" and typed NOTHING although the window HAD
# opened — a human then had to type `nz-jump <sid>` by hand. The fix is to stop
# betting on a delay: SNAPSHOT every window name BEFORE ⌘N, then poll every
# 0.3s up to JUMP_POLL_MAX_S until a name appears that was NOT in the snapshot.
# That window — by name, via AXRaise — is the one that gets `nz-jump`, and the
# only one that ever can: an unreadable snapshot, or a front-window change with
# no new name, both end in nothing typed. Titles collide (Claude Code sets the terminal
# title to the session title, so two sessions are both "Interactive" with only
# a glyph differing), so the match is on the EXACT string and both window lists
# are logged: a miss must be diagnosable from jump.log alone.
#
# Contract: $1 = from_session. Reads ~/.organism/context-guard/pending-jump-<from>.json
# (per-session file: two windows jumping at once never overwrite each other).
#   1. snapshot the window names NOW; the front one is the OLD window;
#   2. ⌘N; poll for a NEW window (a name that was NOT in the snapshot — never
#      a mere front-window change, which is a reorder and not a birth); raise it
#      by name and type `nz-jump <from>`, Enter — nz-jump
#      starts a fresh claude; the SessionStart hook context_jump_resume.py
#      injects the handoff and stamps `to_session`;
#   3. wait (≤ JUMP_WAIT_S, polled every 1s) for `to_session`; then raise the
#      OLD window by name, verify it is front, type `/exit`; wait ≤ EXIT_WAIT_S
#      for from_pid to die; if still alive: kill -INT ×2.
# Nothing is ever typed into a window that was not identified as the new one —
# a wrong keystroke in Zero's other window is worse than an idle one; every
# miss is logged with both window lists, never retried blind (the RETRY, capped
# at 3 gestures per session, belongs to context_window_guard.py).
# Kill switch: CONTEXT_JUMP_OFF=1.
set -u
FROM="${1:-}"
STATE_DIR="$HOME/.organism/context-guard"
PENDING="$STATE_DIR/pending-jump-$FROM.json"
LOG="$STATE_DIR/jump.log"
JUMP_WAIT_S="${JUMP_WAIT_S:-120}"
JUMP_POLL_MAX_S="${JUMP_POLL_MAX_S:-8}"
EXIT_WAIT_S="${EXIT_WAIT_S:-20}"
mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] [$FROM] $*" >> "$LOG"; }
jget() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$PENDING" "$1" 2>/dev/null; }
flat() { printf '%s' "$1" | tr '\n' '|'; }

[ "${CONTEXT_JUMP_OFF:-0}" = "1" ] && { log "disabled by CONTEXT_JUMP_OFF"; exit 0; }
# Capability, not platform: the gesture needs osascript. (uname=Darwin was the
# old test — it is true on a Mac with no GUI seat and false on the shimmed
# osascript the gesture test drives, so the honest question is the binary.)
command -v osascript >/dev/null 2>&1 || { log "no osascript on PATH: no window gesture"; exit 0; }
[ -n "$FROM" ] && [ -f "$PENDING" ] || { log "no pending-jump file for '$FROM'"; exit 1; }
FROM_PID=$(jget from_pid)

# AppleScript takes the window name as an ARGUMENT (on run argv), never spliced
# into source: a title with a quote or backslash must not become code.
AS="$STATE_DIR/window_jump.applescript"
cat > "$AS" <<'EOF'
on run argv
  set act to item 1 of argv
  tell application "Ghostty" to activate
  tell application "System Events" to tell process "ghostty"
    if act is "front-name" then
      return name of window 1
    else if act is "window-names" then
      -- front window first (window 1 is the front one), one name per line
      set AppleScript's text item delimiters to linefeed
      set out to (name of every window) as text
      set AppleScript's text item delimiters to ""
      return out
    else if act is "cmd-n" then
      keystroke "n" using command down
      return "ok"
    else if act is "type-here" then
      if name of window 1 is not (item 2 of argv) then error "front window changed"
      keystroke (item 3 of argv)
      delay 0.3
      key code 36
      return "ok"
    else if act is "raise-type" then
      set winName to item 2 of argv
      perform action "AXRaise" of (first window whose name is winName)
      delay 0.5
      if name of window 1 is not winName then error "front window changed"
      keystroke (item 3 of argv)
      delay 0.4
      key code 36
      return "ok"
    end if
  end tell
end run
EOF

BEFORE=$(osascript "$AS" window-names 2>/dev/null || true)
OLD_NAME=$(printf '%s\n' "$BEFORE" | head -1)
log "old window: '${OLD_NAME:-?}' pid=${FROM_PID:-?} · windows before: [$(flat "$BEFORE")]"
# An UNREADABLE window list is not an empty desktop. With BEFORE empty, every
# name polled after ⌘N looks "new", and the first pre-existing window — Zero's
# other session — would take the keystroke. No snapshot, no gesture.
[ -n "$BEFORE" ] || { log "window list unreadable before ⌘N (Accessibility not granted, or Ghostty not up): nothing typed"; exit 1; }

osascript "$AS" cmd-n >/dev/null 2>&1 || { log "⌘N could not be sent (Accessibility?): nothing typed"; exit 1; }

# Poll instead of betting on a delay (v2). ONLY a name that was ABSENT from the
# snapshot may be typed into: a window that already existed is somebody else's
# session, and "the front window changed" is not evidence that a window was
# BORN — windows reorder, focus moves, ⌘N fails. A front change with no new
# name is therefore logged as a diagnosis and acted on never.
NEW_NAME=""
AFTER="$BEFORE"
POLL_DEADLINE=$(( $(date +%s) + JUMP_POLL_MAX_S ))
while :; do
    sleep 0.3
    AFTER=$(osascript "$AS" window-names 2>/dev/null || true)
    while IFS= read -r n; do
        [ -z "$n" ] && continue
        printf '%s\n' "$BEFORE" | grep -Fxq -- "$n" || { NEW_NAME="$n"; break; }
    done <<< "$AFTER"
    [ -n "$NEW_NAME" ] && break
    [ "$(date +%s)" -ge "$POLL_DEADLINE" ] && break
done
FRONT=$(printf '%s\n' "$AFTER" | head -1)
log "windows after: [$(flat "$AFTER")] · new='${NEW_NAME:-}'"
if [ -z "$NEW_NAME" ] && [ -n "$FRONT" ] && [ "$FRONT" != "$OLD_NAME" ]; then
    log "front window is now '$FRONT', but that name was already in the snapshot (a reorder, not a new window): nothing typed"
fi

[ -n "$NEW_NAME" ] || { log "no new window within ${JUMP_POLL_MAX_S}s of ⌘N: nothing typed"; exit 1; }
osascript "$AS" raise-type "$NEW_NAME" "nz-jump $FROM" >/dev/null 2>&1 \
    || { log "new window '$NEW_NAME' could not be raised or front changed under it: nothing typed"; exit 1; }
log "new window '$NEW_NAME' opened, 'nz-jump $FROM' typed"

deadline=$(( $(date +%s) + JUMP_WAIT_S ))
TO=""
while [ "$(date +%s)" -lt "$deadline" ]; do
    TO=$(jget to_session); [ -n "$TO" ] && break; sleep 1
done
[ -n "$TO" ] || { log "new session did not report within ${JUMP_WAIT_S}s: old window left open"; exit 2; }
log "new session $TO is up"

[ -n "$OLD_NAME" ] || { log "old window name unknown: not closing"; exit 0; }
if osascript "$AS" raise-type "$OLD_NAME" "/exit" >/dev/null 2>&1; then
    log "/exit typed into old window"
else
    log "old window not found by name or front changed: /exit NOT typed"
fi
if [ -n "$FROM_PID" ] && kill -0 "$FROM_PID" 2>/dev/null; then
    deadline=$(( $(date +%s) + EXIT_WAIT_S ))
    while [ "$(date +%s)" -lt "$deadline" ] && kill -0 "$FROM_PID" 2>/dev/null; do sleep 2; done
    if kill -0 "$FROM_PID" 2>/dev/null; then
        kill -INT "$FROM_PID" 2>/dev/null; sleep 1; kill -INT "$FROM_PID" 2>/dev/null; sleep 3
        kill -0 "$FROM_PID" 2>/dev/null && log "old session pid $FROM_PID STILL alive after /exit + SIGINT×2 (left)" \
                                        || log "old session pid $FROM_PID ended by SIGINT×2 (fallback)"
    else
        log "old session pid $FROM_PID ended by /exit"
    fi
fi
exit 0
