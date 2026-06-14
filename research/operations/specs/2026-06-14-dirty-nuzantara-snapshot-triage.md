# Dirty Nuzantara Snapshot Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-nuzantara-snapshot-2026-06-14`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_112529.md`
Overnight branch:
`codex-overnight/spark-alarm-20260614_112631-spark-dispatch-20260614_112529-scout-dirty-nuzantara-snapshot-2026-06-14-20260614_112632`

## Scope

Resolve the actionable Spark signal by turning the broad dirty shared checkout
into a concrete ownership and split plan. This spec is deliberately
decision-only: it does not clean, stage, unstage, stash, or rewrite files in
`/Users/nuzantara/Desktop/nuzantara`.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. The Mini peer was unreachable
  during the session-start SSH check, so peer git sync is unverified.
- Only root `AGENTS.md` is present in this checkout; no path-specific
  `AGENTS.md` exists under `apps/backend-rag/`, `scripts/`, or
  `apps/backend-rag/backend/llm/`.
- Source artifacts exist:
  - `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_112529.md`
  - `/Users/nuzantara/logs/codex-spark-loop/scout-20260614_112529.prompt.md`
  - `/Users/nuzantara/logs/codex-spark-loop/scout-20260614_112529.jsonl`
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1025`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 277`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 181`, `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: `state = running`, `pid = 91159`.
- Codex state files are fresh for this incident:
  - `codex_com_nuzantara_codex_spark_loop.state.json`: 2026-06-14 11:26:03 WITA.
  - `codex_com_nuzantara_codex_spark_alarm.state.json`: 2026-06-14 11:26:31 WITA.
  - `codex_com_nuzantara_codex_spark_harvester.state.json`: 2026-06-14 11:26:48 WITA.
  - `codex_com_nuzantara_codex_overnight_runner.state.json`: 2026-06-14 11:26:50 WITA.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is still dirty on
  `main` at `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`.
- `git status --porcelain=v1` in the shared checkout reports 46 entries.
- Staged executable behavior changes:
  - `scripts/dlq_autopilot.py`: 55 insertions.
  - `scripts/nuzantara-sentinel.py`: 150 insertions, 2 deletions.
- Unstaged tracked changes span 19 files, with `git diff --stat` reporting
  1,520 insertions and 1,127 deletions. The largest tracked surfaces are
  `docs/DOCS_INVENTORY.md`, `docs/AUTOMATIONS_REFERENCE.md`,
  `apps/bali-intel-scraper/data/published_articles.json`, NLM pipeline files,
  `scripts/curiosity_loop.sh`, and `shared/escalations_pro.jsonl`.
- Untracked groups by count:
  - `research/coherence-corpus/`: 840 files, about 44 MB.
  - `outputs/`: 51 files, about 40 MB, including base64 chunks and client CSVs.
  - `apps/mouth/src/content/articles/`: 5 MDX files.
  - `research/regulatory/`: 5 delta JSON files.
  - `research/nb-health/`: 5 health markdown reports.
  - `scripts/`: `nb_export_corpus.py`, `nb_generate_inventory.py`.
  - `apps/evaluator/nlm_deep_research/output/multimodal/`: one NB6 audio file,
    about 47 MB.
  - Single-file groups: `apps/crm-cell/war-room/interactive_cli.sh`,
    `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`,
    `research/commercial/`, and two operations research notes.

## Root-Cause Classification

Primary cluster: multi-lane work accumulated in the shared `main` checkout.

The evidence does not justify a Spark LaunchAgent repair. The actionable problem
is that unrelated work is co-resident in `/Users/nuzantara/Desktop/nuzantara`:
automation code, NLM pipeline edits, content publication metadata, generated
research corpora, CRM/war-room artifacts, and docs inventories. These have
different owners, validation gates, and privacy risks, so they must not be
committed as one broad snapshot.

## Lane Plan

