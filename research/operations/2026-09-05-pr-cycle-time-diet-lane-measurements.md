---
date: 2026-09-05
domain: operations
client_case: none — internal PR-cycle-time study, raw measurement lane (sibling of 2026-09-05-pr-cycle-time-diet.md)
adversarial_review: codex
sources: gh api (repos/Bali-Zero/Teman2), GraphQL mergeQueue introspection — all fetched live in this session, 2026-09-04/05
---

# PR cycle-time — raw measurement lane

> Companion to `2026-09-05-pr-cycle-time-diet.md`. This file is the evidence: every number in the
> main report's §1 traces back to a table here. Method in one line: 30 most-recently-merged PRs on
> `Bali-Zero/Teman2` (all merged 2026-09-04, 08:21–15:35 UTC, a 7h14m window — this was a
> high-velocity day, not a representative week; treat medians as this-session, not annual, truth),
> `gh api repos/Bali-Zero/Teman2/actions/runs?head_sha=<PR head SHA>` per PR for `pull_request`
> runs (bypasses the Actions-runs-list 1000-item cap that a plain `event=pull_request&created=...`
> query hits — verified live: total_count 3054 for the window, only the newest ~700 fit in 1000
> paginated rows, and worse, the `pull_requests[]` field GitHub attaches to a run is *cleared once
> the PR merges or closes* — so matching old runs to old PRs by that field silently loses most of
> the sample. `head_sha` filtering sidesteps both). `merge_group` runs matched by parsing the PR
> number out of `head_branch` (`gh-readonly-queue/main/pr-<n>-<sha>`) — GitHub does not expose a
> `pull_requests[]` link for merge-group runs. Job-level timing (`actions/runs/{id}/jobs`) fetched
> only for the two multi-job workflows that contain the required checks (`Tests & Coverage`,
> `Security Scanning`); every other workflow's job IS the run, so run-level `created_at` /
> `run_started_at` / `updated_at` stand in for queue-wait / duration without an extra call per run.
> Total API calls: ~30 (PR metadata) + ~30 (head SHA) + ~30 (PR-event runs) + 30+39 (TC jobs) +
> 30+39 (Security jobs) ≈ 228, well inside the 5000/hr authenticated budget (0 used before this
> session per `gh api rate_limit`).
>
> **Per-PR vs per-batch attribution, checked not assumed.** `merge_group` batches up to 5 queue
> entries (`maximumEntriesToBuild: 5`, §5) into one merge attempt, raising the question of whether
> the `pr-<n>-<sha>` in a run's `head_branch` names the WHOLE batch (in which case matching by
> that number would misattribute a shared batch's runs to one PR) or one temporary ref per queue
> entry. Checked directly: across all 487 matched `merge_group` runs, zero `head_sha` values are
> shared across two different `pr_number` values — every entry has its own unique temporary
> commit. Consistent with GitHub's documented cumulative-batch build (entry N's temp branch
> contains entries 1..N but is still built and reported under entry N's own PR number) — per-PR
> attribution below is exact, not inferred.

## 1. Sample

30 PRs, numbers 5648–5685 (not contiguous — 5661, 5664–5666, 5669, 5673, 5675, 5682 are excluded:
either not merged or fell outside the most-recent-30 window). Every PR in the sample went through
the required-checks gate and the merge queue; none was an admin override.

## 2. Open → merge wall time, per PR (minutes)

| PR | wall (min) | PR | wall (min) | PR | wall (min) |
|---|---|---|---|---|---|
| 5680 | 28.3 | 5670 | 35.1 | 5654 | 48.6 |
| 5658 | 29.5 | 5662 | 35.3 | 5649 | 50.5 |
| 5677 | 31.1 | 5667 | 37.1 | 5652 | 54.9 |
| 5663 | 31.2 | 5679 | 37.2 | 5657 | 61.0 |
| 5683 | 31.4 | 5681 | 39.2 | 5674 | 67.8 |
| 5685 | 31.5 | 5659 | 44.2 | 5651 | 83.0 |
| 5671 | 31.8 | 5648 | 44.5 | 5676 | 116.4 |
| 5668 | 31.9 | | | 5650 | 123.5 |
| 5656 | 33.0 | | | 5653 | 173.1 |
| 5684 | 33.2 | | | | |
| 5672 | 33.7 | | | | |
| 5678 | 33.7 | | | | |
| 5655 | 34.2 | | | | |
| 5660 | 34.4 | | | | |

