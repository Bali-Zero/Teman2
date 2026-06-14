# Dirty Main Triage - NLM Research Articles - 2026-06-14

Date: 2026-06-14
Dispatch key: `dirty-main-nlm-research-articles`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260614_121320.md`
Owner: Ops/repo-hygiene owner for `/Users/nuzantara/Desktop/nuzantara`
Decision deadline: 2026-06-14 18:00 WITA

## Scope

Resolve the dirty shared-checkout signal in `/Users/nuzantara/Desktop/nuzantara`
without repairing Spark LaunchAgents, deploying, or moving unreviewed generated
artifacts into the overnight branch.

This triage spec is decision-only. The safe remediation is to classify the
shared checkout and define keep/drop/commit boundaries, because the checkout is
both dirty and stale relative to `origin/main`.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`; peer `mini` was unreachable during
  the session-start SSH check, so peer sync is unverified.
- Isolated overnight branch:
  `codex-overnight/spark-alarm-20260614_121435-spark-dispatch-20260614_121320-scout-dirty-main-nlm-research-articles-20260614_125834`.
- Overnight branch HEAD: `84ae8edae`; no local modifications before this spec.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45`, with `git rev-list --left-right --count main...origin/main`
  reporting `2 173`. Do not pull, merge, reset, or branch-switch there until the
  dirty work is isolated.
- Shared checkout dirty summary:
  - 19 unstaged modified tracked files.
  - 2 staged modified tracked files.
  - 911 untracked files from `git ls-files --others --exclude-standard`.
- Spark lifecycle is not actionable:
  - `com.nuzantara.codex-spark-loop`: `state = running`, PID observed live as
    `2066`, `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `last exit code = 0`, `run interval = 180 seconds`.
- State files under `/Users/nuzantara/.agent/decisions/state` exist and include
  fresh Codex/Spark files updated around 12:59-13:01 WITA on 2026-06-14.

## Root-Cause Classification

Primary cluster: broad shared-checkout accumulation from NLM/NotebookLM pipeline
rotation, generated research outputs, article publication artifacts, and staged
automation repair scripts.

The evidence does not justify restarting or rewriting Spark services. The
actionable issue is that unrelated code, content, runtime outputs, and local
artifacts are mixed in the main checkout while that checkout is far behind
`origin/main`.

## File Plan

