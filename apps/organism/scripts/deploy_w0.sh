#!/usr/bin/env bash
#
# deploy_w0.sh — install Wave 0 LaunchAgent plist into ~/Library/LaunchAgents
# with a 5-trigger abort guard against the cicatrix STRUCTURAL plist-corruption
# (P0-3, 2026-04-29 — 51/54 plist truncated by an unidentified producer).
#
# Pattern: per Zero Q1 22:08 WITA — bootout/bootstrap (NOT load/unload).
# For each plist in PLISTS: chmod u+w on target if present → bootout
# (idempotent) → cp from repo → plutil -lint → chmod 0444 → bootstrap →
# verify "state = running" within VERIFY_TIMEOUT_SECONDS. Any failure
# rolls back this plist and aborts.
#
# Triggers (any one fires the abort + Telegram alert):
#   1. plutil -lint exit != 0 after cp
#   2. file size < MIN_PLIST_BYTES after cp
#   3. launchctl bootstrap exit != 0
#   4. presence of new .bak-* / .disabled / .backup-* files in
#      ~/Library/LaunchAgents/com.{nuzantara,balizero,cell}.* not seen pre-cp
#   5. launchctl print gui/$(id -u)/<label> doesn't show "state = running"
#      within VERIFY_TIMEOUT_SECONDS
#
# Usage:
#   ./deploy_w0.sh                    # full deploy
#   DRY_RUN=1 ./deploy_w0.sh          # validate without touching launchd
#
# Env (optional):
#   TELEGRAM_BOT_TOKEN, TELEGRAM_OWNER_CHAT_ID — for abort alert (defaults to 1125336968)
#   ORGANISM_REPO — repo dir (defaults to /Users/nuzantara/Desktop/nuzantara/apps/organism)
#   VERIFY_TIMEOUT_SECONDS — bootstrap-to-running timeout (default 30)
#
# Authoritative spec: docs/innervation-2026-04-29/99c_w0a_bis_kickoff.md §3.3
# Cicatrix ref: .claude/rules/cicatrix-scars.md "Unknown agent overwrites
# loaded LaunchAgent plist files" (2026-04-29 15:09 + 16:05).

set -euo pipefail

# ----- config ---------------------------------------------------------------

ORGANISM_REPO="${ORGANISM_REPO:-/Users/nuzantara/Desktop/nuzantara/apps/organism}"
REPO="${ORGANISM_REPO}/organism/launchd"
TARGET="${HOME}/Library/LaunchAgents"
VERIFY_TIMEOUT_SECONDS="${VERIFY_TIMEOUT_SECONDS:-30}"
MIN_PLIST_BYTES=500
DRY_RUN="${DRY_RUN:-0}"

# Plists deployed in this wave. Order matters: supervisor first (consumes
# the bus), control-panel second (admin UI), scheduled-tick last (cron).
PLISTS=(
  com.nuzantara.organism.supervisor.plist
  com.nuzantara.organism.control-panel.plist
  com.nuzantara.organism.scheduled-tick.plist
)

CHAT_ID="${TELEGRAM_OWNER_CHAT_ID:-1125336968}"
UID_NUM="$(id -u)"

# ----- helpers --------------------------------------------------------------

plist_label() {
  # com.nuzantara.organism.supervisor.plist → com.nuzantara.organism.supervisor
  local f=$1
  echo "${f%.plist}"
}

snapshot_target_dir() {
  # Capture .bak-* / .disabled / .backup-* files currently in TARGET so we
  # can detect new ones post-cp (trigger 4 — quarantine pattern).
  if [ ! -d "$TARGET" ]; then
    return 0
  fi
  find "$TARGET" -maxdepth 1 -type f \
    \( -name 'com.nuzantara.*.bak-*' \
    -o -name 'com.balizero.*.bak-*' \
    -o -name 'com.cell.*.bak-*' \
    -o -name 'com.nuzantara.*.disabled' \
    -o -name 'com.balizero.*.disabled' \
    -o -name 'com.cell.*.disabled' \
    -o -name 'com.nuzantara.*.backup-*' \
    -o -name 'com.balizero.*.backup-*' \
    -o -name 'com.cell.*.backup-*' \
    \) 2>/dev/null | sort
}

