#!/bin/zsh
# scripts/translate-articles-cron-wrapper.sh
#
# Structural fix for the 2026-08-07 "mouth main-dirt" disease: translate-articles.py
# had zero git awareness and wrote hourly straight into ~/nuzantara's TRACKED working
# tree via com.balizero.translate.hourly — 48 files sat dirty for 2+ days, tripping
# the proprioception git_alignment gate and blocking the worktree-isolation
# ff-only-pull exception. This wrapper runs the script inside an isolated, ephemeral
# worktree (scripts/agent_start.py, lane=mouth) instead — the main checkout is never
# touched — and auto-promotes any output via a PR with auto-merge armed. Most hourly
# runs are no-ops (source_sha256 freshness check finds nothing stale), so the
# worktree is created and released again within the same run when there is nothing
# to promote.
#
# Invoked by ~/Library/LaunchAgents/com.balizero.translate.hourly.plist (plain
# `/bin/zsh <this-script>`, no -lc — a login-shell invocation reads as an INLINE
# shell string to infra/organ-conformance/check_organ_conformance.py, which then
# analyzes the argv join instead of resolving this file and reports every content
# gene missing. `gh`/`git` resolve fine from a non-login shell as long as PATH/HOME
# are set, which the plist's EnvironmentVariables already do — same non-`-lc`
# pattern as com.balizero.nb-curator.daily.plist and com.balizero.zoho-mail-loop.daily.plist),
# which now points at THIS script instead of calling translate-articles.py directly.
set -uo pipefail

# G5_kill_switch (organ-conformance): TRANSLATE_HOURLY_ENABLED=false disables the
# run without touching the plist. Defaults to enabled.
if [ "${TRANSLATE_HOURLY_ENABLED:-true}" != "true" ]; then
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] TRANSLATE_HOURLY_ENABLED=false — skipping run" >>"${HOME}/logs/translate-hourly-wrapper.log"
  exit 0
fi

REPO_ROOT="${HOME}/nuzantara"
LOG="${HOME}/logs/translate-hourly-wrapper.log"
mkdir -p "$(dirname "$LOG")"

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

# G2_heartbeat (organ-conformance): proof of life at ~/.organism/last_seen/<id>.json,
# which is what organs_registry.yaml's pro.translate_hourly bridge_source and the
# stale-detector actually read. Invoked under `bash`, never sourced — this wrapper
# is zsh and heartbeat.sh declares `local status=…`, which dies on zsh's read-only
# `status` special parameter (same fix as scripts/nb-curator-daily.sh, 2026-07-29).
# The EXIT trap covers paths nobody wrote a verdict on purpose (an unset variable
# under `set -u`, a `cd` failure before the first heartbeat call): without it those
# runs leave NO sidecar, which reads as "never scheduled" rather than "died" — the
# two cures differ (cicatrix-superscar.md #2, "Esiste ≠ Armato").
ORGAN_ID="pro.translate_hourly"
SCRIPT_DIR="${0:A:h}"
if [ -n "${ORGANISM_HEARTBEAT_LIB:-}" ]; then
  HEARTBEAT_LIB="$ORGANISM_HEARTBEAT_LIB"
elif [ -r "$SCRIPT_DIR/lib/heartbeat.sh" ]; then
  HEARTBEAT_LIB="$SCRIPT_DIR/lib/heartbeat.sh"
else
  HEARTBEAT_LIB="$HOME/scripts/lib/heartbeat.sh"
fi
HB_EMITTED=0
heartbeat() {  # heartbeat <status> [note]
  HB_EMITTED=1
  [ -f "$HEARTBEAT_LIB" ] || return 0
  bash "$HEARTBEAT_LIB" "$ORGAN_ID" "$1" "${2:-}" || true
}
_hb_on_exit() {
  local rc=$?
  if [ "$HB_EMITTED" -eq 0 ]; then
    heartbeat error "aborted before verdict (rc=$rc)"
  fi
  return 0
}
trap _hb_on_exit EXIT

cd "$REPO_ROOT" || {
  log "FATAL: cannot cd to $REPO_ROOT"
  exit 1
}

# Opportunistic reap of a PREVIOUS run's worktree, now that its PR (if any) may have
# merged in the meantime. Best-effort and safe either way: agent_start.py's own
# merged-into-base guard refuses to touch a worktree whose PR is still open, so this
# never races a pending promotion.
python3 scripts/agent_start.py --cleanup >>"$LOG" 2>&1

