# wr2-deploy-pull (Pro-local script snapshot)

Live path: `~/scripts/wr2-deploy-pull.sh` (Pro only, **NOT** git-tracked).
Plist: `~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist`
(mirrored at `infra/launchagents/com.balizero.wr2.deploy-puller.plist`).
Sprint: Sprint C C1 (2026-05-08).

This snapshot is the contractual repo copy: any edit to the live script body must be reflected here in the same PR. Reviewers can audit puller logic via this file without granting them shell access to Pro.

## What it does

Every hour (`StartInterval=3600`, `RunAtLoad=true`) the script:

1. Verifies `~/Desktop/nuzantara-deploy` exists, is on `deploy/main`, and is clean.
2. Runs `git fetch origin deploy/main` (falls back to `origin/main` if the named branch is missing on origin).
3. If local already at remote → exit 0 with `last_status=ok`.
4. If local AHEAD of remote (operator wrote here) → P0 Telegram + exit 1.
5. If branches DIVERGED (neither is ancestor) → P0 Telegram + exit 1.
6. Otherwise `git merge --ff-only origin/<branch>` and log the advance count.

All failure paths Telegram-alert with a 6h per-key cooldown so a persistent
breakage doesn't spam the operator. State file:
`~/.agent/decisions/state/wr2_deploy_pull.state`.

## Why a dedicated puller (not nuz-sync)

- `nuz-sync` is git-sync between Pro and Air, NOT a memory-sync; the
  cicatrix scar "Untracked files lost when sibling automation switches
  branches" (2026-04-29) flagged `nuz-sync` as the prime suspect for
  incident #1. Reusing it for the deploy worktree would inherit the same
  branch-hijack risk.
- The deploy worktree is a SEPARATE git checkout pinned to branch
  `deploy/main`. It must never have local commits — operators work in
  `~/Desktop/nuzantara`. The puller enforces that contract.
- Cf. `discovery_worktree_deploy_isolation_2026_05_06.md`.

## Production wiring

`~/.openclaw/bin/wr2/wr2-script-wrapper.sh` defaults
`REPO_ROOT="${WR2_REPO_ROOT:-${HOME}/Desktop/nuzantara-deploy}"`. Every
WR2 cron (canva-apply, fact-extractor, fact-checker, supervisor,
image-generator) `cd $REPO_ROOT` before running its Python script. So
`git pull` here = "deploy" for the WR2 pipeline within ~1h.

## Bootstrap (one-time, manual operator step)

The puller assumes the deploy worktree exists. If it doesn't:

```bash
cd ~/Desktop/nuzantara
git fetch origin
# Create the worktree on the deploy/main branch (or on main directly if
# deploy/main does not exist).
git branch deploy/main origin/main 2>/dev/null || true
git worktree add ~/Desktop/nuzantara-deploy deploy/main
# Verify:
cd ~/Desktop/nuzantara-deploy && git rev-parse --abbrev-ref HEAD
# → deploy/main
```

Then bootstrap the LaunchAgent:

```bash
cp infra/launchagents/com.balizero.wr2.deploy-puller.plist ~/Library/LaunchAgents/
plutil -lint ~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist
launchctl print gui/$(id -u)/com.balizero.wr2.deploy-puller | head -20
chmod 0444 ~/Library/LaunchAgents/com.balizero.wr2.deploy-puller.plist
# Watch the first pull:
tail -f ~/logs/wr2-deploy-pull.log
```

## Test matrix

| Path | Setup | Stub | Expected |
|------|-------|------|----------|
| Healthy fast-forward | clean worktree, remote ahead | none | exit 0, log "fast-forwarded X → Y", state.last_status=advanced |
| Already up-to-date | clean worktree, remote == local | none | exit 0, log "already up-to-date" |
| Missing worktree | dir absent | none | exit 1, Telegram "deploy_missing" |
| Wrong branch | worktree on `feature/foo` | none | exit 1, Telegram "wrong_branch" |
| Dirty worktree | local modifications | none | exit 1, Telegram "dirty_worktree" |
| Local ahead | local commit not on remote | none | exit 1, Telegram "local_ahead" |
| Diverged | local + remote both have unique commits | none | exit 1, Telegram "diverged" |
| Cooldown active | recent alert in state | stub git | exit 1, log "alert suppressed" |

Tests run from the snapshot via `tests/lint/test_wr2_deploy_pull.sh`
(extracts the bash body, mounts a sandbox HOME with a local git fixture).

## Script body (mirror — keep byte-identical with `~/scripts/wr2-deploy-pull.sh`)

