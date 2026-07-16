#!/bin/bash
# Pro-side periodic git pull for ~/nuzantara (the interactive/dev main checkout).
#
# WHY THIS EXISTS (root-cause 2026-07-16): Pro's ~/nuzantara had NO automated
# origin/main sync since the nuz-sync LaunchAgents were archived 2026-05-05. It
# stayed current only as a side-effect of interactive Claude sessions pulling; when
# session activity paused (2026-07-15) it drifted 66 commits behind, so cron jobs
# that exec from the main checkout ran ~2-day-stale code. Mini has
# com.nuzantara.git-pull-main.5min; Pro had no equivalent. This restores it.
#
# TWO WAYS IT DIFFERS FROM scripts/mini/mini-git-pull.sh (both deliberate):
#
#  1. UNTRACKED COLLISIONS ARE RESOLVED, NOT SKIPPED. Pro's pipelines write runtime
#     artifacts (research/*, apps/*/output/, docs/AUTOMATIONS_REFERENCE.md,
#     shared/*.jsonl) as untracked files into TRACKED dirs; the same artifacts arrive
#     on main via other machines, so an incoming tracked path collides with the local
#     untracked (or .gitignore-ignored!) file and a plain `git merge --ff-only` would
#     abort forever. Mini SKIPS such a tick (its collisions are sibling WIP that self-
#     resolves); on Pro they never self-resolve, so it MOVES the colliding path aside
#     to a timestamped, PID-unique, no-clobber backup and proceeds. Move-aside is
#     Law-5-safe by RECOVERABILITY (nothing deleted; every move logged + alerted).
#     NOTE: ignored files are covered too — `git merge --ff-only` SILENTLY overwrites
#     an ignored untracked file (verified 2026-07-16), so `--exclude-standard` is the
#     WRONG lens; we test each incoming path for "exists on disk ∧ not tracked".
#
#  2. TRACKED-DIRTY = SKIP, NEVER STASH. If the working tree has uncommitted TRACKED
#     changes, that is almost certainly a sibling session's WIP (sessions run in
#     .worktrees/, so the main checkout is dirty only from the operator or a stray).
#     Stashing it — Mini's approach — is the exact Law-5 violation, and stash/pop on a
#     shared checkout can apply/drop ANOTHER session's stash. So we SKIP + alert and
#     let sync resume once the tree is clean. No stash logic at all.
#
# EXECUTION LOCATION: run from ~/nuzantara-deploy (kept current by the deploy-puller),
# NOT from ~/nuzantara — a puller must not live in the tree it rewrites (self-mod).
# TARGET is $HOME/nuzantara; only origin/main (Pro pushes straight to GitHub).
#
# FAIL-SAFE INVARIANT: every error path leaves the repo untouched or recoverable and
# retries next tick. Known accepted stalls (abort + alert, never data-loss): a local
# untracked FILE named like an incoming DIRECTORY (file/dir conflict), or a path with
# a literal newline in its name (git C-quotes it → mv fails). Both are visible.
#
# Cron: StartInterval on the Pro LaunchAgent (com.nuzantara.git-pull-main.15min).
# Log:  ~/logs/pro-git-pull.log   Backups: ~/.git-pull-collision-backup/<ts>-<pid>/

set -u

REPO="${PRO_GIT_PULL_REPO:-$HOME/nuzantara}"
LOG_FILE="${PRO_GIT_PULL_LOG:-$HOME/logs/pro-git-pull.log}"
LOCK_DIR="${PRO_GIT_PULL_LOCK:-/tmp/pro-git-pull.lock.d}"
BACKUP_ROOT="${PRO_GIT_PULL_BACKUP_ROOT:-$HOME/.git-pull-collision-backup}"
LOCK_STALE_SECONDS=1800
TELEGRAM_ALERT_COOLDOWN=3600
TELEGRAM_STATE_DIR="$HOME/.agent/decisions/state"

