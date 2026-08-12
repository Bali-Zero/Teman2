#!/usr/bin/env bash
# Read-only semantic adapter for scripts/kbli_filiera/kbli_surface_conformance.py.
# launchd runs this through scripts/cron-runner.sh. Recognised detector outcomes
# are normalised only after their raw rc and content have been recorded.

set -euo pipefail

export PATH="/Users/nuzantara/.local/bin:/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export HOME="${HOME:-/Users/nuzantara}"

REPO_ROOT="${KBLI_SURFACE_CONFORMANCE_REPO_ROOT:-/Users/nuzantara/nuzantara}"
DETECTOR_PY="${KBLI_SURFACE_CONFORMANCE_DETECTOR_PY:-/Users/nuzantara/.pyenv/versions/3.11.11/bin/python}"
DETECTOR="${KBLI_SURFACE_CONFORMANCE_DETECTOR:-$REPO_ROOT/scripts/kbli_filiera/kbli_surface_conformance.py}"
HEARTBEAT_PY="${KBLI_SURFACE_CONFORMANCE_HEARTBEAT_PY:-/usr/bin/python3}"
HEARTBEAT="${KBLI_SURFACE_CONFORMANCE_HEARTBEAT:-$REPO_ROOT/scripts/lib/heartbeat.py}"
GATEWAY_PY="${KBLI_SURFACE_CONFORMANCE_GATEWAY_PY:-/usr/bin/python3}"
GATEWAY="${KBLI_SURFACE_CONFORMANCE_GATEWAY:-$REPO_ROOT/scripts/tg_notify.py}"
GTIMEOUT="${KBLI_SURFACE_CONFORMANCE_GTIMEOUT:-/opt/homebrew/bin/gtimeout}"
LSOF_BIN="${KBLI_SURFACE_CONFORMANCE_LSOF:-/usr/sbin/lsof}"
FLY_BIN="${KBLI_SURFACE_CONFORMANCE_FLY_BIN:-/opt/homebrew/bin/fly}"
FLY_CREDENTIAL_LIB="${KBLI_SURFACE_CONFORMANCE_FLY_CREDENTIAL_LIB:-$REPO_ROOT/scripts/lib/fly_credential.sh}"
SECRETS_FILE="${KBLI_SURFACE_CONFORMANCE_SECRETS_FILE:-$HOME/.nuzantara-secrets.env}"
LOG_DIR="${KBLI_SURFACE_CONFORMANCE_LOG_DIR:-$HOME/logs/kbli-conformance}"
LOCK_DIR="${KBLI_SURFACE_CONFORMANCE_LOCK_DIR:-$HOME/.agent/locks/kbli-surface-conformance.lock}"
EXPECTED_HOST="${KBLI_SURFACE_CONFORMANCE_EXPECTED_HOST:-Nuzantara}"
REPORT_HEADER="kbli_documents conformance vs canonical"
ORGAN_ID="pro.kbli_surface_conformance"

# The detector must reach Postgres only through scripts/pg.sh. Even if an
# operator shell happened to carry a DSN/PG tuple, do not let it bypass that
# read-only Keychain contract or leak into child diagnostics.
unset DATABASE_URL DATABASE_URL_LOCAL PGPASSWORD PGHOST PGPORT PGUSER PGDATABASE

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_DIR")"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/kbli-surface-conformance-$RUN_STAMP.log"
RUN_OUT="$LOG_DIR/.detector-$RUN_STAMP-$$.out"
LOCK_OWNER=""

log() {
    printf '[%s] %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >> "$LOG"
}

# shellcheck disable=SC2329  # invoked indirectly by trap
cleanup() {
    /bin/rm -f "$RUN_OUT"
    if [ -n "$LOCK_OWNER" ] && [ -f "$LOCK_DIR/pid" ]; then
        local recorded=""
        IFS= read -r recorded < "$LOCK_DIR/pid" || true
        if [ "$recorded" = "$LOCK_OWNER" ]; then
            /bin/rm -f "$LOCK_DIR/pid"
            /bin/rmdir "$LOCK_DIR" 2>/dev/null || true
        fi
    fi
}
trap cleanup EXIT INT TERM

write_heartbeat() {
    local status="$1" note="$2"
    set +e
    "$HEARTBEAT_PY" "$HEARTBEAT" "$ORGAN_ID" "$status" "$note"
    heartbeat_rc=$?
    set -e
    log "heartbeat_rc=$heartbeat_rc status=$status note=$note"
    return "$heartbeat_rc"
}

