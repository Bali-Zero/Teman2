#!/bin/zsh
# Mata Garuda Pro<->Mini Redis Split-Brain Monitor
# Invoked by com.matagaruda.redis-split-brain.check.plist.
#
# W17 cicatrix 2026-05-22: W16 detector script shipped (commit 542bb2f19)
# but no LaunchAgent wrapped it. Without a cron, the 9.6h enriched drift
# and 210h alerts drift were discovered only by manual ad-hoc investigation.
# W17 wires the detector to launchd with Telegram alert on stderr
# non-empty (any split-brain instance = P1 operator action).
#
# Exit semantics:
#   0   = all hosts in sync OR one host unreachable (no alert needed)
#   1   = drift > 1h detected on one or more streams (JSON-per-line alerts
#         → stderr → launchd error log → Telegram alert)
#
# We do NOT translate exit 1 → 0 here. launchctl `last exit code` should
# reflect "split-brain active" for operator visibility.
#
# Telegram alert behavior:
#   - First detection of new split-brain combo (stream+stale_host): send
#     full alert with JSON snippet.
#   - Repeat of same combo within 4h: suppress (idle quiet hours).
#   - State file: $HOME/.agent/decisions/matagaruda-split-brain-last.txt
#     stores epoch + stream+host combos seen, gc'd after 4h.

set -eu
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

# W84 trampoline (2026-07-14): this script previously logged via launchd
# Standard*Path only (no LOG var) — use a dedicated trampoline breadcrumb
# log so the fail-fast/re-exec event is captured even if the run never
# reaches a point where it would otherwise write anything. Placed BEFORE
# the first ~/Desktop access (REPO= below).
LOG="$HOME/logs/matagaruda-split-brain-trampoline.log"
TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG" "$0"
fi

REPO="$HOME/nuzantara/apps/mata-garuda"
VENV_PY="$REPO/.venv/bin/python"
STATE_DIR="$HOME/.agent/decisions"
STATE_FILE="$STATE_DIR/matagaruda-split-brain-last.txt"
SUPPRESS_WINDOW_S=14400  # 4h

mkdir -p "$STATE_DIR"

if [ ! -x "$VENV_PY" ]; then
    echo "[split-brain] venv python not found at $VENV_PY" >&2
    exit 1
fi

cd "$REPO"

# Run detector, capture stderr (alerts) + exit code.
# $? after `|| true` always returns 0, so we capture exit immediately
# via a temporary file approach (don't use || true here).
set +e
ALERTS=$(PYTHONPATH="$REPO" "$VENV_PY" scripts/check_redis_split_brain.py 2>&1 >/dev/null)
EXIT_CODE=$?
set -e

# Re-emit alerts to launchd stderr so launchctl print shows last exit code
if [ -n "$ALERTS" ]; then
    echo "$ALERTS" >&2
fi

# Telegram alert with dedup (suppress repeat of same stream+stale_host combo)
# tg-gateway migration (2026-07-14): the SEND leg goes through
# scripts/tg_notify.py (--tier p0) instead of a direct Telegram HTTP call —
# the gateway owns token resolution (env / secrets file / ssh relay) so no
# TELEGRAM_BOT_TOKEN/TELEGRAM_OWNER_CHAT_ID gate is needed here anymore.
# Suppress-window/state-file dedup logic below is unchanged — only the
# SEND mechanism changed.
NOW=$(date +%s)
if [ -n "$ALERTS" ]; then
    # GC old state entries
    if [ -f "$STATE_FILE" ]; then
        awk -v now="$NOW" -v window="$SUPPRESS_WINDOW_S" \
            '($1 + window) >= now' "$STATE_FILE" > "${STATE_FILE}.tmp" || true
        mv "${STATE_FILE}.tmp" "$STATE_FILE" 2>/dev/null || true
    else
        touch "$STATE_FILE"
    fi

    # Extract NEW combos (stream + stale_host) not already in state
    NEW_ALERTS=""
    while IFS= read -r line; do
        COMBO=$(echo "$line" | python3 -c "
import json, sys
try:
    d = json.loads(sys.stdin.read())
    print(f\"{d.get('stream','?')}|{d.get('stale_host','?')}\")
except Exception:
    pass
" 2>/dev/null)
        if [ -n "$COMBO" ] && ! grep -q " ${COMBO}$" "$STATE_FILE" 2>/dev/null; then
            echo "${NOW} ${COMBO}" >> "$STATE_FILE"
            NEW_ALERTS="${NEW_ALERTS}${line}\n"
        fi
    done <<< "$ALERTS"

    if [ -n "$NEW_ALERTS" ]; then
        GATEWAY="$(dirname "$0")/tg_notify.py"
        [ -f "$GATEWAY" ] || GATEWAY="$HOME/nuzantara/scripts/tg_notify.py"
        MSG="Mata Garuda Redis Split-Brain

${NEW_ALERTS}
Run manually: python3 ~/nuzantara/apps/mata-garuda/scripts/check_redis_split_brain.py"
        python3 "$GATEWAY" --tier p0 --source matagaruda-redis-split-brain \
            --dedup-key "matagaruda-split-brain:$(hostname -s)" -- "$MSG" >/dev/null 2>&1 || true
    fi
fi

# Stage 1 (2026-06-29): emit organism heartbeat so the receptor sees the
# verdict (alert reaches the brain-session, not only Zero TG).
if [ "$EXIT_CODE" -ne 0 ] || [ -n "$ALERTS" ]; then OSTATUS="degraded"; else OSTATUS="ok"; fi
NSTREAMS=$(printf "%s" "$ALERTS" | grep -c "redis-split-brain" 2>/dev/null || echo 0)
python3 "$HOME/scripts/matagaruda-emit-split-brain-sidecar.py" "$OSTATUS" "$NSTREAMS" 2>/dev/null || true

exit $EXIT_CODE
