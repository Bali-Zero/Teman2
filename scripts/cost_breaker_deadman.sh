#!/usr/bin/env bash
# cost_breaker_deadman.sh — P9 G5 dead-man's switch: the SECOND observer of the
# governance alive-signals.
#
# This realises the UNBUILT "mutual-watch" documented in
# scripts/sentinel_meta_watchdog.sh's header ("sentinel can be extended … to
# alert if THAT goes stale"). The governance layer writes two alive-signals each
# tick:
#   ~/.agent/decisions/state/verify_the_verifiers.json   (the meta-verifier)
#   ~/.agent/decisions/state/sentinel_meta_watchdog.json (the sentinel watcher)
# If EITHER goes stale beyond a critical threshold (≈2× its expected interval),
# the governance has gone MUTE — and nobody would notice, because the thing that
# would notice is the thing that died. This watchdog is that missing observer.
#
# Like sentinel_meta_watchdog.sh, this is short-lived (stat → compare → maybe
# alert → exit) so it cannot itself hang. It writes its OWN alive-signal so it,
# too, can be watched (turtles, but a finite stack: deadman watches verifier +
# sentinel; a human reads deadman's last alert / its own state file).
#
# Self-test:  FORCE_ALERT=1 bash scripts/cost_breaker_deadman.sh
# Classify:   bash scripts/cost_breaker_deadman.sh --classify <file> <thresh_s>
#             -> prints MISSING | STALE | FRESH (no telegram, pure stat compare).
#             This is the REAL stale-detection logic, callable for CI/tests
#             WITHOUT FORCE_ALERT (which short-circuits it). Exit 0=FRESH,
#             1=STALE, 2=MISSING so a caller can branch on the code too.
# Kill-switch: COST_BREAKER_DEADMAN_OFF=1
#
# Run via launchd every ~600s (companion plist not shipped in this safe slice —
# install is an operator step, same pattern as sentinel_meta_watchdog).

set -uo pipefail

# --- Kill-switch -----------------------------------------------------------

if [[ "${COST_BREAKER_DEADMAN_OFF:-0}" == "1" ]]; then
    echo "cost_breaker_deadman: disabled via COST_BREAKER_DEADMAN_OFF=1" >&2
    exit 0
fi

# --- Configuration ---------------------------------------------------------

STATE_DIR="$HOME/.agent/decisions/state"

# The two governance alive-signals we observe, with their critical staleness
# thresholds (≈2× the expected emit interval — generous, only fire on a true
# stall, not a slow tick). verify_the_verifiers + sentinel_meta_watchdog both
# emit on cron cadences in the 10-15min range, so 1800s (30min) is a safe 2×.
OBSERVED_FILES=(
    "$STATE_DIR/verify_the_verifiers.json"
    "$STATE_DIR/sentinel_meta_watchdog.json"
)
CRITICAL_THRESHOLD_SEC="${COST_BREAKER_DEADMAN_THRESHOLD_SEC:-1800}"  # 30 min
COOLDOWN_SEC=3600                                                     # 1 h

LOG_FILE="$HOME/logs/cost-breaker-deadman.log"
DEADMAN_STATE_FILE="$STATE_DIR/cost_breaker_deadman.json"
COOLDOWN_FILE="$STATE_DIR/cost_breaker_deadman.cooldown"

# Source secrets (TELEGRAM_BOT_TOKEN + chat id). NEVER hardcode the token.
if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-${BALIZEROBOT_TOKEN:-}}"
TELEGRAM_CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-${TELEGRAM_CHAT_ID:-1125336968}}}"

# --- Helpers ---------------------------------------------------------------

mkdir -p "$(dirname "$LOG_FILE")" "$STATE_DIR"

log() {
    echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*" >> "$LOG_FILE"
}

