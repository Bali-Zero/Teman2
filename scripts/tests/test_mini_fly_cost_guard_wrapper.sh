#!/bin/bash
# Fake-world proof for mini-fly-cost-guard.sh. No real Fly or Telegram calls.

set -u
PASS=0; FAIL=0
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
WRAPPER="$ROOT/infra/launchagents/wrappers/mini-fly-cost-guard.sh"
TOKEN_MARKER="fly-token-must-not-escape"
GATEWAY_TOKEN_MARKER="gateway-token-must-not-escape"

ok() { PASS=$((PASS + 1)); printf '  ok   %s\n' "$1"; }
bad() { FAIL=$((FAIL + 1)); printf '  FAIL %s\n     %s\n' "$1" "$2"; }

field() { printf '%s' "$1" | sed -n "s/.*\"$2\":\"\([^\"]*\)\".*/\1/p"; }

prepare_case() { # $1=guard rc, $2=guard output, $3=credential failure, $4=guard sleep, $5=gateway echoes secret
    local guard_rc="$1" guard_output="$2" cred_fail="$3" guard_sleep="$4" gateway_echo="$5"
    CASE_TMP="$(mktemp -d)"
    mkdir -p "$CASE_TMP/bin" "$CASE_TMP/home/nuzantara/scripts/lib"
    cp "$ROOT/scripts/lib/fly_credential.sh" "$CASE_TMP/home/nuzantara/scripts/lib/"
    : > "$CASE_TMP/home/nuzantara/scripts/fly_cost_guard.py"
    : > "$CASE_TMP/home/nuzantara/scripts/tg_notify.py"
    printf 'FLY_API_TOKEN=%s\nTELEGRAM_BOT_TOKEN=%s\n' \
        "$TOKEN_MARKER" "$GATEWAY_TOKEN_MARKER" > "$CASE_TMP/home/.nuzantara-secrets.env"
    chmod 600 "$CASE_TMP/home/.nuzantara-secrets.env"

    printf '#!/bin/bash\necho Mini-Pro2\n' > "$CASE_TMP/bin/hostname"
    printf '#!/bin/bash\n[ "${STUB_CRED_FAIL:-false}" = true ] && { echo "credential refused ${FLY_API_TOKEN:-none}" >&2; exit 1; }\nexit 0\n' \
        > "$CASE_TMP/bin/flyctl"
    cat > "$CASE_TMP/bin/python-stub" <<'STUB'
#!/bin/bash
case "$1" in
    */fly_cost_guard.py)
        [ "${STUB_GUARD_SLEEP:-0}" = 0 ] || sleep "$STUB_GUARD_SLEEP"
        printf '%s\n' "$STUB_GUARD_OUTPUT"
        printf '%s|%s|%s|%s|%s|%s|%s\n' \
            "$EXPECTED_APPS" "$MAX_TOTAL_MACHINES" "$MAX_STARTED_MACHINES" \
            "$MAX_STARTED_MEMORY_MB" "$MAX_STARTED_CPUS" "$MAX_TOTAL_VOLUME_GB" \
            "$MAX_DEDICATED_IPV4" > "$STUB_CAPTURE_DIR/ceilings"
        exit "$STUB_GUARD_RC"
        ;;
    */tg_notify.py)
        if [ "${STUB_GATEWAY_ECHO_SECRET:-false}" = true ]; then
            printf 'gateway stdout %s\n' "${TELEGRAM_BOT_TOKEN:-none}"
            printf 'gateway stderr %s\n' "${TELEGRAM_BOT_TOKEN:-none}" >&2
        fi
        {
            printf 'routing=%s\n' "${TG_ACT_ROUTING_ENABLED-UNSET}"
            printf 'relay_set=%s\n' "${TG_RELAY_SSH+x}"
            printf 'relay_value=%s\n' "${TG_RELAY_SSH-UNSET}"
            printf 'fly_token_set=%s\n' "${FLY_API_TOKEN+x}"
            printf 'args=%s\n' "$*"
        } >> "$STUB_CAPTURE_DIR/notify"
        exit 0
        ;;
esac
exit 99
STUB
    chmod +x "$CASE_TMP/bin/hostname" "$CASE_TMP/bin/flyctl" "$CASE_TMP/bin/python-stub"

    STUB_GUARD_RC="$guard_rc"
    STUB_GUARD_OUTPUT="$guard_output"
    STUB_CRED_FAIL="$cred_fail"
    STUB_GUARD_SLEEP="$guard_sleep"
    STUB_GATEWAY_ECHO_SECRET="$gateway_echo"
}