**median 35.2 min · mean 50.0 min · min 28.3 (#5680) · max 173.1 (#5653).** Six PRs exceed 60
min (#5657, #5674, #5651, #5676, #5650, #5653); §5 shows only 4 of those 6 are explained by a
merge-queue requeue (#5674, #5651, #5650, #5653) — #5657 and #5676 are not.

## 3. Top-15 jobs by total minutes, `pull_request` event (30 PRs)

| job | total min | median dur (min) | median queue (s) | n |
|---|---|---|---|---|
| CodeQL Analysis (python) | 363.3 | 13.69 | 70 | 30 |
| Frontend Tests (Next.js) (mouth, true) | 281.3 | 7.81 | 68 | 30 |
| E2E Tests (Playwright) | 257.4 | 7.57 | 70 | 30 |
| Backend Shard 2 | 185.2 | 5.60 | 68 | 30 |
| Visa Oracle fullstack smoke | 173.1 | 6.03 | 71 | 30 |
| Backend Shard 3 | 167.0 | 5.09 | 68 | 30 |
| Backend Shard 1 | 162.9 | 5.36 | 68 | 30 |
| npm audit (advisory) | 149.0 | 2.40 | 69 | 30 |
| Backend Static (Python) | 104.1 | 3.28 | 70 | 30 |
| Immune enforcement (superscar antidotes) | 91.5 | 2.02 | 0 | 30 |
| SAST — Bandit + ESLint Security | 89.6 | 1.77 | 0 | 22 |
| Snyk Node.js Security | 74.8 | 1.87 | 70 | 30 |
| CodeQL Analysis (javascript) | 70.2 | 3.17 | 71 | 30 |
| Snyk Docker Security | 68.2 | 2.31 | 70 | 30 |
| Frontend Tests (Next.js) (admin-dashboard, false) | 65.9 | 1.57 | 70 | 30 |

"queue" = job `started_at` − run `created_at`; for `needs:`-gated jobs (e.g. a fan-in summary
after three shards) this also absorbs upstream wait, so it over-states pure runner-allocation
delay for those specific jobs — noted, not corrected, because the jobs it affects (Test Summary,
Backend Tests (Python) as a context) are not in this top-15 by duration.

Total `pull_request`-event runner-minutes across all jobs, 30 PRs: **3320.7**, mean **110.7
min/PR** — matches the 110–114 CPU-minutes the team lead measured on 2026-09-04 evening on a
different (3-file scripts-only) PR to within rounding. Cross-validates the method.

## 4. Same, `merge_group` event (matched to the 30 PRs by branch-name PR number)

39 matched runs per workflow (not 30 — see §5: nine PRs re-entered the queue).

| job | total min | median dur (min) | n |
|---|---|---|---|
| CodeQL Analysis (python) | 515.9 | 14.78 | 39 |
| Frontend Tests (Next.js) (mouth, true) | 394.6 | 8.60 | 39 |
| E2E Tests (Playwright) | 344.6 | 7.32 | 39 |
| Backend Shard 2 | 307.8 | 7.12 | 39 |
| Backend Shard 1 | 298.4 | 7.38 | 39 |
| Backend Shard 3 | 276.6 | 6.72 | 39 |
| Immune enforcement (superscar antidotes) | 248.1 | 6.50 | 39 |
| npm audit (advisory) | 200.1 | 5.63 | 39 |
| Visa Oracle fullstack smoke | 195.3 | 3.90 | 39 |
| Backend Static (Python) | 145.1 | 3.25 | 39 |
| Detect Secrets | 118.3 | 2.88 | 39 |
| Frontend Tests (Next.js) (admin-dashboard, false) | 117.2 | 1.78 | 39 |
| CodeQL Analysis (javascript) | 106.6 | 4.02 | 39 |
| Snyk Docker Security | 92.6 | 2.32 | 39 |
| Snyk Node.js Security | 91.8 | 1.83 | 39 |

Total `merge_group`-event runner-minutes: **4090.1**, mean **136.3 min/PR** — the re-run in the
merge queue costs *more* CPU than the original PR check run (110.7). Combined CI cost per merged
PR in this sample: **≈247 runner-minutes**, and roughly half of it (136.3/247 = 55%) is the
re-run that happens *after* the PR already went green once.

## 5. Merge-queue requeue (`mergingStrategy: ALLGREEN`)

Live GraphQL introspection of `repository.mergeQueue.configuration`
(`Bali-Zero/Teman2`, fetched this session):

| field | value |
|---|---|
| `checkResponseTimeout` | 5400 s (90 min) |
| `maximumEntriesToBuild` | 5 |
| `maximumEntriesToMerge` | 4 |
| `minimumEntriesToMerge` | 4 |
| `minimumEntriesToMergeWaitTime` | 900 s (15 min) |
| `mergingStrategy` | `ALLGREEN` |
| `mergeMethod` | `SQUASH` |

`ALLGREEN` enum description (fetched live): *"Entries only allowed to merge if they are
passing."* The alternative, `HEADGREEN`: *"Failing Entries are allowed to merge if they are with
a passing entry."* GitHub's own text is the only documentation of the mechanism reached in this
session (the dedicated `managing-a-merge-queue` doc page 404'd on fetch, twice, from two
different URL guesses) — read the two enum strings as read, not expanded into "avoids cancelling
N others", which this session cannot verify without the doc page or a controlled reproduction.

9 of 30 PRs (30%) have **two** `Tests & Coverage` `merge_group` runs instead of one. Full
sequence, not a sample:

| PR | 1st MG run | 2nd MG run | PR's own wall time (min) |
|---|---|---|---|
| 5648 | cancelled (08:46) | success (08:49) | 44.5 |
| 5650 | cancelled (09:05) | cancelled (10:21) | 123.5 |
| 5651 | cancelled (09:32) | success (09:40) | 83.0 |
| 5652 | success (09:05) | cancelled (09:23) | 54.9 |
| 5653 | cancelled (10:49) | success (11:41) | 173.1 |
| 5654 | success (09:25) | cancelled (09:40) | 48.6 |
| 5657 | success (10:56) | cancelled (11:06) | 61.0 |
| 5659 | success (10:53) | cancelled (11:06) | 44.2 |
| 5674 | cancelled (13:52) | success (14:15) | 67.8 |

The pattern is NOT uniform, and the report's main file does not claim it is: 5 of the 9
(5648, 5650, 5651, 5653, 5674) show `cancelled` before `success` or `cancelled`, consistent with
a batch that failed and blocked this PR's own merge until a later attempt — these five include
4 of the 6 PRs whose open→merge time exceeds 60 minutes (5650, 5651, 5653, 5674). The other 4
(5652, 5654, 5657, 5659) show `success` FIRST and `cancelled` SECOND — the PR already merged via
the successful entry, and the later `cancelled` run is a leftover duplicate from a batch the PR
was still nominally part of; it did not add wall time. PR 5650's two entries are both
`cancelled` — its 123.5 min implies at least one more attempt this query did not capture (either
a third `merge_group` run outside the matched set, or a manual re-queue); not resolved in this
session. The two outliers NOT explained by this table at all are 5657 (61.0 min, but its own
requeue happened AFTER its success, so cannot be the cause) and 5676 (116.4 min, only one
`Tests & Coverage` `merge_group` entry — its delay has a different, unidentified source).

`minimumEntriesToMerge: 4` with `minimumEntriesToMergeWaitTime: 900s`: the queue waits for a
total of 4 entries (the arriving PR counts as one of the 4) before batching. A PR that arrives
when fewer than 3 OTHERS are already queued (so the running total is below 4) can wait up to
**15 minutes** for company before GitHub gives up and starts the batch anyway — a fixed tax with
no relationship to the PR's own diff size, paid disproportionately by whoever is *not* shipping
in a burst.

## 6. Jobs finishing under 90 s (runner-spin-up dominated), `pull_request` event

53 of 72 distinct job names had a median duration under 90 seconds — the majority of the 12
required contexts included. Fastest cluster (4–7 s): `Security Summary`, `Test Summary`,
`SonarQube Analysis` (these are fan-in/summary steps, not real work). Most sentinel/lint/guard
jobs (`Root Guard`, `actionlint`, `Docs Guardian`, `Harness floor recompute`, `token-lint`, ~40
more) land in the 29–45 s band — almost entirely checkout + runner cold-start, since the guard
logic itself is a few hundred milliseconds of Python/bash.

## 7. Cancelled / failed, `pull_request` event vs `merge_group` event

| | success | skipped | cancelled | failure |
|---|---|---|---|---|
| `pull_request` (1862 records) | 1802 | 50 | 7 | 3 |
| `merge_group` (1384 records) | 1299 | 59 | 12 | 14 |

`merge_group` has a visibly higher failure rate (14 vs 3) and cancellation rate (12 vs 7) than
the `pull_request` run of the same PR. The two runs are not the same commit: `pull_request`
builds the PR's own head SHA, `merge_group` builds a temporary merge of that PR against the
current queue state (§1 methodology note) — so a `merge_group` failure can be a genuine
integration break the PR-run could never have seen, not necessarily a repeat of the same check.
This session did not read individual job logs to classify cause (§10 limit), so neither "flaky"
nor "genuine regression" is asserted here — only the raw rate difference and, from §5, that at
least some of the `cancelled` entries are the whole-batch-cancel side effect of ANOTHER queue
member's failure, not this PR's own.

## 8. Checks per PR and which one is slowest

Median 62 required+advisory checks per PR (range 57–67) by this session's run-level counting
(each non-multi-job workflow = 1; `Tests & Coverage` and `Security Scanning` sub-jobs counted
individually). The team lead's 2026-09-04 evening measurement on a different PR read 72–75 via
`gh pr checks`, which also counts re-run/duplicate entries from `merge_group` — same phenomenon,
different counting rule; not a contradiction.

Single slowest `pull_request`-event job, per PR — **CodeQL Analysis (python) is the slowest
check on 19 of 30 PRs (63%)**, Frontend Tests (mouth) on 7/30, E2E Tests on 3/30, one Backend
Shard on 1/30. Median share of total PR wall time held by that one slowest job: **34%** (min 8%
on the PR that also hit a 15 s CodeQL fast-path plus a long human-review gap, max 46%).

## 9. CodeQL path-gating: measured effectiveness

`security.yml`'s `codeql` job runs unconditionally (job-level `if: ${{ !cancelled() }}`, no path
filter — deliberately, per the in-file comment: a job-level path skip would collapse the matrix
and leave `CodeQL Analysis (python)`/`(javascript)` as required contexts that never report,
which is worse than running them). The *expensive* steps (Initialize/Autobuild/Analyze) are
gated per-language by a step-level `if: env.RUN_THIS_LANGUAGE == 'true'`, fed by the same
change-map classifier as the test-impact system.

Measured on this sample: 3 of 30 PRs (10%) finished `CodeQL Analysis (python)` in under 45
seconds (gate held, no Python touched); the other 27 (90%) ran the full 11–15 min analysis. This
session's PR mix is unusually Python-heavy (agent/fix PRs, not docs), so 90% is not a general
rate — but it confirms the gate mechanism itself works exactly as designed when a PR is clean.

## 10. What this lane deliberately did not measure

- Per-step timing inside a job (only job-level `started_at`/`completed_at`; a step-level
  breakdown of the CodeQL Analyze step vs Initialize/checkout would need
  `actions/runs/{id}/timing` or job logs, not attempted here — CPU cost/time tradeoff, flagged
  as a limit not a gap silently dropped).
- Runner-pool contention as a variable (`ubuntu-latest` hosted runners; whether Bali-Zero/Teman2
  is on standard or larger runners was not checked — the 60–70s median queue-before-start on
  most jobs is consistent with standard hosted-runner cold start, not a starved pool, but this is
  read off the number, not confirmed from billing/runner-group config).
- The single-digit-percent share of PRs that used an admin merge override (excluded from the
  sample by construction — merge-queue behavior only applies to queue-routed merges).

## Adversarial review

Seat: codex (GPT-5, `codex exec --sandbox read-only`), one round on the main report. Nine of its ten findings were arithmetic or attribution errors that were checked and corrected against the tables in THIS file (off-by-ones in job counts, a 5-vs-6 heavy-job enumeration, totals that did not reconcile, a wrong "same commit" claim); the tenth (HEADGREEN causality) was rebutted by a direct check on `merge_group` head SHAs, also recorded here. Dispositions, one per finding, live in the main report's `## Adversarial review`; this lane holds the raw rows they were verified against and carries no independent narrative to review.
