# Main Dirty Tree Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `main-dirty-tree-triage-20260614`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_085012.md`
Owner: operator or checkout owner for `/Users/nuzantara/Desktop/nuzantara`
Decision deadline: 2026-06-14 18:00 WITA

## Scope

Resolve the actionable dirty-main signal in `/Users/nuzantara/Desktop/nuzantara`
without cleaning, stashing, resetting, or branch-switching the shared checkout
from this overnight worktree.

This spec is deliberately decision-only. The shared checkout contains local
commits, staged executable changes, unstaged tracked changes, and untracked
content/artifacts from multiple workstreams. The safe remediation is to classify
the state, identify stale duplicates versus real local work, and hand off an
ordered preserve/drop/commit plan.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`; peer `mini` unreachable, so peer
  git sync is unverified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_085119-spark-dispatch-20260614_085012-scout-main-dirty-tree-triage-20260614-20260614_085119`.
- Root `AGENTS.md` was read. No path-specific `AGENTS.md` files exist under
  `apps/backend-rag/`, `scripts/`, or `apps/backend-rag/backend/llm/`.
- Spark lifecycle is not the actionable root cause:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1025`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 201`, `last exit code = 0`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 130`, `last exit code = 0`.
- `launchd_bad_exits.json` was fresh at `2026-06-14 08:58:12`; filtering
  `.bad[].label` for `codex` produced no matches.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` reports:
  - `## main...origin/main [ahead 2, behind 170]`
  - local-only commits:
    - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
    - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
  - 46 porcelain entries and 914 untracked files.
  - staged changes in `scripts/dlq_autopilot.py` and
    `scripts/nuzantara-sentinel.py`.
  - large untracked generated-looking trees:
    - `research/coherence-corpus/`: 840 JSON files across 5 notebook corpus
      directories, 44M total.
    - `apps/evaluator/nlm_deep_research/output/multimodal/`: 47M.
    - `outputs/`: 40M, including client CSV/base64 chunk outputs. Do not open
      or copy these outside the Pro-local checkout without an explicit owner
      decision.

## Root-Cause Classification

Primary cluster: stale/diverged shared main checkout plus mixed local outputs.

The LaunchAgent evidence does not support a Spark repair. The shared checkout is
the actionable surface. It is both dirty and stale relative to `origin/main`.
Several dirty paths are not new local work; they are upstream content that only
appears dirty because the local main checkout is 170 commits behind.

Confirmed stale duplicates:

- Staged executable changes:
  - `git diff --cached origin/main --quiet -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`
    returned `0`.
  - Interpretation: the staged W70 DLQ/sentinel changes already match
    `origin/main`; they should not be recommitted from stale main.
- Unstaged NLM evaluator changes:
  - `git diff origin/main --quiet -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`
    returned `0`.
  - Interpretation: this block already matches `origin/main`; it is not an
    independent local workstream.
- Article files tracked upstream:
  - `apps/mouth/src/content/articles/immigration/indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists.mdx`
    matches `origin/main` byte-for-byte.
  - `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.id.mdx`
    matches `origin/main` byte-for-byte.
  - `apps/mouth/src/content/articles/tax/indonesia-umkm-tax-reforms-pp-20-2026.it.mdx`
    matches `origin/main` byte-for-byte.

Local work needing owner review before discard:

- Two article translations differ from `origin/main` and need editorial review:
  - `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.id.mdx`
    differs by 19 insertions and 22 deletions.
  - `apps/mouth/src/content/articles/immigration/indonesia-scraps-fast-track-residency-permits-for-foreigners-minister-says.it.mdx`
    differs by 24 insertions and 29 deletions.
- Six tracked files still differ from `origin/main` and are not covered by the
  stale-duplicate proof:
  - `apps/bali-intel-scraper/data/published_articles.json`
  - `apps/research/sota-social-2026-v1/kpi_timeline.csv`
  - `docs/AUTOMATIONS_REFERENCE.md`
  - `docs/DOCS_INVENTORY.md`
  - `scripts/curiosity_loop.sh`
  - `shared/escalations_pro.jsonl`
- New small research/scripts workstreams not found on `origin/main`:
  - `scripts/nb_export_corpus.py`
  - `scripts/nb_generate_inventory.py`
  - `research/nb-health/2026-06-10-health.md` through
    `research/nb-health/2026-06-14-health.md`
  - `research/regulatory/2026-06-10-delta.json` through
    `research/regulatory/2026-06-14-delta.json`
  - `research/commercial/2026-W24-yield-opportunities.md`
  - `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`
  - `research/operations/2026-06-11-drive-crm-unified-client-folders-design.md`
  - `research/operations/2026-06-11-fable5-extra-task-allocation.md`

