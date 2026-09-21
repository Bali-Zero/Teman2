#!/usr/bin/env bash
# Proof for the failure alert in scripts/cron-wrapper.sh — and for the one
# property its two siblings (cron-state.sh, cron-runner.sh) already had and it
# did not: the alert's dedup key names the job by the SAME string as the state
# file the wrapper writes.
#
# That state file is the witness a consumer opens to prove a failure is over.
# Measured 2026-09-21: all 8 cron-wrapper entries in Pro's crontab have a
# hyphen in their name (7 of them run), alerted as `cron-fail:fly-pg-backup`, and wrote their witness as
# `fly_pg_backup.last.json` with `"job": "fly_pg_backup"` inside. No consumer
# could find it, and one that did would reject it as a stranger's
# (docs/specs/seat-board-drain-v1.md §4).
#
#   GUILT     — a failing HYPHENATED job must alert under a key whose name part
#               is the stem of a state file that exists, and whose own `job`
#               field is that same name. Asserted as the relation, not as a
#               literal, so a future transform on either side cannot pass by
#               happening to agree on one example.
#   INNOCENCE — a job with no hyphen keeps its name unchanged (the fix must not
#               over-transform), and a succeeding job must NOT alert.
#   FAIL-OPEN — a crashing gateway must never rewrite the job's exit code.
#
# No network and no Telegram: the wrapper runs from a tmp copy with the REAL
# tg_notify.py beside it, under TG_DRY_RUN=1, a tmp HOME with no credentials, and
# TG_BOARD_PATH inside the tmp dir. The key is read back from the board row the
# gateway writes — the field a consumer reads — so a flag the real parser rejects
# fails the case instead of being recorded by a stub that accepts anything. Only
# the fail-open case uses a stub, because a gateway that CRASHES is its point.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Every path below is "$TMP/...", and run_case removes several of them. An empty
# TMP would make that `rm -rf /run /home /logs` — so a failed mktemp stops here.
TMP="$(mktemp -d)" || { echo "mktemp failed — refusing to run"; exit 1; }
[ -n "$TMP" ] && [ -d "$TMP" ] || { echo "mktemp gave no directory — refusing to run"; exit 1; }
trap '/bin/rm -rf "$TMP"' EXIT
GATEWAY="$HERE/tg_notify.py"
[ -f "$GATEWAY" ] || { echo "tg_notify.py not found at $GATEWAY"; exit 1; }

WRAPPER="$HERE/cron-wrapper.sh"
[ -f "$WRAPPER" ] || { echo "cron-wrapper.sh not found at $WRAPPER"; exit 1; }

# The wrapper's lock dir is a fixed /tmp path, so every job name carries this
# run's pid — two concurrent runs of this test must not skip each other.
SUFFIX="t$$"

mkstub () {  # mkstub <exit-code>
    cat > "$TMP/run/tg_notify.py" <<STUB
import sys
with open("$TMP/gateway.argv", "a") as fh:
    fh.write("\n".join(sys.argv[1:]) + "\n")
raise SystemExit($1)
STUB
}

PASS=0; FAIL=0
check () {  # check <name> <condition-result>
    if [ "$2" = "0" ]; then PASS=$((PASS+1)); printf '  ok    %s\n' "$1"
    else FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; fi
}

# GATEWAY=real runs the actual tg_notify.py (dry-run, no credentials under the
# tmp HOME, board redirected into TMP): an argv the real parser rejects writes
# no row and fails the case. GATEWAY=stub records argv and exits STUB_RC — used
# only where a CRASHING gateway is the point.
run_case () {  # run_case <job> <cmd...> ; sets RC
    rm -rf "$TMP/run" "$TMP/home" "$TMP/logs" "$TMP/spool" "$TMP/gateway.argv" "$TMP/board.jsonl"
    mkdir -p "$TMP/run" "$TMP/home" "$TMP/logs" "$TMP/spool"
    cp "$WRAPPER" "$TMP/run/cron-wrapper.sh"
    if [ "${GATEWAY_MODE:-real}" = "stub" ]; then mkstub "${STUB_RC:-0}"
    else cp "$GATEWAY" "$TMP/run/tg_notify.py"; fi
    # The routing policy is PINNED, not inherited (PWC-7033 C2). This corpus proves
    # the WRAPPER, and reads its key off the board row the gateway writes — so an
    # ambient TG_ACT_ROUTING_ENABLED=0, or `cron-fail` added to the owner families,
    # would send the alert to Telegram instead of the board and turn this corpus
    # red for a reason that has nothing to do with the wrapper. The owner-families
    # value must be NON-empty: an empty set disables routing altogether.
    HOME="$TMP/home" CRON_LOG_DIR="$TMP/logs" CRON_MAX_RETRIES=0 \
        TG_DRY_RUN=1 TG_SPOOL_DIR="$TMP/spool" TG_BOARD_PATH="$TMP/board.jsonl" \
        TG_ACT_ROUTING_ENABLED=true TG_OWNER_FAMILIES=corpus-owner-only \
        bash "$TMP/run/cron-wrapper.sh" "$@" >/dev/null 2>&1
    RC=$?
}

