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
# REVISED same day: the first cut of this hardening hand-rolled a raw curl
# to Telegram, which enrolled a NEW direct sender against
# scripts/lint_tg_direct_senders.py (infra/tg-gateway/grandfathered.json can
# only shrink). The real fix is better than an exception: route through
# scripts/tg_notify.py, the one gateway that already owns fail-visible
# delivery (spool + digest surfacing of an unsendable P0), so this corpus
# now fakes THAT gateway instead of faking curl for the Telegram leg.
#
#   GUILT   — the gateway script cannot be FOUND at all: the loudest exit
#             code (3) AND the sidecar names the channel, not the login
#             failure.
#   GUILT   — the gateway is found but its invocation itself fails (rc!=0):
#             same loud exit (3), but the sidecar's reason text is distinct
#             ("invocation failed", not "not found").
#   GUILT   — probe failing 2x + gateway armed and healthy: the alert is
#             actually HANDED OFF (assert the fake gateway recorded the
#             call with the right --tier/--source/--dedup-key), delivered
#             exit code (2), sidecar keeps the ordinary login-failure text.
#   INNOCENCE — probe healthy: exit 0, no alert attempted, ever.
#   INNOCENCE — --selftest with a working fake gateway: exit 0, uses its OWN
#             source/dedup-key (never collides with a real alert), and
#             never touches STATE_FILE/COOLDOWN_FILE/sidecar.
#   + extras: a lone first failure must not alert (2-consecutive rule
#             preserved); a broken --selftest must exit non-zero and still
#             touch nothing; an armed cooldown must still suppress a repeat
#             alert (existing 2h-cooldown behaviour preserved) while the
#             exit-code split holds around it.
#
# No network: the wrapper runs from a tmp copy. scripts/login-healthcheck.sh
# resolves the gateway sibling-first ("$(dirname "$0")/tg_notify.py"), same
# convention as scripts/cron-runner.sh's alert_failure() — so a fake
# tg_notify.py placed NEXT TO the copied wrapper is found with zero PATH
# tricks. The login *probe* itself still goes through plain curl, so that
# leg is faked the old way: a fake `curl` placed first on $PATH (the script
# never overwrites PATH itself, so shadowing works), now only ever asked
# about kita.balizero.com.
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
    # Only the login probe leg goes through curl now — the Telegram leg is a
    # fake tg_notify.py sibling (see write_fake_gateway).
    cat > "$TMP/bin/curl" <<'STUB'
#!/usr/bin/env bash
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
        echo "fake curl: unrecognized URL in test (only kita.balizero.com expected): $url" >&2
        exit 1
        ;;
esac
STUB
    chmod +x "$TMP/bin/curl"
}

write_fake_gateway () {  # write_fake_gateway <present:0|1>
    if [ "${1:-1}" = "0" ]; then
        rm -f "$TMP/run/tg_notify.py"
        return
    fi
    cat > "$TMP/run/tg_notify.py" <<'STUB'
#!/usr/bin/env python3
import argparse, json, os, sys

ap = argparse.ArgumentParser()
ap.add_argument("--tier")
ap.add_argument("--source", default="unknown")
ap.add_argument("--dedup-key", default="")
ap.add_argument("--selftest", action="store_true")
ap.add_argument("text", nargs="*")
args = ap.parse_args()

calls_dir = os.environ.get("FAKE_CALLS_DIR", ".")
with open(os.path.join(calls_dir, "tg_notify.calls"), "a") as f:
    f.write(json.dumps({
        "tier": args.tier, "source": args.source,
        "dedup_key": args.dedup_key, "text": " ".join(args.text),
    }) + "\n")

status = os.environ.get("FAKE_TG_NOTIFY_STATUS", "sent")
print(f"tg_notify: {status}", file=sys.stderr)
sys.exit(int(os.environ.get("FAKE_TG_NOTIFY_RC", "0")))
STUB
    chmod +x "$TMP/run/tg_notify.py"
}

