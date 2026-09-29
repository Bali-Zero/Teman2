#!/usr/bin/env bash
# disk_janitor.sh — bounded, allowlisted disk hygiene for Pro (payload of organ pro.disk_janitor).
#
# Why: Pro's Data volume reached 97 % on 2026-09-29 and every reclaim was a hand-run session.
# scripts/disk_watchdog.sh only ALERTS (Telegram at >85 %); scripts/qdrant_backup_retention.sh
# exists but nothing scheduled it. The accumulators that grow without an owner are all
# machine-generated and reproducible, so this janitor prunes them on a schedule and
# journals every run. It NEVER touches data that a human produced or that carries PII:
#   ~/Desktop/OSINT-Nexus, ~/wa-mirror-media, ~/backups/fly-postgres, any *PII-Quarantine* dir,
#   ~/.nuzantara-pilots (evidence), ~/nuzantara/.worktrees (broker-owned), ~/.ollama,
#   ~/.colima (VM disk), ~/.cache/huggingface (model weights), ~/.claude/backups (memory DB),
#   ~/.claude/projects (transcripts + memory).
# Those are not "skipped": they are never a target, and refuse_path() (exact roots, never a
# substring — council finding O1) makes any computed target under one an ERROR that skips
# the item and lets the rest of the run proceed; the receipt carries errors>0.
#
# Targets (each step has its own env knob; ages in days; `-mtime +N` = strictly older than N+1 d):
#   scratch   $DISK_JANITOR_TMP_ROOT/-<project>/<session-uuid>  parent starts with "-", child is a
#             uuid (council O2), older than 7 d, uuid not registered in ~/.claude/sessions; the step
#             is skipped (ERROR) when that registry is absent or empty (council O4, fail-closed)
#   codex     ~/.codex/{sessions,archived_sessions}/**/*.jsonl  >14 d and not open (lsof)
#   logarch   ~/logs/archive/*.gz                                >60 d (log-rotate-run.sh gzips, nothing pruned)
#   qdrant    scripts/qdrant_backup_retention.sh                  delegated, same --apply mode
#   tools     uv cache prune (skipped while a uv process holds the lock) · docker image/volume prune
#             (dangling / anonymous only, NEVER -a: localci-candidate:1 is pinned by image ID in its plans)
#             · docker builder prune --filter until=168h · brew cleanup --prune=30
#
# DRY-RUN by default: reports candidates, removes nothing. `--apply` acts.
# `--check-path P` prints OK|REFUSE for P against the protected roots and exits (used by the test).
# Kill switch: DISK_JANITOR_ENABLED=false. Targets /bin/bash 3.2 (fleet default).
# Log lines carry uuids, archive names and a short hash of codex basenames — never a full
# transcript name (council O7, output boundary). Test: scripts/test_disk_janitor.sh.
set -uo pipefail

JH="${DISK_JANITOR_HOME:-$HOME}"
TMP_ROOT="${DISK_JANITOR_TMP_ROOT:-/private/tmp/claude-501}"
SESSIONS_DIR="${DISK_JANITOR_SESSIONS_DIR:-$JH/.claude/sessions}"
LOG_FILE="${DISK_JANITOR_LOG:-$JH/logs/disk-janitor.log}"
JOURNAL="${DISK_JANITOR_JOURNAL:-$JH/logs/disk-janitor.receipts.jsonl}"
SCRATCH_DAYS="${DISK_JANITOR_SCRATCH_DAYS:-7}"
CODEX_DAYS="${DISK_JANITOR_CODEX_DAYS:-14}"
LOG_ARCHIVE_DAYS="${DISK_JANITOR_LOG_ARCHIVE_DAYS:-60}"
TOOLS="${DISK_JANITOR_TOOLS:-true}"
QDRANT_RETENTION="${DISK_JANITOR_QDRANT_RETENTION-$(cd "$(dirname "$0")" && pwd)/qdrant_backup_retention.sh}"

# Protected roots (exact path or anything below it) + one name-based component.
PROTECTED_ROOTS="$JH/Desktop/OSINT-Nexus
$JH/wa-mirror-media
$JH/backups/fly-postgres
$JH/.nuzantara-pilots
$JH/nuzantara/.worktrees
$JH/.ollama
$JH/.colima
$JH/.cache/huggingface
$JH/.claude/backups
$JH/.claude/projects"
PROTECTED_COMPONENT="Nuzantara-PII-Quarantine"

