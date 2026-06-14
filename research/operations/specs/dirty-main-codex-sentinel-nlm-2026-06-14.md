# Dirty Main Handoff: Codex Sentinel/NLM

Generated: 2026-06-14T14:21:57Z
Dispatch key: `dirty-main-codex-sentinel-nlm`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_221742.md`

## Decision

Actionable, but not as an in-place code fix.

The safe remediation is a triage handoff, not direct mutation of
`/Users/nuzantara/Desktop/nuzantara`. The main checkout is both dirty and
divergent from `origin/main`; committing, pulling, stashing, or resetting there
would mix unrelated user/agent work with generated artifacts.

## Verified State

Live checks on Pro showed:

- `com.nuzantara.codex-spark-loop`: running.
- `com.nuzantara.codex-spark-harvester`: StartInterval idle, last exit code `0`.
- `com.nuzantara.codex-overnight-runner`: running for this intervention run. The
  Spark report's earlier `not running` watch item is stale after the runner
  consumed the task.
- Main checkout: `/Users/nuzantara/Desktop/nuzantara`
  - branch status: `main...origin/main [ahead 2, behind 175]`
  - local HEAD: `e2b355f45`
  - `origin/main`: `a03b928fe`
  - status relative to local HEAD: 938 paths
  - status split: 2 staged modified, 19 unstaged modified, 917 untracked
  - largest untracked groups:
    - 840 under `research/coherence-corpus`
    - 48 under `outputs/_b64chunks`
    - 5 under `research/regulatory`
    - 5 under `research/nb-health`
    - 5 under `apps/mouth`
    - 4 under `apps/evaluator`

Important correction to the Spark seed: the scary-looking staged edits to
`scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py` are identical to
`origin/main` when compared live. The 12 modified files under
`apps/evaluator/nlm_deep_research/` are also identical to `origin/main`.

That means these files are not currently evidence of unmerged risky code; they
are evidence that the root main checkout is stale and dirty at the same time.

## Local Commits To Preserve

The main checkout has two local commits not in `origin/main`:

```text
e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists
c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms
```

Do not reset or rebase the main checkout until these are either pushed through a
proper branch/PR or intentionally superseded.

## Batch Plan For A Follow-Up Agent

### Batch 0: Preserve The Two Local Article Commits

Goal: ensure the two local commits are not lost before any cleanup.

Read-only checks:

```bash
git -C /Users/nuzantara/Desktop/nuzantara log --oneline origin/main..main
git -C /Users/nuzantara/Desktop/nuzantara show --stat --oneline e2b355f45
git -C /Users/nuzantara/Desktop/nuzantara show --stat --oneline c6d6b85fe
```

Safe action pattern:

```bash
cd /Users/nuzantara/Desktop/nuzantara
python scripts/agent_start.py --lane content --task-id preserve-local-article-commits
```

Then cherry-pick or patch only those two commits into the new worktree and open a
normal PR. Do not push `main` directly.

Acceptance:

- The two commits are represented by a PR or an explicit operator decision.
- No generated artifact from the dirty main checkout is included.

### Batch 1: Runtime Script/Sentinel Files

Files:

- `scripts/dlq_autopilot.py`
- `scripts/nuzantara-sentinel.py`

Current finding: no delta versus `origin/main`.

Verification:

```bash
git -C /Users/nuzantara/Desktop/nuzantara diff --cached --stat origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
git -C /Users/nuzantara/Desktop/nuzantara diff --cached --check -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
```

Expected: empty diff/stat against `origin/main`; whitespace check exits `0`.

If a future run finds a real delta, extract only those paths as a patch and apply
it in a fresh worktree:

```bash
git -C /Users/nuzantara/Desktop/nuzantara diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py > /tmp/sentinel-dlq.patch
cd "$FRESH_WORKTREE"
git apply --check /tmp/sentinel-dlq.patch
git apply /tmp/sentinel-dlq.patch
```

Minimum validation for real script deltas:

```bash
source venv/bin/activate
PYTHONPATH=. python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_sentinel_v33.py -q
```

Acceptance:

- Script diffs are either confirmed duplicate-of-origin or isolated in their own
  PR with sentinel/DLQ tests passing.

### Batch 2: NLM Notebook ID And Pipeline Files

Files shown dirty relative to stale local HEAD:

- `apps/evaluator/nlm_deep_research/cross_notebook_correlator.py`
- `apps/evaluator/nlm_deep_research/freshness_monitor.py`
- `apps/evaluator/nlm_deep_research/gap_scanner.py`
- `apps/evaluator/nlm_deep_research/multimodal_pipeline.py`
- `apps/evaluator/nlm_deep_research/nb5_pipeline.py`
- `apps/evaluator/nlm_deep_research/nb6_pipeline.py`
- `apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py`
- `apps/evaluator/nlm_deep_research/persona_definitions.json`
- `apps/evaluator/nlm_deep_research/pipeline.py`
- `apps/evaluator/nlm_deep_research/t4_monitor.py`
- `apps/evaluator/nlm_deep_research/t4_nb5_config.json`
- `apps/evaluator/nlm_deep_research/yt_monitor.py`

Current finding: no delta versus `origin/main`.

Verification:

```bash
git -C /Users/nuzantara/Desktop/nuzantara diff --stat origin/main -- apps/evaluator/nlm_deep_research
git -C /Users/nuzantara/Desktop/nuzantara diff --name-status origin/main -- apps/evaluator/nlm_deep_research
```

Expected: empty output.

Minimum validation if this batch ever has a real delta:

```bash
source venv/bin/activate
PYTHONPATH=. pytest tests/nlm_deep_research/test_notebook_ids.py apps/evaluator/nlm_deep_research/tests/test_multimodal_pipeline.py -q
```

Acceptance:

- Notebook ID changes are either duplicate-of-origin or validated against the
  notebook ID tests before PR.

### Batch 3: Generated Artifacts And Corpora

Observed untracked/generated groups:

- `research/coherence-corpus/*`: 840 files, about 44 MB.
- `apps/evaluator/nlm_deep_research/output/*`: about 171 MB, including `.m4a`
  audio artifacts.
- `outputs/_b64chunks/*`: 48 files, about 1.4 MB.
- `outputs/_clients_b64.txt`, `outputs/clients_all.csv`,
  `outputs/clients_master_clean.csv`.
- `research/regulatory/2026-06-10-delta.json` through
  `research/regulatory/2026-06-14-delta.json`.
- `research/nb-health/2026-06-10-health.md` through
  `research/nb-health/2026-06-14-health.md`.

Default action: do not commit until a generator contract says these files are
intended tracked outputs.

Read-only classification:

```bash
git -C /Users/nuzantara/Desktop/nuzantara ls-files --others --exclude-standard | awk -F/ '{print $1"/"$2}' | sort | uniq -c | sort -nr
du -sh /Users/nuzantara/Desktop/nuzantara/research/coherence-corpus /Users/nuzantara/Desktop/nuzantara/apps/evaluator/nlm_deep_research/output /Users/nuzantara/Desktop/nuzantara/outputs/_b64chunks
```

Acceptance:

- Each generated group is mapped to one of: track intentionally, add/confirm
  `.gitignore`, move to local artifact storage, or leave for operator review.

### Batch 4: Public Content, Docs, And Published Metadata

Observed dirty/untracked examples:

- `apps/bali-intel-scraper/data/published_articles.json`
- `apps/mouth/src/content/articles/**`
- `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`
- `research/commercial/2026-W24-yield-opportunities.md`
- `docs/AUTOMATIONS_REFERENCE.md`
- `docs/DOCS_INVENTORY.md`
- `shared/escalations_pro.jsonl`

These need content/release review, not daemon cleanup. Keep them out of any
sentinel/DLQ PR.

Acceptance:

- Public content has its own content PR or is explicitly left in main as
  operator-owned work.
- Generated registries are regenerated from source or excluded from unrelated
  PRs.

### Batch 5: Non-Codex Launchd Failures

The source Spark report mentioned non-Codex launchd failures such as
`cost-breaker`, `mcp-integrity`, `intake-*`, `wr2.supervisor*`,
`wa-meta-inbox`, and `verify-the-verifiers`.

Those are out of scope for this dirty-main intervention. They should get a
separate launchd health task with fresh `launchctl print` evidence and log tails.

## Main Checkout Cleanup Guardrail

Do not run any of these in `/Users/nuzantara/Desktop/nuzantara` until Batch 0 is
preserved and the untracked artifacts are classified:

```bash
git reset --hard
git clean -fd
git pull --rebase
git stash --include-untracked
```

Instead, do cleanup work in fresh worktrees and leave the dirty main checkout
untouched until an operator or dedicated cleanup agent owns it.

## Completion Criteria For The Follow-Up

- Main local commits are preserved or explicitly retired.
- No dirty runtime scripts remain merely because main is behind `origin/main`.
- Generated artifacts have a track/ignore/archive decision.
- Public content/docs are split from ops daemon work.
- The final cleanup PR contains one coherent batch, not the full 938-path state.
