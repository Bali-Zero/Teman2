#!/usr/bin/env bash
#
# sentry-quota-check.sh — guard against CONFIG that burns the Sentry quota.
#
# It does TWO things, and the second one is the one the name promises:
#
#   A. CONFIG DRIFT (upstream): reads the app's own runtime config via `flyctl ssh`
#      and judges whether it is likely to BURN quota (sample rates, PII flag).
#   B. REAL EXHAUSTION (the actual state): sends one minimal event to the Sentry
#      `store` endpoint using the app's own public DSN and reads the response.
#      Sentry answers HTTP 429 with `x-sentry-rate-limits` naming the reason, e.g.
#      `60:default;error;security;attachment:organization:error_usage_exceeded`.
#
# (B) needs NO authentication — only the DSN, whose `sentry_key` is public by
# design (it ships in the browser bundle). An org-scope API token was tried first
# and is NOT needed: the `sntrys_` build token available returns 403 on every REST
# endpoint (organizations/, projects/, stats_v2/), because it is scoped for
# sourcemap upload, not for reading state.
#
# WHY (B) EXISTS. Until 2026-08-28 this script did only (A) — a config-drift linter
# carrying the name of a detector. The failure it guards against had ALREADY
# happened underneath it: the org-level error bucket was exhausted and Sentry was
# dropping real production errors, while this check ran green every day at 09:00
# WITA. It could not have seen it, by construction, and did not. (B) closes that.
#
# COST, stated because it is a real side effect: (B) sends ONE error event per run
# (~30/month against a 5,000/month tier, 0.6%). When the bucket is already
# exhausted the event is rejected, so it costs nothing in exactly the case that
# matters. Set SENTRY_QUOTA_PROBE=off to disable (B) and keep (A).
#
# The free tier is 5,000 events/month shared across errors AND transactions.
# A traces_sample_rate above ~2% on a real-traffic deploy exhausts the quota
# in days; after that, Sentry silently drops error events too.
#
# This script:
#   1. reads the live config from Fly secrets on `nuzantara-rag`
#   2. alerts Telegram if SENTRY_TRACES_SAMPLE_RATE > 0.02 in production
#      (or if SENTRY_SEND_DEFAULT_PII is enabled, which would bypass the
#      before_send scrubbing contract)
#   3. exits non-zero on violation so cron/CI can fail loud
#
# Intended use:
#   - Run manually:            bash scripts/sentry-quota-check.sh
#   - From cron (Air, daily):  0 9 * * *  bash ~/Projects/nuzantara/scripts/sentry-quota-check.sh
#
# Exit codes:
#   0  config sane AND the error bucket accepted our probe event
#   1  quota-risk config detected (traces_sample_rate > threshold)
#   2  PII bypass detected (SENTRY_SEND_DEFAULT_PII truthy)
#   3  could not read config
#   4  QUOTA EXHAUSTED — Sentry is dropping real errors right now (probe got 429)
#   5  probe inconclusive (network/DSN shape) — explicitly NOT treated as healthy
#
set -euo pipefail

APP="${SENTRY_QUOTA_APP:-nuzantara-rag}"
MAX_TRACES="${SENTRY_MAX_TRACES_SAMPLE_RATE:-0.02}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-8847435604}"

alert() {
    local msg="$1"
    echo "[sentry-quota-check] $msg" >&2
    if [[ -n "$TELEGRAM_BOT_TOKEN" ]]; then
        curl -sS -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d chat_id="$TELEGRAM_CHAT_ID" \
            -d text="⚠️ Sentry quota check ($APP): $msg" \
            -d parse_mode="Markdown" > /dev/null 2>&1 || true
    fi
}

if ! command -v fly >/dev/null 2>&1; then
    echo "[sentry-quota-check] fly CLI not found; skip" >&2
    exit 0
fi

# `fly secrets list` prints NAME only (values are opaque). For value-visibility
# we rely on `fly secrets list --json` and, as fallback, the app's runtime env
# exposed via `fly ssh console --command`.
SECRETS_JSON="$(fly secrets list --app "$APP" --json 2>/dev/null || true)"
if [[ -z "$SECRETS_JSON" ]]; then
    alert "unable to read fly secrets for $APP"
    exit 3
fi

# The env values come from runtime — we read them via fly ssh console with a
# tiny python one-liner so we don't have to parse the Dockerfile.
# Read runtime env via `fly ssh console`. The command emits status banners
# ("No machine specified…", "Connecting to…") before the actual output, so we
# grep only the JSON line. Using a heredoc avoids shell-escaping hell.
RUNTIME_RAW="$(
    fly ssh console --app "$APP" --quiet --command \
        'python -c "import os,json; keys=[\"ENVIRONMENT\",\"SENTRY_TRACES_SAMPLE_RATE\",\"SENTRY_PROFILES_SAMPLE_RATE\",\"SENTRY_SEND_DEFAULT_PII\",\"SKIP_SENTRY_INIT\",\"SENTRY_DSN\"]; print(\"SQC_JSON:\"+json.dumps({k:os.getenv(k,\"\") for k in keys}))"' \
        2>/dev/null || true
)"

RUNTIME_ENV="$(echo "$RUNTIME_RAW" | grep -o 'SQC_JSON:{.*}' | head -1 | sed 's/^SQC_JSON://')"

if [[ -z "$RUNTIME_ENV" ]]; then
    alert "unable to read runtime env from $APP (is a machine running?)"
    exit 3
fi

# Extract the fields we care about.
get() { python3 -c "import json,sys; print(json.loads(sys.stdin.read()).get('$1',''))" <<<"$RUNTIME_ENV"; }

