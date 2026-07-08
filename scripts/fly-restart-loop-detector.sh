#!/usr/bin/env bash
# G3: Fly.io restart loop detector
# Alerts if any machine is NOT in 'started' state, or has unhealthy checks,
# or if restart count (parsed from events) exceeds threshold in last hour.
# Runs every 15min via launchd (com.nuzantara.fly-restart-loop-detector).
#
# SOURCE OF TRUTH: this repo file. The live copy at ~/scripts/ must stay
# byte-identical (cmp) — promoted from HOME 2026-07-02 (cicatrix #1
# HOME-fork antidote; the plist still executes ~/scripts/, sync on change).
#
# Sidecar semantics (2026-07-02, heartbeat-organs TAC): the organism
# heartbeat carries the MONITOR's own health, never its findings. Fly
# findings keep going to Telegram + state file; alerts_fired stays in the
# sidecar metadata. Before this change, 1 benign stopped machine (autostop,
# 0 unhealthy checks, steady since 2026-06-27) made the organ report
# status=degraded every 15min → false-sick at every session boot.

set -uo pipefail

# Innervation W1.1: emit organism sidecar — keep legacy state file too.
ORGAN_ID_W1="pro.fly_restart_loop_detector"
if [[ -r "$HOME/scripts/_organism_lib.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/scripts/_organism_lib.sh"
fi

APPS=(nuzantara-rag nuzantara-postgres)
SUSPENDED_OK=(nuzantara-qdrant)  # expected-suspended apps: log but don't alert
STATE_FILE="$HOME/.agent/decisions/fly_restart_monitor.json"
LOG_FILE="$HOME/logs/fly-restart-detector.log"
COOLDOWN_FILE="$HOME/.agent/decisions/fly_restart_monitor.cooldown"
COOLDOWN_SECONDS=$((60 * 30))  # 30min between alerts per app
RESTART_THRESHOLD=10  # alert if >10 restarts in last hour

if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-}}"

FLY_BIN=$(command -v fly || echo /opt/homebrew/bin/fly)
# fly v0.4.49 regression: does not read access_token from ~/.fly/config.yml
# Pass -t explicitly (same fix as fly-pg-proxy-wrapper.sh)
FLY_TOKEN=$(grep "^access_token:" "$HOME/.fly/config.yml" 2>/dev/null | awk '{print $2}' | tr -d '"')
fly_cmd() { "$FLY_BIN" ${FLY_TOKEN:+-t "$FLY_TOKEN"} "$@"; }

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*" | tee -a "$LOG_FILE"; }

# cohort-3: routes through the notification gateway. Fly machine flapping
# (W60) = prod issue → tier p0; this script keeps its own cooldown. Plain text.
tg_alert() {
    local text="$1"
    local gateway
    gateway="$(dirname "$0")/tg_notify.py"
    [ -f "$gateway" ] || gateway="$HOME/Desktop/nuzantara/scripts/tg_notify.py"
    python3 "$gateway" --tier p0 --source fly-restart-loop \
        --dedup-key "fly-restart-loop" -- "$text" \
        >/dev/null 2>&1 || log "telegram: gateway send failed"
}

cooldown_active() {
    local key="$1"
    [[ ! -f "$COOLDOWN_FILE" ]] && return 1
    local last
    last=$(grep "^$key:" "$COOLDOWN_FILE" 2>/dev/null | tail -1 | cut -d: -f2)
    [[ -z "$last" ]] && return 1
    local now=$(date +%s)
    (( now - last < COOLDOWN_SECONDS ))
}

cooldown_set() {
    local key="$1"
    touch "$COOLDOWN_FILE"
    grep -v "^$key:" "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" 2>/dev/null || true
    echo "$key:$(date +%s)" >> "$COOLDOWN_FILE.tmp"
    mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE"
}

now_ts=$(date +%s)
alerts=()
cli_failures=0
app_results="{}"

log "=== fly-restart-detector start ==="

