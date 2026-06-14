# Runbook - Codex dirty-main state watch

This runbook is the hand-off target for Spark reports with dispatch key
`dirty-main-codex-state-watch`.

It exists for one narrow case: Spark/Codex lifecycle looks healthy, but the
operator's main checkout has broad uncommitted work and Codex state freshness is
not fully proved by the small Spark snapshot. The safe response is an evidence
brief for a heavier agent, not an automatic cleanup.

## Non-negotiable rules

- Do not run `git reset`, `git checkout --`, `git clean`, `git stash`, or
  `git add -A` in `/Users/nuzantara/Desktop/nuzantara`.
- Do not commit from the main checkout.
- Do not normalize, format, or edit files in main while triaging.
- Do not copy WhatsApp, OSINT, CRM, or client raw data out of the Pro machine.
- Do not treat a healthy idle `StartInterval` LaunchAgent as failed.
- Do not call the Spark loop stale unless both runtime state and state-file
  timestamps support that conclusion.

## First-pass evidence

Run these from an isolated worktree or a shell that will not mutate main.

```bash
echo "Machine: $(whoami)@$(hostname)"
git -C /Users/nuzantara/Desktop/nuzantara status --short --branch
git -C /Users/nuzantara/Desktop/nuzantara diff --name-status --cached
git -C /Users/nuzantara/Desktop/nuzantara diff --name-status
git -C /Users/nuzantara/Desktop/nuzantara ls-files -o --exclude-standard
```

Then verify the Codex/Spark lifecycle using launchd state and state files
together:

```bash
launchctl list | rg 'codex-spark|codex-overnight|codex'

for label in \
  com.nuzantara.codex-spark-loop \
  com.nuzantara.codex-spark-alarm \
  com.nuzantara.codex-spark-harvester \
  com.nuzantara.codex-overnight-runner
do
  launchctl print "gui/$(id -u)/$label" 2>/dev/null \
    | awk -v label="$label" \
      'BEGIN{print "label=" label} /state =|runs =|pid =|last exit code =|run interval =/{print}'
done

find /Users/nuzantara/.agent/decisions/state -maxdepth 1 -type f \
  \( -name '*codex*' -o -name '*spark*' -o -name '*overnight*' \) \
  -print -exec stat -f '%Sm %z %N' -t '%Y-%m-%dT%H:%M:%S%z' {} \;
```

Interpretation gates:

| Evidence | Classification |
| --- | --- |
| Spark loop has numeric PID or `state = running` | Healthy, not an actionable Spark outage |
| Alarm/harvester show `state = not running`, `last exit code = 0`, and `run interval` | Healthy idle timer job |
| Alarm/harvester have fresh non-zero exits | Actionable Spark lifecycle issue |
| Codex state files have fresh mtimes and parseable JSON | State freshness proved |
| State file exists but has no mtime/content in the report | Unknown, verify live before acting |
| Main checkout has unrelated staged/unstaged/untracked work | Block automatic cleanup; create owner/domain brief |

## Dirty-main classification

Group the status output into domain buckets before recommending any action.
Use path prefixes, not assumptions about file content ownership.

| Bucket | Typical paths | Default owner/action |
| --- | --- | --- |
| Codex/automation | `scripts/codex/`, `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py`, `.agent/decisions/state` | Ops agent; inspect runtime logs before touching |
| NLM and evaluator research | `apps/evaluator/nlm_deep_research/`, `research/nb-*` | Research/NLM agent; preserve generated outputs separately from source edits |
| Mouth editorial | `apps/mouth/src/content/articles/` | Editorial/Mouth agent; validate metadata and localized MDX pairs |
| CRM/cell | `apps/crm-cell/`, `shared/escalations_pro.jsonl` | Cell/CRM agent; avoid copying raw client data |
| Regulatory/commercial research | `research/regulatory/`, `research/commercial/`, `research/coherence-corpus/` | Research ops; distinguish generated delta data from authored briefs |
| Docs and cicatrix | `docs/`, `.claude/rules/` | Ops/docs agent; keep historical scar edits explicit |
| Generic outputs | `outputs/`, generated `output/` folders | Usually generated artifacts; never delete without source-owner confirmation |

Minimum brief fields:

- snapshot timestamp and machine
- current branch/ahead/behind status for main
- staged files
- unstaged tracked files grouped by bucket
- untracked files/directories grouped by bucket
- fresh Codex/Spark state evidence
- launchd failures that are Codex/Spark-related versus unrelated
- explicit no-touch paths and raw-data boundaries
- recommended next owner for each bucket

## Handoff artifact

Write a single markdown brief outside the dirty main checkout, for example:

```bash
BRIEF="/tmp/dirty-main-codex-state-watch-$(date +%Y%m%d-%H%M%S).md"
```

The brief can be copied into an overnight/backlog item only after it contains
the minimum fields above. The follow-up agent should work from a new isolated
worktree and should only touch one bucket at a time.

## Remediation decision tree

1. If Spark loop is stopped and state/log timestamps are stale, investigate the
   Spark lifecycle first.
2. If Spark lifecycle is healthy and main is dirty across more than one bucket,
   do not clean main automatically. Produce the handoff brief.
3. If main has exactly one coherent bucket and the owner is obvious, create an
   isolated worktree/branch and remediate that bucket only.
4. If main is ahead or behind `origin/main`, include divergence counts in the
   brief. Do not pull, rebase, or reset main as part of triage.
5. If staged files are present, list them first. Do not unstage or restage them.

## Current incident seed - 2026-06-15

The `spark-alarm-20260615_032834` overnight run verified this seed state:

- Pro machine: `nuzantara@Nuzantara`.
- Peer `mini` was unreachable during the session-start sync check.
- Spark loop was running; alarm and harvester were healthy idle timer jobs.
- Codex/Spark state files were fresh under
  `/Users/nuzantara/.agent/decisions/state`.
- Main checkout was `ahead 2, behind 176` with staged changes in
  `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py`.
- Dirty work spanned NLM research pipelines, Mouth article MDX drafts, CRM
  war-room material, regulatory/research outputs, docs/cicatrix edits, and
  escalation/log artifacts.

That seed does not authorize cleanup. It authorizes a bucketed owner brief and
follow-up worktree-per-bucket remediation.
