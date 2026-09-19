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
#   NATIVE — Ghostty >= 1.3 ships an AppleScript dictionary (`new window`,
#   `input text`, `send key`, `close window`, window/terminal `id`s that are
#   STABLE handles). The new window is created and addressed by id: nothing is
#   typed "into whatever is in front", so the two failure modes measured on
#   2026-09-09 (Pro 15:36, M5 17:59: "⌘N did not bring a new window to front
#   (front='?')" — Ghostty not the active app, System Events blind) cannot
#   happen. Needs `macos-applescript = true` in the Ghostty config (the 1.3
#   default) — when it is off, Ghostty answers "AppleScript is disabled" and
#   we fall through.
#
#   KEYSTROKE (fallback) — System Events, for Ghostty < 1.3 or the option
#   switched off. The v1 gesture pressed ⌘N, slept a FIXED 1.2s and read
#   `name of window 1`; Ghostty on Pro took longer, so the script declared
#   "front window changed" and typed NOTHING although the window HAD opened —
#   a human then had to type `nz-jump <sid>` by hand. The fix is to stop
#   betting on a delay: poll every 0.3s up to JUMP_POLL_MAX_S until a name
#   appears that was NOT in the snapshot, and raise THAT window by name.
#
# BOTH routes stand on the same snapshot, and on the same rule (v2.1): every
# window name is read BEFORE any gesture, and ONLY a window whose exact name
# was ABSENT from that snapshot may ever be typed into — including the window
# the native API hands back by id, whose name is cross-checked before a single
# character is sent. Two corollaries, both of them cures for a measured way of
# typing into Zero's OTHER live session:
#   · an UNREADABLE list is not an empty desktop. With the snapshot empty every
#     name looks new and the first PRE-EXISTING window takes the keystroke: no
#     snapshot, no gesture.
#   · a REORDER is not a birth. "The front window changed" is not evidence that
#     a window was created — windows reorder, focus moves, ⌘N fails — so it is
#     logged as a diagnosis and acted on never.
# Both window lists go to jump.log: a miss must be diagnosable from the log
# alone. Titles collide (Claude Code sets the terminal title to the session
# title, so two sessions are both "Interactive" with only a glyph differing),
# so every name comparison is on the EXACT string, glyph included.
#
# Either way: nz-jump starts a fresh claude; SessionStart hook
# context_jump_resume.py injects the handoff and stamps `to_session`; we wait
# (<= JUMP_WAIT_S, polled every 1s) for it, then end the OLD session: `/exit`
# into its terminal when we hold a handle to it, then — measured 2026-09-09
# 12:53 on the live probe: three `/exit` keystrokes left the probe claude alive,
# two SIGINTs ended it — SIGINT×2 on the old claude PID (the guard's own
# parent, carried in the jump file as `from_pid`), and finally `close window`
# on the old window id (native route only; the keystroke route cannot close
# safely).
#
# OWN WINDOW ONLY (v2.2, Zero 2026-09-17: «il saltatore o quello che è atterrato
# non possono killare finestre al di fuori di loro»). The jumper may touch two
# windows: the one it opens (bound by id + a name absent from the snapshot) and
# ITS OWN (the terminal of `from_pid`). v2.1 resolved "its own" as `front window`
# whenever Ghostty was the active app — on 2026-09-17 01:35 the front window was
# a Sonnet session Zero had opened 30 seconds earlier, and it took the `/exit`
# (jump.log: "old window: '◑ Verificare sessioni attive sulle machine'"). The
# front window, the first window of the snapshot and "the window this hook runs
# in" are all guesses. The binding is now POSITIVE: after the new session has
# claimed the jump, the gesture writes an OSC title carrying the session id to
# the TTY OF `from_pid` (`ps -o tty=`) — only the old claude's own terminal can
# show that title — and the old window is the ONE window whose name carries it.
# No tty, no writable device, two matches or none: `/exit` is NOT typed, SIGINT
# to `from_pid` ends the session, and the window is left open. A stamped name
# is never taken for the birth of the new window either.
#
# Contract: $1 = from_session. Reads ~/.organism/context-guard/pending-jump-<from>.json
# (per-session file: two windows jumping at once never overwrite each other).
# A wrong keystroke in Zero's other window is worse than an idle one: every
# miss is logged with both window lists, never retried blind (the RETRY, capped
# at 3 gestures per session, belongs to context_window_guard.py).
# Kill switch: CONTEXT_JUMP_OFF=1. Test seam: OSASCRIPT=<stub> (tests only).
set -u
FROM="${1:-}"
STATE_DIR="$HOME/.organism/context-guard"
PENDING="$STATE_DIR/pending-jump-$FROM.json"
LOG="$STATE_DIR/jump.log"
JUMP_WAIT_S="${JUMP_WAIT_S:-120}"
JUMP_POLL_MAX_S="${JUMP_POLL_MAX_S:-8}"
EXIT_WAIT_S="${EXIT_WAIT_S:-20}"
OSASCRIPT="${OSASCRIPT:-osascript}"
mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] [$FROM] $*" >> "$LOG"; }
# A zombie (exited, parent has not reaped it yet) answers kill -0: it is dead.
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null && [[ "$(ps -o stat= -p "$1" 2>/dev/null)" != Z* ]]; }
jget() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$PENDING" "$1" 2>/dev/null; }
flat() { printf '%s' "$1" | tr '\n' '|'; }
in_snapshot() { printf '%s\n' "$1" | grep -Fxq -- "$2"; }

