#!/bin/zsh
# scripts/automations-reference-cron-wrapper.sh
#
# Structural fix for the "docs/AUTOMATIONS_REFERENCE.md has two authors" disease
# (PENDING-ARMS ledger, 2026-09-11): com.nuzantara.automations-reference regenerated
# this file straight into Pro's MAIN checkout at 23:15 WITA, uncommitted — while the
# committed copy on main is also hand-edited (#6137 hand rows). Every night the two
# authors overwrote each other: the live regen clobbered hand rows, and the next
# `git pull` on main clobbered the regen. This wrapper runs the generator inside an
# isolated, ephemeral worktree (scripts/agent_start.py, lane=docs) instead — the main
# checkout is never touched — and auto-promotes any output via a PR with auto-merge
# armed, same pattern as scripts/translate-articles-cron-wrapper.sh.
#
# The wrapper also used to build docs/automations-inventory.xlsx via
# scripts/generate_automations_excel.py. That step is RETIRED here (decision
# 2026-09-11): it failed on all 28 logged runs with "ERROR: pip install openpyxl" —
# openpyxl was never installed on Pro, so it never once produced output. If the
# xlsx is wanted back, install openpyxl in the worktree's environment and add the
# step explicitly; it is not carried over silently.
#
# Invoked by ~/Library/LaunchAgents/com.nuzantara.automations-reference.plist
# (plain `/bin/zsh <this-script>`, no -lc — same non-login-shell pattern as
# com.balizero.translate.hourly.plist; `gh`/`git`/`python3` resolve fine as long as
# PATH/HOME are set, which the plist's EnvironmentVariables already do).
set -uo pipefail

# G5_kill_switch (organ-conformance): AUTOMATIONS_REFERENCE_ENABLED=false disables
# the run without touching the plist. Defaults to enabled.
if [ "${AUTOMATIONS_REFERENCE_ENABLED:-true}" != "true" ]; then
  print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] AUTOMATIONS_REFERENCE_ENABLED=false — skipping run" >>"${HOME}/logs/automations-reference-wrapper.log"
  exit 0
fi

REPO_ROOT="${HOME}/nuzantara"
LOG="${HOME}/logs/automations-reference-wrapper.log"
mkdir -p "$(dirname "$LOG")"

