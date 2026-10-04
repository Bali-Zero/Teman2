#!/usr/bin/env bash
# qdrant_backup_retention.sh — independent retention guard for ~/backups/qdrant-snapshots
#
# WHY (cicatrix #2 — "esiste ≠ armato" / don't trust the producer's own green):
#   The two Qdrant backup producers already self-prune their OWN outputs inline:
#     * fly-qdrant-backup.sh:214 — keeps last 7 `qdrant-*.tar.gz`  (KEEP_LOCAL=7)
#     * qdrant-snapshot.sh:216   — keeps last 4 `<coll>_*.snapshot` per collection (KEEP_LOCAL=4)
#   Tigris S3 holds the authoritative REMOTE copies (KEEP_REMOTE=30), so local
#   pruning is a convenience-layer cleanup, never the sole DR copy.
#
#   This guard does NOT replace the producers. It is an INDEPENDENT daily backstop:
#     1. ORPHAN SWEEP (the one genuinely-uncovered growth vector) — session dirs
#        named `YYYYMMDD-HHMM/` left behind by a fly-qdrant-backup.sh run that
#        CRASHED between `mkdir "$SESSION_DIR"` (:63) and `rm -rf "$SESSION_DIR"`
#        (:171). NEITHER producer ever cleans an OLD orphan (fly only rm -rf's the
#        current run's dir). Observed live: `20260618-0308/` = 144 MB leaked.
#     2. BACKSTOP PRUNE — re-enforces the SAME thresholds as the producers, so if a
#        producer's inline prune silently breaks (xargs fail / KEEP misconfig /
#        producer stops running), drift is caught. In steady state this is a NO-OP.
#     3. FOOTPRINT READ — reports total bytes and WARNs past a soft cap (an
#        independent liveness read of real state, not a trust of the producer exit).
#
# Scope is HARD-LOCKED to a path ending in `/backups/qdrant-snapshots`. It never
# touches `fly-postgres/`, `postgres/`, or any sibling backup dir. It only ever
# removes files/dirs that match the exact producer-emitted name patterns.
#
# Usage:
#   qdrant_backup_retention.sh            # DRY-RUN (default): report only, remove nothing
#   qdrant_backup_retention.sh --apply    # act
# Kill switch:  QDRANT_RETENTION_ENABLED=false
# Test override: QDRANT_BACKUP_ROOT=/some/.../backups/qdrant-snapshots (must keep the suffix)
#
# Targets /bin/bash 3.2 (the only bash on the Pro/M5 fleet) — no bash-4 features.
set -euo pipefail

QDRANT_RETENTION_ENABLED="${QDRANT_RETENTION_ENABLED:-true}"
BACKUP_ROOT="${QDRANT_BACKUP_ROOT:-$HOME/backups/qdrant-snapshots}"
KEEP_TARGZ="${QDRANT_KEEP_TARGZ:-7}"              # mirror fly-qdrant-backup.sh KEEP_LOCAL
KEEP_SNAP_PER_COLL="${QDRANT_KEEP_SNAP:-4}"       # mirror qdrant-snapshot.sh   KEEP_LOCAL
ORPHAN_DIR_KEEP_DAYS="${QDRANT_ORPHAN_KEEP_DAYS:-14}"
SOFT_CAP_GB="${QDRANT_SOFT_CAP_GB:-12}"
LOG_FILE="${QDRANT_RETENTION_LOG:-$HOME/logs/qdrant-backup-retention.log}"

APPLY=false
[ "${1:-}" = "--apply" ] && APPLY=true

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null || true
ts()  { date +%Y-%m-%dT%H:%M:%S%z; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_FILE" >&2; }

# True if a Qdrant backup PRODUCER is currently running — we must not prune an
# in-flight session dir nor race a producer's concurrent mutation of the dir
# (neither producer takes a lock). Degrades to "not running" if pgrep is absent
# (not our fleet). Pattern overridable for tests via QDRANT_PRODUCER_PROC_RE.
producer_running() {
  command -v pgrep >/dev/null 2>&1 || return 1
  if [ -n "${QDRANT_PRODUCER_PROC_RE:-}" ]; then
    pgrep -f "$QDRANT_PRODUCER_PROC_RE" >/dev/null 2>&1 && return 0
    return 1
  fi
  pgrep -f 'fly-qdrant-backup' >/dev/null 2>&1 && return 0
  pgrep -f 'qdrant-snapshot'   >/dev/null 2>&1 && return 0
  return 1
}

# ── Kill switch ──────────────────────────────────────────────────────────────
enabled_lc=$(printf '%s' "$QDRANT_RETENTION_ENABLED" | tr 'A-Z' 'a-z')
case "$enabled_lc" in
  0|false|no|off) log "DISABLED via QDRANT_RETENTION_ENABLED=$QDRANT_RETENTION_ENABLED — exit 0"; exit 0 ;;
esac

