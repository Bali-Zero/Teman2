#!/usr/bin/env bash
# Corpus for scripts/intake_review_reader_liveness.sh — dossier C-13, 2026-08-15.
#
# DEFECT: `if [[ "$CODE" =~ ^[1-5][0-9][0-9]$ ]]` folded EVERY HTTP status, including 5xx,
# into ALIVE — "any 3-digit code is a heartbeat". A reader whose DB pool died and answered
# 500 on every path logged "OK: reader ALIVE (http 500)" while kita.balizero.com/review was
# actually serving errors. Fix: 1xx-4xx = ALIVE, 5xx = a NEW "SICK" branch that pages P0
# through the same gateway with its own dedup key, gated by the SAME active-active guard
# (no plist here => not this host's job) and the SAME anti-storm cooldown DEAD already used
# (superscar #2 "green lies" + #7/#10 sibling cautions).
#
# The wrapper is proven by EXECUTING it in a fake world — a real (loopback) HTTP server
# standing in for the reader, a fake tg_notify.py that records what it was called with
# instead of paging anyone. Reading the script cannot tell "detected SICK" from "paged for
# SICK" apart (W107) — only running it can.
#
# Usage: bash scripts/tests/test_intake_review_reader_liveness_5xx.sh

set -uo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER_SRC="$REPO/scripts/intake_review_reader_liveness.sh"
[ -f "$WRAPPER_SRC" ] || { echo "intake_review_reader_liveness.sh not found at $WRAPPER_SRC"; exit 1; }

PASS=0
FAIL=0
check() {  # check <name> <expected> <actual>
    if [ "$2" = "$3" ]; then
        echo "  ok    $1"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $1 (expected=$2 actual=$3)"
        FAIL=$((FAIL + 1))
    fi
}
check_true() {  # check_true <name> <shell-test-exit-code>
    if [ "$2" = "0" ]; then
        echo "  ok    $1"
        PASS=$((PASS + 1))
    else
        echo "  FAIL  $1"
        FAIL=$((FAIL + 1))
    fi
}

TMP="$(mktemp -d)"
SERVER_PID=""
SERVER_PORT=""

stop_fake_server() {
    local pid="${SERVER_PID:-}"
    if [ -z "$pid" ]; then
        SERVER_PORT=""
        return 0
    fi
    kill "$pid" 2>/dev/null || true
    wait "$pid" 2>/dev/null || true
    SERVER_PID=""
    SERVER_PORT=""
}

cleanup() {
    local status=$?
    trap - EXIT
    stop_fake_server
    rm -rf -- "$TMP"
    exit "$status"
}
trap cleanup EXIT

HOSTSHORT="$(hostname -s)"

# --- Fake HTTP server: answers every GET with a fixed status code on a free
# loopback port, until killed. stdlib only. ---
cat > "$TMP/fake_server.py" <<'PYEOF'
import http.server
import socket
import sys

code = int(sys.argv[1])


class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(code)
        self.end_headers()

    def log_message(self, *_a):
        pass


s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
port = s.getsockname()[1]
s.close()

with http.server.HTTPServer(("127.0.0.1", port), Handler) as httpd:
    print(port, flush=True)
    httpd.serve_forever()
PYEOF

start_fake_server() {  # start_fake_server <http-code> -> sets SERVER_PORT
    stop_fake_server
    rm -f "$TMP/port.txt"
    python3 "$TMP/fake_server.py" "$1" >"$TMP/port.txt" 2>"$TMP/server.err" &
    SERVER_PID=$!
    for _ in $(seq 1 50); do
        if [ -s "$TMP/port.txt" ]; then
            IFS= read -r SERVER_PORT < "$TMP/port.txt"
            [ -n "$SERVER_PORT" ] && return 0
        fi
        sleep 0.1
    done
    echo "fake HTTP server failed to publish a port" >&2
    stop_fake_server
    return 1
}

# A port nothing is listening on (bind-then-close, never serve): curl gets an
# immediate connection-refused = code 000, same as a genuinely dead reader.
closed_port() {
    python3 - <<'PYEOF'
import socket
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.bind(("127.0.0.1", 0))
print(s.getsockname()[1])
s.close()
PYEOF
}

# --- Fake Telegram gateway: records argv (JSON array per call) to $TG_RECORD
# instead of sending anything. ---
cat > "$TMP/tg_notify.py" <<'PYEOF'
import json
import os
import sys

record = os.environ.get("TG_RECORD")
if record:
    with open(record, "a") as f:
        f.write(json.dumps(sys.argv[1:]) + "\n")
sys.exit(0)
PYEOF

# --- World: a scripts/ dir with the REAL wrapper + the fake gateway beside it
# (dirname "$0" resolution), and an isolated $HOME. ---
make_world() {  # make_world <root>
    local root="$1"
    mkdir -p "$root/scripts" "$root/home/Library/LaunchAgents"
    cp "$WRAPPER_SRC" "$root/scripts/intake_review_reader_liveness.sh"
    cp "$TMP/tg_notify.py" "$root/scripts/tg_notify.py"
}