TASK_ID="hourly-$(date +%Y%m%d%H%M%S)"
CREATE_OUT=$(python3 scripts/agent_start.py --lane mouth --task-id "$TASK_ID" --ttl-min 30 2>>"$LOG")
WT_PATH=$(print -r -- "$CREATE_OUT" | awk '/^WORKTREE_READY/ {print $2}')
if [ -z "$WT_PATH" ] || [ ! -d "$WT_PATH" ]; then
  log "FATAL: worktree creation failed: $CREATE_OUT"
  heartbeat error "worktree creation failed"
  exit 1
fi
log "worktree ready: $WT_PATH (task_id=$TASK_ID)"

# translate-articles.py's venv lives at the top-level (not apps/backend-rag/.venv,
# the only one agent_start.py symlinks into new worktrees) — link it in explicitly.
ln -sfn "$REPO_ROOT/.venv" "$WT_PATH/.venv"

NUZANTARA_REPO_ROOT="$WT_PATH" "$WT_PATH/.venv/bin/python" "$WT_PATH/scripts/translate-articles.py" "$@" >>"$LOG" 2>&1
RUN_RC=$?
log "translate-articles.py exit=$RUN_RC"

# Non-zero here does NOT short-circuit: translate-articles.py can leave partial,
# still-worth-promoting output behind it (some files translated before a later
# failure), so whatever it wrote is still detected and promoted below. RUN_RC is
# folded into the heartbeat verdict at each concluding branch and is still this
# process's own exit code at the bottom.
CHANGED=$(git -C "$WT_PATH" status --porcelain -- apps/mouth/src/content/articles | wc -l | tr -d ' ')

if [ "$CHANGED" -gt 0 ]; then
  log "$CHANGED file(s) changed — promoting via PR"
  BRANCH=$(git -C "$WT_PATH" branch --show-current)

  git -C "$WT_PATH" add apps/mouth/src/content/articles
  git -C "$WT_PATH" commit -m "$(
    cat <<EOF
chore(mouth): promote $CHANGED hourly-translated article file(s)

Auto-generated by scripts/translate-articles.py (com.balizero.translate.hourly),
run in an isolated worktree via scripts/translate-articles-cron-wrapper.sh so the
main checkout is never written to directly. Re-translation triggered by
source_sha256 staleness detection.

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
  )" >>"$LOG" 2>&1

  git -C "$WT_PATH" push -u origin "$BRANCH" >>"$LOG" 2>&1
  PUSH_RC=$?
  if [ "$PUSH_RC" -ne 0 ]; then
    log "ERROR: push failed rc=$PUSH_RC — leaving worktree $WT_PATH for manual recovery"
    heartbeat error "push failed rc=$PUSH_RC ($CHANGED file(s) stranded in $WT_PATH)"
    exit 1
  fi

  PR_URL=$(gh pr create --base main --head "$BRANCH" \
    --title "chore(mouth): promote hourly-translated articles ($CHANGED file(s))" \
    --body "Automated promotion of scripts/translate-articles.py output. See scripts/translate-articles-cron-wrapper.sh for the pipeline." \
    2>>"$LOG")
  CREATE_RC=$?
  if [ "$CREATE_RC" -ne 0 ]; then
    log "ERROR: gh pr create failed rc=$CREATE_RC — branch pushed, PR NOT opened, manual recovery: gh pr create --head $BRANCH"
    heartbeat error "gh pr create failed rc=$CREATE_RC (branch $BRANCH pushed, PR not opened)"
    exit 1
  fi
  log "opened PR: $PR_URL"
  PR_NUM=$(print -r -- "$PR_URL" | grep -oE '[0-9]+$')
  # NOT --squash: once a merge queue governs main, the ruleset owns the merge
  # method and --squash is rejected outright (pipeline-ship skill, 2026-07-27+).
  RUN_NOTE=""
  [ "$RUN_RC" -ne 0 ] && RUN_NOTE=" (translate-articles.py exit=$RUN_RC — partial output)"
  if gh pr merge "$PR_NUM" --auto >>"$LOG" 2>&1; then
    heartbeat ok "promoted $CHANGED file(s) via $PR_URL (auto-merge armed)$RUN_NOTE"
  else
    log "WARN: could not arm auto-merge on PR #$PR_NUM — needs manual arm"
    heartbeat degraded "promoted $CHANGED file(s) via $PR_URL but auto-merge did not arm$RUN_NOTE"
  fi
  log "worktree $WT_PATH left in place pending merge (next run's opportunistic --cleanup will collect it once merged)"
else
  log "no mouth content changes this run — releasing worktree"
  python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
  if [ "$RUN_RC" -eq 0 ]; then
    heartbeat ok "no content changes"
  else
    heartbeat error "translate-articles.py exit=$RUN_RC, no output to promote"
  fi
fi

exit $RUN_RC
