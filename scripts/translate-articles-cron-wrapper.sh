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

# Yield every path another open PR already carries. The post-publish poller
# translates an article as it lands, on its own bot/articles-translations-* PR,
# and this run, cut from main, cannot see it: both PRs add the same file and the
# queue ejects whichever merges second (#7862 merged, #7867 add/add, 2026-10-05).
# Older hourly PRs are not yielded to — the loop below supersedes them — unless
# they hold a queue slot and so stay. Read only when this run has output. Any
# failure → nothing is promoted: the batch is cumulative, and the next run
# re-detects the same work from main.
yield_carried_paths() {
  local query carried entry p
  local -a carried_paths entries
  query='query($endCursor:String){repository(owner:"Bali-Zero",name:"Teman2"){pullRequests(states:OPEN,first:50,after:$endCursor){pageInfo{hasNextPage endCursor} nodes{headRefName mergeQueueEntry{state} files(first:100){nodes{path}}}}}}'
  carried=$(gh api graphql --paginate -f query="$query" \
      --jq '.data.repository.pullRequests.nodes[] | select((.headRefName | startswith("agent/nuzantara/mouth/hourly-") | not) or .mergeQueueEntry != null) | .files.nodes[]?.path' 2>>"$LOG") || return 1
  # An array lookup, not `print | grep -q`: under pipefail a list larger than
  # the pipe buffer turned an early match into SIGPIPE (141), read as a miss.
  carried_paths=(${(f)carried})
  # -z: raw paths, never C-quoted; "XY path" entries, "??" = untracked.
  entries=(${(0)"$(git -C "$WT_PATH" status --porcelain -z --untracked-files=all -- apps/mouth/src/content/articles)"}) || return 1
  for entry in $entries; do
    p=${entry[4,-1]}
    (( ${carried_paths[(Ie)$p]} )) || continue
    if [[ ${entry[1,2]} == '??' ]]; then
      rm -f -- "$WT_PATH/$p" || return 1
    else
      git -C "$WT_PATH" checkout -q HEAD -- "$p" || return 1
    fi
    log "yielded $p — another open PR already carries it"
  done
}

# Content guards (scripts/mouth_content_guard.sh): the LLM translation can rewrite a
# line the e33 income-basis / second-home claim ratchets pin, and the hourly PR then
# goes red on both sides and never merges. The guards are right and the content is
# wrong, so ask them before `git add`: green -> promote all; red -> try each slug
# group alone, hold back the groups that fail (restored to HEAD, inside this
# ephemeral worktree only), re-run on the final set, and promote nothing if that is
# still red, if main itself is red, or if the guards cannot run at all.
GUARD="$SCRIPT_DIR/mouth_content_guard.sh"
ESCALATIONS="${MOUTH_GUARD_ESCALATIONS:-$REPO_ROOT/shared/escalations_pro.jsonl}"
GUARD_MAX_GROUPS=60
ART_DIR="apps/mouth/src/content/articles"
SNAP=""
typeset -A GROUP_FILES
typeset -a HELD KEPT

guard() { bash "$GUARD" "$@" >>"$LOG" 2>&1; }

# slug group of an article path: strip the locale suffix, so .en/.id/.it of one slug travel together
group_of() {
  if [[ $1 =~ '^(.*)\.(en|it|id|fr|ru)\.mdx$' ]]; then print -r -- "$match[1]"; else print -r -- "${1:r}"; fi
}

reset_articles() {
  if git -C "$WT_PATH" cat-file -e "HEAD:$ART_DIR" 2>/dev/null; then
    git -C "$WT_PATH" checkout -q HEAD -- "$ART_DIR" || return 1
  fi
  git -C "$WT_PATH" clean -fdq -- "$ART_DIR"
}

# put exactly the given groups' translated files back on top of HEAD
apply_groups() {
  local g f
  reset_articles || return 1
  for g in "$@"; do
    for f in ${(f)GROUP_FILES[$g]}; do
      mkdir -p "$WT_PATH/${f:h}" && cp -p "$SNAP/$f" "$WT_PATH/$f" || return 1
    done
  done
}

