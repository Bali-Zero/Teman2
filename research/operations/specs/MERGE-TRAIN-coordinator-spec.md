# MERGE-TRAIN — serialized merge coordinator + self-healing main (spec v2)

**Date**: 2026-06-12 · **Author**: Claude (Fable 5) session filo1-lead-funnel · **Status**: PANEL-REVIEWED (v2) — pending Antonello GO
**Panel 2026-06-12**: Codex GPT-5.5 (28 findings) + DeepSeek V4 Pro (12 findings) + Claude internal review → 5 real defects incorporated in §10 (which OVERRIDES conflicting text in §3-§6); 4 false positives dismissed with live verification (gh auth valid; `require_last_push_approval=false`; `dismiss_stale_reviews=false`; SPOF-on-Pro is graceful degradation by design, Law 4/6).
**Design directive (Antonello 2026-06-12, memory `decision` imp.9)**: *no human-first alerts* — alarms feed the SYSTEM, which intervenes and repairs; Zero is notified ONLY when self-repair fails (SYMBIOSIS Law 5, "Zero come ultima istanza").

---

## 1. Problem (measured 2026-06-11)

19 PRs with auto-merge armed on a `strict=true` main: every merge invalidated the other 18 → each re-ran `update-branch` → full CI suite (~40 min) restarted for all → throughput ~1 merge/40min, massive Actions waste, sessions (Pro + M5) blocking each other.

Emergency mitigation shipped 2026-06-11: `strict=false` (after a 2-agent risk analysis: 12/19 PRs disjoint, no migrations/registries touched, main still covered by push-main suite + fly-deploy gate). Residual risk accepted temporarily: **semantic conflict** — two individually-green PRs that break main only when combined; detection today is a SILENT red `tests.yml` run on main (no notification, no action).

GitHub native Merge Queue is NOT available: repo is user-owned (`Balizero1987`), queue requires org-owned repos. Migration to an org is the long-term fix; this spec is the until-then regime.

## 2. Target regime (end state)

```
sessions (Pro/M5/anyone) ──arm auto-merge──▶ FIFO queue (= open PRs with auto-merge)
                                                  │
                                   MERGE-TRAIN coordinator (one instance)
                                   updates ONLY the head PR; waits; next
                                                  │
                                       main (strict=true restored)
                                                  │
                              push-main suite fails? ──▶ AUTO-REVERT guardian
                                                  │            │ revert-PR (enters the train)
                                                  │            │ comment on culprit PR
                                                  ▼            ▼
                                            green main     Telegram to Zero ONLY if
                                                            revert itself fails
```

Sessions change NOTHING in their workflow (arm auto-merge as today). The coordinator serializes; the guardian repairs; Zero is out of the operational loop.

## 3. Component A — merge-train coordinator

### 3.1 Placement & lifecycle

- **Runs on the Pro** as LaunchAgent `com.nuzantara.merge-train` — **one-shot script + `StartInterval=180`** (cron-style; NO KeepAlive — W67 lesson: KeepAlive+one-shot = crash-loop signature).
- Single-instance safety: flock on `~/.agent/merge-train.lock` (skip tick if held). NEVER install on Mini too (active-active scar, 2026-05-07 family).
- Auth: existing `gh` CLI auth on the Pro. **Constraint**: `gh pr update-branch` via user PAT/gh-auth DOES trigger CI on the PR (unlike GITHUB_TOKEN pushes from within Actions, which suppress downstream workflows — this is WHY the coordinator lives on the Pro and not as a scheduled GitHub workflow).
- Kill switches: `MERGE_TRAIN_ENABLED=false` in plist env; per-PR opt-out label `no-train`; `launchctl bootout`.

### 3.2 Tick algorithm (one-shot, idempotent)

