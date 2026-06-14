# Main Dirty NLM/Regulatory Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `main-dirty-nlm-regulatory`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_132807.md`
Overnight branch:
`codex-overnight/spark-alarm-20260614_132902-spark-dispatch-20260614_132807-scout-main-dirty-nlm-regulatory-20260614_132903`
Owner: heavier-agent/operator triage owner for `/Users/nuzantara/Desktop/nuzantara`
Decision deadline: 2026-06-14 18:00 WITA

## Scope

Resolve the actionable Spark signal that the shared main checkout has accumulated
NLM, regulatory, generated-output, and automation edits. This spec is
decision-only: it defines the bucket plan and validation gates, but it does not
clean, reset, stash, or commit the shared checkout from an unrelated isolated
worktree.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. Mini peer was unreachable during
  session start, so peer sync is unverified.
- Isolated overnight worktree is clean on
  `codex-overnight/spark-alarm-20260614_132902-spark-dispatch-20260614_132807-scout-main-dirty-nlm-regulatory-20260614_132903`,
  based on `origin/main` at `84ae8edae`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45`, while `origin/main` is `84ae8edae`; `git status` reports
  `main...origin/main [ahead 2, behind 173]`.
- Shared checkout dirty count from
  `git status --porcelain=v1 --untracked-files=all`:

| State | Count | Meaning |
| --- | ---: | --- |
| `M ` | 2 | staged/index-modified tracked files |
| ` M` | 19 | unstaged tracked modifications |
| `??` | 914 | untracked files |
| **total** | **935** | live dirty entries |

- Path buckets from the same status snapshot:

| Bucket | Count | Examples |
| --- | ---: | --- |
| `research/coherence-corpus/` | 840 | Notebook/corpus JSON manifests for `nb-intel-regulation`, `nb3-company-curated`, `nb5-property-curated`, `nb6-operations-curated` |
| `outputs/` | 51 | `_b64chunks/`, `_clients_b64.txt`, `clients_all.csv`, `clients_master_clean.csv` |
| NLM pipeline/config | 13 | `apps/evaluator/nlm_deep_research/*`, including `peraturan_ingestion_trigger.py` and NB5/NB6 configs |
| Articles | 5 | `apps/mouth/src/content/articles/{immigration,tax}/*.mdx` |
| Scripts | 5 | staged `dlq_autopilot.py`, staged `nuzantara-sentinel.py`, plus NLM inventory/export helpers |
| Docs | 2 | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` |
| Other ops/research | 19 | `shared/escalations_pro.jsonl`, `research/regulatory/*-delta.json`, NB health notes, commercial note |

- Staged source changes are real and not generated-output noise:
  `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py` are staged with
  `205 insertions(+), 2 deletions(-)`. The diff appears to add W70 DLQ requeue,
  cron-log-tail enrichment, recovered-terminal clearing, and blind-heal-loop
  alerting behavior.
- Spark lifecycle is not the actionable fault:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 2066`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
  - No Codex LaunchAgent bad-exit evidence was found in the live `launchctl`
    summary.

## Root-Cause Classification

Primary cluster: shared-checkout worktree hygiene failure around NLM/regulatory
research outputs plus staged automation behavior changes.

The evidence does not support a Spark LaunchAgent repair. The risk is that
publishable articles, executable automation changes, generated corpora, private
client/output files, and documentation churn are co-mingled in a `main` checkout
that is also both ahead of and far behind `origin/main`.

## Bucket Plan

| Bucket | Files | Plan | Required validation before commit |
| --- | --- | --- | --- |
| Automation source changes | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py`, `scripts/curiosity_loop.sh` | Review and commit separately from generated files. Do not mix staged W70 DLQ/sentinel behavior with NLM article or corpus work. | Focused script tests or dry-runs; prove CLI path for `dlq_autopilot.py requeue <job>`; run sentinel syntax/import checks; inspect current LaunchAgent logs before changing daemon state. |
| NLM pipeline source/config | `apps/evaluator/nlm_deep_research/*.py`, `*.json`, `apps/mata-garuda/.../nlm_feeder.py` | Keep only intentional pipeline/config deltas. Commit in a dedicated NLM pipeline branch/commit after diff review. | Run the smallest NLM unit/import checks available; if no tests exist, at least `python -m py_compile` on touched Python files from the correct venv. |
| Publishable articles | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Treat as editorial publish set. Commit separately from source-code behavior. | Run the mouth content/frontmatter validation or `npm` lint/build subset used for articles. Confirm language variants and `published_articles.json` consistency. |
| Generated Notebook/corpus files | `research/coherence-corpus/**`, `research/regulatory/*-delta.json`, `research/nb-health/*.md` | Archive or keep as a research data drop only after owner review. Do not bulk-add all untracked JSON by default. | Validate manifests, count files by notebook, check for private/raw content, then either commit an intentional corpus snapshot or move to local archive outside Git. |
| Client/output artifacts | `outputs/_b64chunks/**`, `outputs/*clients*.csv`, `_clients_b64.txt` | Default discard/archive outside Git; these look runtime/generated and may contain client-derived data. | Before deletion, create a local operator-owned backup if needed. Do not commit unless a privacy review explicitly approves. |
| Docs/inventory churn | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, weekly report | Commit only after confirming they were regenerated from the current source tree, not from stale `main` state. | Re-run the inventory generator if available; otherwise compare with source-of-truth docs paths and commit separately. |

## Safe Operator Sequence

Run these from the shared checkout only after taking ownership of the dirty
state. Do not use `--no-verify`, force push, or reset the checkout.

```bash
cd /Users/nuzantara/Desktop/nuzantara
git status --short --branch --untracked-files=all
git branch rescue/main-dirty-nlm-regulatory-20260614
git diff --cached --stat
git diff --stat
git status --porcelain=v1 --untracked-files=all > /tmp/main-dirty-nlm-regulatory-20260614.status
```

Then split the work in this order:

1. Commit the two ahead-of-origin commits or confirm they already exist on a
   remote branch. Do not pull/rebase until their ownership is clear.
2. Validate and commit staged automation source changes by themselves.
3. Validate and commit NLM pipeline/config source changes by themselves.
4. Validate and commit article/frontmatter changes by themselves.
5. Decide whether Notebook/corpus JSON files are a deliberate research snapshot
   or should be archived outside Git.
6. Discard/archive `outputs/` client and base64 chunk artifacts unless an owner
   explicitly approves a sanitized tracked artifact.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean the shared checkout from this isolated overnight worktree.
- Do not use `git reset --hard`, `git checkout --`, force push, or `--no-verify`.
- Do not bulk-add `research/coherence-corpus/**` or `outputs/**` without privacy
  and ownership review.

## Next Step

Assign one heavier agent or human operator to the shared checkout and make the
first checkpoint a rescue branch plus `/tmp/main-dirty-nlm-regulatory-20260614.status`.
If no owner can safely claim the mixed dirty state by the deadline, preserve it
with a normal stash or rescue branch before any branch switch, then stop the
cleanup rather than guessing ownership.
