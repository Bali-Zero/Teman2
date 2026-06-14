# Dirty Main NLM/WR2/Codex Sentinel Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-main-nlm-wr2-codex-sentinel`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_231123.md`
Owner: Ops handoff owner for shared-checkout dirty-state triage
Decision deadline: 2026-06-15 12:00 WITA

## Scope

Resolve the broad dirty checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without changing Spark LaunchAgents, cleaning the shared checkout from this
isolated overnight branch, or mixing generated outputs with source edits.

This spec is deliberately decision-only. The live evidence supports a dirty
shared-checkout handoff, not a Spark lifecycle repair.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer check: `mini` was unreachable during the overnight session, so peer git
  sync was not verified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_233423-spark-dispatch-20260614_231123-scout-dirty-main-nlm-wr2-codex-sentinel-20260614_233424`.
- Root/path instructions read: root `AGENTS.md`; no path-specific `AGENTS.md`
  files exist under `apps/backend-rag/`, `scripts/`, or
  `apps/backend-rag/backend/llm/`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is at `e2b355f45`.
- `git status --porcelain=v1` in the shared checkout shows:
  - 2 staged modified files.
  - 19 unstaged modified files.
  - 25 untracked top-level status entries.
- Staged files:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
- Untracked file counts by group from `git ls-files --others --exclude-standard`:
  - `research/coherence-corpus`: 840 files.
  - `outputs`: 51 files, including client CSV/base64 chunk artifacts.
  - `apps/mouth`: 5 article files.
  - `research/nb-health`: 5 dated health reports.
  - `research/regulatory`: 5 dated delta JSON files.
  - `apps/evaluator`: 4 git-visible multimodal output files.
  - `research/operations`: 2 notes/specs.
  - `scripts`: 2 notebook export/inventory scripts.
  - `apps/crm-cell`: 1 war-room script.
  - `apps/research`: 1 weekly report.
  - `research/commercial`: 1 research file.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, active PID, and last
    exit code `(never exited)`.
  - `com.nuzantara.codex-spark-alarm`: StartInterval timer, `state = not
    running`, last exit `0`, interval `120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: StartInterval timer, `state = not
    running`, last exit `0`, interval `180 seconds`.
  - `com.nuzantara.codex-autofix-ci`,
    `com.nuzantara.codex-coverage-improver`,
    `com.nuzantara.codex-openclaw-analysis`, and
    `com.nuzantara.codex-research-actor` are idle with last exit `0`.

## Root-Cause Classification

Primary cluster: shared-checkout work from multiple workstreams was left in
`/Users/nuzantara/Desktop/nuzantara`.

The dirty surface spans executable Sentinel/DLQ changes, NLM NotebookLM pipeline
configuration, generated research/report outputs, published content, local
client/export artifacts, and escalation/runtime logs. These should not be
committed as one unit and should not be cleaned by an unrelated overnight branch.

## File Plan