mtime_epoch() {
    # Portable mtime-in-epoch-seconds. BSD/macOS stat uses `-f %m`; GNU/Linux
    # stat uses `-c %Y`. Try BSD first, fall back to GNU. Returns 0 if both
    # fail (missing file or unsupported stat) so callers degrade to "stale".
    stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

# classify_file <path> <threshold_sec> [now_epoch]
# The REAL stale-detection logic, isolated + side-effect-free (no telegram, no
# state write). Prints MISSING / STALE / FRESH and returns 2 / 1 / 0. Used by
# main() AND by the CI/unit test (so the logic is exercised, not just bash -n +
# FORCE_ALERT which bypasses it — P2-5).
classify_file() {
    local path="$1" threshold="$2" now="${3:-$(date +%s)}"
    if [[ ! -f "$path" ]]; then
        echo "MISSING"
        return 2
    fi
    local mtime age
    mtime=$(mtime_epoch "$path")
    age=$((now - mtime))
    if (( age > threshold )); then
        echo "STALE"
        return 1
    fi
    echo "FRESH"
    return 0
}

write_state() {
    local status="$1" detail="$2"
    cat > "$DEADMAN_STATE_FILE" <<EOF
{
  "ts": $(date +%s),
  "generated_at": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "status": "$status",
  "critical_threshold_s": $CRITICAL_THRESHOLD_SEC,
  "detail": "$detail",
  "_writer": "cost_breaker_deadman"
}
EOF
}

cooldown_active() {
    [[ ! -f "$COOLDOWN_FILE" ]] && return 1
    local last now elapsed
    last=$(mtime_epoch "$COOLDOWN_FILE")
    now=$(date +%s)
    elapsed=$((now - last))
    (( elapsed < COOLDOWN_SEC ))
}

cooldown_set() {
    touch "$COOLDOWN_FILE"
}

tg_alert() {
    local text="$1"
    if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
        log "telegram: missing creds (token or chat_id), skipping alert"
        return 1
    fi
    curl -sS -m 10 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${text}" \
        -d "parse_mode=HTML" \
        -o /dev/null \
        || log "telegram: post failed"
}

# --- Main ------------------------------------------------------------------

main() {
    local now stale_detail="" any_stale=0
    now=$(date +%s)

    # FORCE_ALERT self-test: pretend the first observed signal is stale.
    if [[ "${FORCE_ALERT:-0}" == "1" ]]; then
        stale_detail="SELF-TEST (FORCE_ALERT=1): simulated stale governance signal"
        any_stale=1
    else
        for f in "${OBSERVED_FILES[@]}"; do
            local name verdict
            name=$(basename "$f" .json)
            # Reuse the SAME classify_file logic the test exercises (P2-5) so
            # production and CI cannot drift.
            verdict=$(classify_file "$f" "$CRITICAL_THRESHOLD_SEC" "$now")
            case "$verdict" in
                MISSING)
                    stale_detail+="${name}=MISSING; "
                    any_stale=1
                    ;;
                STALE)
                    local mtime age
                    mtime=$(mtime_epoch "$f")
                    age=$((now - mtime))
                    stale_detail+="${name}=stale ${age}s; "
                    any_stale=1
                    ;;
            esac
        done
    fi

    if (( any_stale == 0 )); then
        log "OK all governance alive-signals fresh (threshold=${CRITICAL_THRESHOLD_SEC}s)"
        write_state "ok" "all fresh"
        exit 0
    fi

    log "STALE governance: ${stale_detail}"
    write_state "stale" "${stale_detail}"

    if cooldown_active; then
        log "cooldown active, not alerting (will retry next tick after cooldown)"
        exit 0
    fi

    # The alert is a CHOICE, not just a diagnosis (same G3 spirit as the breaker).
    tg_alert "🕳️ <b>governance muta</b>: ${stale_detail}— il cost-breaker / verify-the-verifiers non emette più segnale di vita (>${CRITICAL_THRESHOLD_SEC}s). [I]ndaga / [R]iavvia il guardiano / [S]ilenzia 1h?"
    cooldown_set
}

# --- Dispatch --------------------------------------------------------------
# `--classify <file> <threshold_sec> [now]` is a pure logic probe (no telegram,
# no state write, ignores the kill-switch/cooldown) so CI + unit tests can
# exercise the REAL stale-detection without FORCE_ALERT short-circuiting it.
if [[ "${1:-}" == "--classify" ]]; then
    if [[ -z "${2:-}" || -z "${3:-}" ]]; then
        echo "usage: $0 --classify <file> <threshold_sec> [now_epoch]" >&2
        exit 64
    fi
    if [[ -n "${4:-}" ]]; then
        classify_file "$2" "$3" "$4"
    else
        classify_file "$2" "$3"
    fi
    exit $?
fi

main "$@"
