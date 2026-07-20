#!/bin/zsh
# chronic_failure_digest.sh — wrapper for the weekly chronic-failure digest.
#
# Sources Telegram secrets the same way ~/scripts/audit-launchd-daily.sh does
# (from ~/.nuzantara-secrets.env), then runs the pure-aggregation Python digest.
# Invoked by com.nuzantara.chronic-failure-digest.weekly.plist (Mon 08:30 WITA).
#
# READ-ONLY: reads daily audit snapshots + circuit_breakers.json + dlq.json,
# emits ONE Telegram digest of jobs red >= THRESHOLD consecutive days. No LLM,
# no mutation of any state file. Complements the daily delta-only audit
# (closes the W55 suppression gap where steady-state red drops off the radar).

set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${REPO_ROOT:-/Users/nuzantara/nuzantara}"
DIGEST_SCRIPT="$REPO_ROOT/infra/launchagents/chronic_failure_digest.py"

# Source Telegram secrets (TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID).
if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    # shellcheck disable=SC1091
    set -a; source "$HOME/.nuzantara-secrets.env"; set +a
fi

# Sensible default chat id matches the rest of the fleet (Zero's owner chat).
export TELEGRAM_OWNER_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"

if [[ ! -f "$DIGEST_SCRIPT" ]]; then
    echo "[chronic-failure-digest] FATAL: $DIGEST_SCRIPT missing" >&2
    exit 66
fi

exec python3 "$DIGEST_SCRIPT"
