---
date: 2026-05-30
domain: operations
dispatch_key: repo-dirty-and-nb-staging-2026-05-30
source_agent: com.nuzantara.codex-spark-loop
status: triage-ready
---

# Repo Dirty And NB Staging Triage - 2026-05-30

## Decision

The actionable cluster is local workspace hygiene in `/Users/nuzantara/Desktop/nuzantara`, not a Spark/Codex LaunchAgent outage.

Apply only two safe actions in this branch:

1. Preserve the verified `docs/AI_ONBOARDING.md` docsync correction from `970 tests` to `971 tests`.
2. Record the remaining dirty artifacts as owner-routed follow-up work instead of mutating the shared main checkout.

No launchd restart, deployment, stash, reset, or queue mutation is supported by the evidence in this pass.

## Live Verification

Commands were run from the isolated overnight worktree:

`/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-overnight-runner-runs/spark-alarm-20260530_101101-spark-dispatch-20260530_101035-scout-repo-dirty-and-nb-staging-2026-05-30-20260530_101101`

Observed state:

- Machine: `nuzantara@Nuzantara`.
- Peer: `nuzantara@mini-pro2`.
- Git sync from the overnight worktree check: OK at `9bc201436`.
- Overnight branch: `codex-overnight/spark-alarm-20260530_101101-spark-dispatch-20260530_101035-scout-repo-dirty-and-nb-staging-2026-05-30-20260530_101101`.
- Requested path-specific `AGENTS.md` files under `apps/backend-rag/`, `scripts/`, and `apps/backend-rag/backend/llm/` were absent; root `AGENTS.md` was read.
- Shared main checkout status stayed dirty and was not mutated:
  - `M docs/AI_ONBOARDING.md`
  - `M shared/escalations_pro.jsonl`
  - `?? research/nb-health/2026-05-30-health.md`
  - `?? research/operations/2026-05-30-sota-ai-architecture-methodology.md`

Spark/Codex lifecycle:

- `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1018`, `last exit code = (never exited)`.
- `com.nuzantara.codex-spark-alarm`: `state = not running`, `runs = 23`, `last exit code = 0`, `run interval = 120 seconds`.
- `com.nuzantara.codex-spark-harvester`: `state = not running`, `runs = 16`, `last exit code = 0`, `run interval = 180 seconds`.
- `com.nuzantara.codex-overnight-runner`: `state = running`, `pid = 67835`, `last exit code = (never exited)`.

State/log correlation:

- Spark loop state JSON records the `dispatched` action for this task.
- Spark alarm state JSON records `queue_busy` after promotion, which is expected while this runner is active.
- Spark harvester state JSON records `runner_active`, with queue count 1 and backlog 0.
- Spark alarm log promoted this task at `2026-05-30 10:11:01` and reported `queue_busy count=1` at `10:13:01`.
- Spark alarm and harvester stderr logs were 0 bytes.
- Overnight runner stderr log was 0 bytes.
- Spark loop stderr had one historical `Terminated: 15` timeout line. The current loop is running and the subsequent alarm/harvester state is fresh, so this is a watch item, not a crash loop.
- The alarm log had one `spark_unhealthy stale_state` line at `09:26:48`, followed by fresh Spark states and successful dispatch at `10:11:01`; it is treated as recovered.

## Dirty Path Disposition

| Path | Disposition | Evidence | Next action |
|---|---|---|---|
| `docs/AI_ONBOARDING.md` | keep in this PR | `find apps/backend-rag/backend/tests -name 'test_*.py' \| wc -l` returned `971`; the dirty diff only updates the docsync quick number from `970` to `971`. | Preserve as a safe docsync correction. |
| `shared/escalations_pro.jsonl` | shelve for queue owner | Dirty diff appends four `seo_cell_28d_check` pending escalation records. This is append-only runtime queue state, not source code. | Do not commit in this branch. Let the DLQ/SEO owner drain, archive, or commit from a dedicated ops pass. |
| `research/nb-health/2026-05-30-health.md` | keep, but park | Read-only NB curator report says NB health is stable and includes dedup proposals. It is useful operational evidence, but belongs to NB health reporting. | Preserve in a dedicated NB/research commit after owner review. Do not mix into this Spark triage PR. |
| `research/operations/2026-05-30-sota-ai-architecture-methodology.md` | keep, but park | Long research methodology note with source list and caveats. Useful, but orthogonal to repo-dirty remediation. | Preserve in a dedicated research/operations commit after source/caveat review. |

No path has enough evidence for discard.

## Follow-Up Pass

Run this from a fresh ops worktree, not from `/Users/nuzantara/Desktop/nuzantara`:

```bash
python scripts/agent_start.py --lane ops --task-id repo-dirty-nb-staging-closeout
```

Then:

1. Re-check the shared checkout with `git -C /Users/nuzantara/Desktop/nuzantara status --short --branch`.
2. If this PR is merged, verify `docs/AI_ONBOARDING.md` is no longer dirty; otherwise carry only the verified docsync one-line change into the closeout branch.
3. Preserve `research/nb-health/2026-05-30-health.md` in an NB health commit, or move it to the agreed report archive if the NB owner prefers that path.
4. Preserve `research/operations/2026-05-30-sota-ai-architecture-methodology.md` in a separate research commit after checking that its caveats remain explicit.
5. Treat `shared/escalations_pro.jsonl` as runtime queue state: inspect owner process status before any commit, truncation, or archive action.
6. Repeat the focused log check only on latest files:
   - `tail -n 120 /Users/nuzantara/logs/codex-spark-alarm/launchd.out.log`
   - `tail -n 120 /Users/nuzantara/logs/codex-spark-harvester/launchd.out.log`
   - `tail -n 80 /Users/nuzantara/logs/codex-spark-loop/launchd.err.log`
   - `tail -n 120 /Users/nuzantara/logs/codex-overnight/launchd.out.log`
7. Escalate Spark lifecycle only if the loop is not running with stale state, or alarm/harvester have fresh non-zero exits repeated across ticks.

## Acceptance Criteria For Closeout

- Shared main checkout has no unowned dirty paths.
- Research artifacts are preserved or explicitly routed.
- Runtime queue append-only data is handled by its owner, not by a broad repo cleanup.
- Spark trio remains classified by live state, not stale `launchctl list` exit codes alone.
