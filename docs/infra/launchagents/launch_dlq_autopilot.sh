#!/usr/bin/env bash
# launch_dlq_autopilot.sh — LaunchAgent wrapper that loads secrets from .env
#
# W50 (2026-05-23): exec the REPO copy of dlq_autopilot.py, not the HOME
# fork. Pre-W50: this wrapper exec'd $HOME/scripts/dlq_autopilot.py which
# was a May-11 fork missing the 2026-05-19 ops-hardening fix that routes
# INFO StreamHandler to sys.stdout. Production was running stale code 4
# days post-fix → 9500+ INFO "status=TERMINAL — skipping" lines/day
# polluting dlq_autopilot.error.log (12.7 MB/day per original cicatrix
# comment in scripts/dlq_autopilot.py:25-31). Empirical 2026-05-23 W50:
# repo SHA differs from HOME SHA; HOME has bare StreamHandler() while
# repo has StreamHandler(sys.stdout). Plist had been running stale.
#
# Fix: point exec at $REPO_DIR/scripts/dlq_autopilot.py so every future
# fix that lands on main propagates to production at next cron tick. No
# more sync-by-hand of HOME copies.
set -euo pipefail

ENV_FILE="$HOME/.nuzantara-secrets.env"

if [ ! -f "$ENV_FILE" ]; then
    echo "FATAL: Missing $ENV_FILE" >&2
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

REPO_DIR="$HOME/nuzantara"
SCRIPT="$REPO_DIR/scripts/dlq_autopilot.py"

if [ ! -f "$SCRIPT" ]; then
    echo "FATAL: Missing $SCRIPT (repo path)" >&2
    exit 1
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.pyenv/versions/3.11.11/bin"
exec "$HOME/.pyenv/versions/3.11.11/bin/python3" "$SCRIPT"
