#!/usr/bin/env bash
set -euo pipefail

APP="nuzantara-rag"
DURATION_SECONDS="0"
OUTPUT=""
SNAPSHOT="false"
PATTERN="permission denied|insufficient privilege|team-activity|admin/team|practices"

usage() {
  cat <<'USAGE'
Usage:
  bash scripts/fly_permission_log_monitor.sh --snapshot
  bash scripts/fly_permission_log_monitor.sh --duration-seconds 86400 --output /tmp/nuzantara-rag-permission-monitor.log

Options:
  --app NAME                 Fly app name. Default: nuzantara-rag
  --duration-seconds N       Stream duration. 0 means snapshot/no-tail.
  --output PATH              Append matching lines to this file.
  --pattern REGEX            Extended grep pattern.
  --snapshot                 Force a no-tail snapshot.
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --app)
      APP="$2"
      shift 2
      ;;
    --duration-seconds)
      DURATION_SECONDS="$2"
      shift 2
      ;;
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    --pattern)
      PATTERN="$2"
      shift 2
      ;;
    --snapshot)
      SNAPSHOT="true"
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! command -v fly >/dev/null 2>&1; then
  echo "fly CLI not found. Run this on Pro or in an environment with fly installed." >&2
  exit 1
fi

if ! [[ "$DURATION_SECONDS" =~ ^[0-9]+$ ]]; then
  echo "--duration-seconds must be a non-negative integer" >&2
  exit 2
fi

filter_logs() {
  perl -pe 's/\e\[[0-9;]*[A-Za-z]//g' \
    | grep -E --line-buffered -i "$PATTERN" || true
}

write_output() {
  if [[ -n "$OUTPUT" ]]; then
    mkdir -p "$(dirname "$OUTPUT")"
    tee -a "$OUTPUT"
  else
    cat
  fi
}

echo "Monitoring Fly app=$APP pattern=$PATTERN duration_seconds=$DURATION_SECONDS"

if [[ "$SNAPSHOT" == "true" || "$DURATION_SECONDS" == "0" ]]; then
  fly logs --app "$APP" --no-tail | filter_logs | write_output
  exit 0
fi

if command -v timeout >/dev/null 2>&1; then
  timeout "$DURATION_SECONDS" fly logs --app "$APP" | filter_logs | write_output
else
  fly logs --app "$APP" &
  FLY_PID=$!
  trap 'kill "$FLY_PID" 2>/dev/null || true' EXIT
  sleep "$DURATION_SECONDS"
  kill "$FLY_PID" 2>/dev/null || true
  wait "$FLY_PID" 2>/dev/null || true
fi
