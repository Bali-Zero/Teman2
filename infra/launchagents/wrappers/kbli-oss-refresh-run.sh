#!/usr/bin/env bash
# Weekly semantic adapter for scripts/kbli_filiera/oss_refresh_loop.py (F4).
# launchd runs this through scripts/cron-runner.sh on Mini. The heartbeat is the
# OUTCOME, not the exit code: a run only counts when the report it names exists,
# parses, and carries the same exit code the loop returned.

set -euo pipefail

export PATH="/Users/nuzantara/.local/bin:/opt/homebrew/bin:/Users/nuzantara/.pyenv/versions/3.11.11/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export HOME="${HOME:-/Users/nuzantara}"

REPO_ROOT="${KBLI_OSS_REFRESH_REPO_ROOT:-/Users/nuzantara/nuzantara}"
LOOP_PY="${KBLI_OSS_REFRESH_LOOP_PY:-/Users/nuzantara/.pyenv/versions/3.11.11/bin/python}"
LOOP="${KBLI_OSS_REFRESH_LOOP:-$REPO_ROOT/scripts/kbli_filiera/oss_refresh_loop.py}"
HEARTBEAT_PY="${KBLI_OSS_REFRESH_HEARTBEAT_PY:-/usr/bin/python3}"
HEARTBEAT="${KBLI_OSS_REFRESH_HEARTBEAT:-$REPO_ROOT/scripts/lib/heartbeat.py}"
GATEWAY_PY="${KBLI_OSS_REFRESH_GATEWAY_PY:-/usr/bin/python3}"
REPORT_PY="${KBLI_OSS_REFRESH_REPORT_PY:-/usr/bin/python3}"
GATEWAY="${KBLI_OSS_REFRESH_GATEWAY:-$REPO_ROOT/scripts/tg_notify.py}"
GTIMEOUT="${KBLI_OSS_REFRESH_GTIMEOUT:-/opt/homebrew/bin/gtimeout}"
TIMEOUT_S="${KBLI_OSS_REFRESH_TIMEOUT_S:-900}"
# Outputs keep the repo-relative layout but live OUTSIDE the main checkout, so a
# weekly run never leaves untracked files where `git pull --ff-only` runs.
OUT_ROOT="${KBLI_OSS_REFRESH_OUT_ROOT:-$HOME/nuzantara-vault-evidence/oss-refresh}"
LOG_DIR="${KBLI_OSS_REFRESH_LOG_DIR:-$HOME/logs/kbli-oss-refresh}"
LOCK_DIR="${KBLI_OSS_REFRESH_LOCK_DIR:-$HOME/.agent/locks/kbli-oss-refresh.lock}"
EXPECTED_HOST="${KBLI_OSS_REFRESH_EXPECTED_HOST:-mini-pro2}"
ORGAN_ID="${KBLI_OSS_REFRESH_ORGAN_ID:-mini.kbli_oss_refresh}"

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_DIR")"
RUN_STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
LOG="$LOG_DIR/kbli-oss-refresh-$RUN_STAMP.log"
RUN_OUT="$LOG_DIR/.loop-$RUN_STAMP-$$.out"
LOCK_OWNER=""
report_path=""
loop_rc=""

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
        --source kbli-oss-refresh \
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
    if [ "$gateway_rc" -ne 0 ] || ! accepted_gateway_verdict "$gateway_verdict"; then
        return 1
    fi
    printf '%s' "$gateway_verdict"
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

classify_without_loop() {
    local reason="$1"
    printf '%s\n' "CANNOT VERIFY: $reason" > "$RUN_OUT"
    loop_rc=4
    result="cannot_verify"
    hb_status="warning"
    tier="digest"
    key="kbli-oss-refresh:cannot-verify"
}

# Prints "<exit_code> <errors> <deferred> <proposed>" from the report, or fails.
read_report() {
    "$REPORT_PY" - "$1" <<'PY'
import json, sys
report = json.load(open(sys.argv[1], encoding="utf-8"))
cov, counts = report["coverage"], report["counts"]
print(report["exit_code"], cov["errors"], cov["deferred"], counts["published"] + counts["changed"])
PY
}

host_now="${KBLI_OSS_REFRESH_HOSTNAME:-$(hostname -s 2>/dev/null || hostname 2>/dev/null || echo unknown)}"
log "start host=$host_now expected_host=$EXPECTED_HOST user_key=${OSS_RBA_USER_KEY:+present}"

if [ "${KBLI_OSS_REFRESH_ENABLED:-true}" = "false" ]; then
    if ! write_heartbeat "disabled" "kill switch KBLI_OSS_REFRESH_ENABLED=false"; then
        echo "CRON_ALERT_P0: KBLI OSS refresh disabled but its heartbeat could not be written; log=$LOG" >&2
        exit 70
    fi
    log "result=disabled"
    exit 0
fi

if [ "$host_now" != "$EXPECTED_HOST" ]; then
    classify_without_loop "Mini-only host guard refused host=$host_now expected=$EXPECTED_HOST"
