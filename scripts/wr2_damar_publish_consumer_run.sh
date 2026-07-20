#!/bin/bash
# WR2 Damar publish consumer — LaunchAgent wrapper (STRATO 2).
#
# Polls the local wa-mirror Postgres for Damar's `PUBBLICATO WR2-XXX <url>`
# messages and advances the matching queue item to `published` via STRATO 1.
#
# Cron: every 5 min via com.nuzantara.wr2-damar-publish-consumer.plist
#       (StartInterval, NO KeepAlive — W67: KeepAlive + one-shot = crash-loop).
#
# Requires:
#   * env WA_MIRROR_DATABASE_URL (the wa-mirror local Postgres DSN) — sourced
#     from apps/wa-mirror/.env below; NEVER hard-coded (Golden Rule #6).
#   * backend venv (asyncpg).
#
# Exit codes: 0 = clean (incl. nothing to do); 1 = parsed-but-unresolved
# command(s) need human disambiguation (see ~/.agent/state/wr2_damar_unmatched.jsonl).

set -uo pipefail

REPO_ROOT="${WR2_CONSUMER_REPO_ROOT:-$HOME/nuzantara}"
LOGDIR="${HOME}/logs"
mkdir -p "$LOGDIR"
LOG="$LOGDIR/wr2-damar-publish-consumer.log"

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-damar-publish-consumer starting" >> "$LOG"

# Kill switch (read live each tick).
CONFIG="${HOME}/.agent/wr2-damar-consumer.config"
if [ -f "$CONFIG" ]; then
  if grep -q '"enabled"[[:space:]]*:[[:space:]]*false' "$CONFIG" 2>/dev/null; then
    echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] disabled via config — skip" >> "$LOG"
    exit 0
  fi
fi

# DSN from the wa-mirror env (carries a password — do not echo it).
# IMPORTANT: the LIVE wa-mirror bridge reads its DSN from ~/.wa-mirror.env
# (HOME-fork, W67), which points at the real local Postgres
# (nuzantara@localhost:5432/nuzantara_dev). The in-repo apps/wa-mirror/.env is
# STALE (points at a 15432 DSN with a rotated password that fails auth). Prefer
# the HOME config; fall back to the repo .env only if HOME is absent.
for WA_ENV in "$HOME/.wa-mirror.env" "$REPO_ROOT/apps/wa-mirror/.env"; do
  if [ -f "$WA_ENV" ]; then
    # shellcheck disable=SC1090
    set -a; . "$WA_ENV"; set +a
    [ -n "${WA_MIRROR_DATABASE_URL:-}" ] && break
  fi
done
if [ -z "${WA_MIRROR_DATABASE_URL:-}" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FATAL: WA_MIRROR_DATABASE_URL unset — abort" >> "$LOG"
  exit 2
fi
export WA_MIRROR_DATABASE_URL

VENV="$REPO_ROOT/apps/backend-rag/.venv/bin/python"
if [ ! -x "$VENV" ]; then
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] FATAL: backend venv missing at $VENV — abort" >> "$LOG"
  exit 2
fi

"$VENV" "$REPO_ROOT/scripts/wr2_damar_publish_consumer.py" --once >> "$LOG" 2>&1
RC=$?
echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] wr2-damar-publish-consumer done rc=$RC" >> "$LOG"
exit $RC