log() { print -r -- "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

# G2_heartbeat (organ-conformance): proof of life at ~/.organism/last_seen/<id>.json,
# which is what organs_registry.yaml's pro.automations_reference bridge_source and
# the stale-detector actually read. Invoked under `bash`, never sourced — this
# wrapper is zsh and heartbeat.sh declares `local status=…`, which dies on zsh's
# read-only `status` special parameter (same fix as
# scripts/translate-articles-cron-wrapper.sh). The EXIT trap covers paths nobody
# wrote a verdict on purpose: without it those runs leave NO sidecar, which reads
# as "never scheduled" rather than "died" (cicatrix-superscar.md #2, "Esiste ≠
# Armato").
ORGAN_ID="pro.automations_reference"
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

TASK_ID="automations-$(date +%Y%m%d%H%M%S)"
CREATE_OUT=$(python3 scripts/agent_start.py --lane docs --task-id "$TASK_ID" --ttl-min 30 2>>"$LOG")
WT_PATH=$(print -r -- "$CREATE_OUT" | awk '/^WORKTREE_READY/ {print $2}')
if [ -z "$WT_PATH" ] || [ ! -d "$WT_PATH" ]; then
  log "FATAL: worktree creation failed: $CREATE_OUT"
  heartbeat error "worktree creation failed"
  exit 1
fi
log "worktree ready: $WT_PATH (task_id=$TASK_ID)"

PYTHON="${AUTOMATIONS_PYTHON:-python3}"
"$PYTHON" "$WT_PATH/scripts/generate_automations_reference.py" >>"$LOG" 2>&1
RUN_RC=$?
log "generate_automations_reference.py exit=$RUN_RC"

# Belt and braces: the generator already formats the file itself (cwd=NUZANTARA_ROOT,
# relative path — fixed 2026-09-1x after prettier's own .gitignore matching silently
# no-op'd when it ran with the MAIN checkout's cwd, where .worktrees/ is gitignored).
# This wrapper must not depend on that internal behaviour holding: run prettier again,
# explicitly cd'd INTO the worktree, so a future regression in the generator's own cwd
# handling still leaves the committed file formatted.
(cd "$WT_PATH" && npx prettier --write docs/AUTOMATIONS_REFERENCE.md) >>"$LOG" 2>&1
PRETTIER_RC=$?
log "prettier (wrapper-side) rc=$PRETTIER_RC"

CHANGED=$(git -C "$WT_PATH" status --porcelain -- docs/AUTOMATIONS_REFERENCE.md | wc -l | tr -d ' ')

if [ "$RUN_RC" -ne 0 ] && [ "$CHANGED" -eq 0 ]; then
  log "ERROR: generator failed (rc=$RUN_RC) and produced no output — releasing worktree"
  heartbeat error "generate_automations_reference.py exit=$RUN_RC, no output to promote"
  python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
  exit 1
fi

if [ "$CHANGED" -gt 0 ]; then
  log "$CHANGED file(s) changed — promoting via PR"
  BRANCH=$(git -C "$WT_PATH" branch --show-current)

  git -C "$WT_PATH" add docs/AUTOMATIONS_REFERENCE.md
  git -C "$WT_PATH" commit -m "$(
    cat <<EOF
docs(automations): nightly snapshot of live automations ($(date '+%Y-%m-%d'))

Auto-generated by scripts/generate_automations_reference.py on Pro
(com.nuzantara.automations-reference, 23:15 WITA), run in an isolated
worktree via scripts/automations-reference-cron-wrapper.sh so the main
checkout is never written to directly. The generator is the source; the
file is output (decision 2026-09-11).

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
EOF
  )" >>"$LOG" 2>&1
  COMMIT_RC=$?
  if [ "$COMMIT_RC" -ne 0 ]; then
    # Measured on Pro's first live run: husky's pre-commit lint failed on the
    # unformatted file (prettier had silently no-op'd, see above) and this
    # branch used to ignore that non-zero rc entirely — it pushed a branch
    # IDENTICAL to main (nothing was ever committed) and `gh pr create` died
    # with "No commits between main and branch", so the heartbeat went error
    # for the wrong reason and only after a useless push. A failed commit must
    # never reach push or gh at all.
    log "ERROR: commit failed rc=$COMMIT_RC — worktree left for recovery"
    heartbeat error "commit failed (pre-commit hook?) — worktree left for recovery"
    exit 1
  fi

  git -C "$WT_PATH" push -u origin "$BRANCH" >>"$LOG" 2>&1
  PUSH_RC=$?
  if [ "$PUSH_RC" -ne 0 ]; then
    log "ERROR: push failed rc=$PUSH_RC — leaving worktree $WT_PATH for manual recovery"
    heartbeat error "push failed rc=$PUSH_RC (docs/AUTOMATIONS_REFERENCE.md stranded in $WT_PATH)"
    exit 1
  fi

  PR_URL=$(gh pr create --base main --head "$BRANCH" \
    --title "docs(automations): promote nightly automations snapshot ($(date '+%Y-%m-%d'))" \
    --body "$(
      cat <<EOF
Automated promotion of scripts/generate_automations_reference.py output. See
scripts/automations-reference-cron-wrapper.sh for the pipeline.

Bites: scripts/docs_sync.py::automation_coverage() reads
docs/AUTOMATIONS_REFERENCE.md on main; the "documented" count after this
merge is the observation.
EOF
    )" \
    2>>"$LOG")
  CREATE_RC=$?
  if [ "$CREATE_RC" -ne 0 ]; then
    log "ERROR: gh pr create failed rc=$CREATE_RC — branch pushed, PR NOT opened, manual recovery: gh pr create --head $BRANCH"
    heartbeat error "gh pr create failed rc=$CREATE_RC (branch $BRANCH pushed, PR not opened)"
    exit 1
  fi
  log "opened PR: $PR_URL"
  PR_NUM=$(print -r -- "$PR_URL" | grep -oE '[0-9]+$')

  # Supersede every OLDER open promote PR — the nightly snapshot is a full
  # regeneration by construction (live state re-scanned from scratch every run),
  # so the newest PR carries everything an older one carried, and an older copy
  # can only merge first and turn this one into an empty diff (same reasoning as
  # translate-articles-cron-wrapper.sh, 2026-09-09). Scope: same title prefix AND
  # same branch prefix (entity, not substring). A PR already occupying a merge-
  # queue slot is left alone: it is about to land and closing it would evict it
  # (queue_unstick.py's rule 1).
  OLDER=$(gh pr list --state open --search "promote nightly automations snapshot in:title" \
      --json number,headRefName \
      --jq ".[] | select(.number != $PR_NUM) | select(.headRefName | startswith(\"agent/nuzantara/docs/automations-\")) | .number" 2>>"$LOG")
  for old in ${(f)OLDER}; do
    QUEUED=$(gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){mergeQueueEntry{state}}}}' \
        -f o=Bali-Zero -f r=Teman2 -F n="$old" --jq '.data.repository.pullRequest.mergeQueueEntry // "null"' 2>>"$LOG")
    if [ "$QUEUED" != "null" ] && [ -n "$QUEUED" ]; then
      log "keeping older promote PR #$old — in merge queue ($QUEUED)"
      continue
    fi
    if gh pr close "$old" --delete-branch --comment "Superseded by $PR_URL — the nightly automations snapshot is a full regeneration, this older copy only burned CI (automations-reference-cron-wrapper.sh)." >>"$LOG" 2>&1; then
      log "closed superseded promote PR #$old"
    else
      log "WARN: could not close superseded promote PR #$old"
    fi
  done
  # NOT --squash: once a merge queue governs main, the ruleset owns the merge
  # method and --squash is rejected outright (pipeline-ship skill, 2026-07-27+).
  RUN_NOTE=""
  [ "$RUN_RC" -ne 0 ] && RUN_NOTE=" (generator exit=$RUN_RC — partial output)"
  if gh pr merge "$PR_NUM" --auto >>"$LOG" 2>&1; then
    heartbeat ok "promoted docs/AUTOMATIONS_REFERENCE.md via $PR_URL (auto-merge armed)$RUN_NOTE"
  else
    log "WARN: could not arm auto-merge on PR #$PR_NUM — needs manual arm"
    heartbeat degraded "promoted docs/AUTOMATIONS_REFERENCE.md via $PR_URL but auto-merge did not arm$RUN_NOTE"
  fi
  log "worktree $WT_PATH left in place pending merge (next run's opportunistic --cleanup will collect it once merged)"
else
  log "no change — releasing worktree"
  python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
  heartbeat ok "no change"
fi

exit $RUN_RC
