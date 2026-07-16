#!/usr/bin/env bash
# runtime-reconcile.sh — anti-W81 reconciliation watchdog (SPEC runtime/dev split, P0).
#
# THE SCAR IT KILLS: ~/nuzantara-deploy (the stable runtime checkout the launchd
# organs are meant to run from) VANISHED once and nobody noticed for weeks (W81). The
# deploy-puller kept exiting 1 in silence; 20 organs ran at nothing. This watchdog makes
# the absence LOUD — the reconciliation-report pattern of superscar #2 (built-but-vanished
# is suspended, not alive).
#
# It is a SIGNALLER, not an actuator: it never restarts/moves/heals anything. It asserts
# invariants and pages the operator. Lives OUTSIDE both checkouts by intent (so a vanished
# repo cannot take its own watchdog down with it) — install the live copy under ~/scripts
# via the P1 installer; this repo copy is the source of truth (cmp-checked, anti HOME-fork #1).
#
# INERT in P0: nothing is migrated yet, so by default it only checks what EXISTS and warns
# (never P0-pages) unless RUNTIME_RECONCILE_STRICT=1. Kill switch: NUZ_RUNTIME_RECONCILE_DISABLED=1.
#
# Exit: 0 = all invariants hold (or disabled). 1 = a P0/invariant breach was found+alerted.
set -uo pipefail

DEPLOY_DIR="${WR2_DEPLOY_DIR:-${HOME}/nuzantara-deploy}"
SOURCE_REPO="${WR2_SOURCE_REPO:-${HOME}/nuzantara}"
DEPLOY_BRANCH="${WR2_DEPLOY_BRANCH:-deploy/main}"
MAX_PULL_AGE_SEC="${RUNTIME_RECONCILE_MAX_PULL_AGE_SEC:-7200}"   # deploy must have pulled within 2h
STRICT="${RUNTIME_RECONCILE_STRICT:-0}"                          # P0 default 0 = warn, don't page
PULL_STATE="${HOME}/.agent/decisions/state/wr2_deploy_pull.state"
LOG="${HOME}/logs/runtime-reconcile.log"
STATE="${HOME}/.organism/last_seen/pro.runtime_reconcile.json"
SECRETS="${HOME}/.nuzantara-secrets.env"
ALERT_COOLDOWN_SEC="${RUNTIME_RECONCILE_ALERT_COOLDOWN_SEC:-21600}"
ALERT_STAMP="${HOME}/.agent/decisions/state/runtime_reconcile.alert"

mkdir -p "$(dirname "$LOG")" "$(dirname "$STATE")" "$(dirname "$ALERT_STAMP")"

log() { printf '%s [runtime-reconcile] %s\n' "$(date '+%Y-%m-%d %H:%M:%S WITA')" "$*" >> "$LOG"; }

if [[ "${NUZ_RUNTIME_RECONCILE_DISABLED:-0}" == "1" ]]; then
  log "disabled via NUZ_RUNTIME_RECONCILE_DISABLED=1 — skipping"
  exit 0
fi

# Best-effort Telegram, with cooldown so we never spam. Never fatal if it fails.
alert() {
  local msg="$1"
  log "ALERT: $msg"
  local now; now="$(date +%s)"
  if [[ -f "$ALERT_STAMP" ]]; then
    local last; last="$(cat "$ALERT_STAMP" 2>/dev/null || echo 0)"
    if (( now - last < ALERT_COOLDOWN_SEC )); then
      log "alert within cooldown — not paging again"
      return 0
    fi
  fi
  if [[ -f "$SECRETS" ]]; then
    local tok cid
    tok="$(grep '^TELEGRAM_BOT_TOKEN=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
    cid="$(grep '^TELEGRAM_OWNER_CHAT_ID=' "$SECRETS" | head -1 | cut -d= -f2- | tr -d '"')" || true
    if [[ -n "${tok:-}" && -n "${cid:-}" ]]; then
      curl -s -m 10 "https://api.telegram.org/bot${tok}/sendMessage" \
        --data-urlencode "chat_id=${cid}" \
        --data-urlencode "text=🛟 runtime-reconcile P0 breach: ${msg}" >/dev/null 2>&1 || true
    fi
  fi
  echo "$now" > "$ALERT_STAMP"
}

