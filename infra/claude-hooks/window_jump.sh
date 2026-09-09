#!/bin/bash
# window_jump.sh — the GESTURE of the window jump (macOS + Ghostty only).
#
# Spawned detached by context_window_guard.py the first time a session trips its
# context threshold (Ruling Zero 2026-09-09: "arrivati al contesto, scrivi
# l'handoff, incollalo in una finestra nuova e chiudi la tua" — automatic, no
# human). The CLI has no way to open a window or end a session from a hook
# (research/operations/2026-09-09-window-jump-automatic-handoff-it.md §2), so
# this script does both from outside.
#
# TWO ROUTES, tried in this order:
#
#   NATIVE — Ghostty ≥ 1.3 ships an AppleScript dictionary (`new window`,
#   `input text`, `send key`, `close window`, window/terminal `id`s that are
#   STABLE handles). The new window is created and addressed by id: nothing is
#   typed "into whatever is in front", so the two failure modes measured on
#   2026-09-09 (Pro 15:36, M5 17:59: "⌘N did not bring a new window to front
#   (front='?')" — Ghostty not the active app, System Events blind) cannot
#   happen. Needs `macos-applescript = true` in the Ghostty config (the 1.3
#   default) — when it is off, Ghostty answers "AppleScript is disabled" and
#   we fall through.
#
#   KEYSTROKE (fallback) — System Events: remember the front Ghostty window by
#   NAME, ⌘N, verify a NEW window is front, type `nz-jump <from>`. Kept for
#   Ghostty < 1.3 or the option switched off; every miss is logged, never
#   retried blind. Nothing is typed into a window that is not verified front —
#   a wrong keystroke in Zero's other window is worse than an idle one.
#
# Either way: nz-jump starts a fresh claude; SessionStart hook
# context_jump_resume.py injects the handoff and stamps `to_session`; we wait
# (≤ JUMP_WAIT_S) for it, then end the OLD session: `/exit` into its terminal
# when we hold a handle to it, then — measured 2026-09-09 12:53 on the live
# probe: three `/exit` keystrokes left the probe claude alive, two SIGINTs
# ended it — SIGINT×2 on the old claude PID (the guard's own parent, carried
# in the jump file as `from_pid`), and finally `close window` on the old
# window id (native route only; the keystroke route cannot close safely).
#
# Contract: $1 = from_session. Reads ~/.organism/context-guard/pending-jump-<from>.json
# (per-session file: two windows jumping at once never overwrite each other).
# Kill switch: CONTEXT_JUMP_OFF=1. Test seam: OSASCRIPT=<stub> (tests only).
set -u
FROM="${1:-}"
STATE_DIR="$HOME/.organism/context-guard"
PENDING="$STATE_DIR/pending-jump-$FROM.json"
LOG="$STATE_DIR/jump.log"
JUMP_WAIT_S="${JUMP_WAIT_S:-120}"
EXIT_WAIT_S="${EXIT_WAIT_S:-20}"
OSASCRIPT="${OSASCRIPT:-osascript}"
mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] [$FROM] $*" >> "$LOG"; }
# A zombie (exited, parent has not reaped it yet) answers kill -0: it is dead.
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null && [[ "$(ps -o stat= -p "$1" 2>/dev/null)" != Z* ]]; }
jget() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$PENDING" "$1" 2>/dev/null; }

[ "${CONTEXT_JUMP_OFF:-0}" = "1" ] && { log "disabled by CONTEXT_JUMP_OFF"; exit 0; }
[ "$(uname)" = "Darwin" ] || { log "not macOS: no window gesture"; exit 0; }
[ -n "$FROM" ] && [ -f "$PENDING" ] || { log "no pending-jump file for '$FROM'"; exit 1; }
FROM_PID=$(jget from_pid)
CWD=$(jget cwd)

