#!/bin/bash
# tmux_jump.sh — the GESTURE of the window jump for a claude that sits in a tmux pane.
#
# Spawned detached by context_window_guard.py on seat "tmux", exactly as
# window_jump.sh is on a Ghostty seat. Measured 2026-09-16 on M5: five army
# sessions (scripts/wa_army_launcher.sh puts an interactive `claude` in a
# detached tmux session) tripped the guard at 400K, were classified "headless"
# because TERM_PROGRAM was not ghostty, got no gesture, and died at 405–424K
# with the jump file never claimed. In tmux the gesture is deterministic: the
# old pane is addressed by ITS OWN id ($TMUX_PANE, inherited from the claude
# process the hook runs under), the new window is created by tmux and handed
# back by id, and nothing is ever typed "into whatever is in front".
#
#   1. new-window in the old pane's session, same cwd  -> NEW pane id
#   2. send-keys into NEW: `nz-jump <FROM>` (context_jump_resume.py stamps to_session)
#   3. wait <= JUMP_WAIT_S for to_session; none -> old pane left as is, exit 2
#   4. send-keys into OLD: `/exit`; wait <= EXIT_WAIT_S for from_pid; SIGINT×2 fallback
#
# Same jump.log and the same words where the guard reads them back
# (_should_retry_gesture: "opened, 'nz-jump" = the keystroke landed, "nothing
# typed" = a miss to retry). The launcher is typed by ABSOLUTE path: the new
# window's shell was born from a tmux server whose PATH may be launchd's.
# Kill switch: CONTEXT_JUMP_OFF=1. Test seams: TMUX_BIN=<stub>, NZ_JUMP_BIN=<path>.
set -u
FROM="${1:-}"
STATE_DIR="$HOME/.organism/context-guard"
PENDING="$STATE_DIR/pending-jump-$FROM.json"
LOG="$STATE_DIR/jump.log"
JUMP_WAIT_S="${JUMP_WAIT_S:-120}"
EXIT_WAIT_S="${EXIT_WAIT_S:-20}"
TMUX_BIN="${TMUX_BIN:-tmux}"
LAUNCHER="${NZ_JUMP_BIN:-$HOME/.claude/scripts/nz-jump}"
mkdir -p "$STATE_DIR"
log() { echo "[$(date '+%F %T')] [$FROM] $*" >> "$LOG"; }
# A zombie (exited, parent has not reaped it yet) answers kill -0: it is dead.
alive() { [ -n "${1:-}" ] && kill -0 "$1" 2>/dev/null && [[ "$(ps -o stat= -p "$1" 2>/dev/null)" != Z* ]]; }
jget() { python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]) or '')" "$PENDING" "$1" 2>/dev/null; }

[ "${CONTEXT_JUMP_OFF:-0}" = "1" ] && { log "disabled by CONTEXT_JUMP_OFF"; exit 0; }
command -v "$TMUX_BIN" >/dev/null 2>&1 || { log "tmux: no tmux on PATH: no window gesture"; exit 0; }
[ -n "$FROM" ] && [ -f "$PENDING" ] || { log "tmux: no pending-jump file for '$FROM'"; exit 1; }
[ -n "${TMUX:-}" ] || { log "tmux: not inside a tmux server (TMUX unset): nothing typed"; exit 1; }
OLD_PANE="${TMUX_PANE:-}"
[ -n "$OLD_PANE" ] || { log "tmux: own pane unknown (TMUX_PANE unset): nothing typed"; exit 1; }
FROM_PID=$(jget from_pid)
CWD=$(jget cwd)
[ -n "$CWD" ] && [ -d "$CWD" ] || CWD="$HOME"

# ---- the new window, in the OLD pane's own session --------------------------
OLD_WIN=$("$TMUX_BIN" display-message -p -t "$OLD_PANE" '#{window_id}' 2>/dev/null || true)
[ -n "$OLD_WIN" ] || { log "tmux: own pane $OLD_PANE not found on the server: nothing typed"; exit 1; }
NEW_PANE=$("$TMUX_BIN" new-window -a -t "$OLD_WIN" -c "$CWD" -P -F '#{pane_id}' 2>/dev/null || true)
[ -n "$NEW_PANE" ] || { log "tmux: new-window after $OLD_WIN failed: nothing typed"; exit 1; }
if "$TMUX_BIN" send-keys -t "$NEW_PANE" -l "$LAUNCHER $FROM" 2>/dev/null \
   && "$TMUX_BIN" send-keys -t "$NEW_PANE" Enter 2>/dev/null; then
    log "tmux: new window $NEW_PANE opened, 'nz-jump $FROM' typed"
else
    log "tmux: new window $NEW_PANE opened but send-keys refused: nothing typed"; exit 1
fi

# ---- wait for the new session to claim the jump -----------------------------
deadline=$(( $(date +%s) + JUMP_WAIT_S ))
TO=""
while [ "$(date +%s)" -lt "$deadline" ]; do
    TO=$(jget to_session); [ -n "$TO" ] && break; sleep 1
done
[ -n "$TO" ] || { log "new session did not report within ${JUMP_WAIT_S}s: old pane left open"; exit 2; }
log "new session $TO is up"

# ---- end the OLD session — ITS OWN PANE, by id ------------------------------
if "$TMUX_BIN" send-keys -t "$OLD_PANE" -l "/exit" 2>/dev/null \
   && { sleep 0.3; "$TMUX_BIN" send-keys -t "$OLD_PANE" Enter 2>/dev/null; }; then
    log "/exit typed into old pane $OLD_PANE"
else
    log "old pane $OLD_PANE gone or refused input: /exit NOT typed (SIGINT fallback only)"
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
exit 0
