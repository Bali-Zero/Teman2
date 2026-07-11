#!/bin/bash
# KBLI editorial regen — M5 reconcile loop (pull drafts from the Pro writer,
# audit with the applier's dry-run gates, checkpoint-commit).
#
# The Pro runs editorial_writer.py detached in /tmp/kbli-regen (see RESUME-HERE.md);
# this loop is the M5 side: every tick it rsync-PULLS new drafts into the worktree
# (pull works even when M5->Pro push crawls), runs kbli_apply_editorials.py --dry-run
# as the audit (gates G0-G6 = shape + L3/L10 + numbers), and commits a checkpoint.
# Exits when the Pro writer is dead and a final drain tick brought nothing new,
# or when all 1559 drafts are present. Log: scripts/kbli_triangle/_reconcile_loop.log
set -u

WT="$(cd "$(dirname "$0")/../.." && pwd)"
DRAFTS_REL="scripts/kbli_triangle/editorial_drafts"
LOG="$WT/scripts/kbli_triangle/_reconcile_loop.log"
INTERVAL="${RECONCILE_INTERVAL:-900}"
TOTAL_TARGET=1559

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

log "reconcile loop start (pid $$, interval ${INTERVAL}s, worktree $WT)"
while true; do
  rsync -az pro:/tmp/kbli-regen/scripts/kbli_triangle/editorial_drafts/ \
    "$WT/$DRAFTS_REL/" 2>>"$LOG" || log "rsync FAILED (retry next tick)"
  n=$(ls "$WT/$DRAFTS_REL"/*.json 2>/dev/null | wc -l | tr -d ' ')
  new=$(cd "$WT" && git status --porcelain -- "$DRAFTS_REL" | wc -l | tr -d ' ')

  if [ "$new" -gt 0 ]; then
    audit=$(cd "$WT" && python3 scripts/kbli_apply_editorials.py \
      --drafts-dir "$DRAFTS_REL" --dry-run 2>&1 | tail -3)
    log "pulled $new new/changed drafts (total $n) — audit tail: $audit"
    if (cd "$WT" && git add "$DRAFTS_REL" && git commit \
        -m "chore(kbli): checkpoint drafts ($n) — Terra regen reconcile" \
        -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>") >>"$LOG" 2>&1; then
      log "committed checkpoint ($n drafts)"
    else
      log "COMMIT FAILED (hooks?) — drafts stay staged-dirty, retry next tick"
    fi
  else
    log "no new drafts (total $n)"
  fi

  if [ "$n" -ge "$TOTAL_TARGET" ]; then
    log "ALL $TOTAL_TARGET drafts present — done, exiting"
    break
  fi
  if ! ssh pro 'pgrep -f editorial_writer.py >/dev/null' 2>>"$LOG"; then
    if [ "$new" -eq 0 ]; then
      log "Pro writer DEAD and drain tick empty — exiting at total $n"
      break
    fi
    log "Pro writer DEAD — one more drain tick"
  fi
  sleep "$INTERVAL"
done
log "reconcile loop end"
