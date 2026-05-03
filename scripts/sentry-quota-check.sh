#!/usr/bin/env bash
#
# sentry-quota-check.sh — guard against burning the Sentry free-tier quota.
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
#   0  OK
#   1  quota-risk config detected (traces_sample_rate > threshold)
#   2  PII bypass detected (SENTRY_SEND_DEFAULT_PII truthy)
#   3  could not read config
#
set -euo pipefail

APP="${SENTRY_QUOTA_APP:-nuzantara-rag}"
MAX_TRACES="${SENTRY_MAX_TRACES_SAMPLE_RATE:-0.02}"
TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"

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

echo "[sentry-quota-check] OK"
