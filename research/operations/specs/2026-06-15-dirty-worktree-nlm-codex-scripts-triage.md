# Dirty Worktree Triage - NLM and Codex Scripts - 2026-06-15

Date: 2026-06-15
Dispatch key: `dirty-worktree-nlm-codex-scripts`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_025054.md`
Spark prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_025054.prompt.md`
Runtime worktree:
`/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-overnight-runner-runs/spark-alarm-20260615_025755-spark-dispatch-20260615_025054-scout-dirty-worktree-nlm-codex-scripts-20260615_025755`

## Purpose

Resolve the dirty shared checkout signal in
`/Users/nuzantara/Desktop/nuzantara` without destroying or normalizing work
owned by another live agent. This is a decision and handoff spec for a heavier
agent. It does not authorize cleanup from an unrelated worktree.

## Live Evidence Verified

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer sync: `mini` was unreachable at session start, so cross-machine sync is
  unverified.
- Overnight branch:
  `codex-overnight/spark-alarm-20260615_025755-spark-dispatch-20260615_025054-scout-dirty-worktree-nlm-codex-scripts-20260615_025755`.
- Spark lifecycle is not the actionable root cause:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- Codex/Spark state files under `/Users/nuzantara/.agent/decisions/state` were
  fresh during the live check:
  - `codex_com_nuzantara_codex_spark_loop.state.json`: 2026-06-15 02:56:37 WITA.
  - `codex_com_nuzantara_codex_spark_alarm.state.json`: 2026-06-15 02:57:55 WITA.
  - `codex_com_nuzantara_codex_spark_harvester.state.json`: 2026-06-15 02:58:59 WITA.
  - `launchd_bad_exits.json`: 2026-06-15 02:59:07 WITA.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is broadly dirty:
  - staged/index-touched: `scripts/dlq_autopilot.py`,
    `scripts/nuzantara-sentinel.py`.
  - unstaged NLM pipeline changes under `apps/evaluator/nlm_deep_research/`.
  - unstaged Mata Garuda NLM feeder profile change.
  - unstaged `scripts/curiosity_loop.sh` Python selection change.
  - untracked generated outputs, research corpora, NotebookLM health reports,
    article MDX files, and helper scripts.
- Non-Codex launchd failures are adjacent evidence, not this intervention's
  remediation target:
  - `com.nuzantara.cost-breaker`: last exit `127`.
  - `com.nuzantara.mcp-integrity`: last exit `127`.
  - `com.nuzantara.intake-worker`: last exit `78`.
  - `com.nuzantara.verify-the-verifiers`: last exit `2`.

## Root-Cause Classification

Primary cluster: mixed work left in the shared main checkout after an NLM and
operations maintenance pass.

The evidence does not support a Spark LaunchAgent fix. The dangerous part is the
mix: operator script changes are already staged, while NLM notebook rotations,
generated outputs, article drafts, scars, research deltas, and helper scripts
are unstaged or untracked. Treating this as one commit would blur ownership and
validation.

## Required First Moves For The Heavier Agent

Run these from the shared checkout before deciding what to keep:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git status --short
git diff --cached --name-status
git diff --name-status
git ls-files --others --exclude-standard > /tmp/dirty-worktree-untracked-20260615.txt
git diff --cached > /tmp/dirty-worktree-index-20260615.patch
git diff > /tmp/dirty-worktree-unstaged-20260615.patch
```

Do not run `git reset`, `git checkout --`, `git clean`, `git stash -u`, or a
branch switch until the file plan below has been applied or replaced by a newer
operator-approved plan.

## File Plan

| Bucket | Paths | Current state | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- |
| PR A: DLQ/sentinel heal-loop behavior | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged modifications | Keep only as a dedicated ops-script PR. Do not mix with docs, NLM IDs, generated outputs, or articles. | Run focused script tests and static import/compile checks. Confirm no command path mutates real DLQ or sends alerts during tests. |
| PR B: NLM notebook ID/profile rotation | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged modifications | Keep only if the new NotebookLM IDs and `nlm --profile default` are verified against the live NotebookLM account. Commit separately from PR A. | Tests pass for NLM deep research and Mata Garuda feeder routing. Live verification proves each new notebook ID is reachable and mapped to the intended domain. |
| PR C: runtime Python selection | `scripts/curiosity_loop.sh` | Unstaged modification | Keep as a separate small ops fix or fold into PR A only if it is proven to be the same incident. | Shellcheck if available, plus a dry command resolution check showing the selected Python is executable and Python 3.11+. |
| PR D: documentation and scars | `.claude/rules/cicatrix-scars*.md`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md` | Mixed modified/untracked | Keep only after owner review. Split docs inventory churn from cicatrix rules. | Markdown or JSON/CSV syntax checks where applicable. No runtime code changes in the same commit. |
| PR E: article content | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Modified/untracked | Keep as content PR only after editorial provenance review. | Frontend content lint/build for `apps/mouth`, no duplicate slugs, no private/internal owner names. |
| Archive or ignore: generated media and corpora | `apps/evaluator/nlm_deep_research/output/multimodal/`, `outputs/`, `research/coherence-corpus/`, `research/regulatory/*-delta.json`, `research/nb-health/*.md`, `research/nb-monitor/`, `research/commercial/` | Untracked | Do not commit by default. Archive outside git or add precise `.gitignore` entries only after confirming they are reproducible artifacts. | If retained, each artifact has a manifest, source command, size check, and explicit reason to version it. Otherwise leave untouched until owner archives or removes. |
| Hold for owner | `apps/crm-cell/war-room/`, `research/operations/2026-06-11-*.md`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `scripts/scar_query.py`, `shared/escalations_pro.jsonl` | Untracked or modified | Do not classify automatically. These can contain workflow, corpus, or escalation context. | Owner or source-agent attribution is known, and any raw/private data exposure has been ruled out before commit. |