```
1. queue   = open PRs with autoMergeRequest != null AND label != "no-train",
             ordered by PR number ASC (FIFO; number ≈ creation order)
2. skiplist = entries in state file ~/.agent/merge-train-state.json
              (auto-expire: 4h TTL OR a new push to the PR branch clears it)
3. head    = first queue entry not in skiplist
4. inspect head:
   a. mergeStateStatus == DIRTY/CONFLICTING
        → skiplist + ONE comment on the PR:
          "merge-train: conflicts with main — resolve and push to re-enter the queue"
        → continue to next candidate (max 1 action per tick still respected: comments are cheap, update-branch is the rate-limited action)
   b. any required check == FAILURE on the CURRENT head sha
        → first time: re-run failed checks once (`gh run rerun --failed`) [flake re-roll]
        → second time: skiplist + ONE comment ("merge-train: red checks — fix and push")
   c. mergeStateStatus == BEHIND
        → `gh pr update-branch` (THE serialized action — at most ONE per tick, globally)
   d. checks running / BLOCKED → do nothing (wait)
   e. CLEAN + up-to-date → nothing to do: GitHub's own auto-merge completes it
5. write state file: ts, head, queue_depth, skiplist, last_action
   (alive-signal consumed by the existing deadman/sentinel — W64 "esistere ≠ armato")
```

Properties: starvation-free (FIFO + skiplist never blocks successors), thrash-free (≤1 update-branch per tick repo-wide), zero coupling with sessions, graceful degradation (Pro asleep → PRs simply wait, nothing breaks — Law 4).

### 3.3 What it does NOT do

- Never merges with `--admin`, never closes PRs, never force-pushes, never edits PR content beyond its two canned comments.
- Does not manage PRs without auto-merge armed (drafts, WIP, human-review-pending stay untouched).

## 4. Component B — auto-revert guardian (main self-healing)

### 4.1 Trigger & placement

GitHub Actions workflow `main-autorevert.yml`, `on: workflow_run` of the main test suite (`Backend Tests` umbrella) `types: [completed]`, filtered `branches: [main]`, acting only when `conclusion == failure`.

### 4.2 Action sequence

```
1. culprit = workflow_run.head_sha  (squash merges + serialized train ⇒ 1 push = 1 PR;
   if multiple pushes landed between green→red, ABORT to escalation — never guess)
2. guards (ALL must pass, else escalate instead of acting):
   - culprit commit does NOT carry label/marker "auto-revert" (never revert a revert)
   - ≤ 2 auto-reverts in the last 24h (circuit breaker)
   - culprit is a squash-merge commit mappable to a PR
3. create branch revert/<sha>, `git revert -m`/plain revert, open PR
   with label "auto-revert" + arm auto-merge → it enters the train head-queue
4. comment on the culprit PR: "auto-reverted from main (run <url>); branch intact —
   fix and re-submit" → the owning session finds the work back in its court
5. Telegram to Zero ONLY on: revert conflict, ambiguous culprit, circuit-breaker open,
   or guardian internal error  (escalation = self-repair exhausted)
```

**PAT requirement**: the revert-PR must trigger CI → created with the PAT already in repo secrets (`GH_TOKEN`), not the workflow's `GITHUB_TOKEN`.

### 4.3 Failure containment

- The guardian only ever ADDS a revert-PR (which itself passes through CI + train). Worst case of a guardian bug = a wrong-but-green revert PR, visible and revertable. It cannot push to main directly.
- Flaky-suite protection: before acting, re-run the failed jobs once; only a CONFIRMED red triggers the revert path (clock-race scar: `test_duplicate_alert_id_skipped` family).

## 5. Component C — restore `strict=true`

Once A is enforcing and stable (gate G3), flip back `required_status_checks.strict=true`. The train absorbs the serialization cost that made strict=true unlivable; semantic-conflict risk returns to ~zero; component B remains as the backstop for the residual (e.g. direct pushes).

## 6. Rollout phases & falsifiable gates

