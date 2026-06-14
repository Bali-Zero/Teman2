# Dirty Main Worktree Triage - 2026-06-14 23:46 WITA

Date: 2026-06-14
Dispatch key: `dirty-main-worktree-triage`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_234404.md`
Runner branch: `codex-overnight/spark-alarm-20260614_234426-spark-dispatch-20260614_234404-scout-dirty-main-worktree-triage-20260614_234426`
Machine: Pro, `nuzantara@Nuzantara`
Peer sync: `mini` was unreachable during the session-start check, so peer git
sync was not verified.
Decision deadline: 2026-06-15 12:00 WITA

## Decision

Do not mutate `/Users/nuzantara/Desktop/nuzantara` from this unattended
overnight run.

The Spark lifecycle signal is healthy. The actionable cluster is the shared main
checkout, which is dirty, stale relative to `origin/main`, and actively changing
while observed. The safe remediation is this owner-scoped triage handoff, not a
bulk commit, cleanup, reset, stash-pop, LaunchAgent restart, or deploy.

## Live Evidence

- Root instructions read from `AGENTS.md`.
- No path-specific `AGENTS.md` files were found under `apps/backend-rag/`,
  `scripts/`, or `apps/backend-rag/backend/llm/`.
- Isolated worktree is on the required branch at `a03b928fe`, matching
  `origin/main` at the start of this run.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on:

```text
HEAD: e2b355f45
branch: main...origin/main [ahead 2, behind 175]
```

- Live dirty-state counts from the shared checkout:
  - 942 total `git status --porcelain=v1 --untracked-files=all` entries.
  - 21 unstaged tracked modifications.
  - 2 staged tracked modifications.
  - 919 untracked files.
- The shared checkout was volatile during observation. Two tracked
  `.claude/rules` files appeared as modified after the first status pass, so all
  counts in this document are a timestamped snapshot rather than a lock.
- Spark trio is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: StartInterval timer, `state = not
    running`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: StartInterval timer, `state = not
    running`, `last exit code = 0`, `run interval = 180 seconds`.
- Spark/Codex state files are fresh around 23:44 WITA:
  - `codex_com_nuzantara_codex_spark_loop.state.json`
  - `codex_com_nuzantara_codex_spark_alarm.state.json`
  - `codex_com_nuzantara_codex_spark_harvester.state.json`
- Bad launchd exits are real but outside this root-cause cluster. The fresh
  `/Users/nuzantara/.agent/decisions/state/launchd_bad_exits.json` snapshot at
  23:46:44 WITA includes several `127` exits such as
  `com.nuzantara.cost-breaker`, `com.nuzantara.mcp-integrity`,
  `com.nuzantara.review-gate`, and `com.nuzantara.merge-train`. Handle those in
  a separate runtime-owner pass.

## Root-Cause Classification

Primary cluster: shared-checkout work from multiple owners was accumulated in
`/Users/nuzantara/Desktop/nuzantara`.

This is not one patch. It mixes executable ops changes, NLM NotebookLM routing
changes, generated corpora, local/private exports, published content, docs
inventories, research reports, audio outputs, and runtime JSONL/log data. The
main checkout being `ahead 2, behind 175` means it is also not a safe base for
normalizing runtime or content work.

## Snapshot By Group

| Group | Status count | Current examples | Kind | Default action |
| --- | ---: | --- | --- | --- |
| `.claude/rules` | 3 | `cicatrix-scars*.md`, `cicatrix-superscar.md` | Agent memory/rules | Review with operator. Do not auto-commit from an overnight branch. |
| `scripts/` | 6 | `dlq_autopilot.py`, `nuzantara-sentinel.py`, `curiosity_loop.sh`, `nb_export_corpus.py`, `nb_generate_inventory.py`, `scar_query.py` | Executable source/tooling | Split by owner and validate before staging. |
| `apps/evaluator/nlm_deep_research/` | 16 | Notebook ID edits plus multimodal `.m4a` outputs | NLM source/config and generated media | Commit source/config only after notebook/profile verification; keep media out of git unless explicitly approved. |
| `research/coherence-corpus/` | 840 | `nb-intel-regulation`, `nb3-company-curated`, `nb4-tax-curated`, `nb5-property-curated`, `nb6-operations-curated` JSON files | Generated corpus | Do not commit blindly. Require privacy, size, retention, and artifact-storage decision. |
| `outputs/` | 51 | base64 chunks, `clients_all.csv`, `clients_master_clean.csv` | Local/private export output | Treat as private/local artifact by default. Do not commit raw client/export files. |
| `apps/mouth/src/content/articles/` | 5 | Immigration and tax MDX articles | Published content | Editorial review plus content build/lint before commit. |
| `docs/` | 2 | `AUTOMATIONS_REFERENCE.md`, `DOCS_INVENTORY.md` | Generated docs inventory | Regenerate from canonical command or commit with generator receipt. |
| `research/nb-health/` | 5 | dated health reports | Generated reports | Commit only if tracked daily audit trail is confirmed. |
| `research/regulatory/` | 5 | dated delta JSON files | Generated reports | Validate JSON and source receipt before commit. |
| `apps/bali-intel-scraper/` | 1 | `published_articles.json` | Content index/data | Commit with matching article batch only. |
| `apps/mata-garuda/` | 1 | `nlm_feeder.py` profile change | Source edit | Validate `nlm` profile availability before staging. |
| `apps/research/sota-social-2026-v1/` | 2 | KPI CSV and weekly report | Research output | Commit as dated research output only with traceable sources. |
| `research/operations/` | 2 | Drive/CRM and Fable5 notes | Ops research notes | Review audience and confidentiality before tracking. |
| `research/commercial/` | 1 | yield opportunities note | Commercial research | Review for client/private data before tracking. |
| `apps/crm-cell/war-room/` | 1 | `interactive_cli.sh` | New tooling | Validate shell script and privacy boundaries before staging. |
| `shared/` | 1 | `escalations_pro.jsonl` | Runtime log/output | Do not commit unless append-only audit-log policy is confirmed. |

## Owner-Scoped File Plan

| Owner/workstream | Paths | Plan | Acceptance criteria |
| --- | --- | --- | --- |
| Ops Sentinel/DLQ owner | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Treat staged edits as intentional code until proven otherwise. Extract only these staged diffs into a fresh ops worktree. | `python -m py_compile` passes for both files in the repo venv; sentinel cron-log enrichment and DLQ requeue/resurrection behavior are smoke-tested with fixtures. |
| Ops automation owner | `scripts/curiosity_loop.sh` | Review separately from Sentinel/DLQ because it changes runtime interpreter/fallback behavior. | `bash -n scripts/curiosity_loop.sh` passes; selected Python path exists on Pro runtime. |
| NLM pipeline owner | `apps/evaluator/nlm_deep_research/*.py`, `*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Verify NotebookLM IDs and `nlm` profile before committing. Keep source/config changes separate from audio/corpus outputs. | Notebook IDs match the intended current notebooks; an import or dry-run check passes; no raw NotebookLM/private corpus content is embedded in source. |
| NLM tooling owner | `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Review as source tooling, not with the generated corpus. | `python -m py_compile` passes; invocation and output destination are documented. |
| Corpus/artifact owner | `research/coherence-corpus/`, `apps/evaluator/nlm_deep_research/output/multimodal/` | Park outside git or move to artifact storage unless a sanitized, size-bounded tracking policy exists. | Owner confirms privacy and retention policy; large/raw files are not included in source commits by accident. |
| Client/export data owner | `outputs/` | Treat as local/private output. Remove from git candidate set or convert only sanitized samples into fixtures. | No raw client CSV or base64 export chunks are staged. |
| Editorial/content owner | `apps/mouth/src/content/articles/**`, `apps/bali-intel-scraper/data/published_articles.json` | Review MDX language variants, metadata, and published-article index as one content batch. | Frontmatter validates; sources are current; relevant `apps/mouth` lint/build/content check passes. |
| Docs automation owner | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Regenerate or keep only with a generator receipt. | Diff is reproducible from the documented generator. |
| Research owners | `apps/research/sota-social-2026-v1/`, `research/nb-health/`, `research/regulatory/`, `research/operations/`, `research/commercial/` | Split by dated report family and confidentiality class. | Markdown/CSV/JSON validates; each output has source receipts; private or client-sensitive material is excluded. |
| CRM cell owner | `apps/crm-cell/war-room/interactive_cli.sh` | Review as new CLI tooling. | `bash -n` passes; script does not expose raw CRM/WhatsApp data, secrets, or unsafe defaults. |
| Operator/rules owner | `.claude/rules/**` | Review interactively with the operator. | Rule changes are intentional and do not conflict with current Codex/Claude routing policy. |

## Safe Transfer Procedure

Use a fresh worktree per owner. Do not commit directly from
`/Users/nuzantara/Desktop/nuzantara` while it is behind `origin/main` and still
receiving concurrent edits.

```bash
cd /Users/nuzantara/Desktop/nuzantara
git status --short --branch

# Example: preserve the currently staged Sentinel/DLQ edits as a patch.
git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py \
  > /tmp/dirty-main-sentinel-dlq-20260614.patch

WT=$(python scripts/agent_start.py --lane ops --task-id dirty-main-sentinel-dlq | awk '/WORKTREE_READY/ {print $2}')
git -C "$WT" apply --index /tmp/dirty-main-sentinel-dlq-20260614.patch
```

For unstaged source edits, use `git diff -- <paths> > /tmp/<owner>.patch`.
For untracked files, copy only reviewed owner-approved paths. Never bulk-copy
`outputs/`, `research/coherence-corpus/`, or raw `.m4a` output directories.

## Recommended Commit Order

1. Sentinel/DLQ source patch:
   `fix(ops): restore sentinel dlq diagnostic loop`
2. NLM NotebookLM ID/profile source/config patch:
   `fix(nlm): refresh notebook routing ids`
3. NLM tooling scripts, if validated:
   `feat(nlm): add notebook corpus inventory tooling`
4. Editorial article batch and published article index:
   `content(mouth): add June immigration and tax updates`
5. Docs inventories, only with generator receipt:
   `docs(ops): refresh automation inventory`
6. Dated research reports, one generator family per commit:
   `docs(research): add June regulatory deltas`
7. Corpus/media/export artifacts:
   no source commit unless explicitly sanitized, size-bounded, and approved.

## Non-Goals

- Do not restart, unload, or edit `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not fix the separate `127` launchd failures in this dirty-main triage PR.
- Do not deploy.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  `secrets/*`.
- Do not reset, clean, stash-pop, or checkout over the shared main checkout.
- Do not use `--no-verify`, force push, or bypass branch protections.

## Completion Criteria For The Cleanup Owner

The dirty-main signal is resolved only when every path in the shared checkout is
one of:

- committed through an owner-scoped worktree or PR with validation;
- moved to artifact storage or parked outside git;
- ignored by an explicit policy change;
- intentionally left with a dated owner note and a next action.

Source edits, generated outputs, raw/private exports, and runtime logs must not
be mixed in the same commit.