# ── Scope guard (refuse anything not clearly the qdrant-snapshots backup dir) ──
case "$BACKUP_ROOT" in
  */backups/qdrant-snapshots) : ;;
  *) log "REFUSE: BACKUP_ROOT '$BACKUP_ROOT' does not end in /backups/qdrant-snapshots — exit 2"; exit 2 ;;
esac
if [ "$BACKUP_ROOT" = "$HOME" ] || [ "$BACKUP_ROOT" = "/" ] || [ -z "$BACKUP_ROOT" ]; then
  log "REFUSE: unsafe BACKUP_ROOT '$BACKUP_ROOT' — exit 2"; exit 2
fi

MODE="DRY-RUN"; $APPLY && MODE="APPLY"
log "=== qdrant-backup-retention START ($MODE) root=$BACKUP_ROOT keep_targz=$KEEP_TARGZ keep_snap/coll=$KEEP_SNAP_PER_COLL orphan_days=$ORPHAN_DIR_KEEP_DAYS ==="

# Sibling-race / TOCTOU guard: never prune while a producer is writing this dir.
if producer_running; then
  log "SKIP: a qdrant backup producer is running — retry next cron run — exit 0"; exit 0
fi

if [ ! -d "$BACKUP_ROOT" ]; then
  # Absent dir is a normal state (producers recreate it on next run; this session
  # archived+removed it 2026-07-19). Nothing to prune.
  log "root absent — nothing to do (producers recreate on next run) — exit 0"; exit 0
fi

removed_count=0
freed_bytes=0
traversed=0
refused=0
NL='
'
# Every deletion target is re-validated HERE, whatever enumerated it: the line-based `ls -t`
# readers below split a name carrying a newline into fragments that resolve against the
# CALLER's cwd (janitor council, codex N1). A refused target is kept, counted and fails the run.
target_ok() { # $1 path  $2 f|d
  case "$1" in *"$NL"*) log "  REFUSE (newline in name) $(tag "$1")"; refused=$((refused+1)); return 1 ;; esac
  case "$1" in "$BACKUP_ROOT"/*) : ;; *) log "  REFUSE (outside root) $(tag "$1")"; refused=$((refused+1)); return 1 ;; esac
  case "${1#"$BACKUP_ROOT"/}" in ''|.|..|*/*) log "  REFUSE (not a direct child) $(tag "$1")"; refused=$((refused+1)); return 1 ;; esac
  if [ -L "$1" ]; then log "  REFUSE (symlink) $(tag "$1")"; refused=$((refused+1)); return 1; fi
  if [ "$2" = f ] && [ ! -f "$1" ]; then log "  REFUSE (not a regular file) $(tag "$1")"; refused=$((refused+1)); return 1; fi
  if [ "$2" = d ] && [ ! -d "$1" ]; then log "  REFUSE (not a directory) $(tag "$1")"; refused=$((refused+1)); return 1; fi
  return 0
}

# Size via BSD `stat -f` first, GNU `stat -c` second — and ONLY a purely numeric answer is
# accepted: on GNU, `stat -f '%z'` succeeds and prints filesystem text (codex N5).
fsize() { local s; s=$(stat -f '%z' "$1" 2>/dev/null); case "$s" in ''|*[!0-9]*) s=$(stat -c '%s' "$1" 2>/dev/null) ;; esac
          case "$s" in ''|*[!0-9]*) s=0 ;; esac; printf '%s' "$s"; }
# `|| true` neutralises a find TOCTOU (a file vanishing mid-scan makes find exit non-zero →
# pipefail → set -e would abort AFTER deletes, defeating the guard).
dir_bytes() { { find "$1" -type f -print0 2>/dev/null || true; } | { local t=0 f; while IFS= read -r -d '' f; do t=$((t + $(fsize "$f"))); done; printf '%s' "$t"; }; }
# Output boundary (janitor council, codex N4): this log never carries a candidate's name —
# entries are logged as a 12-hex sha256 of the root-relative path.
tag() { printf '%s' "${1#"$BACKUP_ROOT"/}" | { shasum -a 256 2>/dev/null || sha256sum; } | cut -c1-12; }

remove_file() {
  f="$1"; why="$2"; target_ok "$f" f || return 0; b=$(fsize "$f")
  if $APPLY; then
    if rm -f "$f"; then
      log "  REMOVED [$why] $(tag "$f") (${b}B)"; removed_count=$((removed_count+1)); freed_bytes=$((freed_bytes+b))
    else
      log "  WARN could not remove $(tag "$f")"
    fi
  else
    log "  WOULD-REMOVE [$why] $(tag "$f") (${b}B)"; removed_count=$((removed_count+1)); freed_bytes=$((freed_bytes+b))
  fi
}

remove_dir() {
  d="$1"; why="$2"; target_ok "$d" d || return 0; b=$(dir_bytes "$d")
  if $APPLY; then
    # scope-safe recursive clear (never `rm -rf ~`): empty contents then rmdir
    find "$d" -mindepth 1 -delete 2>/dev/null || true
    if rmdir "$d" 2>/dev/null; then
      log "  REMOVED-DIR [$why] $(tag "$d")/ (${b}B)"; removed_count=$((removed_count+1)); freed_bytes=$((freed_bytes+b))
    else
      log "  WARN could not rmdir $(tag "$d")"
    fi
  else
    log "  WOULD-REMOVE-DIR [$why] $(tag "$d")/ (${b}B)"; removed_count=$((removed_count+1)); freed_bytes=$((freed_bytes+b))
  fi
}

