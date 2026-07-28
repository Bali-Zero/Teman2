#!/usr/bin/env bash
# NB-1 Daily Bundle Refresh — cron wrapper (ARCH-1 + ARCH-8)
# Schedule: daily 04:30 WITA (20:30 UTC prev day)
# Cron: 30 20 * * *
#
# Loads secrets, calls nlm_nb1_daily_refresh.py (which takes ARCH-8 snapshot
# before upload and fires Telegram alert if source count > threshold).

# Shared alarm gateway — see _alert.sh for what the old inline curl hid.
. "$(cd "$(dirname "$0")" && pwd)/_alert.sh" 2>/dev/null || true
# A missing helper must not turn "no alarm" into "the wrapper dies while
# handling a failure": fall back to a LOUD no-op, never a silent one.
command -v alert >/dev/null 2>&1 || alert() {
    echo "ALERT NOT SENT — _alert.sh missing [$1]: ${*:2}" >&2
    return 1
}

set -euo pipefail

# Derived from this script's own location, like every sibling in this directory.
# It was hardcoded to /Users/nuzantara/nuzantara — the same path on Pro, but dead
# on M5 (user `balizero`) and dead again the next time the repo moves, which it
# already did once (~/Desktop -> ~/ on 2026-07-16). A wrapper that cannot run
# outside one machine also cannot be exercised in a test.
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
# PYTHON stays pinned to the pyenv interpreter on purpose: this job's deps are
# installed there, not in the repo venv. Left as-is, not tidied.
PYTHON="/Users/nuzantara/.pyenv/versions/3.11.11/bin/python3"
SCRIPT="$PROJECT_ROOT/scripts/nlm_nb1_daily_refresh.py"

# The secrets file is sourced for the JOB, not for the alarm: `alert` gets its
# own token from the gateway. The two `export TELEGRAM_*` lines that used to sit
# here died on `set -u` whenever the file was absent — an unbound-variable abort
# at line 25, before the wrapper did any work, on the machine least likely to
# have those vars.
# `-f` guard, NOT `|| true`: under `set -e`, bash treats a `source` whose file is
# missing as a failing SPECIAL BUILTIN and EXITS THE SHELL — `|| true` never gets
# to run. Measured on bash 3.2.57 (the macOS system bash these crons use):
#   set -euo pipefail; source /nonexistent 2>/dev/null || true; echo after
#   -> prints nothing after, exits 1.
# So this line was a silent abort at wrapper line 37 on every machine without the
# file, wearing the costume of a tolerant fallback. The other six wrappers in this
# directory already test `-f` first; this one did not.
if [ -f /Users/nuzantara/.zshrc.secrets ]; then
    source /Users/nuzantara/.zshrc.secrets
fi

_send_telegram() {
    local msg="$1"
    alert p0 "${msg}"
}

cd "$PROJECT_ROOT"

set +e  # errexit would abort ON the pipeline, before the capture below
"$PYTHON" "$SCRIPT" "$@"
EXIT_CODE=$?
set -e

if [ $EXIT_CODE -eq 0 ]; then
    # Record heartbeat
    HEARTBEAT_DIR="$HOME/.agent/decisions/state"
    mkdir -p "$HEARTBEAT_DIR"
    echo "{\"job\":\"nb1_daily_refresh\",\"ts\":$(date +%s),\"status\":\"ok\",\"host\":\"$(hostname)\"}" \
        > "$HEARTBEAT_DIR/nb1_daily_refresh.last.json"
else
    _send_telegram "❌ NB-1 daily refresh FAILED (exit ${EXIT_CODE}) — $(date '+%Y-%m-%d %H:%M WITA')"
fi

exit $EXIT_CODE
