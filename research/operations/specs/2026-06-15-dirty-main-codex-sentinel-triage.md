# Dirty Main Codex Sentinel Triage - 2026-06-15

Date: 2026-06-15
Verified at: 2026-06-15 01:50 WITA
Dispatch key: `dirty-main-codex-sentinel-20260614`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_014532.md`
Source prompt: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_014532.prompt.md`
Source JSONL: `/Users/nuzantara/logs/codex-spark-loop/scout-20260615_014532.jsonl`
Shared checkout: `/Users/nuzantara/Desktop/nuzantara`
Intervention branch:
`codex-overnight/spark-alarm-20260615_014810-spark-dispatch-20260615_014532-scout-dirty-main-codex-sentinel-20260614-20260615_014810`

## Scope

Resolve the dirty-main sentinel signal without normalizing or stealing work from
the shared checkout.

This spec is the minimal safe remediation for the Spark finding. Spark/Codex
LaunchAgents are healthy by live lifecycle checks; the actionable cluster is the
broad dirty shared checkout with mixed staged script work, unstaged automation
docs/NLM changes, content outputs, and generated research artifacts.

## Live Evidence

- Machine check ran on Pro: `nuzantara@Nuzantara`. Peer `mini` was unreachable
  during the startup check, so peer git sync is unverified.
- This intervention is already isolated in the required overnight worktree and
  branch.
- No path-specific `AGENTS.md` exists below the root in this checkout.
- Shared checkout HEAD:
  `e2b355f45 feat(articles): add translations for indonesia-eyes-visa-free-access-for-aussie-and-kiwi-tourists`.
- Spark/Codex lifecycle is not the failing surface:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer job, `state = not running`,
    `runs = 117`, `last exit code = 0`, `run interval = 120 seconds`.
  - `com.nuzantara.codex-spark-harvester`: timer job, `state = not running`,
    `runs = 73`, `last exit code = 0`, `run interval = 180 seconds`.
  - `com.nuzantara.codex-overnight-runner`: running in `launchctl list`
    with exit status `0`.
- Spark loop logs show repeated successful scout ticks through
  `2026-06-15 01:45:53`, including the source report for this dispatch.
- Shared checkout is dirty and matches the Spark report:
  - 2 staged script modifications:
    `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py`.
  - Staged script diff size:
    `205 insertions(+), 2 deletions(-)`.
  - 21 unstaged modified tracked files across `.claude/rules/`,
    `apps/bali-intel-scraper`, `apps/evaluator/nlm_deep_research`,
    `apps/mata-garuda`, `apps/research`, `docs`, `scripts`, and
    `shared/escalations_pro.jsonl`.
  - Multiple untracked content/research/output paths, including new
    `apps/mouth/src/content/articles/...` MDX articles, `outputs/`,
    `research/coherence-corpus/`, `research/commercial/`,
    `research/nb-health/*.md`, `research/regulatory/*-delta.json`, and
    `scripts/nb_*` helpers.
- Non-Codex launchd failures are real noise but separate from this root cause:
  examples include `cost-breaker`, `mcp-integrity`, `intake-*`,
  `wr2.supervisor*`, `wa-*`, and `merge-train`.

## Root-Cause Classification

Primary cluster: shared-checkout work accumulation.

The dirty main checkout mixes unrelated ownership domains. Treating it as one
commit would blur executable sentinel changes, generated outputs, operational
docs, NLM pipeline edits, and published content. Treating it as a Spark repair
would be wrong: Spark loop/alarm/harvester are live and healthy under the
snapshot lifecycle semantics.

## Bucket Plan

