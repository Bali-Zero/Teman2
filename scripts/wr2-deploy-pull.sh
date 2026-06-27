#!/usr/bin/env bash
# wr2-deploy-pull.sh
#
# Keeps the WR2 deploy worktree at ~/Desktop/nuzantara-deploy fast-forwarded
# to origin/main for launchd jobs that run from a stable production checkout.

set -uo pipefail

DEPLOY_DIR="${WR2_DEPLOY_DIR:-${HOME}/Desktop/nuzantara-deploy}"
SOURCE_REPO="${WR2_SOURCE_REPO:-${HOME}/Desktop/nuzantara}"
# 2026-06-27: track `main` directly. The old `deploy/main` intermediate branch made sense
# only when -deploy was a WORKTREE (to isolate its HEAD from the main checkout's branch).
# Now -deploy is an isolated CLONE, so a separate branch is pure overhead — and it caused a
# STERILE pull: origin/deploy/main lagged origin/main by 3 commits and nobody advanced it, so
# the puller saw "up-to-date" against a phantom ref while the real merges (incl. #1766) never
# reached the live organs. Tracking main directly is the cure. (TAC self-loop anti-sterility.)
EXPECTED_BRANCH="${WR2_DEPLOY_BRANCH:-main}"
LOG="${HOME}/logs/wr2-deploy-pull.log"
STATE="${HOME}/.agent/decisions/state/wr2_deploy_pull.state"
LOCK="${HOME}/.agent/decisions/state/wr2_deploy_pull.lock"
SECRETS="${HOME}/.nuzantara-secrets.env"
ALERT_COOLDOWN_SEC=21600

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"

log() {
  printf '%s [wr2-deploy-pull] %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S WITA')" "$*" >> "$LOG"
}

if [[ -f "$SECRETS" ]]; then
  TELEGRAM_BOT_TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
  TELEGRAM_OWNER_CHAT_ID="$(grep '^TELEGRAM_OWNER_CHAT_ID=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
  export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  if ! flock -n 9; then
    log "another deploy-pull is in progress, skipping"
    exit 0
  fi
fi

PATH="${WR2_DEPLOY_PULL_TEST_PATH_PREFIX:+${WR2_DEPLOY_PULL_TEST_PATH_PREFIX}:}/Users/nuzantara/.local/bin:/Users/nuzantara/.npm-global/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PATH

now_epoch() { date '+%s'; }

state_get() {
  local key="$1"
  [[ -f "$STATE" ]] || return 0
  awk -F= -v k="$key" '$1==k {print $2}' "$STATE" | tail -1
}

state_set() {
  local key="$1" val="$2"
  mkdir -p "$(dirname "$STATE")"
  if [[ -f "$STATE" ]]; then
    awk -F= -v k="$key" -v v="$val" '
      BEGIN{found=0}
      $1==k {print k"="v; found=1; next}
      {print}
      END{if(!found) print k"="v}
    ' "$STATE" > "${STATE}.tmp" && mv "${STATE}.tmp" "$STATE"
  else
    printf '%s=%s\n' "$key" "$val" > "$STATE"
  fi
}

alert_due() {
  local key="$1" now last age
  now=$(now_epoch)
  last=$(state_get "last_alert_${key}")
  [[ -z "$last" || ! "$last" =~ ^[0-9]+$ ]] && return 0
  age=$(( now - last ))
  (( age >= ALERT_COOLDOWN_SEC ))
}

send_telegram() {
  local key="$1" text="$2"
  if [[ -z "${TELEGRAM_BOT_TOKEN:-}" ]]; then
    log "Telegram skipped (no TELEGRAM_BOT_TOKEN)"
    return 0
  fi
  if ! alert_due "$key"; then
    log "alert ${key} suppressed (cooldown active)"
    return 0
  fi
  local chat_id="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
  curl -fsS -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    --data-urlencode "chat_id=${chat_id}" \
    --data-urlencode "parse_mode=Markdown" \
    --data-urlencode "disable_web_page_preview=true" \
    --data-urlencode "text=${text}" \
    -o /dev/null --max-time 10 \
    || log "Telegram POST failed (network/curl)"
  state_set "last_alert_${key}" "$(now_epoch)"
}

