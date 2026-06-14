# Main Dirty Worktree Triage - 2026-06-15

Date: 2026-06-15
Dispatch key: `main-dirty-worktree-triage`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_014006.md`
Runner branch: `codex-overnight/spark-alarm-20260615_014041-spark-dispatch-20260615_014006-scout-main-dirty-worktree-triage-20260615_014041`
Shared checkout under triage: `/Users/nuzantara/Desktop/nuzantara`

## Scope

Resolve the dirty shared-checkout signal without touching Spark LaunchAgents,
production daemons, deploy state, secrets, or raw OSINT/WhatsApp data.

This spec is intentionally decision-first. The overnight runner verified the
signal from an isolated worktree and did not mutate the dirty shared checkout.
The safe next move is a heavier cleanup pass that preserves all user work, splits
coherent changes into owner branches, and archives or discards generated outputs
only after dry-run evidence.

## Live Evidence

- Machine check: Pro, `nuzantara@Nuzantara`; peer `mini` was unreachable during
  the session-start SSH check, so cross-machine git sync is unverified.
- Runner worktree is clean on the required branch at `a03b928fe`
  (`origin/main`, `feat(intake): Mythos M4... (#1430)`).
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45` and is `ahead 2, behind 175` versus `origin/main`.
- Shared checkout status contains 23 tracked modified paths, with two staged:
  `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py`.
- Staged script diff summary: 205 insertions and 2 deletions across the two
  scripts. `git diff --cached --check` passes.
- Broader shared checkout `git diff --check` fails on trailing whitespace in
  `apps/research/sota-social-2026-v1/kpi_timeline.csv`.
- Untracked file count is 919. The largest untracked groups are:
  - 284 files in `research/coherence-corpus/nb3-company-curated`
  - 202 files in `research/coherence-corpus/nb6-operations-curated`
  - 166 files in `research/coherence-corpus/nb4-tax-curated`
  - 146 files in `research/coherence-corpus/nb5-property-curated`
  - 42 files in `research/coherence-corpus/nb-intel-regulation`
  - 5 article files under `apps/mouth/src/content/articles`
  - generated media under `apps/evaluator/nlm_deep_research/output/multimodal`
  - scratch/export files under `outputs/`
- Spark lifecycle is not the actionable cluster:
  - `com.nuzantara.codex-spark-loop` is running with PID `1212`.
  - `com.nuzantara.codex-spark-alarm` is a timer job, not running between ticks,
    with last exit code `0`.
  - `com.nuzantara.codex-spark-harvester` is a timer job, not running between
    ticks, with last exit code `0`.
  - `com.nuzantara.codex-overnight-runner` is running for this task.
- Recent Codex log roots exist and include older/auth/network noise, but the
  live LaunchAgent state and successful Spark report do not support a Spark
  lifecycle repair in this intervention.

## Root-Cause Classification

Primary cluster: stale shared `main` checkout with mixed owner work.

The dirty tree combines at least five separate streams: staged DLQ/sentinel
behavior changes, NLM deep-research code/config edits, generated NLM/corpus
outputs, article/content publishing artifacts, and ops/research documentation.
Because `main` is both behind `origin/main` and ahead by two local commits,
cleaning it directly from an unrelated runner branch would risk losing user work
or mixing unrelated domains.

## Queue Plan

| Queue | Paths | Rationale | Required gate |
| --- | --- | --- | --- |
| `keep/stage` | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Staged W70 DLQ/sentinel heal-loop changes look intentional and are executable behavior, not generated output. | Move to a dedicated ops branch. Run `python -m py_compile scripts/dlq_autopilot.py scripts/nuzantara-sentinel.py` plus the smallest DLQ/sentinel fixture or dry-run validation available. Commit separately from docs/content. |
| `move to worktree` | `apps/evaluator/nlm_deep_research/*.py`, `apps/evaluator/nlm_deep_research/*.json`, `apps/mata-garuda/mata_garuda/workers/nlm_feeder.py`, `scripts/nb_export_corpus.py`, `scripts/nb_generate_inventory.py` | Coherent NLM pipeline and feeder changes need code review and validation in their own branch. | Create a dedicated NLM worktree from current `origin/main`, apply only these path diffs, run focused Python compile/tests for the touched modules, and verify config JSON parses. |
| `move to worktree` | `apps/mouth/src/content/articles/**/*.mdx`, `apps/bali-intel-scraper/data/published_articles.json` | Article translations and published-article metadata are content/publishing work, separate from ops automation. | Create a content branch. Validate MDX/frontmatter using the existing mouth/content check or `npm run lint` in `apps/mouth` if available. Do not mix with NLM or sentinel changes. |
| `move to worktree` | `.claude/rules/cicatrix-scars*.md`, `docs/AUTOMATIONS_REFERENCE.md`, `docs/DOCS_INVENTORY.md`, `scripts/curiosity_loop.sh`, `apps/crm-cell/war-room/interactive_cli.sh`, `scripts/scar_query.py` | Ops docs/tooling and cicatrix scars are reviewable but broad. They should not ride with executable sentinel fixes. | Create an ops-docs branch. Check markdown diff for secrets, run shellcheck for shell scripts if available, and keep runtime logs out of the commit. |
| `move to worktree` | `apps/research/sota-social-2026-v1/kpi_timeline.csv`, `apps/research/sota-social-2026-v1/weekly_report_2026-06-13.md`, `research/commercial/2026-W24-yield-opportunities.md` | Social/commercial research output is a separate reporting bundle. | Fix the `kpi_timeline.csv` trailing whitespace before commit. Validate CSV parses and commit with the weekly report if it is source-backed. |
| `archive/generated` | `research/coherence-corpus/**`, `research/regulatory/2026-06-10-delta.json` through `2026-06-14-delta.json`, `research/nb-health/2026-06-10-health.md` through `2026-06-14-health.md`, `apps/evaluator/nlm_deep_research/output/multimodal/**/*.m4a` | Large generated corpus, regulatory deltas, health snapshots, and audio outputs should not be accidentally committed without ownership and retention policy. | Preserve locally outside the repo or in the intended artifact store, then commit only manifests/summaries that are meant to be reviewed. Use `git clean -nd` before any deletion. |
| `archive/generated` | `outputs/_b64chunks/**`, `outputs/_clients_b64.txt`, `outputs/clients_all.csv`, `outputs/clients_master_clean.csv` | Scratch/export outputs may contain client-derived data and should stay local unless a sanitized artifact policy explicitly says otherwise. | Do not open or upload raw content unnecessarily. If retained, move to a local-only artifact directory with restricted scope; otherwise remove only after backup and dry-run confirmation. |
| `discard candidate` | `shared/escalations_pro.jsonl` | Looks like append-only local runtime state. It is risky to commit raw escalation logs. | Review only metadata, redact if a summary is needed, and prefer local archive or discard after confirming no operator-owned event must be preserved in git. |

## Safe Cleanup Sequence

Run from `/Users/nuzantara/Desktop/nuzantara` only after the cleanup owner is
ready to act:

1. Capture non-destructive evidence.
   - `git status --short --branch`
   - `git rev-list --left-right --count origin/main...main`
   - `git diff --cached --stat`
   - `git diff --stat`
   - `git ls-files --others --exclude-standard | wc -l`
2. Preserve the local `main` head before any branch switch.
   - `git branch preserve/main-dirty-20260615 main`
3. Export local-only patch backups before splitting.
   - `git diff --cached --binary > /tmp/main-dirty-20260615-staged.patch`
   - `git diff --binary > /tmp/main-dirty-20260615-unstaged.patch`
   - Create a local-only manifest of untracked paths. Do not upload raw client
     outputs or OSINT-derived files.
4. Split one queue at a time into isolated worktrees or branches.
   - Apply only the path group under review.
   - Run the queue-specific validation gate.
   - Commit and push that queue before starting the next one.
5. Only after all keep/move queues are preserved, run destructive cleanup as a
   dry run first.
   - `git clean -nd`
   - Review exact paths.
   - Use `git clean -fd -- <path>` only for paths confirmed generated or backed
     up locally.

## Non-Goals

- Do not unload, restart, or rewrite `com.nuzantara.codex-spark-*` LaunchAgents.
- Do not deploy.
- Do not push directly to `main`.
- Do not use `--no-verify`, force push, `git reset --hard`, or `git checkout --`
  against the dirty shared checkout.
- Do not edit `backend/prompts/zantara_core.py`, `fly.toml`, `.env*`, or secrets.
- Do not move WhatsApp/OSINT raw data out of the Pro machine.

## Acceptance Criteria For Heavier Agent

- `main` unique commits are preserved by branch, PR, or documented archive.
- Every tracked path is classified into exactly one queue and has either a
  committed owner branch or a documented discard/archive decision.
- Every untracked generated directory has a local-only archive/discard decision.
- `git diff --check` passes for any committed queue.
- Shared checkout returns to a clean `git status --short --branch`, or remaining
  dirt is explicitly documented with owner, branch, and deadline.

## Next Step

Start with the staged DLQ/sentinel queue because it is executable behavior and
already passes whitespace validation. After preserving that queue, split the NLM
pipeline/corpus and article bundles into separate worktrees. Leave `outputs/`
and raw runtime/export files out of git unless a sanitized artifact policy is
explicitly chosen.
