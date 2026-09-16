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

# HOME must be usable even if the launchd environment never set it — a bare
# `set -u` reference to an unset $HOME a few lines below would kill the
# script before anything, including an emergency heartbeat, could run.
: "${HOME:=/Users/nuzantara}"

REPO_ROOT="${META_ONE_REPO_ROOT:-/Users/nuzantara/nuzantara}"

# Self-contained emergency heartbeat (Codex red-team finding #5). Every
# fallible step below this point — repo missing, secrets unreadable, python
# missing — must still leave a REAL verdict (superscar #2: esiste!=armato).
# This writer depends on NOTHING but $HOME/bash/date/mv: not the repo, not
# python, not scripts/lib/heartbeat.sh — because the repo itself can be the
# thing that's missing.
_emergency_heartbeat() {
  local status="$1" note="$2"
  local dir="${ORGANISM_LAST_SEEN_DIR:-${HOME}/.organism/last_seen}"
  mkdir -p "$dir" 2>/dev/null || return 0
  local tmp="$dir/pro.meta_one_steward.json.tmp.$$"
  printf '{"ts":"%s","status":"%s","note":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "$note" > "$tmp" 2>/dev/null \
    && mv -f "$tmp" "$dir/pro.meta_one_steward.json" 2>/dev/null
}

# PY_RAN gates the trap: once we hand off to python, python's own tick (or
# the post-run block further down, once the repo is confirmed present) owns
# writing an accurate, specific heartbeat — the trap's generic "wrapper
# failed" note must never clobber that. The trap exists ONLY to catch a
# failure that happens BEFORE that handoff (the class this wrapper used to
# leave completely silent).
PY_RAN=""
_on_exit() {
  local rc=$?
  if [ "$rc" -ne 0 ] && [ -z "$PY_RAN" ]; then
    _emergency_heartbeat "error" "wrapper failed before python ran (rc=$rc)"
  fi
}
trap _on_exit EXIT

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
  _emergency_heartbeat "disabled" "META_ONE_STEWARD_ENABLED=false"
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

PY_RAN=1
"$PY" "$REPO_ROOT/scripts/meta_one_steward.py" tick >> "$LOG" 2>&1
RC=$?
echo "[$(ts)] meta-one-steward done rc=$RC" >> "$LOG"

# A crashed python still leaves a REAL verdict (superscar #2: esiste!=armato).
# meta_one_steward.py's own tick already writes ok/warning/error heartbeats on
# every path it can reach; this is the last-resort net for the rc it can NOT
# reach (e.g. python itself segfaulting after start). The repo is confirmed
# present at this point, so the richer heartbeat.sh contract is preferred,
# falling back to the same self-contained writer the trap uses.
if [ "$RC" -ne 0 ]; then
  HEARTBEAT_SH="$REPO_ROOT/scripts/lib/heartbeat.sh"
  if [ -f "$HEARTBEAT_SH" ]; then
    # shellcheck disable=SC1090
    . "$HEARTBEAT_SH"
    organism_heartbeat "pro.meta_one_steward" "error" "wrapper rc=$RC"
  else
    _emergency_heartbeat "error" "wrapper rc=$RC (heartbeat.sh missing)"
  fi
fi

exit $RC