is_git_worktree() {
  local dir="$1"
  [[ -d "$dir/.git" || -f "$dir/.git" ]]
}

# 2026-06-27: -deploy is now a full CLONE (not a worktree) — council Q1, isolated object
# store immune to the main's sibling-race (W63/#5). The clone is cheap: HEAD tree ~0.9GB
# (the 45G "repo" was venv+node_modules+.worktrees, which a clone never materializes).
# Bootstrap = git clone from the REAL origin (GitHub), so a vanished main cannot block it.
bootstrap_deploy_clone() {
  if [[ -e "$DEPLOY_DIR" ]]; then
    log "ERROR: deploy path exists but is not a git checkout: ${DEPLOY_DIR}"
    return 1
  fi
  # Resolve the GitHub origin from the source repo (fallback if source is gone).
  local origin_url
  origin_url="$(git -C "$SOURCE_REPO" remote get-url origin 2>/dev/null)"
  if [[ -z "$origin_url" ]]; then
    origin_url="${WR2_DEPLOY_ORIGIN:-https://github.com/Balizero1987/Teman2.git}"
    log "source origin unknown; falling back to ${origin_url}"
  fi

  log "deploy clone missing at ${DEPLOY_DIR}; cloning ${EXPECTED_BRANCH} from ${origin_url}"
  # --no-hardlinks not relevant for a network clone; branch points at the runtime branch.
  if ! git clone --quiet --branch "$EXPECTED_BRANCH" "$origin_url" "$DEPLOY_DIR" 2>>"$LOG"; then
    # branch may not exist on origin yet -> clone main then create the branch
    if ! git clone --quiet "$origin_url" "$DEPLOY_DIR" 2>>"$LOG"; then
      log "ERROR: git clone failed for ${DEPLOY_DIR} from ${origin_url}"
      return 1
    fi
    git -C "$DEPLOY_DIR" checkout -B "$EXPECTED_BRANCH" origin/main >>"$LOG" 2>&1 || true
  fi

  state_set "last_bootstrap_ts" "$(now_epoch)"
  log "OK: bootstrapped deploy CLONE at ${DEPLOY_DIR} on ${EXPECTED_BRANCH}"
  return 0
}

log "deploy-pull start dir=${DEPLOY_DIR}"

# A clone has .git as a DIR; a worktree as a FILE. We REQUIRE a clone now: if .git is a
# file (someone re-created a worktree) treat it as missing and re-bootstrap a clone.
if [[ ! -d "$DEPLOY_DIR/.git" ]]; then
  if [[ -f "$DEPLOY_DIR/.git" ]]; then
    log "WARN: ${DEPLOY_DIR} is a worktree (.git is a file), not the required clone — removing + recloning"
    rm -rf "$DEPLOY_DIR" 2>>"$LOG"; git -C "$SOURCE_REPO" worktree prune 2>>"$LOG" || true
  fi
  if ! bootstrap_deploy_clone; then
    log "ERROR: deploy clone missing at ${DEPLOY_DIR}"
    send_telegram "deploy_missing" \
      "WR2 deploy CLONE missing at \`${DEPLOY_DIR}\`. Self-heal failed. Run: \`git clone --branch deploy/main https://github.com/Balizero1987/Teman2.git ~/Desktop/nuzantara-deploy\`"
    exit 1
  fi
fi