```bash
#!/usr/bin/env bash
# wr2-deploy-pull.sh — Sprint C C1 (2026-05-08)
#
# Auto-pulls origin/main into the WR2 deploy worktree at
# ~/Desktop/nuzantara-deploy so production cron scripts (canva-apply,
# fact-extractor, fact-checker, supervisor, image-generator) pick up
# merged code within DEPLOY_PULL_INTERVAL_SEC (default 1h via plist
# StartInterval=3600).
#
# Why a dedicated puller instead of `nuz-sync`:
# - nuz-sync is git-sync Pro↔Air, NOT memory-sync (cf. cicatrix scar
#   "Untracked files lost when sibling automation switches branches"
#   2026-04-29 — nuz-sync was the prime suspect for incident #1).
# - The deploy worktree is a SEPARATE git checkout pinned to branch
#   `deploy/main`; nuz-sync would not touch it. We need a worktree-
#   specific puller that's isolated from the main `~/Desktop/nuzantara`
#   working tree (preventing branch-hijack of in-progress dev work).
# - Cf. discovery_worktree_deploy_isolation_2026_05_06.md.
#
# Behavior:
# - flock single-instance (no overlap if a previous run is still in
#   flight, e.g. slow network).
# - `git fetch origin main` then `git merge --ff-only origin/main`. If
#   merge would NOT be fast-forward (someone wrote locally to the
#   deploy worktree), abort + Telegram P0 alert + exit 1. The deploy
#   worktree should NEVER have local commits — operators must work in
#   the main repo at ~/Desktop/nuzantara.
# - Telegram alerts gated by 6h cooldown via state file.
# - Logs every run to ~/logs/wr2-deploy-pull.log.

set -uo pipefail

DEPLOY_DIR="${WR2_DEPLOY_DIR:-${HOME}/Desktop/nuzantara-deploy}"
LOG="${HOME}/logs/wr2-deploy-pull.log"
STATE="${HOME}/.agent/decisions/state/wr2_deploy_pull.state"
LOCK="${HOME}/.agent/decisions/state/wr2_deploy_pull.lock"
SECRETS="${HOME}/.nuzantara-secrets.env"

ALERT_COOLDOWN_SEC=21600  # 6h between repeat alerts on the same key

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")"

log() {
  printf '%s [wr2-deploy-pull] %s\n' \
    "$(date '+%Y-%m-%d %H:%M:%S WITA')" "$*" >> "$LOG"
}

# Pull only TELEGRAM_* from secrets (same pattern as the OAuth
# watchdog: don't poison subprocess env with OPENROUTER_API_KEY etc.).
if [[ -f "$SECRETS" ]]; then
  TELEGRAM_BOT_TOKEN="$(grep '^TELEGRAM_BOT_TOKEN=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"' )" || true
  TELEGRAM_OWNER_CHAT_ID="$(grep '^TELEGRAM_OWNER_CHAT_ID=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"' )" || true
  export TELEGRAM_BOT_TOKEN TELEGRAM_OWNER_CHAT_ID
fi

# Single-instance lock.
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
  [[ -z "$last" || ! "$last" =~ ^[0-9]+$ ]] && return 0  # never alerted → due
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

# ─────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────

log "deploy-pull start dir=${DEPLOY_DIR}"

# 1. Worktree must exist. We do NOT auto-create it (operator-controlled
#    one-time setup) — alert and exit instead. Cf. memory
#    `discovery_worktree_deploy_isolation_2026_05_06.md` for the
#    canonical setup commands.
if [[ ! -d "$DEPLOY_DIR/.git" && ! -f "$DEPLOY_DIR/.git" ]]; then
  log "ERROR: deploy worktree missing at ${DEPLOY_DIR}"
  send_telegram "deploy_missing" \
    "🚨 *WR2 deploy worktree MISSING*\nExpected at \`${DEPLOY_DIR}\`.\n\nRun once: \`cd ~/Desktop/nuzantara && git worktree add ~/Desktop/nuzantara-deploy -b deploy/main origin/main\`"
  exit 1
fi

cd "$DEPLOY_DIR" || {
  log "ERROR: cannot cd to ${DEPLOY_DIR}"
  exit 1
}

# 2. Verify on the expected branch (deploy/main). A different branch
#    means an operator manually checked out something — treat as a
#    misconfiguration alert (don't auto-correct).
CURRENT_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)"
EXPECTED_BRANCH="${WR2_DEPLOY_BRANCH:-deploy/main}"
if [[ "$CURRENT_BRANCH" != "$EXPECTED_BRANCH" ]]; then
  log "ERROR: deploy worktree on branch=${CURRENT_BRANCH}, expected ${EXPECTED_BRANCH}"
  send_telegram "wrong_branch" \
    "🚨 *WR2 deploy worktree on WRONG branch*\nExpected: \`${EXPECTED_BRANCH}\`\nFound: \`${CURRENT_BRANCH}\`\n\nFix: \`cd ${DEPLOY_DIR} && git checkout ${EXPECTED_BRANCH}\`"
  exit 1
fi

# 3. Fast-forward only — refuse to merge if someone added local commits
#    or modified tracked files in the deploy worktree.
DIRTY="$(git status --porcelain 2>/dev/null | head -1)"
if [[ -n "$DIRTY" ]]; then
  log "ERROR: deploy worktree has local changes — first dirty entry: ${DIRTY}"
  send_telegram "dirty_worktree" \
    "🚨 *WR2 deploy worktree DIRTY*\nLocal modifications block fast-forward pull.\nFirst dirty entry: \`${DIRTY}\`\n\nFix: inspect \`cd ${DEPLOY_DIR} && git status\`. The deploy worktree should ONLY contain origin/main commits — work in \`~/Desktop/nuzantara\`."
  exit 1
fi

# 4. Fetch + fast-forward.
if ! git fetch --quiet origin "$EXPECTED_BRANCH" 2>>"$LOG"; then
  # Fly back to the canonical name in case the branch on origin is
  # truly `main` (some setups use deploy/main as a rename of main).
  if ! git fetch --quiet origin main 2>>"$LOG"; then
    log "ERROR: git fetch failed for both ${EXPECTED_BRANCH} and main"
    send_telegram "fetch_failed" \
      "🚨 *WR2 deploy-pull: git fetch failed*\n\`${DEPLOY_DIR}\` could not reach origin. Check network + Github auth."
    exit 1
  fi
fi

REMOTE_REF="origin/${EXPECTED_BRANCH}"
# If origin/deploy/main isn't a thing, fall back to origin/main.
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

# Ahead-check: if local is ahead of remote → operator wrote here.
AHEAD="$(git rev-list --count "${REMOTE_REF}..HEAD" 2>/dev/null || echo 0)"
if [[ "$AHEAD" =~ ^[0-9]+$ ]] && (( AHEAD > 0 )); then
  log "ERROR: deploy worktree is ${AHEAD} commit(s) ahead of ${REMOTE_REF} — refusing to merge"
  send_telegram "local_ahead" \
    "🚨 *WR2 deploy worktree has LOCAL commits*\n${AHEAD} commits ahead of \`${REMOTE_REF}\`.\nThe deploy worktree is meant to be read-only. Inspect:\n\`cd ${DEPLOY_DIR} && git log ${REMOTE_REF}..HEAD\`"
  exit 1
fi

# Diverged-check: if neither is an ancestor of the other → conflict.
if ! git merge-base --is-ancestor "$LOCAL_HEAD" "$REMOTE_HEAD"; then
  log "ERROR: branches diverged — local=${LOCAL_HEAD:0:9} remote=${REMOTE_HEAD:0:9}"
  send_telegram "diverged" \
    "🚨 *WR2 deploy-pull: branches DIVERGED*\nlocal HEAD \`${LOCAL_HEAD:0:9}\` is not an ancestor of \`${REMOTE_REF}\` (\`${REMOTE_HEAD:0:9}\`). Manual resolution required:\n\`cd ${DEPLOY_DIR} && git status && git log --oneline ${LOCAL_HEAD}..${REMOTE_HEAD}\`"
  exit 1
fi

# All clear — fast-forward.
if ! git merge --ff-only "$REMOTE_REF" >>"$LOG" 2>&1; then
  log "ERROR: git merge --ff-only failed unexpectedly"
  send_telegram "ff_failed" \
    "🚨 *WR2 deploy-pull: ff-merge failed unexpectedly*\nManual investigation: \`cd ${DEPLOY_DIR} && git status\`"
  exit 1
fi

NEW_HEAD="$(git rev-parse HEAD)"
COMMIT_COUNT="$(git rev-list --count "${LOCAL_HEAD}..${NEW_HEAD}" 2>/dev/null || echo ?)"
log "OK: fast-forwarded ${LOCAL_HEAD:0:9} → ${NEW_HEAD:0:9} (${COMMIT_COUNT} commit(s))"
state_set "last_status" "advanced"
state_set "last_run_ts" "$(now_epoch)"
state_set "last_head" "$NEW_HEAD"
state_set "last_advance_count" "$COMMIT_COUNT"
exit 0
```

## Operator runbook

When a Telegram alert fires:

| Alert key | Cause | Fix |
|---|---|---|
| `deploy_missing` | `~/Desktop/nuzantara-deploy` removed | Re-create via `git worktree add` (see Bootstrap above) |
| `wrong_branch` | manual checkout to a non-`deploy/main` branch | `cd ~/Desktop/nuzantara-deploy && git checkout deploy/main` |
| `dirty_worktree` | local edits to tracked files | `git status` then `git stash` or revert; deploy worktree must be clean |
| `local_ahead` | someone committed in the deploy dir | Cherry-pick the commit(s) into the main repo, then `git reset --hard origin/deploy/main` here |
| `diverged` | force-push on origin OR rebase mid-flight | Operator-judgement reset/recreate; `discovery_worktree_deploy_isolation_2026_05_06.md` documents the canonical recipe |
| `fetch_failed` | network or GitHub auth issue | `gh auth status`, check VPN/NordVPN |
| `ff_failed` | unexpected git error | Inspect `git status` + `~/logs/wr2-deploy-pull.log` |