[ "${CONTEXT_JUMP_OFF:-0}" = "1" ] && { log "disabled by CONTEXT_JUMP_OFF"; exit 0; }
# Capability, not platform: the gesture needs osascript. (uname=Darwin was the
# old test — it is true on a Mac with no GUI seat and false on the shimmed
# osascript the gesture test drives, so the honest question is the binary.)
command -v "$OSASCRIPT" >/dev/null 2>&1 || { log "no osascript on PATH: no window gesture"; exit 0; }
[ -n "$FROM" ] && [ -f "$PENDING" ] || { log "no pending-jump file for '$FROM'"; exit 1; }
FROM_PID=$(jget from_pid)
CWD=$(jget cwd)
SID8="${FROM:0:8}"
STAMP="⏩ nz-jump $SID8"

# Write the stamp to the old claude's own terminal. JUMP_TTY overrides the
# device (tests only). Returns 1 — and logs why — whenever the window cannot be
# PROVEN ours: then nothing is typed into any window.
stamp_own_window() {
    [ -n "${FROM_PID:-}" ] && [ "$FROM_PID" -gt 1 ] 2>/dev/null || { log "own window not stamped: no from_pid"; return 1; }
    alive "$FROM_PID" || { log "own window not stamped: pid $FROM_PID not alive"; return 1; }
    local dev="${JUMP_TTY:-}"
    if [ -z "$dev" ]; then
        local tty
        tty=$(ps -o tty= -p "$FROM_PID" 2>/dev/null | tr -d ' ')
        # No controlling terminal: BSD ps prints "??", Linux procps "?".
        case "$tty" in ""|\?*) log "own window not stamped: pid $FROM_PID has no tty (window left open)"; return 1 ;; esac
        dev="/dev/$tty"
    fi
    [ -w "$dev" ] || { log "own window not stamped: $dev not writable (window left open)"; return 1; }
    printf '\033]0;%s\007' "$STAMP" > "$dev" 2>/dev/null || { log "own window not stamped: write to $dev failed (window left open)"; return 1; }
    log "own window stamped '$STAMP' on $dev (tty of pid $FROM_PID)"
    sleep 0.5
}
# The ONE line of a window list that carries our session id; two or none -> "".
own_name_in() { printf '%s\n' "$1" | grep -F -- "$SID8" | awk 'NR==1{a=$0} END{if(NR==1) printf "%s", a}'; }

# AppleScript takes every value as an ARGUMENT (on run argv), never spliced
# into source: a title, a path or a session id with a quote or backslash must
# not become code.
AS_NATIVE="$STATE_DIR/window_jump_native.applescript"
cat > "$AS_NATIVE" <<'EOF'
on run argv
  set act to item 1 of argv
  tell application "Ghostty"
    if act is "window-names" then
      -- the snapshot both routes stand on, one name per line, front first
      set AppleScript's text item delimiters to linefeed
      set out to (name of every window) as text
      set AppleScript's text item delimiters to ""
      return out
    else if act is "old-id" then
      -- The ONLY window whose title carries this session id: the title the
      -- gesture stamped on the old claude's tty (or nz-jump's stub name).
      -- NEVER the front window — on 2026-09-17 01:35 "front" was the Sonnet
      -- session Zero had opened 30 seconds earlier, and it took the /exit.
      -- Two or none: unknown — better an old window left open than /exit
      -- typed into the wrong one.
      set sid to item 2 of argv
      set found to {}
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
    else if act is "name-of-id" then
      return name of (window id (item 2 of argv))
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

