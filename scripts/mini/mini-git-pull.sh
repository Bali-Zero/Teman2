#!/bin/bash
# Mini-side periodic git pull for ~/Desktop/nuzantara on main.
#
# Runs ON Mini via com.nuzantara.git-pull-main.5min LaunchAgent.
# Pattern: detect-mismatch → stash → fetch pro+origin → ff to most-advanced → stash pop.
#
# Hardened against the 2026-05-06 incident where a tracked symlink in
# main collided with a 762 MB local directory (.venv) on Mini, causing
# silent 8+ retry failures because `git stash --include-untracked` tried
# to stash the entire dir.
#
# Hardening:
#   1. Detect symlink-vs-dir / dir-vs-symlink mismatches BEFORE stash and
#      skip with Telegram alert (these need human triage).
#   2. Stash only tracked-modified paths via `git stash push --keep-index`
#      pattern, never `--include-untracked` blindly. Untracked files
#      survive a ff-only pull anyway.
#   3. Bound the stash retention: if stash list exceeds N entries, alert
#      (sign that pop has been failing).
#   4. Telegram alert on every non-trivial WARN/ERROR via the same
#      bot used by login-healthcheck (TELEGRAM_BOT_TOKEN secret on Mini).
#
# Source-of-truth selection (2026-07-05 fix — M5 era):
#   Fetch BOTH `pro/main` and `origin/main` (best-effort each), then ff to the
#   MOST-ADVANCED of the two. The pre-M5 policy was Pro-first with origin only
#   as unreachable-fallback — it silently left Mini stale whenever Pro was
#   reachable but itself behind origin (M5 pushes straight to GitHub; on
#   2026-07-02 Mini sat 13 commits behind origin logging "ahead of pro/main;
#   skip pull" every 5 min).
#   If pro/main and origin/main have DIVERGED, prefer origin/main (GitHub is
#   authoritative) and Telegram-alert so Pro's unpushed work gets human triage.
#
# Cron: StartInterval=300 on Mini.
# Log:  ~/logs/mini-git-pull.log
# Error: ~/logs/mini-git-pull.error.log

set -u

REPO="$HOME/Desktop/nuzantara"
LOG_FILE="$HOME/logs/mini-git-pull.log"
LOCK_FILE="/tmp/mini-git-pull.lock"
STASH_RETENTION_THRESHOLD=5  # alert if more stashes than this accumulate
TELEGRAM_ALERT_COOLDOWN=3600  # 1h cooldown per alert key
TELEGRAM_STATE_DIR="$HOME/.agent/decisions/state"

mkdir -p "$(dirname "$LOG_FILE")" "$TELEGRAM_STATE_DIR"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# Telegram alert with per-key cooldown (avoid notification storms).
telegram_alert() {
  local key="$1"
  local message="$2"
  local state_file="$TELEGRAM_STATE_DIR/mini-git-pull-alert-${key}.ts"
  local now last_ts
  now=$(date +%s)
  if [ -f "$state_file" ]; then
    last_ts=$(cat "$state_file" 2>/dev/null || echo "0")
    if [ $((now - last_ts)) -lt "$TELEGRAM_ALERT_COOLDOWN" ]; then
      return 0  # within cooldown, skip
    fi
  fi
  # Source secrets if available — Telegram bot token must be there.
  if [ -f "$HOME/.nuzantara-secrets.env" ]; then
    set -a
    # shellcheck source=/dev/null
    source "$HOME/.nuzantara-secrets.env" 2>/dev/null || true
    set +a
  fi
  local token="${TELEGRAM_BOT_TOKEN:-}"
  local chat="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  if [ -z "$token" ]; then
    log "  (telegram skipped — TELEGRAM_BOT_TOKEN not in env)"
    return 0
  fi
  curl -s --max-time 8 \
    "https://api.telegram.org/bot${token}/sendMessage" \
    -d "chat_id=${chat}" \
    -d "text=[mini-git-pull] ${message}" >/dev/null 2>&1 || true
  echo "$now" > "$state_file"
}

