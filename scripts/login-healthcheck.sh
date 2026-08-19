#!/usr/bin/env bash
# login-healthcheck: probe end-to-end login flow for kita.balizero.com.
#
# Why this exists: during the 2026-04-29 incident the backend /health was 200
# while /api/auth/login was 500. We learned that the metric users care about
# is "can I log in", not "does /health respond". This probe tests login
# *end-to-end* through the Vercel proxy, the same path a user takes.
#
# Run from cron every 5-15 min. Alerts to Telegram if 2 consecutive failures.
# Uses the dedicated healthcheck@balizero.com account (role=client, lowest
# privilege) — credentials in ~/.nuzantara-secrets.env.
#
# Alerts are routed through scripts/tg_notify.py — the ONE gateway every
# Telegram notification in this repo must use (infra/tg-gateway/
# grandfathered.json is an anti-regrowth lint, scripts/lint_tg_direct_senders.py:
# a NEW file that calls the Telegram Bot HTTP API directly fails CI). This
# script never talks to Telegram itself and never reads
# TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID — the gateway resolves its own
# credentials.
#
# Exit codes (hardened 2026-08-19, revised same day after routing through
# tg_notify.py — see scripts/test_login_healthcheck_alert.sh and
# infra/home-fork/declared-pairs.json):
#   0  - probe healthy (status=ok). Also: --selftest proved the gateway is
#        reachable.
#   1  - probe failed, but no alert was due this run (first of a 2-consecutive
#        pair, or an already-armed cooldown suppressed a repeat) — routine.
#   2  - probe failed, a 2-consecutive alert was due AND was HANDED OFF to
#        the gateway successfully.
#   3  - probe failed, a 2-consecutive alert was due but could NOT be handed
#        to the gateway at all — the gateway script was not found, or the
#        invocation itself failed (interpreter missing/broken, non-zero
#        exit). ("I could not tell anyone.") Strictly louder than 2: a dead
#        alarm channel is worse than a live one, because it silently masks
#        every future failure too. On this path the cooldown is deliberately
#        NOT armed, so the next run (5 min later) retries instead of going
#        quiet for 2h.
#   --selftest (see below) exits 0 if the gateway is reachable, 1 if not. It
#   never returns 2 or 3 — those only apply to a probe run.
#
# HONESTY NOTE on what exit 2 does and does NOT prove (2026-08-19): tg_notify.py
# is designed to NEVER fail its caller — an unsendable P0 is spooled as
# p0_unsent and surfaces on the next digest, and a duplicate condition is
# deduped by design. Its own exit code is therefore always 0 once it runs,
# and cannot tell us whether a message actually reached Telegram THIS run.
# Exit 2 means "the gateway ran and accepted the notification" — sent,
# deduped, or spooled are ALL fail-visible outcomes per the gateway's own
# contract (see its header) — it does NOT mean "delivered to Telegram this
# instant". This script has no way to prove that anymore, and does not
# pretend to. Exit 3 is the one state genuinely worse than that: nothing ran
# at all, so nothing could even be spooled.
#
# --selftest: proves the gateway is reachable without probing the login
# endpoint at all — the answer to "a receptor whose healthy output is
# silence must be able to prove it is not simply mute." Hands a self-test
# message to the same tg_alert() codepath as a real alert, tagged with its
# own source/dedup-key so it never collides with a real alert's dedup state.
# Does NOT write STATE_FILE, COOLDOWN_FILE, or the Genoma sidecar — a
# selftest run must leave no trace in the state this script otherwise
# maintains (it DOES reach the gateway's own spool, same as a real alert
# would — that is the thing being proven).

set -uo pipefail

SELFTEST=0
if [[ "${1:-}" == "--selftest" ]]; then
    SELFTEST=1
fi

LOGIN_URL="https://kita.balizero.com/api/auth/login"
TIMEOUT_SECONDS=15
STATE_FILE="$HOME/.agent/decisions/login_healthcheck.json"
LOG_FILE="$HOME/logs/login-healthcheck.log"
COOLDOWN_FILE="$HOME/.agent/decisions/login_healthcheck.cooldown"
COOLDOWN_SECONDS=$((60 * 60 * 2))

if [[ -f "$HOME/.nuzantara-secrets.env" ]]; then
    set -a
    # shellcheck disable=SC1090
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*" | tee -a "$LOG_FILE"; }

