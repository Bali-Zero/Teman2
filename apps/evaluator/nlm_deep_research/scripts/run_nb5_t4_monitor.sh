#!/usr/bin/env bash
# T4 Social Monitor for NB-5 Property & Real Estate Indonesia
# Monitors: Instagram (ATR/BPN, Kanwil, Kantah), X/Twitter, Web (tarubali, JDIH)
# Cron: 0 18 * * 2,4  (02:00 WITA Tue/Thu = 18:00 UTC Mon/Wed)
# Runs on Pro via OpenClaw — before NB-5 NLM pipeline at 02:25 WITA

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
LOG_FILE="$PROJECT_ROOT/apps/evaluator/nlm_deep_research/nb5_t4_monitor.log"
cd "$PROJECT_ROOT"

# T4-monitor-cure (2026-07-16): this wrapper carried NO secrets/PATH at all —
# t4_monitor.py's Haiku classifier shells out to `claude -p`, which fell back
# to the macOS-Keychain-stored OAuth token (inaccessible in a headless cron
# context) and exited non-zero on every call, driving admit=0 for 3 weeks.
# Mirrors the token/PATH sourcing already proven in
# infra/launchagents/wrappers/regulatory-watcher-run.sh (cure #1987) — not a
# new pattern. Also restores the `~/.local/bin` PATH entry (nlm CLI) that the
# sibling wrapper scripts/run_t4_monitor.sh already carries but this one lacked.
[ -f "$HOME/.nuzantara-secrets.env" ] && set -a && source "$HOME/.nuzantara-secrets.env" && set +a
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
if [ -n "${SSH_CONNECTION:-}" ] && [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && [ -n "${CLAUDE_CODE_OAUTH_TOKEN_1:-}" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_CODE_OAUTH_TOKEN_1"
fi

# Activate venv
if [ -f "apps/backend-rag/.venv/bin/activate" ]; then
    source apps/backend-rag/.venv/bin/activate
elif [ -f "apps/backend-rag/venv/bin/activate" ]; then
    source apps/backend-rag/venv/bin/activate
fi

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] NB-5 T4 monitor starting..." >> "$LOG_FILE"

# Run T4 monitor for NB-5 Property & Real Estate
# notebook-id = d9438180-5e63-4e2a-a473-6061101f6a8d (from t4_nb5_config.json)
python -m apps.evaluator.nlm_deep_research.t4_monitor \
    --notebook-id "d9438180-5e63-4e2a-a473-6061101f6a8d" \
    2>&1 | tee -a "$LOG_FILE"

EXIT_CODE=${PIPESTATUS[0]}

# Alert on failure — routed through the Telegram gateway (cohort pattern, see
# scripts/disk_watchdog.sh), replacing the previous direct HTTP call. The
# gateway owns token resolution + dedup; this script keeps its own exit-code
# gate. --tier p0: a failed T4 monitor run is actionable now (silent-broken
# ingestion into NB-5), not a cron-green digest item.
if [ "$EXIT_CODE" -ne 0 ]; then
    python3 "$PROJECT_ROOT/scripts/tg_notify.py" --tier p0 --source nb5-t4-monitor \
        --dedup-key "nb5-t4-monitor-fail" \
        -- "NB-5 T4 monitor failed (exit $EXIT_CODE). Check nb5_t4_monitor.log" \
        >/dev/null 2>&1 || true
fi

exit "$EXIT_CODE"