ROUTE=""
OLD_ID=""
OLD_NAME=""
NEW_ID=""
NEW_NAME=""
NERR="$STATE_DIR/.native-$FROM.err"

# ---- the snapshot, BEFORE any gesture ---------------------------------------
SNAP_SRC="native"
BEFORE=$("$OSASCRIPT" "$AS_NATIVE" window-names 2>"$NERR" || true)
if [ -z "$BEFORE" ]; then
    log "native window list unavailable ($(tr '\n' ' ' < "$NERR" | cut -c1-120)): asking System Events"
    SNAP_SRC="keys"
    BEFORE=$("$OSASCRIPT" "$AS_KEYS" window-names 2>/dev/null || true)
fi
FRONT_BEFORE=$(printf '%s\n' "$BEFORE" | head -1)
log "front window: '${FRONT_BEFORE:-?}' (not assumed ours) pid=${FROM_PID:-?} · windows before ($SNAP_SRC): [$(flat "$BEFORE")]"
# An UNREADABLE window list is not an empty desktop. With BEFORE empty, every
# name read after the gesture looks "new", and the first pre-existing window —
# Zero's other session — would take the keystroke. No snapshot, no gesture.
[ -n "$BEFORE" ] || { log "window list unreadable before the gesture (Accessibility not granted, or Ghostty not up): nothing typed"; rm -f "$NERR"; exit 1; }

# ---- NATIVE route -----------------------------------------------------------
if [ "$SNAP_SRC" = "native" ]; then
    NEW_ID=$("$OSASCRIPT" "$AS_NATIVE" new-window "$CWD" 2>"$NERR" || true)
    if [ -z "$NEW_ID" ]; then
        log "native: new window FAILED ($(tr '\n' ' ' < "$NERR" | cut -c1-160)): falling back to keystrokes"
    else
        # The id is a handle, but the RULE is the name: a window whose name
        # was already in the snapshot is somebody else's, whatever handed
        # it to us. Unreadable is refused too — no evidence, no keystroke.
        # A name carrying OUR session id is our own old window, not a birth.
        NEW_NAME=$("$OSASCRIPT" "$AS_NATIVE" name-of-id "$NEW_ID" 2>/dev/null || true)
        if [ -z "$NEW_NAME" ]; then
            log "native: window id='$NEW_ID' created but its name is unreadable, so it cannot be checked against the snapshot: nothing typed (window left open)"
            rm -f "$NERR"; exit 1
        elif in_snapshot "$BEFORE" "$NEW_NAME"; then
            log "native: window id='$NEW_ID' is named '$NEW_NAME', a name ALREADY in the snapshot (not a birth): nothing typed (window left open)"
            rm -f "$NERR"; exit 1
        elif [ -n "$(own_name_in "$NEW_NAME")" ]; then
            log "native: window id='$NEW_ID' is named '$NEW_NAME', which carries THIS session's id (our own window, not a birth): nothing typed (window left open)"
            rm -f "$NERR"; exit 1
        elif "$OSASCRIPT" "$AS_NATIVE" type-into "$NEW_ID" "nz-jump $FROM" >/dev/null 2>"$NERR"; then
            ROUTE="native"
            log "native: new window id='$NEW_ID' name='$NEW_NAME' (absent from the snapshot), 'nz-jump $FROM' sent; old window resolved by stamp after the claim"
        else
            log "native: new window id='$NEW_ID' opened but input FAILED ($(tr '\n' ' ' < "$NERR" | cut -c1-160)): nothing typed"
            rm -f "$NERR"; exit 1
        fi
    fi
fi
rm -f "$NERR"

