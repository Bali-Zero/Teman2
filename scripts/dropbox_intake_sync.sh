#!/bin/bash
# dropbox-intake-sync.sh — Dropbox → Google Drive intake. COPY ONLY: never move,
# never delete. Dropbox is never emptied (operator decision 2026-06-12).
#
# Src: dropbox-bayu:           (Dropbox, data.bayusantero@gmail.com)
# Dst: gdrive:Dropbox-Intake/  (Google Drive, antonellosiano@gmail.com)
#
# Runtime: Pro, LaunchAgent com.balizero.dropbox-intake every 10 min.
# A single-instance lock self-paces long runs (first backfill ~527 GiB):
# while a run is alive, later ticks exit 0 immediately.
#
# Source of truth: scripts/dropbox_intake_sync.sh (repo). After edits, re-run
# infra/launchagents/install_dropbox_intake.sh on the Pro (HOME-fork discipline,
# scar family W50/W51/W52).
#
# Kill switch: DROPBOX_INTAKE_ENABLED=false (plist env or shell).
set -uo pipefail

ENABLED="${DROPBOX_INTAKE_ENABLED:-true}"
SRC="${DROPBOX_INTAKE_SRC:-dropbox-bayu:}"
DST="${DROPBOX_INTAKE_DST:-gdrive:Dropbox-Intake}"
BWLIMIT="${DROPBOX_INTAKE_BWLIMIT:-4M}"
# Dropbox throttles aggressively (HTTP 429 "too many requests"); cap the API
# transaction rate + listing concurrency to avoid the 429->backoff death-spiral
# that crawls throughput to ~100 B/s on a large tree. All env-overridable,
# same idiom as BWLIMIT above. (anti-throttle tuning 2026-06-16)
TPSLIMIT="${DROPBOX_INTAKE_TPSLIMIT:-12}"
CHECKERS="${DROPBOX_INTAKE_CHECKERS:-4}"
TRANSFERS="${DROPBOX_INTAKE_TRANSFERS:-4}"
LOW_LEVEL_RETRIES="${DROPBOX_INTAKE_LLR:-20}"
LOG_DIR="${HOME}/.cache/dropbox-intake"
STATE_DIR="${HOME}/.agent/decisions/state"
STATE_FILE="${STATE_DIR}/dropbox_intake.last.json"
LOCK_FILE="${LOG_DIR}/.lock"
RUN_LOG="${LOG_DIR}/run-$(date +%Y%m%d-%H%M%S).log"
LATEST="${LOG_DIR}/latest.log"
SECRETS_FILE="${HOME}/.nuzantara-secrets.env"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-1125336968}"
ALERT_COOLDOWN_S=3600

mkdir -p "$LOG_DIR" "$STATE_DIR"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] [dropbox-intake] $*" >> "$LATEST"; }

if [ "$ENABLED" != "true" ]; then
  log "disabled via DROPBOX_INTAKE_ENABLED — exit 0"
  exit 0
fi

# Single-instance lock (a long backfill run keeps it; later cron ticks skip).
# Validate the locked PID is OUR script, not just any live PID. The kernel
# recycles PIDs: a stale lock pointing at a number later reassigned to an
# unrelated process (e.g. syncthing) would make every tick exit 0 forever,
# silently freezing the flow while the state-file goes stale and the sentinel
# stays blind. Trust the lock only if the live process is dropbox-intake-sync.
# (scar #2 "esiste ≠ armato" — recycled-PID stale-lock, 2026-06-27)
LOCK_TAG="dropbox-intake-sync"
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$PID" ] && ps -p "$PID" >/dev/null 2>&1; then
    if ps -p "$PID" -o command= 2>/dev/null | grep -q "$LOCK_TAG"; then
      log "another run alive (PID $PID) — exit 0"
      exit 0
    fi
    log "stale lock: PID $PID alive but not $LOCK_TAG (recycled PID) — reclaiming"
  fi
  rm -f "$LOCK_FILE"
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

telegram() {
  # Token lives ONLY in the 0600 secrets file — never in plist, never logged.
  local text="$1"
  [ -f "$SECRETS_FILE" ] || return 0
  # shellcheck disable=SC1090
  set -a; source "$SECRETS_FILE" >/dev/null 2>&1; set +a
  [ -n "${TELEGRAM_BOT_TOKEN:-}" ] || return 0
  curl -sS --max-time 20 \
    "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    --data-urlencode "text=${text}" >/dev/null 2>&1 || log "telegram post failed"
}