abort() {
  local trigger=$1 plist=$2 msg=$3
  echo "🔴 W0-B ABORT — trigger=$trigger plist=$plist msg=$msg" >&2

  # Best-effort rollback: bootout the half-deployed service + remove the file.
  if [ "$DRY_RUN" != "1" ]; then
    local label
    label=$(plist_label "$plist")
    launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true
    if [ -f "$TARGET/$plist" ]; then
      chmod u+w "$TARGET/$plist" 2>/dev/null || true
      rm -f "$TARGET/$plist"
    fi
  fi

  # Persist for cross-session visibility (best-effort).
  if [ -x "$HOME/.claude/scripts/mem" ]; then
    "$HOME/.claude/scripts/mem" save unresolved \
      "W0-B abort trigger=$trigger plist=$plist msg=$msg ts=$(date -u +%FT%TZ)" \
      7 2>/dev/null || true
  fi

  # Telegram alert (best-effort).
  if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
      -d "chat_id=${CHAT_ID}" \
      --data-urlencode "text=🔴 W0-B ABORT — P0-3 plist corruption signal detected during deploy
Trigger: $trigger
Plist: $plist
Msg: $msg
Time: $(date -u +%FT%TZ)
State: rolled back, organism still on pre-W0 baseline
Next: Zero needs to triage producer before W0-B retry" \
      >/dev/null 2>&1 || true
  fi

  exit 1
}

deploy_one() {
  local plist=$1
  local src="$REPO/$plist"
  local dst="$TARGET/$plist"
  local label
  label=$(plist_label "$plist")

  if [ ! -f "$src" ]; then
    abort "src_missing" "$plist" "no $src in repo"
  fi

  echo "→ deploy $plist (label=$label)"

  if [ "$DRY_RUN" = "1" ]; then
    plutil -lint "$src" || abort "1_plutil_lint_dry" "$plist" "repo source fails lint"
    local size
    size=$(wc -c <"$src" | tr -d ' ')
    if [ "$size" -lt "$MIN_PLIST_BYTES" ]; then
      abort "2_size_dry" "$plist" "repo source $size bytes < $MIN_PLIST_BYTES"
    fi
    echo "  [DRY] would bootout/cp/bootstrap label=$label"
    return 0
  fi

  # 1. Snapshot quarantine files before mutation.
  local pre_snap
  pre_snap=$(snapshot_target_dir)

  # 2. Bootout (idempotent — succeeds even if not loaded).
  launchctl bootout "gui/${UID_NUM}/${label}" 2>/dev/null || true

  # 3. chmod u+w if existing target (P0-3 hardening makes plist 0444/0400).
  if [ -f "$dst" ]; then
    chmod u+w "$dst" 2>/dev/null || true
  fi

  # 4. cp from repo.
  install -m 0644 "$src" "$dst"

  # 5. trigger 1 — plutil lint.
  if ! plutil -lint "$dst" >/dev/null; then
    abort "1_plutil_lint" "$plist" "lint failed after cp"
  fi

  # 6. trigger 2 — file size.
  local size
  size=$(wc -c <"$dst" | tr -d ' ')
  if [ "$size" -lt "$MIN_PLIST_BYTES" ]; then
    abort "2_size" "$plist" "deployed file $size bytes < $MIN_PLIST_BYTES"
  fi

  # 7. trigger 4 — quarantine snapshot delta.
  local post_snap
  post_snap=$(snapshot_target_dir)
  if [ "$pre_snap" != "$post_snap" ]; then
    abort "4_quarantine" "$plist" \
      "new .bak/.disabled/.backup file appeared in $TARGET during cp"
  fi

  # 8. Read-only mode (P0-3 hardening parity).
  chmod 0444 "$dst"

  # 9. trigger 3 — bootstrap.
  if ! launchctl bootstrap "gui/${UID_NUM}" "$dst" 2>&1; then
    abort "3_bootstrap" "$plist" "launchctl bootstrap exited non-zero"
  fi

  # 10. trigger 5 — verify "state = running" within timeout.
  local elapsed=0
  local seen_running=0
  while [ "$elapsed" -lt "$VERIFY_TIMEOUT_SECONDS" ]; do
    if launchctl print "gui/${UID_NUM}/${label}" 2>/dev/null \
        | grep -qE 'state = running'; then
      seen_running=1
      break
    fi
    sleep 1
    elapsed=$((elapsed + 1))
  done
  if [ "$seen_running" != "1" ]; then
    abort "5_state_running" "$plist" \
      "launchctl print did not show 'state = running' within ${VERIFY_TIMEOUT_SECONDS}s"
  fi

  echo "  ✓ $plist deployed and running"
}

# ----- main -----------------------------------------------------------------

main() {
  if [ ! -d "$REPO" ]; then
    echo "🔴 ABORT — repo launchd dir missing: $REPO" >&2
    exit 1
  fi

  if [ ! -d "$TARGET" ] && [ "$DRY_RUN" != "1" ]; then
    mkdir -p "$TARGET"
  fi

  local plist
  for plist in "${PLISTS[@]}"; do
    deploy_one "$plist"
  done

  echo "✅ W0-B deploy complete (${#PLISTS[@]} plist deployed)"
}

main "$@"
