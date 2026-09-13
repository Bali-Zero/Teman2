#!/bin/bash
# test_window_jump_gesture.sh — guilt + innocence for window_jump.sh's GESTURE,
# with a shimmed `osascript` on PATH.
#
# Why a shell test and not a python one: the thing that broke on 2026-09-09 was
# not the guard's bookkeeping (test_context_window_jump.py already pins that) —
# it was the handful of lines that open a window and decide WHICH window gets
# the keystroke. v1 slept a fixed 1.2s and read `name of window 1`; Ghostty on
# Pro was slower, so the script declared "front window changed" and typed
# nothing although the window HAD opened, and a human had to type
# `nz-jump <sid>`. The script now has TWO routes — Ghostty's native AppleScript
# API (window ids as handles) and the System Events keystrokes as fallback —
# and the corpus holds BOTH to the same rule: only a window whose exact name
# was ABSENT from the pre-gesture snapshot may ever be typed into.
#
# A real Ghostty window is NEVER opened here (Zero's screen is live and a
# stray keystroke lands in a real session): `osascript` is replaced on PATH by
# a scripted fake that tells the two AppleScript files apart by name, answers
# `window-names` from a per-call table, and records every keystroke or
# `input text` it is asked to perform. What the corpus proves is exactly the
# thing that failed: with the front window UNCHANGED for two polls and a new
# name appearing only on the third, `nz-jump <sid>` is typed into the NEW
# window — and that nothing is typed at all when no window appears, when the
# window list was unreadable to begin with (every name would look new), when
# the front window merely CHANGED without any name being born, or when the
# native API hands back a window whose name was already on the desktop.
#
# Run: bash infra/claude-hooks/test_window_jump_gesture.sh
# Against an INSTALLED copy: WINDOW_JUMP_SH=~/.claude/hooks/window_jump.sh bash ...
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT="${WINDOW_JUMP_SH:-$HERE/window_jump.sh}"
[ -f "$SCRIPT" ] || { echo "FATAL: no window_jump.sh at $SCRIPT"; exit 2; }
PASSED=0; FAILED=0

ok()   { PASSED=$((PASSED+1)); echo "  ok   — $1"; }
bad()  { FAILED=$((FAILED+1)); echo "  FAIL — $1"; }
check(){ if [ "$2" = "yes" ]; then ok "$1"; else bad "$1"; fi; }
has()  { grep -Fq -- "$2" "$1" 2>/dev/null && echo yes || echo no; }
hasnt(){ grep -Fq -- "$2" "$1" 2>/dev/null && echo no || echo yes; }
typed_line() { printf '%s\t%s' "$1" "$2"; }

# One sandbox per case: HOME, a pending-jump file, and the osascript shim. The
# shim answers the NATIVE script only when the case enables it (otherwise it
# replies like Ghostty with `macos-applescript = false`, which is what sends
# the script down the keystroke route); System Events `window-names` answers
# come from files names.1, names.2, ... (calls past the table repeat the last).
setup() {
    SID="$1"; shift
    HOMEDIR="$(mktemp -d)"
    SHIM="$HOMEDIR/shim"; mkdir -p "$SHIM"
    mkdir -p "$HOMEDIR/.organism/context-guard"
    printf '{"from_session":"%s","from_pid":null,"to_session":null,"cwd":"/tmp","hops":1}\n' \
        "$SID" > "$HOMEDIR/.organism/context-guard/pending-jump-$SID.json"
    local i=1
    for names in "$@"; do printf '%s\n' "$names" > "$SHIM/names.$i"; i=$((i+1)); done
    printf '%s\n' "$names" > "$SHIM/names.last"   # calls past the table repeat the last answer
    cat > "$SHIM/osascript" <<'SHIMEOF'
#!/bin/bash
# fake osascript: $1 = script path, $2 = action, $3.. = args.
d="$(cd "$(dirname "$0")" && pwd)"
act="${2:-}"
case "$(basename "${1:-}")" in
  *native*)
    # Ghostty with the dictionary switched off answers exactly this and the
    # script falls through to the keystrokes; a case opts in with `native_on`.
    [ -f "$d/native_on" ] || { echo "execution error: AppleScript is disabled by the macos-applescript configuration. (-1743)" >&2; exit 1; }
    echo "$act ${3:-}" >> "$d/nativecalls"
    case "$act" in
      window-names) cat "$d/nnames" ;;
      old-id)       echo "win-OLD" ;;
      new-window)   echo "win-NEW" ;;
      name-of-id)   if [ "${3:-}" = "win-NEW" ]; then cat "$d/newname"; else echo "old title"; fi ;;
      type-into)    printf '%s\t%s\n' "${3:-}" "${4:-}" >> "$d/typed"; echo ok ;;
      close-window) echo "${3:-}" >> "$d/closed"; echo ok ;;
      *) echo "unknown native action $act" >&2; exit 1 ;;
    esac
    exit 0 ;;
