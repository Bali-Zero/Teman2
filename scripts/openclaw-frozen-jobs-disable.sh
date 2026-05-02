#!/usr/bin/env bash
# openclaw-frozen-jobs-disable.sh — Sprint 0 Track A5
#
# Mark every job in ~/.openclaw/cron/jobs.json as enabled=false so when
# OpenClaw v2026.4.29 unfreezes the scheduler, the queue stays inert and
# does NOT collide with cron-agent-python.
#
# Usage:
#   bash scripts/openclaw-frozen-jobs-disable.sh --dry-run   # default; print plan
#   bash scripts/openclaw-frozen-jobs-disable.sh --apply     # actually edit
#   bash scripts/openclaw-frozen-jobs-disable.sh --revert    # restore from backup
#
# Backup: --apply always copies jobs.json to jobs.json.pre-disable-<date>
# before writing. The --revert flag picks the most recent backup and
# restores it.
#
# Idempotent: re-running --apply has no effect (jobs are already disabled
# after the first run).
#
# Reference: brainstorm 2026-05-02 round 2 § "Disabilitare 24 OpenClaw frozen jobs".

set -euo pipefail

JOBS="${HOME}/.openclaw/cron/jobs.json"

if [[ ! -f "$JOBS" ]]; then
  echo "ERROR: $JOBS not found — OpenClaw not installed?" >&2
  exit 0   # exit 0 so cron/automation doesn't error on a clean host
fi
if ! command -v jq >/dev/null 2>&1; then
  echo "ERROR: jq required for safe JSON edits" >&2
  exit 2
fi

MODE="${1:-}"
case "$MODE" in
  --apply|--dry-run|--revert) ;;
  ""|--help|-h) sed -n '2,22p' "$0"; exit 0 ;;
  *)
    echo "ERROR: unknown command '$MODE'" >&2
    exit 2
    ;;
esac

count_jobs() {
  jq 'length' "$1"
}

count_enabled() {
  jq '[.[] | select(.enabled != false)] | length' "$1"
}

if [[ "$MODE" == "--revert" ]]; then
  latest_backup="$(ls -t "${JOBS}".pre-disable-* 2>/dev/null | head -1 || true)"
  if [[ -z "$latest_backup" ]]; then
    echo "ERROR: no backup found at ${JOBS}.pre-disable-*" >&2
    exit 1
  fi
  cp "$latest_backup" "$JOBS"
  echo "[frozen-jobs] restored from $latest_backup"
  echo "[frozen-jobs] hot-reload OpenClaw to pick up changes:"
  echo "[frozen-jobs]   launchctl kickstart -k gui/\$(id -u)/ai.openclaw.gateway"
  exit 0
fi

total="$(count_jobs "$JOBS")"
enabled="$(count_enabled "$JOBS")"
echo "[frozen-jobs] state: total=$total enabled=$enabled disabled=$(( total - enabled ))"

if (( enabled == 0 )); then
  echo "[frozen-jobs] all already disabled — no-op"
  exit 0
fi

if [[ "$MODE" == "--dry-run" ]]; then
  echo "[frozen-jobs] would disable $enabled job(s) (--apply to commit)"
  jq -r '.[] | select(.enabled != false) | "  - " + (.name // .id // "<no-id>") + "  schedule=" + (.schedule // "<none>")' "$JOBS"
  exit 0
fi

# --apply
backup="${JOBS}.pre-disable-$(date +%F)"
cp "$JOBS" "$backup"
echo "[frozen-jobs] backup: $backup"

tmp="$(mktemp)"
jq '
  map(
    .enabled = false |
    ._disabled_at = "'"$(date +%F)"'" |
    ._disabled_by = "Sprint 0 Track A5 — split clean Opzione C"
  )
' "$JOBS" > "$tmp"
mv "$tmp" "$JOBS"

new_enabled="$(count_enabled "$JOBS")"
echo "[frozen-jobs] disabled: $enabled job(s); now enabled=$new_enabled"
echo "[frozen-jobs] hot-reload OpenClaw to pick up changes:"
echo "[frozen-jobs]   launchctl kickstart -k gui/\$(id -u)/ai.openclaw.gateway"
