#!/usr/bin/env bash
# disk_janitor.sh — bounded, allowlisted disk hygiene for Pro (payload of organ pro.disk_janitor).
#
# Why: Pro's Data volume reached 97 % on 2026-09-29 and every reclaim was a hand-run session.
# scripts/disk_watchdog.sh only ALERTS (Telegram at >85 %); scripts/qdrant_backup_retention.sh
# exists but nothing scheduled it. The accumulators that grow without an owner are all
# machine-generated and reproducible, so this janitor prunes them on a schedule and
# journals every run. It NEVER touches data that a human produced or that carries PII:
#   ~/Desktop/OSINT-Nexus, ~/wa-mirror-media, ~/backups/fly-postgres, any path with a
#   *PII-Quarantine* component, ~/.nuzantara-pilots (evidence), ~/nuzantara/.worktrees
#   (broker-owned), ~/.ollama, ~/.colima (VM disk), ~/.cache/huggingface (model weights),
#   ~/.claude/backups (memory DB), ~/.claude/projects (transcripts + memory).
# Those are not "skipped": they are never a target, and is_protected() (exact roots — literal
# and physical — plus the PII component, no temp files, no I/O; council O1/R1) makes any
# computed target under one, or ABOVE one, an ERROR that skips the item and lets the rest of
# the run proceed; the receipt carries errors>0 and the run exits 1.
#
# Targets (each step has its own env knob; ages in days via `find -mtime +N`: "more than N days"
# with platform rounding — BSD find rounds the age up, GNU truncates — so the exact boundary
# differs by up to a day; fixtures sit well inside (N-1 vs N+3) and never on it — codex R6):
#   scratch   $DISK_JANITOR_TMP_ROOT/-<project>/<session-uuid>  parent starts with "-", child is a
#             uuid (council O2), older than 7 d, uuid not registered in ~/.claude/sessions; the step
#             is skipped (ERROR) when that registry is absent or empty (council O4, fail-closed)
#   codex     ~/.codex/{sessions,archived_sessions}/**/*.jsonl  >14 d and not open; the step is
#             skipped (ERROR) when the open-file probe (lsof) is unavailable or fails (council R5)
#   logarch   ~/logs/archive/*.gz  (direct children only)       >60 d (log-rotate-run.sh gzips, nothing pruned)
#   qdrant    scripts/qdrant_backup_retention.sh                  delegated, same --apply mode
#   tools     uv cache prune (skipped while a uv process holds the lock) · docker image/volume prune
#             (dangling / anonymous only, NEVER -a: localci-candidate:1 is pinned by image ID in its plans)
#             · docker builder prune --filter until=168h · brew cleanup --prune=30
#
# DRY-RUN by default: reports candidates, removes nothing. `--apply` acts.
# `--check-path P` prints OK|REFUSE for P against the protected set and exits (used by the test).
# Kill switch: DISK_JANITOR_ENABLED=false. Targets /bin/bash 3.2 (fleet default).
# Output boundary (council O7/R4): log lines never carry a candidate's name — scratch is logged
# by its session uuid, everything else by a 12-hex sha256 of the path relative to $HOME.
# Test: scripts/test_disk_janitor.sh.
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
LSOF="${DISK_JANITOR_LSOF:-lsof}"
QDRANT_RETENTION="${DISK_JANITOR_QDRANT_RETENTION-$(cd "$(dirname "$0")" && pwd)/qdrant_backup_retention.sh}"

# Protected roots (exact path or anything below it) + one name-based component. Arrays, not a
# here-document: a here-document needs a temp file and bash falls through when it cannot make
# one (council R1), which would have read as "not protected".
PROTECTED_ROOTS=(
  "$JH/Desktop/OSINT-Nexus" "$JH/wa-mirror-media" "$JH/backups/fly-postgres"
  "$JH/.nuzantara-pilots" "$JH/nuzantara/.worktrees" "$JH/.ollama" "$JH/.colima"
  "$JH/.cache/huggingface" "$JH/.claude/backups" "$JH/.claude/projects"
)
PROTECTED_COMPONENT="PII-Quarantine"

