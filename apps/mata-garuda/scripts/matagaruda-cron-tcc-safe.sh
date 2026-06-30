#!/bin/zsh
# Mata Garuda generic cron wrapper — TCC-safe (W19+W20 pattern)
# Usage: matagaruda-cron-tcc-safe.sh <entry_script_path> [log_label]
#
# Eliminates the /bin/bash -lc + source .venv/bin/activate failure that
# launchd TCC sandbox produced as false-noise in .error.log for at
# least kg-linker + wr-topic crons (W20 cicatrix 2026-05-22).
#
# Reusable: caller passes entry script. Wrapper does no business logic.

set -e
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

if [ $# -lt 1 ]; then
    echo "[ERROR] usage: $0 <entry_script_abs_path> [log_label]" >&2
    exit 2
fi

ENTRY="$1"
LABEL="${2:-$(basename "$ENTRY" .py)}"

# Path-aware: derive repo root from THIS script's location
# (<repo>/apps/mata-garuda/scripts/matagaruda-cron-tcc-safe.sh).
SCRIPT_DIR="${0:A:h}"            # zsh: absolute dir of this script
REPO_ROOT="${REPO_ROOT:-${SCRIPT_DIR:h:h:h}}"   # up 3: scripts→mata-garuda→apps→repo
APP_ROOT="$REPO_ROOT/apps/mata-garuda"
VENV_PY="$APP_ROOT/.venv/bin/python"

if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    . "$HOME/.nuzantara-secrets.env"
    set +a
fi

# Canonical Redis = Pro (127.0.0.1). Was 100.93.236.6 (Mini) → caused
# the live split-brain: 10 crons read Mini while monitor/archiver/rollup
# read Pro, and 982 alerts sat unsent. Fixed canonical to Pro 2026-06-30.
export GARUDA_REDIS_HOST="${GARUDA_REDIS_HOST:-127.0.0.1}"  # canonical=Pro (Zero 2026-06-30, Stage1)
export PYTHONPATH="${PYTHONPATH:-$APP_ROOT}"

[ -x "$VENV_PY" ] || { echo "[ERROR] venv python missing: $VENV_PY" >&2; exit 2; }
[ -f "$ENTRY" ] || { echo "[ERROR] entry script missing: $ENTRY" >&2; exit 2; }

cd "$APP_ROOT"
# W21 fix: do NOT redirect stdout/stderr — let launchd's StandardOutPath
# and StandardErrorPath capture them separately. The W19+W20 version
# redirected to ~/logs/matagaruda-${LABEL}.log which merged stdout+stderr
# into one file, defeating the W8 signal/noise separation purpose.
# Python -u flag forces unbuffered output for real-time log visibility.
exec "$VENV_PY" -u "$ENTRY"
