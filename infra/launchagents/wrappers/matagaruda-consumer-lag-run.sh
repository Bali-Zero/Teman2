#!/bin/zsh
# matagaruda-consumer-lag-run.sh — W84 trampoline wrapper for
# com.matagaruda.consumer-lag.check.
#
# Extracted from the plist (2026-07-14): the canon plist used to exec the
# venv python DIRECTLY with EnvironmentVariables (GARUDA_CANONICAL_REDIS_HOST,
# PYTHONPATH, WorkingDirectory) all pointing under ~/Desktop/nuzantara — so a
# TCC-dead launchd context (scar W84) kills the job with "Operation not
# permitted" before it ever reaches Redis. This wrapper interposes the W84
# fail-fast probe / ssh-localhost trampoline BEFORE any ~/Desktop access, and
# re-sets the env the plist used to carry (lost across the ssh re-exec — see
# lib/trampoline.sh's caveat).
#
# Repointed in canon because com.matagaruda.* plists are resurrected from
# canon by the plist-watchdog.hourly job — a HOME-only fix here would be
# clobbered on the next watchdog tick.
LOG="$HOME/logs/matagaruda-consumer-lag.log"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    source "$HOME/.nuzantara-secrets.env"
    set +a
fi

TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG"
fi

REPO="${REPO_ROOT:-$HOME/Desktop/nuzantara}"

# Env the plist's EnvironmentVariables dict used to set — NOT inherited
# across the ssh-localhost re-exec (lib/trampoline.sh caveat), so it must be
# (re)set here regardless of which path (direct or trampolined) got us here.
export GARUDA_CANONICAL_REDIS_HOST="${GARUDA_CANONICAL_REDIS_HOST:-127.0.0.1}"
export PYTHONPATH="$REPO/apps/mata-garuda"

cd "$REPO/apps/mata-garuda"
exec "$REPO/apps/mata-garuda/.venv/bin/python" -u scripts/check_consumer_lag.py
