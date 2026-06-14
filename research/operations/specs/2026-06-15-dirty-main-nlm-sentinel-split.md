# Dirty Main NLM/Sentinel Split - 2026-06-15

Date: 2026-06-15
Dispatch key: `dirty-main-nlm-sentinel-split`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_062023.md`
Overnight branch:
`codex-overnight/spark-alarm-20260615_062107-spark-dispatch-20260615_062023-scout-dirty-main-nlm-sentinel-split-20260615_062108`
Shared checkout under review: `/Users/nuzantara/Desktop/nuzantara`

## Scope

Resolve the actionable Spark signal without editing the shared dirty checkout.

This spec is decision-only remediation. The confirmed problem is not the Spark
lifecycle. It is a broad mixed dirty state in the shared main checkout, including
staged automation changes plus unrelated NLM, content, generated-output, docs,
and potentially sensitive local-output artifacts. The safe intervention is to
define split boundaries and validation gates so the owner can preserve and land
the work without accidental mixed commits or data leakage.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`.
- Peer check: `mini` was unreachable over SSH during the session-start check, so
  peer sync could not be verified.
- Isolated worktree was clean at start on:
  `codex-overnight/spark-alarm-20260615_062107-spark-dispatch-20260615_062023-scout-dirty-main-nlm-sentinel-split-20260615_062108`.
- No path-specific `AGENTS.md` files exist under `apps/backend-rag/`,
  `scripts/`, or `apps/backend-rag/backend/llm/`; only the root `AGENTS.md`
  applies.
- Spark lifecycle is healthy:
  - `launchctl list` shows `1212 0 com.nuzantara.codex-spark-loop`.
  - `launchctl print gui/501/com.nuzantara.codex-spark-loop` shows
    `state = running`, `pid = 1212`, `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm` and
    `com.nuzantara.codex-spark-harvester` are idle timer jobs with last exit
    `0`.
  - `com.nuzantara.codex-overnight-runner` was running with PID `27406`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on
  `main...origin/main [ahead 2, behind 176]`, HEAD `e2b355f45`.
- Staged dirty state is limited to automation code:
  - `scripts/dlq_autopilot.py`
  - `scripts/nuzantara-sentinel.py`
  - staged stat: 205 insertions and 2 deletions.
- Unstaged tracked dirty state spans 22 files, with 2303 insertions and 1634
  deletions.
- Untracked state spans 921 files. Top-level counts:
  - `.claude`: 1
  - `apps/crm-cell`: 1
  - `apps/evaluator`: 4
  - `apps/mouth`: 5
  - `apps/research`: 1
  - `outputs`: 51
  - `research/coherence-corpus`: 840
  - `research/commercial`: 1
  - `research/nb-health`: 6
  - `research/nb-monitor`: 1
  - `research/operations`: 2
  - `research/regulatory`: 5
  - `scripts`: 3

## Root-Cause Classification

Primary cluster: mixed work accumulated in the shared main checkout while the
checkout is also stale relative to `origin/main`.

Spark/Codex LaunchAgents do not need repair. The risk is that staged W70
automation behavior, NotebookLM notebook migrations, content publishing,
generated reports, local outputs, and possible client/CRM artifacts could be
committed together from an old `main` base. That would make review, rollback,
and data-sovereignty checks too weak.

## Split Plan

