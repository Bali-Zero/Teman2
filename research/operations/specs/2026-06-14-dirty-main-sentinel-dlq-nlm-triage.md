# Dirty Main Sentinel/DLQ/NLM Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-main-sentinel-dlq-nlm`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_161119.md`
Prompt snapshot: `/Users/nuzantara/logs/codex-spark-loop/scout-20260614_161119.prompt.md`
Owner: Ops checkout steward plus NLM/content workstream owners

## Scope

Resolve the actionable signal from Spark without editing the shared checkout at
`/Users/nuzantara/Desktop/nuzantara` from this isolated overnight worktree.

The live evidence does not support a Spark LaunchAgent repair. The actionable
problem is that the shared `main` checkout is stale and broadly dirty, with a
staged Sentinel/DLQ cluster that is already present in `origin/main` plus several
unrelated NLM, content, output, research, and docs surfaces.

This spec is deliberately decision-only. It records the split plan so the next
heavier agent can drain the dirty checkout safely instead of committing unrelated
work together or overwriting another agent's artifacts.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. Peer `mini` was unreachable during
  the session-start SSH check, so peer sync is unverified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_161310-spark-dispatch-20260614_161119-scout-dirty-main-sentinel-dlq-nlm-20260614_161310`.
- Only root `AGENTS.md` exists in this worktree. No path-specific `AGENTS.md`
  was found under `scripts/`, `apps/backend-rag/`, or
  `apps/backend-rag/backend/llm/`.
- Spark lifecycle is healthy, not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 2066`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`, `pid = 27996`,
    `last exit code = 0`.
  - `com.nuzantara.codex-overnight-feeder`: calendar job, `state = not running`;
    no bad Codex exit was observed.
- Non-Codex LaunchAgents still have bad exits, but they are outside this dispatch
  key. Examples include WR2/WR3 supervisors, intake workers, split-brain/lag
  checks, and local service helpers.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45`, while `origin/main` is `a03b928fe`; status reports
  `ahead 2, behind 175`.
- Shared checkout staged paths:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
- Staged Sentinel/DLQ patch size against the stale shared-checkout `HEAD`:
  `205 insertions(+), 2 deletions(-)`.
- The staged Sentinel/DLQ paths have no delta against `origin/main`:
  `git diff origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`
  and the cached equivalent both returned empty output.
- Current `origin/main` history already contains the W70 work:
  - `849a4a213 fix(ops): re-arm blind heal-loop... (#1344)`
  - `6938d3883 fix(sentinel): close the blind heal-loop... (#1413)`
  - `c454afb3d fix(sentinel): bound enrich tail... (#1418)`
- Shared checkout unstaged tracked surface includes NLM pipelines, generated docs,
  content metadata, research CSVs, `scripts/curiosity_loop.sh`, and
  `shared/escalations_pro.jsonl`.
- Shared checkout untracked surface summary by top cluster:
  - `research/coherence-corpus`: 840 files
  - `outputs`: 51 files
  - `research/regulatory`: 5 files
  - `research/nb-health`: 5 files
  - `apps/mouth`: 5 article files
  - `scripts`: 2 files
  - `research/operations`: 2 files
  - one-file clusters under `apps/crm-cell`, `apps/evaluator`,
    `apps/research`, and `research/commercial`

## Root-Cause Classification

Primary cluster: stale shared `main` checkout with orphaned staged W70
Sentinel/DLQ changes.

Secondary cluster: unrelated local workstreams accumulated in the same shared
checkout: NLM/NotebookLM pipelines and outputs, published articles, generated
docs inventories, regulatory/health research deltas, commercial research, CRM
war-room tooling, and runtime escalation logs.

The staged Sentinel/DLQ work should not be recommitted from the shared checkout
because the same file content is already in `origin/main`. The remaining dirty
surface still needs owner-driven triage before the shared checkout can safely
fast-forward.

## Workstream Split Plan