TARGET_REF="origin/main"
TARGET_REMOTE="origin"

# Detect tracked-symlink vs local-dir (or vice versa) mismatches.
# Returns 0 if clean, 1 if mismatch found (caller skips).
#
# Walks the FULL target tree of symlinks (tree mode 120000) and the
# subset of "tree" entries (mode 040000). For each, compares the local
# filesystem reality against origin's expectation. The 2026-05-06
# incident path (.venv: tracked symlink, local 762 MB dir) is the
# canonical case.
#
# Cost-bounded: typical repo has <100 symlinks; full scan is ~50 ms.
check_type_mismatch() {
  local mismatch_count=0
  local mismatch_first=""

  # Pass 1: every symlink declared in origin/main must be a symlink
  # locally (or absent — pull will create it). If it's a real file or
  # dir, we have a mismatch.
  # ls-tree format is `<mode> SP <type> SP <hash> TAB <path>`. We extract
  # the path field (everything after the TAB) via awk.
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    # Path absent locally is fine (pull will create it).
    [ -e "$path" ] || [ -L "$path" ] || continue
    local fs_kind="other"
    if [ -L "$path" ]; then fs_kind="symlink"
    elif [ -d "$path" ]; then fs_kind="dir"
    elif [ -f "$path" ]; then fs_kind="file"
    fi
    if [ "$fs_kind" != "symlink" ]; then
      mismatch_count=$((mismatch_count + 1))
      [ -z "$mismatch_first" ] && mismatch_first="$path (origin=symlink, local=$fs_kind)"
    fi
  done < <(git ls-tree -r "$TARGET_REF" 2>/dev/null | awk -F'\t' '$1 ~ /^120000/ {print $2}')

  # Pass 2: every regular file declared in origin/main must NOT be a
  # local dir or symlink. (Files are 100644/100755.) Dirs in git are
  # implicit (tree entries appear when -t flag is used; we don't use -t
  # so this pass only sees files. We focus on files-vs-dir conflicts.)
  while IFS= read -r path; do
    [ -z "$path" ] && continue
    [ -e "$path" ] || [ -L "$path" ] || continue
    local fs_kind="other"
    if [ -L "$path" ]; then fs_kind="symlink"
    elif [ -d "$path" ]; then fs_kind="dir"
    elif [ -f "$path" ]; then fs_kind="file"
    fi
    if [ "$fs_kind" != "file" ]; then
      mismatch_count=$((mismatch_count + 1))
      [ -z "$mismatch_first" ] && mismatch_first="$path (origin=file, local=$fs_kind)"
    fi
  done < <(git ls-tree -r "$TARGET_REF" 2>/dev/null | awk -F'\t' '$1 ~ /^10064[45]|^10075[5]/ {print $2}')

  if [ "$mismatch_count" -gt 0 ]; then
    log "ERROR: $mismatch_count type-mismatch path(s) detected, refusing pull."
    log "  first: $mismatch_first"
    log "  HINT: human triage needed. Likely a tracked symlink in main has been"
    log "        materialized as a real dir/file on Mini. mv it aside before retry."
    telegram_alert "type-mismatch" \
      "${mismatch_count} path type-mismatch (e.g. ${mismatch_first}). Pull refused. Manual triage on Mini."
    return 1
  fi
  return 0
}

