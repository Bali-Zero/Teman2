# Main Dirty NLM/Regulatory Bundle Triage - 2026-06-14

Date: 2026-06-14
Dispatch key: `main-dirty-nlm-regulatory-bundle`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_141255.md`
Intervention branch: `codex-overnight/spark-alarm-20260614_141404-spark-dispatch-20260614_141255-scout-main-dirty-nlm-regulatory-bundle-20260614_141405`
Owner: next heavier agent or human operator assigned to reconcile the shared main checkout.

## Scope

Define the safe reconciliation plan for `/Users/nuzantara/Desktop/nuzantara`.
This spec is decision-only. The shared checkout contains mixed staged,
unstaged, and untracked work, so this intervention does not clean, reset, or
commit those files from an unrelated worktree.

No production deploy is in scope.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Session-start peer check: `mini` was unreachable, so cross-machine git sync
  was not verified during this intervention.
- Spark lifecycle is not the actionable failure:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 2066`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- Spark state files under `/Users/nuzantara/.agent/decisions/state` were fresh
  around 14:13-14:16 WITA on 2026-06-14.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` and reports
  `ahead 2, behind 173` relative to `origin/main`.
- The two local commits ahead of `origin/main` are article translation commits:
  - `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`
  - `c6d6b85fe feat(articles): add translations for ojk-puts-8-online-lenders-on-watchlist-license-revocation-looms`
- Two files are staged in the shared checkout:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
- Comparing the staged script index against `origin/main` shows no script delta.
  The staged edits are already represented on `origin/main`; the only related
  difference is that the stale local index lacks
  `scripts/tests/test_sentinel_w70_resurrect_enrich.py`, which exists on
  `origin/main`.
- Unstaged modified files against the stale local `HEAD` include NLM pipeline
  files, Mata Garuda feeder files, generated docs inventories, article data,
  `scripts/curiosity_loop.sh`, and `shared/escalations_pro.jsonl`.
- The shared checkout has 914 untracked paths. A batch comparison found 5 of
  those paths already tracked on `origin/main`; 909 are still new relative to
  `origin/main`.
- Largest untracked/generated clusters:
  - `research/coherence-corpus`: 840 paths, about 44M.
  - `outputs`: 51 paths, about 40M.
  - `apps/evaluator/nlm_deep_research/output`: about 51M.
  - `research/regulatory`: 5 delta JSON files.
  - `research/nb-health`: 5 health report markdown files.
- `git diff --check` in the shared checkout fails on
  `apps/research/sota-social-2026-v1/kpi_timeline.csv` because the new row has
  trailing whitespace.

## Root-Cause Classification

Primary cluster: stale and divergent shared main checkout with mixed generated
artifacts.

Spark itself is healthy enough for this snapshot. The actionable issue is that a
dirty shared checkout is 173 commits behind `origin/main`, has 2 local commits
not on origin, and contains a large mixed bundle of generated research/content
outputs plus staged script changes that appear duplicated by current origin.

This state is unsafe for a direct commit, stash, reset, or deploy decision
because the local index is not a trustworthy review base.

## Workstream Plan

| Workstream | Current state | Plan | Acceptance criteria |
| --- | --- | --- | --- |
| Git base preservation | `main` is `ahead 2, behind 173`. | Preserve the two local article commits on a named safety branch or PR before any base reconciliation. | Both local commits are reachable from a branch or remote ref; `git log origin/main..HEAD` no longer contains unprotected work before any reset/rebase/fast-forward operation. |
| Staged sentinel/DLQ scripts | Staged against stale `HEAD`; script content matches `origin/main`. | Do not commit these staged script entries from the stale index. After preserving local commits, compare against `origin/main` and drop the index entries if still duplicate. | `git diff --cached origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py` is empty before dropping; W70 tests remain present from `origin/main`. |
| W70 validation | Origin already has `scripts/tests/test_sentinel_w70_resurrect_enrich.py`. | If touching the sentinel/DLQ scripts again, validate the existing W70 coverage instead of relying on staged code shape. | `PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_escalations_s3.py -q` passes in the reconciled checkout. |
| Article content | 5 article MDX paths are untracked locally but already tracked on `origin/main`; two local ahead commits add other translation files. | Split published article metadata from MDX content. Preserve local ahead commits first, then compare each untracked/stale article file with origin before deciding keep/drop. | No duplicate article MDX is re-added; article metadata in `apps/bali-intel-scraper/data/published_articles.json` matches the retained content set. |
| NLM pipeline files | Multiple NLM pipeline/config files are modified against stale `HEAD`. | Re-review only after syncing the base. Many of these changes may collapse against `origin/main`. | On the reconciled base, `git diff -- apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` shows only intentional new deltas, each with a focused test or dry-run. |
| Regulatory and NB reports | `research/regulatory/*.json` and `research/nb-health/*.md` are untracked generated outputs. | Commit only curated deltas/reports with a manifest and source timestamp. Park bulk generated material outside the code commit if it is only transient evidence. | JSON validates with `jq`; reports identify source notebooks/dates; no raw private data is included. |
| Coherence corpus | 840 untracked JSON files under `research/coherence-corpus`. | Treat as generated corpus, not normal source. Route to artifact storage or a dedicated corpus PR only if the owning workflow requires versioned fixtures. | Manifest exists; sample files validate; PR description states size and regeneration command; otherwise corpus remains uncommitted. |
| `outputs/` | 51 untracked paths including CSV and base64 chunk outputs. | Do not commit raw `outputs/` from the shared checkout. Review for client/private data before any archival decision. | Either ignored/parked by the owner or converted into sanitized derived artifacts; no raw client CSV/base64 chunk bundle enters a general source PR. |
| Generated docs | `docs/AUTOMATIONS_REFERENCE.md` and `docs/DOCS_INVENTORY.md` are modified. | Regenerate on the reconciled base and commit separately from NLM/content changes. | Generator command is recorded; `git diff --check` passes; docs-only commit contains no unrelated runtime state. |
| KPI timeline | New CSV row has trailing whitespace. | Normalize only if retaining the KPI timeline update. | `git diff --check -- apps/research/sota-social-2026-v1/kpi_timeline.csv` passes. |

## Recommended Commit Order

1. Preserve local article translation commits:
   `feat(articles): preserve local translation commits`
2. Reconcile `main` with `origin/main` without losing the preserved commits.
3. Drop duplicate staged sentinel/DLQ entries if the origin comparison remains
   empty.
4. Docs/generated inventories commit, only after regeneration.
5. Article/published metadata commit, only after duplicate MDX comparison.
6. NLM feeder/pipeline commit, only after focused dry-run/tests.
7. Regulatory/NB report commit, only if curated and source-tagged.
8. Corpus/artifact handling, preferably outside a normal source PR unless
   explicitly required.

Do not mix executable sentinel/DLQ script changes, docs regeneration, article
content, and bulk generated research outputs in one commit.

## Verification Commands For The Follow-Up Owner

```bash
git status --short --branch
git log --oneline origin/main..HEAD
git log --oneline HEAD..origin/main | head
git diff --cached origin/main -- scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py
PYTHONPATH=. pytest scripts/tests/test_sentinel_w70_resurrect_enrich.py scripts/tests/test_escalations_s3.py -q
git diff --check
jq empty research/regulatory/*.json
```

For backend safety, if any backend code is touched during reconciliation, also
run:

```bash
cd apps/backend-rag
source .venv/bin/activate
PYTHONPATH=. pytest backend/tests/services/rag/test_kg_langgraph.py backend/tests/services/rag/test_kg_subgraphs.py backend/tests/services/rag/test_confidence.py -q
python -c "from backend.app.dependencies import get_current_user; print('OK')"
```

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`
  LaunchAgents based on this snapshot.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean the shared checkout from an unrelated isolated worktree.
- Do not use `--no-verify`, force push, or reset the shared checkout.
- Do not commit raw `outputs/` or broad generated corpus material without an
  owner and manifest.

## Next Step

Assign a heavier agent or human operator to preserve the two local article
commits, reconcile the shared checkout with `origin/main`, and then process the
remaining dirty files by the workstream plan above. Until that happens, treat
the shared main checkout as a contaminated review base and avoid deploy or
archive decisions from it.