alert_once() {
  # Failure alert with 1h cooldown — alert on breakage, don't spam (W55/W70).
  local text="$1" now last
  now=$(date +%s)
  last=$(cat "${LOG_DIR}/.last_alert" 2>/dev/null || echo 0)
  if [ $((now - last)) -ge "$ALERT_COOLDOWN_S" ]; then
    telegram "$text"
    echo "$now" > "${LOG_DIR}/.last_alert"
  else
    log "alert suppressed (cooldown): $text"
  fi
}

# Pre-flight: both remotes must exist, else skip quietly + one deduped alert.
REMOTES=$(rclone listremotes 2>/dev/null || echo "")
for r in "${SRC%%:*}" "${DST%%:*}"; do
  if ! echo "$REMOTES" | grep -q "^${r}:$"; then
    log "remote '$r' not configured — exit 0"
    alert_once "⚠️ dropbox-intake: remote rclone '$r' non configurato su $(hostname -s) — flow fermo (rifare rclone authorize, vedi docs/runbooks/dropbox-intake.md)"
    exit 0
  fi
done

START=$(date +%s)
log "run start: $SRC -> $DST (bwlimit=$BWLIMIT tpslimit=$TPSLIMIT checkers=$CHECKERS) log=$RUN_LOG"

# Skip Dropbox junk that clogs the queue head (alphabetically first), wastes
# Drive quota, and pollutes the CRM intake: "(Selective Sync Conflict)" duplicate
# folders, a stray cracked-software archive, and a Driver dump. (junk-exclude 2026-06-16)
# --max-age 24h: day-only regime (Zero GO 2026-07-04) — the historical-archive
# backfill was aborted after it flooded the Pro intake (81GB blobs, 175k pending,
# disk 100%); only files modified in the last day are mirrored from now on.
rclone copy "$SRC" "$DST" \
  --log-level INFO --log-file "$RUN_LOG" \
  --transfers "$TRANSFERS" --checkers "$CHECKERS" \
  --tpslimit "$TPSLIMIT" --tpslimit-burst 1 \
  --low-level-retries "$LOW_LEVEL_RETRIES" --retries 5 \
  --fast-list --max-age 24h \
  --bwlimit "$BWLIMIT" \
  --drive-stop-on-upload-limit \
  --exclude ".DS_Store" --exclude "/.dropbox.cache/**" \
  --exclude "*(Selective Sync Conflict)*/**" \
  --exclude "Adobe CS4*/**" \
  --exclude "Driver/**"
RC=$?
ELAPSED=$(( $(date +%s) - START ))

COPIED=$(grep -c ": Copied (new)" "$RUN_LOG" 2>/dev/null || true)
REPLACED=$(grep -c ": Copied (replaced existing)" "$RUN_LOG" 2>/dev/null || true)
COPIED="${COPIED:-0}"
REPLACED="${REPLACED:-0}"

if [ "$RC" -ne 0 ]; then
  log "FAIL rc=$RC copied=$COPIED replaced=$REPLACED elapsed=${ELAPSED}s"
  alert_once "🔴 dropbox-intake FAILED (exit $RC) su $(hostname -s) — copied=$COPIED elapsed=${ELAPSED}s. Log: ~/.cache/dropbox-intake/"
else
  log "ok: copied=$COPIED replaced=$REPLACED elapsed=${ELAPSED}s"
  TOTAL=$(( COPIED + REPLACED ))
  if [ "$TOTAL" -gt 0 ]; then
    NAMES=$(grep -E ": Copied \((new|replaced existing)\)" "$RUN_LOG" \
      | sed -E 's/^.*INFO[[:space:]]*:[[:space:]]*//; s/: Copied.*$//' | head -10)
    MSG="📥 Dropbox-Intake: ${COPIED} nuovi file → Drive/Dropbox-Intake"
    [ "$REPLACED" -gt 0 ] && MSG="${MSG} (+${REPLACED} aggiornati)"
    MSG="${MSG}
${NAMES}"
    EXTRA=$(( TOTAL - 10 ))
    [ "$EXTRA" -gt 0 ] && MSG="${MSG}
… +${EXTRA} altri"
    telegram "$MSG"
  fi
fi

printf '{"job":"dropbox_intake","ts":%s,"status":"%s","copied":%s,"replaced":%s,"elapsed":%s,"host":"%s"}\n' \
  "$(date +%s)" "$([ "$RC" -eq 0 ] && echo ok || echo fail)" "$COPIED" "$REPLACED" "$ELAPSED" "$(hostname -s)" \
  > "$STATE_FILE"

# Keep last 100 run logs.
ls -t "${LOG_DIR}"/run-*.log 2>/dev/null | tail -n +101 | xargs rm -f 2>/dev/null || true

exit "$RC"