## Focused Validation Commands

Use the repo virtualenv. Do not use system Python.

### PR A - DLQ and sentinel scripts

```bash
cd /Users/nuzantara/Desktop/nuzantara
source apps/backend-rag/.venv/bin/activate
python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_escalations_s3.py scripts/tests/test_sentinel_v33.py -q
```

Safety checks before merge:

```bash
git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
rg -n "send_alert|clear_dlq_entry|requeue_terminal|BLIND_LOOP|cron log tail|print\\(" scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
```

Expected decision: commit as `fix(ops): restore DLQ sentinel diagnostics` only
if the tests pass and the diff is still limited to the heal-loop behavior.

### PR B - NotebookLM pipeline changes

```bash
cd /Users/nuzantara/Desktop/nuzantara
source apps/backend-rag/.venv/bin/activate
PYTHONPATH=. pytest \
  apps/evaluator/nlm_deep_research/tests/test_cross_notebook_correlator.py \
  apps/evaluator/nlm_deep_research/tests/test_freshness_monitor.py \
  apps/evaluator/nlm_deep_research/tests/test_gap_remediation.py \
  apps/evaluator/nlm_deep_research/tests/test_multimodal_pipeline.py \
  apps/mata-garuda/tests/test_nlm_feeder.py \
  -q
```

Live NotebookLM verification must precede merge:

```bash
nlm notebook list --profile default
nlm notebook list --profile zero
```

Decision rule:
- If `default` is correct and `zero` is obsolete, keep the profile change and
  migrate the duplicated notebook IDs into one registry follow-up.
- If both profiles are valid, stop and ask the operator which profile owns
  production ingestion.
- If the new notebook IDs are not visible, revert or stash PR B only.

### PR C - Curiosity loop Python selection

```bash
cd /Users/nuzantara/Desktop/nuzantara
bash -n scripts/curiosity_loop.sh
test -x "$HOME/.pyenv/versions/3.11.11/bin/python3" || test -x "$HOME/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3"
"$HOME/.pyenv/versions/3.11.11/bin/python3" --version 2>/dev/null || "$HOME/Desktop/nuzantara/apps/backend-rag/.venv/bin/python3" --version
```

## Commit Order

1. `fix(ops): restore DLQ sentinel diagnostics`
2. `fix(nlm): rotate notebook IDs and profile`
3. `fix(ops): pin curiosity loop python`
4. `docs(ops): update cicatrix and automation inventory`
5. `content(mouth): add June regulatory articles`
6. Archive generated artifacts outside git, or commit only a manifest if
   explicitly approved.

Each commit must be pushed after it is created. Do not accumulate more than one
cluster of uncommitted changes.

## Non-Goals And Hard Stops

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not mutate `backend/prompts/zantara_core.py`.
- Do not mutate `fly.toml`, `.env*`, or `secrets/*`.
- Do not change the embedding model from `text-embedding-3-small`.
- Do not force push, use `--no-verify`, or bypass required checks.
- Do not move raw WhatsApp/OSINT/corpus data off Pro or into public PRs.
- Do not clean the shared checkout from an unrelated worktree.

## Completion Criteria

The dirty-worktree incident is closed only when:

- `/Users/nuzantara/Desktop/nuzantara` has no staged operational scripts mixed
  with unrelated untracked artifacts.
- Every kept cluster has its own branch/PR or commit with relevant validation.
- Every generated or private artifact is archived outside git or explicitly
  justified by a manifest.
- Launchd non-Codex failures are either linked to an owner ticket or placed into
  a separate remediation spec.
- A final status note records what was kept, what was stashed or archived, and
  what remains blocked.
