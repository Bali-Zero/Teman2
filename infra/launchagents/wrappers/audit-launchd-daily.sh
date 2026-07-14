#!/bin/zsh
# W24 daily launchd audit wrapper — emits JSON snapshot + Telegram delta alert
# Invoked by com.balizero.audit-launchd.daily.plist (02:00 WITA).
#
# State files:
#   ~/.agent/decisions/audit-launchd-last-summary.json — last snapshot summary
#   ~/logs/audit-launchd-daily-snapshots/YYYY-MM-DD.json — daily archive
#
# Telegram alert on delta:
#   - unhealthy_delta > 0 (new unhealthy plists since yesterday)
#   - any plist with recent_24h_real_errors increased

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${REPO_ROOT:-$HOME/Desktop/nuzantara}"
AUDIT_SCRIPT="$HOME/scripts/audit_launchd_crons.py"
STATE_DIR="$HOME/.agent/decisions"
STATE_FILE="$STATE_DIR/audit-launchd-last-summary.json"
ARCHIVE_DIR="$HOME/logs/audit-launchd-daily-snapshots"
TODAY=$(date +%Y-%m-%d)
ARCHIVE_FILE="$ARCHIVE_DIR/${TODAY}.json"

mkdir -p "$STATE_DIR" "$ARCHIVE_DIR"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi

# W84 trampoline (2026-07-14): AUDIT_SCRIPT lives at $HOME/scripts (outside
# ~/Desktop, TCC-safe) and audit_launchd_crons.py itself only reads
# ~/Library/LaunchAgents + the log paths its own plists declare (none under
# ~/Desktop as of this audit — verified against the live plist set) — so
# this wrapper does NOT currently have a hard ~/Desktop dependency. REPO_ROOT
# above is defined but unused today; kept deploy-aware ($HOME-relative, not
# hardcoded /Users/nuzantara) in case a future revision starts reading repo
# files under it. The probe is inserted anyway (cheap insurance, and W84 is
# a moving target — see infra/launchagents/wrappers/lib/trampoline.sh) right
# after secrets sourcing, before the audit run.
LOG="$HOME/logs/audit-launchd-daily.log"
TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG" "$0"
fi

# Run audit, write JSON directly to archive (avoid bash variable munging
# of backslash escapes inside JSON strings like '\\\'' from embedded scripts).
set +e
python3 "$AUDIT_SCRIPT" > "$ARCHIVE_FILE" 2>/dev/null
AUDIT_EXIT=$?
set -e

# All Python processing reads files directly (not from stdin via heredoc)
# to avoid bash escape conflicts with JSON content.
DELTA_FILE=$(mktemp)
SUMMARY_LINE_FILE=$(mktemp)
RECENT_LIST_FILE=$(mktemp)
NEW_STATE_FILE=$(mktemp)

python3 - "$ARCHIVE_FILE" "$STATE_FILE" "$DELTA_FILE" "$SUMMARY_LINE_FILE" "$RECENT_LIST_FILE" "$NEW_STATE_FILE" <<'PY'
import json, sys, os
archive, state, delta_out, summary_out, recent_out, new_state = sys.argv[1:7]
data = json.load(open(archive))
s = data["summary"]

# 1. Summary line
with open(summary_out, "w") as f:
    f.write(
        f"unhealthy={s['unhealthy']}/{s['total_plists']} | "
        f"hot1h={s.get('with_real_errors_hot_1h', 0)} | "
        f"recent24h={s['with_real_errors_recent_24h']} | "
        f"degrading_recovered={s.get('with_degrading_recovered', 0)} | "
        f"historical_only={s['with_historical_only']} | "
        f"lc_antipattern={s['with_lc_antipattern']}"
    )

# 2. Delta vs previous baseline (if any)
delta_msg = ""
if os.path.exists(state):
    try:
        prev = json.load(open(state))
        deltas = []
        for k in ("unhealthy", "with_real_errors_hot_1h",
                  "with_real_errors_recent_24h", "with_real_errors_total"):
            p, c = prev.get(k, 0), s.get(k, 0)
            if c > p:
                deltas.append(f"{k}: {p} -> {c} (+{c-p})")
            elif c < p:
                deltas.append(f"{k}: {p} -> {c} ({c-p})")
        delta_msg = " | ".join(deltas)
    except Exception as e:
        delta_msg = f"(prev state unreadable: {e})"
with open(delta_out, "w") as f:
    f.write(delta_msg)

# 3. HOT (currently broken last 1h) actionable list — only this triggers alarm.
hot = [r for r in data["rows"] if r.get("stderr_real_hot_1h", 0) > 0]
with open(recent_out, "w") as f:
    if not hot:
        f.write("(none)")
    else:
        for r in sorted(hot, key=lambda x: -x["stderr_real_hot_1h"]):
            f.write(f"- {r['plist']}: hot1h={r['stderr_real_hot_1h']} "
                    f"recent24h={r.get('stderr_real_recent_24h', 0)} "
                    f"total={r['stderr_real_errors']}\n")

# 4. New state snapshot (summary only, for delta tracking next run)
with open(new_state, "w") as f:
    json.dump(s, f)
PY

DELTA_MSG=$(cat "$DELTA_FILE")
SUMMARY_LINE=$(cat "$SUMMARY_LINE_FILE")
RECENT_LIST=$(cat "$RECENT_LIST_FILE")
mv "$NEW_STATE_FILE" "$STATE_FILE"
rm -f "$DELTA_FILE" "$SUMMARY_LINE_FILE" "$RECENT_LIST_FILE"

# Send digest if there's a delta OR recent errors present.
# tg-gateway migration (2026-07-14): the SEND leg goes through
# scripts/tg_notify.py (--tier digest) instead of a direct Telegram HTTP
# call — this is an informative delta report, not an actionable-now
# alert, so it is spooled and flushed in the grouped digest rather than
# sent immediately. The gateway owns token resolution, so no
# TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID gate is needed here anymore.
# Delta-detection logic above is unchanged — only the SEND mechanism
# changed.
# `recent_lines` count: empty marker "(none)" => no recent errors
HAS_RECENT=$(echo "$RECENT_LIST" | grep -q "^- " && echo yes || echo no)
if [ -n "$DELTA_MSG" ] || [ "$HAS_RECENT" = "yes" ]; then
    MSG="Launchd audit daily report

$SUMMARY_LINE

Delta vs yesterday: ${DELTA_MSG:-no change}

Plists currently broken (hot, last 1h):
$RECENT_LIST

Snapshot: $ARCHIVE_FILE"

    GATEWAY="$(dirname "$0")/tg_notify.py"
    [ -f "$GATEWAY" ] || GATEWAY="$HOME/Desktop/nuzantara/scripts/tg_notify.py"
    python3 "$GATEWAY" --tier digest --source audit-launchd-daily \
        --dedup-key "audit-launchd-daily:$(hostname -s):$TODAY" -- "$MSG" > /dev/null 2>&1 || true
fi

# Re-emit summary to stdout for launchd logging
echo "[audit-launchd-daily] $TODAY $SUMMARY_LINE"
echo "[audit-launchd-daily] delta=${DELTA_MSG:-no_change}"
echo "[audit-launchd-daily] snapshot=$ARCHIVE_FILE"

exit $AUDIT_EXIT
