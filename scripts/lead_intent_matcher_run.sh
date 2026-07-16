#!/bin/bash
# Lead intent → clients matcher cron wrapper (content-funnel "Filo 1").
#
# Invoked every 5 min by LaunchAgent com.nuzantara.lead-intent-matcher
# (template: infra/launchagents/com.nuzantara.lead-intent-matcher.plist).
# Runbook: docs/runbooks/lead-intent-matcher.md
#
# No secrets in the plist (scar 2026-04-29 plist-secret-leak): DATABASE_URL
# comes from the environment or from ~/.nuzantara-secrets.env (0600).
set -uo pipefail

REPO_ROOT="${REPO_ROOT:-$HOME/nuzantara}"
LOG_FILE="${LOG_FILE:-$HOME/logs/lead-intent-matcher.log}"
mkdir -p "$(dirname "$LOG_FILE")"

SECRETS_FILE="${NUZANTARA_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
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

"$PYTHON_BIN" "$REPO_ROOT/scripts/lead_intent_matcher.py" >> "$LOG_FILE" 2>&1
rc=$?
echo "[$(date -Iseconds)] pass complete rc=$rc" >> "$LOG_FILE"
exit "$rc"
