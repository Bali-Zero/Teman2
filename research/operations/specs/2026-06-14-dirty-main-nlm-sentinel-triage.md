# Dirty Main NLM/Sentinel Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-main-nlm-sentinel-triage`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_134451.md`
Overnight branch: `codex-overnight/spark-alarm-20260614_134632-spark-dispatch-20260614_134451-scout-dirty-main-nlm-sentinel-triage-20260614_134632`
Decision owner: main-checkout operator plus NLM, content, and sentinel owners

## Scope

Classify the actionable Spark signal from `/Users/nuzantara/Desktop/nuzantara`
and define the smallest safe ownership plan. This spec does not clean, reset,
unstage, or otherwise mutate the shared main checkout.

The verified actionable cluster is worktree hygiene. Spark/Codex lifecycle is
healthy under the provided launchd semantics, so there is no Spark LaunchAgent
repair in scope.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`. Mini peer was unreachable during
  the session-start SSH sync check, so cross-machine sync is unverified.
- Root `AGENTS.md` was read. Requested path-specific files were checked and are
  absent in this checkout:
  - `apps/backend-rag/AGENTS.md`
  - `scripts/AGENTS.md`
  - `apps/backend-rag/backend/llm/AGENTS.md`
- Isolated overnight branch is clean and based on current `origin/main`
  (`84ae8edae docs(research): Mythos M3 follow-up - P0-6 kitas page is an
  orphan (not live) (#1425)`).
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45 feat(articles): add translations for
  indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`.
- Shared checkout divergence after `git fetch origin`:
  - `git rev-list --left-right --count HEAD...origin/main` returned `2 173`.
  - Local-only commits:
    - `e2b355f45 feat(articles): add translations for
      indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
    - `c6d6b85fe feat(articles): add translations for
      ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Codex Spark lifecycle is not actionable:
  - `launchctl list` shows `2066 0 com.nuzantara.codex-spark-loop`.
  - `launchctl print gui/501/com.nuzantara.codex-spark-loop` shows
    `state = running`, `pid = 2066`, and `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm` and
    `com.nuzantara.codex-spark-harvester` show `- 0` timer-idle semantics.
- Spark state is fresh enough to reject the stale-state hypothesis:
  - `codex_com_nuzantara_codex_spark_loop.state.json`: 2026-06-14 13:45:31
  - `codex_com_nuzantara_codex_spark_harvester.state.json`: 2026-06-14 13:46:31
  - `codex_com_nuzantara_codex_spark_alarm.state.json`: 2026-06-14 13:46:32
- Shared checkout dirty summary:
  - 19 unstaged tracked files.
  - 2 staged tracked files.
  - 914 untracked files.
  - Large untracked artifact directories: `outputs/` 40M,
    `research/coherence-corpus/` 44M,
    `apps/evaluator/nlm_deep_research/output/multimodal/` 47M.

## Root-Cause Classification

Primary cluster: shared `main` checkout has become a mixed holding area while
also lagging `origin/main` by 173 commits and carrying 2 local-only content
commits.

Several dirty files are not new work; they are duplicate local copies of changes
already merged into `origin/main`. A direct fast-forward is still unsafe because
the checkout also contains local-only article commits, generated artifacts,
runtime logs, and untracked deliverables.

## Ownership Buckets

| Bucket | Live paths | Current state | Upstream relation | Owner | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- | --- | --- |
| Repository/head hygiene | `main` branch in `/Users/nuzantara/Desktop/nuzantara` | `2` commits ahead, `173` behind `origin/main` | Diverged | Main-checkout operator | Preserve the two local article commits on a named branch or PR before any reset/sync. Do not run destructive cleanup from an unrelated worktree. | `git status --short --branch` shows no ambiguous staged/untracked work; local article commits are reachable from a named branch or PR; main can then be resynced intentionally. |
| NLM research pipeline | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged modified files updating NotebookLM IDs and `nlm --profile default` | Byte-equivalent to current `origin/main` for these paths | NLM research owner | Treat as upstream duplicate, not a new local commit. After local-only article commits are preserved, resync main or drop the duplicate file states by explicit owner action. | `git diff --exit-code origin/main -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` remains clean before cleanup. |
| NLM/ops runtime wrapper | `scripts/curiosity_loop.sh` | Unstaged local Python 3.11 pin | Still differs from `origin/main` | NLM/ops owner | Review separately from notebook-ID churn. Keep only if the pyenv 3.11 path or backend venv fallback is required on Pro LaunchAgent runtime. | `bash -n scripts/curiosity_loop.sh`; runtime owner verifies the selected Python is 3.11 and the job has a fresh successful state before commit. |
| Sentinel/DLQ scripts | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged modifications | Staged content is byte-equivalent to current `origin/main` for both files | Sentinel owner | Do not commit these staged changes as new work. They are already upstream via the W70 sentinel/DLQ fixes. Unstage/drop only after preserving unrelated local work. | `git diff --cached --exit-code origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py` passes; if further sentinel edits are made, run `PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_sentinel_v33.py -q`. |
| Published articles and article index | `apps/bali-intel-scraper/data/published_articles.json`, `apps/mouth/src/content/articles/**` | Local-only article commits, modified published index, 5 untracked article files | Conflicts with newer upstream content reshaping and deletions | Content/publishing owner | Branch the local article work first. Reconcile against current `origin/main` article taxonomy before adding translations or index updates. Do not mix article metadata with runtime generated files. | Local commits are cherry-picked or PR'd against current `origin/main`; content build/tests for articles pass; no hidden slug files such as `apps/mouth/src/content/articles/immigration/.mdx` are introduced. |
| Generated outputs and research deltas | `outputs/`, `research/coherence-corpus/`, `research/regulatory/*.json`, `research/nb-health/*.md`, `apps/evaluator/nlm_deep_research/output/multimodal/` | 914 untracked files; large CSV/base64/audio/JSON/health artifacts | Mostly untracked runtime output | NLM/corpus owner | Keep out of source commits unless a manifest explicitly requires them. Archive or move to the intended artifact store after owner review; consider `.gitignore` only if these are repeatedly regenerated in the repo root. | Owner classifies each directory as source, fixture, or artifact; source/fixture additions have manifests and tests; artifacts are archived outside git or ignored deliberately. |
| Generated docs and runtime ledgers | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl`, `apps/research/sota-social-2026-v1/kpi_timeline.csv` | Unstaged generated/reference/ledger changes | Partly expected output, not a single feature | Ops docs owner | Re-run the owning generators if these are desired. Do not commit append-only runtime ledger growth with unrelated doc regeneration. | Generator command is recorded; regenerated docs are committed separately from `shared/escalations_pro.jsonl`; ledger retention policy is explicit if committed. |
| CRM war-room | `apps/crm-cell/war-room/interactive_cli.sh` | Untracked 4K script | Local-only | CRM/cell owner | Inspect as a separate feature or tooling handoff. Do not fold into NLM/sentinel/content cleanup. | Owner validates shell syntax and intended package boundary; commit includes a README or integration reference if this is meant to stay. |

## Recommended Commit Order For Main Owner

1. Preserve local-only article commits:
   `git switch -c chore/preserve-main-article-translations-2026-06-14`
   or create an equivalent worktree/branch from the current `main` HEAD.
2. Reconcile article translations and `published_articles.json` against current
   `origin/main`; commit content only after content validation.
3. Drop or unstage duplicate upstream sentinel/DLQ and NLM NotebookLM changes
   only after step 1 is complete and the owner has confirmed the branch is
   recoverable.
4. Decide whether `scripts/curiosity_loop.sh` is a valid Pro runtime fix; commit
   it separately if validated.
5. Classify generated artifacts and runtime ledgers. Commit only source/fixture
   material; archive or ignore pure outputs.
6. Inspect `apps/crm-cell/war-room/interactive_cli.sh` as a separate CRM tooling
   branch if it is still needed.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`.
- Do not reset, clean, stash, or unstage the shared main checkout from this
  overnight worktree.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not fold NLM, sentinel, content, generated output, and CRM work into one
  catch-all commit.

## Verification Commands Used

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short
git -C /Users/nuzantara/Desktop/nuzantara rev-list --left-right --count HEAD...origin/main
git -C /Users/nuzantara/Desktop/nuzantara log --oneline origin/main..HEAD
git -C /Users/nuzantara/Desktop/nuzantara diff --exit-code origin/main -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py
git -C /Users/nuzantara/Desktop/nuzantara diff --cached --exit-code origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
launchctl list | rg 'codex-spark|codex-overnight|codex-autofix|codex-research|codex-coverage|codex-openclaw'
launchctl print gui/$(id -u)/com.nuzantara.codex-spark-loop
find /Users/nuzantara/.agent/decisions/state -maxdepth 1 -type f -print0 | xargs -0 stat -f '%Sm %N' -t '%Y-%m-%d %H:%M:%S'
```

## Next Step

Assign a main-checkout owner to preserve the two local article commits first.
Until those commits and untracked artifacts are assigned, the correct action is
handoff and branch preservation, not Spark repair and not bulk cleanup.
