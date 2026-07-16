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
# HOW IT DIFFERS FROM scripts/mini/mini-git-pull.sh (deliberate): it RESOLVES the local
# changes that block a fast-forward instead of skipping the tick, and it never stashes.
# Pro's main checkout is ~ALWAYS dirty from pipeline output — untracked runtime artifacts
# written into tracked dirs (research/*, apps/*/output/, …) AND in-place modifications to
# TRACKED files (apps/bali-intel-scraper/data/published_articles.json,
# docs/AUTOMATIONS_REFERENCE.md, shared/escalations_pro.jsonl). Those same artifacts land
# on main via other machines, so an incoming path collides with the local version and a
# plain `git merge --ff-only` aborts. Mini SKIPS such a tick (its dirt is short-lived
# sibling WIP that self-resolves); on Pro it never self-resolves, so skipping = NEVER
# syncing (verified 2026-07-16: those 3 tracked files are persistently dirty).
#
# So, for each INCOMING path that collides with a LOCAL change, this puller backs the
# local version up to a timestamped PID-unique no-clobber backup and clears it (untracked
# → move aside; tracked mod → `git checkout HEAD`), then fast-forwards. NON-colliding local
# changes — runtime writes to files origin did NOT touch this pull — are LEFT UNTOUCHED (the
# common case). Law-5-safe by RECOVERABILITY (nothing deleted; every backup logged + alerted),
# and correct because the main checkout carries no human WIP to protect (sessions run in
# .worktrees/). No stash logic — so no risk of popping a sibling's shared-repo stash.
# Ignored files are covered too: `git merge --ff-only` SILENTLY overwrites an ignored
# untracked file (verified), so detection is per-incoming-path ("exists on disk ∧ not
# tracked", or "tracked ∧ locally modified"), never the `--exclude-standard` lens.
#
# EXECUTION LOCATION: run from ~/nuzantara-deploy (kept current by the deploy-puller),
# NOT from ~/nuzantara — a puller must not live in the tree it rewrites (self-mod).
# TARGET is $HOME/nuzantara; only origin/main (Pro pushes straight to GitHub).
#
# FAIL-SAFE INVARIANT: every error path leaves the repo untouched or recoverable and
# retries next tick. Known accepted stalls (abort + alert, never data-loss): a local
# untracked FILE named like an incoming DIRECTORY (file/dir conflict), or a path with
# a literal newline in its name (git C-quotes it → mv fails). Both are visible. Accepted
# residual race (not closed — would need to lock every pipeline writer): a writer that
# rewrites a colliding tracked file in the microsecond window between its backup-cp and
# `git checkout HEAD` loses that single write from the backup; it is regenerated next cycle.
#
# Cron: StartInterval on the Pro LaunchAgent (com.nuzantara.git-pull-main.15min).
# Log:  ~/logs/pro-git-pull.log   Backups: ~/.git-pull-collision-backup/<ts>-<pid>/

set -u

SELF_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
REPO="${PRO_GIT_PULL_REPO:-$HOME/nuzantara}"
LOG_FILE="${PRO_GIT_PULL_LOG:-$HOME/logs/pro-git-pull.log}"
LOCK_DIR="${PRO_GIT_PULL_LOCK:-/tmp/pro-git-pull.lock.d}"
BACKUP_ROOT="${PRO_GIT_PULL_BACKUP_ROOT:-$HOME/.git-pull-collision-backup}"
LOCK_STALE_SECONDS=1800

# Every `-- "$f"` below is an EXACT filename taken from git's own output. Force literal
# pathspecs so an exotic tracked name (`:(glob)**`, `*`, `:/`) can never be read as
# pathspec magic and reset unrelated files (would silently discard non-colliding mods).
export GIT_LITERAL_PATHSPECS=1

mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

