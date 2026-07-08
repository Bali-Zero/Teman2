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

# ── C2: deploy outcome heartbeat (~/.organism/last_seen/wr2.deploy_pull.json) ──
# Written by a trap on EVERY exit path — success, error and unexpected alike.
# Pre-C2 the puller only touched its private state file, so the organism could
# not see whether the deploy artery was pumping (red-team finding, 2026-07-02).
# Status values are fixed keywords → JSON-safe by construction.
OUTCOME_STATUS="error:unclassified"
OUTCOME_OLD_HEAD=""
OUTCOME_NEW_HEAD=""
OUTCOME_ADVANCE=0
# set (not appended to OUTCOME_STATUS directly) if the dirty-classifier below
# self-heals class-b entries; folded into the terminal ok:* status so the
# heartbeat distinguishes a healed run from a routinely-clean one (§1 spec).
SELF_HEALED=0

write_outcome() {
  local rc="${1:-0}"
  local dir="${HOME}/.organism/last_seen"
  mkdir -p "$dir" 2>/dev/null || return 0
  local tmp="${dir}/wr2.deploy_pull.json.tmp.$$"
  printf '{"ts":"%s","status":"%s","old_head":"%s","new_head":"%s","advance_count":%s,"exit":%s}\n' \
    "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$OUTCOME_STATUS" "$OUTCOME_OLD_HEAD" \
    "$OUTCOME_NEW_HEAD" "${OUTCOME_ADVANCE:-0}" "$rc" > "$tmp" 2>/dev/null \
    && mv "$tmp" "${dir}/wr2.deploy_pull.json" 2>/dev/null || true
}
trap 'write_outcome $?' EXIT

if [[ -f "$SECRETS" ]]; then
  TELEGRAM_BOT_TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
  TELEGRAM_OWNER_CHAT_ID="$(grep '^TELEGRAM_OWNER_CHAT_ID=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
  export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID
fi

if command -v flock >/dev/null 2>&1; then
  exec 9>"$LOCK"
  if ! flock -n 9; then
    log "another deploy-pull is in progress, skipping"
    OUTCOME_STATUS="skipped:lock"
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

# ── tg_notify gateway (#2067): prefer the one true gate over raw send_telegram
# so alerts/heals show up in the P0/digest tiers instead of rotting behind the
# old per-key 6h cooldown (the incident this self-heal fixes sat silent for
# 2+ days because "dirty_worktree" was already in cooldown). Falls through to
# send_telegram if the gateway script is missing (e.g. a bootstrap clone with
# no scripts/ yet) or errors — never let notification wiring change exit codes.
TG_NOTIFY_PY="${WR2_TG_NOTIFY_PY:-${SOURCE_REPO}/scripts/tg_notify.py}"

