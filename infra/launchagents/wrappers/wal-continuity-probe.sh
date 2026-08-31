#!/bin/bash
# wal-continuity-probe.sh — LaunchAgent wrapper for scripts/wal_continuity_probe.py.
#
# Answers the question a green backup does not: is the WAL chain continuous, and is
# archiving succeeding RIGHT NOW? See the probe's own header for why (2026-08-09: WAL
# archiving was off, every backup reported DONE, nothing was red).
#
# HOST: Pro. That is where `fly-pg-backup.sh` already runs and where a live `fly`
# credential exists; the probe needs the same reach.
#
# W84-safe: the executed copy lives OUTSIDE ~/Desktop, because launchd loses the TCC
# grant there and a plist under it goes green-but-dead. Canon is the repo; the live copy
# is ~/.nuzantara-cron/ (canon-pair, same shape as auth_sentinel_cron.sh) — declare the
# pair in scripts/declared-pairs.json when installing, or lint_home_fork cannot see it
# drift (W107: the pairs nobody declared were the ones that diverged).
#
# Pure cron, not a daemon: StartInterval, KeepAlive absent (superscar #7).
set -uo pipefail

REPO="${WAL_PROBE_REPO:-$HOME/nuzantara}"
LOG_DIR="$HOME/.local/state/wal-continuity-probe"
LOG="$LOG_DIR/run.log"
HEARTBEAT_DIR="$HOME/.organism/last_seen"
mkdir -p "$LOG_DIR" "$HEARTBEAT_DIR"

ts() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# Kill switch — an organ must be able to die without uninstalling its plist (superscar #2).
if [ "${WAL_PROBE_ENABLED:-true}" = "false" ]; then
  echo "[$(ts)] WAL_PROBE_ENABLED=false → skip tick" >> "$LOG"
  exit 0
fi

# Heartbeat, so the guardian is itself observable and cannot become a green-but-dead.
# Written with the OUTCOME, never merely "I ran": an exit code is the point.
heartbeat() {
  printf '{"organ":"wal-continuity-probe","host":"%s","ts":"%s","exit":%s}\n' \
    "$(hostname -s)" "$(ts)" "${1:-null}" > "$HEARTBEAT_DIR/wal-continuity-probe.json" 2>/dev/null || true
}

# The paid Anthropic key must never be visible to anything this wrapper spawns.
unset ANTHROPIC_API_KEY 2>/dev/null || true

# Cron's PATH is /usr/bin:/bin:/usr/sbin:/sbin — Homebrew is not on it and flyctl lives
# there, so a bare `fly` works in every interactive test and fails on every scheduled run
# (the exact trap that blinded drive_token_watchdog for 24 days).
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

# Secrets by NAME, never by value. The gateway (scripts/tg_notify.py) reads
# TELEGRAM_BOT_TOKEN / TELEGRAM_OWNER_CHAT_ID from the environment; this wrapper only
# makes them available and never echoes them.
for _f in "$HOME/.nuzantara-secrets.env"; do
  if [ -f "$_f" ]; then
    set -a; . "$_f"; set +a
  fi
done

# Errexit is deliberately NOT armed around the probe. `set -e` under a bare invocation is
# how W101-recidiva-fly-backup made its own PARTIAL report unreachable: bash aborted before
# the exit code could be captured, and the reporting branch was dead code on the only path
# it existed for. Judge by the CAPTURED code, never by having survived.
set +e
python3 "$REPO/scripts/wal_continuity_probe.py" >> "$LOG" 2>&1
RC=$?
set -e

heartbeat "$RC"
echo "[$(ts)] wal-continuity-probe exit=$RC" >> "$LOG"

# 0 clean · 1 RED (probe already paged) · 2 blind · 4 cannot-verify.
# Exiting non-zero is what lets cron-runner.sh / cron-state.sh see a failure at all.
exit "$RC"