accepted_gateway_verdict() {
    case "$1" in
        sent|deduped|spooled|logged|p0_overflow_spooled|p0_unsent_spooled) return 0 ;;
        *) return 1 ;;
    esac
}

send_outcome_alert() {
    local tier="$1" key="$2" message="$3"
    local gateway_reply="" gateway_rc=0 gateway_verdict="" line=""
    set +e
    gateway_reply=$("$GATEWAY_PY" "$GATEWAY" \
        --tier "$tier" \
        --source kbli-surface-conformance \
        --dedup-key "$key" \
        -- "$message" 2>&1)
    gateway_rc=$?
    set -e

    while IFS= read -r line; do
        case "$line" in
            "tg_notify: sent"|"tg_notify: deduped"|"tg_notify: spooled"|"tg_notify: logged"|\
            "tg_notify: p0_overflow_spooled"|"tg_notify: p0_unsent_spooled")
                gateway_verdict="${line#tg_notify: }"
                ;;
        esac
    done <<< "$gateway_reply"

    log "gateway_rc=$gateway_rc gateway_verdict=${gateway_verdict:-absent}"
    if [ "$gateway_verdict" = "p0_overflow_spooled" ]; then
        log "night-cap-note: P0 budget overflowed; gateway durably accepted the alert for digest delivery"
    fi
    if [ "$gateway_rc" -ne 0 ] || ! accepted_gateway_verdict "$gateway_verdict"; then
        return 1
    fi
    printf '%s' "$gateway_verdict"
}

extract_fly_tokens_only() {
    local line="" key="" value=""
    [ -r "$SECRETS_FILE" ] || return 0
    while IFS= read -r line || [ -n "$line" ]; do
        if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?(FLY_API_TOKEN|FLY_ACCESS_TOKEN)[[:space:]]*=(.*)$ ]]; then
            key="${BASH_REMATCH[2]}"
            value="${BASH_REMATCH[3]}"
            value="${value#\"}"; value="${value%\"}"
            value="${value#\'}"; value="${value%\'}"
            if [ "$key" = "FLY_API_TOKEN" ]; then
                export FLY_API_TOKEN="$value"
            else
                export FLY_ACCESS_TOKEN="$value"
            fi
        fi
    done < "$SECRETS_FILE"
}

port_is_listening() {
    "$LSOF_BIN" -nP -iTCP:15432 -sTCP:LISTEN >/dev/null 2>&1
}

acquire_lock() {
    local existing=""
    if /bin/mkdir "$LOCK_DIR" 2>/dev/null; then
        LOCK_OWNER="$$"
        printf '%s\n' "$LOCK_OWNER" > "$LOCK_DIR/pid"
        return 0
    fi

    if [ -r "$LOCK_DIR/pid" ]; then
        IFS= read -r existing < "$LOCK_DIR/pid" || true
    fi
    if [[ "$existing" =~ ^[0-9]+$ ]] && kill -0 "$existing" 2>/dev/null; then
        return 2
    fi

    # One stale-lock cleanup and one retry; never remove a live owner's lock.
    /bin/rm -f "$LOCK_DIR/pid"
    /bin/rmdir "$LOCK_DIR" 2>/dev/null || return 3
    if /bin/mkdir "$LOCK_DIR" 2>/dev/null; then
        LOCK_OWNER="$$"
        printf '%s\n' "$LOCK_OWNER" > "$LOCK_DIR/pid"
        return 0
    fi
    return 3
}

classify_without_detector() {
    local reason="$1"
    printf '%s\n' "CANNOT VERIFY: $reason" > "$RUN_OUT"
    detector_rc=4
    result="cannot_verify"
    hb_status="warning"
    tier="digest"
    key="kbli-surface:cannot-verify"
}

host_now="${KBLI_SURFACE_CONFORMANCE_HOSTNAME:-$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)}"
log "start host=$host_now expected_host=$EXPECTED_HOST"

if [ "${KBLI_SURFACE_CONFORMANCE_ENABLED:-true}" = "false" ]; then
    if ! write_heartbeat "disabled" "kill switch KBLI_SURFACE_CONFORMANCE_ENABLED=false"; then
        echo "CRON_ALERT_P0: KBLI conformance detector disabled but its heartbeat could not be written; log=$LOG" >&2
        exit 70
    fi
    log "result=disabled"
    exit 0
fi