# ── 1) ORPHAN session-dir sweep (the real uncovered vector) ──────────────────
# Only dirs whose name is exactly the producer TIMESTAMP format YYYYMMDD-HHMM,
# older than ORPHAN_DIR_KEEP_DAYS (dir mtime ≈ crash time). Anything else: skip.
while IFS= read -r d; do
  [ -z "$d" ] && continue
  traversed=$((traversed+1))
  remove_dir "$d" "orphan-session-dir >${ORPHAN_DIR_KEEP_DAYS}d"
done < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d \
              -name '[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9]' \
              -mtime +"$ORPHAN_DIR_KEEP_DAYS" 2>/dev/null | sort)

# The two backstops below order candidates with `ls -t`, which is line-based: ONE entry whose
# name carries a newline would be read as several — fragments that can collide with a real
# sibling inside the root or resolve outside it (codex N1/N3). Neither producer can emit such
# a name, so its presence is an anomaly: both backstops are refused, loudly, and the run fails.
if [ -n "$(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -name "*${NL}*" -print 2>/dev/null | head -c 1)" ]; then
  log "  REFUSE (newline-named entry in root — line-based backstops unsafe) $(tag "$BACKUP_ROOT")"; refused=$((refused+1))
  KEEP_TARGZ=999999999; KEEP_SNAP_PER_COLL=999999999   # nothing below can qualify
fi

# ── 2) BACKSTOP: qdrant-*.tar.gz keep newest KEEP_TARGZ (mirrors producer) ────
targz=()
while IFS= read -r line; do [ -n "$line" ] && targz+=("$line"); done < <(ls -t "$BACKUP_ROOT"/qdrant-*.tar.gz 2>/dev/null || true)
if [ "${#targz[@]}" -gt "$KEEP_TARGZ" ]; then
  idx=0
  for f in "${targz[@]}"; do
    if [ "$idx" -ge "$KEEP_TARGZ" ]; then traversed=$((traversed+1)); remove_file "$f" "tar.gz backstop keep-$KEEP_TARGZ"; fi
    idx=$((idx+1))
  done
fi

# ── 3) BACKSTOP: per-collection <coll>_*.snapshot keep newest KEEP_SNAP_PER_COLL
# Collection key = filename with trailing `_YYYYMMDD-HHMM.snapshot` stripped.
colls=()
while IFS= read -r line; do [ -n "$line" ] && colls+=("$line"); done < <(ls "$BACKUP_ROOT"/*_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].snapshot 2>/dev/null | sed -E 's|.*/||; s/_[0-9]{8}-[0-9]{4}\.snapshot$//' | sort -u || true)
if [ "${#colls[@]}" -gt 0 ]; then
  for coll in "${colls[@]}"; do
    [ -z "$coll" ] && continue
    snaps=()
    while IFS= read -r line; do [ -n "$line" ] && snaps+=("$line"); done < <(ls -t "$BACKUP_ROOT/${coll}"_[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]-[0-9][0-9][0-9][0-9].snapshot 2>/dev/null || true)
    if [ "${#snaps[@]}" -gt "$KEEP_SNAP_PER_COLL" ]; then
      idx=0
      for f in "${snaps[@]}"; do
        if [ "$idx" -ge "$KEEP_SNAP_PER_COLL" ]; then traversed=$((traversed+1)); remove_file "$f" "snapshot backstop keep-$KEEP_SNAP_PER_COLL/coll[$(tag "$BACKUP_ROOT/$coll")]"; fi
        idx=$((idx+1))
      done
    fi
  done
fi

# ── Footprint read (independent liveness, W84 blind-scan note) ────────────────
total_bytes=$(dir_bytes "$BACKUP_ROOT")
total_gb=$(awk -v b="$total_bytes" 'BEGIN{printf "%.2f", b/1073741824}')
if [ "$traversed" -eq 0 ]; then
  log "note: 0 prune-candidates traversed (dir present but nothing matched retention patterns)"
fi
cap_hit=""
if awk -v b="$total_bytes" -v cap="$SOFT_CAP_GB" 'BEGIN{exit !(b > cap*1073741824)}'; then
  cap_hit="  ⚠️ OVER SOFT CAP ${SOFT_CAP_GB}G"
fi
freed_gb=$(awk -v b="$freed_bytes" 'BEGIN{printf "%.2f", b/1073741824}')
verb="would-free"; $APPLY && verb="freed"
log "=== COMPLETE ($MODE): $removed_count candidate(s), $verb ${freed_gb}G — footprint now ${total_gb}G${cap_hit} ==="
[ "$refused" -eq 0 ] || { log "=== $refused target(s) REFUSED by the root guard — exit 1 ==="; exit 1; }
exit 0
