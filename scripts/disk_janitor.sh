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
#   tools     uv cache prune (skipped while a uv process holds the lock) · restic cache --cleanup
#             · brew cleanup --prune=30
# These tool steps land in the receipt's "steps" object with their own df -k delta on the Data volume.
# Docker and the Colima VM are not this janitor's: scripts/localci/prune.py is their one owner (images
# by explicit tag, never by age; it also trims the guest after every tick). Ruled 2026-10-10.
#
# Deliberately absent: anything that deletes a directory which is or may hold a git checkout
# (stale ~/.codex/worktrees) and the Chrome code-sign clones. Reclaiming a checkout needs a
# repository-shape proof that never converged (PR #7841); this janitor removes no git data.
#
# DRY-RUN by default: reports candidates, removes nothing. `--apply` acts.
# `--check-path P` prints OK|REFUSE for P against the protected set and exits (used by the test).
# Kill switch: DISK_JANITOR_ENABLED=false. Targets /bin/bash 3.2 (fleet default).
# Output boundary (council O7/R4): log lines never carry a candidate's name — scratch is logged
# by its session uuid, everything else by a 12-hex sha256 of the path relative to $HOME.
# Test: scripts/test_disk_janitor.sh.
set -uo pipefail

JH="${DISK_JANITOR_HOME:-$HOME}"
while [ "${JH%/}" != "$JH" ]; do JH="${JH%/}"; done   # a trailing slash would defeat the literal compare (kimi R-6)
[ -n "$JH" ] || { echo "disk-janitor: REFUSE: DISK_JANITOR_HOME resolves to / — exit 2" >&2; exit 2; }
TMP_ROOT="${DISK_JANITOR_TMP_ROOT:-/private/tmp/claude-501}"
SESSIONS_DIR="${DISK_JANITOR_SESSIONS_DIR:-$JH/.claude/sessions}"
LOG_FILE="${DISK_JANITOR_LOG:-$JH/logs/disk-janitor.log}"
JOURNAL="${DISK_JANITOR_JOURNAL:-$JH/logs/disk-janitor.receipts.jsonl}"
SCRATCH_DAYS="${DISK_JANITOR_SCRATCH_DAYS:-7}"
CODEX_DAYS="${DISK_JANITOR_CODEX_DAYS:-14}"
LOG_ARCHIVE_DAYS="${DISK_JANITOR_LOG_ARCHIVE_DAYS:-60}"
TOOLS="${DISK_JANITOR_TOOLS:-true}"
LSOF="${DISK_JANITOR_LSOF:-lsof}"
CACHE_TIMEOUT="${DISK_JANITOR_CACHE_TIMEOUT-600}"   # uv, restic, brew
DF_PATH="${DISK_JANITOR_DF_PATH:-/System/Volumes/Data}"; [ -d "$DF_PATH" ] || DF_PATH=/
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
  [ "$1" = "/" ] && return 0   # the root of everything is above every protected root (kimi R-6)
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
# The kill switch is read BEFORE the audit-trail probe: a disabled run deletes nothing, so the
# documented "DISABLED — exit 0" holds even on a host whose log is unwritable (kimi K4).
case "$(printf '%s' "${DISK_JANITOR_ENABLED:-true}" | tr 'A-Z' 'a-z')" in
  0|false|no|off) log "DISABLED via DISK_JANITOR_ENABLED — exit 0"; exit 0 ;;
esac
if ! { : >> "$LOG_FILE"; } 2>/dev/null || ! { : >> "$JOURNAL"; } 2>/dev/null; then
  echo "[$(ts)] disk-janitor[$MODE] REFUSE: log or receipts journal not writable — exit 2" >&2; exit 2
fi
# Age knobs are integers or the run refuses: `find -mtime +abc` lists nothing, and the step
# would no-op silently with errors=0 in the receipt (kimi K3).
for knob in SCRATCH_DAYS CODEX_DAYS LOG_ARCHIVE_DAYS; do
  case "${!knob}" in
    ''|*[!0-9]*) log "REFUSE: DISK_JANITOR_$knob must be a non-negative integer — exit 2"; exit 2 ;;
  esac
done
# The timeout is a plain decimal integer in a range: `0` is no timeout, `08` aborts bash
# arithmetic mid-run and `030` reads as octal, a 15-digit value
# overflows (review of #7859, F6). Refused before any step runs.
knob_range() { # $1 knob  $2 min  $3 max
  local v=${!1}
  case "$v" in ''|0*|*[!0-9]*) v="" ;; esac
  if [ -z "$v" ] || [ "${#v}" -gt 6 ] || [ "$v" -lt "$2" ] || [ "$v" -gt "$3" ]; then
    log "REFUSE: DISK_JANITOR_$1 must be a plain integer $2..$3 (no sign, no leading zero) — exit 2"; exit 2
  fi
}
for knob in CACHE_TIMEOUT; do knob_range "$knob" 1 86400; done

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
listable() { [ -d "$1" ] && [ -r "$1" ] && [ -x "$1" ]; }   # a root find cannot list would make its step no-op silently (kimi K3)
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
elif ! listable "$TMP_ROOT"; then
  ERRORS=$((ERRORS + 1)); log "scratch: root not listable — step skipped"
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
    if ! listable "$root"; then ERRORS=$((ERRORS + 1)); log "codex: root $(tag "$root") not listable — skipped"; continue; fi
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
if [ -d "$JH/logs/archive" ] && ! listable "$JH/logs/archive"; then
  ERRORS=$((ERRORS + 1)); log "logarch: root not listable — step skipped"