canon() { # physical path when resolvable (symlinked parents), else the literal
  if [ -d "$1" ]; then (cd "$1" 2>/dev/null && pwd -P) || printf '%s' "$1"
  else d=$(dirname "$1"); b=$(basename "$1"); (cd "$d" 2>/dev/null && printf '%s/%s' "$(pwd -P)" "$b") || printf '%s' "$1"; fi
}
is_protected() { # 0 = protected
  local p c r
  p="$1"; c=$(canon "$1")
  case "/$p/" in */"$PROTECTED_COMPONENT"/*) return 0 ;; esac
  case "/$c/" in */"$PROTECTED_COMPONENT"/*) return 0 ;; esac
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    case "$p" in "$r"|"$r"/*) return 0 ;; esac
    case "$c" in "$r"|"$r"/*) return 0 ;; esac
  done <<EOF
$PROTECTED_ROOTS
EOF
  return 1
}
if [ "${1:-}" = "--check-path" ]; then
  [ -n "${2:-}" ] || { echo "usage: --check-path P" >&2; exit 64; }
  if is_protected "$2"; then echo "REFUSE $2"; exit 3; else echo "OK $2"; exit 0; fi
fi

APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true
MODE=DRY-RUN; $APPLY && MODE=APPLY

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JOURNAL")" 2>/dev/null || true
ts()  { date +%Y-%m-%dT%H:%M:%S%z; }
safe() { printf '%s' "$1" | tr '\n\r' '??'; }
log() { echo "[$(ts)] disk-janitor[$MODE] $*" | tee -a "$LOG_FILE" >&2; }

case "$(printf '%s' "${DISK_JANITOR_ENABLED:-true}" | tr 'A-Z' 'a-z')" in
  0|false|no|off) log "DISABLED via DISK_JANITOR_ENABLED — exit 0"; exit 0 ;;
esac

# The scratch root is the one target that can be pointed elsewhere by env/plist (council O3):
# it must be an absolute, non-symlinked path whose basename is claude-<uid>.
case "$TMP_ROOT" in
  /*/claude-[0-9]*) : ;;
  *) log "REFUSE: DISK_JANITOR_TMP_ROOT '$(safe "$TMP_ROOT")' must be an absolute path ending in claude-<uid> — exit 2"; exit 2 ;;
esac
if [ -L "$TMP_ROOT" ]; then log "REFUSE: DISK_JANITOR_TMP_ROOT is a symlink — exit 2"; exit 2; fi

FREED=0; ERRORS=0
N_SCRATCH=0; N_CODEX=0; N_LOGARCH=0
bytes_of() { du -sk "$1" 2>/dev/null | head -1 | awk '{print $1*1024}' | tr -d '\n'; }
remove() { # $1 path  $2 step  $3 label for the log
  local b
  if [ -z "$1" ] || [ "$1" = "/" ] || [ "$1" = "$JH" ]; then log "$2: REFUSE unsafe target '$(safe "$1")' — abort rc=2"; exit 2; fi
  if is_protected "$1"; then ERRORS=$((ERRORS + 1)); log "$2: REFUSE $3 (protected tree) — skipped"; return 1; fi
  b=$(bytes_of "$1"); b=${b:-0}
  if $APPLY; then
    if rm -rf -- "$1" 2>/dev/null; then FREED=$((FREED + b)); log "$2: removed $3 ($b B)"
    else ERRORS=$((ERRORS + 1)); log "$2: FAILED to remove $3"; return 1; fi
  else
    log "$2: would remove $3 ($b B)"; FREED=$((FREED + b))
  fi
  return 0
}

UUID_RE='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
session_live() { grep -rlq -- "$1" "$SESSIONS_DIR" 2>/dev/null; }

# ── scratch: $TMP_ROOT/-<project>/<session-uuid> ───────────────────────────────
if [ ! -d "$TMP_ROOT" ]; then
  log "scratch: root absent — nothing to do"
elif [ ! -d "$SESSIONS_DIR" ] || [ -z "$(find "$SESSIONS_DIR" -maxdepth 1 -name '*.json' -print -quit 2>/dev/null)" ]; then
  ERRORS=$((ERRORS + 1)); log "scratch: session registry $SESSIONS_DIR absent or empty — step skipped (cannot tell live from dead)"
else
  while IFS= read -r -d '' d; do
    u=$(basename "$d"); p=$(basename "$(dirname "$d")")
    case "$p" in -*) : ;; *) log "scratch: keep $(safe "$p")/$(safe "$u") (not a project dir)"; continue ;; esac
    [[ "$u" =~ $UUID_RE ]] || { log "scratch: keep $(safe "$p")/$(safe "$u") (not a session uuid)"; continue; }
    session_live "$u" && { log "scratch: keep $p/$u (session live)"; continue; }
    remove "$d" scratch "$p/$u" && N_SCRATCH=$((N_SCRATCH + 1))
  done < <(find "$TMP_ROOT" -mindepth 2 -maxdepth 2 -type d -mtime +"$SCRATCH_DAYS" -print0 2>/dev/null)