# Detect untracked local files that occupy a path the incoming merge also
# touches. `git stash push` (without --include-untracked, see below) does
# NOT cover untracked files, so they survive the stash step unchanged —
# but `git merge --ff-only` still refuses when one of them collides with
# a path the target ref introduces or modifies. Without this check the
# script stashes tracked changes, fails the merge on the untracked
# collision, restores the stash, and repeats the whole cycle every 5 min
# forever (observed 2026-07-11: 7+ retries over 40 min, same path each
# time) — wasted churn plus a generic "pull-failed" alert that doesn't
# name the actual blocker. Detect it BEFORE stashing so we skip cleanly
# with one targeted alert naming the colliding path(s); this is most
# often a sibling session's uncommitted WIP (e.g. a new test file),
# which resolves itself once that work is committed or removed — never
# something this script should touch (Law 5 / sibling-race discipline).
#
# Returns 0 if clean, 1 if a collision is found (caller skips this tick).
check_untracked_collision() {
  local changed_paths untracked_paths colliding
  changed_paths=$(git diff --name-only HEAD "$TARGET_REF" 2>/dev/null)
  [ -z "$changed_paths" ] && return 0
  untracked_paths=$(git ls-files --others --exclude-standard 2>/dev/null)
  [ -z "$untracked_paths" ] && return 0
  colliding=$(comm -12 <(echo "$changed_paths" | sort) <(echo "$untracked_paths" | sort))
  if [ -n "$colliding" ]; then
    local colliding_oneline
    colliding_oneline=$(echo "$colliding" | tr '\n' ' ' | sed 's/ $//')
    log "WARN: untracked file(s) collide with incoming $TARGET_REF: $colliding_oneline"
    log "  HINT: likely a sibling session's uncommitted WIP (new file not yet"
    log "        committed). Leave it alone — will retry once committed/removed."
    telegram_alert "untracked-collision" \
      "Mini pull skipped — untracked file(s) collide with incoming ${TARGET_REMOTE}/main: ${colliding_oneline}. Likely sibling WIP; retries once committed/removed."
    return 1
  fi
  return 0
}

# ===== MAIN =====

# Single-instance lock
if [ -f "$LOCK_FILE" ]; then
  PID=$(cat "$LOCK_FILE" 2>/dev/null || echo "")
  if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
    log "Already running (PID $PID), skip"
    exit 0
  fi
fi
echo $$ > "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

cd "$REPO" 2>/dev/null || { log "FATAL: $REPO not found"; exit 1; }

# Sane PATH under launchd (no shell rc files sourced).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"

# Skip if not on main — Mini may be temporarily on a feature branch.
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [ "$BRANCH" != "main" ]; then
  log "On branch '$BRANCH' (not main), skip"
  exit 0
fi

# Fetch BOTH remotes best-effort, then follow the most-advanced ref. Pro may
# hold commits not yet pushed to GitHub, and origin may hold commits Pro has
# not pulled (M5 pushes straight to GitHub) — either side can be ahead.
PRO_SSH="ssh -o BatchMode=yes -o ConnectTimeout=10 -o IdentitiesOnly=yes -i $HOME/.ssh/id_ed25519"
PRO_FETCHED=0
ORIGIN_FETCHED=0
if GIT_SSH_COMMAND="$PRO_SSH" git fetch --quiet pro main 2>>"$LOG_FILE"; then
  PRO_FETCHED=1
else
  log "WARN: git fetch pro failed"
fi
if git fetch --quiet origin main 2>>"$LOG_FILE"; then
  ORIGIN_FETCHED=1
else
  log "WARN: git fetch origin failed"
fi

if [ "$PRO_FETCHED" = "0" ] && [ "$ORIGIN_FETCHED" = "0" ]; then
  log "git fetch failed for both pro and origin (network?), skip"
  telegram_alert "fetch-failed" "Mini could not fetch pro/main or origin/main. Sync skipped."
  exit 0
elif [ "$PRO_FETCHED" = "0" ]; then
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
elif [ "$ORIGIN_FETCHED" = "0" ]; then
  TARGET_REF="pro/main"
  TARGET_REMOTE="pro"
elif git merge-base --is-ancestor pro/main origin/main 2>/dev/null; then
  # origin/main contains pro/main (equal counts as ancestor) — origin wins.
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
elif git merge-base --is-ancestor origin/main pro/main 2>/dev/null; then
  # pro/main is strictly ahead (Pro has commits not yet on GitHub).
  TARGET_REF="pro/main"
  TARGET_REMOTE="pro"
