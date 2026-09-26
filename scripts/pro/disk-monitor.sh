#!/usr/bin/env bash
# G2: disk usage + log size monitor
# Runs every 30min via launchd com.nuzantara.disk-monitor
# --dry-run: print readings and alerts; send, write and cooldown nothing.

set -uo pipefail

DRY_RUN=0
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

# Innervation W1.1: emit organism sidecar — keep legacy state file too.
ORGAN_ID_W1="pro.disk_monitor"
if [[ -r "$HOME/scripts/_organism_lib.sh" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/scripts/_organism_lib.sh"
fi

ROOT_THRESHOLD_PCT=85
LOGS_DIR_THRESHOLD_MB=500
SINGLE_LOG_THRESHOLD_MB=50
SWAP_THRESHOLD_PCT=50
VM_THRESHOLD_MB=8192
VM_VOLUME="${DISK_MONITOR_VM_VOLUME:-/System/Volumes/VM}"
STATE_FILE="$HOME/.agent/decisions/disk_monitor.json"
LOG_FILE="$HOME/logs/disk-monitor.log"
COOLDOWN_FILE="$HOME/.agent/decisions/disk_monitor.cooldown"
COOLDOWN_SECONDS=$((60 * 60 * 6))  # 6h between alerts of the same kind

if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
TG_NOTIFY="${TG_NOTIFY:-$HOME/nuzantara/scripts/tg_notify.py}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

log() {
    local line="[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*"
    if (( DRY_RUN )); then echo "$line"; else echo "$line" | tee -a "$LOG_FILE"; fi
}

tg_alert() {
    local text="$1"
    [[ -f "$TG_NOTIFY" ]] || { log "telegram: $TG_NOTIFY missing"; return 1; }
    python3 "$TG_NOTIFY" --tier p0 --source disk-monitor "$text" >/dev/null 2>&1 \
        || { log "telegram: tg_notify failed"; return 1; }
}

cooldown_active() {
    local key="$1"
    (( DRY_RUN )) && return 1
    [[ ! -f "$COOLDOWN_FILE" ]] && return 1
    local last
    last=$(grep "^$key:" "$COOLDOWN_FILE" 2>/dev/null | tail -1 | cut -d: -f2)
    [[ -z "$last" ]] && return 1
    local now=$(date +%s)
    (( now - last < COOLDOWN_SECONDS ))
}

cooldown_set() {
    local key="$1"
    (( DRY_RUN )) && return 0
    touch "$COOLDOWN_FILE"
    grep -v "^$key:" "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" 2>/dev/null || true
    echo "$key:$(date +%s)" >> "$COOLDOWN_FILE.tmp"
    mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE"
}

now_ts=$(date +%s)
alerts=()

log "=== disk-monitor start ==="

# --- 1. Data volume usage ---
# On APFS macOS `/` is the sealed read-only system snapshot and never fills; user
# data, Postgres, Redis and ~/logs live on /System/Volumes/Data. Measuring `/`
# read 33% on 2026-09-26 while Data hit 100% twice (Redis MISCONF, postgresql@17
# crash-recovery, ~20 launchd jobs ENOSPC) and this monitor never alerted.
DATA_VOLUME="${DISK_MONITOR_VOLUME:-/System/Volumes/Data}"
[[ -d "$DATA_VOLUME" ]] || DATA_VOLUME="/"
root_pct=$(df -P "$DATA_VOLUME" | awk 'NR==2 {print $5}' | tr -d '%')
log "data volume ${DATA_VOLUME}: ${root_pct}% used"
if (( root_pct > ROOT_THRESHOLD_PCT )); then
    if ! cooldown_active "root_full"; then
        alerts+=("💾 <b>Data volume</b> ${DATA_VOLUME}: ${root_pct}% used (threshold ${ROOT_THRESHOLD_PCT}%)")
        cooldown_set "root_full"
    fi
fi

# --- 2. ~/logs directory total size ---
logs_size_mb=0
if [[ -d "$HOME/logs" ]]; then
    logs_size_mb=$(du -sm "$HOME/logs" 2>/dev/null | awk '{print $1}')
fi
log "~/logs total: ${logs_size_mb} MB"
if (( logs_size_mb > LOGS_DIR_THRESHOLD_MB )); then
    if ! cooldown_active "logs_dir_big"; then
        alerts+=("📂 <b>~/logs</b>: ${logs_size_mb} MB (threshold ${LOGS_DIR_THRESHOLD_MB} MB)")
        cooldown_set "logs_dir_big"
    fi
fi

# --- 3. any single log > 50MB ---
big_logs=()
if [[ -d "$HOME/logs" ]]; then
    while IFS= read -r -d '' logfile; do
        size_mb=$(du -m "$logfile" 2>/dev/null | awk '{print $1}')
        if (( size_mb > SINGLE_LOG_THRESHOLD_MB )); then
            big_logs+=("$(basename "$logfile")|$size_mb")
        fi
    done < <(find "$HOME/logs" -type f \( -name "*.log" -o -name "*.jsonl" -o -name "*.err" \) -print0 2>/dev/null)
fi
if (( ${#big_logs[@]} > 0 )); then
    log "big logs: ${#big_logs[@]}"
    if ! cooldown_active "single_log_big"; then
        msg="📄 <b>Large log files</b> (>${SINGLE_LOG_THRESHOLD_MB} MB):"$'\n'
        for entry in "${big_logs[@]}"; do
            name="${entry%|*}"
            size="${entry#*|}"
            msg+="  • $name: ${size} MB"$'\n'
        done
        alerts+=("$msg")
        cooldown_set "single_log_big"
    fi
fi

# --- 4. swap + VM volume ---
# The 2026-09-25/26 ENOSPC bursts on Pro were macOS swap: swapfiles in
# /System/Volumes/VM share the APFS container with Data, grew to >=18 GiB under
# RAM over-commit, and jetsam LOWSWAP killed 164/209 processes. `df` on Data
# never shows it, so read the swap and the VM volume directly.
swap_line="${DISK_MONITOR_SWAPUSAGE:-$(LC_ALL=C /usr/sbin/sysctl -n vm.swapusage 2>/dev/null)}"
read -r swap_total_mb swap_used_mb < <(printf '%s\n' "$swap_line" | LC_ALL=C awk '
    function mb(v,  u, n) { gsub(",", ".", v); u = substr(v, length(v)); n = substr(v, 1, length(v) - 1) + 0
        if (u == "G") n *= 1024; else if (u == "K") n /= 1024; return int(n + 0.5) }
    { for (i = 1; i < NF; i++) { if ($i == "total") t = mb($(i + 2)); if ($i == "used") u = mb($(i + 2)) } }
    END { print t + 0, u + 0 }')
swap_pct=0
(( swap_total_mb > 0 )) && swap_pct=$(( swap_used_mb * 100 / swap_total_mb ))
vm_used_mb="${DISK_MONITOR_VM_USED_MB:-}"
if [[ -z "$vm_used_mb" ]]; then
    vm_used_mb=0
    [[ -d "$VM_VOLUME" ]] && vm_used_mb=$(df -k "$VM_VOLUME" | awk 'NR==2 {print int($3 / 1024)}')
fi
log "swap: used ${swap_used_mb}/${swap_total_mb} MB (${swap_pct}%) · VM volume ${VM_VOLUME}: ${vm_used_mb} MB"
if (( swap_pct > SWAP_THRESHOLD_PCT )) && ! cooldown_active "swap_high"; then
    alerts+=("🧠 <b>Swap</b>: ${swap_used_mb}/${swap_total_mb} MB used (${swap_pct}%, threshold ${SWAP_THRESHOLD_PCT}%) — RAM over-commit, jetsam LOWSWAP risk")
    cooldown_set "swap_high"
fi
if (( vm_used_mb > VM_THRESHOLD_MB )) && ! cooldown_active "vm_volume_big"; then
    alerts+=("🌀 <b>VM volume</b> ${VM_VOLUME}: ${vm_used_mb} MB (threshold ${VM_THRESHOLD_MB} MB) — swapfiles eat the Data container's free space")
    cooldown_set "vm_volume_big"
fi

if (( DRY_RUN )); then
    echo "dry-run: ${#alerts[@]} alert(s); nothing sent, written or cooled down"
    (( ${#alerts[@]} > 0 )) && printf '%s\n' "${alerts[@]}"
    exit 0
fi

# --- state file (human-readable JSON, sentinel-trackable) ---
big_logs_json="[]"
if (( ${#big_logs[@]} > 0 )); then
    big_logs_json=$(printf '%s\n' "${big_logs[@]}" | python3 -c "
import sys, json
items = []
for line in sys.stdin:
    line = line.strip()
    if not line: continue
    name, size = line.rsplit('|', 1)
    items.append({'name': name, 'mb': int(size)})
print(json.dumps(items))
")
fi

cat > "$STATE_FILE" <<EOF
{
  "checked_at": $now_ts,
  "root_pct": $root_pct,
  "logs_dir_mb": $logs_size_mb,
  "big_logs": $big_logs_json,
  "swap_used_mb": $swap_used_mb,
  "swap_total_mb": $swap_total_mb,
  "swap_pct": $swap_pct,
  "vm_volume_mb": $vm_used_mb,
  "alerts_fired": ${#alerts[@]}
}
EOF

# --- fire alerts ---
if (( ${#alerts[@]} > 0 )); then
    msg="⚠️ <b>Disk Monitor (mac-pro)</b>"$'\n\n'
    for line in "${alerts[@]}"; do
        msg+="$line"$'\n'
    done
    tg_alert "$msg" && log "alerts fired (${#alerts[@]})"
fi

# sentinel state
cat > "$HOME/.agent/decisions/disk_monitor.state.json" <<EOF
{"status": "ok", "ts": $now_ts, "last_error": ""}
EOF

# Innervation W1.1: emit sidecar (status reflects whether alerts fired).
if declare -F emit_organ_last_seen >/dev/null 2>&1; then
    if (( ${#alerts[@]} > 0 )); then
        emit_organ_last_seen "$ORGAN_ID_W1" "degraded" \
            "{\"root_pct\":${root_pct},\"logs_dir_mb\":${logs_size_mb},\"swap_pct\":${swap_pct},\"vm_volume_mb\":${vm_used_mb},\"alerts\":${#alerts[@]}}" || true
    else
        emit_organ_last_seen "$ORGAN_ID_W1" "ok" \
            "{\"root_pct\":${root_pct},\"logs_dir_mb\":${logs_size_mb},\"swap_pct\":${swap_pct},\"vm_volume_mb\":${vm_used_mb}}" || true
    fi
fi

log "=== disk-monitor done ==="
