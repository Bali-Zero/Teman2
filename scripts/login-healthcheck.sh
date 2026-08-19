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
# Exit codes (hardened 2026-08-19 — see scripts/test_login_healthcheck_alert.sh
# and infra/home-fork/declared-pairs.json):
#   0  - probe healthy (status=ok). Also: --selftest proved the alarm path
#        can deliver.
#   1  - probe failed, but no alert was due this run (first of a 2-consecutive
#        pair, or an already-armed cooldown suppressed a repeat) — routine.
#   2  - probe failed, a 2-consecutive alert was due AND was delivered
#        ("I told someone").
#   3  - probe failed, a 2-consecutive alert was due but could NOT be
#        delivered — missing Telegram creds, or the curl to Telegram itself
#        failed ("I could not tell anyone"). Strictly louder than 2: a dead
#        alarm channel is worse than a live one that already fired, because
#        it silently masks every future failure too. On this path the
#        cooldown is deliberately NOT armed, so the next run (5 min later)
#        retries delivery instead of going quiet for 2h.
#   --selftest (see below) exits 0 if the alarm channel is proven reachable,
#   1 if it is not. It never returns 2 or 3 — those only apply to a probe run.
#
# --selftest: proves the ALARM PATH works without probing the login endpoint
# at all — the answer to "a receptor whose healthy output is silence must be
# able to prove it is not simply mute." Sends a self-test Telegram message
# using the same tg_alert() codepath as a real alert. Does NOT write
# STATE_FILE, COOLDOWN_FILE, or the Genoma sidecar — a selftest run must
# leave no trace in the state this script otherwise maintains.

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
# 2026-08-19: the @Balizerobot fallback (BALIZEROBOT_TOKEN) is deleted, not
# just unused. That bot is decommissioned — its token sat in cleartext on
# this repo's public default branch, it cannot be revoked (BotFather only
# answers the account that created it, which is lost), and its destination
# chat belongs to the same lost account. Any code path that can still reach
# it is a live liability. TELEGRAM_CHAT_ID keeps its own fallback below —
# TELEGRAM_ADMIN_CHAT_ID is not the dead bot's chat.
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-${TELEGRAM_ADMIN_CHAT_ID:-}}"

mkdir -p "$(dirname "$STATE_FILE")" "$(dirname "$LOG_FILE")"

log() { echo "[$(date '+%Y-%m-%dT%H:%M:%S%z')] $*" | tee -a "$LOG_FILE"; }

# tg_alert: return codes distinguish WHY delivery didn't happen, so the
# caller can tell "unarmed" from "armed but the POST itself failed" —
# both are "I could not tell anyone", but knowing which is faster to fix.
#   0 = delivered · 1 = missing creds (channel unarmed) · 2 = curl/API failed
tg_alert() {
    local text="$1"
    if [[ -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID" ]]; then
        log "telegram: missing creds"
        return 1
    fi
    if ! curl -sS -m 10 -X POST \
        "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
        -d "chat_id=${TELEGRAM_CHAT_ID}" \
        -d "text=${text}" \
        -d "parse_mode=HTML" >/dev/null; then
        log "telegram: post failed"
        return 2
    fi
    return 0
}

if [[ "$SELFTEST" -eq 1 ]]; then
    log "=== login-healthcheck --selftest start ==="
    if tg_alert "🔧 <b>login-healthcheck --selftest</b>%0Aalarm channel self-test — if you see this, Telegram delivery works."; then
        log "=== login-healthcheck --selftest end (alarm channel OK) ==="
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
# could not deliver it — the loudest condition this script can report.
# alert_delivered (set) means: an alert was due and WAS delivered.
# Neither set + current_status=fail means: no alert was due this run
# (first of a 2-consecutive pair, or an armed cooldown suppressed it).
alert_channel_down=""
alert_delivered=""
if [[ "$current_status" == "fail" && "$prev_status" == "fail" ]]; then
    if ! cooldown_active "login_fail"; then
        alert_msg="🔐 <b>kita.balizero.com login probe failed</b> (2 consecutive)%0Aprobe: POST $LOGIN_URL%0Ahttp_code: <code>$http_code</code>%0Ahas_token: $has_token%0Aaccount: $HEALTHCHECK_EMAIL"
        if tg_alert "$alert_msg"; then
            alert_delivered=1
            cooldown_set "login_fail"
            log "ALERT: login_fail (delivered)"
        else
            tg_rc=$?
            if [[ "$tg_rc" -eq 1 ]]; then
                alert_channel_down="telegram creds not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID unset)"
            else
                alert_channel_down="telegram POST failed (network/API error, rc=$tg_rc)"
            fi
            # Deliberately do NOT cooldown_set here: the cooldown exists to
            # avoid re-spamming a channel that already heard us, not to go
            # quiet for 2h while the channel itself is broken. Next run (5
            # min later) retries delivery.
            log "ALERT-CHANNEL-DOWN: login_fail alert could NOT be delivered ($alert_channel_down) — cooldown NOT set, will retry next run"
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
        f"ALARM-CHANNEL-DOWN: {alert_channel_down} -- could not deliver alert "
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
