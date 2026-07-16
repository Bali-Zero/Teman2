#!/usr/bin/env bash
# disk_watchdog.sh — Telegram alert if root disk usage > 85%
#
# Hardening Team Wave 2 (2026-05-19, post-cicatrix WR2 panel).
#
# Why this exists: on 2026-05-14, com.balizero.intel.nightly died
# silently mid-SEO scrape because disk was 94% full (false launchd
# exit 0 because asyncpg got killed by OOM, not crash). Cron jobs
# that depend on disk-write succeed silently fail when disk fills
# faster than rotation. With this watchdog running once per day,
# Telegram alerts at 85% (15% headroom before any cron starts to
# truncate/fail/skip).
#
# Threshold rationale: 85% chosen because:
#   - Below 80% = no concern (steady-state)
#   - 80-85% = warning zone, manual cleanup recommended within week
#   - >85% = alert (15% = ~70GB on 460GB disk, ~3 days at typical
#     codebase growth rate including build artifacts + logs)
#   - >90% = critical (typically what triggered 2026-05-14 incident)
#
# Cooldown: 24h. Disk pressure is slow-moving; once-per-day alert
# is enough. State in ~/.agent/decisions/state/disk_watchdog_*.
#
# Reference:
#   cicatrix-scars.md (2026-05-14 intel.nightly disk full)
#   memory/discovery_intel_nightly_disk_full_2026_05_14.md

set -uo pipefail

THRESHOLD_PERCENT=85
COOLDOWN_SEC=86400  # 24h
STATE_DIR="${HOME}/.agent/decisions/state"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"

mkdir -p "$STATE_DIR"

if [[ -f "$SECRETS_FILE" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$SECRETS_FILE" 2>/dev/null || true
    set +a
fi

if [[ -z "${TELEGRAM_BOT_TOKEN:-}" || -z "${TELEGRAM_OWNER_CHAT_ID:-}" ]]; then
    echo "disk_watchdog: Telegram credentials missing, exiting silently" >&2
    exit 0
fi

# Parse df: "/dev/disk3s1s1   460Gi    12Gi    29Gi    29%    ..."
DISK_LINE=$(df -h /System/Volumes/Data | tail -1)
USED_PERCENT=$(echo "$DISK_LINE" | awk '{print $5}' | tr -d '%')
USED_HUMAN=$(echo "$DISK_LINE" | awk '{print $3}')
AVAIL_HUMAN=$(echo "$DISK_LINE" | awk '{print $4}')
TOTAL_HUMAN=$(echo "$DISK_LINE" | awk '{print $2}')

if ! [[ "$USED_PERCENT" =~ ^[0-9]+$ ]]; then
    echo "disk_watchdog: failed to parse df output, exiting" >&2
    exit 1
fi

if (( USED_PERCENT < THRESHOLD_PERCENT )); then
    echo "$(date '+%Y-%m-%d %H:%M:%S WITA') disk_watchdog: ${USED_PERCENT}% used, OK"
    exit 0
fi

# Per-disk cooldown
state_file="$STATE_DIR/disk_watchdog_root.state"
last_alert_ts=$(cat "$state_file" 2>/dev/null || echo 0)
NOW_TS=$(date +%s)
elapsed=$((NOW_TS - last_alert_ts))
if (( elapsed < COOLDOWN_SEC )); then
    echo "$(date '+%Y-%m-%d %H:%M:%S WITA') disk_watchdog: ${USED_PERCENT}% used but cooldown active (${elapsed}s/${COOLDOWN_SEC}s)"
    exit 0
fi

# Identify top 3 weight contributors (helps user act)
TOP_3=$(du -sh /Users/nuzantara/Desktop/* 2>/dev/null | sort -hr | head -3 | awk '{printf "  - %s %s\n", $1, $2}')

# Send Telegram alert
SEVERITY="WARNING"
[[ "$USED_PERCENT" -ge 90 ]] && SEVERITY="CRITICAL"

msg="💾 Disk ${SEVERITY}: ${USED_PERCENT}% used (${USED_HUMAN}/${TOTAL_HUMAN}, ${AVAIL_HUMAN} free)

Top Desktop dirs:
${TOP_3}

Hint: git gc, prune build artifacts, rotate logs."

# Notification gateway (cohort-3, 2026-07-07): disk full = act-now → tier p0.
# Gateway owns token resolution + 6h dedup; this script keeps its own cooldown.
gateway="$(dirname "$0")/tg_notify.py"
[ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
python3 "$gateway" --tier p0 --source disk-watchdog \
    --dedup-key "disk-watchdog:$(hostname -s)" -- "$msg" >/dev/null 2>&1 || true

echo "$NOW_TS" > "$state_file"
echo "$(date '+%Y-%m-%d %H:%M:%S WITA') disk_watchdog: ALERT sent (${USED_PERCENT}% used)"
exit 0
