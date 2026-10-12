#!/bin/bash
# mini.fly_cost_guard — weekly Fly resource ceilings on Mini.
# Canon: infra/launchagents/wrappers/mini-fly-cost-guard.sh
# Live:  ~/scripts/mini-fly-cost-guard.sh (declared pair, node=mini)
#
# The Pro twins (com.balizero.fly-cost-alert.weekly and its crontab line) are
# deliberately untouched here. They retire only at cutover after this organ is armed.

set -u
umask 077

ORGAN_ID="mini.fly_cost_guard"
LOG_DIR="$HOME/logs/mini-fly-cost-guard"
LOG="$LOG_DIR/run.log"
SIDECAR_DIR="$HOME/.organism/last_seen"
LOCKDIR="${MINI_FLY_COST_GUARD_LOCKDIR:-/tmp/nuzantara-mini-fly_cost_guard.lock}"
REPO="$HOME/nuzantara"
GUARD="$REPO/scripts/fly_cost_guard.py"
GATEWAY="$REPO/scripts/tg_notify.py"
PYTHON_BIN="${MINI_FLY_COST_GUARD_PYTHON_BIN:-/usr/bin/python3}"
# Test-only override lets the offline harness exercise the timeout quickly; production uses 900.
GUARD_TIMEOUT_SECONDS="${MINI_FLY_COST_GUARD_TEST_TIMEOUT_SECONDS:-900}"
mkdir -p "$LOG_DIR" "$SIDECAR_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
SENSITIVE_VALUES=()
redact() {
    local text="$1" secret pattern
    for secret in ${SENSITIVE_VALUES[@]+"${SENSITIVE_VALUES[@]}"}; do
        [ -n "$secret" ] || continue
        pattern=$(printf '%s' "$secret" | sed 's/[][?*\\]/\\&/g')
        text=${text//$pattern/[REDACTED]}
    done
    printf '%s' "$text"
}
log() { printf '[%s] %s\n' "$(ts)" "$(redact "$*")" >> "$LOG"; }
log_output() { printf '%s\n' "$1" | while IFS= read -r line; do log "$line"; done; }

heartbeat() {
    local tmp="$SIDECAR_DIR/.$ORGAN_ID.json.$$"
    printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$1" "$2" > "$tmp" \
        && mv -f "$tmp" "$SIDECAR_DIR/$ORGAN_ID.json" \
        || { rm -f "$tmp"; return 1; }
}

notify() {
    local tier="$1" key="$2" message="$3" routing=true gateway_output rc
    [ "$tier" = "p0" ] && routing=false
    gateway_output=$(TG_ACT_ROUTING_ENABLED=$routing TG_RELAY_SSH='' "$PYTHON_BIN" "$GATEWAY" \
        --tier "$tier" --source fly-cost-guard --dedup-key "$key" -- "$message" \
        2>&1)
    rc=$?
    [ -n "$gateway_output" ] && log_output "$gateway_output"
    return "$rc"
}

if [ "$(hostname -s | tr '[:upper:]' '[:lower:]')" != "mini-pro2" ]; then
    log "node guard: $(hostname -s) != mini-pro2 — not my node, exiting"
    heartbeat "disabled" "wrong-node $(hostname -s)"
    exit 0
fi

if [ "${MINI_FLY_COST_GUARD_ENABLED:-true}" = "false" ]; then
    log "kill switch MINI_FLY_COST_GUARD_ENABLED=false — exiting"
    heartbeat "disabled" "kill switch"
    exit 0
fi

proc_id() { echo "$1 $(ps -p "$1" -o lstart= 2>/dev/null | tr -s ' ')"; }
if ! mkdir "$LOCKDIR" 2>/dev/null; then
    owner=$(cat "$LOCKDIR/pid" 2>/dev/null || true)
    owner_pid=${owner%% *}
    # perl, not stat: BSD `stat -f %m` and GNU `stat -c %Y` disagree, and the corpus runs on Linux.
    mtime=$(/usr/bin/perl -e 'my @s = stat shift; print @s ? $s[9] : 0' "$LOCKDIR" 2>/dev/null)
    case "$mtime" in ''|*[!0-9]*) mtime=0 ;; esac
    age=$(( $(date +%s) - mtime ))
    if [ -z "$owner" ] && [ "$age" -lt 120 ]; then
        log "lock just created by another run — skipping"
        heartbeat "warning" "run already active"
        exit 0
    fi
    if [ -n "$owner_pid" ] && kill -0 "$owner_pid" 2>/dev/null \
        && [ "$(proc_id "$owner_pid")" = "$owner" ] \
        && ps -p "$owner_pid" -o command= 2>/dev/null | grep -q "mini-fly-cost-guard.sh"; then
        if [ "$age" -ge 1800 ]; then
            log "previous run (pid $owner_pid) still alive for ${age}s — skipping"
            heartbeat "warning" "run already active; age=${age}s"
        else
            log "previous run (pid $owner_pid) still alive — skipping"
            heartbeat "warning" "run already active"
        fi
        exit 0
    fi
    log "stale lock (owner ${owner_pid:-unknown} gone) — taking it over"
    mv "$LOCKDIR" "$LOCKDIR.stale.$$" 2>/dev/null && rm -rf "$LOCKDIR.stale.$$"
    if ! mkdir "$LOCKDIR" 2>/dev/null; then
        heartbeat "error" "lock acquisition failed"
        notify p0 "fly-cost:broken:lock" \
            "fly cost guard broken on Mini: lock acquisition failed." || true
        exit 2
    fi