elif [ -d "$JH/logs/archive" ]; then
  while IFS= read -r -d '' f; do
    remove "$f" logarch "$(tag "$f")" && N_LOGARCH=$((N_LOGARCH + 1))
  done < <(find "$JH/logs/archive" -mindepth 1 -maxdepth 1 -type f -name '*.gz' -mtime +"$LOG_ARCHIVE_DAYS" -print0 2>/dev/null)
fi

# ── qdrant backup retention: delegated to its own tested script, same mode ─────
# The delegate's root is pinned here (never inherited from the environment) and passed through
# the same gate as every other target before the delegate runs (codex R1). Every other knob that
# decides WHAT the delegate deletes or whether it deletes at all is pinned to the delegate's own
# defaults too — an inherited QDRANT_KEEP_TARGZ=0 would prune every archive and an inherited
# QDRANT_RETENTION_ENABLED=false would no-op silently under rc=0 (kimi round 3); only the
# producer-liveness pattern stays inheritable, since steering it can only make the delegate
# skip, never delete more. Its audit log is pinned under the same HOME as ours.
QDRANT_RC=skipped
qdrant_run() { # $@ delegate args
  QDRANT_BACKUP_ROOT="$QROOT" QDRANT_RETENTION_ENABLED=true QDRANT_KEEP_TARGZ=7 QDRANT_KEEP_SNAP=4 \
  QDRANT_ORPHAN_KEEP_DAYS=14 QDRANT_RETENTION_LOG="$JH/logs/qdrant-backup-retention.log" \
  bash "$QDRANT_RETENTION" "$@" >/dev/null 2>&1
}
if [ -n "$QDRANT_RETENTION" ] && [ -f "$QDRANT_RETENTION" ]; then
  QROOT="$JH/backups/qdrant-snapshots"
  if is_protected "$QROOT" || has_protected_descendant "$QROOT"; then
    ERRORS=$((ERRORS + 1)); QDRANT_RC=refused; log "qdrant: REFUSE $(tag "$QROOT") (protected tree or descendant) — delegation skipped"
  else
    if $APPLY; then qdrant_run --apply; else qdrant_run; fi
    QDRANT_RC=$?; [ "$QDRANT_RC" -eq 0 ] || ERRORS=$((ERRORS + 1))
    log "qdrant: retention rc=$QDRANT_RC"
  fi
fi