fi

# ── codex sessions: transcripts older than CODEX_DAYS, never an open file ───────
HAVE_LSOF=true; command -v lsof >/dev/null 2>&1 || { HAVE_LSOF=false; log "codex: lsof absent — open-file check unavailable"; }
for root in "$JH/.codex/sessions" "$JH/.codex/archived_sessions"; do
  [ -d "$root" ] || continue
  while IFS= read -r -d '' f; do
    label="${f#"$JH"/}"; label="$(dirname "$label")/$(printf '%s' "$(basename "$f")" | shasum -a 256 | cut -c1-12).jsonl"
    if $HAVE_LSOF && lsof -- "$f" >/dev/null 2>&1; then log "codex: keep $label (open)"; continue; fi
    remove "$f" codex "$label" && N_CODEX=$((N_CODEX + 1))
  done < <(find "$root" -type f -name '*.jsonl' -mtime +"$CODEX_DAYS" -print0 2>/dev/null)
  $APPLY && find "$root" -mindepth 1 -type d -empty -mtime +1 -delete 2>/dev/null
done

# ── log archive: gzipped rotations older than LOG_ARCHIVE_DAYS ─────────────────
if [ -d "$JH/logs/archive" ]; then
  while IFS= read -r -d '' f; do
    remove "$f" logarch "$(safe "${f#"$JH"/}")" && N_LOGARCH=$((N_LOGARCH + 1))
  done < <(find "$JH/logs/archive" -type f -name '*.gz' -mtime +"$LOG_ARCHIVE_DAYS" -print0 2>/dev/null)
fi

# ── qdrant backup retention: delegated to its own tested script, same mode ─────
QDRANT_RC=skipped
if [ -n "$QDRANT_RETENTION" ] && [ -f "$QDRANT_RETENTION" ]; then
  if $APPLY; then bash "$QDRANT_RETENTION" --apply >/dev/null 2>&1; else bash "$QDRANT_RETENTION" >/dev/null 2>&1; fi
  QDRANT_RC=$?; [ "$QDRANT_RC" -eq 0 ] || ERRORS=$((ERRORS + 1))
  log "qdrant: retention rc=$QDRANT_RC"
fi

# ── tool caches: only real tools, only their own safe prune verbs ───────────────
TOOLS_DONE=""
if [ "$TOOLS" = "true" ] && $APPLY; then
  if command -v uv >/dev/null 2>&1; then
    if pgrep -x uv >/dev/null 2>&1; then log "tools: uv cache prune skipped (a uv process holds the cache lock)"
    else uv cache prune >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE uv" || ERRORS=$((ERRORS + 1)); fi
  fi
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker image prune -f >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-image" || ERRORS=$((ERRORS + 1))
    docker volume prune -f >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-volume" || ERRORS=$((ERRORS + 1))
    docker builder prune -f --filter until=168h >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-builder" || ERRORS=$((ERRORS + 1))
  else
    log "tools: docker not reachable — skipped"
  fi
  if command -v brew >/dev/null 2>&1; then
    brew cleanup --prune=30 -s >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE brew" || ERRORS=$((ERRORS + 1))
  fi
  log "tools: done:${TOOLS_DONE:- none}"
elif [ "$TOOLS" = "true" ]; then
  log "tools: would run uv cache prune · docker image/volume/builder prune · brew cleanup --prune=30"
fi

DF_AVAIL=$(df -k /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $4*1024}')
DF_PCT=$(df -k /System/Volumes/Data 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
printf '{"ts":"%s","mode":"%s","host":"%s","freed_bytes":%s,"scratch":%s,"codex":%s,"logarch":%s,"qdrant_rc":"%s","tools":"%s","errors":%s,"data_avail_bytes":%s,"data_used_pct":%s}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$(hostname -s)" "$FREED" "$N_SCRATCH" "$N_CODEX" "$N_LOGARCH" \
  "$QDRANT_RC" "${TOOLS_DONE# }" "$ERRORS" "${DF_AVAIL:-0}" "${DF_PCT:-0}" >> "$JOURNAL"
log "done freed=${FREED}B scratch=$N_SCRATCH codex=$N_CODEX logarch=$N_LOGARCH errors=$ERRORS data_used=${DF_PCT:-?}%"
[ "$ERRORS" -eq 0 ]
