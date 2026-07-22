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
STATE_DIR="${MAGAZINE_STATE_DIR:-$HOME/.local/state/bali-zero-magazine}"
INPUT_DIR="${MAGAZINE_INPUT_DIR:-$STATE_DIR/inputs}"
OUTPUT_DIR="${MAGAZINE_OUTPUT_DIR:-$STATE_DIR/packets}"
LOG_DIR="${MAGAZINE_LOG_DIR:-$HOME/logs}"
DATE_WITA="$(TZ=Asia/Makassar date +%Y-%m-%d)"
LOG="$LOG_DIR/bali-zero-magazine-${MODE}.log"
LOCKDIR="$STATE_DIR/${MODE}.lock"
TIMEOUT_SECONDS="${MAGAZINE_TIMEOUT_SECONDS:-840}"
PUBLISH_ENABLED="${MAGAZINE_PUBLISH_ENABLED:-true}"
REQUIRED_SYSTEM_IDS=(${=MAGAZINE_REQUIRED_SYSTEM_IDS:-intel-lake mata-garuda regulatory-watcher notebooklm})

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

if ! mkdir "$LOCKDIR" 2>/dev/null; then
    other_pid="$(cat "$LOCKDIR/pid" 2>/dev/null || true)"
    if [ -n "$other_pid" ] && kill -0 "$other_pid" 2>/dev/null; then
        log "duplicate suppressed mode=$MODE live_pid=$other_pid"
        exit 0
    fi
    log "stale lock recovered mode=$MODE old_pid=${other_pid:-none}"
    rm -rf "$LOCKDIR"
    if ! mkdir "$LOCKDIR" 2>/dev/null; then
        log "lock race lost mode=$MODE"
        exit 0
    fi
fi
echo $$ > "$LOCKDIR/pid"

finish() {
    local rc=$?
    rm -rf "$LOCKDIR"
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

run_with_timeout() {
    "$@" >> "$LOG" 2>&1 &
    local pid=$!
    local deadline=$((SECONDS + TIMEOUT_SECONDS))
    while kill -0 "$pid" 2>/dev/null; do
        if [ "$SECONDS" -ge "$deadline" ]; then
            log "timeout mode=$MODE pid=$pid seconds=$TIMEOUT_SECONDS"
            kill "$pid" 2>/dev/null || true
            sleep 2
            kill -9 "$pid" 2>/dev/null || true
            wait "$pid" 2>/dev/null || true
            return 124
        fi
        sleep 1
    done
    wait "$pid"
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

preflight_manifest "$INPUT" >> "$LOG" 2>&1

if [ "$PUBLISH_ENABLED" = "true" ]; then
    if [ ! -f "$ASSET_MANIFEST" ]; then
        log "fatal: publish enabled but asset manifest is missing mode=$MODE"
        exit 78
    fi
    COMMAND+=( --publish --asset-manifest "$ASSET_MANIFEST" )
else
    COMMAND+=( --dry-run )
fi

log "starting mode=$MODE publish=$PUBLISH_ENABLED output=$OUTPUT"
cd "$MEDIA_DIR"
PYTHONPATH="$MEDIA_DIR" run_with_timeout "${COMMAND[@]}"
