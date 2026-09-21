#!/usr/bin/env bash
# Proof for the failure alert in scripts/cron-wrapper.sh — and for the one
# property its two siblings (cron-state.sh, cron-runner.sh) already had and it
# did not: the alert's dedup key names the job by the SAME string as the state
# file the wrapper writes.
#
# That state file is the witness a consumer opens to prove a failure is over.
# Measured 2026-09-21: all 8 cron-wrapper jobs on Pro have a hyphen in their
# name, alerted as `cron-fail:fly-pg-backup`, and wrote their witness as
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
# No network and no Telegram: the wrapper runs from a tmp copy with a fake
# tg_notify.py beside it, which records argv instead of sending anything.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

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

run_case () {  # run_case <job> <cmd...> ; sets RC
    rm -rf "$TMP/run" "$TMP/home" "$TMP/logs" "$TMP/gateway.argv"
    mkdir -p "$TMP/run" "$TMP/home" "$TMP/logs"
    cp "$WRAPPER" "$TMP/run/cron-wrapper.sh"
    mkstub "${STUB_RC:-0}"
    HOME="$TMP/home" CRON_LOG_DIR="$TMP/logs" CRON_MAX_RETRIES=0 \
        bash "$TMP/run/cron-wrapper.sh" "$@" >/dev/null 2>&1
    RC=$?
}

# The key the gateway received, e.g. `cron-fail:foo_bar`, or empty.
alert_key () { grep -m1 '^cron-fail:' "$TMP/gateway.argv" 2>/dev/null || true; }
STATE="$TMP/home/.agent/decisions/state"

echo "GUILT — a failing hyphenated job alerts under the name of its own witness"
JOB="fly-pg-backup-$SUFFIX"
run_case "$JOB" sh -c 'echo boom >&2; exit 7'
KEY="$(alert_key)"
NAME="${KEY#cron-fail:}"
check "the job's exit code is preserved (7)" "$([ "$RC" = "7" ] && echo 0 || echo 1)"
check "the gateway was invoked with a cron-fail key" "$([ -n "$KEY" ] && echo 0 || echo 1)"
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
check "--source still carries the raw name for a human" "$(grep -qx -- "cron:$JOB" "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"

echo "INNOCENCE — a name with no hyphen is not transformed"
JOB="plainjob$SUFFIX"
run_case "$JOB" sh -c 'exit 4'
check "the key is exactly cron-fail:<name>" "$(grep -qx -- "cron-fail:$JOB" "$TMP/gateway.argv" 2>/dev/null && echo 0 || echo 1)"
check "and its witness is exactly <name>.last.json" "$([ -f "$STATE/$JOB.last.json" ] && echo 0 || echo 1)"

echo "INNOCENCE — a succeeding job does not speak"
run_case "happy-job-$SUFFIX" sh -c 'exit 0'
check "exit 0 preserved" "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "the gateway was not invoked" "$([ ! -s "$TMP/gateway.argv" ] && echo 0 || echo 1)"
check "the witness is still written, status ok" "$(
    [ -f "$STATE/happy_job_$SUFFIX.last.json" ] &&
    python3 -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1])).get("status") == "ok" else 1)' \
        "$STATE/happy_job_$SUFFIX.last.json" && echo 0 || echo 1)"

echo "FAIL-OPEN — a broken alarm cannot rewrite the job's outcome"
STUB_RC=1 run_case "crashing-gateway-$SUFFIX" sh -c 'exit 3'
check "exit 3 preserved even when the gateway crashes" "$([ "$RC" = "3" ] && echo 0 || echo 1)"

echo
echo "cron-wrapper alert: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
