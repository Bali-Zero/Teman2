#!/bin/zsh
# Bali Zero Magazine publisher wrapper.
# Pro-only runtime: LaunchAgents run this on Nuzantara/Pro after upstream collectors.
# The wrapper owns scheduling safety only: locks, timeouts, secret hydration,
# manifest preflight, and payload-free logs. Editorial composition/publishing stays
# in zantara_media.cli.magazine_publish.

set -uo pipefail

unset ANTHROPIC_API_KEY

export HOME="${HOME:-/Users/nuzantara}"
export PATH="/opt/homebrew/bin:/Users/nuzantara/.local/bin:/usr/local/bin:/usr/bin:/bin"

MODE="${1:-morning}"
case "$MODE" in
    morning|breaking) ;;
    *)
        echo "[$(date)] fatal: expected mode morning|breaking, got '$MODE'" >&2
        exit 64
        ;;
esac

HOSTNAME_VALUE="$(hostname 2>/dev/null || true)"
if [ "$HOSTNAME_VALUE" != "Nuzantara" ] && [ "${MAGAZINE_ALLOW_NON_PRO:-false}" != "true" ]; then
    echo "[$(date)] fatal: magazine publisher is Pro-only; host=$HOSTNAME_VALUE" >&2
    exit 78
fi

ROOT="${MAGAZINE_ROOT:-/Users/nuzantara/nuzantara}"
MEDIA_DIR="$ROOT/apps/zantara-media"
PYTHON_BIN="${MAGAZINE_PYTHON:-$MEDIA_DIR/.venv/bin/python}"
PROCESS_LAUNCHER_PYTHON="${MAGAZINE_PROCESS_LAUNCHER_PYTHON:-$PYTHON_BIN}"
STATE_DIR="${MAGAZINE_STATE_DIR:-$HOME/.local/state/bali-zero-magazine}"
INPUT_DIR="${MAGAZINE_INPUT_DIR:-$STATE_DIR/inputs}"
OUTPUT_DIR="${MAGAZINE_OUTPUT_DIR:-$STATE_DIR/packets}"
LOG_DIR="${MAGAZINE_LOG_DIR:-$HOME/logs}"
DATE_WITA="$(TZ=Asia/Makassar date +%Y-%m-%d)"
LOG="$LOG_DIR/bali-zero-magazine-${MODE}.log"
LOCKFILE="$STATE_DIR/${MODE}.flock"
TIMEOUT_SECONDS="${MAGAZINE_TIMEOUT_SECONDS:-840}"
KILL_GRACE_SECONDS="${MAGAZINE_KILL_GRACE_SECONDS:-2}"
POST_KILL_WAIT_SECONDS="${MAGAZINE_POST_KILL_WAIT_SECONDS:-5}"
PUBLISH_ENABLED="${MAGAZINE_PUBLISH_ENABLED:-true}"
export MAGAZINE_AUTO_ASSETS="${MAGAZINE_AUTO_ASSETS:-false}"
export MAGAZINE_ASSET_STATE_DIR="${MAGAZINE_ASSET_STATE_DIR:-$STATE_DIR/assets}"
REQUIRED_SYSTEM_IDS=(${=MAGAZINE_REQUIRED_SYSTEM_IDS:-intel-lake mata-garuda regulatory-watcher notebooklm})
ACTIVE_PROCESS_GROUP=""

mkdir -p "$STATE_DIR" "$INPUT_DIR" "$OUTPUT_DIR" "$LOG_DIR"

HEARTBEAT_LIB="${ORGANISM_HEARTBEAT_LIB:-$ROOT/scripts/lib/heartbeat.sh}"
HEARTBEAT_ID="pro.bali_zero_magazine_${MODE}"

log() {
    echo "[$(date)] $1" >> "$LOG"
}

heartbeat() {
    local hb_status="$1"
    local note="${2:-}"
    if [ -x "$HEARTBEAT_LIB" ]; then
        bash "$HEARTBEAT_LIB" "$HEARTBEAT_ID" "$hb_status" "$note" || true
    fi
}

if [ "${MAGAZINE_AUTOMATION_ENABLED:-true}" = "false" ]; then
    log "disabled mode=$MODE kill_switch=MAGAZINE_AUTOMATION_ENABLED"
    heartbeat "disabled" "kill switch"
    exit 0
fi