# 0 = promote $KEPT, 1 = nothing to promote ($HELD says why), >1 = abort with that code
prune_by_guards() {
  local entry p g rc
  local -a groups
  SNAP=$(mktemp -d) || return 4
  for entry in ${(0)"$(git -C "$WT_PATH" status --porcelain -z --untracked-files=all -- "$ART_DIR")"}; do
    p=${entry[4,-1]}
    [ -f "$WT_PATH/$p" ] || continue
    mkdir -p "$SNAP/${p:h}" && cp -p "$WT_PATH/$p" "$SNAP/$p" || return 4
    g=$(group_of "$p")
    GROUP_FILES[$g]+="$p"$'\n'
  done
  groups=(${(ko)GROUP_FILES})
  guard "$WT_PATH"; rc=$?
  if [ "$rc" -eq 0 ]; then KEPT=($groups); return 0; fi
  [ "$rc" -eq 3 ] && return 3
  if [ ${#groups} -gt "$GUARD_MAX_GROUPS" ]; then log "${#groups} slug groups exceed $GUARD_MAX_GROUPS — cannot bisect"; return 4; fi
  reset_articles || return 4
  guard --base "$WT_PATH"; rc=$?
  [ "$rc" -ne 0 ] && return "$rc"
  for g in $groups; do
    apply_groups "$g" || return 4
    guard "$WT_PATH"; rc=$?
    case "$rc" in 0) KEPT+=("$g") ;; 1) HELD+=("$g") ;; *) return "$rc" ;; esac
  done
  apply_groups $KEPT || return 4
  if [ ${#KEPT} -gt 0 ]; then
    guard "$WT_PATH" || { log "final set red after pruning — promoting nothing"; return 5; }
  fi
  [ ${#KEPT} -gt 0 ]
}

held_slugs() { local g; for g in $HELD; do print -rn -- "${g:t} "; done; }

report_held() {
  [ ${#HELD} -gt 0 ] || return 0
  log "held back by content guards: $(held_slugs)"
  python3 -c 'import json,sys,time,socket
row={"ts":time.time(),"type":"mouth_content_guard_hold","job":"translate-hourly","priority":"NORMAL","status":"pending","machine":socket.gethostname(),"slugs":sys.argv[2:],"error_summary":"mouth hourly translation held back by content guards: "+" ".join(sys.argv[2:])}
open(sys.argv[1],"a").write(json.dumps(row)+"\n")' "$ESCALATIONS" ${HELD:t} >>"$LOG" 2>&1 || log "WARN: could not append the escalation row"
}

abort_unpromotable() {  # abort_unpromotable <rc> <why>
  log "ERROR: $2 — promoting nothing this run"
  reset_articles
  python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
  heartbeat degraded "$2, nothing promoted (translate-articles.py exit=$RUN_RC)"
  exit "$1"
}

CHANGED=$(git -C "$WT_PATH" status --porcelain -- apps/mouth/src/content/articles | wc -l | tr -d ' ')
if [ "$CHANGED" -gt 0 ]; then
  if ! yield_carried_paths; then
    log "ERROR: cannot read or yield the paths open PRs carry — promoting nothing this run"
    git -C "$WT_PATH" checkout -q -- apps/mouth/src/content/articles
    git -C "$WT_PATH" clean -fdq -- apps/mouth/src/content/articles
    python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
    heartbeat degraded "open PRs' paths unreadable, nothing promoted (translate-articles.py exit=$RUN_RC)"
    exit 1
  fi
  # recounted only after a scan: a count never follows an unscanned zero
  CHANGED=$(git -C "$WT_PATH" status --porcelain -- apps/mouth/src/content/articles | wc -l | tr -d ' ')
fi

if [ "$CHANGED" -gt 0 ]; then
  prune_by_guards; GUARD_RC=$?
  rm -rf "$SNAP"
  case "$GUARD_RC" in
    0|1) ;;
    2) abort_unpromotable 2 "content guards are red on main itself" ;;
    3) abort_unpromotable 3 "content guards cannot run (vitest/typescript/guard files missing)" ;;
    5) report_held; abort_unpromotable 5 "content guards still red on the pruned set" ;;
    *) abort_unpromotable 4 "content-guard pruning failed (rc=$GUARD_RC)" ;;
  esac
  report_held
  CHANGED=$(git -C "$WT_PATH" status --porcelain -- apps/mouth/src/content/articles | wc -l | tr -d ' ')
fi