invoke_case() { # $1=capture path, $2=test-only timeout seconds
    local capture_path="$1" timeout_seconds="$2"
    env -i HOME="$CASE_TMP/home" PATH="$CASE_TMP/bin:/usr/bin:/bin" \
        MINI_FLY_COST_GUARD_PYTHON_BIN="$CASE_TMP/bin/python-stub" \
        MINI_FLY_COST_GUARD_FLY_BIN="$CASE_TMP/bin/flyctl" \
        MINI_FLY_COST_GUARD_LOCKDIR="$CASE_TMP/lock" \
        MINI_FLY_COST_GUARD_TEST_TIMEOUT_SECONDS="$timeout_seconds" \
        STUB_CAPTURE_DIR="$CASE_TMP" STUB_GUARD_RC="$STUB_GUARD_RC" \
        STUB_GUARD_OUTPUT="$STUB_GUARD_OUTPUT" STUB_CRED_FAIL="$STUB_CRED_FAIL" \
        STUB_GUARD_SLEEP="$STUB_GUARD_SLEEP" STUB_GATEWAY_ECHO_SECRET="$STUB_GATEWAY_ECHO_SECRET" \
        /bin/bash "$WRAPPER" > "$capture_path" 2>&1
    CASE_RC=$?
    CASE_HB="$(cat "$CASE_TMP/home/.organism/last_seen/mini.fly_cost_guard.json" 2>/dev/null)"
}

run_case() { # $1=guard rc, $2=guard output, $3=credential failure, $4=sleep, $5=gateway echo, $6=timeout
    prepare_case "$1" "$2" "$3" "${4:-0}" "${5:-false}"
    invoke_case "$CASE_TMP/captured" "${6:-900}"
}

run_live_lock_case() { # $1=young/old
    local age_kind="$1" owner_pid owner_start
    prepare_case 0 'Fly resource guard: within limits' false 0 false
    cat > "$CASE_TMP/bin/ps" <<'STUB'
#!/bin/bash
case "$*" in
    *lstart=*) printf ' Mon Jan  1 00:00:00 2024\n' ;;
    *command=*) printf '/bin/bash mini-fly-cost-guard.sh\n' ;;
esac
STUB
    chmod +x "$CASE_TMP/bin/ps"
    owner_pid=$$
    owner_start=$("$CASE_TMP/bin/ps" -p "$owner_pid" -o lstart= | tr -s ' ')
    mkdir "$CASE_TMP/lock"
    printf '%s %s\n' "$owner_pid" "$owner_start" > "$CASE_TMP/lock/pid"
    [ "$age_kind" = old ] && touch -t 200001010000 "$CASE_TMP/lock"
    invoke_case "$CASE_TMP/second-captured" 900
}

assert_no_token() {
    local found=""
    for path in "$CASE_TMP/captured" "$CASE_TMP/notify" \
        "$CASE_TMP/home/.organism/last_seen/mini.fly_cost_guard.json" \
        "$CASE_TMP/home/logs/mini-fly-cost-guard/run.log"; do
        [ -f "$path" ] && grep -Fq "$TOKEN_MARKER" "$path" && found="$found $path"
    done
    [ -z "$found" ] && ok "$1 does not expose the token" || bad "$1 leaked the token" "$found"
}

echo "== rc 0: digest plus healthy heartbeat =="
run_case 0 \
    'Apps: 2 | Machines: 6/7 started (limit 6/7)
Fly resource guard: within limits' false
[ "$CASE_RC" -eq 0 ] && ok "rc 0 preserved" || bad "rc 0" "$CASE_RC"
[ "$(field "$CASE_HB" status)" = "ok" ] && ok "rc 0 heartbeat is ok" || bad "rc 0 heartbeat" "$CASE_HB"
grep -q -- '--tier digest' "$CASE_TMP/notify" && grep -q 'Apps: 2' "$CASE_TMP/notify" \
    && grep -q '^fly_token_set=$' "$CASE_TMP/notify" \
    && ok "rc 0 sends the report through digest without the Fly credential" \
    || bad "rc 0 digest" "$(cat "$CASE_TMP/notify")"
[ "$(cat "$CASE_TMP/ceilings")" = 'nuzantara-rag,nuzantara-postgres|7|6|12288|11|77|0' ] \
    && ok "wrapper exports the retired workflow ceilings exactly" \
    || bad "wrong ceilings" "$(cat "$CASE_TMP/ceilings")"
assert_no_token "rc 0"

echo "== rc 1: p0, deterministic dedup, monitor stays healthy =="
run_case 1 \
    'Apps: 2 | Machines: 7/8 started (limit 6/7)
::error::Fly resource guard: volumes 78GB>77GB; started machines 7>6' false
EXPECTED_HASH=$(printf '%s\n' 'started machines 7>6' 'volumes 78GB>77GB' | shasum -a 1 | awk '{print substr($1,1,12)}')
[ "$CASE_RC" -eq 1 ] && ok "rc 1 preserved" || bad "rc 1" "$CASE_RC"
[ "$(field "$CASE_HB" status)" = "ok" ] && [ "$(field "$CASE_HB" note)" = 'monitor healthy; findings=2' ] \
    && ok "findings leave an ok monitor heartbeat with count" || bad "rc 1 heartbeat" "$CASE_HB"
