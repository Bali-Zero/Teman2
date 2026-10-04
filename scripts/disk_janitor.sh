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
#   chrome    $DISK_JANITOR_CHROME_ROOT/*/*/X/com.google.Chrome.code_sign_clone/code_sign_clone.*
#             >1 d, never the newest of its parent, never one a process holds (lsof +D)
#   codexwt   ~/.codex/worktrees/<id>  >14 d with no file touched since, not a live session's cwd,
#             no process anchored below it; every git checkout found within 3 levels must be a
#             LINKED worktree (a standalone repository's refs and objects would die with it), not
#             locked, clean (untracked files count), and its HEAD on some branch/remote/tag ref.
#             Git probes run with --no-optional-locks: a probe that refreshes the index would
#             reset the 14-day clock it is judging.
#   tools     uv cache prune (skipped while a uv process holds the lock) · restic cache --cleanup
#             · docker image/volume prune (dangling / anonymous) · docker unused TAGGED images >30 d
#             no container descends from (per image, never `prune -a`: localci-candidate is pinned
#             by image ID in its plans and is never a candidate) · docker builder prune --filter
#             until=168h · colima fstrim LAST (guest, when running), so the blocks the docker steps
#             freed go back to the host in the same run · brew cleanup --prune=30
# v2 steps land in the receipt's "steps" object with their own df -k delta on the Data volume.
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
CHROME_ROOT="${DISK_JANITOR_CHROME_ROOT:-/private/var/folders}"
CHROME_DAYS="${DISK_JANITOR_CHROME_DAYS:-1}"
CODEX_WT_DAYS="${DISK_JANITOR_CODEX_WT_DAYS:-14}"
DOCKER_DAYS="${DISK_JANITOR_DOCKER_DAYS:-30}"
FSTRIM_TIMEOUT="${DISK_JANITOR_FSTRIM_TIMEOUT:-180}"
DOCKER_KEEP="localci-candidate ${DISK_JANITOR_DOCKER_KEEP:-}"   # extendable, never emptiable
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
for knob in SCRATCH_DAYS CODEX_DAYS LOG_ARCHIVE_DAYS CHROME_DAYS CODEX_WT_DAYS DOCKER_DAYS FSTRIM_TIMEOUT; do
  case "${!knob}" in
    ''|*[!0-9]*) log "REFUSE: DISK_JANITOR_$knob must be a non-negative integer — exit 2"; exit 2 ;;
  esac
