#!/bin/bash
# meta-one-steward.sh — LaunchAgent wrapper for scripts/meta_one_steward.py.
#
# Runs the Meta One Advanced Access ledger's daily tick: probe -> ingest ->
# ledger -> digest -> heartbeat (playbook section 4.3). One-shot, no
# KeepAlive — see com.nuzantara.meta-one-steward.plist (superscar #7:
# KeepAlive + one-shot = restart-loop).
#
# Cron: daily 06:20 WITA via com.nuzantara.meta-one-steward.plist.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

REPO_ROOT="${META_ONE_REPO_ROOT:-/Users/nuzantara/nuzantara}"
LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/meta-one-steward.log"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

echo "[$(ts)] meta-one-steward starting" >> "$LOG"

# Kill switch (G5 gene): operator can stop this organ without uninstalling
# it. Honored live, every tick — writes a final `disabled` heartbeat so the
# healer never tries to resurrect an intentionally-stopped organ.
if [ "${META_ONE_STEWARD_ENABLED:-true}" = "false" ]; then
  echo "[$(ts)] disabled via META_ONE_STEWARD_ENABLED=false — skip" >> "$LOG"
  HEARTBEAT_SH="$REPO_ROOT/scripts/lib/heartbeat.sh"
  if [ -f "$HEARTBEAT_SH" ]; then
    # shellcheck disable=SC1090
    . "$HEARTBEAT_SH"
    organism_heartbeat "pro.meta_one_steward" "disabled" "META_ONE_STEWARD_ENABLED=false"
  fi
  exit 0
fi

# Secrets: sourced, never echoed (Golden Rule #6). INSTAGRAM_ACCESS_TOKEN
# (or the IG_LONG_LIVED_TOKEN fallback) and the Telegram token both live here.
SECRETS="${HOME}/.nuzantara-secrets.env"
if [ -f "$SECRETS" ]; then
  set -a
  # shellcheck disable=SC1090
  . "$SECRETS"
  set +a
else
  echo "[$(ts)] WARNING: $SECRETS not found — token probe will read as unknown" >> "$LOG"
fi

# Prefer a modern python (homebrew 3.14) — /usr/bin/python3 is 3.9.
PY="/opt/homebrew/bin/python3"
[ -x "$PY" ] || PY="python3"

cd "$REPO_ROOT" || {
  echo "[$(ts)] FATAL: repo root missing at $REPO_ROOT — abort" >> "$LOG"
  exit 2
}

"$PY" "$REPO_ROOT/scripts/meta_one_steward.py" tick >> "$LOG" 2>&1
RC=$?
echo "[$(ts)] meta-one-steward done rc=$RC" >> "$LOG"

# A crashed python still leaves a REAL verdict (superscar #2: esiste!=armato).
# meta_one_steward.py's own tick already writes ok/warning/error heartbeats on
# every path it can reach; this is the last-resort net for the rc it can NOT
# reach (e.g. python itself missing/segfaulting before any Python runs).
if [ "$RC" -ne 0 ]; then
  HEARTBEAT_SH="$REPO_ROOT/scripts/lib/heartbeat.sh"
  if [ -f "$HEARTBEAT_SH" ]; then
    # shellcheck disable=SC1090
    . "$HEARTBEAT_SH"
    organism_heartbeat "pro.meta_one_steward" "error" "wrapper rc=$RC"
  fi
fi

exit $RC
