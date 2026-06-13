---
date: 2026-06-14
domain: operations
status: handoff-spec
source_report: /Users/nuzantara/codex-spark-loop/reports/scout-20260614_024238.md
dispatch_key: dirty-nlm-regulatory-worktree
machine: Pro
---

# Dirty NLM / Regulatory Worktree Triage

## Summary

Spark correctly found an actionable operational signal, but the root cause is not
the Spark lifecycle itself. The live issue is a heavily dirty main checkout at
`/Users/nuzantara/Desktop/nuzantara`, with NLM pipeline edits, public content,
regulatory research deltas, automation script/docs edits, and generated output
artifacts mixed together.

This must be split by a heavier agent into small, reviewable groups. Do not try
to normalize the main checkout in place, do not mass-stage everything, and do not
deploy from this state.

## Live Evidence

Verified from isolated overnight worktree
`/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-overnight-runner-runs/spark-alarm-20260614_024448-spark-dispatch-20260614_024238-scout-dirty-nlm-regulatory-worktree-20260614_024448`.

### Spark / overnight lifecycle

`launchctl print` evidence:

| Label | Live state | Interpretation |
| --- | --- | --- |
| `com.nuzantara.codex-spark-loop` | `state = running`, `pid = 1025`, `last exit code = (never exited)` | Healthy active loop. |
| `com.nuzantara.codex-spark-alarm` | `state = not running`, `last exit code = 0`, `run interval = 120 seconds` | Healthy idle timer. |
| `com.nuzantara.codex-spark-harvester` | `state = not running`, `last exit code = 0`, `run interval = 180 seconds` | Healthy idle timer. |
| `com.nuzantara.codex-overnight-runner` | `state = running`, `pid = 76704`, `last exit code = 0` | This intervention is active. |

Fresh non-zero LaunchAgent exits still needing separate follow-up:

| Label | Current last exit | Scope |
| --- | ---: | --- |
| `com.nuzantara.mcp-integrity` | 2 | MCP integrity, separate ops task. |
| `com.balizero.wr2.plist-watchdog` | 1 | WR2 launchd watchdog, separate WR2 task. |
| `com.balizero.wr2.html-apply` | 1 | WR2 HTML apply, separate WR2 task. |

Spark reported `com.nuzantara.cost-ledger-export` as last exit `1`; live
verification now shows `last exit code = 0`, so that assertion is stale and
should not be used as a blocker.

### Main checkout dirty state

`git -C /Users/nuzantara/Desktop/nuzantara status --short --branch` shows:

- `main...origin/main [ahead 2, behind 159]`
- 17 modified tracked files
- many untracked artifacts under `apps/crm-cell/war-room/`,
  `apps/evaluator/nlm_deep_research/output/`, `apps/mouth/src/content/articles/`,
  `outputs/`, `research/coherence-corpus/`, `research/nb-health/`,
  `research/operations/`, `research/regulatory/`, and `scripts/`.

This is a mixed working tree, not a single coherent patch.

## Safety Rules

1. Work only from a dedicated worktree/branch created by `scripts/agent_start.py`.
2. Treat `/Users/nuzantara/Desktop/nuzantara` as evidence, not as the mutation target.
3. Do not run `git add -A` or commit from the main checkout.
4. Do not push directly to `main`.
5. Do not deploy.
6. Do not copy raw OSINT, client exports, or generated CSV/base64 chunks into a PR
   until provenance and sensitivity are explicitly reviewed.
7. Keep each resulting PR scoped to one group below.

## Split Groups

### Group A: NLM Pipeline Source Changes

Candidate paths:

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
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `scripts/nb_export_corpus.py`

Required classification:

- Determine whether these are a coordinated NLM pipeline update or incidental
  edits from separate agents.
- Verify no prompt/key/model changes introduce new Anthropic API-key environment
  usage or new OpenAI API-key environment usage.
- Verify the frozen embedding model remains `text-embedding-3-small` for RAG
  vector paths.

Suggested validation:

```bash
python -m py_compile \
  apps/evaluator/nlm_deep_research/cross_notebook_correlator.py \
  apps/evaluator/nlm_deep_research/freshness_monitor.py \
  apps/evaluator/nlm_deep_research/gap_scanner.py \
  apps/evaluator/nlm_deep_research/multimodal_pipeline.py \
  apps/evaluator/nlm_deep_research/nb5_pipeline.py \
  apps/evaluator/nlm_deep_research/nb6_pipeline.py \
  apps/evaluator/nlm_deep_research/peraturan_ingestion_trigger.py \
  apps/evaluator/nlm_deep_research/pipeline.py \
  apps/evaluator/nlm_deep_research/t4_monitor.py \
  apps/evaluator/nlm_deep_research/yt_monitor.py \
  apps/mata-garuda/mata_garuda/workers/nlm_feeder.py \
  scripts/nb_export_corpus.py
python -m json.tool apps/evaluator/nlm_deep_research/persona_definitions.json >/dev/null
python -m json.tool apps/evaluator/nlm_deep_research/t4_nb5_config.json >/dev/null
```

### Group B: Published/Public Content

