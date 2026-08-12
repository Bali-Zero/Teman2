#!/usr/bin/env bash
# Proof that nb-agents-daily-dr names its cause AND that the cause escapes.
#
# TRAUMA (2026-08-10). `nb-agents-daily-dr` failed 13 consecutive days
# (2026-07-28 → 08-09) and sent 13 Telegram P0s reading, verbatim:
#
#     CRON FAIL Nuzantara / Job: nb-agents-daily-dr / Exit: 1 / Duration: 38s
#
# Ten of those mornings the answer was already on disk. `~/.cron-agent/logs/
# dr-raw-<date>.json` held six BYTE-IDENTICAL 227-byte payloads:
#
#     {"status":"error","error":"Query failed: Authentication expired.
#      Run 'nlm login' in your terminal to re-authenticate. ..."}
#
# The cause named its own cure and never reached anyone. TWO independent defects,
# and fixing either alone leaves the organ mute:
#
#   1. ESCAPE. Line ~30 is `exec >>"$TODAY_LOG" 2>&1` — from there the script's
#      stderr belongs to the day log, and `cron-state.sh` (which builds the alert
#      from the child's stderr) captures nothing. The crontab line was already in
#      the cured shape; the PAYLOAD defeated it.
#   2. NAMING. The parse block raised "unexpected nlm JSON shape - top-level keys:
#      ['error','status']" — it HELD `data["error"]` and threw it away for a
#      complaint about shape, sending the reader after a parser bug that does not
#      exist. A diagnosis that names the wrong thing is worse than none (W106).
#
#   GUILT ×2    — on the real auth payload the invoker's stderr must carry
#                 "nlm login" (escape + naming together), and must NOT carry the
#                 shape complaint. Both assertions matter: the first proves the
#                 cause got out, the second proves it is the RIGHT cause.
#   INNOCENCE ×3 — a genuinely unknown shape still reports the shape complaint
#                 (the old branch is kept, not replaced); a SUCCESSFUL run stays
#                 silent on the invoker's stderr and writes its report; and a
#                 successful payload that also carries an "error" key is not
#                 hijacked into a failure.
#
# The fake world is deliberately rich enough to REACH the failing path: a tmp
# HOME, a stub `nlm` on PATH, and a stub `lib/claude_seat.sh` whose failure the
# script already handles by falling back to its default slug. A world too poor
# measures its own poverty and reports the wrong count (W108).
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
SCRIPT="$REPO/scripts/nb-agents-daily-dr.sh"
[ -f "$SCRIPT" ] || { echo "FATAL: not found: $SCRIPT"; exit 1; }

TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

PASS=0; FAIL=0
ok ()  { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad () { FAIL=$((FAIL + 1)); printf '  FAIL %s\n' "$1"; }
want_in ()    { case "$2" in (*"$1"*) ok "$3";; (*) bad "$3 (missing: $1)";; esac; }
want_not_in () { case "$2" in (*"$1"*) bad "$3 (unexpectedly present: $1)";; (*) ok "$3";; esac; }

# run_case <name> <nlm-stdout-payload>  -> sets RC, STDERR_TXT, RUN_HOME
run_case () {
    local name="$1" payload="$2"
    local d="$TMP/$name"
    mkdir -p "$d/home" "$d/run/lib" "$d/bin"
    cp "$SCRIPT" "$d/run/"
    # The script sources lib/claude_seat.sh relative to ITSELF. Returning 1 takes
    # the documented "claude unusable -> default slug" path, which the script
    # already handles — no seat, no network, no OAuth in this corpus.
    printf 'claude_seat_run () { return 1; }\n' > "$d/run/lib/claude_seat.sh"
    printf '#!/bin/sh\ncat <<'"'"'PAYLOAD'"'"'\n%s\nPAYLOAD\n' "$payload" > "$d/bin/nlm"
    chmod +x "$d/bin/nlm"

    RUN_HOME="$d/home"
    set +e
    HOME="$RUN_HOME" PATH="$d/bin:$PATH" bash "$d/run/nb-agents-daily-dr.sh" 2>"$d/stderr.txt" >"$d/stdout.txt"
    RC=$?
    set -e
    STDERR_TXT="$(cat "$d/stderr.txt" 2>/dev/null)"
}

echo "== GUILT: the real auth payload — the cause escapes AND is the right one =="
run_case auth '{"status":"error","error":"Query failed: Authentication expired. Run '"'"'nlm login'"'"' in your terminal to re-authenticate."}'
if [ "$RC" -ne 0 ]; then ok "the run fails (exit $RC)"; else bad "the run should fail (got exit 0)"; fi
want_in "nlm login" "$STDERR_TXT" "the invoker's stderr NAMES the cure (escaped the self-redirect)"
want_in "Authentication expired" "$STDERR_TXT" "and carries the CLI's own sentence"
want_not_in "unexpected nlm JSON shape" "$STDERR_TXT" "it does NOT blame the JSON shape"

echo "== INNOCENCE: a genuinely unknown shape still reports the shape complaint =="
run_case weird '{"status":"ok","whatever":1}'
if [ "$RC" -ne 0 ]; then ok "the run fails (exit $RC)"; else bad "the run should fail (got exit 0)"; fi
want_in "unexpected nlm JSON shape" "$STDERR_TXT" "the old branch survives for shapes with no error to name"

echo "== INNOCENCE: a SUCCESSFUL run is silent on the invoker's stderr =="
run_case good '{"answer":"### risposta reale\nqualche riga","references":[],"sources_used":[]}'
if [ "$RC" -eq 0 ]; then ok "the run succeeds (exit 0)"; else bad "the run should succeed (got exit $RC)"; fi
want_not_in "tail of" "$STDERR_TXT" "no cause report is emitted on success"
if ls "$RUN_HOME"/nuzantara/research/agent-craft/*.md >/dev/null 2>&1; then
    ok "the report was written"
else
    bad "the report should have been written"
fi

echo "== INNOCENCE: a successful payload carrying an 'error' key is NOT hijacked =="
run_case both '{"answer":"### risposta reale\ncon un campo error accanto","error":"a warning that is not a failure","references":[],"sources_used":[]}'
if [ "$RC" -eq 0 ]; then ok "the run still succeeds (exit 0)"; else bad "an answer WITH an error key must still succeed (got exit $RC)"; fi
want_not_in "nlm query failed" "$STDERR_TXT" "the error key did not fabricate a failure"

echo
echo "TOTAL: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ] || exit 1
