#!/usr/bin/env bash
# cron-state.sh - run an arbitrary cron command and emit a Cell-readable receipt.

set -uo pipefail

JOB_NAME="${1:-}"
if [ -n "$JOB_NAME" ]; then
    shift
fi

export PATH="/Users/nuzantara/.local/bin:/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export HOME="${HOME:-/Users/nuzantara}"

STATE_DIR="${CRON_STATE_DIR:-$HOME/.agent/decisions/state}"
HOSTNAME_SHORT="$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)"

sanitize_key() {
    printf '%s' "$1" \
        | tr '[:upper:]' '[:lower:]' \
        | sed 's/[^a-z0-9]/_/g; s/__*/_/g; s/^_//; s/_$//'
}

write_state() {
    local job_key="$1"
    local status="$2"
    local start_ts="$3"
    local end_ts="$4"
    local exit_code="$5"
    local command_text="$6"
    local state_file tmp

    mkdir -p "$STATE_DIR"
    state_file="$STATE_DIR/$job_key.last.json"
    tmp="$state_file.$$"

    if command -v python3 >/dev/null 2>&1; then
        python3 - "$tmp" "$job_key" "$status" "$start_ts" "$end_ts" "$exit_code" "$command_text" "$HOSTNAME_SHORT" <<'PY'
import json
import sys

path, job, status, start_ts, end_ts, exit_code, command, host = sys.argv[1:]
start = int(float(start_ts))
end = int(float(end_ts))
payload = {
    "job": job,
    "ts": end,
    "status": status,
    "host": host,
    "source": "cron-state",
    "duration_ms": max(0, (end - start) * 1000),
    "command": command,
    "exit_code": int(exit_code),
}
if status != "ok":
    payload["last_error"] = f"exit {exit_code}"
with open(path, "w", encoding="utf-8") as fh:
    json.dump(payload, fh, separators=(",", ":"))
    fh.write("\n")
PY
    else
        printf '{"job":"%s","ts":%d,"status":"%s","host":"%s","source":"cron-state","duration_ms":%d,"exit_code":%d}\n' \
            "$job_key" "$end_ts" "$status" "$HOSTNAME_SHORT" "$(( (end_ts - start_ts) * 1000 ))" "$exit_code" > "$tmp"
    fi

    mv "$tmp" "$state_file"
}

if [ -z "$JOB_NAME" ] || [ "$#" -eq 0 ]; then
    echo "Usage: cron-state.sh <job-name> <command...>" >&2
    exit 64
fi

JOB_KEY="$(sanitize_key "$JOB_NAME")"
START_TS="$(date +%s)"
COMMAND_TEXT="$(printf '%q ' "$@")"

"$@"
EXIT_CODE=$?
END_TS="$(date +%s)"
STATUS="ok"
if [ "$EXIT_CODE" -ne 0 ]; then
    STATUS="failed"
fi
write_state "$JOB_KEY" "$STATUS" "$START_TS" "$END_TS" "$EXIT_CODE" "$COMMAND_TEXT"
exit "$EXIT_CODE"