if [ "$CHANGED" -gt 0 ]; then
  log "$CHANGED file(s) changed — promoting via PR"
  BRANCH=$(git -C "$WT_PATH" branch --show-current)

  HELD_NOTE=""
  [ ${#HELD} -gt 0 ] && HELD_NOTE=$'\n\nHeld back by content guards (slugs, not promoted): '"$(held_slugs)"
  git -C "$WT_PATH" add apps/mouth/src/content/articles
  git -C "$WT_PATH" commit -m "$(
    cat <<EOF
chore(mouth): promote $CHANGED hourly-translated article file(s)

Auto-generated by scripts/translate-articles.py (com.balizero.translate.hourly),
run in an isolated worktree via scripts/translate-articles-cron-wrapper.sh so the
main checkout is never written to directly. Re-translation triggered by
source_sha256 staleness detection.

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
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
    --body "Automated promotion of scripts/translate-articles.py output. See scripts/translate-articles-cron-wrapper.sh for the pipeline.${HELD_NOTE}" \
    2>>"$LOG")
  CREATE_RC=$?
  if [ "$CREATE_RC" -ne 0 ]; then
    log "ERROR: gh pr create failed rc=$CREATE_RC — branch pushed, PR NOT opened, manual recovery: gh pr create --head $BRANCH"
    heartbeat error "gh pr create failed rc=$CREATE_RC (branch $BRANCH pushed, PR not opened)"
    exit 1
  fi
  log "opened PR: $PR_URL"
  PR_NUM=$(print -r -- "$PR_URL" | grep -oE '[0-9]+$')

  # Supersede every OLDER open promote PR (2026-09-09: 68 identical copies were
  # open at once, one per hour since 2026-09-04, each burning a full CI run).
  # The hourly batch is cumulative by construction — staleness is re-detected
  # from main every run, so the newest PR carries everything an older one
  # carried — and an older copy can only merge first and turn this one into an
  # empty diff. Scope: same title prefix AND same branch prefix (entity, not
  # substring). A PR already occupying a merge-queue slot is left alone: it is
  # about to land and closing it would evict it (queue_unstick.py's rule 1).
  OLDER=$(gh pr list --state open --search "promote hourly-translated in:title" \
      --json number,headRefName \
      --jq ".[] | select(.number != $PR_NUM) | select(.headRefName | startswith(\"agent/nuzantara/mouth/hourly-\")) | .number" 2>>"$LOG")
  for old in ${(f)OLDER}; do
    QUEUED=$(gh api graphql -f query='query($o:String!,$r:String!,$n:Int!){repository(owner:$o,name:$r){pullRequest(number:$n){mergeQueueEntry{state}}}}' \
        -f o=Bali-Zero -f r=Teman2 -F n="$old" --jq '.data.repository.pullRequest.mergeQueueEntry // "null"' 2>>"$LOG")
    if [ "$QUEUED" != "null" ] && [ -n "$QUEUED" ]; then
      log "keeping older promote PR #$old — in merge queue ($QUEUED)"
      continue
    fi
    if gh pr close "$old" --delete-branch --comment "Superseded by $PR_URL — the hourly translation batch is cumulative, this older copy only burned CI (translate-articles-cron-wrapper.sh)." >>"$LOG" 2>&1; then
      log "closed superseded promote PR #$old"
    else
      log "WARN: could not close superseded promote PR #$old"
    fi
  done
  # NOT --squash: once a merge queue governs main, the ruleset owns the merge
  # method and --squash is rejected outright (pipeline-ship skill, 2026-07-27+).
  RUN_NOTE=""
  [ "$RUN_RC" -ne 0 ] && RUN_NOTE=" (translate-articles.py exit=$RUN_RC — partial output)"
  [ ${#HELD} -gt 0 ] && RUN_NOTE="$RUN_NOTE; held ${#HELD} slug(s): $(held_slugs)"
  # label + arm via the shared helper (falls back to the bare arm if this checkout predates it)
  if [ -x "$REPO_ROOT/scripts/signal_merge_intent.sh" ]; then
    "$REPO_ROOT/scripts/signal_merge_intent.sh" "$PR_NUM" >>"$LOG" 2>&1; ARM_RC=$?
  else
    gh pr merge "$PR_NUM" --auto >>"$LOG" 2>&1; ARM_RC=$?
  fi
  if [ "$ARM_RC" -eq 0 ]; then
    heartbeat ok "promoted $CHANGED file(s) via $PR_URL (auto-merge armed)$RUN_NOTE"
  else
    log "WARN: merge intent failed on PR #$PR_NUM (label and/or arm, rc=$ARM_RC — see SIGNAL_INTENT_FAIL above) — needs: scripts/signal_merge_intent.sh $PR_NUM"
    heartbeat degraded "promoted $CHANGED file(s) via $PR_URL but auto-merge did not arm$RUN_NOTE"
  fi
  log "worktree $WT_PATH left in place pending merge (next run's opportunistic --cleanup will collect it once merged)"
else
  log "no mouth content changes this run — releasing worktree"
  python3 scripts/agent_start.py --release "$TASK_ID" >>"$LOG" 2>&1
  if [ ${#HELD} -gt 0 ]; then
    heartbeat degraded "held ${#HELD} slug(s) by content guards, nothing to promote: $(held_slugs)"
  elif [ "$RUN_RC" -eq 0 ]; then
    heartbeat ok "no content changes"
  else
    heartbeat error "translate-articles.py exit=$RUN_RC, no output to promote"
  fi
fi

exit $RUN_RC