tg_notify_or_fallback() {
  local tier="$1" key="$2" fallback_key="$3" text="$4"
  if [[ -f "$TG_NOTIFY_PY" ]]; then
    if python3 "$TG_NOTIFY_PY" --tier "$tier" --source wr2-deploy-pull \
        --dedup-key "$key" -- "$text" >>"$LOG" 2>&1; then
      return 0
    fi
    log "WARN: tg_notify.py failed (tier=${tier} key=${key}), falling back to send_telegram"
  fi
  send_telegram "$fallback_key" "$text"
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
    # rm -rf guard: only ever destroy a path that IS the canonical deploy dir
    # by name — a mistyped WR2_DEPLOY_DIR must not delete a real worktree.
    if [[ "$(basename "$DEPLOY_DIR")" == "nuzantara-deploy" ]]; then
      log "WARN: ${DEPLOY_DIR} is a worktree (.git is a file), not the required clone — removing + recloning"
      rm -rf "$DEPLOY_DIR" 2>>"$LOG"; git -C "$SOURCE_REPO" worktree prune 2>>"$LOG" || true
    else
      log "REFUSING rm -rf: basename(${DEPLOY_DIR}) != nuzantara-deploy"
      OUTCOME_STATUS="error:deploy-dir-suspect"
      exit 1
    fi
  fi
  if ! bootstrap_deploy_clone; then
    log "ERROR: deploy clone missing at ${DEPLOY_DIR}"
    send_telegram "deploy_missing" \
      "WR2 deploy CLONE missing at \`${DEPLOY_DIR}\`. Self-heal failed. Run: \`git clone --branch deploy/main https://github.com/Balizero1987/Teman2.git ~/Desktop/nuzantara-deploy\`"
    OUTCOME_STATUS="error:clone-missing"
    exit 1
  fi
fi

cd "$DEPLOY_DIR" || {
  log "ERROR: cannot cd to ${DEPLOY_DIR}"
  OUTCOME_STATUS="error:cd-failed"
  exit 1
}

CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
if [[ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]]; then
  log "ERROR: deploy worktree on branch=${CURRENT_BRANCH}, expected ${EXPECTED_BRANCH}"
  send_telegram "wrong_branch" \
    "WR2 deploy worktree on WRONG branch. Expected: \`${EXPECTED_BRANCH}\`. Found: \`${CURRENT_BRANCH}\`. Fix: \`cd ${DEPLOY_DIR} && git checkout ${EXPECTED_BRANCH}\`"
  OUTCOME_STATUS="error:wrong-branch"
  exit 1
fi

# ── Dirty-worktree classification + self-heal (W81/#2, incident 2026-07-05→07) ──
# The deploy clone is BY CONTRACT read-only runtime — any local modification is
# drift, never valuable work. A sibling session leaving one tracked-deleted
# plist (unstaged) froze code propagation for 2+ days because the OLD single
# DIRTY-block treated every porcelain line the same (alert once, cooldown-
# suppress, exit 1 forever). Classify instead of blanket-blocking:
#   (a) untracked (`?? `)              -> NOT blocking, just log+continue
#       (runtime junk: venvs/output dirs legitimately live in the clone)
#   (b) unstaged tracked mod/del       -> SELF-HEAL: git checkout -- <path>
#       (worktree col M/D, index col space or M — never touches staged/index)
#   (c) anything else (staged, renamed,
#       conflicts) or failed self-heal -> block as before (now via tg_notify P0)
DIRTY_RAW="$(git status --porcelain 2>/dev/null)"
if [[ -n "$DIRTY_RAW" ]]; then
  UNTRACKED_PATHS=()
  HEALABLE_PATHS=()
  BLOCKING_LINES=()
  while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    idx_col="${line:0:1}"
    wt_col="${line:1:1}"
    path="${line:3}"
    if [[ "$idx_col" == "?" && "$wt_col" == "?" ]]; then
      UNTRACKED_PATHS+=("$path")
    elif [[ ( "$idx_col" == " " || "$idx_col" == "M" ) && ( "$wt_col" == "M" || "$wt_col" == "D" ) ]]; then
      HEALABLE_PATHS+=("$path")
    else
      BLOCKING_LINES+=("$line")
    fi
  done <<< "$DIRTY_RAW"

  if (( ${#UNTRACKED_PATHS[@]} > 0 )); then
    preview="$(printf '%s, ' "${UNTRACKED_PATHS[@]:0:3}")"
    preview="${preview%, }"
    log "untracked entries present (${#UNTRACKED_PATHS[@]}) - not blocking: ${preview}$( (( ${#UNTRACKED_PATHS[@]} > 3 )) && echo " ...")"
  fi

  if (( ${#BLOCKING_LINES[@]} > 0 )); then
    first_blocking="${BLOCKING_LINES[0]}"
    log "ERROR: deploy worktree has non-healable local changes - first blocking entry: ${first_blocking}"
    tg_notify_or_fallback p0 "wr2-deploy-pull-dirty" "dirty_worktree" \
      "WR2 deploy worktree DIRTY (non-healable). First blocking entry: \`${first_blocking}\`. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
    OUTCOME_STATUS="error:dirty"
    exit 1
  fi

  if (( ${#HEALABLE_PATHS[@]} > 0 )); then
    if [[ "${WR2_DEPLOY_PULL_SELFHEAL:-1}" == "1" ]]; then
      if git checkout -- "${HEALABLE_PATHS[@]}" 2>>"$LOG"; then
        STILL_DIRTY="$(git status --porcelain -- "${HEALABLE_PATHS[@]}" 2>/dev/null)"
        if [[ -z "$STILL_DIRTY" ]]; then
          healed_preview="$(printf '%s, ' "${HEALABLE_PATHS[@]:0:3}")"
          healed_preview="${healed_preview%, }"
          log "self-healed dirty: ${healed_preview}$( (( ${#HEALABLE_PATHS[@]} > 3 )) && echo " ...")"
          tg_notify_or_fallback digest "wr2-deploy-pull-selfheal" "selfheal_worktree" \
            "WR2 deploy worktree self-healed ${#HEALABLE_PATHS[@]} dirty tracked path(s): \`${healed_preview}\`."
          SELF_HEALED=1
        else
          log "ERROR: self-heal ran but worktree still dirty for healable paths: ${STILL_DIRTY}"
          tg_notify_or_fallback p0 "wr2-deploy-pull-dirty" "dirty_worktree" \
            "WR2 deploy worktree self-heal FAILED to converge. Remaining: \`${STILL_DIRTY}\`. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
          OUTCOME_STATUS="error:dirty"
          exit 1
        fi
      else
        log "ERROR: git checkout -- self-heal failed"
        tg_notify_or_fallback p0 "wr2-deploy-pull-dirty" "dirty_worktree" \
          "WR2 deploy worktree self-heal FAILED (git checkout error). Inspect: \`cd ${DEPLOY_DIR} && git status\`."
        OUTCOME_STATUS="error:dirty"
        exit 1
      fi
    else
      first_healable="${HEALABLE_PATHS[0]}"
      log "ERROR: deploy worktree has local changes - first dirty entry:  M ${first_healable} (self-heal disabled: WR2_DEPLOY_PULL_SELFHEAL=0)"
      tg_notify_or_fallback p0 "wr2-deploy-pull-dirty" "dirty_worktree" \
        "WR2 deploy worktree DIRTY. First dirty entry: \` M ${first_healable}\`. Self-heal disabled. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
      OUTCOME_STATUS="error:dirty"
      exit 1
    fi
  fi
fi

if ! git fetch --quiet origin "$EXPECTED_BRANCH" 2>>"$LOG"; then
  if ! git fetch --quiet origin main 2>>"$LOG"; then
    log "ERROR: git fetch failed for both ${EXPECTED_BRANCH} and main"
    send_telegram "fetch_failed" \
      "WR2 deploy-pull: git fetch failed for \`${DEPLOY_DIR}\`. Check network and GitHub auth."
    OUTCOME_STATUS="error:fetch-failed"
    exit 1
  fi
fi

REMOTE_REF="origin/${EXPECTED_BRANCH}"
if ! git rev-parse --verify --quiet "$REMOTE_REF" >/dev/null; then
  REMOTE_REF="origin/main"
fi

LOCAL_HEAD="$(git rev-parse HEAD 2>>"$LOG")"
REMOTE_HEAD="$(git rev-parse "$REMOTE_REF" 2>>"$LOG")"
# set -e is off: a failed rev-parse yields an EMPTY var that would otherwise
# masquerade as divergence/ff errors downstream (red-team finding). Fail here
# with the real cause instead.
if [[ -z "$LOCAL_HEAD" || -z "$REMOTE_HEAD" ]]; then
  log "ERROR: git rev-parse produced empty head (local='${LOCAL_HEAD}' remote='${REMOTE_HEAD}')"
  OUTCOME_STATUS="error:rev-parse"
  exit 1
fi
OUTCOME_OLD_HEAD="$LOCAL_HEAD"
if [[ "$LOCAL_HEAD" == "$REMOTE_HEAD" ]]; then
  log "OK: already up-to-date (${LOCAL_HEAD:0:9})"
  state_set "last_status" "ok"
  state_set "last_run_ts" "$(now_epoch)"
  state_set "last_head" "$LOCAL_HEAD"
  OUTCOME_STATUS="ok:up-to-date"
  (( SELF_HEALED == 1 )) && OUTCOME_STATUS="ok:self-healed"
  OUTCOME_NEW_HEAD="$LOCAL_HEAD"
  exit 0
fi

AHEAD="$(git rev-list --count "${REMOTE_REF}..HEAD" 2>/dev/null || echo 0)"
if [[ "$AHEAD" =~ ^[0-9]+$ ]] && (( AHEAD > 0 )); then
  log "ERROR: deploy worktree is ${AHEAD} commit(s) ahead of ${REMOTE_REF} - refusing to merge"
  send_telegram "local_ahead" \
    "WR2 deploy worktree has LOCAL commits: ${AHEAD} ahead of \`${REMOTE_REF}\`. Inspect: \`cd ${DEPLOY_DIR} && git log ${REMOTE_REF}..HEAD\`."
  OUTCOME_STATUS="error:local-ahead"
  exit 1
fi

if ! git merge-base --is-ancestor "$LOCAL_HEAD" "$REMOTE_HEAD"; then
  log "ERROR: branches diverged - local=${LOCAL_HEAD:0:9} remote=${REMOTE_HEAD:0:9}"
  send_telegram "diverged" \
    "WR2 deploy-pull: branches DIVERGED. local \`${LOCAL_HEAD:0:9}\`, remote \`${REMOTE_HEAD:0:9}\`. Manual resolution required."
  OUTCOME_STATUS="error:diverged"
  exit 1
fi

if ! git merge --ff-only "$REMOTE_REF" >>"$LOG" 2>&1; then
  log "ERROR: git merge --ff-only failed unexpectedly"
  send_telegram "ff_failed" \
    "WR2 deploy-pull: ff-merge failed unexpectedly. Inspect: \`cd ${DEPLOY_DIR} && git status\`."
  OUTCOME_STATUS="error:ff-failed"
  exit 1
fi

NEW_HEAD="$(git rev-parse HEAD)"
COMMIT_COUNT="$(git rev-list --count "${LOCAL_HEAD}..${NEW_HEAD}" 2>/dev/null || echo ?)"
log "OK: fast-forwarded ${LOCAL_HEAD:0:9} -> ${NEW_HEAD:0:9} (${COMMIT_COUNT} commit(s))"
state_set "last_status" "advanced"
state_set "last_run_ts" "$(now_epoch)"
state_set "last_head" "$NEW_HEAD"
state_set "last_advance_count" "$COMMIT_COUNT"
OUTCOME_STATUS="ok:advanced"
(( SELF_HEALED == 1 )) && OUTCOME_STATUS="ok:self-healed"
OUTCOME_NEW_HEAD="$NEW_HEAD"
[[ "$COMMIT_COUNT" =~ ^[0-9]+$ ]] && OUTCOME_ADVANCE="$COMMIT_COUNT"

# ── C2 (flag-gated, DEFAULT OFF): wake the organs on the NEW code ────────────
# The one-shot html-apply worker gets a plain kickstart (its next run imports
# fresh code). The long-running supervisor + watchdog need `-k` (restart) or
# they keep executing the pre-pull code forever — the RUNTIME_STALE disease
# the C2 watchdog probe detects. OFF until armed (PENDING-ARMS ledger):
#   WR2_DEPLOY_PULL_KICKSTART=1
if [[ "${WR2_DEPLOY_PULL_KICKSTART:-0}" == "1" ]]; then
  UID_N="$(id -u)"
  if launchctl kickstart "gui/${UID_N}/com.balizero.wr2.html-apply" >>"$LOG" 2>&1; then
    log "kickstart html-apply OK"
  else
    log "WARN: kickstart html-apply failed (label not loaded?)"
  fi
  for svc in com.balizero.wr2.supervisor com.balizero.wr2.supervisor-watchdog; do
    if launchctl kickstart -k "gui/${UID_N}/${svc}" >>"$LOG" 2>&1; then
      log "kickstart -k ${svc} OK (daemon restarted on new code)"
    else
      log "WARN: kickstart -k ${svc} failed (label not loaded?)"
    fi
  done
else
  log "kickstart skipped (WR2_DEPLOY_PULL_KICKSTART != 1)"
fi
exit 0