# tg_alert: hand off to scripts/tg_notify.py, resolved sibling-first (same
# convention as scripts/cron-runner.sh's alert_failure()) so this works both
# from the live $HOME/scripts/ copy and from a repo checkout, with a
# repo-anchored fallback for the odd case where the sibling is missing.
# Interpreter is an ABSOLUTE path (/usr/bin/python3), not `python3` resolved
# from PATH — an alarm that runs on the interpreter whose corruption is
# among the things it might need to report shares the failure mode of the
# thing it reports (scar W108).
#
# Return codes (see the HONESTY NOTE above for what these do/don't prove):
#   0 = the gateway ran and accepted the notification
#   1 = the gateway script could not be FOUND
#   2 = the gateway was found but the invocation itself failed to run
tg_alert() {  # tg_alert <text> [source] [dedup_key]
    local text="$1"
    local source="${2:-login-healthcheck}"
    local dedup_key="${3:-login-healthcheck:probe-down}"
    local gateway
    gateway="$(dirname -- "$0")/tg_notify.py"
    if [[ ! -f "$gateway" ]]; then
        gateway="$HOME/nuzantara/scripts/tg_notify.py"
    fi
    if [[ ! -f "$gateway" ]]; then
        log "tg gateway not found (checked sibling dir and \$HOME/nuzantara/scripts/)"
        return 1
    fi
    local out rc
    out="$(/usr/bin/python3 "$gateway" \
        --tier p0 \
        --source "$source" \
        --dedup-key "$dedup_key" \
        -- "$text" 2>&1 >/dev/null)"
    rc=$?
    if [[ "$rc" -ne 0 ]]; then
        log "tg gateway invocation failed (rc=$rc): ${out:0:200}"
        # `return` only carries tg_alert's OWN 1/2 signal (see doc comment
        # above) — stash the gateway's real exit code so the caller's
        # sidecar/log message can name it instead of the generic 2.
        TG_ALERT_GATEWAY_RC="$rc"
        return 2
    fi
    local status
    status="$(printf '%s\n' "$out" | grep -o 'tg_notify: [a-z_]*' | tail -1)"
    log "tg gateway ran (${status:-no status line captured})"
    return 0
}

if [[ "$SELFTEST" -eq 1 ]]; then
    log "=== login-healthcheck --selftest start ==="
    selftest_msg="🔧 login-healthcheck --selftest
alarm channel self-test — if you see this arrive (or land in the tg_notify
spool/digest), the gateway path works."
    if tg_alert "$selftest_msg" "login-healthcheck-selftest" "login-healthcheck:selftest"; then
        log "=== login-healthcheck --selftest end (gateway reachable) ==="
        exit 0
    fi
    tg_rc=$?
    log "=== login-healthcheck --selftest end (ALARM CHANNEL DOWN, tg_alert rc=$tg_rc) ==="
    exit 1
fi

if [[ -z "${HEALTHCHECK_EMAIL:-}" || -z "${HEALTHCHECK_PIN:-}" ]]; then
    log "FATAL: HEALTHCHECK_EMAIL or HEALTHCHECK_PIN not set in ~/.nuzantara-secrets.env"
    exit 78
fi

cooldown_active() {
    local key="$1"
    [[ ! -f "$COOLDOWN_FILE" ]] && return 1
    local last
    last=$(grep "^$key:" "$COOLDOWN_FILE" 2>/dev/null | tail -1 | cut -d: -f2)
    [[ -z "$last" ]] && return 1
    local now=$(date +%s)
    (( now - last < COOLDOWN_SECONDS ))
}

cooldown_set() {
    local key="$1"
    touch "$COOLDOWN_FILE"
    grep -v "^$key:" "$COOLDOWN_FILE" > "$COOLDOWN_FILE.tmp" 2>/dev/null || true
    echo "$key:$(date +%s)" >> "$COOLDOWN_FILE.tmp"
    mv "$COOLDOWN_FILE.tmp" "$COOLDOWN_FILE"
}

prev_status="ok"
if [[ -f "$STATE_FILE" ]]; then
    prev_status=$(python3 -c '
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("status", "ok"))
except Exception:
    print("ok")
' "$STATE_FILE" 2>/dev/null || echo ok)
fi

log "=== login-healthcheck start (prev=$prev_status) ==="

# Build request body without exposing secrets in process listings:
# write to a temp file with strict permissions, hand to curl, delete.
body_file=$(mktemp)
chmod 600 "$body_file"
trap "rm -f '$body_file'" EXIT
python3 -c '
import json, os, sys
json.dump(
    {"email": os.environ["HEALTHCHECK_EMAIL"], "pin": os.environ["HEALTHCHECK_PIN"]},
    open(sys.argv[1], "w"),
)
' "$body_file"

# Probe — capture status code + timing + check token presence in response.
http_code=$(curl -sS -m "$TIMEOUT_SECONDS" \
    -o /tmp/login-healthcheck.body \
    -w "%{http_code}" \
    -X POST \
    -H "Content-Type: application/json" \
    --data-binary "@$body_file" \
    "$LOGIN_URL" 2>/dev/null) || http_code="000"