if [ "$host_now" != "$EXPECTED_HOST" ]; then
    classify_without_detector "Pro-only host guard refused host=$host_now expected=$EXPECTED_HOST"
else
    set +e
    acquire_lock
    lock_rc=$?
    set -e
    case "$lock_rc" in
        0) ;;
        2) classify_without_detector "overlapping run holds lock $LOCK_DIR" ;;
        *) classify_without_detector "lock unavailable after one stale-lock retry: $LOCK_DIR" ;;
    esac

    if [ "${result:-}" != "cannot_verify" ]; then
        if ! port_is_listening; then
            extract_fly_tokens_only
            if [ ! -r "$FLY_CREDENTIAL_LIB" ]; then
                classify_without_detector "Fly credential resolver missing: $FLY_CREDENTIAL_LIB"
            else
                # shellcheck source=/dev/null
                source "$FLY_CREDENTIAL_LIB"
                set +e
                resolve_fly_credential "$FLY_BIN" machine list --app nuzantara-postgres
                fly_rc=$?
                set -e
                if [ "$fly_rc" -ne 0 ]; then
                    classify_without_detector "app-scoped Fly credential/proxy preflight failed"
                else
                    log "Fly credential preflight accepted source=${FLY_CREDENTIAL_SOURCE:-unknown}"
                fi
            fi
        else
            log "Postgres proxy already listening on 127.0.0.1:15432; Fly probe skipped"
        fi
    fi

    if [ "${result:-}" != "cannot_verify" ]; then
        if [ ! -x "$DETECTOR_PY" ] || [ ! -r "$DETECTOR" ] || [ ! -x "$GTIMEOUT" ]; then
            classify_without_detector "runtime missing (detector python, detector, or gtimeout)"
        else
            set +e
            "$GTIMEOUT" -k 30 180 "$DETECTOR_PY" "$DETECTOR" > "$RUN_OUT" 2>&1
            detector_rc=$?
            set -e

            case "$detector_rc" in
                0)
                    hb_status="ok"; result="conformant"; tier="none"; key=""
                    ;;
                1)
                    if grep -Fqx "$REPORT_HEADER" "$RUN_OUT"; then
                        hb_status="error"; result="divergence"; tier="p0"; key="kbli-surface:divergence"
                    else
                        hb_status="error"; result="detector_failure"; tier="p0"; key="kbli-surface:detector-failure"
                    fi
                    ;;
                4|124)
                    hb_status="warning"; result="cannot_verify"; tier="digest"; key="kbli-surface:cannot-verify"
                    ;;
                *)
                    hb_status="error"; result="detector_failure"; tier="p0"; key="kbli-surface:detector-failure"
                    ;;
            esac
        fi
    fi
fi

{
    printf 'detector_rc=%s result=%s\n' "$detector_rc" "$result"
    printf '%s\n' '--- detector output ---'
    /bin/cat "$RUN_OUT"
} >> "$LOG"

if ! write_heartbeat "$hb_status" "detector_rc=$detector_rc result=$result log=$LOG"; then
    echo "CRON_ALERT_P0: KBLI conformance $result was recorded, but its direct heartbeat failed; detector_rc=$detector_rc log=$LOG" >&2
    exit 70
fi

case "$result" in
    conformant)
        log "healthy silence: gateway not invoked"
        exit 0
        ;;
    divergence)
        message="KBLI SURFACE DIVERGENCE
The detector completed a comparison and found load-bearing disagreement.
detector_rc=$detector_rc
log=$LOG"
        ;;
    cannot_verify)
        message="KBLI CONFORMANCE CANNOT VERIFY — NO COMPARISON VERDICT
The read-only detector could not complete a trustworthy comparison.
detector_rc=$detector_rc
log=$LOG"
        ;;
    detector_failure)
        message="KBLI CONFORMANCE DETECTOR FAILURE
The detector crashed or returned rc=1 without its conformance report header. This is not a divergence verdict.
detector_rc=$detector_rc
log=$LOG"
        ;;
    *)
        echo "CRON_ALERT_P0: KBLI conformance adapter reached unknown result=$result; log=$LOG" >&2
        exit 70
        ;;
esac

if ! gateway_verdict=$(send_outcome_alert "$tier" "$key" "$message"); then
    echo "CRON_ALERT_P0: KBLI conformance $result could not hand its alert to the gateway; detector_rc=$detector_rc log=$LOG" >&2
    exit 70
fi
log "completed result=$result detector_rc=$detector_rc gateway_verdict=$gateway_verdict"
exit 0
