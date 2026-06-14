# Dirty Worktree NLM/Sentinel Triage - 2026-06-14

Source dispatch: `dirty-worktree-nlm-sentinel-triage`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_094010.md`
Verified on: `nuzantara@Nuzantara` (Pro), 2026-06-14 local time

## Outcome

Spark lifecycle is not the actionable root cause. The actionable signal is the
dirty root checkout at `/Users/nuzantara/Desktop/nuzantara`, with staged
sentinel/DLQ changes mixed with NLM NotebookLM ID/profile edits and generated or
operator data outputs. Do not clean this tree by blanket stash, reset, or add.

## Live Evidence

Commands run from the overnight worktree unless otherwise noted:

- `launchctl list | rg 'com\.nuzantara\.codex|codex-'`
  - `com.nuzantara.codex-spark-loop` is running with PID `1025`.
  - `com.nuzantara.codex-spark-alarm`, `com.nuzantara.codex-spark-harvester`,
    `com.nuzantara.codex-autofix-ci`, `com.nuzantara.codex-coverage-improver`,
    `com.nuzantara.codex-openclaw-analysis`, and
    `com.nuzantara.codex-research-actor` show healthy idle `- 0` semantics.
  - `com.nuzantara.codex-overnight-runner` is active with PID `33558`.
- `cd /Users/nuzantara/Desktop/nuzantara && git status --short --branch`
  - Root checkout is `main...origin/main [ahead 2, behind 172]`.
  - Staged files: `scripts/dlq_autopilot.py`,
    `scripts/nuzantara-sentinel.py`.
  - Tracked unstaged NLM cluster: 13 files under
    `apps/evaluator/nlm_deep_research/` plus
    `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`.
  - Untracked outputs include `outputs/`, `research/coherence-corpus/`,
    `apps/evaluator/nlm_deep_research/output/multimodal/`,
    `research/regulatory/2026-06-*.json`, `research/nb-health/*.md`, and
    article MDX files.
- `git diff --cached --stat`
  - `scripts/dlq_autopilot.py`: 55 insertions.
  - `scripts/nuzantara-sentinel.py`: 152 insertions, 2 deletions.
- `git diff --stat -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
  - NotebookLM cluster is small in tracked diff: 26 insertions and 26 deletions.
  - Main changes replace notebook IDs for immigration/property/operations and
    switch `nlm source add --profile zero` to `--profile default`.
- `du -sh apps/evaluator/nlm_deep_research/output/multimodal outputs research/coherence-corpus research/commercial apps/crm-cell/war-room`
  - `apps/evaluator/nlm_deep_research/output/multimodal`: 47M.
  - `outputs`: 40M.
  - `research/coherence-corpus`: 44M.
  - `research/commercial`: 16K.
  - `apps/crm-cell/war-room`: 4K.
- `find apps/evaluator/nlm_deep_research/output/multimodal outputs research/coherence-corpus research/commercial apps/crm-cell/war-room -type f | wc -l`
  - 899 untracked files across the output/corpus/war-room cluster.

## Triage Buckets

### Keep / Commit Candidate

Handle these first, in a fresh rescue worktree, because they are staged and look
like intentional operational fixes rather than generated output:

- `scripts/dlq_autopilot.py`
  - Adds `requeue_terminal(job_id)` for explicit operator requeue of TERMINAL
    DLQ entries.
  - Requires focused validation before commit:
    `python -m py_compile scripts/dlq_autopilot.py`.
  - Also inspect CLI behavior for `clear` and `requeue` without mutating the
    live DLQ unless an operator explicitly asks.
- `scripts/nuzantara-sentinel.py`
  - Adds cron-log-tail enrichment for bare `exit N` errors.
  - Adds resurrection of recovered DLQ-TERMINAL jobs.
  - Adds blind heal-loop counter and alerting.
  - Requires focused validation before commit:
    `python -m py_compile scripts/nuzantara-sentinel.py`.
  - Review alert cooldown behavior and file writes under
    `~/.agent/decisions/blind_loop_counter.json` before enabling.

Recommended rescue pattern:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py > /tmp/w70-sentinel-dlq-staged.patch
WT=$(python scripts/agent_start.py --lane ops --task-id w70-sentinel-dlq-rescue | awk '/WORKTREE_READY/ {print $2}')
cd "$WT"
git apply /tmp/w70-sentinel-dlq-staged.patch
python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
```

Do not unstage, reset, or commit from the dirty root checkout unless the
operator explicitly chooses that path.

### Keep / Commit Candidate After Verification

These are plausible NotebookLM migration edits, but they are mixed with output
artifacts and must not be bundled with the staged sentinel/DLQ fix:

- `apps/evaluator/nlm_deep_research/*`
  - Replaces old notebook IDs with:
    - immigration: `cff93ab0-813a-42f2-a8de-36987e724271`
    - property: `d9438180-5e63-4e2a-a473-6061101f6a8d`
    - operations: `85207af3-352f-4554-8d2a-18f42cc541ba`
  - Verify these IDs against the NotebookLM/NLM registry before committing.
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
  - Switches NLM CLI profile from `zero` to `default`.
  - Verify `nlm profile list` and one harmless dry-run/list command before
    committing. Do not add sources during verification unless requested.

Suggested validation:

```bash
nlm profile list
rg -n "271c7159|93314ad3|7fbf37ed|cff93ab0|d9438180|85207af3|--profile zero|--profile default" apps/evaluator/nlm_deep_research apps/mata-garuda
```

### Archive / Generated

Treat these as generated or bulky research artifacts. Archive or commit only
after a policy decision on artifact retention, privacy, and repository size:

- `apps/evaluator/nlm_deep_research/output/multimodal/`
  - 47M, includes NotebookLM audio and infographic outputs.
- `research/coherence-corpus/`
  - 44M, many generated JSON corpus records under notebook-specific folders.
- `research/regulatory/2026-06-10-delta.json` through
  `research/regulatory/2026-06-14-delta.json`.
- `research/nb-health/2026-06-10-health.md` through
  `research/nb-health/2026-06-14-health.md`.
- `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`.
- `research/commercial/2026-W24-yield-opportunities.md`.

If retained, prefer a dedicated artifact PR with a manifest and provenance
note. If archived outside git, record the destination and checksum.

### Discard Only With Explicit Approval

Do not delete or discard these automatically. They may contain client,
operator, or live-state material:

- `outputs/_clients_b64.txt`
- `outputs/_b64chunks/`
- `outputs/clients_master_clean.csv`
- `outputs/clients_all.csv`
- `shared/escalations_pro.jsonl`
- `apps/crm-cell/war-room/`
- `apps/bali-intel-scraper/data/published_articles.json`
- Untracked article MDX files under `apps/mouth/src/content/articles/`

For client/output files, use local-only inspection and sanitized summaries.
Never copy raw WhatsApp/CRM/client material to another machine.

## Recommended Order For Heavy Agent

1. Snapshot current root checkout without changing it:
   `git status --short --branch`, `git diff --cached --stat`,
   `git diff --stat`, and `git log --oneline origin/main..HEAD`.
2. Rescue staged sentinel/DLQ patch into a new worktree branch and validate it.
3. Separately rescue and validate the NLM notebook/profile edits.
4. Classify generated artifacts by retention policy. Create a manifest before
   moving or archiving anything.
5. Leave `discard only with explicit approval` files untouched until the
   operator approves exact paths.
6. Only after the above, reconcile the dirty `main` checkout that is currently
   ahead 2 and behind 172.

## Stop Conditions

Stop and write a blocked status if any of these happen:

- `git diff --cached` no longer contains the staged sentinel/DLQ files, because
  another agent has changed the evidence.
- The NotebookLM IDs cannot be verified against the active NLM registry.
- Any path in the approval-only bucket is needed for the proposed commit.
- The root checkout changes during triage in a way that invalidates the snapshot.
