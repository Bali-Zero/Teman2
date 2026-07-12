#!/bin/bash
# KBLI editorial regen — M5 reconcile loop (pull drafts from the Pro writer,
# audit with the applier's dry-run gates, checkpoint-commit).
#
# The Pro runs editorial_writer.py detached in ~/kbli-regen (see RESUME-HERE.md —
# durable HOME path, NOT /tmp: a Pro reboot on 2026-07-11 wiped /tmp/kbli-regen);
# this loop is the M5 side: every tick it rsync-PULLS new drafts into the worktree
# (pull works even when M5->Pro push crawls), runs kbli_apply_editorials.py --dry-run
# as the audit (gates G0-G6 = shape + L3/L10 + numbers), and commits a checkpoint.
# Exits when the Pro writer is PROVABLY not running (ssh reached the host, pgrep
# found nothing — ssh failure is a network flap, family #8, NEVER a death verdict)
# and a final drain tick brought nothing new, or when all 1559 drafts are present.
# Log: scripts/kbli_triangle/_reconcile_loop.log
set -u

WT="$(cd "$(dirname "$0")/../.." && pwd)"
PRO_JOB_DIR="${PRO_JOB_DIR:-kbli-regen}"   # relative to the Pro $HOME
DRAFTS_REL="scripts/kbli_triangle/editorial_drafts"
LOG="$WT/scripts/kbli_triangle/_reconcile_loop.log"
INTERVAL="${RECONCILE_INTERVAL:-900}"
TOTAL_TARGET=1559

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >>"$LOG"; }

log "reconcile loop start (pid $$, interval ${INTERVAL}s, worktree $WT)"
while true; do
  rsync -az --timeout=60 "pro:$PRO_JOB_DIR/$DRAFTS_REL/" \
    "$WT/$DRAFTS_REL/" 2>>"$LOG" || log "rsync FAILED (network flap? retry next tick)"
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
  # ssh rc=255 means the CONNECTION failed (flap) — the writer's state is UNKNOWN,
  # never conclude death from it (that false verdict killed the loop on 2026-07-11).
  probe_rc=0
  ssh -o ConnectTimeout=20 pro 'pgrep -f editorial_writer.py >/dev/null' 2>>"$LOG" || probe_rc=$?
  if [ "$probe_rc" -eq 255 ]; then
    log "ssh to Pro FAILED (flap) — writer state unknown, keep looping"
  elif [ "$probe_rc" -ne 0 ]; then
    if [ "$new" -eq 0 ]; then
      log "Pro writer NOT RUNNING (host reached) and drain tick empty — exiting at total $n"
      break
    fi
    log "Pro writer NOT RUNNING (host reached) — one more drain tick"
  fi
  sleep "$INTERVAL"
done
log "reconcile loop end"