| Workstream | Paths | Current state | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Sentinel/DLQ W70 dedupe | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged in shared `main`, but identical to `origin/main` | Ops/sentinel owner | Confirm both `git diff origin/main -- <paths>` and `git diff --cached origin/main -- <paths>` are empty, then remove the duplicate staged state only after preserving a checkpoint of the full shared checkout. Do not create another W70 PR. |
| Sentinel/DLQ validation receipt | `scripts/tests/test_sentinel_w70_resurrect_enrich.py`, existing sentinel tests | Present in `origin/main`, absent from stale shared `HEAD` | Ops/sentinel owner | On a fresh worktree, run `source .venv/bin/activate && PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_sentinel_v33.py -q` before declaring W70 fully drained. |
| NLM pipeline code | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Mixed unstaged tracked and untracked script changes | NLM/NotebookLM owner | Move to a dedicated branch/worktree, add focused `tests/nlm_deep_research` coverage or run existing focused tests, and keep generated media/output files out of the code commit unless explicitly intended. |
| Generated NLM/output artifacts | `outputs/`, `apps/evaluator/nlm_deep_research/output/multimodal/`, `research/coherence-corpus/` | Large untracked artifact surface | NLM/data owner | Decide keep/export/drop policy. If committed, include manifest/provenance and ensure no raw private WhatsApp/OSINT data is present. Otherwise move outside the repo or add an ignore rule in a separate hygiene PR. |
| Published articles/content | `apps/bali-intel-scraper/data/published_articles.json`, `apps/mouth/src/content/articles/**`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `apps/research/sota-social-2026-v1/kpi_timeline.csv` | Mixed tracked and untracked content changes | Content/publishing owner | Commit articles and content metadata together only after frontmatter/build validation for `apps/mouth` and confirmation that article slugs match the published metadata. |
| Docs inventory regeneration | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Unstaged generated docs diff | Docs/automation owner | Regenerate from the documented scripts and commit only if generation is deterministic. Otherwise discard local inventory drift after preserving evidence. |
| Research deltas | `research/regulatory/*.json`, `research/nb-health/*.md`, `research/operations/*.md`, `research/commercial/` | Untracked research outputs | Research owner | Group by research run/date, include source/provenance, and avoid mixing with runtime scripts. |
| CRM war-room tool | `apps/crm-cell/war-room/interactive_cli.sh` | Untracked app tool | CRM-cell owner | Review for secrets and local-only assumptions, then commit with its own usage note or move outside repo if it is an operator scratch script. |
| Runtime logs/escalations | `shared/escalations_pro.jsonl` | Unstaged runtime JSONL append | Ops owner | Treat as runtime state unless a migration explicitly requires it. Validate that no secret or client-private raw payload is being committed. |

## Safe Drain Order

1. Preserve the dirty shared checkout state before any cleanup:
   `git status --short --branch`, staged diff stats, and untracked inventory.
2. Confirm the Sentinel/DLQ staged scripts are duplicate of `origin/main`.
3. Drain or drop the duplicate staged Sentinel/DLQ state; do not open a new PR
   for already-merged W70 code.
4. Split NLM code, generated artifacts, content/articles, docs inventories, and
   research outputs into separate branches or stashes with owners.
5. Only after the unique local work is protected, fast-forward or recreate the
   shared checkout from `origin/main`.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`.
- Do not deploy.
- Do not clean or reset `/Users/nuzantara/Desktop/nuzantara` from an unrelated
  overnight worktree.
- Do not recommit W70 Sentinel/DLQ code that already exists in `origin/main`.
- Do not mix NLM artifacts, article content, generated docs, and runtime logs in
  one commit.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.

## Next Step

Assign a checkout steward to drain `/Users/nuzantara/Desktop/nuzantara` using the
split above. The first action should be the Sentinel/DLQ dedupe check because it
is staged and already absorbed upstream; after that, preserve and route the NLM,
content, docs, and research surfaces into owned workstreams before syncing the
shared checkout to `origin/main`.