Candidate paths:

- `apps/bali-intel-scraper/data/published_articles.json`
- `apps/mouth/src/content/articles/immigration/indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists.mdx`
- `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.id.mdx`
- `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.it.mdx`
- `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.id.mdx`
- `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.it.mdx`

Required classification:

- Confirm each article has source URLs, dates, language metadata, and no internal
  client names.
- Confirm `published_articles.json` matches the article slugs and does not mark
  drafts as published accidentally.

Suggested validation:

```bash
python -m json.tool apps/bali-intel-scraper/data/published_articles.json >/dev/null
cd apps/mouth && npm run lint
```

### Group C: Regulatory Delta / NB Health Research

Candidate paths:

- `research/regulatory/2026-06-10-delta.json`
- `research/regulatory/2026-06-11-delta.json`
- `research/regulatory/2026-06-12-delta.json`
- `research/regulatory/2026-06-13-delta.json`
- `research/nb-health/2026-06-10-health.md`
- `research/nb-health/2026-06-11-health.md`
- `research/nb-health/2026-06-12-health.md`
- `research/nb-health/2026-06-13-health.md`
- `research/coherence-corpus/`

Required classification:

- Separate small human-authored health notes from large generated corpus files.
- JSON deltas can be considered for commit only after schema/provenance check.
- `research/coherence-corpus/` should be treated as generated corpus output and
  reviewed for size, source license, and sensitivity before inclusion.

Suggested validation:

```bash
for f in research/regulatory/2026-06-{10,11,12,13}-delta.json; do
  python -m json.tool "$f" >/dev/null
done
find research/coherence-corpus -type f | wc -l
find research/coherence-corpus -type f -size +5M -print
```

### Group D: Automation Docs and Scripts

Candidate paths:

- `docs/AUTOMATIONS_REFERENCE.md`
- `scripts/curiosity_loop.sh`
- `apps/crm-cell/war-room/interactive_cli.sh`
- `research/operations/2026-06-11-drive-crm-unified-client-folders-design.md`
- `research/operations/2026-06-11-fable5-extra-task-allocation.md`

Required classification:

- Keep docs-only changes separate from runnable automation changes.
- Confirm shell scripts use strict mode and do not embed secrets.
- Confirm any CRM/Drive material is client-safe before public PR.

Suggested validation:

```bash
bash -n scripts/curiosity_loop.sh
bash -n apps/crm-cell/war-room/interactive_cli.sh
rg -n "api_key|secret|token|BEGIN .*PRIVATE KEY" \
  docs/AUTOMATIONS_REFERENCE.md scripts/curiosity_loop.sh apps/crm-cell/war-room/interactive_cli.sh
```

### Group E: Generated Outputs / Client Exports

Candidate paths:

- `apps/evaluator/nlm_deep_research/output/multimodal/`
- `outputs/_b64chunks/`
- `outputs/_clients_b64.txt`
- `outputs/clients_all.csv`
- `outputs/clients_master_clean.csv`
- `apps/evaluator/nlm_deep_research/output/multimodal/nb6/audio/20260611_nb6.m4a`

Default disposition:

- Do not commit these in the first pass.
- Move to an artifact store or add an explicit follow-up to `.gitignore` only
  after confirming they are reproducible/generated and not intended source data.
- Treat client CSVs and base64 chunks as sensitive until proven otherwise.

### Group F: LaunchAgent Follow-ups

Candidate tasks:

- `com.nuzantara.mcp-integrity` exit 2.
- `com.balizero.wr2.plist-watchdog` exit 1.
- `com.balizero.wr2.html-apply` exit 1.

Required classification:

- Do not fold these into NLM/regulatory cleanup PRs.
- Each label needs its own log read, wrapper inspection, and minimal validation.
- `com.nuzantara.cost-ledger-export` is not currently non-zero and should not be
  queued from this snapshot alone.

## Recommended Execution Order

1. Create one dedicated worktree per accepted group.
2. Rebase each group from current `origin/main`, not from stale local `main`.
3. For each group, selectively copy or apply only that group's paths from the
   dirty main checkout.
4. Run the group's validations before committing.
5. Open one PR per group.
6. Leave generated outputs uncommitted unless a human explicitly authorizes
   their publication or artifact-storage path.

## Stop Conditions

Stop and write a blocked status if any of these are true:

- The dirty main checkout changes while being classified and the path ownership
  cannot be established.
- Any candidate file contains raw WhatsApp/OSINT data, client export data, or
  secrets.
- A group requires production deploy or live LaunchAgent reload.
- `origin/main` has diverged in a way that makes clean selective application
  impossible without human ownership decisions.

## Acceptance Criteria for the Heavier Agent

- Produce a table of every dirty path with one group assignment and disposition:
  `commit`, `artifact`, `ignore`, `separate task`, or `blocked`.
- Produce at most one PR per group.
- Include exact validation commands and outputs in each PR body.
- Leave `/Users/nuzantara/Desktop/nuzantara` no worse than found.
- Do not mark Spark lifecycle as failed unless a new live check shows the loop is
  not running or the alarm/harvester have fresh non-zero exits.
