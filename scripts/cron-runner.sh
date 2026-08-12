#!/usr/bin/env bash
# cron-runner.sh - run a shell script from cron and emit a Cell-readable receipt.

set -uo pipefail

SCRIPT="${1:-}"
if [ -n "$SCRIPT" ]; then
    shift
fi

export PATH="/Users/nuzantara/.local/bin:/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export HOME="${HOME:-/Users/nuzantara}"

STATE_DIR="${CRON_RUNNER_STATE_DIR:-$HOME/.agent/decisions/state}"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)"

sanitize_key() {
    printf '%s' "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | sed 's/[^a-z0-9]/_/g; s/__*/_/g; s/^_//; s/_$//'
}

derive_job_key() {
    if [ -n "${CRON_RUNNER_JOB_NAME:-}" ]; then
        sanitize_key "$CRON_RUNNER_JOB_NAME"
        return
    fi

    local base
    base="$(basename "$SCRIPT")"
    base="${base%.*}"

    local key arg_key
    key="$(sanitize_key "$base")"
    for arg in "$@"; do
        arg_key="$(sanitize_key "$arg")"
        if [ -n "$arg_key" ]; then
            key="${key}_${arg_key}"
        fi
    done
    printf '%s' "$key"
}

write_state() {
    local job_key="$1"
    local status="$2"
    local start_ts="$3"
    local end_ts="$4"
    local exit_code="$5"
    local script_path="$6"
    local state_file tmp
    shift 6

    mkdir -p "$STATE_DIR"
    state_file="$STATE_DIR/$job_key.last.json"
    tmp="$state_file.$$"

    if command -v python3 >/dev/null 2>&1; then
        python3 - "$tmp" "$job_key" "$status" "$start_ts" "$end_ts" "$exit_code" "$script_path" "$HOSTNAME_SHORT" "$@" <<'PY'
import json
import os
import sys

path, job, status, start_ts, end_ts, exit_code, script, host, *argv = sys.argv[1:]
start = int(float(start_ts))
end = int(float(end_ts))
payload = {
    "job": job,
    "ts": end,
    "status": status,
    "host": host,
    "source": "cron-runner",
    "duration_ms": max(0, (end - start) * 1000),
    "script": script,
    "argv": argv,
    "exit_code": int(exit_code),
}
if status != "ok":
    # Record the REAL failure cause (captured stderr/stdout tail), not just
    # "exit N" — a bare exit code gives the DLQ autopilot nothing to classify
    # (UNKNOWN/confidence=0.0) → blind escalate→TERMINAL loop (superscar #2).
    err = os.environ.get("CRON_RUNNER_LAST_ERROR", "").strip()
    payload["last_error"] = err[-2000:] if err else f"exit {exit_code}"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, separators=(",", ":"))
    fh.write("\n")
PY
    else
        printf '{"job":"%s","ts":%d,"status":"%s","host":"%s","source":"cron-runner","duration_ms":%d,"script":"%s","exit_code":%d}\n' \
            "$job_key" "$end_ts" "$status" "$HOSTNAME_SHORT" "$(( (end_ts - start_ts) * 1000 ))" "$script_path" "$exit_code" > "$tmp"
    fi

    mv "$tmp" "$state_file"
}

# ── Alert on failure (2026-07-28) ───────────────────────────────────────────
# Until now this wrapper only wrote a receipt, exactly like cron-state.sh did
# before 2026-07-27. Giving cron-state a voice and stopping there was half a
# fix, and it cured the smaller wrapper: censused on Pro the next day by the
# `source` field of the receipts, there are FIVE producers, and cron-runner is
# the largest (36 receipts, 30 invocations = 25 crontab + 5 plist) against
# cron-state's 28 / 27. Two cron-runner jobs failed in the 24h after that fix
# shipped — garuda_indexer 27/07 20:36 and run_ops_briefing 27/07 00:00 — with
# zero `cron-fail:` in the 239-row P0 archive or the 54-row digest spool.
# Nobody heard either one.
#
# Same gateway, tier and `cron-fail:` dedup key as cron-state.sh and
# cron-wrapper.sh, so a flapping job collapses to one alert per window, the
# reserved lane (TG_CRON_FAIL_RESERVE) applies, and with no credentials the
# alert lands in the digest spool instead of vanishing.
#
# Deliberately fail-open: the job's exit code is the contract this wrapper
# exists to preserve, and an alerting problem must never rewrite it.
# ── One voice per failure (2026-08-07) ──────────────────────────────────────
# 19 of the 20 nlm_deep_research wrappers alarm for themselves AND run under
# this runner, so one failure sent two P0s ~2s apart. Rather than silence
# either — measured, the job's sentence names the log path and this one's raw
# tail does not — the payload hands us its sentence and we carry it. Contract
# in apps/evaluator/nlm_deep_research/scripts/_alert.sh; the marker is
# duplicated there and in cron-wrapper.sh, pinned by test_cron_single_voice.sh.
CRON_ALERT_MARKER="CRON_ALERT_P0:"