mkdir -p "$(dirname "$LOG_FILE")" "$TELEGRAM_STATE_DIR" 2>/dev/null

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

telegram_alert() {
  [ "${PRO_GIT_PULL_NO_ALERT:-0}" = "1" ] && return 0  # hermetic test / dry mode
  local key="$1" message="$2"
  local state_file="$TELEGRAM_STATE_DIR/pro-git-pull-alert-${key}.ts"
  local now last_ts
  now=$(date +%s)
  if [ -f "$state_file" ]; then
    last_ts=$(cat "$state_file" 2>/dev/null || echo 0)
    [[ "$last_ts" =~ ^[0-9]+$ ]] || last_ts=0          # set -u / arithmetic-injection guard
    [ $((now - last_ts)) -lt "$TELEGRAM_ALERT_COOLDOWN" ] && return 0
  fi
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set +u; set -a; source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true; set +a; set -u
  fi
  local token="${TELEGRAM_BOT_TOKEN:-}" chat="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  [ -z "$token" ] && { log "  (telegram skipped — no TELEGRAM_BOT_TOKEN)"; return 0; }
  curl -s --max-time 8 "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" -d "text=[pro-git-pull] ${message}" >/dev/null 2>&1 || true
  echo "$now" > "$state_file"
}

# Atomic single-instance lock via mkdir (POSIX-atomic). Steals a lock older than
# LOCK_STALE_SECONDS (crash leftover). Returns 0 if acquired, 1 if a live peer holds it.
acquire_lock() {
  if mkdir "$LOCK_DIR" 2>/dev/null; then echo $$ > "$LOCK_DIR/pid" 2>/dev/null; return 0; fi
  local now mtime age
  now=$(date +%s)
  mtime=$(stat -f %m "$LOCK_DIR" 2>/dev/null || echo "$now")
  age=$(( now - mtime ))
  if [ "$age" -gt "$LOCK_STALE_SECONDS" ]; then
    log "Stale lock ${age}s old, stealing"
    rm -rf "$LOCK_DIR"
    if mkdir "$LOCK_DIR" 2>/dev/null; then echo $$ > "$LOCK_DIR/pid" 2>/dev/null; return 0; fi
  fi
  return 1
}

# Move aside any local on-disk path that collides with an incoming tracked path
# (exists locally ∧ not tracked → untracked OR ignored). Per-incoming-path (the
# incoming set is small and its names are clean git history) so a huge ignore tree
# is never enumerated and weird LOCAL filenames never get parsed as text.
# Returns 0 on success (incl. nothing to do); 1 on ANY mv/mkdir failure (fail-safe:
# caller then skips the merge, leaving everything recoverable).
resolve_untracked_collisions() {
  local changed f backup moved=0 first="" ts
  changed=$(git -c core.quotepath=false diff --name-only HEAD "$REMOTE" 2>/dev/null)
  [ -z "$changed" ] && return 0
  ts="$(date '+%Y%m%d-%H%M%S')-$$"
  backup="$BACKUP_ROOT/$ts"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    [ -e "$REPO/$f" ] || continue                                  # incoming path absent locally
    git ls-files --error-unmatch -- "$f" >/dev/null 2>&1 && continue  # tracked → not a collision
    if ! mkdir -p "$backup/$(dirname "$f")" 2>>"$LOG_FILE"; then
      log "  ERROR: mkdir backup dir failed for $f — aborting tick (fail-safe)"; return 1
    fi
    if mv -n "$REPO/$f" "$backup/$f" 2>>"$LOG_FILE" && [ ! -e "$REPO/$f" ]; then
      moved=$((moved + 1)); [ -z "$first" ] && first="$f"
      log "  moved colliding path -> $backup/$f"
    else
      log "  ERROR: mv failed / backup dest existed for $f — aborting tick (fail-safe)"; return 1
    fi
  done < <(printf '%s\n' "$changed")

  if [ "$moved" -gt 0 ]; then
    log "Relocated $moved colliding path(s) to $backup (recoverable)."
    telegram_alert "untracked-collision" \
      "Pro pull: moved ${moved} colliding untracked/ignored path(s) aside to ${backup} (e.g. ${first}). Runtime artifacts by design; restore from backup if one was real WIP."
  fi
  return 0
}