# A3 (reflexion-che-impara) call-site: when a breach is a VERIFIED failure of the organism,
# persist it as a promoted lesson to MOS (type=pattern, importance>=7 → auto-loaded at next
# SessionStart = the cross-session retrieval half for free). This is the loop-closing half A3
# lacked: save_lesson_mos had ZERO live callers (TAC 2026-06-27). A reconcile breach is the
# textbook "verified failure" — it only fires after the invariant checks actually ran on disk,
# so it satisfies the promote-gate (no hallucinated lesson auto-persists). Best-effort: never
# fatal if mem CLI is absent (graceful degradation, same as the reflexion lib's except path).
MEM_CLI="${HOME}/.claude/scripts/mem"
LESSON_STAMP="${HOME}/.agent/decisions/state/runtime_reconcile.lesson"
LESSON_COOLDOWN_SEC="${RUNTIME_RECONCILE_LESSON_COOLDOWN_SEC:-86400}"   # 1 lesson/day max
save_lesson() {
  local lesson="$1"
  [[ -x "$MEM_CLI" ]] || return 0
  local now; now="$(date +%s)"
  if [[ -f "$LESSON_STAMP" ]]; then
    local last; last="$(cat "$LESSON_STAMP" 2>/dev/null || echo 0)"
    (( now - last < LESSON_COOLDOWN_SEC )) && return 0   # dedup: don't re-learn the same breach daily
  fi
  "$MEM_CLI" save pattern "[reflexion:runtime_reconcile] ${lesson}" 7 >/dev/null 2>&1 || true
  echo "$now" > "$LESSON_STAMP"
  log "A3: persisted breach lesson to MOS (auto-loads next SessionStart)"
}

breaches=0
note() { breaches=$((breaches+1)); log "INVARIANT BREACH: $*"; }

# --- Invariant 1: the deploy runtime checkout must exist (the W81 check) ---
deploy_exists=true
if [[ ! -e "$DEPLOY_DIR/.git" ]]; then
  deploy_exists=false
  note "deploy runtime checkout missing: $DEPLOY_DIR (W81 vector)"
fi

# --- Invariant 2: deploy is a CLONE, not a worktree sharing the dirty main's .git ---
# (council decision Q1: full clone, never worktree — isolates the runtime from the main's
#  sibling-race / .git churn, scar W63/#5). A clone has .git as a DIR; a worktree as a FILE.
# 2026-06-27: the clone IS feasible (HEAD tree is only ~0.9GB; the 45G repo was venv +
#  node_modules + .worktrees which a clone does NOT materialize). Done — so a worktree here
#  is now a real regression, not the disk-bound compromise it briefly was.
if $deploy_exists; then
  if [[ -f "$DEPLOY_DIR/.git" ]]; then
    note "deploy checkout is a git WORKTREE (.git is a file) — must be a full clone (scar W63/#5)"
  fi
fi

# --- Invariant 3: deploy on the expected branch ---
if $deploy_exists; then
  cur_branch="$(git -C "$DEPLOY_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
  if [[ "$cur_branch" != "$DEPLOY_BRANCH" && "$cur_branch" != "main" ]]; then
    note "deploy on unexpected branch '$cur_branch' (want '$DEPLOY_BRANCH' or 'main')"
  fi
fi

# --- Invariant 4: deploy pulled recently (puller not silently dead, the other half of W81) ---
if $deploy_exists && [[ -f "$PULL_STATE" ]]; then
  pull_mtime="$(stat -f %m "$PULL_STATE" 2>/dev/null || echo 0)"
  age=$(( $(date +%s) - pull_mtime ))
  if (( age > MAX_PULL_AGE_SEC )); then
    note "deploy pull is stale: ${age}s since last pull-state (> ${MAX_PULL_AGE_SEC}s) — puller may be dead"
  fi
fi

# --- write heartbeat (organism A2-observable) ---
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
status="ok"; [[ $breaches -gt 0 ]] && status="degraded"
printf '{"ts":"%s","status":"%s","note":"breaches=%d deploy_exists=%s strict=%s"}\n' \
  "$ts" "$status" "$breaches" "$deploy_exists" "$STRICT" > "$STATE" 2>/dev/null || true

if (( breaches > 0 )); then
  # A3: a confirmed breach is a verified organism failure → learn it (cooldown-deduped).
  save_lesson "runtime-root breach detected (deploy_exists=${deploy_exists}, breaches=${breaches}). W81 vector recurred — check ~/nuzantara-deploy + the deploy-puller before trusting any merge reached the live organs."
  if [[ "$STRICT" == "1" ]]; then
    alert "$breaches invariant breach(es) — see $LOG"
    exit 1
  else
    log "P0 mode (STRICT=0): $breaches breach(es) recorded but not paging (split not armed yet)"
    exit 0
  fi
fi

log "all runtime invariants hold (deploy_exists=$deploy_exists)"
exit 0
