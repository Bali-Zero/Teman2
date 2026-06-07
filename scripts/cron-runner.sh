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
    payload["last_error"] = f"exit {exit_code}"
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

if [ -z "$SCRIPT" ]; then
    echo "Usage: cron-runner.sh <script> [args...]" >&2
    exit 64
fi

JOB_KEY="$(derive_job_key "$@")"
START_TS="$(date +%s)"

if [ ! -f "$SCRIPT" ]; then
    END_TS="$(date +%s)"
    echo "ERROR: $SCRIPT not found" >&2
    write_state "$JOB_KEY" "failed" "$START_TS" "$END_TS" 1 "$SCRIPT" "$@"
    exit 1
fi

/bin/bash "$SCRIPT" "$@"
EXIT_CODE=$?
END_TS="$(date +%s)"
STATUS="ok"
if [ "$EXIT_CODE" -ne 0 ]; then
    STATUS="failed"
fi
write_state "$JOB_KEY" "$STATUS" "$START_TS" "$END_TS" "$EXIT_CODE" "$SCRIPT" "$@"
exit "$EXIT_CODE"