| Phase | What | Gate to advance (falsifiable) |
|---|---|---|
| 0 — observe | coordinator in DRY-RUN: logs the action it WOULD take each tick, 24h | ≥95% of logged decisions match what a human would do on inspection of 10 sampled ticks; zero crashes; alive-signal fresh |
| 1 — enforce (strict still false) | coordinator acts (update-branch/comments) | 48h: zero wrong update-branch (i.e. never updated a non-head PR), zero duplicate instances (lock held), queue drains monotonically |
| 2 — strict=true flip | restore strictness | 72h: ≥8 merges/day sustained with queue ≥3; no PR stalled >3h with green checks; Actions minutes/merge ≤ 1.2× single-suite cost |
| 3 — auto-revert armed | enable B beyond dry-run | staged drill: intentionally-broken trivial commit on a Friday-night window → guardian reverts to green main in ≤30 min without human input; culprit PR commented; Telegram only on drill's forced-failure case |

Each phase has its own kill switch; rollback = previous phase.

## 7. Observability (system-facing, per the no-human-alerts directive)

- State file `~/.agent/merge-train-state.json` (alive-signal) → added to the existing deadman `OBSERVED_FILES` (cost_breaker_deadman.sh pattern) — the watcher-of-watchers notices a dead train without involving Zero.
- Weekly digest line in the existing reflexion/ops digest (queue throughput, skiplist hits, reverts count) — informational, not actionable.

## 8. Open questions for the panel

1. FIFO by PR number vs by "armed-at" timestamp — number is stable but penalizes long-lived PRs re-armed late; is that acceptable?
2. Should the train PAUSE when the fly-deploy workflow is mid-rollout on main (avoid merging during a deploy)? Cheap check: skip tick if a `fly-deploy` run is in_progress.
3. Flake re-roll (one `rerun --failed`) — is one enough, given the known clock-race tests?
4. Auto-revert for mouth/Vercel breaks: Vercel build failure does NOT show as a red GitHub check on main — out of scope v1, acceptable?
5. Is 180s tick + ~40min CI a sane duty cycle, or should the tick adapt (e.g. 60s when queue>5)?

## 9. Out of scope (v1)