# AppleScript takes every value as an ARGUMENT (on run argv), never spliced
# into source: a title, a path or a session id with a quote or backslash must
# not become code.
AS_NATIVE="$STATE_DIR/window_jump_native.applescript"
cat > "$AS_NATIVE" <<'EOF'
on run argv
  set act to item 1 of argv
  tell application "Ghostty"
    if act is "old-id" then
      -- The window this hook runs in is the one the operator is looking at
      -- when Ghostty is the active app; otherwise the ONLY terminal whose
      -- title names this session (Claude Code titles the tab after the
      -- mandate; nz-jump's stub names the session). Two or none: unknown —
      -- better an old window left open than /exit typed into the wrong one.
      set sid to item 2 of argv
      set found to {}
      try
        if frontmost then return id of front window
      end try
      repeat with w in windows
        try
          if (name of w) contains sid then set end of found to id of w
        end try
      end repeat
      if (count of found) is 1 then return item 1 of found
      return ""
    else if act is "new-window" then
      set cfg to new surface configuration
      if (item 2 of argv) is not "" then set initial working directory of cfg to item 2 of argv
      set w to new window with configuration cfg
      delay 1.0
      return id of w
    else if act is "type-into" then
      set w to window id (item 2 of argv)
      set t to focused terminal of selected tab of w
      input text (item 3 of argv) to t
      send key "enter" to t
      return "ok"
    else if act is "close-window" then
      close window (window id (item 2 of argv))
      return "ok"
    end if
  end tell
end run
EOF

AS_KEYS="$STATE_DIR/window_jump.applescript"
cat > "$AS_KEYS" <<'EOF'
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

ROUTE=""
OLD_ID=""
OLD_NAME=""
NEW_ID=""

# ---- NATIVE route -----------------------------------------------------------
NERR="$STATE_DIR/.native-$FROM.err"
if OLD_ID=$("$OSASCRIPT" "$AS_NATIVE" old-id "${FROM:0:8}" 2>"$NERR"); then
    NEW_ID=$("$OSASCRIPT" "$AS_NATIVE" new-window "$CWD" 2>"$NERR" || true)
    if [ -n "$NEW_ID" ] && "$OSASCRIPT" "$AS_NATIVE" type-into "$NEW_ID" "nz-jump $FROM" >/dev/null 2>"$NERR"; then
        ROUTE="native"
        log "native: old window id='${OLD_ID:-?}' pid=${FROM_PID:-?}; new window id='$NEW_ID' opened, 'nz-jump $FROM' sent"
    elif [ -n "$NEW_ID" ]; then
        log "native: new window id='$NEW_ID' opened but input FAILED ($(tr '\n' ' ' < "$NERR" | cut -c1-160)): nothing typed"
        rm -f "$NERR"; exit 1
    else
        log "native: new window FAILED ($(tr '\n' ' ' < "$NERR" | cut -c1-160)): falling back to keystrokes"
    fi
else
    log "native route unavailable ($(tr '\n' ' ' < "$NERR" | cut -c1-120)): falling back to keystrokes"
fi
rm -f "$NERR"

# ---- KEYSTROKE route (fallback) ---------------------------------------------
if [ -z "$ROUTE" ]; then
    OLD_NAME=$("$OSASCRIPT" "$AS_KEYS" front-name 2>/dev/null || true)
    log "keys: old window: '${OLD_NAME:-?}' pid=${FROM_PID:-?}"
    NEW_NAME=$("$OSASCRIPT" "$AS_KEYS" new-window 2>/dev/null || true)
    if [ -z "$NEW_NAME" ] || [ "$NEW_NAME" = "$OLD_NAME" ]; then
        log "keys: ⌘N did not bring a new window to front (front='${NEW_NAME:-?}'): nothing typed"; exit 1
    fi
    "$OSASCRIPT" "$AS_KEYS" type-here "$NEW_NAME" "nz-jump $FROM" >/dev/null 2>&1 \
        || { log "keys: front window changed before typing (expected '$NEW_NAME'): nothing typed"; exit 1; }
    ROUTE="keys"
    log "keys: new window '$NEW_NAME' opened, 'nz-jump $FROM' typed"
fi

# ---- wait for the new session to claim the jump -----------------------------
deadline=$(( $(date +%s) + JUMP_WAIT_S ))
TO=""
while [ "$(date +%s)" -lt "$deadline" ]; do
    TO=$(jget to_session); [ -n "$TO" ] && break; sleep 3
done
[ -n "$TO" ] || { log "new session did not report within ${JUMP_WAIT_S}s: old window left open"; exit 2; }
log "new session $TO is up"

# ---- end the OLD session -----------------------------------------------------
if [ "$ROUTE" = "native" ]; then
    if [ -n "$OLD_ID" ] && [ "$OLD_ID" != "$NEW_ID" ]; then
        "$OSASCRIPT" "$AS_NATIVE" type-into "$OLD_ID" "/exit" >/dev/null 2>&1 \
            && log "/exit typed into old window id=$OLD_ID" \
            || log "old window id=$OLD_ID gone or refused input: /exit NOT typed"
    else
        log "old window id unknown: /exit NOT typed (SIGINT fallback only, window left open)"
    fi
else
    if [ -n "$OLD_NAME" ] && "$OSASCRIPT" "$AS_KEYS" raise-type "$OLD_NAME" "/exit" >/dev/null 2>&1; then
        log "/exit typed into old window"
    else
        log "old window not found by name or front changed: /exit NOT typed"
    fi
fi
if alive "$FROM_PID"; then
    deadline=$(( $(date +%s) + EXIT_WAIT_S ))
    while [ "$(date +%s)" -lt "$deadline" ] && alive "$FROM_PID"; do sleep 2; done
    if alive "$FROM_PID"; then
        kill -INT "$FROM_PID" 2>/dev/null; sleep 1; kill -INT "$FROM_PID" 2>/dev/null; sleep 3
        alive "$FROM_PID" && log "old session pid $FROM_PID STILL alive after /exit + SIGINT×2 (left)" \
                                        || log "old session pid $FROM_PID ended by SIGINT×2 (fallback)"
    else
        log "old session pid $FROM_PID ended by /exit"
    fi
fi
# Close the old window only when its claude is gone (a live child would make
# Ghostty ask "close running process?") and only when we hold its id.
if [ "$ROUTE" = "native" ] && [ -n "$OLD_ID" ] && [ "$OLD_ID" != "$NEW_ID" ]; then
    if alive "$FROM_PID"; then
        log "old window id=$OLD_ID NOT closed: pid $FROM_PID still alive"
    elif "$OSASCRIPT" "$AS_NATIVE" close-window "$OLD_ID" >/dev/null 2>&1; then
        log "old window id=$OLD_ID closed"
    else
        log "old window id=$OLD_ID close FAILED (left open)"
    fi
fi
exit 0