install_plist() {  # install_plist <root>
    : > "$1/home/Library/LaunchAgents/com.nuzantara.intake-review-reader.plist"
}

run_wrapper() {  # run_wrapper <root> <port> [extra env assignments...]
    local root="$1" port="$2"; shift 2
    ( cd "$root" && env "$@" \
        HOME="$root/home" \
        TG_RECORD="$root/home/tg_calls.jsonl" \
        PROBE_PORT="$port" \
        bash "$root/scripts/intake_review_reader_liveness.sh" \
        >"$root/home/stdout.log" 2>"$root/home/stderr.log" )
    echo $?
}

n_pages() {  # n_pages <root>  -> number of recorded Telegram sends
    local f="$1/home/tg_calls.jsonl"
    [ -f "$f" ] && wc -l < "$f" | tr -d ' ' || echo 0
}

# Portable octal file-mode read: GNU stat (Linux CI runners) uses `-c '%a'`;
# BSD/macOS stat (local dev) has no `-c` and instead uses `-f '%Lp'` — passing
# the wrong flag to the wrong `stat` doesn't error cleanly, it silently
# switches BSD `-f` into "report on the FILESYSTEM, not the file" mode and
# prints a multi-line df-style blob that satisfies no `check` on any OS. Try
# GNU form first (suppressing its "invalid option" stderr), fall back to BSD.
file_mode() {  # file_mode <path> -> octal mode (e.g. "600"), empty if missing
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null
}

echo "GUILT — a 5xx must page as SICK, not fold into ALIVE"

ROOT="$TMP/w-sick-guilt"; make_world "$ROOT"; install_plist "$ROOT"
start_fake_server 500 || exit 1
PORT="$SERVER_PORT"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=0)"
check "500 with plist present -> wrapper exits 1 (alert sent)" 1 "$RC"
check "exactly one page recorded" 1 "$(n_pages "$ROOT")"
check_true "page carries the SICK dedup key (not DEAD's)" \
    "$(grep -q "intake-review-reader:sick:${HOSTSHORT}" "$ROOT/home/tg_calls.jsonl" 2>/dev/null; echo $?)"
check_true "log names the state SICK" \
    "$(grep -q 'reader SICK' "$ROOT/home/logs/intake-review-reader-liveness.log" 2>/dev/null; echo $?)"
# Anchored to the SICK verdict line itself (not just "the log contains 500" anywhere) —
# refuter finding #6: a bare `grep -q '500'` also passes on the PRE-fix script, which
# logs "OK: reader ALIVE (http 500)" for the exact same input (the old code folded every
# 1xx-5xx into ALIVE), so that check never actually exercised the fix it claimed to guard.
# "ALERT: reader SICK on port <N> (http 500" only appears if the SICK branch ran at all.
check_true "log names the SICK verdict WITH the code (500), not just ALIVE-with-500" \
    "$(grep -qE 'ALERT: reader SICK on port [0-9]+ \(http 500' "$ROOT/home/logs/intake-review-reader-liveness.log" 2>/dev/null; echo $?)"
check_true "state file records action=sick" \
    "$(grep -q '"last_action": "sick"' "$ROOT/home/.agent/decisions/state/intake_review_reader_liveness.json" 2>/dev/null; echo $?)"
check "state write is atomic+hardened: file mode is 600" \
    "600" "$(file_mode "$ROOT/home/.agent/decisions/state/intake_review_reader_liveness.json")"
check "state write is atomic+hardened: no .tmp.* leftover" \
    0 "$(find "$ROOT/home/.agent/decisions/state" -name '*.tmp.*' 2>/dev/null | wc -l | tr -d ' ')"
stop_fake_server

echo
echo "INNOCENCE — process up and CORRECT must not page"

ROOT="$TMP/w-ok-200"; make_world "$ROOT"; install_plist "$ROOT"
start_fake_server 200 || exit 1
PORT="$SERVER_PORT"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=0)"
check "200 -> wrapper exits 0" 0 "$RC"
check "no page sent" 0 "$(n_pages "$ROOT")"
check_true "log names the state ALIVE" \
    "$(grep -q 'ALIVE' "$ROOT/home/logs/intake-review-reader-liveness.log" 2>/dev/null; echo $?)"
stop_fake_server

ROOT="$TMP/w-ok-401"; make_world "$ROOT"; install_plist "$ROOT"
start_fake_server 401 || exit 1
PORT="$SERVER_PORT"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=0)"
check "401 (JWT-gated, still up) -> wrapper exits 0" 0 "$RC"
check "no page sent" 0 "$(n_pages "$ROOT")"
stop_fake_server

echo
echo "INNOCENCE — the DEAD path (000, port closed) is unchanged by this fix"

