# S1 — ARM THE ARMER

**One line:** `queue_shepherd` logged `rearmed=0 cancelled=0` on 1879 of 1880 ticks because its rearm-candidate GraphQL query exceeds GitHub's resource limit, and it exits 0 anyway.

**Wave 1 · Pro · runs in parallel with S2** (disjoint files, separate worktrees). Built from C1, plus the pre-push floor gate from C9. Operator items: 2.

## Mandate prompt — paste everything below this line into a fresh `claude` session

SEAT AND CONTRACT
You are a Fable 5.1 session that Zero chose manually, running at max effort on Pro (`nuzantara@Nuzantara`, repo `~/nuzantara`). You own this mandate end to end: review → merge → arm → deploy → prove-live. The codeowner does not merge, review or deploy. Pin every subagent's model in the Agent call: `sonnet` for readers and implementers, `haiku` for grunt work, `opus` only for a final on-disk gate. An unpinned subagent inherits your model. Builder Contract: every PR gets its own worktree from `scripts/agent_start.py`, cut from a fresh origin/main. One PR, one concern, ≤~400 net lines. Every PR body carries a `Bites:` line naming the consumer and the observation that proves the change is live. Arm auto-merge when you open the PR; from then on the branch is frozen. Push, create and merge are three separate commands. Never rerun a red check until you know why it is red. Three reds for the same cause → suspend and write the spec. A fix-of-a-fix stops at depth 1. Reaching a Claude model through a paid per-token Anthropic endpoint is banned as an entity: use the `claude` CLI with `CLAUDE_CODE_OAUTH_TOKEN` only, and refuse any tool, MCP server or cron that needs `ANTHROPIC_API_KEY`, `from anthropic import Anthropic`, a renamed variable, a wrapper or a Bedrock/Vertex route. PII is an output boundary: no PR body, log, alert, memory, ledger row or report carries client PII or OSINT in cleartext. Off-limits files: `zantara_core.py`, `fly.toml`, `.env*`, `apps/bali-intel-scraper/backend/db/migrations/env.py`. Never edit Zero's own files: `~/.claude/CLAUDE.md`, branch protection, required-context lists. File operator items as a PENDING-ARMS row with the exact ask, and never wait on them.

MISSION
Repair the merge queue's re-armer so it can actually re-arm. Make its failures honest, make the three-reds suspension mechanical, and add the pre-push floor gate. Prove it with consecutive live ticks, not with a diff.

GROUND (judge 2026-09-10T13:02–13:09Z, red-team re-run about an hour later; re-derive ALL of it in your first hour)
- `grep -c 'rearmed=0 cancelled=0' ~/logs/queue-shepherd.err.log` against `grep -c '^tick complete' ~/logs/queue-shepherd.err.log` → 1879/1880 at the judge's read, 1880/1881 at the red-team's. The pair grows every 10 minutes, so re-measure and quote your own.
- `tail -6 ~/logs/queue-shepherd.err.log` → `CANNOT-VERIFY rearm candidates: gh api graphql failed rc=1: gh: HTTP 502`, then `tick complete: rearmed=0 cancelled=0 dry_run=False`.
- Flags: `python3 scripts/queue_shepherd.py --help` → `[-h] [--tick] [--report] [--dry-run]`. There is no `--json`. `--dry-run` on its own prints usage and exits 1. `--tick --dry-run` reproduces the 502, but that dry-run tick reported `cancelled=6` for runs the live janitor skips as known-uncancellable. A dry-run tick is not a stand-in for a live one.
- The cause is query complexity, not the rate limit. A reader saw 4741/5000 remaining while the same query 502'd, with `Resource limits for this query exceeded`.
- The heavy query fails on its own. At the red-team's read, `gh pr list -R Bali-Zero/Teman2 --state open --limit 200 --json number,mergeStateStatus,isDraft,autoMergeRequest` returned 46 open, 0 UNKNOWN, 10 armed. An hour earlier the judge had seen 45 UNKNOWN and 11 armed. Open, armed and CLEAN counts drift hourly: re-measure at start, and never paste a sweep count into a PR body.
- PR #6100 merged at 2026-09-10T12:55Z. At floor 2, a missing `harness/fable-gate` verdict now fails `Harness floor recompute`. Mini's fleet-watch is posting `gate-verdict-missing` stalls on several PRs. That is how the queue behaves after #6100; it is not a shepherd bug.
- Required contexts: `gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks --jq '.contexts|length'` → 13, matching `infra/required.d/contexts.json`. The "27" is a stale sentence of prose.
- Deploy path: the LaunchAgent `com.nuzantara.queue-shepherd` (10-minute interval) runs the script from `~/nuzantara`, which `com.nuzantara.git-pull-main.15min` keeps at origin/main. A merged fix goes live only after that puller has run.

DISEASE
Superscar #2 on the ship lifecycle itself. The re-armer exists, is scheduled and contains `gh pr merge --auto`. But it swallows its own GraphQL failure and exits 0, so its monitor stays green while the organ does nothing. "Could not read" must never look like "found nothing".