| Bucket | Paths | Risk | Required action | Acceptance criteria |
| --- | --- | --- | --- | --- |
| Sentinel and DLQ scripts | `scripts/nuzantara-sentinel.py`, `scripts/dlq_autopilot.py` | High, executable automation | Validate and commit separately only if the staged diff is still intentional. Do not mix with docs or generated output. Respect the protected-script lease guidance in `docs/runbooks/redis-lease-registry.md` before further edits. | `python` AST/syntax validation without writing bytecode; focused dry-run or fixture test for DLQ requeue and sentinel blind-loop/resurrection behavior; no `print()` added except existing CLI command output patterns; commit message `fix(sentinel): ...` or `feat(dlq): ...`. |
| NLM research pipelines | `apps/evaluator/nlm_deep_research/*`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py` | Medium/high, pipeline behavior | Review as a coherent NLM pipeline branch. Keep code/config edits separate from generated output directories. | Focused evaluator/NLM tests or import checks pass; generated `output/` files are either ignored, summarized into docs, or committed only if explicitly intended as fixtures. |
| Content/articles | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Medium, user-facing content | Validate frontmatter/slugs and commit content separately from pipeline or sentinel changes. | Content build or MDX validation passes; `published_articles.json` references only articles intentionally being published. |
| Automation docs and scars | `.claude/rules/*`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `shared/escalations_pro.jsonl` | Medium, operational memory | Split historical scar/archive changes from docs inventory refreshes. Do not use these docs to justify executable changes without code validation. | Markdown/JSONL validity checks pass; docs changes cite source evidence and avoid secrets. |
| Generated research outputs | `outputs/`, `research/coherence-corpus/`, `research/commercial/`, `research/nb-health/*.md`, `research/regulatory/*-delta.json`, `apps/research/sota-social-2026-v1/*` | Medium, large/noisy artifacts | Decide keep/drop per artifact class. Prefer summaries over raw generated dumps unless downstream code reads them. | File sizes are reviewed; no raw private WhatsApp/OSINT export is introduced; committed artifacts have a named consumer or report. |
| Launchd failure follow-ups | `cost-breaker`, `mcp-integrity`, `intake-*`, `wr2.supervisor*`, `wa-*`, `merge-train` | Separate incident class | Write separate per-cluster follow-up specs or dispatches. Do not fold into this dirty-main cleanup. | Each follow-up has live `launchctl print`, last log excerpt, owner, and rollback/safe-restart plan. |

## Execution Order For The Heavier Agent

1. Re-run the live evidence commands from the shared checkout:
   `git status --short --branch`, `git diff --cached --stat`,
   `git diff --stat`, and `launchctl list | rg 'codex-spark|codex-overnight'`.
2. Preserve the shared checkout before touching it:
   create a WIP branch or normal stash only for the files being moved, never a
   destructive reset.
3. Process the staged sentinel/DLQ scripts first because they are already in the
   index and affect automation behavior.
4. Process NLM pipeline code/config next.
5. Process content/articles and published article metadata next.
6. Process docs/scars and generated artifacts last.
7. Dispatch launchd failures as separate incidents after the checkout ownership
   is clear.

## Commit Boundaries

Recommended commit order, if validation supports keeping each bucket:

1. `fix(sentinel): restore dlq diagnostic recovery loop`
2. `fix(nlm): update notebook research pipeline behavior`
3. `feat(content): add june immigration and tax articles`
4. `docs(ops): refresh automation inventory and cicatrix archive`
5. `chore(research): add june generated research snapshots`

Do not create a single "dirty main cleanup" commit.

## Non-Goals

- Do not restart, unload, or rewrite `com.nuzantara.codex-spark-*`
  LaunchAgents for this incident.
- Do not deploy.
- Do not edit `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or
  secrets.
- Do not clean, reset, checkout, or stash the shared checkout from an unrelated
  isolated worktree unless the cleanup operation is the explicit task.
- Do not use `--no-verify`, force push, or bypass review gates.
- Do not copy raw WhatsApp/OSINT data into generated research artifacts.

## Stop Conditions

Stop and write a blocked status if:

- The staged script changes are no longer present and no dirty-main signal is
  reproducible.
- The shared checkout has switched branch or HEAD since this spec and the new
  owner is unclear.
- Any bucket contains secrets, `.env*`, raw private exports, or production-only
  credentials.
- Validation cannot distinguish generated output from source fixtures.

## Next Step

Assign a heavier agent to process the bucket plan above from the shared checkout,
starting with the staged sentinel/DLQ scripts. The first deliverable should be a
small, validated commit or an explicit decision to unstage and park those script
changes behind a separate follow-up spec.
