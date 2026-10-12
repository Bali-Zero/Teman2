#!/usr/bin/env bash
# detect_secrets_nightly_alert.sh — legacy-named composer for a failed manual
# full-tree run of security.yml. Scheduled scans now belong to the Mini organ.
#
# The manual run stays on the CI-native notifier because an ephemeral runner
# has no persistent fleet spool. The Mini organ uses scripts/tg_notify.py.
#
# Honesty invariant (W114/W106 — "a message that inventories mutable state
# lies"): this script does not assume the job failed BECAUSE a secret was
# found. The same job can also fail earlier — `pip install detect-secrets`,
# the scan itself crashing, or the auto-triage script erroring — and none of
# those leave a findings summary behind. The message says only what it can
# prove: if a summary file was captured it is quoted verbatim; if not, the
# message says so explicitly, never fabricating a "secret found" claim the
# run cannot back.
#
# Usage:
#   EVENT_NAME=workflow_dispatch RUN_URL=https://... SUMMARY_FILE=/tmp/x.txt \
#     TELEGRAM_BOT_TOKEN=... TELEGRAM_OWNER_CHAT_ID=... \
#     bash detect_secrets_nightly_alert.sh
#
# TELEGRAM_NOTIFY_BIN overrides the gateway binary — tests point this at a
# stub so the guilt/innocence corpus never touches the network.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NOTIFY_BIN="${TELEGRAM_NOTIFY_BIN:-${SCRIPT_DIR}/telegram_notify.sh}"

EVENT_NAME="${EVENT_NAME:-unknown}"
RUN_URL="${RUN_URL:-}"
SUMMARY_FILE="${SUMMARY_FILE:-}"

SUMMARY="(no findings summary captured for this run — the failure may be earlier in the job: pip install, the scan itself, or auto-triage; check the run log)"
if [ -n "${SUMMARY_FILE}" ] && [ -s "${SUMMARY_FILE}" ]; then
  SUMMARY="$(head -c 2500 "${SUMMARY_FILE}")"
fi

TEXT="$(printf '%s\n' \
  "Detect Secrets - manual full-tree scan FAILED (event: ${EVENT_NAME})" \
  "" \
  "Diff-scoped PR runs only see changed files; Mini owns the scheduled full-tree scan." \
  "" \
  "${SUMMARY}" \
  "" \
  "Audit: python scripts/detect_secrets_auto_triage.py --report" \
  "" \
  "${RUN_URL}")"

bash "${NOTIFY_BIN}" --text "${TEXT}"
