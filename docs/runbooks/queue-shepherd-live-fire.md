# queue-shepherd live-fire drill

The shepherd's READ path proves itself every ten minutes: a tick that examines every open PR,
classifies each candidate and logs a named refusal is visible in `~/logs/queue-shepherd.log`
without anyone doing anything. Its WRITE path does not. `rearm_pr` only runs when a PR is
ejected from the merge queue with an INFRA-flavoured cause, and a healthy week can pass without
one — after the 2026-09-10 ship, eight consecutive ticks logged `rearmed=0` for exactly that
reason. "Never ran" and "runs correctly" look identical in the log.

This drill closes that gap on purpose: it induces one controlled ejection and watches the
shepherd re-arm it. Superscar #2 in one line — a green cron is not a working cron, and the
only proof that a write path works is having watched it write.

## What the shepherd will see

`_run_has_infra_signature` reads a merge_group run whose own conclusion is `cancelled` (with no
job that failed for a real reason) as INFRA. `classify_ejection_reason` turns that into the
INFRA class, `decide_rearm` allows it while the per-(PR, head) budget has room
(`INFRA_BUDGET_MAX`, rolling 24 h), and `rearm_pr` runs `gh pr merge <n> --auto`. So cancelling
the merge_group run of a PR that is sitting in the queue produces precisely the ejection the
write path exists for.

## Procedure

1. **Pick a sacrificial PR.** Small, low-risk, genuinely mergeable — this document's own PR was
   the first one. Never someone else's work.
2. **Arm it and let it enter the queue.** `gh pr merge <n> --auto`, then poll
   `mergeQueueEntry` until `state` is `AWAITING_CHECKS`.
3. **Read the batch before touching it.** GitHub batches queue entries: one
   `gh-readonly-queue/main/pr-<n>-<sha>` branch can carry several PRs. Cancelling its run ejects
   EVERY PR in that batch, including other people's.

   ```
   gh api "repos/<owner>/<repo>/actions/runs?event=merge_group&per_page=100" \
     --jq '.workflow_runs[] | select(.head_branch|contains("pr-<n>-")) | .head_branch' | sort -u
   ```

   If the branch name carries a PR number that is not yours, **stop and wait** for a batch that
   is yours alone. This is the one step of the drill that can hurt somebody else.

   In practice a busy queue almost never hands you a batch of one, and two drills died here.
   Do not loosen the rule — change WHEN you arm: wait for the queue to hold no PR but yours,
   arm the subject only then, and it enters as its own batch. The guard still runs and still
   stops the drill if somebody armed in the same second.

   The rule is OWNERSHIP, not arithmetic: a batch of several PRs that are ALL yours is fine —
   the ejection costs only your own work and the shepherd re-arms it. A batch of one that
   belongs to another lane is not.

4. **Cancel the run**, not the PR — and do it FAST. A merge_group batch here finishes in
   minutes but most of its runs finish in SECONDS (change-map skips), so a poll loop that
   sleeps 12 s arrives after the fact. Poll every few seconds and cancel the moment the batch
   is confirmed yours.

   ```
   gh run cancel <run_id>                                    # plain endpoint
   gh api -X POST repos/<owner>/<repo>/actions/runs/<id>/force-cancel   # when it 409s
   ```

   **Never discard the cancel's output.** `gh run cancel` on an already-finished run answers
   `Cannot cancel a workflow run that is completed` and exits non-zero; a `>/dev/null` on that
   line turns a failed drill into one that looks successful. `queue_shepherd.py::cancel_run`
   documents the same 409 family and its force-cancel fallback — read it before improvising.

   When it lands, GitHub ejects the PR with reason `failed_checks`.

5. **Watch the next tick** (they are ten minutes apart) in `~/logs/queue-shepherd.log`:

   ```
   PR #<n> head=<sha8> class=INFRA allowed=True (infra_budget_ok(1/3))
   tick complete: examined=… candidates=… rearmed=1 …
   ```

   `rearmed=1` is the observation the drill exists to make. Anything else — `class=CODE`,
   `allowed=False`, `unverified=1` — is a finding, not a failed drill: write down what the log
   says and why before touching any code.

6. **Let it merge.** The re-arm puts the PR back in the queue; it goes through normally.

## Reading the aftermath

- The budget file records the re-arm against `(PR, head_sha)`. Three INFRA re-arms of the same
  head in 24 h exhaust it — the drill costs one.
- The red-state file records one red for the PR. Three reds with the SAME cause fingerprint
  suspend it (Builder Contract §1); one cancellation is far from that.
- The drill leaves no code behind. If you find yourself editing `queue_shepherd.py` to make the
  drill work, the drill has become a fiction — stop.

## When to run it

After any change to the classification or re-arm path, and otherwise whenever the log has shown
`rearmed=0` for long enough that nobody can say when the write path last executed.

## Drill log

One line per execution. A drill that was aborted is worth recording too: the abort condition
(a batch carrying someone else's PR) is the part of this procedure people get wrong.

| Date       | Subject PR | Outcome                                                                                                                                                                                                                                                                                                                  |
| ---------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 2026-09-11 | #6160      | MISSED — the cancel came 28 s after the group was created and 11 of the 13 runs had already completed; `gh run cancel` answered `Cannot cancel a workflow run that is completed` and the PR merged normally. Two lessons, both in the procedure below: cancel within seconds, and never discard the cancel's own output. |
| 2026-09-11 | #6163      | ABORTED BY THE GUARD — the batch carried 2 commits, so step 3 stopped the drill and cancelled nothing. Correct behaviour, and the reason the drill is hard to land: a busy queue almost never gives a batch of one.                                                                                                      |
| 2026-09-11 | this PR    | pending                                                                                                                                                                                                                                                                                                                  |
