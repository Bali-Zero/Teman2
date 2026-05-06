#!/bin/bash
# Mini-side periodic git pull for ~/Desktop/nuzantara on main.
#
# Runs ON Mini via com.nuzantara.git-pull-main.5min LaunchAgent.
# Pattern: detect-mismatch → stash → pull --ff-only → stash pop.
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

# Detect tracked-symlink vs local-dir (or vice versa) mismatches.
# Returns 0 if clean, 1 if mismatch found (caller skips).
#
# Walks the FULL origin/main tree of symlinks (tree mode 120000) and the
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
  done < <(git ls-tree -r origin/main 2>/dev/null | awk -F'\t' '$1 ~ /^120000/ {print $2}')

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
  done < <(git ls-tree -r origin/main 2>/dev/null | awk -F'\t' '$1 ~ /^10064[45]|^10075[5]/ {print $2}')

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

# Fetch quietly. Network failures are non-fatal.
if ! git fetch --quiet origin main 2>>"$LOG_FILE"; then
  log "git fetch failed (network?), skip"
  exit 0
fi

LOCAL=$(git rev-parse HEAD 2>/dev/null)
REMOTE=$(git rev-parse origin/main 2>/dev/null)

# Already up to date — silent (avoid log noise on every 5-min tick).
if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

# Refuse if HEAD has diverged from origin/main (not ff-able).
if ! git merge-base --is-ancestor HEAD origin/main 2>/dev/null; then
  log "WARN: HEAD diverged from origin/main (not ff-able)."
  log "  local=$LOCAL  remote=$REMOTE"
  telegram_alert "diverged" \
    "Mini main HEAD diverged from origin (local=${LOCAL:0:9} vs remote=${REMOTE:0:9}). Manual rebase needed."
  exit 1
fi

# 2026-05-06 hardening: detect symlink↔dir mismatches BEFORE attempting stash.
# These happened with apps/backend-rag/.venv (origin symlink, Mini real 762MB dir).
if ! check_type_mismatch; then
  exit 1
fi

# Check stash retention (sign of repeated pop failures).
STASH_COUNT=$(git stash list 2>/dev/null | wc -l | tr -d ' ')
if [ "$STASH_COUNT" -gt "$STASH_RETENTION_THRESHOLD" ]; then
  log "WARN: $STASH_COUNT stashes accumulated (threshold $STASH_RETENTION_THRESHOLD)."
  telegram_alert "stash-bloat" \
    "Mini has ${STASH_COUNT} stashes accumulated. Likely repeated pop conflicts. \`git stash list\` on Mini."
fi

COMMITS_BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")

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
    log "Stashed tracked changes ('$STASH_MSG'), pulling $COMMITS_BEHIND commits..."
  else
    log "ERROR: git stash failed, skip"
    telegram_alert "stash-failed" "git stash failed on Mini. Manual triage."
    exit 1
  fi
else
  log "Clean tracked tree, pulling $COMMITS_BEHIND commits..."
fi

# Pull ff-only.
if ! git pull --ff-only --quiet origin main 2>>"$LOG_FILE"; then
  log "ERROR: git pull --ff-only failed"
  telegram_alert "pull-failed" "git pull --ff-only failed on Mini. Probably new mismatch type appeared."
  if [ "$STASHED" = "1" ]; then
    log "  attempting to restore stash..."
    git stash pop --quiet 2>>"$LOG_FILE" || \
      log "  WARN: stash pop failed too — stash retained"
  fi
  exit 1
fi

NEW_HEAD=$(git rev-parse --short HEAD)
log "OK pulled to $NEW_HEAD ($COMMITS_BEHIND commits)"

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