- Org migration + native Merge Queue (tracked separately; this spec becomes obsolete the day that lands — by design).
- Batching (testing N PRs combined like GitHub's queue): explicitly rejected for v1 — complexity ≫ benefit at current merge volume.
- Cross-repo coordination.
- Vercel/mouth build failures (do NOT appear as red GitHub checks on main — verified): coverage stays the existing post-deploy QA; one status line in the weekly digest. A Vercel API poller is wrong cost/benefit for v1.

---

## 10. REV 2 — panel findings incorporated (2026-06-12, OVERRIDES §3-§6 where conflicting)

### 10.1 Red-main mode + revert priority (panel defect #1 — Codex 7/12, DeepSeek 4)

§3.2 FIFO-by-number would put an emergency revert-PR (highest number) at the BACK of the queue while the coordinator keeps update-branching normal PRs onto a broken main (false failures → unjust mass-skiplisting). Corrected behavior:

- **Tick precondition**: if the latest required suite run on `origin/main` HEAD is red OR a guardian incident is active → the train PAUSES for normal PRs (no update-branch, no skiplist mutations, no comments).
- **Priority lane**: PRs labeled `auto-revert` jump to absolute queue head.
- **Guardian watches its own revert-PR**: if the revert does not reach merge within 30 min, THAT is "self-repair exhausted" → Telegram to Zero. (Closes the DeepSeek-4 gap: a failed repair could otherwise rot silently.)

### 10.2 Phase-3 prerequisite: main must test every commit (internal-review finding — neither external LLM saw it)

`tests.yml` uses concurrency group `tests-${{ github.ref }}` with `cancel-in-progress: true` — ALSO on main. Back-to-back merges cancel the in-flight main run → commits land untested and the guardian's green→red window spans multiple pushes, making ABORT-to-escalation the COMMON case (defeats the prime directive). **Prerequisite fix before Phase 3**: `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` (PR runs keep cancelling, main tests every commit).

### 10.3 update-branch is async and race-prone (panel defect #3 — Codex 5/6/13/14/17/19, DeepSeek 3)

- Use the REST endpoint with `expected_head_sha` (the `gh pr update-branch` CLI does not expose it); on 422 → re-fetch and retry next tick. Never blind-update.
- 202 = queued, not done: poll until `headRefOid` changes and checks attach to the new SHA before recording "updated".
- Flake re-roll: resolve exact run IDs for the head SHA and rerun those; keep retry-state keyed `(pr, head_sha, run_id)` so a queued/running rerun is never misread as a second failure, and the re-roll happens at most once per SHA.
- Any API error on the head → skiplist with `reason=api_error` (visible, retried on TTL) instead of a silent stuck head.
- Skiplist keys are `(pr, head_sha, reason)` and clear ONLY on a new push (new SHA) — kills the every-4h re-comment spam; TTL applies only to `api_error` entries.
- `mergeStateStatus == UNKNOWN` → re-query with backoff; never mutate on a stale snapshot. `BLOCKED` is classified via GraphQL blocker fields: automation-resolvable (checks running) → wait; human-only (review/conversation required) → skiplist + one comment.

### 10.4 Progress-aware liveness (panel defect #4 — DeepSeek 5/3; the concrete prime-directive violation)

A fresh state-file mtime does NOT mean the train works (dead token → every tick "succeeds" at writing state while the queue never drains). The alive-signal carries SEMANTICS:

- `last_successful_action_ts` (last update-branch/merge observed), `head_pr`, `head_unchanged_since`, `queue_depth`, `auth_ok` (per-tick `gh api user` preflight).
- Deadman rule: alert on **no-progress** (`queue_depth>0` AND `head_unchanged_since > 3h`) or `auth_ok=false` persisting — not on mtime.
- Self-repair first: deadman attempts ONE `launchctl kickstart` before any human alert.

### 10.5 Revert mechanics corrected (panel defect #5 — Codex 8/9/10/11, DeepSeek 12)

- Commits cannot carry labels: "never revert a revert" is enforced via `[auto-revert]` marker in the squash title + commit→PR mapping.
- Squash commits are single-parent: `git revert <sha>` plain; `-m 1` ONLY for true merge commits (parent-count check).
- Act only when `workflow_run.head_sha == origin/main` HEAD and no newer run supersedes the failure.
- Actions `concurrency` group + per-SHA idempotency key → no duplicate revert-PRs from parallel failure events.
- Circuit breaker counts AUTO reverts only (marker-based), not manual reverts.

### 10.6 Open questions resolved (panel §c)

1. FIFO by PR number — confirmed (deterministic; low number = old PR = head, which is correct), with the `auto-revert` priority-lane exception (§10.1).
2. Pause on in-flight `fly-deploy` run — YES, global pause (one `gh run list` check per tick; ~3 ticks of wait per rollout).
3. One flake re-roll — confirmed sufficient (residual ≈ p²) given keyed retry-state; on the GUARDIAN path the rerun is awaited to conclusion (never timeout→"confirmed red": the cost there is reverting an innocent PR).
4. Vercel out of scope v1 — confirmed (moved to §9).
5. Fixed 180s tick + ±30s jitter (avoid cron sync against the API); adaptive ticking rejected — CI duration dominates, tick overhead ≤7%.

### 10.7 Implementation notes

- macOS has no `flock(1)`: single-instance lock via `mkdir`-lock or `python fcntl`, with hard timeout + stale-lock diagnostics in the state file (a hung script must not hold the lock forever).
- LaunchAgent env under launchd: absolute paths for `gh`/python, explicit `PATH`, `WorkingDirectory`, log paths, wrapper timeout (Codex 22).
- Kill switch read from a runtime config file each tick (`~/.agent/merge-train.config`), not only plist env (live toggle without reload).
- `strict=true` restore via the specific `required_status_checks` PATCH endpoint (never a broad protection PUT — risk of zeroing unrelated settings).
- Auth/scopes preflight every tick (cheap `gh api user`) — feeds `auth_ok` in the alive-signal.
