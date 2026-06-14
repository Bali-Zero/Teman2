# Main Dirty Mixed Worktree Hygiene - 2026-06-15

Date: 2026-06-15 01:16 WITA
Dispatch key: `main-dirty-mixed-worktree`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_005718.md`
Overnight branch:
`codex-overnight/spark-alarm-20260615_010829-spark-dispatch-20260615_005718-scout-main-dirty-mixed-worktree-20260615_010829`
Audited checkout: `/Users/nuzantara/Desktop/nuzantara`

## Scope

Resolve the actionable Spark signal without modifying the shared main checkout.

The live evidence supports one root-cause cluster: mixed uncommitted work in the
shared `main` checkout. Spark itself is healthy by launchd lifecycle semantics,
so the safe remediation is a decision spec that assigns ownership and gates for
the dirty files. This spec is intentionally read-only with respect to
`/Users/nuzantara/Desktop/nuzantara`.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. The Mini peer was unreachable
  during the session-start SSH check, so Pro-to-Mini git sync is unverified.
- No path-specific `AGENTS.md` files exist under `apps/backend-rag/`, `scripts/`,
  or `apps/backend-rag/backend/llm/`; root `AGENTS.md` applies.
- Isolated overnight branch is clean before this spec.
- Shared checkout status:
  - `main...origin/main [ahead 2, behind 175]`
  - ahead commits:
    - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
    - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Live Spark/Codex launchd state:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 97`, `last exit code = 0`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 60`, `last exit code = 0`.
  - `codex-autofix-ci`, `codex-coverage-improver`, `codex-openclaw-analysis`,
    and `codex-research-actor` are idle/zero or never-run, not fresh failures.
- Separate non-Codex launchd failures remain:
  - `com.nuzantara.cost-breaker`: exit `127`
  - `com.nuzantara.mcp-integrity`: exit `127`
  - `com.nuzantara.intake-worker`: exit `78: EX_CONFIG`
  - `com.balizero.wr2.supervisor`: exit `66: EX_NOINPUT`
- An NLM writer is active from the shared checkout:
  - `~/scripts/cron-agent.sh exec nlm-deep-research ~/Desktop/nuzantara/scripts/nlm_pipeline_run.sh --force`
  - `/Users/nuzantara/Desktop/nuzantara/apps/backend-rag/.venv/bin/python -m apps.evaluator.nlm_deep_research.pipeline --verbose --force`

## Dirty State Summary

Staged executable changes:

- `scripts/dlq_autopilot.py`
- `scripts/nuzantara-sentinel.py`

Unstaged modified files:

- `.claude/rules/cicatrix-scars-archive.md`
- `.claude/rules/cicatrix-scars.md`
- `apps/bali-intel-scraper/data/published_articles.json`
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
- `apps/research/sota-social-2026-v1/kpi_timeline.csv`
- `docs/AUTOMATIONS_REFERENCE.md`
- `docs/DOCS_INVENTORY.md`
- `scripts/curiosity_loop.sh`
- `shared/escalations_pro.jsonl`

Untracked groups by count:

| Count | Group |
| ---: | --- |
| 840 | `research/coherence-corpus/` |
| 51 | `outputs/` |
| 5 | `research/regulatory/` |
| 5 | `research/nb-health/` |
| 5 | `apps/mouth/src/content/articles/` |
| 4 | `apps/evaluator/nlm_deep_research/output/multimodal/` |
| 3 | `scripts/` |
| 1 | `.claude/rules/cicatrix-superscar.md` |
| 1 | `apps/crm-cell/war-room/` |
| 1 | `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md` |
| 1 | `research/commercial/` |
| 2 | `research/operations/2026-06-11-*.md` |

Size-risk highlights:

- `apps/evaluator/nlm_deep_research/output/multimodal/`: `167M`, audio output.
- `research/coherence-corpus/`: `44M`, 840 JSON files.
- `outputs/`: `40M`, includes `_clients_b64.txt`, `_b64chunks/`,
  `clients_all.csv`, and `clients_master_clean.csv`.
- `research/commercial/`: small currently, but still untracked business research.

## Root-Cause Classification

Primary cluster: shared-checkout mixed WIP from several owners.

Subclusters:

1. Automation heal-loop patch work staged in `scripts/dlq_autopilot.py` and
   `scripts/nuzantara-sentinel.py`.
2. NotebookLM/NLM pipeline configuration drift and generated output, including
   notebook ID rotations, `nlm` profile changes, corpus export, health reports,
   regulatory deltas, and multimodal audio.
3. Content/publication work, including article MDX files and
   `published_articles.json`.
4. Automation inventory and cicatrix memory maintenance output.
5. Private or high-risk local exports in `outputs/`, likely not suitable for git.
6. Separate launchd failures that are real but not causally tied to Spark.

Because the shared checkout is both behind `origin/main` and ahead by two local
commits, cleanup must not begin with `git pull`, branch switching, reset, or a
global stash. The active NLM writer is an additional hard gate.

## Action Matrix

| Group | Current evidence | Owner/domain | Safe action | Gate |
| --- | --- | --- | --- | --- |
| `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged W70 heal-loop changes, 205 inserted lines. | Automation/sentinel owner | Keep candidate. Move to a dedicated branch or commit separate from generated outputs. | Run syntax checks and focused sentinel/DLQ validation before commit. Do not mix with docs or NLM data. |
| `apps/evaluator/nlm_deep_research/*.py`, `persona_definitions.json`, `t4_nb5_config.json` | Notebook IDs changed for NB-2, NB-5, NB-6. | NLM pipeline owner | Keep candidate if IDs are confirmed current. Commit as one config-only change. | Wait until active `nlm-deep-research` process exits. Verify notebook IDs and run focused NLM smoke checks. |
| `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | `nlm --profile zero` changed to `--profile default`. | Mata Garuda/NLM owner | Keep only if `default` is the intended production profile. Otherwise revert or make profile configurable. | Verify installed `nlm` profiles and run a dry source-add against a safe test notebook. |
| `research/coherence-corpus/` | 840 untracked JSON files, `44M`. | NLM corpus owner | Generated-output candidate. Prefer archive outside git or commit only manifest/summaries. | Check for client/private payloads before any commit. |
| `apps/evaluator/nlm_deep_research/output/multimodal/` | 4 untracked `.m4a` files, `167M`. | NLM multimedia owner | Archive artifact outside git. Do not commit audio blobs unless a tracked artifact policy explicitly allows it. | Confirm destination and retention policy. |
| `outputs/` | `40M`, client CSV and base64 chunk names. | Private data owner | Do not commit. Treat as private/local export. Archive securely or drop from git view only after owner confirmation. | Never inspect raw contents in a general-purpose cleanup pass. |
| `apps/mouth/src/content/articles/*`, `apps/bali-intel-scraper/data/published_articles.json`, ahead article commits | Public content pipeline. | Editorial/content owner | Keep candidate in a content branch. Commit MDX and registry updates separately from automation. | Run content build/lint and verify source URLs/citations. |
| `.claude/rules/cicatrix-*`, `scripts/scar_query.py` | Scar archive rotation plus new superscar/query helper. | Cicatrix/memory owner | Keep candidate if generated by scar rotation. Commit active/archive/helper together after review. | Check no secrets in scar text and validate helper `--help`. |
| `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl` | Generated automation inventory and escalation output. | Ops documentation owner | Generated snapshot candidate. Commit only if timestamped snapshot is intended; otherwise regenerate after main is synced. | Confirm generator command and rerun from a clean branch. |
| `research/nb-health/`, `research/regulatory/`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/operations/2026-06-11-*.md`, `research/commercial/` | Research reports and deltas. | Research/NB health owner | Keep as documentation if reviewed, otherwise archive as generated run output. | Check filenames, dates, and source provenance. |
| `apps/crm-cell/war-room/interactive_cli.sh` | One untracked shell helper. | CRM cell owner | Keep only with a README/test or drop from git. | Inspect for secrets and validate shell syntax. |
| `com.nuzantara.cost-breaker`, `com.nuzantara.mcp-integrity`, `com.nuzantara.intake-worker`, `com.balizero.wr2.supervisor` | launchd exits `127`, `127`, `78`, `66`. | Ops launchd owner | Separate follow-up incident. Do not conflate with Spark/dirty-main cleanup. | Triage each with logs, plist, and program path checks. |

## Recommended Cleanup Order

1. Stop the bleed: wait until the active `nlm-deep-research` process exits, then
   confirm no known writers are running:
   `ps -o pid,etime,command -u $(whoami) | rg 'nlm_pipeline_run|nlm_deep_research|nb_export_corpus|nb_generate_inventory'`.
2. Preserve branch context before touching WIP: record `git status --short
   --branch`, the two ahead commits, and a grouped file manifest. Do not run a
   global `git stash -u` because it would mix private exports, generated blobs,
   and executable behavior changes.
3. Handle executable code first:
   - automation heal-loop staged patch in its own branch/commit;
   - NLM config/notebook ID changes in their own branch/commit;
   - `nlm_feeder.py` profile change only after profile verification.
4. Handle public content second: MDX articles plus
   `published_articles.json`, after the content build passes.
5. Handle generated docs/research third: commit only reviewed summaries and
   manifests, not bulk generated artifacts by default.
6. Handle private/generated blobs last: `outputs/`, audio, and corpus exports
   should be archived outside git or removed from the working tree only by the
   owning operator.
7. Triage non-Codex launchd failures in a separate ops ticket/spec. Do not block
   the dirty-main cleanup on them unless they are active writers.

## Non-Goals

- Do not restart, unload, or rewrite Spark LaunchAgents.
- Do not clean, stash, reset, or stage files in `/Users/nuzantara/Desktop/nuzantara`
  from this overnight branch.
- Do not inspect raw client export contents under `outputs/`.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`,
  `secrets/*`, or `backend/app/dependencies.py`.

## Exit Criteria For The Heavier Cleanup Agent

- Shared checkout no longer has mixed owner WIP.
- Any private/generated outputs are either ignored, archived outside git, or
  explicitly documented as tracked artifacts.
- Executable behavior changes have focused validation and separate commits.
- Content updates have content build/lint validation and separate commits.
- `main` is reconciled with `origin/main` without losing the two local ahead
  commits.
- Spark lifecycle remains healthy after cleanup, with no new Codex LaunchAgent
  failures introduced.
