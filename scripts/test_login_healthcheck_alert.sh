#!/usr/bin/env bash
# Proof for the alarm-channel-down hardening in scripts/login-healthcheck.sh.
#
# TRAUMA (measured 2026-08-19, ~/logs/login-healthcheck.log, 5941 lines):
# status=ok: 0. status=fail: 2940. ALERT: login_fail logged 61 times — the
# 2-consecutive-failure gate works. telegram: missing creds logged 61
# times — EVERY alarm died at the gateway, and the script's own exit code
# and Genoma last_error never said so: it looked exactly like an ordinary
# failed probe. A monitor that cannot tell "the thing I watch is broken"
# from "I have no way to tell anyone" is worse than no monitor at all,
# because it looks alive.
#
#   GUILT   — alarm channel unarmed (no creds) + probe failing 2x in a row:
#             the loudest exit code (3) AND the sidecar names the channel,
#             not the login failure.
#   GUILT   — probe failing 2x + alarm channel armed: the alert is actually
#             ATTEMPTED (assert the fake gateway was called), delivered
#             exit code (2), sidecar keeps the ordinary login-failure text.
#   INNOCENCE — probe healthy: exit 0, no alert attempted, ever.
#   INNOCENCE — --selftest with a working fake gateway: exit 0, and it
#             never touches STATE_FILE/COOLDOWN_FILE/sidecar.
#   + extras: a lone first failure must not alert (2-consecutive rule
#             preserved); a broken --selftest must exit non-zero and still
#             touch nothing; an armed cooldown must still suppress a repeat
#             alert (existing 2h-cooldown behaviour preserved) while the
#             new exit-code split holds around it.
#
# No network: the wrapper runs from a tmp copy with a fake `curl` placed
# FIRST on $PATH (login-healthcheck.sh never overwrites PATH itself, unlike
# cron-runner.sh — so plain PATH-shadowing works here). The fake curl
# recognizes the two URLs this script calls (api.telegram.org for the
# alert, kita.balizero.com for the login probe) and answers each from env
# knobs, recording every call it saw for assertions.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP="$(mktemp -d)"
trap '/bin/rm -rf "$TMP"' EXIT

WRAPPER="$HERE/login-healthcheck.sh"
[ -f "$WRAPPER" ] || { echo "login-healthcheck.sh not found at $WRAPPER"; exit 1; }

PASS=0; FAIL=0
check () {  # check <name> <0-or-1>
    if [ "$2" = "0" ]; then PASS=$((PASS+1)); printf '  ok    %s\n' "$1"
    else FAIL=$((FAIL+1)); printf '  FAIL  %s\n' "$1"; fi
}

write_fake_curl () {
    cat > "$TMP/bin/curl" <<'STUB'
#!/usr/bin/env bash
# Fake curl for login-healthcheck test: routes by URL, controlled by env.
url=""
outfile=""
prev=""
for a in "$@"; do
    if [ "$prev" = "-o" ]; then outfile="$a"; fi
    case "$a" in
        http*) url="$a" ;;
    esac
    prev="$a"
done

case "$url" in
    *api.telegram.org*)
        printf '%s\n' "$*" >> "$FAKE_CALLS_DIR/telegram.calls"
        exit "${FAKE_TG_RC:-0}"
        ;;
    *kita.balizero.com*)
        printf '%s\n' "$*" >> "$FAKE_CALLS_DIR/login.calls"
        if [ -n "$outfile" ]; then
            if [ "${FAKE_LOGIN_HAS_TOKEN:-false}" = "true" ]; then
                printf '{"token":"fake-jwt"}' > "$outfile"
            else
                printf '{"error":"forbidden"}' > "$outfile"
            fi
        fi
        printf '%s' "${FAKE_LOGIN_HTTP_CODE:-200}"
        exit 0
        ;;
    *)
        echo "fake curl: unrecognized URL: $url" >&2
        exit 1
        ;;
esac
STUB
    chmod +x "$TMP/bin/curl"
}

reset_env () {
    rm -rf "${TMP:?}/run" "${TMP:?}/home" "${TMP:?}/bin" "${TMP:?}/calls"
    mkdir -p "$TMP/run" "$TMP/home" "$TMP/bin" "$TMP/calls"
    cp "$WRAPPER" "$TMP/run/login-healthcheck.sh"
    chmod +x "$TMP/run/login-healthcheck.sh"
    write_fake_curl
}

SIDECAR="$TMP/home/.agent/decisions/state/login_healthcheck.last.json"
STATEFILE="$TMP/home/.agent/decisions/login_healthcheck.json"
COOLDOWNFILE="$TMP/home/.agent/decisions/login_healthcheck.cooldown"
LOGFILE="$TMP/home/logs/login-healthcheck.log"

run_case () {  # run_case [--selftest]
    HOME="$TMP/home" \
    PATH="$TMP/bin:$PATH" \
    FAKE_CALLS_DIR="$TMP/calls" \
    FAKE_TG_RC="${FAKE_TG_RC:-0}" \
    FAKE_LOGIN_HTTP_CODE="${FAKE_LOGIN_HTTP_CODE:-200}" \
    FAKE_LOGIN_HAS_TOKEN="${FAKE_LOGIN_HAS_TOKEN:-true}" \
    HEALTHCHECK_EMAIL="healthcheck@balizero.com" \
    HEALTHCHECK_PIN="000000" \
    TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN-}" \
    TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID-}" \
        bash "$TMP/run/login-healthcheck.sh" "$@" >"$TMP/stdout.log" 2>"$TMP/stderr.log"
    RC=$?
}