else
  # Diverged: Pro has unpushed commits AND origin moved past Pro. Follow
  # origin (GitHub authoritative); Pro's unpushed work needs human triage.
  log "WARN: pro/main and origin/main have diverged; following origin/main"
  telegram_alert "pro-origin-diverged" \
    "pro/main and origin/main diverged. Mini follows origin/main; Pro has unpushed commits needing manual push/rebase."
  TARGET_REF="origin/main"
  TARGET_REMOTE="origin"
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse "$TARGET_REF" 2>/dev/null)

# Already up to date — silent (avoid log noise on every 5-min tick).
if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# Refuse if HEAD has diverged from target ref (not ff-able).
if ! git merge-base --is-ancestor HEAD "$TARGET_REF" 2>/dev/null; then
  if git merge-base --is-ancestor "$TARGET_REF" HEAD 2>/dev/null; then
    log "Local main is ahead of $TARGET_REF; skip pull"
    exit 0
  fi
  log "WARN: HEAD diverged from $TARGET_REF (not ff-able)."
  log "  local=$LOCAL  remote=$REMOTE"
  telegram_alert "diverged" \
    "Mini main HEAD diverged from ${TARGET_REF} (local=${LOCAL:0:9} vs remote=${REMOTE:0:9}). Manual rebase needed."
  exit 1
fi

# 2026-05-06 hardening: detect symlink↔dir mismatches BEFORE attempting stash.
# These happened with apps/backend-rag/.venv (origin symlink, Mini real 762MB dir).
if ! check_type_mismatch; then
  exit 1
fi

# 2026-07-11 hardening: detect untracked-file collisions BEFORE attempting
# stash. See check_untracked_collision() above.
if ! check_untracked_collision; then
  exit 1
fi

# 2026-05-10 Fase 0c hardening: acquire repo-mutating exclusive lock so
# Cluster C/D cron jobs do not read half-rewritten .py / .yaml during git
# pull. Cron jobs use `flock --shared` on the same lock during their
# startup phase. Timeout 30s — if not acquired, skip this 5min tick.
if ! command -v flock >/dev/null 2>&1; then
  log "WARN: flock not installed (brew install flock); skipping repo-mutating lock"
else
  REPO_LOCK="/tmp/repo-mutating.lock"
  exec 8>"$REPO_LOCK"
  if ! flock --exclusive --timeout 30 8; then
    log "WARN: could not acquire $REPO_LOCK in 30s — cron job is reading repo, skip this tick"
    exit 0
  fi
  # Lock auto-released on exit (fd 8 closes); add to trap so explicit cleanup is safe.
  trap 'flock -u 8 2>/dev/null || true; rm -f "$LOCK_FILE"' EXIT
fi

# Check stash retention (sign of repeated pop failures).
STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
if [ "$STASH_COUNT" -gt "$STASH_RETENTION_THRESHOLD" ]; then
  log "WARN: $STASH_COUNT stashes accumulated (threshold $STASH_RETENTION_THRESHOLD)."
  telegram_alert "stash-bloat" \
    "Mini has ${STASH_COUNT} stashes accumulated. Likely repeated pop conflicts. \`git stash list\` on Mini."
fi

COMMITS_BEHIND=$(git rev-list --count HEAD.."$TARGET_REF" 2>/dev/null || echo "?")

# Stash only tracked dirty files. Untracked survive ff-only pulls
# untouched anyway, no need to stash them (and they may be huge — like
# the 762 MB .venv dir that bit us).
STASHED=0
DIRTY_TRACKED=$(git diff --name-only HEAD 2>/dev/null)
DIRTY_STAGED=$(git diff --cached --name-only 2>/dev/null)
if [ -n "$DIRTY_TRACKED" ] || [ -n "$DIRTY_STAGED" ]; then
  STASH_MSG="mini-git-pull-auto $(date +%Y-%m-%d_%H:%M:%S)"
  # `git stash push` without `--include-untracked` only stashes tracked
  # changes. This is what we want.
  if git stash push --quiet -m "$STASH_MSG" 2>>"$LOG_FILE"; then
    STASHED=1
    log "Stashed tracked changes ('$STASH_MSG'), pulling $COMMITS_BEHIND commits from $TARGET_REF..."
  else
    log "ERROR: git stash failed, skip"
    telegram_alert "stash-failed" "git stash failed on Mini. Manual triage."
    exit 1
  fi