else
    set +e
    acquire_lock
    lock_rc=$?
    set -e
    case "$lock_rc" in
        0) ;;
        2) classify_without_loop "overlapping run holds lock $LOCK_DIR" ;;
        *) classify_without_loop "lock unavailable after one stale-lock retry: $LOCK_DIR" ;;
    esac

    if [ "${result:-}" != "cannot_verify" ]; then
        if [ ! -x "$LOOP_PY" ] || [ ! -r "$LOOP" ] || [ ! -x "$GTIMEOUT" ]; then
            classify_without_loop "runtime missing (loop python, loop, or gtimeout)"
        else
            set +e
            "$GTIMEOUT" -k 30 "$TIMEOUT_S" "$LOOP_PY" "$LOOP" --apply --out-root "$OUT_ROOT" > "$RUN_OUT" 2>&1
            loop_rc=$?
            set -e
            report_path="$(/usr/bin/sed -n 's/^OSS_REFRESH_REPORT=//p' "$RUN_OUT" | /usr/bin/tail -n 1)"

            case "$loop_rc" in
                0|1|4)
                    if [ -n "$report_path" ] && facts="$(read_report "$report_path" 2>/dev/null)"; then
                        read -r report_rc errors deferred proposed <<< "$facts"
                        if [ "$report_rc" != "$loop_rc" ]; then
                            hb_status="error"; result="loop_failure"; tier="p0"; key="kbli-oss-refresh:loop-failure"
                        elif [ "$loop_rc" = "4" ]; then
                            hb_status="warning"; result="cannot_verify"; tier="digest"; key="kbli-oss-refresh:cannot-verify"
                        elif [ "$loop_rc" = "1" ]; then
                            hb_status="ok"; result="new_scopes"; tier="digest"; key="kbli-oss-refresh:new-scopes"
                            # a proposal from a partial run is real news over an unverified rest
                            if [ "$errors" != "0" ] || [ "$deferred" != "0" ]; then hb_status="warning"; fi
                        elif [ "$errors" != "0" ] || [ "$deferred" != "0" ]; then
                            # rc 0 is only legal when every code answered: a report saying
                            # otherwise contradicts its own verdict.
                            hb_status="error"; result="loop_failure"; tier="p0"; key="kbli-oss-refresh:loop-failure"
                        else
                            hb_status="ok"; result="nothing_new"; tier="none"; key=""
                        fi
                    elif [ "$loop_rc" = "4" ]; then
                        # rc 4 before any fetch (canonical unreadable / empty population): no report by design.
                        hb_status="warning"; result="cannot_verify"; tier="digest"; key="kbli-oss-refresh:cannot-verify"
                    else
                        hb_status="error"; result="loop_failure"; tier="p0"; key="kbli-oss-refresh:loop-failure"
                    fi
                    ;;
                124)
                    hb_status="warning"; result="cannot_verify"; tier="digest"; key="kbli-oss-refresh:cannot-verify"
                    ;;
                *)
                    hb_status="error"; result="loop_failure"; tier="p0"; key="kbli-oss-refresh:loop-failure"
                    ;;
            esac
        fi
    fi
fi

{
    printf 'loop_rc=%s result=%s report=%s\n' "$loop_rc" "$result" "${report_path:-none}"
    printf '%s\n' '--- loop output ---'
    /bin/cat "$RUN_OUT"
} >> "$LOG"

if ! write_heartbeat "$hb_status" "loop_rc=$loop_rc result=$result report=${report_path:-none}"; then
    echo "CRON_ALERT_P0: KBLI OSS refresh $result was recorded, but its direct heartbeat failed; loop_rc=$loop_rc log=$LOG" >&2
    exit 70
fi

case "$result" in
    nothing_new)
        log "healthy silence: gateway not invoked"
        exit 0
        ;;
    new_scopes)
        message="KBLI OSS REFRESH — NEW SCOPES PUBLISHED
OSS now publishes a ruang-lingkup scope for $proposed licensing-gap code(s). A cure SPEC was emitted; nothing was written to the canonical.
unanswered: errors=$errors deferred=$deferred
report=$report_path
log=$LOG"
        ;;
    cannot_verify)
        message="KBLI OSS REFRESH CANNOT VERIFY — NO VERDICT ON THE GAPS
The loop could not vouch for its answers (partial run, auth refused, endpoint blind, empty fetch, timeout, or a guard refused the run).
unanswered: errors=${errors:-?} deferred=${deferred:-?}
loop_rc=$loop_rc report=${report_path:-none}
log=$LOG"
        ;;
    loop_failure)
        message="KBLI OSS REFRESH LOOP FAILURE
The loop crashed, or its report is missing or disagrees with its exit code. This is not a verdict on the gaps.
loop_rc=$loop_rc
log=$LOG"
        ;;
    *)
        echo "CRON_ALERT_P0: KBLI OSS refresh adapter reached unknown result=$result; log=$LOG" >&2
        exit 70
        ;;
esac

if ! gateway_verdict=$(send_outcome_alert "$tier" "$key" "$message"); then
    echo "CRON_ALERT_P0: KBLI OSS refresh $result could not hand its alert to the gateway; loop_rc=$loop_rc log=$LOG" >&2
    exit 70
fi
log "completed result=$result loop_rc=$loop_rc gateway_verdict=$gateway_verdict"
exit 0