echo "GUILT 1 — alarm channel unarmed + probe failing 2x => loudest exit + sidecar names the channel"
reset_env
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # 1st failure: no alert due yet
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # 2nd: alert due, creds missing
check "exit code 3 (alarm channel down)"        "$([ "$RC" = "3" ] && echo 0 || echo 1)"
check "sidecar names ALARM-CHANNEL-DOWN"        "$(grep -q 'ALARM-CHANNEL-DOWN' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "sidecar alarm_channel_ok is false"       "$(grep -q '\"alarm_channel_ok\": false' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "telegram gateway never invoked (no creds -> no curl attempt)" \
                                                 "$([ ! -s "$TMP/calls/telegram.calls" ] && echo 0 || echo 1)"
check "log carries ALERT-CHANNEL-DOWN"          "$(grep -q 'ALERT-CHANNEL-DOWN' "$LOGFILE" && echo 0 || echo 1)"
check "no cooldown armed (must retry next run)" "$([ ! -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"

echo "GUILT 2 — probe failing 2x + alarm channel armed => alert actually attempted and delivered"
reset_env
export TELEGRAM_BOT_TOKEN="fake-bot-token"
export TELEGRAM_CHAT_ID="12345"
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false FAKE_TG_RC=0 run_case
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false FAKE_TG_RC=0 run_case
check "exit code 2 (alert delivered)"           "$([ "$RC" = "2" ] && echo 0 || echo 1)"
check "telegram gateway WAS invoked"            "$([ -s "$TMP/calls/telegram.calls" ] && echo 0 || echo 1)"
check "log carries ALERT: login_fail (delivered)" "$(grep -q 'ALERT: login_fail' "$LOGFILE" && echo 0 || echo 1)"
check "sidecar keeps the login-failure text (not the alarm-channel one)" \
    "$(grep -q 'login probe failed' "$SIDECAR" 2>/dev/null && ! grep -q 'ALARM-CHANNEL-DOWN' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "cooldown IS armed on successful delivery" "$([ -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

echo "INNOCENCE 1 — probe healthy => exit 0, no alert, ever"
reset_env
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
FAKE_LOGIN_HTTP_CODE=200 FAKE_LOGIN_HAS_TOKEN=true run_case
check "exit 0 on first healthy run"             "$([ "$RC" = "0" ] && echo 0 || echo 1)"
FAKE_LOGIN_HTTP_CODE=200 FAKE_LOGIN_HAS_TOKEN=true run_case
check "exit 0 on second healthy run"            "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "no telegram call across 2 healthy runs"  "$([ ! -s "$TMP/calls/telegram.calls" ] && echo 0 || echo 1)"

echo "INNOCENCE 2 — --selftest with a working fake gateway => exit 0, no state files touched"
reset_env
export TELEGRAM_BOT_TOKEN="fake-bot-token"
export TELEGRAM_CHAT_ID="12345"
FAKE_TG_RC=0 run_case --selftest
check "selftest exit 0"                         "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "telegram gateway called during selftest" "$([ -s "$TMP/calls/telegram.calls" ] && echo 0 || echo 1)"
check "selftest never writes legacy state file" "$([ ! -f "$STATEFILE" ] && echo 0 || echo 1)"
check "selftest never writes the Genoma sidecar" "$([ ! -f "$SIDECAR" ] && echo 0 || echo 1)"
check "selftest never writes/arms the cooldown"  "$([ ! -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

echo "GUILT 3 — --selftest with a broken gateway (no creds) => non-zero exit, still touches nothing"
reset_env
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID
run_case --selftest
check "selftest with dead channel exits non-zero" "$([ "$RC" != "0" ] && echo 0 || echo 1)"
check "still no state file written"             "$([ ! -f "$STATEFILE" ] && echo 0 || echo 1)"
check "still no sidecar written"                "$([ ! -f "$SIDECAR" ] && echo 0 || echo 1)"

echo "extra — a lone first failure (not yet 2 consecutive) must not alert (2-consecutive rule preserved)"
reset_env
export TELEGRAM_BOT_TOKEN="fake-bot-token"
export TELEGRAM_CHAT_ID="12345"
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
check "exit 1 on lone first failure"            "$([ "$RC" = "1" ] && echo 0 || echo 1)"
check "no telegram call on lone first failure"  "$([ ! -s "$TMP/calls/telegram.calls" ] && echo 0 || echo 1)"
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

echo "extra — armed cooldown still suppresses a repeat alert (existing 2h behaviour preserved)"
reset_env
export TELEGRAM_BOT_TOKEN="fake-bot-token"
export TELEGRAM_CHAT_ID="12345"
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run1: ok->fail, no alert due
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run2: fail->fail, alert delivered, cooldown armed
check "run2 exit 2 (delivered)"                 "$([ "$RC" = "2" ] && echo 0 || echo 1)"
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run3: still failing, cooldown active
check "run3 exit 1 (in cooldown, not re-alerted, not channel-down)" "$([ "$RC" = "1" ] && echo 0 || echo 1)"
tg_calls="$(wc -l < "$TMP/calls/telegram.calls" 2>/dev/null | tr -d ' ')"
check "telegram called exactly once across 3 runs (cooldown holds)" "$([ "$tg_calls" = "1" ] && echo 0 || echo 1)"
unset TELEGRAM_BOT_TOKEN TELEGRAM_CHAT_ID

echo
printf 'login-healthcheck alert corpus: %d ok, %d FAIL\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