ROOT="$TMP/w-dead"; make_world "$ROOT"; install_plist "$ROOT"
PORT="$(closed_port)"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=0)"
check "port closed -> wrapper exits 1 (alert sent)" 1 "$RC"
check "exactly one page recorded" 1 "$(n_pages "$ROOT")"
check_true "page still carries DEAD's original dedup key (stalled)" \
    "$(grep -q "intake-review-reader:stalled:${HOSTSHORT}" "$ROOT/home/tg_calls.jsonl" 2>/dev/null; echo $?)"
check_true "log names the state DEAD" \
    "$(grep -q 'reader DEAD' "$ROOT/home/logs/intake-review-reader-liveness.log" 2>/dev/null; echo $?)"
check_true "state file records action=alert_dead (unchanged)" \
    "$(grep -q '"last_action": "alert_dead"' "$ROOT/home/.agent/decisions/state/intake_review_reader_liveness.json" 2>/dev/null; echo $?)"

echo
echo "GUILT/INNOCENCE — SICK mirrors DEAD's two shared guards, not just its message"

# Active-active guard: no plist here + no FORCE_CHECK => stay silent even SICK.
ROOT="$TMP/w-sick-noop"; make_world "$ROOT"
start_fake_server 503 || exit 1
PORT="$SERVER_PORT"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=0)"
check "503, no plist, no FORCE_CHECK -> no-op exit 0 (not this host)" 0 "$RC"
check "no page sent" 0 "$(n_pages "$ROOT")"
stop_fake_server

# Cooldown guard, PART 1: cooldown is ALERT-only — a recent HEALTHY tick (last_ok_ts
# recent, last_action_ts untouched/zero) must NOT suppress the next SICK page. This is
# the opposite of what the pre-cooldown-fix code did: write_state("ok", ...) used to bump
# the SAME last_action_ts field the cooldown gate reads, so a healthy tick right before a
# fresh incident could mute its first alert for up to COOLDOWN_S. A fresh incident must
# always page on its first detection, no matter how recently the reader was healthy.
#
# ORGANIC, not hand-seeded (fast-follow, 2026-08-18 — refuter finding N1 on #4247: the
# hand-seeded state JSON below matched ONLY the post-fix field semantics, so this
# scenario stayed green even against a full revert of the cooldown-split commit —
# reverting-and-rerunning the shipped corpus proved 24/25 still pass, both PART 1 and
# PART 2 among them. A real ALIVE tick, then a real SICK tick, exercises write_ok_state
# and the cooldown gate exactly as production does; it fails on the reverted commit
# (single shared last_action_ts suppresses the SICK page) and passes on the fix.
ROOT="$TMP/w-sick-recent-ok-does-not-suppress"; make_world "$ROOT"; install_plist "$ROOT"
start_fake_server 200 || exit 1
PORT="$SERVER_PORT"
RC0="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=1800)"
check "priming healthy tick -> wrapper exits 0 (writes its own ok state)" 0 "$RC0"
stop_fake_server
start_fake_server 500 || exit 1
PORT="$SERVER_PORT"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=1800)"
check "500 right after a recent HEALTHY tick -> exit 1 (fresh incident pages immediately)" 1 "$RC"
check "a recent last_ok_ts does NOT suppress the first SICK page" 1 "$(n_pages "$ROOT")"
stop_fake_server

# Cooldown guard, PART 2: a recent SICK/DEAD ALERT (last_action_ts recent) must still
# suppress the next page within COOLDOWN_S, so a flapping backend does not page every
# tick (the defect this mirrors DEAD to avoid: an un-throttled SICK path would page every
# 5min).
#
# ORGANIC, not hand-seeded (fast-follow, 2026-08-18, same finding as PART 1 above): a
# real SICK tick primes the alert state via write_alert_state, then an immediate second
# real SICK tick against the same root must be suppressed by the cooldown it just wrote.
ROOT="$TMP/w-sick-recent-alert-suppresses"; make_world "$ROOT"; install_plist "$ROOT"
start_fake_server 500 || exit 1
PORT="$SERVER_PORT"
RC0="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=1800)"
check "priming SICK tick -> wrapper exits 1 (alert sent)" 1 "$RC0"
check "priming SICK tick pages exactly once" 1 "$(n_pages "$ROOT")"
RC="$(run_wrapper "$ROOT" "$PORT" COOLDOWN_S=1800)"
check "500 right after a recent SICK alert -> exit 1 (still unhealthy) but suppressed" 1 "$RC"
check "cooldown suppresses the repeat page (page count unchanged)" 1 "$(n_pages "$ROOT")"
check_true "log says cooldown active" \
    "$(grep -q 'cooldown active' "$ROOT/home/logs/intake-review-reader-liveness.log" 2>/dev/null; echo $?)"
stop_fake_server

echo
echo "result: $PASS pass, $FAIL fail"
[ "$FAIL" -eq 0 ]
