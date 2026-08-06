#!/bin/bash
# Web-lead funnel report cron wrapper.
#
# Invoked weekly by LaunchAgent com.nuzantara.web-lead-funnel
# (template: infra/launchagents/com.nuzantara.web-lead-funnel.plist).
#
# Must run on the machine that OWNS the wa-mirror (the Pro): the arrival half
# of the funnel exists only in the local Postgres there. Elsewhere the report
# still runs and reports arrivals as UNKNOWN rather than zero, which is the
# whole point — see the module docstring.
#
# No secrets in the plist (scar 2026-04-29): both DSNs come from the
# environment or from ~/.nuzantara-secrets.env (0600).
set -uo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/nuzantara}"
LOG_FILE="${LOG_FILE:-$HOME/logs/web-lead-funnel.log}"
mkdir -p "$(dirname "$LOG_FILE")"

SECRETS_FILE="${NUZANTARA_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
# `[ -f ]` before sourcing: under `set -e` a failed `source` is a special
# builtin and EXITS the shell outright — `|| true` cannot save it (W108).
if [ -z "${DATABASE_URL:-}" ] && [ -f "$SECRETS_FILE" ]; then
    # shellcheck disable=SC1090
    set -a
    source "$SECRETS_FILE"
    set +a
fi

if [ -z "${DATABASE_URL:-}" ]; then
    # Unarmed-but-visible: every tick leaves a trace (W64: esistere ≠ armato).
    echo "[$(date -Iseconds)] SKIP DATABASE_URL not set (checked env + $SECRETS_FILE)" >> "$LOG_FILE"
    exit 0
fi

PYTHON_BIN=""
for candidate in \
    "$REPO_ROOT/apps/backend-rag/.venv/bin/python" \
    "/Users/nuzantara/nuzantara/apps/backend-rag/.venv/bin/python"; do
    if [ -x "$candidate" ] && "$candidate" -c "import asyncpg" 2>/dev/null; then
        PYTHON_BIN="$candidate"
        break
    fi
done
if [ -z "$PYTHON_BIN" ]; then
    echo "[$(date -Iseconds)] FAIL no python venv with asyncpg (repo_root=$REPO_ROOT)" >> "$LOG_FILE"
    exit 1
fi

# errexit disarmed around the job and the exit code CAPTURED, never inferred
# from having survived the line (W101 and its four recidivas).
set +e
"$PYTHON_BIN" "$REPO_ROOT/scripts/web_lead_funnel_report.py" --telegram >> "$LOG_FILE" 2>&1
rc=$?
set -e

echo "[$(date -Iseconds)] pass complete rc=$rc" >> "$LOG_FILE"
exit "$rc"
