#!/usr/bin/env bash
# launchd_env_loader.sh — boot-time setenv loader for nuzantara secrets.
#
# Problem: launchctl setenv vars do NOT persist across logout/reboot. After
# every reboot Pro, organs that depend on TELEGRAM_BOT_TOKEN (Supervisor,
# liveness watchdog, sentinel, etc.) lose their alert capability silently.
#
# This script runs at boot via com.nuzantara.launchd-env-loader plist
# (RunAtLoad=true, StartInterval=43200 = 12h refresh) and:
#   1. Sources ~/.nuzantara-secrets.env
#   2. Calls launchctl setenv for the env vars enumerated below
#
# Why launchctl setenv (not just export):
#   - launchd-spawned processes inherit env from launchctl, NOT from shell
#   - Setting in shell rc files (.zshrc) only affects interactive sessions
#   - Daemons need explicit launchctl setenv for env propagation
#
# Why an explicit allowlist (not all secrets):
#   - launchd env is global to all spawned processes — narrow exposure
#   - Secrets needed by daemons (Telegram, GH, Telegram chat IDs) only
#   - DB_URL, API_KEYS for Fly stay confined to per-process spawn
#
# Reference:
#   - cicatrix STRUCTURAL P0-3 RECURRENCE PATTERN (2026-05-08 P1)
#   - Issue #541 task 1
#   - Pre-existing pattern: some secrets ARE in plist EnvironmentVariables;
#     this script is the safer alternative (env via setenv, not in plist file).

set -u -o pipefail

LOG_FILE="${LOG_FILE:-$HOME/logs/launchd-env-loader.log}"
mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" >>"$LOG_FILE"; }

SECRETS_FILE="$HOME/.nuzantara-secrets.env"
if [ ! -f "$SECRETS_FILE" ]; then
  log "ERROR: $SECRETS_FILE missing — cannot load env"
  exit 1
fi

# shellcheck disable=SC1091
source "$SECRETS_FILE"

# Allowlist: only env vars actually needed by launchd-spawned organs.
# Add new entries here as needed; do NOT setenv blanket-everything.
ENV_VARS=(
  TELEGRAM_BOT_TOKEN
  TELEGRAM_OWNER_CHAT_ID
  TELEGRAM_ADMIN_CHAT_ID
  TELEGRAM_ZERO_CHAT_ID
)

LOADED=()
SKIPPED=()
for var in "${ENV_VARS[@]}"; do
  val="${!var:-}"
  if [ -z "$val" ]; then
    SKIPPED+=("$var")
    continue
  fi
  launchctl setenv "$var" "$val"
  LOADED+=("$var")
done

log "Loaded env: ${LOADED[*]}"
if [ "${#SKIPPED[@]}" -gt 0 ]; then
  log "Skipped (not in secrets): ${SKIPPED[*]}"
fi
log "Done. Total loaded: ${#LOADED[@]}, skipped: ${#SKIPPED[@]}"
