# Dirty Worktree NLM Regulatory Triage

Date: 2026-06-14
Dispatch key: `nuzantara-dirty-worktree-nlm-regulatory-triage`
Machine: Pro, `nuzantara@Nuzantara`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_122418.md`

## Scope

Create an operator-safe triage path for the broad dirty state in the main checkout at `/Users/nuzantara/Desktop/nuzantara`.

This spec is the remediation for the Spark signal. It does not clean the main checkout, commit the existing WIP, delete generated output, restart LaunchAgents, or deploy.

## Live Verification

The Spark report was rechecked from an isolated overnight worktree on 2026-06-14 WITA.

- Spark/Codex lifecycle is not the actionable root cause:
  - `com.nuzantara.codex-spark-loop` is running.
  - `com.nuzantara.codex-spark-alarm` and `com.nuzantara.codex-spark-harvester` are idle timer jobs with last exit `0`.
  - Codex state files under `/Users/nuzantara/.agent/decisions/state` are fresh.
- The main checkout dirty state is still live:
  - 19 tracked files modified.
  - Untracked buckets include articles, regulatory deltas, NotebookLM health reports, corpus/output directories, and new scripts.
- Most non-Codex LaunchAgent bad exits from the Spark snapshot had cleared during recheck; `com.balizero.wr2.plist-watchdog` remained non-zero. Treat LaunchAgent follow-up as a separate owner task unless it directly explains a dirty file bucket.

Useful recheck commands:

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short
git -C /Users/nuzantara/Desktop/nuzantara diff --stat
git -C /Users/nuzantara/Desktop/nuzantara diff --name-status
git -C /Users/nuzantara/Desktop/nuzantara ls-files --others --exclude-standard
launchctl list | rg 'codex-spark|wr2\.plist-watchdog|wr2\.hardening|openclaw\.guardian-board|canva-token-watchdog|matagaruda|domain-mesh'
```

## Triage Buckets

The next heavier agent should produce a manifest where every dirty path has: bucket, owner, evidence source, validation command, commit decision, and privacy risk.

### A. Source Changes

Candidate source paths:

- `apps/evaluator/nlm_deep_research/*.py`
- `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
- `scripts/curiosity_loop.sh`
- `scripts/dlq_autopilot.py`
- `scripts/nuzantara-sentinel.py`
- `scripts/nb_export_corpus.py`
- `scripts/nb_generate_inventory.py`
- `apps/crm-cell/war-room/interactive_cli.sh`

Required handling:

- Inspect diffs file by file.
- Separate intentional behavior changes from debug residue.
- Do not mix generated outputs or published articles in the same commit.
- For Python scripts, run syntax/import validation from the repo root with the active virtualenv.
- For shell scripts, run `bash -n`.
- If a source file reads client, WhatsApp, or OSINT data, verify only on Pro and do not copy raw data to another machine.

Minimum validation candidates:

```bash
source venv/bin/activate
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
  scripts/nb_export_corpus.py \
  scripts/nb_generate_inventory.py
bash -n scripts/curiosity_loop.sh
```

### B. Structured Data and Registry Updates

Candidate paths:

- `apps/bali-intel-scraper/data/published_articles.json`
- `apps/evaluator/nlm_deep_research/persona_definitions.json`
- `apps/evaluator/nlm_deep_research/t4_nb5_config.json`
- `apps/research/sota-social-2026-v1/kpi_timeline.csv`
- `docs/AUTOMATIONS_REFERENCE.md`
- `docs/DOCS_INVENTORY.md`

Required handling:

- Verify whether each file is generated from a script or edited by hand.
- If generated, identify and run the generator instead of hand-normalizing the file.
- Keep docs inventory churn separate from source changes unless the generator requires both.
- Validate JSON with `python -m json.tool`; validate CSV shape with a lightweight parser.

### C. Publishable Content and Research Artifacts

Candidate paths:

- `apps/mouth/src/content/articles/immigration/*.mdx`
- `apps/mouth/src/content/articles/tax/*.mdx`
- `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`
- `research/nb-health/2026-06-10-health.md`
- `research/nb-health/2026-06-11-health.md`
- `research/nb-health/2026-06-12-health.md`
- `research/nb-health/2026-06-13-health.md`
- `research/nb-health/2026-06-14-health.md`
- `research/operations/2026-06-11-drive-crm-unified-client-folders-design.md`
- `research/operations/2026-06-11-fable5-extra-task-allocation.md`
- `research/regulatory/2026-06-10-delta.json`
- `research/regulatory/2026-06-11-delta.json`
- `research/regulatory/2026-06-12-delta.json`
- `research/regulatory/2026-06-13-delta.json`
- `research/regulatory/2026-06-14-delta.json`

Required handling:

- Treat MDX articles as publishable content, not disposable output.
- Verify frontmatter and locale coverage before staging articles.
- For regulatory deltas, decide whether they are raw scan output, curated evidence, or follow-up inputs.
- Do not publish or merge regulatory content until source URLs and NotebookLM grounding have been checked.

Minimum validation candidates:

```bash
cd apps/mouth
npm run lint
npm run build
```

### D. Generated, Disposable, or Archive Candidates

Observed untracked generated/output buckets:

- `apps/evaluator/nlm_deep_research/output/multimodal/` around 47 MB.
- `research/coherence-corpus/` around 44 MB, with hundreds of JSON files.
- `outputs/` around 40 MB, including base64 chunks and client CSV exports.
- `research/commercial/` small untracked bucket.

Required handling:

- Do not commit these buckets wholesale.
- Check `.gitignore` before deleting or moving anything.
- Any file that contains client, WhatsApp, OSINT, or CRM-derived rows must stay local to Pro and must not be pushed.
- If the artifact is needed for reproducibility, compress/archive outside the repo or add a small manifest only.
- If the artifact is safe and intentionally versioned, commit it separately from source changes with an explicit owner note.

## Commit Strategy

Use small, reviewable commits after the manifest is complete:

1. Source-only commit for NLM pipeline or sentinel/autopilot behavior.
2. Generated-docs or registry commit, only if backed by generator evidence.
3. Publishable content commit, only after frontmatter/source validation.
4. Ignore/archive policy commit, if generated output should be excluded.

Never create a single catch-all dirty-worktree commit.

## Stop Conditions

Stop and write a blocked status if any of these are true:

- The dirty paths change materially during triage and ownership cannot be established.
- A file contains raw client, WhatsApp, OSINT, or credential-like data and the safe handling path is unclear.
- Validation requires production deploy, direct `main` push, `--no-verify`, force push, or secret/env changes.
- LaunchAgent failures become the dominant root cause and require service restarts outside this dirty-worktree scope.

## Exit Criteria

The heavier triage is complete when:

- Every dirty path in `/Users/nuzantara/Desktop/nuzantara` is assigned to one of the four buckets.
- Every source-path candidate has a validation command and owner.
- Generated/disposable buckets are either ignored, archived outside the repo, or represented by a safe manifest.
- Publishable articles and regulatory deltas have source validation notes.
- The final PR contains only one coherent bucket, or a blocked status explains why no safe commit can be made.