# ---- KEYSTROKE route (fallback) ---------------------------------------------
if [ -z "$ROUTE" ]; then
    if [ "$SNAP_SRC" != "keys" ]; then
        SNAP_SRC="keys"
        BEFORE=$("$OSASCRIPT" "$AS_KEYS" window-names 2>/dev/null || true)
        FRONT_BEFORE=$(printf '%s\n' "$BEFORE" | head -1)
        log "keys: front window: '${FRONT_BEFORE:-?}' (not assumed ours) · windows before: [$(flat "$BEFORE")]"
        [ -n "$BEFORE" ] || { log "keys: window list unreadable before ⌘N (Accessibility not granted, or Ghostty not up): nothing typed"; exit 1; }
    fi
    "$OSASCRIPT" "$AS_KEYS" cmd-n >/dev/null 2>&1 || { log "keys: ⌘N could not be sent (Accessibility?): nothing typed"; exit 1; }

    # Poll instead of betting on a delay (v2). ONLY a name that was ABSENT from
    # the snapshot may be typed into: a window that already existed is somebody
    # else's session, and a front-window change is not evidence of a birth.
    # A name carrying OUR session id is our own old window, never the new one.
    AFTER="$BEFORE"
    POLL_DEADLINE=$(( $(date +%s) + JUMP_POLL_MAX_S ))
    while :; do
        sleep 0.3
        AFTER=$("$OSASCRIPT" "$AS_KEYS" window-names 2>/dev/null || true)
        while IFS= read -r n; do
            [ -z "$n" ] && continue
            [ -n "$(own_name_in "$n")" ] && continue
            in_snapshot "$BEFORE" "$n" || { NEW_NAME="$n"; break; }
        done <<< "$AFTER"
        [ -n "$NEW_NAME" ] && break
        [ "$(date +%s)" -ge "$POLL_DEADLINE" ] && break
    done
    FRONT=$(printf '%s\n' "$AFTER" | head -1)
    log "keys: windows after: [$(flat "$AFTER")] · new='${NEW_NAME:-}'"
    if [ -z "$NEW_NAME" ] && [ -n "$FRONT" ] && [ "$FRONT" != "$FRONT_BEFORE" ]; then
        log "keys: front window is now '$FRONT', but that name was already in the snapshot (a reorder, not a new window): nothing typed"
    fi
    [ -n "$NEW_NAME" ] || { log "keys: no new window within ${JUMP_POLL_MAX_S}s of ⌘N: nothing typed"; exit 1; }
    "$OSASCRIPT" "$AS_KEYS" raise-type "$NEW_NAME" "nz-jump $FROM" >/dev/null 2>&1 \
        || { log "keys: new window '$NEW_NAME' could not be raised or front changed under it: nothing typed"; exit 1; }
    ROUTE="keys"
    log "keys: new window '$NEW_NAME' opened, 'nz-jump $FROM' typed"
fi

# ---- wait for the new session to claim the jump -----------------------------
deadline=$(( $(date +%s) + JUMP_WAIT_S ))
TO=""
while [ "$(date +%s)" -lt "$deadline" ]; do
    TO=$(jget to_session); [ -n "$TO" ] && break; sleep 1
done
[ -n "$TO" ] || { log "new session did not report within ${JUMP_WAIT_S}s: old window left open"; exit 2; }
log "new session $TO is up"

# ---- end the OLD session — OWN WINDOW ONLY -----------------------------------
# Resolved NOW, after the claim: stamp the old claude's tty, then take the ONE
# window whose name carries the stamp. Front window, snapshot head, "the window
# this hook runs in": never. Unproven = not typed (SIGINT to from_pid, window
# left open).
if stamp_own_window; then
    if [ "$ROUTE" = "native" ]; then
        OLD_ID=$("$OSASCRIPT" "$AS_NATIVE" old-id "$SID8" 2>/dev/null || true)
        [ -n "$OLD_ID" ] && [ "$OLD_ID" = "$NEW_ID" ] && { log "stamp resolved to the NEW window id=$NEW_ID: refused"; OLD_ID=""; }
    else
        OLD_NAME=$(own_name_in "$("$OSASCRIPT" "$AS_KEYS" window-names 2>/dev/null || true)")
    fi
fi
if [ "$ROUTE" = "native" ]; then
    if [ -n "$OLD_ID" ]; then
        "$OSASCRIPT" "$AS_NATIVE" type-into "$OLD_ID" "/exit" >/dev/null 2>&1 \
            && log "/exit typed into old window id=$OLD_ID (proven ours by stamp)" \
            || log "old window id=$OLD_ID gone or refused input: /exit NOT typed"
    else
        log "old window id unknown: /exit NOT typed (SIGINT fallback only, window left open)"
    fi
else
    if [ -n "$OLD_NAME" ] && "$OSASCRIPT" "$AS_KEYS" raise-type "$OLD_NAME" "/exit" >/dev/null 2>&1; then
        log "/exit typed into old window '$OLD_NAME' (proven ours by stamp)"
    else
        log "old window not proven ours by stamp or front changed: /exit NOT typed (SIGINT fallback only, window left open)"
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
else
    # already gone when we looked: the outcome line is owed to the log either way
    log "old session pid $FROM_PID ended by /exit"
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
