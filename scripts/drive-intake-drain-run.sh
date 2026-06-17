#!/bin/bash
# drive-intake-drain-run.sh — wrapper for the com.balizero.drive-intake-drain
# LaunchAgent. Loads backend secrets (.env via CWD + python-dotenv) and the
# Drive service-account JSON (read at runtime from a 0600 file — NEVER inlined
# in the plist, cicatrix #4) before exec'ing the drain.
#
# Source of truth: THIS repo file (no HOME-fork — superscar #1). The plist passes
# machine-specifics as env (INTAKE_REPO_ROOT / INTAKE_VENV_PYTHON / INTAKE_SA_FILE
# / INTAKE_DRIVE_SCOPE_FOLDER_ID), so this script stays static + tracked and is
# executed in place from the repo. install_drive_intake.sh wires the env values.
set -euo pipefail

: "${INTAKE_REPO_ROOT:?INTAKE_REPO_ROOT not set (installer wires it via the plist)}"
: "${INTAKE_VENV_PYTHON:?INTAKE_VENV_PYTHON not set}"
: "${INTAKE_SA_FILE:?INTAKE_SA_FILE not set}"
: "${INTAKE_DRIVE_SCOPE_FOLDER_ID:?INTAKE_DRIVE_SCOPE_FOLDER_ID not set}"

# Fail loud, not blind: a missing/unreadable SA file means no Drive creds, which
# silently ingests 0 (superscar #2 cron theater). Exit non-zero so it is visible.
[ -r "$INTAKE_SA_FILE" ] || { echo "drain: SA file unreadable: $INTAKE_SA_FILE" >&2; exit 78; }

cd "$INTAKE_REPO_ROOT/apps/backend-rag"

# Service-account JSON read from the 0600 file at runtime (never in the plist).
GOOGLE_SERVICE_ACCOUNT_JSON="$(cat "$INTAKE_SA_FILE")"
export GOOGLE_SERVICE_ACCOUNT_JSON
export GOOGLE_CREDENTIALS_JSON="$GOOGLE_SERVICE_ACCOUNT_JSON"
export INTAKE_DRIVE_SCOPE_FOLDER_ID

exec "$INTAKE_VENV_PYTHON" "$INTAKE_REPO_ROOT/scripts/drive_intake_drain.py"