cd "$DEPLOY_DIR" || {
  log "ERROR: cannot cd to ${DEPLOY_DIR}"
  exit 1
}

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [[ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]]; then
  log "ERROR: deploy worktree on branch=${CURRENT_BRANCH}, expected ${EXPECTED_BRANCH}"
  send_telegram "wrong_branch" \
    "WR2 deploy worktree on WRONG branch. Expected: \`${EXPECTED_BRANCH}\`. Found: \`${CURRENT_BRANCH}\`. Fix: \`cd ${DEPLOY_DIR} && git checkout ${EXPECTED_BRANCH}\`"
  exit 1
fi

DIRTY="$(git status --porcelain 2>/dev/null | head -1)"
if [[ -n "$DIRTY" ]]; then
  log "ERROR: deploy worktree has local changes - first dirty entry: ${DIRTY}"
  send_telegram "dirty_worktree" \
    "WR2 deploy worktree DIRTY. First dirty entry: \`${DIRTY}\`. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
  exit 1
fi

if ! git fetch --quiet origin "$EXPECTED_BRANCH" 2>>"$LOG"; then
  if ! git fetch --quiet origin main 2>>"$LOG"; then
    log "ERROR: git fetch failed for both ${EXPECTED_BRANCH} and main"
    send_telegram "fetch_failed" \
      "WR2 deploy-pull: git fetch failed for \`${DEPLOY_DIR}\`. Check network and GitHub auth."
    exit 1
  fi
fi

REMOTE_REF="origin/${EXPECTED_BRANCH}"
if ! git rev-parse --verify --quiet "$REMOTE_REF" >/dev/null; then
  REMOTE_REF="origin/main"
fi

LOCAL_HEAD="$(git rev-parse HEAD)"
REMOTE_HEAD="$(git rev-parse "$REMOTE_REF")"
if [[ "$LOCAL_HEAD" == "$REMOTE_HEAD" ]]; then
  log "OK: already up-to-date (${LOCAL_HEAD:0:9})"
  state_set "last_status" "ok"
  state_set "last_run_ts" "$(now_epoch)"
  state_set "last_head" "$LOCAL_HEAD"
  exit 0
fi

AHEAD="$(git rev-list --count "${REMOTE_REF}..HEAD" 2>/dev/null || echo 0)"
if [[ "$AHEAD" =~ ^[0-9]+$ ]] && (( AHEAD > 0 )); then
  log "ERROR: deploy worktree is ${AHEAD} commit(s) ahead of ${REMOTE_REF} - refusing to merge"
  send_telegram "local_ahead" \
    "WR2 deploy worktree has LOCAL commits: ${AHEAD} ahead of \`${REMOTE_REF}\`. Inspect: \`cd ${DEPLOY_DIR} && git log ${REMOTE_REF}..HEAD\`."
  exit 1
fi

if ! git merge-base --is-ancestor "$LOCAL_HEAD" "$REMOTE_HEAD"; then
  log "ERROR: branches diverged - local=${LOCAL_HEAD:0:9} remote=${REMOTE_HEAD:0:9}"
  send_telegram "diverged" \
    "WR2 deploy-pull: branches DIVERGED. local \`${LOCAL_HEAD:0:9}\`, remote \`${REMOTE_HEAD:0:9}\`. Manual resolution required."
  exit 1
fi

if ! git merge --ff-only "$REMOTE_REF" >>"$LOG" 2>&1; then
  log "ERROR: git merge --ff-only failed unexpectedly"
  send_telegram "ff_failed" \
    "WR2 deploy-pull: ff-merge failed unexpectedly. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
  exit 1
fi

NEW_HEAD="$(git rev-parse HEAD)"
COMMIT_COUNT="$(git rev-list --count "${LOCAL_HEAD}..${NEW_HEAD}" 2>/dev/null || echo ?)"
log "OK: fast-forwarded ${LOCAL_HEAD:0:9} -> ${NEW_HEAD:0:9} (${COMMIT_COUNT} commit(s))"
state_set "last_status" "advanced"
state_set "last_run_ts" "$(now_epoch)"
state_set "last_head" "$NEW_HEAD"
state_set "last_advance_count" "$COMMIT_COUNT"
exit 0