| Lane | Paths | Current signal | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Sentinel and DLQ automation | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged behavior change adding DLQ requeue and W70 sentinel enrichment/resurrection logic. | Ops automation owner | Commit separately only after `source venv/bin/activate && python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py` and focused tests such as `PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_sentinel_v33.py -q`. Confirm LaunchAgent state/log paths match live Pro paths before merge. |
| NLM pipeline code and config | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Multiple small tracked edits plus two new helper scripts. | NLM / NotebookLM pipeline owner | Commit code/config separately from generated outputs. Validate with `source venv/bin/activate`, `python -m py_compile` on changed Python files, and the smallest existing NLM tests. Do not mix with docs inventory rewrites or content publishing. |
| Generated NLM outputs | `apps/evaluator/nlm_deep_research/output/multimodal/`, `research/nb-health/`, `research/coherence-corpus/`, `research/regulatory/*-delta.json` | Large untracked generated corpus/audio/report artifacts. | Research corpus owner | Keep only artifacts that have a documented consumer. Large binary/audio and raw corpus dumps need an explicit keep/drop decision before git add. Prefer manifests or checksums when the raw payload is not required in git. |
| Published articles | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Five new localized article files plus a 340-line publication registry update. | Editorial / Mouth owner | Commit as one content-publication lane after frontmatter, locale pairing, slug routing, and registry consistency are checked. Run the smallest Mouth validation available, at minimum `cd apps/mouth && npm run lint` or the existing content validation command. |
| Regulatory and social research | `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/operations/2026-06-11-*.md`, `research/commercial/` | Research outputs and planning notes. | Research ops owner | Commit after factual review and date/source consistency checks. Keep separate from executable code and generated docs inventories. |
| Docs inventory and automation reference | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Large generated markdown churn. | Docs automation owner | Regenerate from the canonical generator and commit only if the diff is reproducible. Do not hand-edit these files in the same commit as code or content. |
| Curiosity and escalation logs | `scripts/curiosity_loop.sh`, `shared/escalations_pro.jsonl` | One shell behavior edit and appended escalation records. | Ops / escalation owner | Split shell behavior from append-only operational records. Validate shell syntax with `bash -n scripts/curiosity_loop.sh`. Review log records for privacy before commit. |
| CRM war-room and client exports | `apps/crm-cell/war-room/`, `outputs/clients_all.csv`, `outputs/clients_master_clean.csv`, `outputs/_b64chunks/`, `outputs/_clients_b64.txt` | Untracked CLI plus generated client export material. | CRM / OSINT owner | Treat as privacy-gated. Do not commit raw client exports or base64 chunks until redaction and retention policy are explicit. If these are scratch outputs, move them out of the repo or add a follow-up `.gitignore` rule in a separate reviewed commit. |

## Commit Order

1. `fix(ops): add W70 sentinel dlq recovery path`
   - Only `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py`, and
     their tests if needed.
2. `feat(nlm): update notebook pipeline inventory flow`
   - NLM code/config/helper scripts only.
3. `data(nlm): add curated notebook health and regulatory manifests`
   - Generated NLM/research artifacts only after keep/drop review.
4. `feat(content): publish June immigration and tax articles`
   - MDX articles plus `published_articles.json`.
5. `docs(ops): refresh automation and docs inventories`
   - Generated docs only after reproducibility check.
6. `chore(ops): record research and escalation outputs`
   - Research notes and escalation logs, privacy-reviewed.

Do not merge these lanes into one commit. The automation lane is executable
behavior; the generated-output lanes have size/privacy risk; the content lane is
user-facing editorial surface.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`,
  `secrets/*`, or `backend/app/dependencies.py`.
- Do not clean, stash, unstage, reset, or delete files in the shared checkout
  from an unrelated overnight worktree.
- Do not commit `outputs/` or client/export payloads without explicit privacy
  review.
- Do not use `--no-verify`, force push, or bypass branch protection.

## Immediate Operator Handoff

Run these read-only commands in `/Users/nuzantara/Desktop/nuzantara` before
taking ownership of a lane:

```bash
git status --short
git diff --cached --name-status
git diff --name-status
git ls-files --others --exclude-standard
```

Then claim one lane, stage only that lane, validate it, commit it, and push
through the normal PR path. If no owner claims the privacy-gated `outputs/` and
CRM export material, preserve it outside git or remove it only after confirming
that it is scratch output.

## Overnight Decision

This overnight intervention should stop at this triage spec. The dirty snapshot
is still real, but the safe remediation is ownership separation, not automated
cleanup. The shared checkout remains untouched.