fi
proc_id $$ > "$LOCKDIR/pid"

FINISHED=0
on_exit() {
    local rc=$?
    if [ "$FINISHED" -ne 1 ]; then
        heartbeat "error" "wrapper exited before a verdict rc=$rc" || true
        notify p0 "fly-cost:broken:wrapper" \
            "fly cost guard broken on Mini: wrapper exited before a verdict (rc=$rc)." || true
    fi
    if [ "$(cat "$LOCKDIR/pid" 2>/dev/null)" = "$(proc_id $$)" ]; then
        rm -rf "$LOCKDIR"
    fi
}
trap on_exit EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.local/share/mise/shims:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export PATH
if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi
[ -n "${FLY_API_TOKEN:-}" ] && SENSITIVE_VALUES+=("$FLY_API_TOKEN")
[ -n "${FLY_ACCESS_TOKEN:-}" ] && SENSITIVE_VALUES+=("$FLY_ACCESS_TOKEN")
[ -n "${TELEGRAM_BOT_TOKEN:-}" ] && SENSITIVE_VALUES+=("$TELEGRAM_BOT_TOKEN")

if [ -f "$LOG" ] && [ "$(wc -c < "$LOG" | tr -d ' ')" -gt 5242880 ]; then
    mv -f "$LOG" "$LOG.1"
fi
log "run start"

broken() {
    local kind="$1" note="$2" rc="$3"
    heartbeat "error" "$note" || log "heartbeat write failed (error verdict)"
    notify p0 "fly-cost:broken:$kind" \
        "fly cost guard broken on Mini: $note. Investigate the local private log." || \
        log "p0 notification failed or was spooled"
    FINISHED=1
    log "run done rc=$rc"
    exit "$rc"
}

[ -f "$GUARD" ] || broken payload "guard payload missing" 2
[ -f "$GATEWAY" ] || broken gateway "notification gateway missing" 2
FLY_BIN="${MINI_FLY_COST_GUARD_FLY_BIN:-$(command -v flyctl || true)}"
[ -n "$FLY_BIN" ] || broken flyctl "flyctl missing" 2
FLY_CREDENTIAL_LIB="$REPO/scripts/lib/fly_credential.sh"
[ -f "$FLY_CREDENTIAL_LIB" ] || broken credential-lib "credential resolver missing" 2
# shellcheck source=scripts/lib/fly_credential.sh
. "$FLY_CREDENTIAL_LIB"
resolve_fly_credential "$FLY_BIN" status -a nuzantara-rag || \
    broken credential "credential resolution failed" 2

export EXPECTED_APPS="nuzantara-rag,nuzantara-postgres"
export MAX_TOTAL_MACHINES="7"
export MAX_STARTED_MACHINES="6"
export MAX_STARTED_MEMORY_MB="12288"
export MAX_STARTED_CPUS="11"
export MAX_TOTAL_VOLUME_GB="77"
export MAX_DEDICATED_IPV4="0"

OUTPUT=$(/usr/bin/perl -e 'alarm shift; exec @ARGV' \
    "$GUARD_TIMEOUT_SECONDS" "$PYTHON_BIN" "$GUARD" 2>&1)
RC=$?
unset FLY_API_TOKEN FLY_ACCESS_TOKEN
log_output "$OUTPUT"
REPORT_LINES=$(printf '%s\n' "$OUTPUT" | sed '/^::error::Fly resource guard:/d; /^Fly resource guard: within limits$/d; /^[[:space:]]*$/d')

if [ "$RC" -eq 142 ]; then
    broken guard-timeout "guard timed out after ${GUARD_TIMEOUT_SECONDS} s" 2
elif [ "$RC" -eq 0 ]; then
    heartbeat "ok" "within configured ceilings" || broken heartbeat "heartbeat write failed" 2
    notify digest "fly-cost:success:$(date +%G-W%V)" \
        "Fly cost guard passed on Mini."$'\n'"$REPORT_LINES" || log "digest notification failed or was spooled"
elif [ "$RC" -eq 1 ]; then
    FINDINGS=$(printf '%s\n' "$OUTPUT" | sed -n 's/^::error::Fly resource guard: //p' \
        | tr ';' '\n' | sed 's/^[[:space:]]*//; /^[[:space:]]*$/d' | LC_ALL=C sort)
    [ -n "$FINDINGS" ] || FINDINGS="guard reported findings without details"
    FINDING_COUNT=$(printf '%s\n' "$FINDINGS" | awk 'NF { n++ } END { print n+0 }')
    DEDUP=$(printf '%s\n' "$FINDINGS" | shasum -a 1 | awk '{print substr($1,1,12)}')
    heartbeat "ok" "monitor healthy; findings=$FINDING_COUNT" || broken heartbeat "heartbeat write failed" 2
    notify p0 "fly-cost:$DEDUP" "Fly cost guard findings on Mini:"$'\n'"$FINDINGS" || \
        log "p0 notification failed or was spooled"
else
    broken guard "guard returned unexpected rc=$RC" "$RC"
fi

FINISHED=1
log "run done rc=$RC"
exit "$RC"