grep -q -- '--tier p0' "$CASE_TMP/notify" \
    && grep -q -- "--dedup-key fly-cost:$EXPECTED_HASH" "$CASE_TMP/notify" \
    && grep -q '^routing=false$' "$CASE_TMP/notify" \
    && grep -q '^relay_set=x$' "$CASE_TMP/notify" \
    && grep -q '^relay_value=$' "$CASE_TMP/notify" \
    && grep -q '^fly_token_set=$' "$CASE_TMP/notify" \
    && ok "rc 1 p0 has dedup and direct-routing environment" \
    || bad "rc 1 p0 contract" "$(cat "$CASE_TMP/notify")"
assert_no_token "rc 1"

echo "== credential failure: broken p0 plus error heartbeat =="
run_case 0 'unused' true
[ "$CASE_RC" -eq 2 ] && ok "credential failure exits 2" || bad "credential failure rc" "$CASE_RC"
[ "$(field "$CASE_HB" status)" = "error" ] \
    && ok "credential failure heartbeat is error" || bad "credential failure heartbeat" "$CASE_HB"
grep -q -- '--tier p0' "$CASE_TMP/notify" && grep -q 'fly cost guard broken' "$CASE_TMP/notify" \
    && ok "credential failure sends broken p0" || bad "credential failure p0" "$(cat "$CASE_TMP/notify")"
[ ! -f "$CASE_TMP/ceilings" ] && ok "guard never ran with unresolved credentials" \
    || bad "guard ran after credential failure" "$(cat "$CASE_TMP/ceilings" 2>/dev/null)"
assert_no_token "credential failure"

echo "== stale lock: dead owner is reclaimed =="
prepare_case 0 'Fly resource guard: within limits' false 0 false
mkdir "$CASE_TMP/lock"
printf '999999 dead-owner\n' > "$CASE_TMP/lock/pid"
invoke_case "$CASE_TMP/captured" 900
[ "$CASE_RC" -eq 0 ] && [ "$(field "$CASE_HB" status)" = "ok" ] \
    && [ -f "$CASE_TMP/ceilings" ] && grep -q 'stale lock' "$CASE_TMP/home/logs/mini-fly-cost-guard/run.log" \
    && ok "dead lock owner is reclaimed and the guard runs" \
    || bad "stale lock was not reclaimed" "rc=$CASE_RC heartbeat=$CASE_HB"

echo "== live young lock: later run skips with active warning =="
run_live_lock_case young
[ "$CASE_RC" -eq 0 ] && [ "$(field "$CASE_HB" status)" = "warning" ] \
    && [ "$(field "$CASE_HB" note)" = "run already active" ] \
    && ok "young live lock reports run already active" \
    || bad "young live lock warning" "rc=$CASE_RC heartbeat=$CASE_HB"

echo "== live old lock: warning includes age =="
run_live_lock_case old
[ "$CASE_RC" -eq 0 ] && [ "$(field "$CASE_HB" status)" = "warning" ] \
    && printf '%s' "$(field "$CASE_HB" note)" | grep -Eq '^run already active; age=[0-9]+s$' \
    && ok "old live lock warning names its age" \
    || bad "old live lock warning" "rc=$CASE_RC heartbeat=$CASE_HB"

echo "== timeout: sleeping guard becomes broken p0 =="
run_case 0 'never reached' false 3 false 1
[ "$CASE_RC" -eq 2 ] && [ "$(field "$CASE_HB" status)" = "error" ] \
    && [ "$(field "$CASE_HB" note)" = "guard timed out after 1 s" ] \
    && grep -q -- '--tier p0' "$CASE_TMP/notify" \
    && grep -q 'fly cost guard broken' "$CASE_TMP/notify" \
    && ok "guard timeout writes error heartbeat and broken p0" \
    || bad "guard timeout contract" "rc=$CASE_RC heartbeat=$CASE_HB notify=$(cat "$CASE_TMP/notify" 2>/dev/null)"

echo "== gateway output: stdout and stderr are redacted in the log =="
run_case 0 'Fly resource guard: within limits' false 0 true 900
LOG_FILE="$CASE_TMP/home/logs/mini-fly-cost-guard/run.log"
grep -q 'gateway stdout \[REDACTED\]' "$LOG_FILE" \
    && grep -q 'gateway stderr \[REDACTED\]' "$LOG_FILE" \
    && ! grep -Fq "$GATEWAY_TOKEN_MARKER" "$LOG_FILE" \
    && ok "gateway stdout and stderr pass through redaction" \
    || bad "gateway output redaction" "$(cat "$LOG_FILE")"

echo
printf 'passed %d, failed %d\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ]
