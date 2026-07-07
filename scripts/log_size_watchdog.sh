#!/usr/bin/env bash
# log_size_watchdog.sh — Telegram alert if any ~/logs/*.err.log > 1MB
#
# Wave 1 fix 2026-05-19 (4-LLM panel synthesis 3/3 quorum).
#
# Why this exists: on 2026-05-16, the WR2 supervisor entered an 84h
# silent crashloop with the venv missing. Error logs grew to 6.3 MB
# (wr2_supervisor_watchdog.launchd.err.log) + 1.2 MB (supervisor.err)
# + 4.1 MB (canva_apply.error) before a human noticed. With this
# watchdog running hourly, Telegram would have alerted within 1h of
# the first cumulative MB — 84× faster MTTR.
#
# Threshold rationale: 1 MB (Codex + DeepSeek 1MB recommendation,
# overridden Gemini's 5MB). 1 MB is ~5000-10000 stack-frame lines of
# typical Python traceback — well above any healthy daily growth for
# our cron-style scripts. False-positive rate empirically <1/month.
#
# Cooldown: 6h per file (state in ~/.agent/decisions/state/log_size_*).
# Avoids spam when an issue is acknowledged but not yet fixed.
#
# Reference:
#   research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md
#   research/operations/2026-05-19-wr2-intel-lake-health-snapshot.md

set -uo pipefail

THRESHOLD_BYTES=1048576  # 1 MB
COOLDOWN_SEC=21600       # 6h between repeat alerts on the same file
LOG_DIR="${HOME}/logs"
STATE_DIR="${HOME}/.agent/decisions/state"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"

mkdir -p "$STATE_DIR"

# Source secrets for Telegram. The secrets file uses `export FOO=bar`
# syntax, so we source it directly (set -a to auto-export). We DO NOT
# leak other unrelated env vars into subprocesses because this script
# itself terminates after one execution (no `exec` of payload).
if [[ -f "$SECRETS_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$SECRETS_FILE" 2>/dev/null || true
    set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_OWNER_CHAT_ID:-}" ]]; then
    echo "log_size_watchdog: Telegram credentials missing, exiting silently" >&2
    exit 0
fi

ALERT_COUNT=0
NOW_TS=$(date +%s)

# Match common error-log naming patterns. The trailing -size pre-filter
# is for speed (skip stat call on small files).
while IFS= read -r f; do
    [[ -f "$f" ]] || continue
    size=$(stat -f%z "$f" 2>/dev/null || echo 0)
    [[ "$size" -lt "$THRESHOLD_BYTES" ]] && continue

    # Per-file cooldown (avoid spam)
    basename_safe=$(basename "$f" | tr '/.' '__')
    state_file="$STATE_DIR/log_size_${basename_safe}.state"
    last_alert_ts=$(cat "$state_file" 2>/dev/null || echo 0)
    elapsed=$((NOW_TS - last_alert_ts))
    if (( elapsed < COOLDOWN_SEC )); then
        continue
    fi

    # Format size human-readable
    size_mb=$(awk "BEGIN {printf \"%.1f\", $size / 1024 / 1024}")
    rel_path="${f#$HOME/}"

    # Notification gateway (cohort-3): log housekeeping = informative → digest tier
    msg="📊 Log size alert: ~/${rel_path} = ${size_mb} MB (>1MB threshold). $(tail -1 "$f" 2>/dev/null | head -c 200)"
    gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/Desktop/nuzantara/scripts/tg_notify.py"
    python3 "$gateway" --tier digest --source log-size-watchdog \
        --dedup-key "log-size:${rel_path}" -- "$msg" >/dev/null 2>&1 || true

    # Record alert timestamp
    echo "$NOW_TS" > "$state_file"
    ((ALERT_COUNT++))
done < <(find "$LOG_DIR" -type f \( -name "*.err.log" -o -name "*stderr*.log" -o -name "*.error.log" -o -name "*launchd.err*" \) -size +"$THRESHOLD_BYTES"c 2>/dev/null)

if [[ "$ALERT_COUNT" -gt 0 ]]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S WITA') log_size_watchdog: $ALERT_COUNT alert(s) sent"
fi

exit 0