deferred_summary() {  # deferred_summary <captured-output-file> -> the job's own line
    [ -n "${1:-}" ] && [ -f "$1" ] || return 1
    local line
    line="$(grep -a "^${CRON_ALERT_MARKER}" "$1" 2>/dev/null | tail -1)"
    [ -n "$line" ] || return 1
    line="${line#"$CRON_ALERT_MARKER"}"
    printf '%s' "${line# }"
}

alert_failure() {  # alert_failure <job_key> <exit_code> <start_ts> <end_ts> <tail>
    local job_key="$1" exit_code="$2" start_ts="$3" end_ts="$4" tail_text="$5"
    local gateway
    gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
    [ -f "$gateway" ] || return 0
    /usr/bin/python3 "$gateway" \
        --tier p0 \
        --source "cron:${job_key}" \
        --dedup-key "cron-fail:${job_key}" \
        -- "CRON FAIL $HOSTNAME_SHORT
Job: $job_key
Exit: $exit_code
Duration: $((end_ts - start_ts))s
$(printf '%s' "$tail_text" | tail -c 600)" >/dev/null 2>&1 || true
}

if [ -z "$SCRIPT" ]; then
    echo "Usage: cron-runner.sh <script> [args...]" >&2
    # A crontab line that lost its argument fails this way on EVERY tick and
    # writes no receipt at all — the most invisible of the three exits. Fixed
    # key because there is no job identity to derive; dedup collapses the
    # repeats to one alert per window.
    _now="$(date +%s)"
    alert_failure "_cron_runner_usage" 64 "$_now" "$_now" "cron-runner.sh invoked with no script argument"
    exit 64
fi

JOB_KEY="$(derive_job_key "$@")"
START_TS="$(date +%s)"

if [ ! -f "$SCRIPT" ]; then
    END_TS="$(date +%s)"
    echo "ERROR: $SCRIPT not found" >&2
    write_state "$JOB_KEY" "failed" "$START_TS" "$END_TS" 1 "$SCRIPT" "$@"
    # Armed to nothing (W81): the cron is scheduled, the payload is gone. This
    # says so out loud instead of leaving it in an unread receipt.
    alert_failure "$JOB_KEY" 1 "$START_TS" "$END_TS" "script not found: $SCRIPT"
    exit 1
fi

# Mirror the job's combined output to a tmpfile via tee so we can record the real
# failure cause in last_error. tee still writes to stdout, so the crontab per-job
# log ('>> log 2>&1') keeps getting everything; PIPESTATUS[0] preserves the job's
# true exit code despite the pipe.
ERR_TMP="$(mktemp "${TMPDIR:-/tmp}/cron-runner.XXXXXX" 2>/dev/null || true)"
if [ -n "$ERR_TMP" ]; then
    # Claim the voice ONLY on the branch that can capture the payload's output:
    # without the tmpfile a deferred alarm would be a dropped one.
    export CRON_ALARM_OWNER="$JOB_KEY"
    /bin/bash "$SCRIPT" "$@" 2>&1 | tee "$ERR_TMP"
    EXIT_CODE="${PIPESTATUS[0]}"
else
    /bin/bash "$SCRIPT" "$@"
    EXIT_CODE=$?
fi
END_TS="$(date +%s)"
STATUS="ok"
ALERT_BODY=""
if [ "$EXIT_CODE" -ne 0 ]; then
    STATUS="failed"
    if [ -n "$ERR_TMP" ] && [ -s "$ERR_TMP" ]; then
        export CRON_RUNNER_LAST_ERROR="$(tail -n 40 "$ERR_TMP" 2>/dev/null | tail -c 2000)"
    fi
    ALERT_BODY="${CRON_RUNNER_LAST_ERROR:-}"
    # Only the human-facing alarm swaps in the job's own sentence. The RECEIPT
    # deliberately keeps the raw tail: the DLQ autopilot classifies on
    # last_error, and a 40-line tail carries more for it to classify than one
    # curated line (superscar #9 — don't change a contract its readers didn't
    # ask to change).
    if _summary="$(deferred_summary "$ERR_TMP")" && [ -n "$_summary" ]; then
        ALERT_BODY="$_summary"
    fi
fi
[ -n "$ERR_TMP" ] && rm -f "$ERR_TMP"
write_state "$JOB_KEY" "$STATUS" "$START_TS" "$END_TS" "$EXIT_CODE" "$SCRIPT" "$@"
if [ "$EXIT_CODE" -ne 0 ]; then
    alert_failure "$JOB_KEY" "$EXIT_CODE" "$START_TS" "$END_TS" "$ALERT_BODY"
fi
exit "$EXIT_CODE"