physical() { # physical path of an existing dir / of a file's parent; empty when unresolvable
  local d b
  if [ -d "$1" ]; then (cd -- "$1" 2>/dev/null && pwd -P)
  else d=$(dirname -- "$1"); b=$(basename -- "$1"); (cd -- "$d" 2>/dev/null && printf '%s/%s' "$(pwd -P)" "$b"); fi
}
under_or_above() { # $1 path, $2 root → 0 when path is the root, below it, or an ancestor of it
  case "$1" in "$2"|"$2"/*) return 0 ;; esac
  case "$2" in "$1"/*) return 0 ;; esac
  return 1
}
lc() { printf '%s' "$1" | tr 'A-Z' 'a-z'; }
is_protected() { # 0 = protected (under a root, above a root, or carrying the PII component);
                 # every comparison is made case-folded (APFS is case-insensitive) on the literal
                 # AND the physical form of both sides, so a symlinked protected root is also
                 # protected at its physical location
  local p c r rp comp
  p=$(lc "$1"); c=$(lc "$(physical "$1")"); comp=$(lc "$PROTECTED_COMPONENT")
  case "$p" in *"$comp"*) return 0 ;; esac
  case "$c" in *"$comp"*) return 0 ;; esac
  for r in "${PROTECTED_ROOTS[@]}"; do
    rp=""; [ -d "$r" ] && rp=$(physical "$r")
    r=$(lc "$r"); rp=$(lc "$rp")
    under_or_above "$p" "$r" && return 0
    [ -n "$c" ] && under_or_above "$c" "$r" && return 0
    if [ -n "$rp" ] && [ "$rp" != "$r" ]; then
      under_or_above "$p" "$rp" && return 0
      [ -n "$c" ] && under_or_above "$c" "$rp" && return 0
    fi
  done
  return 1
}
if [ "${1:-}" = "--check-path" ]; then
  [ -n "${2:-}" ] || { echo "usage: --check-path P" >&2; exit 64; }
  if is_protected "$2"; then echo "REFUSE"; exit 3; else echo "OK"; exit 0; fi
fi

APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true
MODE=DRY-RUN; $APPLY && MODE=APPLY

ts()  { date +%Y-%m-%dT%H:%M:%S%z; }
log() { echo "[$(ts)] disk-janitor[$MODE] $*" | tee -a "$LOG_FILE" >&2; }
tag() { printf '%s' "${1#"$JH"/}" | shasum -a 256 | cut -c1-12; }   # relative path → 12-hex, never the name
# The audit trail is the organ's promise: an unwritable log or journal ends the run before any
# deletion (codex R4), and a failed receipt append at the end makes the run fail visibly.
mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$JOURNAL")" 2>/dev/null
if ! { : >> "$LOG_FILE"; } 2>/dev/null || ! { : >> "$JOURNAL"; } 2>/dev/null; then
  echo "[$(ts)] disk-janitor[$MODE] REFUSE: log or receipts journal not writable — exit 2" >&2; exit 2
fi

case "$(printf '%s' "${DISK_JANITOR_ENABLED:-true}" | tr 'A-Z' 'a-z')" in
  0|false|no|off) log "DISABLED via DISK_JANITOR_ENABLED — exit 0"; exit 0 ;;
esac

# The scratch root is the one target that can be pointed elsewhere by env/plist (council O3/R2):
# absolute, basename exactly claude-<digits>, no "." or ".." components, and — when it exists —
# its physical path must equal the literal (no symlink anywhere in the chain).
tmp_root_ok() {
  case "$1" in /*) : ;; *) return 1 ;; esac
  case "$1/" in */./*|*/../*|*//*) return 1 ;; esac
  [[ "$(basename -- "$1")" =~ ^claude-[0-9]+$ ]] || return 1
  if [ -e "$1" ]; then [ ! -L "$1" ] || return 1; [ "$(physical "$1")" = "$1" ] || return 1; fi
  return 0
}
if ! tmp_root_ok "$TMP_ROOT"; then log "REFUSE: DISK_JANITOR_TMP_ROOT must be an absolute, canonical path whose basename is claude-<uid> — exit 2"; exit 2; fi

FREED=0; ERRORS=0
N_SCRATCH=0; N_CODEX=0; N_LOGARCH=0
bytes_of() { du -sk -- "$1" 2>/dev/null | head -1 | awk '{print $1*1024}' | tr -d '\n'; }
has_protected_descendant() { # a directory target must not carry the PII component anywhere below it (codex R1)
  [ -d "$1" ] || return 1
  [ -n "$(find "$1" -iname "*${PROTECTED_COMPONENT}*" -print -quit 2>/dev/null)" ]
}
remove() { # $1 path  $2 step  $3 label for the log
  local b
  if [ -z "$1" ] || [ "$1" = "/" ] || [ "$1" = "$JH" ]; then log "$2: REFUSE unsafe target — abort rc=2"; exit 2; fi
  if is_protected "$1"; then ERRORS=$((ERRORS + 1)); log "$2: REFUSE $3 (protected tree) — skipped"; return 1; fi
  if has_protected_descendant "$1"; then ERRORS=$((ERRORS + 1)); log "$2: REFUSE $3 (protected descendant) — skipped"; return 1; fi
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
session_live() { # 0 = registered (live), 1 = not registered, 2 = registry unreadable (codex R2: never "dead")
  grep -rlq -- "$1" "$SESSIONS_DIR" 2>/dev/null; local rc=$?
  [ "$rc" -le 1 ] && return "$rc"; return 2
}

# ── scratch: $TMP_ROOT/-<project>/<session-uuid> ───────────────────────────────
if [ ! -d "$TMP_ROOT" ]; then
  log "scratch: root absent — nothing to do"
elif [ ! -d "$SESSIONS_DIR" ] || [ -z "$(find "$SESSIONS_DIR" -maxdepth 1 -name '*.json' -print -quit 2>/dev/null)" ]; then
  ERRORS=$((ERRORS + 1)); log "scratch: session registry absent or empty — step skipped (cannot tell live from dead)"
else
  while IFS= read -r -d '' d; do
    u=${d##*/}; pp=${d%/*}; p=${pp##*/}   # parameter expansion, not $(basename): a trailing newline must survive into the regex (codex R2)
    case "$p" in -*) : ;; *) log "scratch: keep $(tag "$d") (not a project dir)"; continue ;; esac
    [[ "$u" =~ $UUID_RE ]] || { log "scratch: keep $(tag "$d") (not a session uuid)"; continue; }
    session_live "$u"; lrc=$?
    [ "$lrc" -eq 0 ] && { log "scratch: keep $u (session live)"; continue; }
    [ "$lrc" -ne 1 ] && { ERRORS=$((ERRORS + 1)); log "scratch: keep $u (registry unreadable rc=$lrc)"; continue; }
    remove "$d" scratch "$u" && N_SCRATCH=$((N_SCRATCH + 1))
  done < <(find "$TMP_ROOT" -mindepth 2 -maxdepth 2 -type d -mtime +"$SCRATCH_DAYS" -print0 2>/dev/null)