ENV_NAME="$(get ENVIRONMENT)"
TRACES="$(get SENTRY_TRACES_SAMPLE_RATE)"
PROFILES="$(get SENTRY_PROFILES_SAMPLE_RATE)"
SEND_PII="$(get SENTRY_SEND_DEFAULT_PII)"
KILL_SWITCH="$(get SKIP_SENTRY_INIT)"
DSN_PRESENT="$([[ -n "$(get SENTRY_DSN)" ]] && echo yes || echo no)"

echo "[sentry-quota-check] app=$APP env=$ENV_NAME dsn=$DSN_PRESENT traces=${TRACES:-<default>} profiles=${PROFILES:-<default>} send_pii=${SEND_PII:-false} skip=${KILL_SWITCH:-false}"

if [[ -n "$KILL_SWITCH" ]]; then
    echo "[sentry-quota-check] SKIP_SENTRY_INIT set — Sentry disabled, nothing to audit"
    exit 0
fi

if [[ "$DSN_PRESENT" != "yes" ]]; then
    echo "[sentry-quota-check] no SENTRY_DSN — Sentry not active"
    exit 0
fi

# PII bypass check (bash 3.x-compatible lowercase via tr).
SEND_PII_LC="$(printf '%s' "$SEND_PII" | tr '[:upper:]' '[:lower:]')"
case "$SEND_PII_LC" in
    1|true|yes)
        alert "SENTRY_SEND_DEFAULT_PII is truthy — PII scrubbing is bypassed. Unset immediately."
        exit 2
        ;;
esac

# Quota check. Only enforce in production.
if [[ "$ENV_NAME" == "production" ]]; then
    TRACES_VAL="${TRACES:-0.0}"
    # Use python for float comparison (bash can't).
    OVER="$(python3 -c "print(1 if float('$TRACES_VAL') > float('$MAX_TRACES') else 0)" 2>/dev/null || echo 0)"
    if [[ "$OVER" == "1" ]]; then
        alert "SENTRY_TRACES_SAMPLE_RATE=$TRACES_VAL exceeds safe ceiling $MAX_TRACES in production. Quota will burn. Lower or unset the secret."
        exit 1
    fi
fi

# ── (B) the real measurement: is the error bucket accepting events RIGHT NOW? ──
#
# Never prints the DSN or its key. The rate-limit header is a policy string and
# carries no secret, so it is echoed verbatim — it is the whole point.
if [[ "${SENTRY_QUOTA_PROBE:-on}" == "off" ]]; then
    echo "[sentry-quota-check] probe disabled (SENTRY_QUOTA_PROBE=off) — config-only run"
    echo "[sentry-quota-check] OK (config only — quota NOT measured)"
    exit 0
fi

PROBE_DSN="$(get SENTRY_DSN)"
if [[ -z "$PROBE_DSN" ]]; then
    echo "[sentry-quota-check] no DSN in runtime env — cannot probe the bucket"
    alert "sentry-quota-check could not probe: no SENTRY_DSN in $APP runtime env. Quota state is UNKNOWN, not healthy."
    exit 5
fi

# The key is NOT hex — a [0-9a-f]+ parser fails silently here. Measured 2026-08-28.
PROBE_OUT="$(SENTRY_PROBE_DSN="$PROBE_DSN" python3 -c '
import os, re, json, urllib.request, urllib.error
dsn = os.environ["SENTRY_PROBE_DSN"]
m = re.match(r"https://([^@]+)@([^/]+)/([0-9]+)", dsn)
if not m:
    print("SHAPE_UNPARSED"); raise SystemExit(0)
key, host, proj = m.groups()
body = json.dumps({"message": "sentry-quota-check probe", "level": "error", "platform": "other"}).encode()
req = urllib.request.Request(
    f"https://{host}/api/{proj}/store/",
    data=body,
    headers={"Content-Type": "application/json",
             "X-Sentry-Auth": f"Sentry sentry_version=7, sentry_key={key}"},
)
try:
    r = urllib.request.urlopen(req, timeout=20); code, hdrs = r.getcode(), dict(r.headers)
except urllib.error.HTTPError as e:
    code, hdrs = e.code, dict(e.headers)
except Exception as e:
    print("NETERR", type(e).__name__); raise SystemExit(0)
low = {k.lower(): v for k, v in hdrs.items()}
print(code, low.get("x-sentry-rate-limits", ""))
' 2>/dev/null)"

PROBE_CODE="${PROBE_OUT%% *}"
PROBE_LIMITS="${PROBE_OUT#* }"

case "$PROBE_CODE" in
    SHAPE_UNPARSED|NETERR|"")
        echo "[sentry-quota-check] probe inconclusive: ${PROBE_OUT:-no output}"
        alert "sentry-quota-check probe was inconclusive (${PROBE_OUT:-no output}). Quota state is UNKNOWN, not healthy."
        exit 5
        ;;
    429)
        echo "[sentry-quota-check] BUCKET REJECTING: HTTP 429 — $PROBE_LIMITS"
        if [[ "$PROBE_LIMITS" == *"usage_exceeded"* ]]; then
            alert "Sentry QUOTA EXHAUSTED — errors are being DROPPED in production right now. Header: $PROBE_LIMITS"
        else
            alert "Sentry is rate-limiting error events (429). Header: $PROBE_LIMITS"
        fi
        exit 4
        ;;
    200)
        echo "[sentry-quota-check] bucket accepting events (HTTP 200)"
        ;;
    *)
        echo "[sentry-quota-check] probe returned HTTP $PROBE_CODE — treating as inconclusive"
        alert "sentry-quota-check probe returned unexpected HTTP $PROBE_CODE. Quota state is UNKNOWN, not healthy."
        exit 5
        ;;
esac

echo "[sentry-quota-check] OK"