SCOPE IN
1. Fix the shape of the rearm-candidate query in `scripts/queue_shepherd.py` (paginate, cut node depth, or split the fetch) until it stays inside the resource limit. This is the core.
2. Honest failure: a tick that could not verify its candidates reports CANNOT-VERIFY as its own outcome, writes a non-ok heartbeat through `_write_heartbeat` and exits non-zero. It never prints `rearmed=0` as though it had looked.
3. Enforce Builder Contract rule 1 in code: three reds for the SAME cause suspends the PR instead of starting a fourth round. Separate PR, with a test.
4. From C9, one deliverable only: a local pre-push check that refuses to push a change whose evidence floor is ≥2 when no brief is attached. That defect produced #6066, #6065 and #6061. Re-baseline it against the post-#6100 rules. Separate PR. If it gets a CI twin, the twin lands advisory-only.
5. Arm and merge the PRs that are genuinely CLEAN when YOU re-derive the list. Some CLEAN PRs were ejected from the queue for a non-INFRA reason: #6099's last `RemovedFromMergeQueueEvent` reads `reason=merged`. By the shepherd's own rule only INFRA ejects auto-rearm, so arm those by hand, and don't read their `rearmed=0` as a failed fix. File a PENDING-ARMS row (owner + cause) for every PR you leave unresolved.
6. Mini's sibling scripts: `queue_unstick` reports `updated=0` with `rewarm_reason='below_floor(0<5)'`, and `queue_stall_notify` suppresses most stalled PRs on each tick. Read both before you declare the family cured. If their floor logic needs a fix, it gets its own PR.

SCOPE OUT
- #5037: its `harness/fable-gate` verdict is a correct depth-4 suspension ("split recommended"). It needs a spec, not a re-trigger.
- #5528/#5529 (dependabot): resolving them means touching the auto-merge author allowlist, which is Zero's call.
- The overall open-PR count as a target, fixing individual PRs' tests (that belongs to a sonnet grunt lane), and the 27-vs-13 item.
- PENDING-ARMS.md structure, the escalation bus and `scripts/tg_notify.py` belong to S4. `queue_shepherd.py` is one of the 29 top-level scripts that call tg_notify; don't change the gateway from here.
- The author allowlist in `.github/workflows/auto-merge-whitelist.yml`.

OPERATOR BOUNDARY
Two items, both filed, neither blocking: the dependabot ruling, and any promotion of a new check to REQUIRED.

METHOD
First hour, in order:
1. Run `python3 scripts/agent_start.py --help`, then `python3 scripts/agent_start.py --lane ops --task-id arm-the-armer`. The branch comes out as `agent/nuzantara/ops/arm-the-armer`: the host segment is the OS short hostname, and `ci` is not a known lane.
2. Before you trust the 60-minute clock for Bite 1, confirm the sync organ is healthy. `tail -5 ~/logs/pro-git_pull_main/run.log` and `cat ~/.organism/last_seen/pro.git_pull_main.json` should show a recent rc=0 and status ok. If they don't, your merged fix never reaches the LaunchAgent, and Bite 1 will look like a fix that failed.
3. Run `python3 scripts/queue_shepherd.py --tick --dry-run` (capture the 502).
4. Re-derive the open, armed and CLEAN lists live.
5. Read the rearm-candidate query, the eject classifier and `_write_heartbeat`. Only then write.
Expect 4 PRs (query shape, honest failure, suspend enforcer, pre-push gate), plus one for Mini's siblings if needed. Serialize any two PRs that share a lockfile.

BITES (each with its proving command)
- Bite 1. Consumer: the scheduled shepherd. After merge, prove the live checkout contains your commit (`git -C ~/nuzantara merge-base --is-ancestor <sha> HEAD && echo live`). Then paste six consecutive `tick complete` lines (~60 minutes) that each log how many candidates the tick examined and contain no CANNOT-VERIFY. `rearmed=0` is only legitimate when an examined count sits next to it.
- Bite 2. Consumer: the same log and the heartbeat. Force one read failure, in a test or a controlled run, and show the tick reports CANNOT-VERIFY, writes a non-ok heartbeat and exits non-zero.
- Bite 3. Consumer: named PRs. List every PR your runs armed or merged, with timestamps. Never claim the overall count.
- Bite 4. Consumer: the pre-push hook. Push a synthetic floor-2 change with no brief, show it blocked, then revert the synthetic change.
- Bite 5. Consumer: the suspend enforcer. A test with three reds from one cause shows the PR suspended; a test with three reds from different causes shows it isn't.

RISK CONTROLS
- Re-derive every count live. Each number in a PR body carries the command that produced it.
- PENDING-ARMS.md uses `merge=union`, and the conflict is live now: #6080 and #6081 are DIRTY on it, and #6101 is DIRTY and touches it too. Append on a branch cut from a fresh origin/main, then check that `git diff origin/main -- .claude/skills/modus/PENDING-ARMS.md` is +N/-0. Never hand-resolve the file and never rebase onto it.
- Never blind-rerun a red check: a blind rerun replays a stale merge ref.
- Never `--dangerously-bypass` a sandbox. Never echo a credential.

STOP CONDITIONS
Stop and file a row if the query fix needs a change on GitHub's side that you can't make, if you get three reds for the same cause, if you catch yourself wanting to widen the auto-merge allowlist, or if the fix would change what a REQUIRED context means.