# ── tool steps (2026-10-03 disk-relief spec §B): each one is a separate receipt step whose gain is
# the `df -k` delta on the Data volume across the step, never `du` — on APFS a clonefile copy
# (venvs) is counted whole by du and frees almost nothing.
STEPS=""; S_DF0=""; S_N=0
df_avail() { df -k "$DF_PATH" 2>/dev/null | awk 'NR==2{print $4*1024}'; }
step_begin() { S_DF0=$(df_avail); S_N=0; }
step_end() { # $1 step  $2 done|dry-run|skipped|error  $3 reason (optional, no path ever)
  local d1 delta=0; d1=$(df_avail)
  if $APPLY && [ -n "$S_DF0" ] && [ -n "$d1" ]; then delta=$((d1 - S_DF0)); fi
  STEPS="$STEPS${STEPS:+,}\"$1\":{\"status\":\"$2\",\"count\":$S_N,\"df_delta_bytes\":$delta${3:+,\"reason\":\"$3\"}}"
  log "$1: $2${3:+ ($3)} count=$S_N df_delta=${delta}B"
}
# bounded SECONDS CMD…: a real deadline (no coreutils timeout on stock macOS). `alarm`+`exec` is not one:
# Go binaries (restic) ignore SIGALRM. The parent forks, the child gets its own process
# group and /dev/null as stdin; at the deadline the group gets TERM, then KILL after 2 s. rc 124 = timed
# out, otherwise the command's rc (death by signal n reads 128+n).
bounded() {
  local s=$1; shift
  perl -e 'use POSIX ":sys_wait_h"; my $t = shift; my $p = fork; defined $p or exit 127;
    if (!$p) { setpgrp(0, 0); open STDIN, "<", "/dev/null"; exec { $ARGV[0] } @ARGV or exit 127 }
    my ($end, $r, $to) = (time + $t, 0, 0);
    until (($r = waitpid($p, WNOHANG)) != 0) {
      if (!$to && time >= $end) { $to = 1; kill "TERM", -$p; kill "TERM", $p; $end = time + 2 }
      elsif ($to && time >= $end) { kill "KILL", -$p; kill "KILL", $p; $r = waitpid($p, 0); last }
      select(undef, undef, undef, 0.1);
    }
    kill "KILL", -$p if $to;
    exit 124 if $to; exit 127 if $r < 0;
    exit($? & 127 ? 128 + ($? & 127) : $? >> 8);' "$s" "$@"
}
timeout_or() { [ "$2" -eq 124 ] && echo "$3" || echo "$1"; }   # $1 reason, $2 rc, $3 reason when rc is the bounded() timeout
# ── tool caches: only real tools, only their own safe prune verbs ───────────────
TOOLS_DONE=""; TOOLS_SEEN=""
if [ "$TOOLS" = "true" ]; then
  for t in uv brew restic; do command -v "$t" >/dev/null 2>&1 && TOOLS_SEEN="$TOOLS_SEEN $t"; done
  # Every external verb below runs through bounded() (a real deadline, TERM then KILL): a daily job
  # hung on one tool would skip every later day behind the wrapper's live-lock (status=warn) instead
  # of failing once, visibly. A timed-out step is an error with a named reason; later steps still run.
  # uv_cache_prune (skipped while a uv process holds the cache lock)
  step_begin
  if ! command -v uv >/dev/null 2>&1; then step_end uv_cache_prune skipped uv-absent
  elif pgrep -x uv >/dev/null 2>&1; then step_end uv_cache_prune skipped uv-lock-held
  elif ! $APPLY; then step_end uv_cache_prune dry-run
  else
    bounded "$CACHE_TIMEOUT" uv cache prune >/dev/null 2>&1; rc=$?
    if [ "$rc" -eq 0 ]; then S_N=1; TOOLS_DONE="$TOOLS_DONE uv"; step_end uv_cache_prune "done"
    else ERRORS=$((ERRORS + 1)); step_end uv_cache_prune error "$(timeout_or prune-failed "$rc" prune-timeout)"; fi
  fi
  # restic_cache_cleanup: removes only cache dirs restic itself considers stale; no repo needed
  step_begin
  if ! command -v restic >/dev/null 2>&1; then step_end restic_cache_cleanup skipped restic-absent
  elif ! $APPLY; then step_end restic_cache_cleanup dry-run
  else
    bounded "$CACHE_TIMEOUT" restic cache --cleanup >/dev/null 2>&1; rc=$?
    if [ "$rc" -eq 0 ]; then S_N=1; TOOLS_DONE="$TOOLS_DONE restic"; step_end restic_cache_cleanup "done"
    else ERRORS=$((ERRORS + 1)); step_end restic_cache_cleanup error "$(timeout_or cleanup-failed "$rc" cleanup-timeout)"; fi
  fi
  if $APPLY; then
    if command -v brew >/dev/null 2>&1; then
      bounded "$CACHE_TIMEOUT" brew cleanup --prune=30 -s >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE brew" || ERRORS=$((ERRORS + 1))
    else log "tools: brew not on PATH — skipped"; fi
    # No tool at all on PATH is not "nothing to do": it is the launchd-minimal-PATH failure mode
    # (kimi R-2) and the step would be dead forever under rc=0 — so it is an ERROR.
    if [ -z "$TOOLS_SEEN" ]; then ERRORS=$((ERRORS + 1)); log "tools: NO tool reachable on PATH — step dead, check the wrapper's PATH export"; fi
    log "tools: done:${TOOLS_DONE:- none}"
  else
    log "tools: would run brew cleanup --prune=30"
  fi
fi

DF_AVAIL=$(df -k "$DF_PATH" 2>/dev/null | awk 'NR==2{print $4*1024}')
DF_PCT=$(df -k "$DF_PATH" 2>/dev/null | awk 'NR==2{print $5}' | tr -d '%')
printf '{"ts":"%s","mode":"%s","host":"%s","freed_bytes":%s,"scratch":%s,"codex":%s,"logarch":%s,"qdrant_rc":"%s","tools":"%s","errors":%s,"data_avail_bytes":%s,"data_used_pct":%s,"steps":{%s}}\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$(hostname -s)" "$FREED" "$N_SCRATCH" "$N_CODEX" "$N_LOGARCH" \
  "$QDRANT_RC" "${TOOLS_DONE# }" "$ERRORS" "${DF_AVAIL:-0}" "${DF_PCT:-0}" "$STEPS" >> "$JOURNAL" \
  || { ERRORS=$((ERRORS + 1)); log "receipt append FAILED"; }
log "done freed=${FREED}B scratch=$N_SCRATCH codex=$N_CODEX logarch=$N_LOGARCH errors=$ERRORS data_used=${DF_PCT:-?}%"
[ "$ERRORS" -eq 0 ]
