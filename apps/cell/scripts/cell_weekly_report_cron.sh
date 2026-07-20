#!/bin/bash
# CELL Weekly Report cron wrapper.
# Runs the Python report against the Cell's actual DB (Fly via flyctl proxy on :15432).
# Activated by crontab: every Sunday at 08:00 WITA (`0 8 * * 0 ...`).

set -euo pipefail

CELL_DIR="/Users/nuzantara/nuzantara/apps/cell"
VENV="${CELL_DIR}/.venv/bin/python"
SCRIPT="${CELL_DIR}/scripts/cell_weekly_report.py"

# Cell main process points at Fly Postgres via local flyctl proxy on port 15432.
# The weekly-report script must read from the same DB to see real pulses.
# Source from secrets file (CELL_DATABASE_URL or DATABASE_URL key) — never
# inline the password here, secret-scanners (Detect Secrets) flag it on PR.
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [ -f "${SECRETS_FILE}" ]; then
    set -a; source "${SECRETS_FILE}"; set +a
fi
# Honour the fallback this script's own comment promises ("CELL_DATABASE_URL or
# DATABASE_URL key"): the generic DATABASE_URL points at the same Fly Postgres,
# so use it when the cell-specific var is absent. Without this the report failed
# every Sunday since 2026-05-10 (exit 3) despite the DSN being present in secrets.
: "${CELL_DATABASE_URL:=${DATABASE_URL:-}}"
if [ -z "${CELL_DATABASE_URL:-}" ]; then
    echo "[cell-weekly-report] FATAL: CELL_DATABASE_URL not set." >&2
    echo "[cell-weekly-report]        Add it to ${SECRETS_FILE} or export before running." >&2
    echo "[cell-weekly-report]        Expected DSN format: postgresql scheme + user + password + host:port + db" >&2
    echo "[cell-weekly-report]        Reference example: apps/cell/cell/core/config.py" >&2
    exit 3
fi
export CELL_DATABASE_URL

# Fail fast if the venv or script are missing — the previous wrapper just
# vanished and the cron logged "script not found" silently for 2 weeks.
[ -x "${VENV}" ] || { echo "[cell-weekly-report] FATAL: venv missing: ${VENV}" >&2; exit 2; }
[ -f "${SCRIPT}" ] || { echo "[cell-weekly-report] FATAL: script missing: ${SCRIPT}" >&2; exit 2; }

cd "${CELL_DIR}"
exec "${VENV}" "${SCRIPT}"