Generated/local-only artifact candidates:

- `outputs/` should be treated as sensitive local output until proven otherwise.
- `research/coherence-corpus/` looks like a generated notebook export corpus and
  should not be committed wholesale without an owner proving the corpus belongs
  in git.
- `apps/evaluator/nlm_deep_research/output/multimodal/nb6/audio/20260611_nb6.m4a`
  is a binary/media artifact and should be parked outside git or moved to an
  artifact store unless a specific workflow expects it in the repository.

## File Plan

| Path or group | Current state in main | Plan | Owner | Acceptance criteria |
| --- | --- | --- | --- | --- |
| `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged modifications, already equal to `origin/main` | Do not recommit. After preserving real local work, unstage by updating main from `origin/main` or reset only these paths with explicit operator approval. | Ops/sentinel owner | `git diff --cached origin/main --quiet -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py` remains `0`; focused W70 tests pass from a clean updated checkout. |
| `apps/evaluator/nlm_deep_research/`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged modifications, already equal to `origin/main` | Do not recommit. Treat as stale-main noise. | NLM evaluator owner | `git diff origin/main --quiet -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` remains `0`. |
| Byte-identical untracked article files | Untracked because local main is stale | Do not preserve separately; they are already upstream. | Editorial owner | `git show origin/main:<path> | cmp -s - <path>` returns success for each file before discard. |
| Two differing article translations | Untracked and differ from `origin/main` | Review and either commit as a small editorial patch on a fresh branch, or intentionally discard after editorial signoff. | Editorial owner | Compare against `origin/main`, render/build affected article pages, and confirm no empty-slug files are introduced. |
| `published_articles.json`, docs inventory/reference, `curiosity_loop.sh`, `kpi_timeline.csv`, `shared/escalations_pro.jsonl` | Tracked unstaged differences versus `origin/main` | Split into content index, docs generated refresh, script behavior, KPI data, and escalation-log workstreams. Do not bundle them together. | Respective content/docs/ops owners | Each group has a separate diff review and the smallest relevant validation before commit. |
| NB health, regulatory deltas, commercial report, weekly report, NB export scripts | Untracked small files | Preserve as a research/NB workstream if still relevant. Commit only after JSON validation and script lint/test. | Research/NB owner | JSON files parse; scripts pass focused lint/import; reports have owner and date provenance. |
| `outputs/`, `research/coherence-corpus/`, multimodal audio output | Large untracked generated/local artifacts | Do not commit wholesale. Move to ignored artifact storage or add narrow ignore rules only after owner confirms these are reproducible outputs. | Ops/research owner | Artifact retention decision recorded; no raw client/output material is pushed to git accidentally. |

## Suggested Operator Sequence

1. Preserve the two local commits before any destructive cleanup:
   `git branch preserve/main-local-articles-20260614 main`.
2. Preserve non-duplicate local edits into topic branches or patch files from the
   shared checkout, grouped by the file plan above.
3. For stale duplicates, verify equality to `origin/main` again before discard.
4. Only after preservation, realign the shared checkout to current `origin/main`
   using the operator's normal protected workflow.
5. Re-run `git status --short --branch` and ensure the main checkout is clean or
   contains only consciously parked local work.

## Validation Commands

Run these from `/Users/nuzantara/Desktop/nuzantara` before any cleanup:

```bash
git status --short --branch
git log --oneline origin/main..main
git diff --cached origin/main --quiet -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
git diff origin/main --quiet -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py
git ls-files --others --exclude-standard | wc -l
```

For W70 sentinel/DLQ validation from a clean updated checkout:

```bash
source /Users/nuzantara/Desktop/nuzantara/.venv/bin/activate
PYTHONPATH=. python -m pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_escalations_s3.py -q
```

For backend smoke after the shared checkout is clean:

```bash
cd apps/backend-rag
source .venv/bin/activate
python -c "from backend.app.dependencies import get_current_user; print('OK')"
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
```

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean the shared checkout from this unrelated isolated worktree.
- Do not use `--no-verify`, force push, or reset the shared checkout.
- Do not open or copy local `outputs/` client artifacts for this triage.

## Next Step

The immediate safe action is an operator-owned preserve pass, not a blind reset:
branch or patch the local-only article/content/research workstreams, confirm the
stale duplicate groups still equal `origin/main`, then realign the shared main
checkout. Spark itself should be left alone.
