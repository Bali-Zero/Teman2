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

ORGAN_ID="pro.web_lead_funnel"

# --- G2 organism heartbeat sidecar (scripts/lib/heartbeat.{sh,py} convention) ---
# Every exit below publishes to ~/.organism/last_seen/pro.web_lead_funnel.json,
# so this organ's own liveness is provable rather than assumed — including the
# exits that do no work. Resolved before the kill switch so a deliberately
# stopped organ still publishes a "disabled" signal: otherwise the healer reads
# silence as death and resurrects something an operator turned off on purpose.
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$HOME/scripts/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$REPO_ROOT/scripts/lib/heartbeat.sh"
fi

# --- G5 kill switch: stop the organ without uninstalling the plist ---
if [ "${WEB_LEAD_FUNNEL_ENABLED:-true}" = "false" ]; then
    echo "[$(date -Iseconds)] kill switch WEB_LEAD_FUNNEL_ENABLED=false — exiting" >> "$LOG_FILE"
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "$ORGAN_ID" "disabled" "kill switch"
    exit 0
fi

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
    # Unarmed-but-visible: every tick leaves a trace (W64: esistere ≠ armato),
    # and the heartbeat says WHY rather than simply going quiet.
    echo "[$(date -Iseconds)] SKIP DATABASE_URL not set (checked env + $SECRETS_FILE)" >> "$LOG_FILE"
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "$ORGAN_ID" "degraded" "DATABASE_URL not set"
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
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "$ORGAN_ID" "error" "no python venv with asyncpg"
    exit 1
fi

# errexit disarmed around the job and the exit code CAPTURED, never inferred
# from having survived the line (W101 and its four recidivas).
set +e
"$PYTHON_BIN" "$REPO_ROOT/scripts/web_lead_funnel_report.py" --telegram >> "$LOG_FILE" 2>&1
rc=$?
set -e

echo "[$(date -Iseconds)] pass complete rc=$rc" >> "$LOG_FILE"

# The heartbeat reports the CAPTURED exit code, never the fact that this line
# was reached — a wrapper that survives is not a job that succeeded (W101).
if [ "$rc" -eq 0 ]; then
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "$ORGAN_ID" "ok" "report sent"
else
    [ -f "$HEARTBEAT_LIB" ] && bash "$HEARTBEAT_LIB" "$ORGAN_ID" "error" "report exited rc=$rc"
fi

exit "$rc"