| Path or group | Current state | Kind | Owner/workstream | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- | --- |
| `scripts/dlq_autopilot.py` | Staged modification | Source edit | Ops/Sentinel DLQ owner | Review and validate as a dedicated DLQ requeue feature. Commit separately from all generated artifacts. | `python -m py_compile scripts/dlq_autopilot.py` passes in the repo venv; CLI behavior for `clear` and new `requeue` mode is documented or smoke-tested against a disposable DLQ fixture. |
| `scripts/nuzantara-sentinel.py` | Staged modification | Source edit | Ops/Sentinel owner | Review as the W70 blind-loop and cron-log enrichment fix. Commit separately with focused tests or an explicit smoke receipt. | `python -m py_compile scripts/nuzantara-sentinel.py` passes; cron-log enrichment is exercised with a temporary log fixture; DLQ terminal resurrection cannot clear unrelated jobs. |
| `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json` | Unstaged modifications | Source/config edits | NLM research pipeline owner | Review NotebookLM ID/profile changes and config edits as one NLM pipeline commit only after proving the target notebooks and `nlm` profile are correct. | `git diff` confirms only intended notebook IDs/configs changed; smallest available NLM pipeline dry-run or import check passes; no raw NotebookLM/private corpus content is embedded in code. |
| `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged modification | Source edit | Mata Garuda/NLM feeder owner | Decide whether `--profile default` should replace `--profile zero`; commit with the NLM profile change only if current auth supports it. | A live `nlm` profile check or mocked worker command test proves the chosen profile is available on Pro. |
| `scripts/curiosity_loop.sh` | Unstaged modification | Source edit | Ops automation owner | Validate the Python 3.11 pin and backend venv fallback on Pro before commit. | `bash -n scripts/curiosity_loop.sh` passes and the selected interpreter exists on the runtime machine. |
| `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md` | Unstaged modifications | Generated/docs inventory | Docs automation owner | Regenerate from the canonical inventory command or commit only with generator receipt. | Diff is reproducible from the documented generator; no unrelated manual edits are mixed in. |
| `apps/bali-intel-scraper/data/published_articles.json`, `apps/mouth/src/content/articles/**/*.mdx` | Modified/untracked | Published content/index | Editorial/content owner | Review article source, language variants, metadata, and index update together. Commit only after content validation. | Article frontmatter is valid; referenced sources are current; `apps/mouth` content build or lint passes for the touched articles. |
| `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md` | Modified/untracked | Research output | SOTA social research owner | Keep as a dated research-output commit if the report was intentionally generated; otherwise park outside git. | CSV/report values are traceable to source data and no temporary local notes are included. |
| `research/nb-health/*.md`, `research/regulatory/*-delta.json` | Untracked | Generated dated reports | NB health/regulatory watcher owner | Commit only if these reports are part of the tracked daily audit trail; otherwise move to artifact storage or ignore policy. | Each report has a generator/source receipt and dated filename; JSON validates. |
| `research/coherence-corpus/` | Untracked, 840 files | Generated corpus | Coherence/NLM corpus owner | Do not commit until privacy, size, and retention policy are checked. If keepable, split into manifest plus sampled corpus or artifact storage. | Owner confirms corpus is sanitized and intended for git, or files are parked outside the repo before main cleanup. |
| `outputs/` | Untracked, 51 files | Local/private export output | Ops/client-data owner | Treat as local artifact by default. Do not commit client CSV or base64 chunks unless explicitly converted into sanitized fixtures. | Raw client/export data is removed from git candidate set or replaced with a sanitized fixture plus README. |
| `apps/evaluator/nlm_deep_research/output/multimodal/` | Untracked media outputs | Generated media | NLM multimodal owner | Keep outside git unless the media files are required reviewed artifacts. | Artifact destination is documented; git commit includes only intentional small manifests, not raw media by default. |
| `apps/crm-cell/war-room/interactive_cli.sh` | Untracked | Source/tooling | CRM cell owner | Review as a new tool and validate it in an isolated worktree before staging. | `bash -n` passes; script does not expose raw CRM/WhatsApp data or secrets. |
| `research/operations/*.md`, `research/commercial/` | Untracked | Research/ops notes | Ops/research owner | Review for audience, confidentiality, and whether each note belongs in tracked research. | Notes contain no raw private client data and have clear owner/date/context. |
| `shared/escalations_pro.jsonl` | Unstaged modification | Runtime log/output | Ops escalation owner | Do not commit as a source change unless this file is intentionally tracked as an audit log. Prefer export/rotation policy. | Owner confirms append-only log policy; JSONL validates; no secret or raw client content is introduced. |
| `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Untracked | Source scripts | NLM tooling owner | Review with NLM source changes, not with generated corpus output. | `python -m py_compile` passes and scripts have a documented invocation path. |

## Safe Transfer Procedure

Do not commit from `/Users/nuzantara/Desktop/nuzantara` directly. Move one
owner-scoped subset at a time into a fresh agent worktree:

```bash
cd /Users/nuzantara/Desktop/nuzantara
git status --short

# Example: capture only the staged Sentinel/DLQ source edits.
git diff --cached -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py > /tmp/dirty-main-sentinel-w70.patch

# Create the destination worktree from the clean repo state, then apply the
# selected patch there for review, validation, commit, and PR.
WT=$(python scripts/agent_start.py --lane ops --task-id dirty-main-sentinel-w70 | awk '/WORKTREE_READY/ {print $2}')
git -C "$WT" apply --index /tmp/dirty-main-sentinel-w70.patch
```

For unstaged owner subsets, capture with `git diff -- <paths>`. For untracked
files, copy only the reviewed owner-approved paths into the worktree. Do not
bulk-copy `outputs/` or raw corpus/client artifacts.

## Recommended Commit Order

1. Ops Sentinel/DLQ source patch:
   `fix(ops): restore sentinel dlq diagnostic loop`
2. NLM NotebookLM pipeline/profile source/config changes:
   `fix(nlm): refresh notebook pipeline routing`
3. NLM tooling scripts, if validated:
   `feat(nlm): add notebook corpus inventory tooling`
4. Editorial published-article content and index:
   `content(mouth): add June immigration and tax updates`
5. Generated reports/docs inventories, one generator family per commit:
   `docs(ops): refresh automation inventory`
6. Local/generated artifacts cleanup or artifact-storage handoff:
   no source commit unless explicitly sanitized and approved.

## Non-Goals

- Do not restart, unload, edit, or reclassify `com.nuzantara.codex-spark-*`
  LaunchAgents.
- Do not run production deploys.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  `secrets/*`.
- Do not reset, stash-pop, checkout over, or delete files in the shared checkout
  from this overnight branch.
- Do not use `--no-verify`, force push, or bypass branch protections.

## Completion Criteria For The Heavier Owner

The dirty-main signal is resolved when:

- Every dirty path in `/Users/nuzantara/Desktop/nuzantara` is either committed
  through an owner-scoped worktree/PR, parked outside git as a local artifact, or
  intentionally left with a dated owner note.
- Source edits and generated outputs are not mixed in the same commit.
- Private/client outputs under `outputs/` and large generated corpus/media
  directories are not accidentally committed.
- The shared checkout can be brought back to a clean or explicitly documented
  state without losing another agent's work.