done

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
remove() { # $1 path  $2 step  $3 label for the log  $4 "nodu": size is the step's df delta, not du
  local b
  if [ -z "$1" ] || [ "$1" = "/" ] || [ "$1" = "$JH" ]; then log "$2: REFUSE unsafe target — abort rc=2"; exit 2; fi
  if is_protected "$1"; then ERRORS=$((ERRORS + 1)); log "$2: REFUSE $3 (protected tree) — skipped"; return 1; fi
  if has_protected_descendant "$1"; then ERRORS=$((ERRORS + 1)); log "$2: REFUSE $3 (protected descendant) — skipped"; return 1; fi
  b=0; [ "${4:-}" = nodu ] || { b=$(bytes_of "$1"); b=${b:-0}; }
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

# ── v2 steps (2026-10-03 disk-relief spec §B): each one is a separate receipt step whose gain is
# the `df -k` delta on the Data volume across the step, never `du` — on APFS a clonefile copy
# (Chrome code-sign clones, venvs) is counted whole by du and frees almost nothing.
STEPS=""; S_DF0=""; S_N=0
df_avail() { df -k "$DF_PATH" 2>/dev/null | awk 'NR==2{print $4*1024}'; }
step_begin() { S_DF0=$(df_avail); S_N=0; }
step_end() { # $1 step  $2 done|dry-run|skipped|error  $3 reason (optional, no path ever)
  local d1 delta=0; d1=$(df_avail)
  if $APPLY && [ -n "$S_DF0" ] && [ -n "$d1" ]; then delta=$((d1 - S_DF0)); fi
  STEPS="$STEPS${STEPS:+,}\"$1\":{\"status\":\"$2\",\"count\":$S_N,\"df_delta_bytes\":$delta${3:+,\"reason\":\"$3\"}}"
  log "$1: $2${3:+ ($3)} count=$S_N df_delta=${delta}B"
}
bounded() { local s=$1; shift; perl -e 'alarm shift; exec @ARGV or exit 127' "$s" "$@"; }   # no coreutils timeout on stock macOS
dir_in_use() { # 0 = a process has its cwd or an open file below $1, 1 = none, 2 = cannot tell. Port of
  # agent_start.py::_worktree_has_live_process: lsof +D reports rc=1 both for "nothing" and for
  # "matches plus a descent warning", so a data line beyond the header means LIVE whatever the rc.
  local out rc; out=$(bounded 120 "$LSOF" +D "$1" 2>/dev/null); rc=$?
  # shellcheck disable=SC2143  # grep -q would SIGPIPE the producer, and pipefail reads that as "no match"
  [ -n "$(printf '%s\n' "$out" | grep -v '^COMMAND' | grep '[^[:space:]]')" ] && return 0
  [ "$rc" -le 1 ] && return 1; return 2
}
to_epoch() { date -j -f '%Y-%m-%d %H:%M:%S' "$1" +%s 2>/dev/null || date -d "$1" +%s 2>/dev/null; }
rgit() { # read-only git: never steered by an inherited GIT_* variable, never takes the index lock
  (unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
   bounded 120 git --no-optional-locks "$@")
}
wt_hold() { # $1 worktree dir → prints why it must be kept (empty = no git reason). Fail-closed:
  # any git answer it cannot read is a reason to keep.
  local g st
  while IFS= read -r -d '' g; do
    g=${g%/.git}
    if [ -d "$g/.git" ]; then echo "standalone repository"; return; fi
    st=$(rgit -C "$g" status --porcelain --untracked-files=normal 2>/dev/null) || { echo "git state unreadable"; return; }
    [ -n "$st" ] && { echo "uncommitted work"; return; }
    st=$(rgit -C "$g" rev-parse --absolute-git-dir 2>/dev/null) || { echo "git state unreadable"; return; }
    [ -e "$st/locked" ] && { echo "locked worktree"; return; }
    rgit -C "$g" rev-parse -q --verify HEAD >/dev/null 2>&1 || continue   # unborn HEAD: no commit to lose
    st=$(rgit -C "$g" for-each-ref --contains HEAD --count=1 --format=x refs/heads refs/remotes refs/tags 2>/dev/null) \
      || { echo "git state unreadable"; return; }
    [ -z "$st" ] && { echo "commits on no ref"; return; }
  done < <(find "$1" -maxdepth 3 -name .git -print0 2>/dev/null)
}

# R2 chrome_code_sign_clones: every Chrome relaunch leaves a code-sign clone of the app bundle.
# Only clones older than CHROME_DAYS, never the newest of its parent, never one a process holds.
step_begin
if ! command -v "$LSOF" >/dev/null 2>&1; then
  ERRORS=$((ERRORS + 1)); step_end chrome_code_sign_clones error lsof-unavailable
else
  for parent in "$CHROME_ROOT"/*/*/X/com.google.Chrome.code_sign_clone; do
    [ -d "$parent" ] || continue
    newest=$(ls -td -- "$parent"/code_sign_clone.* 2>/dev/null | head -1)
    while IFS= read -r -d '' c; do
      [ "$c" = "$newest" ] && { log "chrome_code_sign_clones: keep $(tag "$c") (newest)"; continue; }
      dir_in_use "$c"; r=$?
      [ "$r" -eq 0 ] && { log "chrome_code_sign_clones: keep $(tag "$c") (in use)"; continue; }
      [ "$r" -ne 1 ] && { ERRORS=$((ERRORS + 1)); log "chrome_code_sign_clones: probe failed rc=$r on $(tag "$c") — kept"; continue; }
      remove "$c" chrome_code_sign_clones "$(tag "$c")" nodu && S_N=$((S_N + 1))
    done < <(find "$parent" -mindepth 1 -maxdepth 1 -type d -name 'code_sign_clone.*' -mtime +"$CHROME_DAYS" -print0 2>/dev/null)
  done
  if $APPLY; then step_end chrome_code_sign_clones "done"; else step_end chrome_code_sign_clones dry-run; fi
fi

# R5 codex_stale_worktrees: ~/.codex/worktrees/<id> older than CODEX_WT_DAYS with no file touched
# since, not the cwd of a registered session, no process anchored below it, no uncommitted work.
step_begin
WT_ROOT="$JH/.codex/worktrees"
if [ ! -d "$WT_ROOT" ]; then step_end codex_stale_worktrees skipped root-absent
elif ! listable "$WT_ROOT"; then ERRORS=$((ERRORS + 1)); step_end codex_stale_worktrees error root-not-listable
elif ! command -v "$LSOF" >/dev/null 2>&1; then ERRORS=$((ERRORS + 1)); step_end codex_stale_worktrees error lsof-unavailable
else
  while IFS= read -r -d '' d; do
    t=$(tag "$d")
    [ -n "$(find "$d" -mtime -"$CODEX_WT_DAYS" -print -quit 2>/dev/null)" ] && { log "codex_stale_worktrees: keep $t (recent activity)"; continue; }
    session_live "$d"; lrc=$?
    [ "$lrc" -eq 0 ] && { log "codex_stale_worktrees: keep $t (session live)"; continue; }
    [ "$lrc" -ne 1 ] && { ERRORS=$((ERRORS + 1)); log "codex_stale_worktrees: keep $t (registry unreadable rc=$lrc)"; continue; }
    dir_in_use "$d"; r=$?
    [ "$r" -eq 0 ] && { log "codex_stale_worktrees: keep $t (process anchored)"; continue; }
    [ "$r" -ne 1 ] && { ERRORS=$((ERRORS + 1)); log "codex_stale_worktrees: probe failed rc=$r on $t — kept"; continue; }
    hold=$(wt_hold "$d")
    [ -n "$hold" ] && { log "codex_stale_worktrees: keep $t ($hold)"; continue; }
    remove "$d" codex_stale_worktrees "$t" nodu && S_N=$((S_N + 1))
  done < <(find "$WT_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime +"$CODEX_WT_DAYS" -print0 2>/dev/null)
  if $APPLY; then step_end codex_stale_worktrees "done"; else step_end codex_stale_worktrees dry-run; fi
fi

# ── tool caches: only real tools, only their own safe prune verbs ───────────────
TOOLS_DONE=""; TOOLS_SEEN=""
if [ "$TOOLS" = "true" ]; then
  for t in uv docker brew colima restic; do command -v "$t" >/dev/null 2>&1 && TOOLS_SEEN="$TOOLS_SEEN $t"; done
  # Every external verb is time-bounded: a daily job hung on one tool would skip every later day
  # behind the wrapper's live-lock (status=warn) instead of failing once, visibly.
  # R3 uv_cache_prune (skipped while a uv process holds the cache lock)
  step_begin
  if ! command -v uv >/dev/null 2>&1; then step_end uv_cache_prune skipped uv-absent
  elif pgrep -x uv >/dev/null 2>&1; then step_end uv_cache_prune skipped uv-lock-held
  elif ! $APPLY; then step_end uv_cache_prune dry-run
  elif bounded 600 uv cache prune >/dev/null 2>&1; then S_N=1; TOOLS_DONE="$TOOLS_DONE uv"; step_end uv_cache_prune "done"
  else ERRORS=$((ERRORS + 1)); step_end uv_cache_prune error prune-failed; fi
  # R4 restic_cache_cleanup: removes only cache dirs restic itself considers stale; no repo needed
  step_begin
  if ! command -v restic >/dev/null 2>&1; then step_end restic_cache_cleanup skipped restic-absent
  elif ! $APPLY; then step_end restic_cache_cleanup dry-run
  elif bounded 600 restic cache --cleanup >/dev/null 2>&1; then S_N=1; TOOLS_DONE="$TOOLS_DONE restic"; step_end restic_cache_cleanup "done"
  else ERRORS=$((ERRORS + 1)); step_end restic_cache_cleanup error cleanup-failed; fi
  if $APPLY && command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    docker image prune -f >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-image" || ERRORS=$((ERRORS + 1))
    docker volume prune -f >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-volume" || ERRORS=$((ERRORS + 1))
    docker builder prune -f --filter until=168h >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE docker-builder" || ERRORS=$((ERRORS + 1))
  fi
  # R6 docker_unused_images: tagged images older than DOCKER_DAYS that no container (running or
  # stopped) descends from. NOT `image prune -a`: localci-candidate is pinned by image ID in the
  # local-CI plans and a rebuilt image is refused there, so its repository is never a candidate.
  step_begin
  if ! command -v docker >/dev/null 2>&1; then step_end docker_unused_images skipped docker-absent
  elif ! bounded 60 docker info >/dev/null 2>&1; then step_end docker_unused_images skipped docker-unreachable
  elif ! imgs=$(docker image ls --format '{{.ID}}|{{.Repository}}|{{.Tag}}|{{.CreatedAt}}' 2>/dev/null); then
    ERRORS=$((ERRORS + 1)); step_end docker_unused_images error list-failed
  else
    cutoff=$(( $(date +%s) - DOCKER_DAYS * 86400 ))
    while IFS='|' read -r id repo tg created; do
      [ -n "$id" ] || continue
      case " $DOCKER_KEEP " in *" $repo "*) log "docker_unused_images: keep $(tag "$repo") (pinned repository)"; continue ;; esac
      ep=$(to_epoch "${created:0:19}") || ep=""
      [ -n "$ep" ] || { log "docker_unused_images: keep $(tag "$id") (age unreadable)"; continue; }
      [ "$ep" -lt "$cutoff" ] || continue
      users=$(docker ps -a -q --filter "ancestor=$id" 2>/dev/null) || { log "docker_unused_images: keep $(tag "$id") (container probe failed)"; continue; }
      [ -n "$users" ] && { log "docker_unused_images: keep $(tag "$id") (used by a container)"; continue; }
      ref="$id"; [ "$repo" != "<none>" ] && [ "$tg" != "<none>" ] && ref="$repo:$tg"
      if ! $APPLY; then S_N=$((S_N + 1)); log "docker_unused_images: would remove $(tag "$ref")"
      elif docker image rm "$ref" >/dev/null 2>&1; then S_N=$((S_N + 1)); log "docker_unused_images: removed $(tag "$ref")"
      else ERRORS=$((ERRORS + 1)); log "docker_unused_images: FAILED to remove $(tag "$ref")"; fi
    done < <(printf '%s\n' "$imgs")
    if $APPLY; then step_end docker_unused_images "done"; else step_end docker_unused_images dry-run; fi
  fi
  # R1 colima_fstrim, AFTER the docker steps: the guest discards the blocks they just freed and vz
  # punches the matching holes in the host datadisk (idempotent; ~13 GiB measured 2026-10-03).
  step_begin
  if ! command -v colima >/dev/null 2>&1; then step_end colima_fstrim skipped colima-absent
  elif ! bounded 60 colima status 2>&1 | grep -qi 'colima is running'; then step_end colima_fstrim skipped colima-not-running
  elif ! $APPLY; then step_end colima_fstrim dry-run
  elif bounded "$FSTRIM_TIMEOUT" colima ssh -- sudo fstrim -av >/dev/null 2>&1; then S_N=1; TOOLS_DONE="$TOOLS_DONE colima-fstrim"; step_end colima_fstrim "done"
  else ERRORS=$((ERRORS + 1)); step_end colima_fstrim error fstrim-failed-or-timeout; fi
  if $APPLY; then
    if command -v brew >/dev/null 2>&1; then
      brew cleanup --prune=30 -s >/dev/null 2>&1 && TOOLS_DONE="$TOOLS_DONE brew" || ERRORS=$((ERRORS + 1))
    else log "tools: brew not on PATH — skipped"; fi
    # No tool at all on PATH is not "nothing to do": it is the launchd-minimal-PATH failure mode
    # (kimi R-2) and the step would be dead forever under rc=0 — so it is an ERROR.
    if [ -z "$TOOLS_SEEN" ]; then ERRORS=$((ERRORS + 1)); log "tools: NO tool reachable on PATH — step dead, check the wrapper's PATH export"; fi
    log "tools: done:${TOOLS_DONE:- none}"
  else
    log "tools: would run docker image/volume/builder prune (dangling only) · brew cleanup --prune=30"
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
