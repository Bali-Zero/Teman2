#!/usr/bin/env bash
# detect_secrets_nightly_alert.sh — page when the FULL-TREE Detect Secrets
# scan fails (schedule / workflow_dispatch runs of security.yml only).
#
# WHY THIS EXISTS (audit lever L3, 2026-08-21,
# research/operations/2026-08-21-token-ceremony-ci-system-audit.md §7): PR and
# merge-queue runs of the `detect-secrets` job now scan only the diff's
# changed files (#4488, merge-base anchored via hotzone_changed_files.sh) — a
# secret sitting in a file no PR touched is caught only by the scheduled
# full-tree run. `main-push-failure-watch.yml` already pages the owner on ANY
# "Security Scanning" workflow failure on push/schedule to main, but it names
# only the WORKFLOW, never which of its 6 jobs failed or what a secrets scan
# actually found — a dependency CVE from Snyk and a leaked credential read
# identically in that generic message. This is the job-specific,
# content-bearing alert layered on top of it (the same pattern security.yml
# already uses for its Docker-build-failure alert): it fires only for THIS
# job on the full-tree path, and it quotes what was found.
#
# NOT scripts/tg_notify.py. That gateway is fleet-native — it spools under
# $HOME, dedups on a repeat ladder, and batches into a digest — none of which
# survive an ephemeral GitHub Actions runner with no persistent $HOME between
# runs; routing through it here would silently defeat its own contract. This
# workflow's own file already established the CI-native, NON-BLIND
# convention for this exact problem (see the "Telegram alert — production
# image failed to BUILD" step further down in security.yml):
# scripts/ci/telegram_notify.sh, which judges the Telegram API's REPLY via
# telegram_verdict.sh (W104: curl's exit code lies — a rotated token still
# answers 200 or a well-formed 401) instead of trusting a POST's exit code.
# That is the identical "judge the verdict, never the exit code" contract the
# antidotes lint (scripts/tests/test_gateway_callers_read_the_verdict.py)
# enforces for tg_notify.py's own Python callers — applied here through the
# gateway this workflow already uses, rather than introducing a second one
# mid-file for one step.
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
#   EVENT_NAME=schedule RUN_URL=https://... SUMMARY_FILE=/tmp/x.txt \
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
  "Detect Secrets - nightly full-tree scan FAILED (event: ${EVENT_NAME})" \
  "" \
  "Diff-scoped PR/queue runs (lever L3) only see changed files - this scheduled full-tree run is the net for anything else." \
  "" \
  "${SUMMARY}" \
  "" \
  "Audit: python scripts/detect_secrets_auto_triage.py --report" \
  "" \
  "${RUN_URL}")"

bash "${NOTIFY_BIN}" --text "${TEXT}"
