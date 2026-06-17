# Dirty Main Snapshot Triage - 2026-06-15

Date: 2026-06-15 WITA
Dispatch key: `dirty-main-snapshot-20260615`
Source report: `/Users/nuzantara/codex-spark-loop/reports/scout-20260615_035002.md`
Overnight branch: `codex-overnight/spark-alarm-20260615_035040-spark-dispatch-20260615_035002-scout-dirty-main-snapshot-20260615-20260615_035040`
Owner: Ops/heavier-agent queue for shared-checkout hygiene

## Scope

Diagnose the Spark-dispatched dirty main checkout signal without editing
`/Users/nuzantara/Desktop/nuzantara`, deploying, or restarting production
LaunchAgents.

The safe output is a handoff spec because the shared main checkout contains broad
dirty work and is also behind `origin/main`. A cleanup or pull from an unrelated
overnight worktree could overwrite operator or sibling-agent work.

## Live Evidence

- Machine check ran on Pro: `nuzantara@Nuzantara`. Mini was unreachable during
  the SSH peer check, so peer sync is unverified.
- Isolated overnight worktree is clean on
  `codex-overnight/spark-alarm-20260615_035040-spark-dispatch-20260615_035002-scout-dirty-main-snapshot-20260615-20260615_035040`
  at `0207c648a`.
- No path-specific `AGENTS.md` files exist at the requested runbook locations:
  `apps/backend-rag/AGENTS.md`, `scripts/AGENTS.md`, or
  `apps/backend-rag/backend/llm/AGENTS.md`.
- Spark lifecycle is not the root cause:
  - `com.nuzantara.codex-spark-loop`: `state = running`, `pid = 1212`,
    `last exit code = (never exited)`.
  - `com.nuzantara.codex-spark-alarm`: timer idle, `last exit code = 0`.
  - `com.nuzantara.codex-spark-harvester`: timer idle, `last exit code = 0`.
- Shared checkout `/Users/nuzantara/Desktop/nuzantara` is on `main` at
  `e2b355f45`, while `origin/main` and this overnight worktree are at
  `0207c648a`. The shared checkout reports `ahead 2, behind 176`.
- The shared checkout is dirty across rules, docs, research outputs,
  article/content files, evaluator pipelines, `scripts/*`, and `outputs/`.
  `scripts/dlq_autopilot.py` and `scripts/nuzantara-sentinel.py` are
  index-modified/staged according to `git status --short`.
- `com.nuzantara.agent-worktree-cleanup.daily` currently points at
  `/Users/nuzantara/Desktop/nuzantara/scripts/agent_worktree_cleanup_cron.sh`
  and reports `last exit code = 1`.
- The runtime main checkout copy of `scripts/agent_worktree_cleanup_cron.sh`
  still exits with the broker return code on WIP skips and logs
  `done (exit 1)`.
- Current `origin/main` already contains the cleanup-cron exit-semantics fix in
  `8ce1930a9` (`fix(ops)+test(setup): Antibody Debt ledger #2 + #5 ...`):
  WIP skips map broker `rc=1` to wrapper exit `0`, with warning signal carried
  by heartbeat/logs.
- Focused broker validation in this overnight branch initially failed three
  cleanup tests because `agent_start.py` invoked `lsof` through PATH. On this
  Mac, `lsof` exists at `/usr/sbin/lsof`, while the LaunchAgent PATH is
  `/opt/homebrew/bin:/usr/bin:/bin`. That would make clean expired worktrees
  look live and avoid reaping under launchd.

## Root-Cause Classification

Primary cluster: stale, dirty shared checkout used as launchd runtime.

The failed cleanup LaunchAgent is not evidence of a new cleanup-cron code defect
on `origin/main`. It is evidence that the LaunchAgent is still executing the old
script from the dirty main checkout. The main checkout cannot be safely fast-
forwarded by this overnight agent because it has local commits, staged changes,
modified tracked files, and broad untracked output/content directories.

Secondary cleanup bug fixed in this branch: `scripts/agent_start.py` now resolves
`lsof` with a macOS fallback to `/usr/sbin/lsof`, so the broker's live-process
guard works even under the restricted launchd PATH.

## File Plan

| Surface | Current state | Plan | Acceptance criteria |
| --- | --- | --- | --- |
| Spark LaunchAgents | Healthy under lifecycle semantics | Do not restart or edit. | Spark loop has active PID; alarm/harvester idle with exit 0. |
| `agent-worktree-cleanup.daily` | Stale runtime script exits 1 on WIP skip | Do not patch runtime main from this branch. Preserve WIP first, then fast-forward main to a commit containing `8ce1930a9` or newer. | Next cron log says `done (broker rc=1, exit 0)` for WIP skips, or `done (broker rc=0, exit 0)` when clean. |
| Broker live-process guard | `lsof` is outside launchd PATH on macOS | Patch `scripts/agent_start.py` to resolve `/usr/sbin/lsof` as fallback and cover it with a test. | `scripts/tests/test_agent_start.py` passes under the repo venv. |
| Dirty main content/research outputs | Broad intentional-looking WIP mixed with code changes | Triage by owner, not by automated sweep. Separate content/research artifacts from executable script changes. | Each retained cluster has an owner, branch, commit, or explicit discard decision. |
| Staged/index-modified scripts | `scripts/dlq_autopilot.py`, `scripts/nuzantara-sentinel.py` | Review first because they are executable automation changes. | Focused validation is recorded before commit or discard. |

## Recovery Sequence

1. In `/Users/nuzantara/Desktop/nuzantara`, capture a read-only inventory:
   `git status --short --branch`, `git log --oneline --decorate -5`, and
   `git diff --name-status`.
2. Classify WIP into content/research outputs versus executable automation code.
   Do not mix these in one commit.
3. Preserve intentional WIP using normal commits on an owner branch, or an
   explicit stash with a descriptive label. Do not use `git reset --hard`.
4. Once the shared checkout is clean enough, fast-forward it to a commit that
   includes both the wrapper exit fix and the `lsof` fallback.
5. Run:
   `bash -n scripts/agent_worktree_cleanup_cron.sh`
6. Kick or wait for the daily job, then verify:
   `launchctl print gui/$(id -u)/com.nuzantara.agent-worktree-cleanup.daily`
   and `tail -n 80 ~/logs/agent-worktree-cleanup.log`.

## Non-Goals

- Do not deploy.
- Do not modify `.env*`, `secrets/*`, `fly.toml`, or
  `backend/prompts/zantara_core.py`.
- Do not copy script files into the shared main checkout from an overnight
  worktree.
- Do not force-push, bypass checks, or use `--no-verify`.
- Do not remove `outputs/` or research directories without an owner decision.

## Next Step

Queue a heavier shared-checkout hygiene pass with operator awareness. Its first
deliverable should be a clean preservation plan for the two local commits, the
staged automation files, and the content/research output directories. After that
plan is applied, fast-forwarding main will pick up the already-merged cleanup
cron fix and should clear the `agent-worktree-cleanup.daily` bad-exit noise.