load_secret_from_keychain() {
    local env_name="$1"
    local account="$2"
    if [ -n "${(P)env_name:-}" ]; then
        return 0
    fi
    if command -v security >/dev/null 2>&1; then
        local value
        value="$(security find-generic-password -s bali-zero-magazine -a "$account" -w 2>/dev/null || true)"
        if [ -n "$value" ]; then
            export "$env_name=$value"
        fi
    fi
}

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

load_secret_from_keychain MAGAZINE_SIWC_BEARER_TOKEN siwc-bearer-token
load_secret_from_keychain MAGAZINE_HMAC_SECRET hmac-secret
load_secret_from_keychain MAGAZINE_AUDIT_PRIVATE_KEY_B64 audit-private-key-b64

if [[ -e "$LOCKFILE" && ! -f "$LOCKFILE" ]]; then
    log "fatal mode=$MODE advisory_lock_path_not_regular"
    exit 70
fi
if ! touch "$LOCKFILE"; then
    log "fatal mode=$MODE advisory_lock_path_unavailable"
    exit 70
fi
if ! zmodload zsh/system; then
    log "fatal mode=$MODE advisory_lock_module_unavailable"
    exit 70
fi
zsystem flock -t 0.001 -i 0.001 -f MAGAZINE_LOCK_FD "$LOCKFILE"
lock_rc="$?"
case "$lock_rc" in
    0) ;;
    2)
        log "duplicate suppressed mode=$MODE advisory_lock_busy"
        exit 0
        ;;
    *)
        log "fatal mode=$MODE advisory_lock_failed rc=$lock_rc"
        exit 70
        ;;
esac

finish() {
    local rc=$?
    if [ -n "$ACTIVE_PROCESS_GROUP" ]; then
        terminate_process_group "$ACTIVE_PROCESS_GROUP"
        ACTIVE_PROCESS_GROUP=""
    fi
    zsystem flock -u "$MAGAZINE_LOCK_FD" || true
    if [ "$rc" -eq 0 ]; then
        heartbeat "ok" "mode=$MODE rc=0"
    else
        heartbeat "error" "mode=$MODE rc=$rc"
    fi
    log "finished mode=$MODE rc=$rc"
    trap - EXIT
    exit "$rc"
}

trap finish EXIT

process_group_is_alive() {
    local process_group_id="$1"
    kill -0 -- -"$process_group_id" 2>/dev/null
}