esac
echo "$act ${3:-}" >> "$d/keyscalls"
case "$act" in
  window-names)
    n=$(cat "$d/wn" 2>/dev/null || echo 0); n=$((n+1)); echo "$n" > "$d/wn"
    f="$d/names.$n"; [ -f "$f" ] || f="$d/names.last"; cat "$f" ;;
  front-name) head -1 "$d/names.last" ;;
  cmd-n) echo "$(( $(cat "$d/cmdn" 2>/dev/null || echo 0) + 1 ))" > "$d/cmdn"; echo ok ;;
  raise-type|type-here) printf '%s\t%s\n' "${3:-}" "${4:-}" >> "$d/typed"; echo ok ;;
  *) echo "unknown action $act" >&2; exit 1 ;;
esac
exit 0
SHIMEOF
    chmod 755 "$SHIM/osascript"
    TYPED="$SHIM/typed"; LOG="$HOMEDIR/.organism/context-guard/jump.log"
    : > "$TYPED"
}

# Same sandbox, with Ghostty's native dictionary ANSWERING: $2 = the window
# names it reports before the gesture, $3 = the name of the window it hands
# back (win-NEW) when asked to create one.
setup_native() {
    setup "$1" "$2"
    printf '%s\n' "$2" > "$SHIM/nnames"
    printf '%s\n' "$3" > "$SHIM/newname"
    : > "$SHIM/native_on"
}

run_gesture() {
    HOME="$HOMEDIR" PATH="$SHIM:/usr/bin:/bin" JUMP_WAIT_S=1 JUMP_POLL_MAX_S=2 \
        bash "$SCRIPT" "$SID" >/dev/null 2>&1
    RC=$?
}

echo "== window_jump.sh gesture (shimmed osascript, no real window) =="

# --- guilt: the exact 2026-09-09 failure — front unchanged for two polls -----
echo "[1] front unchanged for 2 polls, new window name on the 3rd"
setup "s-slow" "◑ Interactive" "◑ Interactive" "◑ Interactive" "◑ Interactive
~/nuzantara"
run_gesture
check "nz-jump typed into the NEW window, not the old one" \
      "$(has "$TYPED" "$(typed_line "~/nuzantara" "nz-jump s-slow")")"
check "the old window was never typed into" \
      "$(hasnt "$TYPED" "$(typed_line "◑ Interactive" "nz-jump s-slow")")"
check "jump.log names both window lists" "$(has "$LOG" "windows before (keys): [◑ Interactive]")"
check "jump.log records the landing" "$(has "$LOG" "new window '~/nuzantara' opened, 'nz-jump s-slow' typed")"
check "exit 2: typed, but no to_session within JUMP_WAIT_S" "$([ "$RC" = 2 ] && echo yes || echo no)"

# --- guilt: titles collide, only the glyph differs --------------------------
echo "[2] two windows already named 'Interactive' (glyph-only difference)"
setup "s-glyph" "◑ Interactive
✳ Interactive" "◑ Interactive
✳ Interactive" "◑ Interactive
✳ Interactive
~/nuzantara"
run_gesture
check "the new window gets the keystroke" \
      "$(has "$TYPED" "$(typed_line "~/nuzantara" "nz-jump s-glyph")")"
check "Zero's other session (✳ Interactive) is never typed into" \
      "$(hasnt "$TYPED" "$(typed_line "✳ Interactive" "nz-jump s-glyph")")"

# --- innocence: a REORDER is not a birth -----------------------------------
# The front window changing is not evidence that a window was created: ⌘N can
# fail while focus moves, and every name still in the snapshot belongs to a
# session that is somebody else's. v2.1 refuses this case instead of typing.
echo "[3] no new name, front window changed (reorder): nothing may be typed"
setup "s-front" "A
B" "B
A"
run_gesture
check "not one keystroke was sent" "$([ ! -s "$TYPED" ] && echo yes || echo no)"
check "jump.log names the reorder" "$(has "$LOG" "already in the snapshot (a reorder, not a new window): nothing typed")"
check "exit 1" "$([ "$RC" = 1 ] && echo yes || echo no)"