else
  log "Clean tracked tree, pulling $COMMITS_BEHIND commits from $TARGET_REF..."
fi

# Pull ff-only.
if ! git merge --ff-only --quiet "$TARGET_REF" 2>>"$LOG_FILE"; then
  log "ERROR: git merge --ff-only $TARGET_REF failed"
  telegram_alert "pull-failed" "git merge --ff-only ${TARGET_REF} failed on Mini. Probably new mismatch type appeared."
  if [ "$STASHED" = "1" ]; then
    log "  attempting to restore stash..."
    git stash pop --quiet 2>>"$LOG_FILE" || \
      log "  WARN: stash pop failed too — stash retained"
  fi
  exit 1
fi

NEW_HEAD=$(git rev-parse --short HEAD)
log "OK pulled to $NEW_HEAD ($COMMITS_BEHIND commits from $TARGET_REMOTE)"

# Keep the launchd-safe deployed script in sync with the repo source. The
# LaunchAgent executes ~/scripts/mini-git-pull.sh because macOS TCC can block
# direct execution from ~/Desktop.
mkdir -p "$HOME/scripts" 2>/dev/null
if [ -f "$REPO/scripts/mini/mini-git-pull.sh" ]; then
  if ! cmp -s "$REPO/scripts/mini/mini-git-pull.sh" "$HOME/scripts/mini-git-pull.sh" 2>/dev/null; then
    cp "$REPO/scripts/mini/mini-git-pull.sh" "$HOME/scripts/mini-git-pull.sh" 2>>"$LOG_FILE" && \
      chmod 755 "$HOME/scripts/mini-git-pull.sh" 2>/dev/null && \
      log "  updated ~/scripts/mini-git-pull.sh from repo source"
  fi
fi

# 2026-05-11 TCC-safe sync via git checkout (cp falliva su TCC, ma
# git binary ha FDA implicito quindi git --git-dir + --work-tree va).
# git esce 0 anche per "no change", quindi check exit + verifica file.
mkdir -p "$HOME/agent-config" 2>/dev/null
if git --git-dir="$REPO/.git" --work-tree="$HOME/agent-config" \
       checkout "$TARGET_REF" -- config/job-ownership.yaml 2>>"$LOG_FILE"; then
  if [ -f "$HOME/agent-config/config/job-ownership.yaml" ]; then
    # Move into root for backwards compat ($HOME/agent-config/job-ownership.yaml)
    mv "$HOME/agent-config/config/job-ownership.yaml" \
       "$HOME/agent-config/job-ownership.yaml" 2>/dev/null || true
    rmdir "$HOME/agent-config/config" 2>/dev/null || true
    log "  synced config/job-ownership.yaml -> ~/agent-config/ (via git checkout)"
  fi
else
  log "  WARN: failed to sync job-ownership.yaml to ~/agent-config/"
fi

# Restore stash. Conflict-tolerant: on conflict, leave stash for human review.
if [ "$STASHED" = "1" ]; then
  if git stash pop --quiet 2>>"$LOG_FILE"; then
    log "  stash restored cleanly"
  else
    log "  WARN: stash pop conflict — stash retained."
    telegram_alert "stash-pop-conflict" \
      "stash pop conflict on Mini after ff-pull to ${NEW_HEAD}. \`git status\` + \`git stash list\` on Mini."
    # Don't exit error — pull succeeded. Conflict is a separate issue.
  fi
fi