# ===== MAIN =====
if ! acquire_lock; then exit 0; fi           # a live peer is running — silent skip
trap 'rm -rf "$LOCK_DIR"' EXIT

cd "$REPO" 2>/dev/null || { log "FATAL: $REPO not found"; exit 1; }
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-/usr/bin:/bin}"

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$BRANCH" != "main" ]; then log "On branch '$BRANCH' (not main), skip"; exit 0; fi

if ! git fetch --quiet origin main 2>>"$LOG_FILE"; then
  log "git fetch origin failed (network?), skip"
  telegram_alert "fetch-failed" "Pro could not fetch origin/main. Sync skipped."
  exit 0
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse FETCH_HEAD 2>/dev/null)   # OID we validated; merge targets THIS, not the moving ref
[ -z "$REMOTE" ] && REMOTE=$(git rev-parse origin/main 2>/dev/null)
[ "$LOCAL" = "$REMOTE" ] && exit 0               # up to date — silent

# Not fast-forwardable → do NOT touch. Either local is ahead (unpushed work) or diverged.
if ! git merge-base --is-ancestor HEAD "$REMOTE" 2>/dev/null; then
  if git merge-base --is-ancestor "$REMOTE" HEAD 2>/dev/null; then
    log "Local main ahead of origin; skip"; exit 0
  fi
  log "WARN: HEAD diverged from origin (local=$LOCAL remote=$REMOTE); skip"
  telegram_alert "diverged" "Pro main HEAD diverged from origin/main (${LOCAL:0:9} vs ${REMOTE:0:9}). Manual rebase needed."
  exit 1
fi

# Tracked-dirty = sibling WIP → skip, never stash (Law 5 / #5 sibling-race).
if [ -n "$(git diff --name-only HEAD 2>/dev/null)" ] || [ -n "$(git diff --cached --name-only 2>/dev/null)" ]; then
  log "Tracked-dirty working tree (sibling WIP?), skip — not stashing (Law 5)"
  telegram_alert "tracked-dirty" "Pro ~/nuzantara has uncommitted TRACKED changes; auto-sync skipped (not touching sibling WIP). Commit/discard to resume."
  exit 0
fi

COMMITS_BEHIND=$(git rev-list --count HEAD.."$REMOTE" 2>/dev/null || echo "?")

# Move aside runtime-artifact untracked/ignored collisions before the ff.
if ! resolve_untracked_collisions; then
  telegram_alert "collision-resolve-failed" "Pro pull: collision-resolve errored; tick skipped, nothing merged. Check ~/logs/pro-git-pull.log."
  exit 1
fi

# Re-verify state right before the ONLY mutation (close the check→merge TOCTOU window).
NOWBRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
[ "$NOWBRANCH" = "main" ] || { log "branch changed to '$NOWBRANCH' mid-tick, skip merge"; exit 0; }
git merge-base --is-ancestor HEAD "$REMOTE" 2>/dev/null || { log "HEAD advanced mid-tick, skip merge"; exit 0; }

if ! git merge --ff-only --quiet "$REMOTE" 2>>"$LOG_FILE"; then
  log "ERROR: git merge --ff-only failed (file/dir conflict or new mismatch)"
  telegram_alert "pull-failed" "git merge --ff-only failed on Pro after collision-resolve. Likely a file/dir conflict — check ~/logs/pro-git-pull.log."
  exit 1
fi

NEW_HEAD=$(git rev-parse --short HEAD)
log "OK pulled to $NEW_HEAD ($COMMITS_BEHIND commits from origin)"