# All Telegram goes through the ONE gateway (scripts/tg_notify.py): it owns tiering,
# dedup, budget and the token chain, and NEVER fails the caller. Direct Telegram HTTP
# senders are forbidden by the anti-regrowth lint. tier=digest — a sync stall is
# informative, not NOW-actionable-prod-down; tg_notify's dedup replaces the old cooldown.
telegram_alert() {
  [ "${PRO_GIT_PULL_NO_ALERT:-0}" = "1" ] && return 0  # hermetic test / dry mode
  local key="$1" message="$2" tg="${SELF_DIR:-.}/../tg_notify.py"
  if [ -f "$tg" ]; then
    python3 "$tg" --tier digest --source pro-git-pull --dedup-key "pro-git-pull-${key}" "$message" >/dev/null 2>&1 || true
  else
    log "  (tg_notify.py not found at $tg — alert not sent: $message)"
  fi
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

# Neutralise every LOCAL change that would block the fast-forward: an INCOMING tracked
# path that also exists locally as (a) an untracked/ignored file, or (b) a tracked file
# with LOCAL modifications. Each is backed up (recoverable) then cleared, so the ff can
# land origin's version. NON-colliding local changes — runtime writes to files origin did
# NOT touch this pull — are LEFT UNTOUCHED. That is the whole point on Pro's main checkout:
# its tracked-dirty state is pipeline output (published_articles.json, AUTOMATIONS_REFERENCE.md,
# shared/escalations_pro.jsonl, …) that is ~always dirty and almost never in the incoming
# diff, so skipping on "any tracked dirt" would mean never syncing. There is no human WIP on
# the main checkout to protect (sessions run in .worktrees/); recoverability + alert cover
# the rare case a colliding local change was unexpected.
# Per-incoming-path: the incoming set is small and its names are clean git history, so a huge
# ignore tree is never enumerated and weird LOCAL filenames are never parsed as text.
# Returns 0 on success (incl. nothing to do); 1 on ANY failure (fail-safe: caller skips the
# merge, everything recoverable).
resolve_collisions() {
  local changed f backup n=0 first="" ts
  changed=$(git -c core.quotepath=false diff --name-only HEAD "$REMOTE" 2>/dev/null)
  [ -z "$changed" ] && return 0
  ts="$(date '+%Y%m%d-%H%M%S')-$$"
  backup="$BACKUP_ROOT/$ts"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if git ls-files --error-unmatch -- "$f" >/dev/null 2>&1; then
      # tracked: a collision ONLY if locally modified (else ff updates it cleanly, mod-free)
      git diff --quiet HEAD -- "$f" 2>/dev/null && continue
      mkdir -p "$backup/$(dirname "$f")" 2>>"$LOG_FILE" || { log "  ERROR: mkdir backup for $f"; return 1; }
      # cp -p saves only the WORKING-TREE version; if a distinct STAGED version exists,
      # `git checkout HEAD` would discard it unrecoverably — back the index blob up too.
      if ! git diff --quiet --cached HEAD -- "$f" 2>/dev/null; then
        git show ":$f" > "$backup/$f.staged" 2>>"$LOG_FILE" || { log "  ERROR: staged-blob backup failed for $f — aborting (fail-safe)"; return 1; }
      fi
      if cp -p "$REPO/$f" "$backup/$f" 2>>"$LOG_FILE" && git checkout HEAD -- "$f" 2>>"$LOG_FILE"; then
        n=$((n + 1)); [ -z "$first" ] && first="$f (tracked)"
        log "  backed up + reset colliding tracked mod: $f -> $backup/$f"
      else
        log "  ERROR: backup/checkout failed for tracked $f — aborting tick (fail-safe)"; return 1
      fi
    else
      # untracked/ignored: a collision ONLY if it exists on disk at the incoming path
      # (-L too: a DANGLING symlink is invisible to -e but still blocks/loses on ff)
      [ -e "$REPO/$f" ] || [ -L "$REPO/$f" ] || continue
      mkdir -p "$backup/$(dirname "$f")" 2>>"$LOG_FILE" || { log "  ERROR: mkdir backup for $f"; return 1; }
      if mv -n "$REPO/$f" "$backup/$f" 2>>"$LOG_FILE" && [ ! -e "$REPO/$f" ]; then
        n=$((n + 1)); [ -z "$first" ] && first="$f (untracked)"
        log "  moved colliding untracked/ignored: $f -> $backup/$f"
      else
        log "  ERROR: mv failed / backup dest existed for $f — aborting tick (fail-safe)"; return 1
      fi
    fi
  done < <(printf '%s\n' "$changed")

  if [ "$n" -gt 0 ]; then
    log "Neutralised $n colliding local path(s) into $backup (recoverable)."
    telegram_alert "collision" \
      "Pro pull: backed up + cleared ${n} local path(s) colliding with incoming (e.g. ${first}) into ${backup}. Runtime output by design; restore from backup if any was real WIP."
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

COMMITS_BEHIND=$(git rev-list --count HEAD.."$REMOTE" 2>/dev/null || echo "?")

# Neutralise local changes that collide with incoming (tracked mods + untracked/ignored),
# backing each up first. Non-colliding local runtime state is preserved (the common case on
# Pro's main checkout) — see resolve_collisions. We do NOT skip merely because tracked files
# are dirty: on Pro they ~always are (pipeline output), and skipping would mean never syncing.
if ! resolve_collisions; then
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