fi

# ── codex sessions: transcripts older than CODEX_DAYS, never an open file ───────
# lsof: rc 0 = open (keep), rc 1 = not open (candidate), anything else or no lsof = cannot tell
# → the whole step is skipped as an ERROR (fail-closed, council R5).
if ! command -v "$LSOF" >/dev/null 2>&1; then
  ERRORS=$((ERRORS + 1)); log "codex: open-file probe '$LSOF' unavailable — step skipped"
else
  for root in "$JH/.codex/sessions" "$JH/.codex/archived_sessions"; do
    [ -d "$root" ] || continue
    if is_protected "$root"; then ERRORS=$((ERRORS + 1)); log "codex: root $(tag "$root") is protected — skipped"; continue; fi
    while IFS= read -r -d '' f; do
      "$LSOF" -- "$f" >/dev/null 2>&1; lrc=$?
      if [ "$lrc" -eq 0 ]; then log "codex: keep $(tag "$f") (open)"; continue; fi
      if [ "$lrc" -ne 1 ]; then ERRORS=$((ERRORS + 1)); log "codex: probe failed rc=$lrc on $(tag "$f") — kept"; continue; fi
      remove "$f" codex "$(tag "$f")" && N_CODEX=$((N_CODEX + 1))
    done < <(find "$root" -type f -name '*.jsonl' -mtime +"$CODEX_DAYS" -print0 2>/dev/null)
    if $APPLY; then   # empty-dir sweep goes through the same gate as every deletion (codex R1)
      while IFS= read -r -d '' e; do
        if is_protected "$e"; then ERRORS=$((ERRORS + 1)); log "codex: REFUSE empty dir $(tag "$e") (protected tree) — skipped"; continue; fi
        rmdir -- "$e" 2>/dev/null || true
      done < <(find "$root" -mindepth 1 -depth -type d -empty -mtime +1 -print0 2>/dev/null)
    fi
  done
fi

# ── log archive: gzipped rotations older than LOG_ARCHIVE_DAYS ─────────────────
if [ -d "$JH/logs/archive" ]; then
  while IFS= read -r -d '' f; do
    remove "$f" logarch "$(tag "$f")" && N_LOGARCH=$((N_LOGARCH + 1))
  done < <(find "$JH/logs/archive" -mindepth 1 -maxdepth 1 -type f -name '*.gz' -mtime +"$LOG_ARCHIVE_DAYS" -print0 2>/dev/null)
fi

# ── qdrant backup retention: delegated to its own tested script, same mode ─────
# The delegate's root is pinned here (never inherited from the environment) and passed through
# the same gate as every other target before the delegate runs (codex R1).
QDRANT_RC=skipped
if [ -n "$QDRANT_RETENTION" ] && [ -f "$QDRANT_RETENTION" ]; then
  QROOT="$JH/backups/qdrant-snapshots"
  if is_protected "$QROOT" || has_protected_descendant "$QROOT"; then
    ERRORS=$((ERRORS + 1)); QDRANT_RC=refused; log "qdrant: REFUSE $(tag "$QROOT") (protected tree or descendant) — delegation skipped"
  else
    if $APPLY; then QDRANT_BACKUP_ROOT="$QROOT" bash "$QDRANT_RETENTION" --apply >/dev/null 2>&1
    else QDRANT_BACKUP_ROOT="$QROOT" bash "$QDRANT_RETENTION" >/dev/null 2>&1; fi
    QDRANT_RC=$?; [ "$QDRANT_RC" -eq 0 ] || ERRORS=$((ERRORS + 1))
    log "qdrant: retention rc=$QDRANT_RC"
  fi
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
  "$QDRANT_RC" "${TOOLS_DONE# }" "$ERRORS" "${DF_AVAIL:-0}" "${DF_PCT:-0}" >> "$JOURNAL" \
  || { ERRORS=$((ERRORS + 1)); log "receipt append FAILED"; }
log "done freed=${FREED}B scratch=$N_SCRATCH codex=$N_CODEX logarch=$N_LOGARCH errors=$ERRORS data_used=${DF_PCT:-?}%"
[ "$ERRORS" -eq 0 ]
