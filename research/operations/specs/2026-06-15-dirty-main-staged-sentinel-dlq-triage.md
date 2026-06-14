# Dirty Main Staged Sentinel/DLQ Triage - 2026-06-15

Date: 2026-06-15
Dispatch key: `dirty-main-broad-staged-sentinel-dlq`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_054245.md`
Runner branch: `codex-overnight/spark-alarm-20260615_054435-spark-dispatch-20260615_054245-scout-dirty-main-broad-staged-sentinel-dlq-20260615_054435`
Scope owner: Ops / overnight runner

## Scope

Resolve the actionable Spark signal without mutating the shared checkout at
`/Users/nuzantara/Desktop/nuzantara`.

Spark correctly identified a high-risk pattern: a broad dirty `main` checkout
with staged automation changes in `scripts/dlq_autopilot.py` and
`scripts/nuzantara-sentinel.py`. Live verification shows the staged script
content is already present on the current `origin/main`-based overnight branch,
so there is no missing script code to rescue. The remaining work is dirty
checkout triage and ownership separation.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer SSH check: `mini` unreachable during runner start; peer sync unverified.
- Root instructions read from `AGENTS.md`; no path-specific `AGENTS.md` files
  were present under `scripts/`, `apps/backend-rag/`, or
  `apps/backend-rag/backend/llm/`.
- Spark lifecycle is healthy under the local LaunchAgent semantics:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: idle timer job, `last exit code = 0`.
  - `com.nuzantara.codex-spark-harvester`: idle timer job, `last exit code = 0`.
  - `com.nuzantara.codex-overnight-runner`: current runner has active PID.
- Fresh Codex/Spark state files exist under
  `/Users/nuzantara/.agent/decisions/state`:
  - `codex_com_nuzantara_codex_spark_loop.state.json`: generated
    `2026-06-14T21:43:03Z`, action `dispatched`.
  - `codex_com_nuzantara_codex_spark_alarm.state.json`: generated
    `2026-06-14T21:46:36Z`, action `queue_busy`.
  - `codex_com_nuzantara_codex_spark_harvester.state.json`: generated
    `2026-06-14T21:44:34Z`, action `backlog_waiting`.
  - `dlq_autopilot.last.json`: `status=ok`, detail
    `processed=26 fixed=0 escalated=2`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45` and reports `ahead 2, behind 176` against the local
  `origin/main` ref.
- Current overnight branch is at `0207c648a` (`origin/main`,
  `fix(mouth): improve a11y and semantic HTML in chat components (#1427)`).
- The two staged script files in the shared checkout match the current branch
  byte-for-byte:

| Path | Main index SHA-256 | Overnight branch SHA-256 | Classification |
| --- | --- | --- | --- |
| `scripts/dlq_autopilot.py` | `7726e0ed036f3b236a48aecc440b3fd194afabaf26211af4397484150581b8d8` | `7726e0ed036f3b236a48aecc440b3fd194afabaf26211af4397484150581b8d8` | Already upstream in current branch |
| `scripts/nuzantara-sentinel.py` | `c7a7b11fb4e7b20f511a5baf7198c33b39a3ba557b8779bca788cee54989ddd2` | `c7a7b11fb4e7b20f511a5baf7198c33b39a3ba557b8779bca788cee54989ddd2` | Already upstream in current branch |

## Root-Cause Classification

Primary cluster: stale shared-checkout index plus broad unrelated dirty work.

The staged Sentinel/DLQ files are not an unresolved source-change cluster. They
appear staged because local `main` is far behind the current `origin/main` ref,
while its index contains script versions that already landed upstream. Cleaning
or committing them from the dirty shared checkout would add risk without
preserving new work.

The broader dirty checkout remains real and should be triaged by ownership
bucket, not committed wholesale.

## Ownership Buckets

| Bucket | Paths observed | Owner | Safe next action | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Already-upstream automation scripts | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Ops/sentinel owner | Do not port code. In the shared checkout, only the checkout owner should refresh or unstage after reconciling local `main` with `origin/main`. | Hashes still match the target branch before any cleanup; no script diff is committed from the dirty checkout. |
| NLM deep research pipeline edits | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `apps/backend-rag/requirements.txt` | Research/NLM owner | Split into a dedicated worktree or branch and validate pipeline-specific commands. | Dependency changes are justified, scripts import under their venv, and generated outputs are separated from source edits. |
| Content and regulatory artifacts | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json`, `research/regulatory/*.json` | Content/regulatory owner | Review as a content batch, not as operations cleanup. | MDX builds or content checks pass; published article registry matches the article set. |
| Generated research/output directories | `outputs/`, `research/nb-monitor/`, `research/coherence-corpus/`, `research/commercial/`, `apps/evaluator/nlm_deep_research/output/multimodal/` | Research artifact owner | Keep only curated deliverables; leave raw output untracked unless an owner claims it. | Each retained artifact has a consumer and no raw/private source material is added accidentally. |
| Ops docs and cicatrix changes | `.claude/rules/*`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `research/operations/*.md` | Ops/docs owner | Commit separately from executable changes. | Docs are internally consistent and do not claim runtime changes unless verified live. |
| Runtime journals / escalation logs | `shared/escalations_pro.jsonl` | Runtime owner | Treat as runtime output until explicitly curated. | No volatile log append is committed as source by accident. |
| New utility scripts | `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `scripts/scar_query.py`, `scripts/curiosity_loop.sh` | Tooling owner | Review and validate as a separate tooling change. | CLI help/import checks pass and scripts do not depend on unstated local-only paths. |

## Recommended Resolution Order

1. Leave the shared checkout untouched from this isolated overnight branch.
2. The checkout owner should first reconcile `main` with `origin/main` in a
   controlled session, preserving any local-only commits or work as needed.
3. Confirm the staged Sentinel/DLQ hashes still match the upstream versions, then
   clear only that stale index state in the shared checkout.
4. Move remaining dirty paths into ownership buckets above and promote each
   bucket through its own worktree/branch, validation, commit, and PR.
5. Do not mix generated outputs, article batches, NLM executable changes, and
   runtime logs into a single cleanup commit.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not mutate `/Users/nuzantara/Desktop/nuzantara` from this runner.
- Do not use `--no-verify`, force push, or reset the shared checkout.

## Completion Criteria

This Spark intervention is complete when this spec is committed and pushed from
the isolated overnight branch, with validation proving no script code needed to
be changed. Follow-up cleanup belongs to the checkout owner because the
remaining dirty state spans multiple ownership domains.
