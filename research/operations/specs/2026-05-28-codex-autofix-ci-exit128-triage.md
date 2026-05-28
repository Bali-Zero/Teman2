# Codex Autofix CI Exit 128 Triage

Date: 2026-05-28
Dispatch key: 86012d033977
Job: `com.nuzantara.codex-autofix-ci`

## Scope

Diagnose the Spark signal that `com.nuzantara.codex-autofix-ci` reported launchd `last exit code = 128`, correlate it with the latest logs and state files, and define the smallest safe remediation.

No production deploy is in scope.

## Live Evidence

- Machine: Pro, `nuzantara@Nuzantara`.
- Peer Mini was reachable, but Git sync was out of sync during this triage:
  - local Pro HEAD: `380130e92 feat(inbox): restrict /api/workspace/inbox to owner (zero@) only (#906)`
  - Mini HEAD: `0a7ef76c5 fix(wa-mirror): restore direct ingest on Baileys rc13`
- `launchctl print gui/501/com.nuzantara.codex-autofix-ci` showed:
  - state: `not running`
  - runs: `50`
  - last exit code: `128`
  - working directory: `/Users/nuzantara/Desktop/nuzantara`
  - program: `/bin/bash /Users/nuzantara/scripts/cron-runner.sh /Users/nuzantara/scripts/codex/nightly-autofix-ci.sh`
- `/Users/nuzantara/.agent/decisions/state/codex_com_nuzantara_codex_autofix_ci.state.json` showed a later non-failing state:
  - outcome: `skipped`
  - action: `daily_cap`
  - message: `Daily cap reached (3/3)`
  - worktree: `/Users/nuzantara/Desktop/nuzantara/.worktrees/codex-autofix-ci-runtime`
- `/Users/nuzantara/logs/codex-autofix-ci/launchd.err.log` contained historical hard failures:
  - malformed log paths from TSV parsing in older script revisions
  - `cd: /Users/nuzantara/Desktop/nuzantara/.worktrees/codex-autofix-ci-runtime: No such file or directory`
  - `fatal: couldn't find remote ref <branch>`
  - SSH public-key failures on some fetch attempts
- `/Users/nuzantara/logs/codex-autofix-ci/launchd.out.log` showed the newest concrete `128`-class event:
  - run `26558623369`
  - branch `agent/nuzantara/backend-rag/inbox-admin-gate-2026-05-28`
  - `fatal: couldn't find remote ref agent/nuzantara/backend-rag/inbox-admin-gate-2026-05-28`

## Root-Cause Classification

Primary cluster: Git/runtime hygiene.

The actionable failure is not a model/auth failure. The script treated stale or deleted GitHub Actions head branches as normal checkout targets. With `set -euo pipefail`, a failed `git fetch origin "$BRANCH"` can terminate the LaunchAgent with Git exit `128`. The runtime worktree had also been absent in earlier runs, causing repeated `cd` failures before the newer external script added worktree creation.

Secondary observations:

- Daily cap state at 15:37 proves the job can now complete a skip path, but launchd preserves the last non-zero exit until a later scheduled zero-exit run updates it.
- Dirty files in the main checkout are not remediated here. The autofix job uses a runtime worktree and should skip dirty runtime states safely.

## Minimal Remediation

Update the repository copy of the Codex autofix scripts so the tracked implementation matches the safer live script behavior:

- source the maintained automation library path: `${HOME}/scripts/codex/automation-lib.sh`
- ensure the runtime worktree exists before `cd "$REPO_ROOT"`
- treat missing branch fetch, non-checkoutable branch, or non-resettable SHA as `skipped` state with exit `0`
- consume daily cap only after logs are fetched and the failing SHA is checked out
- run Codex with OpenAI environment variables removed so OAuth profile behavior is not shadowed by ambient API keys
- return to detached `origin/main` instead of mutating `main` in the runtime worktree

## Restart and Clear-State Criteria

Safe restart criteria:

1. `bash -n scripts/codex/codex-nightly-autofix-ci.sh scripts/codex_automation_lib.sh` passes.
2. Focused automation-lib tests pass.
3. The runtime worktree path is either an existing Git worktree or empty/missing.
4. The latest state is `idle`, `skipped`, or `blocked` with a clear non-destructive reason.

Clear-state criteria:

- Do not delete `codex_autofix_ci.state` merely because launchd reports `128`; it is the per-run cooldown ledger.
- It is safe to remove only a stale lock directory when:
  - its `pid` is absent or not running, or
  - the lock directory is older than four hours.
- It is safe to reset the daily count only for a known false attempt where logs were not fetched and no Codex run started. Otherwise let the next date roll the cap naturally.

## Verification Commands

```bash
bash -n scripts/codex/codex-nightly-autofix-ci.sh scripts/codex_automation_lib.sh
PYTHONPATH=. pytest tests/scripts/test_codex_automation_lib.py -q
launchctl print gui/$(id -u)/com.nuzantara.codex-autofix-ci
```