for app in "${APPS[@]}"; do
    log "checking $app..."
    raw=$(fly_cmd status --json -a "$app" 2>&1) || {
        log "$app: fly status failed — $raw"
        cli_failures=$((cli_failures + 1))
        if ! cooldown_active "${app}_unreachable"; then
            alerts+=("🛫 ${app}: fly status CLI failed")
            cooldown_set "${app}_unreachable"
        fi
        continue
    }

    summary=$(echo "$raw" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception as e:
    print('PARSE_ERROR:' + str(e))
    sys.exit(0)
machines = d.get('Machines', [])
total = len(machines)
started = sum(1 for m in machines if m.get('state') == 'started')
not_started = [m.get('state', 'unknown') for m in machines if m.get('state') != 'started']
unhealthy_checks = 0
for m in machines:
    for c in m.get('checks', []) or []:
        if c.get('status') not in ('passing', None):
            unhealthy_checks += 1
print(f'total={total}|started={started}|bad_states={\",\".join(not_started) or \"none\"}|unhealthy_checks={unhealthy_checks}')
")

    if [[ "$summary" == PARSE_ERROR:* ]]; then
        log "$app: ${summary}"
        continue
    fi

    total=$(echo "$summary" | tr '|' '\n' | grep ^total= | cut -d= -f2)
    started=$(echo "$summary" | tr '|' '\n' | grep ^started= | cut -d= -f2)
    bad_states=$(echo "$summary" | tr '|' '\n' | grep ^bad_states= | cut -d= -f2)
    unhealthy=$(echo "$summary" | tr '|' '\n' | grep ^unhealthy_checks= | cut -d= -f2)

    log "$app: total=$total started=$started bad=$bad_states unhealthy_checks=$unhealthy"

    trigger_alert=0
    alert_reasons=()
    if (( started < total )); then
        trigger_alert=1
        alert_reasons+=("$((total - started))/$total machines NOT started ($bad_states)")
    fi
    if (( unhealthy > 0 )); then
        trigger_alert=1
        alert_reasons+=("$unhealthy unhealthy health checks")
    fi

    if (( trigger_alert )); then
        if ! cooldown_active "${app}_bad"; then
            joined_reasons=$(printf '%s\n  • ' "${alert_reasons[@]}")
            alerts+=("🛫 ${app}:"$'\n'"  • ${joined_reasons%???}")
            cooldown_set "${app}_bad"
        fi
    fi

    app_results=$(echo "$app_results" | python3 -c "
import json, sys
d = json.load(sys.stdin)
d['$app'] = {
    'total': $total,
    'started': $started,
    'bad_states': '$bad_states',
    'unhealthy_checks': $unhealthy,
}
print(json.dumps(d))
")
done

cat > "$STATE_FILE" <<EOF
{
  "checked_at": $now_ts,
  "apps": $app_results,
  "alerts_fired": ${#alerts[@]}
}
EOF

if (( ${#alerts[@]} > 0 )); then
    msg="🚨 Fly.io Health (${#alerts[@]} apps)"$'\n\n'
    for line in "${alerts[@]}"; do
        msg+="$line"$'\n\n'
    done
    tg_alert "$msg" && log "alerts fired (${#alerts[@]})"
fi

cat > "$HOME/.agent/decisions/fly_restart_monitor.state.json" <<EOF
{"status": "ok", "ts": $now_ts, "last_error": ""}
EOF

# Innervation W1.1 (revised 2026-07-02): status reflects the MONITOR's own
# health — degraded only when the fly CLI itself failed. Findings about the
# monitored apps travel via Telegram + state file; alerts_fired is metadata.
if declare -F emit_organ_last_seen >/dev/null 2>&1; then
    if (( cli_failures > 0 )); then
        emit_organ_last_seen "$ORGAN_ID_W1" "degraded" \
            "{\"cli_failures\":${cli_failures},\"alerts_fired\":${#alerts[@]}}" || true
    else
        emit_organ_last_seen "$ORGAN_ID_W1" "ok" \
            "{\"apps_checked\":${#APPS[@]},\"alerts_fired\":${#alerts[@]}}" || true
    fi
fi

log "=== fly-restart-detector done ==="
