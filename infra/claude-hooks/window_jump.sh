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
# Contract: $1 = from_session. Reads ~/.organism/context-guard/pending-jump-<from>.json
# (per-session file: two windows jumping at once never overwrite each other).
#   1. remember the OLD window = the front Ghostty window NOW (Claude Code sets
#      the terminal title to the session title, so the name is a handle);
#   2. ⌘N; verify a NEW window is front (name changed); type `nz-jump <from>`,
#      Enter — nz-jump starts a fresh claude; the SessionStart hook
#      context_jump_resume.py injects the handoff and stamps `to_session`;
#   3. wait (≤ JUMP_WAIT_S) for `to_session`; then raise the OLD window by name,
#      verify it is front, type `/exit`; wait ≤ EXIT_WAIT_S for from_pid to die;
#      if still alive: kill -INT ×2. Nothing is typed into a window that is not
#      verified front — a wrong keystroke in Zero's other window is worse than
#      an idle one; every miss is logged, never retried blind.
# Kill switch: CONTEXT_JUMP_OFF=1.
set -u
FROM="${1:-}"
STATE_DIR="$HOME/.organism/context-guard"
PENDING="$STATE_DIR/pending-jump-$FROM.json"
LOG="$STATE_DIR/jump.log"
JUMP_WAIT_S="${JUMP_WAIT_S:-120}"
EXIT_WAIT_S="${EXIT_WAIT_S:-20}"
mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] [$FROM] $*" >> "$LOG"; }
jget() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$PENDING" "$1" 2>/dev/null; }

[ "${CONTEXT_JUMP_OFF:-0}" = "1" ] && { log "disabled by CONTEXT_JUMP_OFF"; exit 0; }
[ "$(uname)" = "Darwin" ] || { log "not macOS: no window gesture"; exit 0; }
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
    else if act is "new-window" then
      keystroke "n" using command down
      delay 1.2
      return name of window 1
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

OLD_NAME=$(osascript "$AS" front-name 2>/dev/null || true)
log "old window: '${OLD_NAME:-?}' pid=${FROM_PID:-?}"

NEW_NAME=$(osascript "$AS" new-window 2>/dev/null || true)
if [ -z "$NEW_NAME" ] || [ "$NEW_NAME" = "$OLD_NAME" ]; then
    log "⌘N did not bring a new window to front (front='${NEW_NAME:-?}'): nothing typed"; exit 1
fi
osascript "$AS" type-here "$NEW_NAME" "nz-jump $FROM" >/dev/null 2>&1 || { log "front window changed before typing (expected '$NEW_NAME'): nothing typed"; exit 1; }
log "new window '$NEW_NAME' opened, 'nz-jump $FROM' typed"

deadline=$(( $(date +%s) + JUMP_WAIT_S ))
TO=""
while [ "$(date +%s)" -lt "$deadline" ]; do
    TO=$(jget to_session); [ -n "$TO" ] && break; sleep 3
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