# --- innocence: an UNREADABLE snapshot is not an empty desktop --------------
# If the first `window-names` fails (Accessibility not granted, Ghostty still
# starting) BEFORE is empty, so every name polled afterwards looks "new" — and
# the first one is a PRE-EXISTING window of Zero's. No snapshot, no gesture.
# Neither route may proceed on it: with the native dictionary off, both the
# native and the System Events list come back empty here.
echo "[3b] window list unreadable before the gesture: nothing may be typed"
setup "s-blind" "" "✳ Interactive di Zero"
run_gesture
check "not one keystroke was sent" "$([ ! -s "$TYPED" ] && echo yes || echo no)"
check "Zero's pre-existing window is never typed into" \
      "$(hasnt "$TYPED" "nz-jump s-blind")"
check "jump.log says the list was unreadable" "$(has "$LOG" "window list unreadable")"
check "exit 1" "$([ "$RC" = 1 ] && echo yes || echo no)"

# --- innocence: no window ever appears -> NOTHING is typed ------------------
echo "[4] ⌘N opens nothing: nothing may be typed"
setup "s-none" "◑ Interactive"
run_gesture
check "not one keystroke was sent" "$([ ! -s "$TYPED" ] && echo yes || echo no)"
check "jump.log says nothing typed" "$(has "$LOG" "nothing typed")"
check "exit 1" "$([ "$RC" = 1 ] && echo yes || echo no)"

# --- innocence: kill switch -------------------------------------------------
echo "[5] CONTEXT_JUMP_OFF=1"
setup "s-off" "◑ Interactive" "◑ Interactive
~/nuzantara"
HOME="$HOMEDIR" PATH="$SHIM:/usr/bin:/bin" CONTEXT_JUMP_OFF=1 JUMP_WAIT_S=1 \
    bash "$SCRIPT" "$SID" >/dev/null 2>&1; RC=$?
check "nothing typed, exit 0" "$([ ! -s "$TYPED" ] && [ "$RC" = 0 ] && echo yes || echo no)"
check "jump.log says why" "$(has "$LOG" "disabled by CONTEXT_JUMP_OFF")"

# --- innocence: no pending file --------------------------------------------
echo "[6] no pending-jump file for the session"
setup "s-nofile" "◑ Interactive"
rm -f "$HOMEDIR/.organism/context-guard/pending-jump-s-nofile.json"
run_gesture
check "nothing typed, exit 1" "$([ ! -s "$TYPED" ] && [ "$RC" = 1 ] && echo yes || echo no)"

# --- guilt: the NATIVE route -----------------------------------------------
# Ghostty >= 1.3 with the dictionary open: the window is created and addressed
# by ID, so System Events is never touched — but the id is only a handle, and
# the RULE is still the snapshot: the name it comes back with is checked
# against the pre-gesture list before a single character is sent.
echo "[7] native API answers: the new window is typed into by id, keystrokes untouched"
setup_native "s-native" "◑ Interactive" "~/nuzantara"
run_gesture
check "nz-jump sent to the window the API returned (by id)" \
      "$(has "$TYPED" "$(typed_line "win-NEW" "nz-jump s-native")")"
check "the old window never got nz-jump" \
      "$(hasnt "$TYPED" "$(typed_line "win-OLD" "nz-jump s-native")")"
check "System Events was never touched" "$([ ! -s "$SHIM/keyscalls" ] && echo yes || echo no)"
check "the name was checked against the snapshot before typing" \
      "$(has "$LOG" "name='~/nuzantara' (absent from the snapshot)")"
check "jump.log carries the pre-gesture window list" "$(has "$LOG" "windows before (native): [◑ Interactive]")"
check "exit 2: typed, but no to_session within JUMP_WAIT_S" "$([ "$RC" = 2 ] && echo yes || echo no)"

# --- innocence: the native route obeys the same snapshot --------------------
# If the window handed back carries a name that was ALREADY on the desktop,
# the id proves nothing about a birth: it may be Zero's other session. The
# name, not the handle, authorises the keystroke.
echo "[8] native API returns a window whose name was already in the snapshot: nothing may be typed"
setup_native "s-native-dup" "✳ Interactive di Zero" "✳ Interactive di Zero"
run_gesture
check "not one character was sent" "$([ ! -s "$TYPED" ] && echo yes || echo no)"
check "Zero's pre-existing window is never typed into" "$(hasnt "$TYPED" "nz-jump s-native-dup")"
check "jump.log names the collision" "$(has "$LOG" "a name ALREADY in the snapshot (not a birth): nothing typed")"
check "exit 1" "$([ "$RC" = 1 ] && echo yes || echo no)"

echo
echo "== $PASSED passed, $FAILED failed =="
[ "$FAILED" -eq 0 ] || exit 1