# A field of the routed board row the real gateway wrote, or empty.
board_field () {
    [ -s "$TMP/board.jsonl" ] || return 0
    python3 -c 'import json,sys; print(json.loads(open(sys.argv[1]).readline()).get(sys.argv[2], ""))' \
        "$TMP/board.jsonl" "$1" 2>/dev/null || true
}
STATE="$TMP/home/.agent/decisions/state"

echo "GUILT — a failing hyphenated job alerts under the name of its own witness"
JOB="fly-pg-backup-$SUFFIX"
run_case "$JOB" sh -c 'echo boom >&2; exit 7'
KEY="$(board_field job)"
NAME="${KEY#cron-fail:}"
check "the job's exit code is preserved (7)" "$([ "$RC" = "7" ] && echo 0 || echo 1)"
check "the REAL gateway parsed the call and routed a cron-fail row" "$([ "${KEY%%:*}" = "cron-fail" ] && [ -n "$NAME" ] && echo 0 || echo 1)"
check "the key's name part carries no hyphen" "$([ -n "$NAME" ] && [ "${NAME//-/}" = "$NAME" ] && echo 0 || echo 1)"
check "a state file exists at <key name>.last.json" "$([ -n "$NAME" ] && [ -f "$STATE/$NAME.last.json" ] && echo 0 || echo 1)"
check "that file's own \"job\" field is the key's name" "$(
    [ -f "$STATE/$NAME.last.json" ] &&
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("job") == sys.argv[2] else 1)' \
        "$STATE/$NAME.last.json" "$NAME" && echo 0 || echo 1)"
check "the witness records the failure" "$(
    [ -f "$STATE/$NAME.last.json" ] &&
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("status") == "failed" else 1)' \
        "$STATE/$NAME.last.json" && echo 0 || echo 1)"
check "--source still carries the raw name for a human" "$([ "$(board_field context)" = "cron:$JOB" ] && echo 0 || echo 1)"

echo "INNOCENCE — a name with no hyphen is not transformed"
JOB="plainjob$SUFFIX"
run_case "$JOB" sh -c 'exit 4'
check "the key is exactly cron-fail:<name>" "$([ "$(board_field job)" = "cron-fail:$JOB" ] && echo 0 || echo 1)"
check "and its witness is exactly <name>.last.json" "$([ -f "$STATE/$JOB.last.json" ] && echo 0 || echo 1)"

echo "INNOCENCE — a succeeding job does not speak"
run_case "happy-job-$SUFFIX" sh -c 'exit 0'
check "exit 0 preserved" "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "the gateway wrote nothing" "$([ ! -s "$TMP/board.jsonl" ] && [ -z "$(ls -A "$TMP/spool" 2>/dev/null)" ] && echo 0 || echo 1)"
check "the witness is still written, status ok" "$(
    [ -f "$STATE/happy_job_$SUFFIX.last.json" ] &&
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("status") == "ok" else 1)' \
        "$STATE/happy_job_$SUFFIX.last.json" && echo 0 || echo 1)"

echo "FAIL-OPEN — a broken alarm cannot rewrite the job's outcome"
GATEWAY_MODE=stub STUB_RC=1 run_case "crashing-gateway-$SUFFIX" sh -c 'exit 3'
check "exit 3 preserved even when the gateway crashes" "$([ "$RC" = "3" ] && echo 0 || echo 1)"

echo
echo "cron-wrapper alert: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
