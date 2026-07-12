#!/usr/bin/env bash
# run-nb-curator-mode-c.sh — invoke nb-curator agent in Mode C
#
# Schedule (set in com.balizero.nb-curator.mode-c.weekly.plist):
#   every Monday 05:00 WITA
#
# Scope decision happens inside the agent based on today's date:
#   day-of-month <= 7 AND Monday → full pass (5 NB + stale-all)
#   any other Monday             → Press + stale-all only
#
# Stale >90 days runs every Monday for all 5 NB.
#
# Output:
#   - Markdown report at ~/Desktop/nuzantara/research/nb-health/YYYY-MM-nb-intel-curation.md
#   - Telegram digest to chat_id 1125336968 (from agent)
# Failure handling:
#   - Wrapper redirects stdout+stderr to ~/logs/nb-curator-mode-c.log
#   - Telegram alert if exit != 0
#
# W89 class-audit fix (2026-07-11, PENDING-ARMS ledger ~68): sonnet-5 in --print mode can
# silently spawn its work as a background task; the CLI kills it at the print-mode ceiling
# and exits 0 with no report on disk (incident: regulatory-watcher 2026-07-05). Fix here:
# raise the background ceiling, tell the model inline never to background, and log an
# explicit "used: tier1-<model>" provenance line (single-tier by design — this agent's
# NotebookLM MCP tool access needs Claude, not agy/codex/ollama).

set -uo pipefail

LOG_FILE="${HOME}/logs/nb-curator-mode-c.log"
mkdir -p "$(dirname "$LOG_FILE")"

# Load secrets for Telegram alerting on wrapper-level failure
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
if [[ -f "$SECRETS_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a; source "$SECRETS_FILE"; set +a
fi

PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME}/.pyenv/versions/3.11.11/bin:${PATH:-}"
export PATH HOME

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >> "$LOG_FILE"
}

log "=== nb-curator Mode C run starting ==="

# sonnet-5 --print + background tasks (W89 class-audit, 2026-07-11): the CLI kills
# backgrounded work after the print-mode ceiling; 30min keeps a legitimate full-pass run
# (5 NB + dedup clustering) alive.
export CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS="${CLAUDE_CODE_PRINT_BG_WAIT_CEILING_MS:-1800000}"

# Invoke claude CLI to run the nb-curator agent in Mode C.
# The agent reads the date itself and decides scope (full vs Press-only).
PROMPT="Run nb-curator agent in Mode C (Dedupe/Summarize). Read today's date, decide scope per the schedule in your spec (day-of-month <=7 AND Monday = full pass; else Press + stale-all). Emit markdown report under ~/Desktop/nuzantara/research/nb-health/ and Telegram digest. Do NOT call any nlm rm or any mutating command — propose-only per Article 1. Do ALL the work inline in this turn — never spawn a background task or background agent for this; this is a one-shot print-mode run and backgrounded work is terminated at exit, leaving no report on disk (W89 class-audit, regulatory-watcher incident 2026-07-05)."

if ! command -v claude >/dev/null 2>&1; then
    log "FAIL: claude CLI not in PATH"
    exit 127
fi

# Use subagent invocation via stdin so we don't depend on a specific CLI flag.
# The agent file at ~/.claude/agents/nb-curator.md is autoloaded.
START_EPOCH=$(date +%s)

# Allow up to 30 min for the full pass (5 NB × ~3min each + dedup clustering)
timeout 1800 claude -p "$PROMPT" --model claude-sonnet-5 \
    >> "$LOG_FILE" 2>&1
EXIT=$?

END_EPOCH=$(date +%s)
DURATION=$((END_EPOCH - START_EPOCH))

log "=== nb-curator Mode C done (exit=${EXIT}, duration=${DURATION}s) ==="

# Explicit tier-provenance line (W89 class-audit, 2026-07-11): single-tier by design (no
# claude-cascade.sh fallback — NotebookLM MCP access needs Claude specifically).
if [[ "$EXIT" -eq 0 ]]; then
    log "[nb-curator-mode-c] used: tier1-claude-sonnet-5 (exit=0)"
else
    log "[nb-curator-mode-c] agent run FAILED (exit=${EXIT}) model=claude-sonnet-5"
fi

if [[ "$EXIT" -ne 0 ]]; then
    # Notification gateway (post-#2263 canon promotion): tg_notify.py owns token
    # resolution + dedup — no env-token gate, the alert must not vanish silently.
    msg="⚠️ nb-curator Mode C failed (exit=${EXIT}, ${DURATION}s). Log: ${LOG_FILE}"
    gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/Desktop/nuzantara/scripts/tg_notify.py"
    python3 "$gateway" --tier p0 --source nb-curator-mode-c \
        --dedup-key "nb-curator-mode-c:$(hostname -s)" -- "$msg" >/dev/null 2>&1 || true
fi

exit "$EXIT"