# Did the response contain a JWT? (redacted from logs.)
has_token="false"
if [[ -f /tmp/login-healthcheck.body ]]; then
    if grep -q '"token"' /tmp/login-healthcheck.body 2>/dev/null; then
        has_token="true"
    fi
    rm -f /tmp/login-healthcheck.body
fi

current_status="ok"
if [[ "$http_code" != "200" || "$has_token" != "true" ]]; then
    current_status="fail"
fi

log "result: http=$http_code has_token=$has_token status=$current_status"

# alert_channel_down (set) means: an alert was DUE this run and tg_alert
# could not hand it to the gateway at all — the loudest condition this
# script can report. alert_delivered (set) means: an alert was due and WAS
# handed off successfully (see the HONESTY NOTE above for what that does and
# does not prove). Neither set + current_status=fail means: no alert was due
# this run (first of a 2-consecutive pair, or an armed cooldown suppressed it).
alert_channel_down=""
alert_delivered=""
if [[ "$current_status" == "fail" && "$prev_status" == "fail" ]]; then
    if ! cooldown_active "login_fail"; then
        alert_msg="🔐 kita.balizero.com login probe failed (2 consecutive)
probe: POST $LOGIN_URL
http_code: $http_code
has_token: $has_token
account: $HEALTHCHECK_EMAIL"
        if tg_alert "$alert_msg"; then
            alert_delivered=1
            cooldown_set "login_fail"
            log "ALERT: login_fail (handed to tg gateway)"
        else
            tg_rc=$?
            if [[ "$tg_rc" -eq 1 ]]; then
                alert_channel_down="tg_notify.py gateway script not found"
            else
                alert_channel_down="tg_notify.py gateway invocation failed (rc=${TG_ALERT_GATEWAY_RC:-$tg_rc})"
            fi
            # Deliberately do NOT cooldown_set here: the cooldown exists to
            # avoid re-spamming a channel that already heard us, not to go
            # quiet for 2h while the channel itself is unreachable. Next run
            # (5 min later) retries.
            log "ALERT-CHANNEL-DOWN: login_fail alert could NOT be handed to the gateway ($alert_channel_down) — cooldown NOT set, will retry next run"
        fi
    else
        log "login_fail in cooldown"
    fi
fi

python3 - "$STATE_FILE" "$current_status" "$http_code" <<EOF
import json, sys, time
with open(sys.argv[1], "w") as f:
    json.dump({
        "status": sys.argv[2],
        "last_http_code": sys.argv[3],
        "ts": time.time(),
    }, f, indent=2)
EOF

# Genoma sidecar (B2 fix 2026-04-30): organism genome.yaml declares a
# bridge_source for pro.login_healthcheck pointing at
# ~/.agent/decisions/state/login_healthcheck.last.json. The legacy state file
# above lives at ~/.agent/decisions/login_healthcheck.json and is consumed
# by the existing 2-strikes-then-Telegram logic. We additionally emit the
# Genoma sidecar so cell.sensors.bridge_state_reader can compute virtual
# heartbeat without modifying this script's existing state contract.
SIDECAR_DIR="$HOME/.agent/decisions/state"
mkdir -p "$SIDECAR_DIR"
# M1 (2026-07-20): include last_error on failure — sentinel's classifier reads
# this field; without it every blip escalated as "UNKNOWN / (no exit summary)".
# 2026-08-19: when the alarm channel itself is down, last_error now names
# THAT fact (prefixed ALARM-CHANNEL-DOWN) instead of the generic login
# failure — otherwise a dead alarm and a dead login look identical to
# anything reading this field. alarm_channel_ok is a new key (added, not a
# rename) so nothing reading the existing keys breaks.
python3 - "$SIDECAR_DIR/login_healthcheck.last.json" "$current_status" "$http_code" "$has_token" "$alert_channel_down" <<EOF
import json, sys, time
status, http_code, has_token, alert_channel_down = sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
payload = {"ts": time.time(), "status": status, "http_code": http_code}
if alert_channel_down:
    payload["last_error"] = (
        f"ALARM-CHANNEL-DOWN: {alert_channel_down} -- could not hand off alert "
        f"for repeated login-probe failure (http={http_code} has_token={has_token})"
    )
    payload["alarm_channel_ok"] = False
elif status != "ok":
    payload["last_error"] = (
        f"login probe failed: http={http_code} has_token={has_token} "
        f"(POST https://kita.balizero.com/api/auth/login via Vercel edge, timeout 15s)"
    )
with open(sys.argv[1], "w") as f:
    json.dump(payload, f)
EOF

exit_code=0
if [[ "$current_status" != "ok" ]]; then
    if [[ -n "$alert_channel_down" ]]; then
        exit_code=3
    elif [[ -n "$alert_delivered" ]]; then
        exit_code=2
    else
        exit_code=1
    fi
fi

log "=== login-healthcheck end (status=$current_status, exit=$exit_code) ==="
exit "$exit_code"