reset_env () {  # reset_env <gateway-present:0|1, default 1>
    rm -rf "${TMP:?}/run" "${TMP:?}/home" "${TMP:?}/bin" "${TMP:?}/calls"
    mkdir -p "$TMP/run" "$TMP/home" "$TMP/bin" "$TMP/calls"
    cp "$WRAPPER" "$TMP/run/login-healthcheck.sh"
    chmod +x "$TMP/run/login-healthcheck.sh"
    write_fake_curl
    write_fake_gateway "${1:-1}"
}

SIDECAR="$TMP/home/.agent/decisions/state/login_healthcheck.last.json"
STATEFILE="$TMP/home/.agent/decisions/login_healthcheck.json"
COOLDOWNFILE="$TMP/home/.agent/decisions/login_healthcheck.cooldown"
LOGFILE="$TMP/home/logs/login-healthcheck.log"
GWCALLS="$TMP/calls/tg_notify.calls"

run_case () {  # run_case [--selftest]
    HOME="$TMP/home" \
    PATH="$TMP/bin:$PATH" \
    FAKE_CALLS_DIR="$TMP/calls" \
    FAKE_TG_NOTIFY_RC="${FAKE_TG_NOTIFY_RC:-0}" \
    FAKE_TG_NOTIFY_STATUS="${FAKE_TG_NOTIFY_STATUS:-sent}" \
    FAKE_LOGIN_HTTP_CODE="${FAKE_LOGIN_HTTP_CODE:-200}" \
    FAKE_LOGIN_HAS_TOKEN="${FAKE_LOGIN_HAS_TOKEN:-true}" \
    HEALTHCHECK_EMAIL="healthcheck@balizero.com" \
    HEALTHCHECK_PIN="000000" \
        bash "$TMP/run/login-healthcheck.sh" "$@" >"$TMP/stdout.log" 2>"$TMP/stderr.log"
    RC=$?
}