terminate_process_group() {
    local process_group_id="$1"
    local waited=0
    if ! kill -TERM -- -"$process_group_id" 2>/dev/null; then
        kill -TERM "$process_group_id" 2>/dev/null || true
    fi
    while process_group_is_alive "$process_group_id" && [ "$waited" -lt "$KILL_GRACE_SECONDS" ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if process_group_is_alive "$process_group_id"; then
        kill -KILL -- -"$process_group_id" 2>/dev/null || true
    fi
    waited=0
    while process_group_is_alive "$process_group_id" && [ "$waited" -lt "$POST_KILL_WAIT_SECONDS" ]; do
        sleep 1
        waited=$((waited + 1))
    done
    wait "$process_group_id" 2>/dev/null || true
    waited=0
    while process_group_is_alive "$process_group_id" && [ "$waited" -lt "$POST_KILL_WAIT_SECONDS" ]; do
        sleep 1
        waited=$((waited + 1))
    done
    if process_group_is_alive "$process_group_id"; then
        log "fatal mode=$MODE process_group_survived_kill process_group=$process_group_id"
        return 1
    fi
    return 0
}

interrupt_active_run() {
    local signal_name="$1"
    local exit_code="$2"
    log "interrupted mode=$MODE signal=$signal_name process_group=${ACTIVE_PROCESS_GROUP:-none}"
    if [ -n "$ACTIVE_PROCESS_GROUP" ]; then
        terminate_process_group "$ACTIVE_PROCESS_GROUP" || true
        ACTIVE_PROCESS_GROUP=""
    fi
    exit "$exit_code"
}

trap 'interrupt_active_run TERM 143' TERM
trap 'interrupt_active_run INT 130' INT
trap 'interrupt_active_run HUP 129' HUP

run_with_timeout() {
    "$PROCESS_LAUNCHER_PYTHON" -c \
        'import os, sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])' \
        "$@" >> "$LOG" 2>&1 &
    local pid=$!
    ACTIVE_PROCESS_GROUP="$pid"
    local deadline=$((SECONDS + TIMEOUT_SECONDS))
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            log "timeout mode=$MODE process_group=$pid seconds=$TIMEOUT_SECONDS"
            terminate_process_group "$pid"
            ACTIVE_PROCESS_GROUP=""
            return 124
        fi
        sleep 1
    done
    local rc=0
    wait "$pid" || rc=$?
    if process_group_is_alive "$pid"; then
        log "fatal mode=$MODE orphan_process_group=$pid"
        terminate_process_group "$pid"
        rc=70
    fi
    ACTIVE_PROCESS_GROUP=""
    return "$rc"
}

preflight_manifest() {
    local manifest="$1"
    "$PYTHON_BIN" - "$manifest" "${REQUIRED_SYSTEM_IDS[@]}" <<'PYEOF'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
required = set(sys.argv[2:])
if not manifest_path.is_file():
    raise SystemExit(f"missing manifest: {manifest_path}")
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
items = manifest.get("projection_inputs")
if items is None:
    item = manifest.get("projection_input")
    items = [] if item is None else [item]
systems = {str(item.get("system_id")) for item in items if isinstance(item, dict)}
missing = sorted(required - systems) if manifest.get("schema_version") == "magazine-morning-input.v2" else []
if missing:
    raise SystemExit(f"missing required systems: {', '.join(missing)}")
for item in items:
    projection = Path(str(item.get("projection_path", "")))
    if not projection.is_file():
        raise SystemExit(f"missing projection for {item.get('system_id')}")
PYEOF
}

if [ ! -x "$PYTHON_BIN" ]; then
    log "fatal: missing python venv at $PYTHON_BIN"
    exit 78
fi
if [ ! -x "$PROCESS_LAUNCHER_PYTHON" ]; then
    log "fatal: missing process launcher python at $PROCESS_LAUNCHER_PYTHON"
    exit 78
fi

case "$MODE" in
    morning)
        INPUT="${MAGAZINE_MORNING_INPUT:-$INPUT_DIR/morning-${DATE_WITA}.json}"
        OUTPUT="${MAGAZINE_MORNING_OUTPUT:-$OUTPUT_DIR/morning-${DATE_WITA}.json}"
        ASSET_MANIFEST="${MAGAZINE_MORNING_ASSET_MANIFEST:-$INPUT_DIR/assets-${DATE_WITA}.json}"
        CUTOFF="$(TZ=UTC date +%Y-%m-%dT%H:%M:%SZ)"
        COMMAND=( "$PYTHON_BIN" -m zantara_media.cli.magazine_publish morning
            --input "$INPUT"
            --output "$OUTPUT"
            --cutoff "$CUTOFF" )
        for system_id in "${REQUIRED_SYSTEM_IDS[@]}"; do
            COMMAND+=( --required-system-id "$system_id" )
        done
        ;;
    breaking)
        INPUT="${MAGAZINE_BREAKING_INPUT:-$INPUT_DIR/breaking-ready.json}"
        OUTPUT="${MAGAZINE_BREAKING_OUTPUT:-$OUTPUT_DIR/breaking-${DATE_WITA}-$(date +%H%M%S).json}"
        ASSET_MANIFEST="${MAGAZINE_BREAKING_ASSET_MANIFEST:-$INPUT_DIR/breaking-assets.json}"
        COMMAND=( "$PYTHON_BIN" -m zantara_media.cli.magazine_publish breaking
            --input "$INPUT"
            --output "$OUTPUT" )
        ;;
esac

if [ "$MODE" = "morning" ] && [ "${MAGAZINE_PREPARE_INPUTS:-true}" = "true" ]; then
    log "preparing collector projections mode=morning"
    cd "$MEDIA_DIR"
    PYTHONPATH="$MEDIA_DIR" run_with_timeout \
        "$PYTHON_BIN" -m zantara_media.cli.magazine_prepare morning \
        --repo-root "$ROOT" \
        --state-dir "$STATE_DIR" \
        --cutoff "$CUTOFF"
fi

if ! preflight_manifest "$INPUT" >> "$LOG" 2>&1; then
    log "fatal mode=$MODE manifest_preflight_failed"
    exit 65
fi

if [ "$PUBLISH_ENABLED" = "true" ]; then
    COMMAND+=( --publish --asset-manifest "$ASSET_MANIFEST" )
else
    COMMAND+=( --dry-run )
fi

log "starting mode=$MODE publish=$PUBLISH_ENABLED auto_assets=$MAGAZINE_AUTO_ASSETS output=$OUTPUT"
cd "$MEDIA_DIR"
PYTHONPATH="$MEDIA_DIR" run_with_timeout "${COMMAND[@]}"
