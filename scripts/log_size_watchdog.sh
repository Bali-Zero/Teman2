#!/usr/bin/env bash
# log_size_watchdog.sh — Telegram alert if an ~/logs/*.err.log passes the
#                        size at which the rotator will actually trim it
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
# Threshold rationale — REVISED 2026-08-06 after measuring the channel.
#
# It was a standalone 1 MB ("false-positive rate empirically <1/month",
# Codex + DeepSeek panel 2026-05-19). Measured over the 29.5 days to
# 2026-08-06: this script produced 1798 of the organism's 5202 Telegram
# events — 34.6%, the single loudest source on the fleet, 19 files each
# re-announced roughly every 6 hours for a month.
#
# None of them was a false positive, and none was actionable either.
# The cure — log-rotate-run.sh — trims error logs at 10 MB. Between the
# 1 MB alarm line and the 10 MB cure line was a dead zone: every one of
# the 11 files then over the line sat at 1.1-7.1 MB, so all of them were
# permanently loud and permanently ineligible for rotation. Three had
# stopped being written altogether (mtime 04/07, 21/07, 31/07) and would
# have been announced forever.
#
# This gap had already been found once. log-rotate-run.sh carries its own
# comment dated 2026-07-20 naming the "1-50MB dead zone" and lowering its
# error threshold 50 -> 10 MB to close it. That closed it half way; the
# population simply lived in what was left.
#
# So the value is not the defect — the INDEPENDENCE is. An alarm line and
# a cure line maintained as two unrelated constants will drift apart again
# the next time either is tuned. This threshold now DERIVES from the
# rotator's own knob, and scripts/tests/test_log_watchdog_dead_zone.py
# fails the build if the two ever separate. An alarm must name a condition
# some organ will act on; otherwise it is a metronome that teaches everyone
# to ignore the channel where the real ones arrive.
#
# Measurement: research/operations/2026-08-06-telegram-messaging-study.md
#
# Cooldown: 6h per file (state in ~/.agent/decisions/state/log_size_*).
# Avoids spam when an issue is acknowledged but not yet fixed.
#
# Reference:
#   research/operations/2026-05-19-wr2-intel-lake-fixes-panel.md
#   research/operations/2026-05-19-wr2-intel-lake-health-snapshot.md

set -uo pipefail

# The rotator's error-log knob is the SSOT: alarm where the cure acts, so an
# operator who tunes one moves both. LOG_SIZE_WATCHDOG_THRESHOLD_MB overrides
# for the rare case where they must genuinely differ — and the tripwire test
# reads the DEFAULTS, so an override cannot silently reopen the dead zone.
THRESHOLD_MB="${LOG_SIZE_WATCHDOG_THRESHOLD_MB:-${PRO_LOG_ROTATE_ERR_THRESHOLD_MB:-10}}"
THRESHOLD_BYTES=$(( THRESHOLD_MB * 1048576 ))
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
    msg="📊 Log size alert: ~/${rel_path} = ${size_mb} MB (>${THRESHOLD_MB}MB threshold). $(tail -1 "$f" 2>/dev/null | head -c 200)"
    gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/nuzantara/scripts/tg_notify.py"
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