| Split | Files | Current state | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- |
| A. W70 DLQ/sentinel remediation | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged | Land first as a focused automation PR, reconstructed onto a fresh branch from current `origin/main`. | Syntax-check both scripts without writing bytecode; validate `requeue` behavior against a disposable DLQ fixture; validate sentinel enrichment/resurrection/blind-loop paths with a focused fixture or unit test; no production LaunchAgent restart in the PR. |
| B. NotebookLM notebook/profile migration | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Unstaged | Land separately from W70 because it changes live NotebookLM IDs and CLI profile routing. | Verify the replacement notebook IDs are current and owned; grep confirms no stale NB2/NB5/NB6 IDs remain in the NLM pipeline after the commit; run the smallest NLM pipeline import/syntax checks; document whether `--profile default` is now canonical. |
| C. Runtime/dependency hygiene | `apps/backend-rag/requirements.txt`, `scripts/curiosity_loop.sh` | Unstaged | Split from NLM and W70 unless proven to be the same incident. | For `certifi`, run backend dependency lock/update policy checks if present; for `curiosity_loop.sh`, prove the configured Python path exists on Pro and that the fallback venv exists. |
| D. Generated automation docs and scars | `.claude/rules/cicatrix-scars*.md`, `.claude/rules/cicatrix-superscar.md`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl` | Unstaged and untracked | Treat as generated-operational snapshot, not code. Commit only if the generator and timestamp are verified. | JSONL validates; generated docs contain no secrets; automation reference was regenerated from live Pro state; cicatrix archive move is reviewed as a mechanical archive. |
| E. Mouth/content publishing | `apps/mouth/src/content/articles/**`, `apps/bali-intel-scraper/data/published_articles.json` | Unstaged and untracked | Land as a content PR. Do not mix with automation or NLM plumbing. | Run the Mouth content/frontmatter validation or `npm run lint`/content build for the affected app; verify article locales and published article registry consistency. |
| F. Research reports and regulatory deltas | `apps/research/sota-social-2026-v1/*`, `research/commercial/*`, `research/nb-health/*`, `research/nb-monitor/*`, `research/operations/*`, `research/regulatory/*` | Unstaged and untracked | Split by report family. Keep only source-backed reports needed for handoff. | JSON files parse; markdown reports cite their source run or notebook; no duplicated/generated scratch files are committed unless intentionally archived. |
| G. Bulky generated outputs and corpus | `outputs/**`, `research/coherence-corpus/**`, `apps/evaluator/nlm_deep_research/output/multimodal/**` | Untracked | Do not commit blindly. Decide whether these are durable corpus artifacts, ignored scratch outputs, or external storage assets. | Size and sensitivity scan completed; binary audio/output chunks are either moved to the intended artifact store or explicitly ignored; no client/WhatsApp raw data enters Git. |
| H. CRM/local war-room artifacts | `apps/crm-cell/war-room/**`, `outputs/clients*.csv` | Untracked | Treat as sensitive until proven sanitized. | Human or data-owner review confirms derived/sanitized status before any commit; otherwise keep local only or store in the approved private location. |

## Recommended Commit Order

1. Preserve the dirty state before any pull, rebase, branch switch, or cleanup.
   The safest owner action is to create a local rescue branch at the current
   dirty base before splitting:
   `git -C /Users/nuzantara/Desktop/nuzantara switch -c rescue/dirty-main-20260615`.
2. Reconstruct split A on a fresh worktree from current `origin/main`, validate,
   commit, and open a focused PR.
3. Reconstruct split B on its own fresh worktree after split A is safe, because
   NotebookLM IDs and CLI profile behavior need separate review.
4. Handle C through F as independent PRs or archive commits.
5. Do not commit G or H until size, storage policy, and sensitivity checks are
   complete.

## Validation Commands For The Split Owner

Use read-only commands first:

```bash
git -C /Users/nuzantara/Desktop/nuzantara status --short --branch
git -C /Users/nuzantara/Desktop/nuzantara diff --cached --stat
git -C /Users/nuzantara/Desktop/nuzantara diff --stat
git -C /Users/nuzantara/Desktop/nuzantara ls-files --others --exclude-standard | wc -l
```

For split A, validate the staged automation code without creating `__pycache__`:

```bash
python - <<'PY'
from pathlib import Path
for path in ["scripts/dlq_autopilot.py", "scripts/nuzantara-sentinel.py"]:
    source = Path(path).read_text()
    compile(source, path, "exec")
print("syntax ok")
PY
```

Then add fixture tests for:

- `dlq_autopilot.py requeue <job>` resets only matching `TERMINAL` entries,
  keeps nonmatching entries unchanged, and returns nonzero when no terminal entry
  exists.
- `nuzantara-sentinel.py` enriches bare `exit N` errors from a bounded cron-log
  tail but leaves meaningful `last_error` values unchanged.
- `nuzantara-sentinel.py` clears a terminal DLQ corpse only when the live state is
  fresh `ok`.
- blind-loop alert state increments and cooldown-gates alerts.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`
  LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean, reset, stash, or unstage the shared checkout from an unrelated
  isolated worktree.
- Do not commit `outputs/**`, `research/coherence-corpus/**`, client CSVs, or
  CRM war-room files without an explicit sensitivity and storage decision.
- Do not use `--no-verify`, force push, or bypass branch protections.

## Next Step

The main checkout owner should preserve the current dirty state, then split the
work in the order above. The first executable PR should be split A because it is
already staged and forms a coherent W70 DLQ/sentinel remediation. Everything
else should remain out of that PR unless live evidence proves it is required for
the same root cause.
