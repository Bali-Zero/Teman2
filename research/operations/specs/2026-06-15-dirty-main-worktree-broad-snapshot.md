# Dirty Main Worktree Broad Snapshot Triage - 2026-06-15

Date: 2026-06-15 00:37 WITA
Dispatch key: `repo-dirty-broad-snapshot-20260614`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_002302.md`
Source prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_002302.prompt.md`
Owner: next heavier ops agent with explicit shared-checkout cleanup authority
Decision deadline: 2026-06-15 12:00 WITA

## Scope

Resolve the broad dirty-state signal in the shared checkout
`/Users/nuzantara/Desktop/nuzantara` without editing, resetting, stashing, or
committing another operator's work from an unrelated isolated worktree.

This spec is the minimal safe remediation for the Spark-dispatched scout task.
The Codex/Spark LaunchAgent lifecycle is healthy; the actionable cluster is the
shared `main` checkout having a mixed index, unstaged source edits, generated
outputs, and new content artifacts that could be accidentally committed
together.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`.
- Peer check: Mini was unreachable during this overnight session, so cross-node
  git sync was not verified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260615_002549-spark-dispatch-20260615_002302-scout-repo-dirty-broad-snapshot-20260614-20260615_002549`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at:
  `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- Current shared-checkout staged changes:
  - `scripts/dlq_autopilot.py`: modified, staged, 55 inserted lines.
  - `scripts/nuzantara-sentinel.py`: modified, staged, 152 touched lines,
    mostly inserted lines.
- Current shared-checkout unstaged tracked changes span 21 files across
  `.claude/rules/`, `apps/evaluator/nlm_deep_research/`,
  `apps/mata-garuda/`, `apps/research/`, `docs/`, `scripts/`, and
  `shared/`.
- Current shared-checkout untracked clusters include:
  - `.claude/rules/cicatrix-superscar.md`
  - `apps/crm-cell/war-room/` (1 file)
  - `apps/evaluator/nlm_deep_research/output/multimodal/` (8 files)
  - five new `apps/mouth/src/content/articles/**` MDX files
  - `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`
  - `outputs/` (53 files)
  - `research/coherence-corpus/` (840 files)
  - `research/commercial/` (1 file)
  - five new `research/nb-health/2026-06-1*-health.md` files
  - two new `research/operations/2026-06-11-*.md` files
  - five new `research/regulatory/2026-06-1*-delta.json` files
  - `scripts/nb_export_corpus.py`
  - `scripts/nb_generate_inventory.py`
  - `scripts/scar_query.py`
- No path-specific `AGENTS.md` files were present under the worktree beyond the
  repository root `AGENTS.md`.

## Root-Cause Classification

Primary cluster: shared `main` checkout accumulation from multiple producers.

The staged index contains executable ops changes, while the unstaged and
untracked work mixes documentation updates, NLM pipeline edits, generated
NotebookLM/regulatory artifacts, content/article deliverables, and local output
exports. The risk is not a failed Spark loop; it is an accidental mixed commit
or branch switch from the shared checkout.

## Handoff Protocol For The Heavier Agent

1. Stay in `/Users/nuzantara/Desktop/nuzantara` only long enough to inspect and
   preserve evidence. Do not run `git reset`, `git checkout --`, `git clean`,
   or `git add -A`.
2. Capture immutable triage inputs before any staging changes:
   - `git status --short --branch`
   - `git diff --cached --name-status`
   - `git diff --cached --stat`
   - `git diff --name-status`
   - `git diff --stat`
   - `find outputs research/coherence-corpus apps/evaluator/nlm_deep_research/output/multimodal -type f | wc -l`
3. Review the staged scripts first. They are the highest-risk mixed-commit
   source because the index is already non-empty on `main`.
4. Produce a per-cluster decision table: keep and commit, keep but unstage,
   generated artifact to ignore/archive, or needs owner confirmation.
5. If a branch switch is required, first preserve the exact current index and
   worktree state with a named, non-destructive snapshot mechanism approved by
   the operator. Do not assume untracked research/output directories can be
   discarded.

## File Plan

| Cluster | Current state | Plan | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `scripts/dlq_autopilot.py` | Staged modification | Inspect first and either commit as a standalone ops fix or unstage for further validation. Never bundle with generated outputs. | DLQ/ops owner | Diff reviewed, no secrets, focused script validation or dry-run performed, commit message names the DLQ behavior. |
| `scripts/nuzantara-sentinel.py` | Staged modification | Inspect with `dlq_autopilot` only if they form one confirmed sentinel/DLQ root cause; otherwise split into separate commits. | Sentinel owner | Diff reviewed, launchd/sentinel dry-run or unit-level validation recorded, no plist/secrets changes bundled. |
| `.claude/rules/*` | Tracked edits plus one new superscar file | Treat as policy/scar documentation. Commit only after confirming it belongs to the current cicatrix rotation. | Ops memory/policy owner | Markdown reviewed, no private client names or raw OSINT, committed separately from executable scripts. |
| `apps/evaluator/nlm_deep_research/*` | Tracked NLM pipeline edits plus untracked multimodal output | Separate source edits from generated output. | NLM evaluator owner | Source changes validated with the smallest available pipeline/unit check; output artifacts either ignored, archived, or committed in a data-artifact commit with provenance. |
| `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged tracked modification | Validate with the NLM source edits if they are causally linked; otherwise split. | Mata Garuda owner | Worker import or focused test passes; no production daemon change is made. |
| `apps/mouth/src/content/articles/**` | Untracked MDX articles | Treat as content deliverables. Verify frontmatter/build impact before commit. | Mouth/content owner | Frontmatter valid, article route build/lint passes, committed separately from ops scripts and generated corpora. |
| `apps/bali-intel-scraper/data/published_articles.json` | Unstaged tracked modification | Pair only with the matching article MDX files if it is the article index update. | Content/scraper owner | JSON valid and matches article slugs. |
| `docs/AUTOMATIONS_REFERENCE.md` and `docs/DOCS_INVENTORY.md` | Unstaged tracked modifications | Treat as generated or inventory docs until proven manual. | Docs owner | Regeneration command or manual rationale recorded; commit separate from code. |
| `outputs/` | Untracked output export, 53 files | Do not commit until classified as deliverable vs local scratch. | Producing agent owner | If scratch, add/confirm ignore rule in a separate reviewed change; if deliverable, move to an approved artifact path with provenance. |
| `research/coherence-corpus/` | Untracked corpus export, 840 files | Do not commit by default. This is likely generated corpus material and may contain derived client/corpus data. | Research/NB owner | Provenance, privacy review, and storage policy documented before any commit. |
| `research/nb-health/*.md` and `research/regulatory/*.json` | Untracked dated generated reports | Batch by generator/date only after validation. | NB/regulatory owner | JSON/Markdown valid, no duplicate older artifact, commit message names generator and date range. |
| `research/operations/2026-06-11-*.md` and `research/commercial/2026-W24-yield-opportunities.md` | Untracked research docs | Review as human-facing research deliverables. | Ops/research owner | No raw private data, citations/provenance present, committed separately from generated machine output. |
| `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `scripts/scar_query.py` | Untracked scripts | Treat as new executable tooling, not generated artifacts. | Script owner | Shebang/venv discipline, type hints where applicable, focused dry-run or help output recorded. |

## Suggested Commit Order

1. Staged ops scripts only, if validated:
   `fix(ops): harden sentinel and dlq autopilot`
2. NLM evaluator source edits only, if validated:
   `fix(nlm): align deep research pipeline monitors`
3. Content article MDX plus matching published article index:
   `feat(articles): add june immigration and tax articles`
4. Policy/scar documentation:
   `docs(ops): rotate cicatrix scars`
5. Research/regulatory/NB generated reports by generator/date:
   `docs(research): add june notebook and regulatory reports`
6. Generated corpus/output artifacts only if they pass privacy/provenance review:
   `data(research): add curated coherence corpus export`

Do not mix steps. If a cluster cannot be validated quickly, leave it unstaged
with an explicit owner note rather than bundling it into the nearest commit.

## Non-Goals

- Do not restart, unload, or edit `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not push directly to `main`.
- Do not use `--no-verify`, force push, `git reset --hard`, `git checkout --`,
  or `git clean`.
- Do not modify `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`,
  `secrets/*`, or `backend/app/dependencies.py`.
- Do not copy WhatsApp/OSINT data between machines or into this repository.
- Do not infer that `outputs/` or `research/coherence-corpus/` are safe to
  commit just because they are present in the checkout.

## Validation Ladder

Run the narrowest validation for each retained cluster:

- Staged ops scripts: import/help/dry-run checks using the repository virtualenv;
  inspect any launchd-facing paths without loading or unloading agents.
- Python source edits: focused unit tests or module imports with `PYTHONPATH=.`.
- Article/content edits: JSON validation for `published_articles.json` plus the
  smallest `apps/mouth` lint/build check available.
- Generated JSON artifacts: `python -m json.tool` or equivalent parser checks.
- Markdown docs: `git diff --check` and privacy/provenance review.
- Corpus/output directories: provenance and privacy review before any commit.

## Stop Conditions

Stop and write a blocked status if any of these are true:

- The shared checkout changes while the heavier agent is triaging and ownership
  can no longer be inferred.
- The staged scripts contain secrets, destructive operations, or production
  deployment behavior.
- Generated corpus/output files appear to contain raw private or client data.
- The required owner for a cluster is unknown and validation cannot prove it is
  safe.

## Next Step

Dispatch a heavier ops agent with this spec and the current Spark prompt/report.
Its first deliverable should be a reviewed keep/drop/commit table, not a commit.
Only after that table is complete should it stage explicit file paths and open
separate PRs or commits for each validated cluster.