echo "GUILT 1 — gateway script not found at all => loudest exit + sidecar names it"
reset_env 0   # no tg_notify.py sibling
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # 1st failure: no alert due yet
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # 2nd: alert due, gateway missing
check "exit code 3 (alarm channel down)"        "$([ "$RC" = "3" ] && echo 0 || echo 1)"
check "sidecar names ALARM-CHANNEL-DOWN"        "$(grep -q 'ALARM-CHANNEL-DOWN' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "sidecar reason says gateway not found"   "$(grep -q 'gateway script not found' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "sidecar alarm_channel_ok is false"       "$(grep -q '\"alarm_channel_ok\": false' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "log carries ALERT-CHANNEL-DOWN"          "$(grep -q 'ALERT-CHANNEL-DOWN' "$LOGFILE" && echo 0 || echo 1)"
check "no cooldown armed (must retry next run)" "$([ ! -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"

echo "GUILT 2 — gateway found but its invocation itself fails => loud exit, distinct reason"
reset_env 1
FAKE_TG_NOTIFY_RC=9 FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
FAKE_TG_NOTIFY_RC=9 FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
check "exit code 3 (alarm channel down)"          "$([ "$RC" = "3" ] && echo 0 || echo 1)"
check "sidecar reason says invocation failed (rc=9)" "$(grep -q 'invocation failed (rc=9)' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "gateway WAS invoked (it just failed)"      "$([ -s "$GWCALLS" ] && echo 0 || echo 1)"
check "no cooldown armed"                         "$([ ! -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"

echo "GUILT 3 — probe failing 2x + gateway armed and healthy => actually handed off"
reset_env 1
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
check "exit code 2 (handed off)"                "$([ "$RC" = "2" ] && echo 0 || echo 1)"
check "gateway WAS invoked"                     "$([ -s "$GWCALLS" ] && echo 0 || echo 1)"
check "gateway called with --tier p0"           "$(grep -q '\"tier\": \"p0\"' "$GWCALLS" && echo 0 || echo 1)"
check "gateway called with the real-alert source/key" \
    "$(grep -q '\"source\": \"login-healthcheck\"' "$GWCALLS" && grep -q '\"dedup_key\": \"login-healthcheck:probe-down\"' "$GWCALLS" && echo 0 || echo 1)"
check "log carries ALERT: login_fail (handed to gateway)" "$(grep -q 'ALERT: login_fail' "$LOGFILE" && echo 0 || echo 1)"
check "sidecar keeps the login-failure text (not the alarm-channel one)" \
    "$(grep -q 'login probe failed' "$SIDECAR" 2>/dev/null && ! grep -q 'ALARM-CHANNEL-DOWN' "$SIDECAR" 2>/dev/null && echo 0 || echo 1)"
check "cooldown IS armed on a successful hand-off" "$([ -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"

echo "INNOCENCE 1 — probe healthy => exit 0, no alert, ever"
reset_env 1
FAKE_LOGIN_HTTP_CODE=200 FAKE_LOGIN_HAS_TOKEN=true run_case
check "exit 0 on first healthy run"             "$([ "$RC" = "0" ] && echo 0 || echo 1)"
FAKE_LOGIN_HTTP_CODE=200 FAKE_LOGIN_HAS_TOKEN=true run_case
check "exit 0 on second healthy run"            "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "no gateway call across 2 healthy runs"   "$([ ! -s "$GWCALLS" ] && echo 0 || echo 1)"

echo "INNOCENCE 2 — --selftest with a working fake gateway => exit 0, own source/key, no state files touched"
reset_env 1
run_case --selftest
check "selftest exit 0"                         "$([ "$RC" = "0" ] && echo 0 || echo 1)"
check "gateway called during selftest"          "$([ -s "$GWCALLS" ] && echo 0 || echo 1)"
check "selftest uses its OWN source/dedup-key (never the real alert's)" \
    "$(grep -q '\"source\": \"login-healthcheck-selftest\"' "$GWCALLS" && grep -q '\"dedup_key\": \"login-healthcheck:selftest\"' "$GWCALLS" && echo 0 || echo 1)"
check "selftest never writes legacy state file" "$([ ! -f "$STATEFILE" ] && echo 0 || echo 1)"
check "selftest never writes the Genoma sidecar" "$([ ! -f "$SIDECAR" ] && echo 0 || echo 1)"
check "selftest never writes/arms the cooldown"  "$([ ! -f "$COOLDOWNFILE" ] && echo 0 || echo 1)"

echo "GUILT 4 — --selftest with no gateway at all => non-zero exit, still touches nothing"
reset_env 0
run_case --selftest
check "selftest with dead gateway exits non-zero" "$([ "$RC" != "0" ] && echo 0 || echo 1)"
check "still no state file written"             "$([ ! -f "$STATEFILE" ] && echo 0 || echo 1)"
check "still no sidecar written"                "$([ ! -f "$SIDECAR" ] && echo 0 || echo 1)"

echo "extra — a lone first failure (not yet 2 consecutive) must not alert (2-consecutive rule preserved)"
reset_env 1
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case
check "exit 1 on lone first failure"            "$([ "$RC" = "1" ] && echo 0 || echo 1)"
check "no gateway call on lone first failure"   "$([ ! -s "$GWCALLS" ] && echo 0 || echo 1)"

echo "extra — armed cooldown still suppresses a repeat alert (existing 2h behaviour preserved)"
reset_env 1
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run1: ok->fail, no alert due
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run2: fail->fail, handed off, cooldown armed
check "run2 exit 2 (handed off)"                "$([ "$RC" = "2" ] && echo 0 || echo 1)"
FAKE_LOGIN_HTTP_CODE=401 FAKE_LOGIN_HAS_TOKEN=false run_case   # run3: still failing, cooldown active
check "run3 exit 1 (in cooldown, not re-alerted, not channel-down)" "$([ "$RC" = "1" ] && echo 0 || echo 1)"
gw_calls="$(wc -l < "$GWCALLS" 2>/dev/null | tr -d ' ')"
check "gateway called exactly once across 3 runs (cooldown holds)" "$([ "$gw_calls" = "1" ] && echo 0 || echo 1)"

echo
printf 'login-healthcheck alert corpus: %d ok, %d FAIL\n' "$PASS" "$FAIL"
[ "$FAIL" -eq 0 ] || exit 1
