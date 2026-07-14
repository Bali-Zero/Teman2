#!/bin/bash
# curiosity-batch.sh — SYMBIOSIS Pillar 6 weekly Telegram digest wrapper.
#
# Reads the top cell_curiosity_findings and sends Zero a weekly Telegram summary.
# Promoted into the repo (was a ~/scripts HOME-fork, superscar #1). The DB
# password that used to be exported here in cleartext (cicatrix #4) is gone:
# DATABASE_URL now comes from ~/.nuzantara-secrets.env like every other secret.
#
# Runs every Sunday 20:00 WITA (12:00 UTC) via com.nuzantara.curiosity-batch.weekly.
set -euo pipefail

# W84 trampoline sweep (2026-07-14): this wrapper is DEPLOYED to ~/scripts/
# (declared pair in infra/home-fork/declared-pairs.json) — dirname-based
# REPO resolution (BASH_SOURCE[0]) is wrong there, since it would resolve
# REPO to $HOME instead of the repo checkout. REPO_ROOT lets an operator
# override for testing; the deploy-aware default assumes the canonical
# checkout location.
REPO="${REPO_ROOT:-$HOME/Desktop/nuzantara}"

# sshd (W84 trampoline) and bare launchd contexts carry a minimal PATH.
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

LOG="$HOME/logs/curiosity-batch.log"

# Kill switch (gene G5)
if [ "${CURIOSITY_BATCH_ENABLED:-true}" = "false" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): CURIOSITY_BATCH_ENABLED=false — skipping" >> "$LOG"
    exit 0
fi

# W84 trampoline (2026-07-14): fail fast / re-exec via ssh-localhost if this
# launchd context has lost the TCC grant to ~/Desktop, BEFORE SCRIPT/VENV
# below (both REPO-relative, i.e. under ~/Desktop) are ever touched.
TRAMPOLINE_LIB="$HOME/scripts/lib/trampoline.sh"
[ -f "$TRAMPOLINE_LIB" ] || TRAMPOLINE_LIB="$(dirname "$0")/lib/trampoline.sh"
if [ -f "$TRAMPOLINE_LIB" ]; then
    source "$TRAMPOLINE_LIB"
    w84_trampoline_or_die "$LOG"
fi

SCRIPT="$REPO/scripts/cron-agent-python/curiosity_batch.py"
VENV="$REPO/apps/backend-rag/.venv"
SECRETS="$HOME/.nuzantara-secrets.env"

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Starting curiosity batch" >> "$LOG"

if [ -f "$SECRETS" ]; then
    set -a; source "$SECRETS"; set +a
else
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): WARNING secrets file not found at $SECRETS" >> "$LOG"
fi

source "$VENV/bin/activate"

# DATABASE_URL must come from the secrets file (env-only, no hardcoded password).
if [ -z "${DATABASE_URL:-}" ]; then
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): FATAL DATABASE_URL not set — aborting" >> "$LOG"
    exit 1
fi

# Organism heartbeat (gene G2): source the shared lib the way its own
# docstring documents ("Source pattern (bash)") and call organism_heartbeat
# directly — same lib-resolution order as
# infra/launchagents/wrappers/regulatory-watcher-run.sh (prefer ~/scripts/lib,
# outside the TCC-protected ~/Desktop; fall back to repo canon). python3's
# exit code is captured explicitly (not left to -e) so a failing run still
# gets an honest "error" heartbeat instead of the wrapper dying silently
# before the write.
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
    HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$HOME/scripts/lib/heartbeat.sh" ]; then
    HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
else
    HEARTBEAT_LIB="$HOME/Desktop/nuzantara/scripts/lib/heartbeat.sh"
fi
if [ -r "$HEARTBEAT_LIB" ]; then
    source "$HEARTBEAT_LIB"
fi

set +e
python3 "$SCRIPT" >> "$LOG" 2>&1
PY_EXIT=$?
set -e

if [ "$PY_EXIT" -eq 0 ]; then
    HB_STATUS="ok"
    HB_NOTE="completed"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): Curiosity batch completed" >> "$LOG"
else
    HB_STATUS="error"
    HB_NOTE="rc=${PY_EXIT}"
    echo "$(date -u +%Y-%m-%dT%H:%M:%SZ): FAILED curiosity batch rc=${PY_EXIT}" >> "$LOG"
fi
if command -v organism_heartbeat >/dev/null 2>&1; then
    organism_heartbeat "pro.curiosity_weekly" "$HB_STATUS" "$HB_NOTE"
fi

exit "$PY_EXIT"