| Cluster | Paths | Current state | Plan | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Staged W70 automation repair | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged modifications; +205/-2 lines total. Adds DLQ terminal requeue, cron-log enrichment, resurrection cleanup, and blind-loop alerting. | Keep as a dedicated ops/autonomy PR only after syntax and focused sentinel/DLQ validation. Do not mix with articles, NLM IDs, docs, or generated outputs. | `python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`; focused tests or dry-run proving no alert storms and no data loss in DLQ state. |
| NLM NotebookLM ID and profile rotation | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/curiosity_loop.sh` | Unstaged code/config edits. Mostly NB2/NB5/NB6 notebook ID replacements, `nlm` CLI profile change from `zero` to `default`, and Python 3.11 pinning for curiosity loop. | Keep only as a separate NLM infrastructure PR after live owner confirms the new notebook IDs and `nlm --profile default` are canonical. Consider centralizing IDs before commit if this pattern keeps recurring. | Python compile of affected modules; a non-mutating NLM profile check; proof that the new IDs match the intended NotebookLM notebooks. |
| Published article register | `apps/bali-intel-scraper/data/published_articles.json` | Unstaged generated data edit; +340 JSON lines, no deletions. | Keep only with the article-content PR if the generated register is the canonical publish ledger. Otherwise regenerate after `main` is updated. | JSON validity; source generator identified; duplicate URL check passes; no unrelated article history churn. |
| Article MDX content | 5 files under `apps/mouth/src/content/articles/{immigration,tax}/` | Untracked article drafts/published content. | Review editorially and commit separately from scraper ledgers and NLM code. Avoid committing as part of repo-hygiene cleanup. | Frontmatter valid; source links reviewed; `apps/mouth` lint/build or the smallest article parser validation passes. |
| Generated and sensitive local outputs | `outputs/`, `apps/evaluator/nlm_deep_research/output/multimodal/`, `research/coherence-corpus/`, `research/regulatory/*-delta.json`, `research/nb-health/*` | Untracked outputs: `outputs=51`, `nlm_output=1`, `coherence=840`, `regulatory=5`, `nb_health=5`. `outputs/` includes client CSV/base64 artifacts. | Do not commit in bulk. Move to artifact storage or ignore after owner review. Treat `outputs/` as sensitive until inspected and sanitized. | Explicit owner decision for each directory; no client CSV/base64 files enter git; large binary/audio artifacts stay out of source control unless there is a documented release reason. |
| Generated docs and research summaries | `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/commercial/2026-W24-yield-opportunities.md` | Mixed tracked generated diffs plus untracked reports. | Commit only from the generator owner after confirming these are reproducible outputs. Keep docs inventory updates separate from runtime automation code. | Generator command recorded; markdown reviewed for stale runtime claims; CSV schema unchanged. |
| Runtime escalation state | `shared/escalations_pro.jsonl` | Unstaged append from empty file; 53 runtime queue entries. | Do not commit as-is. Preserve locally if needed, then revert or move to an ignored runtime location after owner approval. | No live queue state, private operational telemetry, or unsanitized escalation payloads enter a PR. |
| Misc new operator tooling/docs | `apps/crm-cell/war-room/interactive_cli.sh`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py`, `research/operations/2026-06-11-*.md` | Untracked scripts and ops notes. | Review and commit individually only if they are source artifacts, not run leftovers. Scripts need shellcheck or focused dry-run before inclusion. | Each file has an owner, purpose, and validation command before commit. |

## Recommended Commit Order

1. Safety checkpoint outside git history if an operator must preserve the shared
   checkout before touching it:
   `git diff > /tmp/dirty-main-20260614.patch`,
   `git diff --cached > /tmp/dirty-main-20260614-staged.patch`, and
   `git ls-files --others --exclude-standard > /tmp/dirty-main-20260614-untracked.txt`.
2. W70 automation repair PR:
   `fix(ops): restore dlq diagnostic recovery loop`.
3. NLM infrastructure PR:
   `chore(nlm): rotate notebook ids and default profile`.
4. Article publication PR:
   `content(articles): publish june immigration and tax updates`.
5. Generated docs/research PR:
   `docs(ops): refresh automation and inventory snapshots`.
6. Cleanup decision:
   ignore, move, or delete generated local outputs only after the owner confirms
   they are not needed. Do not run destructive cleanup from an unrelated agent.

## Validation Matrix

| Surface | Smallest meaningful validation |
| --- | --- |
| Staged automation scripts | `python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py`; focused DLQ fixture test or dry-run. |
| NLM Python modules | `python -m compileall apps/evaluator/nlm_deep_research apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`; non-mutating NLM profile/notebook check. |
| Published article JSON | `python -m json.tool apps/bali-intel-scraper/data/published_articles.json >/dev/null`; duplicate URL scan. |
| MDX articles | `cd apps/mouth && npm run lint` or the existing content parser test if cheaper. |
| Generated docs | Re-run the documented generator and confirm a clean second diff. |
| Runtime/output artifacts | No commit validation until owner decides keep versus artifact storage versus ignore. |

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not change `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean the shared checkout from this isolated overnight branch.
- Do not use `--no-verify`, force push, direct `main` push, or reset the shared
  checkout.
- Do not commit client CSV/base64 artifacts or live escalation state without a
  sanitization decision.

## Next Step

The shared-checkout owner should first isolate the dirty main state before any
pull or branch switch, then split the work by the commit order above. The most
urgent human decision is whether the staged W70 automation repair is ready for a
dedicated PR; it is the only cluster already staged and executable.
