#!/bin/zsh
# Mata Garuda NLM Feeder Stream — Hourly cron wrapper
# Invoked by com.matagaruda.nlm-feeder-stream.hourly.plist.
#
# W19 cicatrix 2026-05-22: previous plist used /bin/zsh -lc with `cd ...
# && source ~/.nuzantara-secrets.env; .venv/bin/python ...` inline. The
# `-l` flag sources .zshrc which contains commands that try to `pwd`
# parent dirs. Under launchd's sandbox, parent dirs of ~/Desktop/...
# return EPERM → 842 lines of "shell-init: error retrieving current
# directory: getcwd: cannot access parent directories" noise in
# .error.log over ~3 weeks of hourly runs. 100% noise, zero signal.
#
# W19 fix: TCC-safe wrapper (W7+W17 pattern) — venv python direct, no
# zsh -l, .nuzantara-secrets.env sourced explicitly.
#
# Exit semantics: bubbles up Python exit code unchanged.

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Self-locating: APP_ROOT is this script's grandparent dir
# (<repo>/apps/mata-garuda/scripts/<this>.sh → :h:h). REPO_ROOT still overridable.
# (cicatrix #1: no hardcoded HOME-fork path.)
APP_ROOT="${0:A:h:h}"
REPO_ROOT="${REPO_ROOT:-${APP_ROOT:h:h}}"
VENV_PY="$APP_ROOT/.venv/bin/python"
ENTRY="$APP_ROOT/scripts/run_nlm_feeder_stream.py"
LOG="$HOME/logs/matagaruda-nlm-feeder-stream.log"

mkdir -p "$HOME/logs"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Redis host selection — Mythos-P3 (2026-06-14).
# The 2026-05-06 split-brain fix pinned this feeder at Mini
# (GARUDA_REDIS_HOST=100.93.236.6, also set in the plist). But the
# producers (scorer/classifier/ner) write to Pro LOCALHOST and Mini is
# currently DOWN — so the feeder consumed an unreachable redis and the
# redis-cli timeout was swallowed as "0 new items" → 33-day silent
# starvation while 3144 items piled up on localhost.
# Honour a REACHABLE configured host; otherwise fall back to 127.0.0.1
# (where the producers actually write). The plist override is now a
# stale config — P2 should drop GARUDA_REDIS_HOST from the plist so it
# defaults to localhost like the producers.
_cfg_host="${GARUDA_REDIS_HOST:-127.0.0.1}"
if [ "$_cfg_host" != "127.0.0.1" ] && [ "$_cfg_host" != "localhost" ]; then
    if ! redis-cli -h "$_cfg_host" -p "${GARUDA_REDIS_PORT:-6379}" -t 4 ping >/dev/null 2>&1; then
        echo "[nlm-feeder-stream] WARN: configured redis $_cfg_host unreachable — falling back to 127.0.0.1 (producers' redis)" >&2
        _cfg_host="127.0.0.1"
    fi
fi
export GARUDA_REDIS_HOST="$_cfg_host"

if [ ! -x "$VENV_PY" ]; then
    echo "[ERROR] venv python not found: $VENV_PY" >&2
    exit 2
fi
if [ ! -f "$ENTRY" ]; then
    echo "[ERROR] entry script not found: $ENTRY" >&2
    exit 2
fi

cd "$APP_ROOT"
exec "$VENV_PY" "$ENTRY" >> "$LOG" 2>&1
