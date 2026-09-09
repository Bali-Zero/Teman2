---
date: 2026-09-10
domain: operations
companion: 2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md
status: complete
adversarial_review: codex
model_selection: "codex (gpt-5.6-sol) via `codex exec`, blind review — no prior context of this document's authorship"
---

# PR time, merge queue and Fly/Vercel cost — study 2026-09-10

> Mandate (Zero, 2026-09-09): "best practice mondiali per ridurre ancora tempo PR e coda, e
> risparmiare i costi Fly e Vercel senza perdere tempo". Three read-only audits (Fly, Vercel,
> world practices) plus the day's measurements. Companion to
> `2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md` (R1–R6, kimi-k3 reviewed); this
> document does not re-derive that one — it adds what was measured on 2026-09-09 and the
> cost side, which the earlier study did not cover.

## 0. Two facts that reframe the question

1. **The repo is public** (`gh repo view --json isPrivate` → false) and the org is on the
   Enterprise plan. Standard GitHub-hosted runner minutes are free, and job-scheduling latency
   once a workflow is created is low (one merge-group run sampled: 14–16 sibling jobs, max 3 s
   created→started — a single correlated sample from one event, not independent queue-wait
   draws across PRs, and it does not measure how long a PR sits before a check is even
   created). CI buys **time**, not runner-minute dollars; other GitHub-side costs (artifact
   storage, LFS, cache overage) were not audited here and are assumed negligible at this
   repo's scale, not verified at zero. The dollars we track live on Vercel and Fly.
2. **The queue itself is not where PRs park.** Last 25 merged PRs: 6–27 min in the queue,
   always one enqueue, never kicked — a survivor-biased sample: PRs that were evicted, closed
   unmerged, or are still parked indefinitely are excluded by construction, so this does not
   establish that parking never happens inside the queue, only that it wasn't observed in this
   sample. The parking happens before the queue: red checks a seat has to diagnose, and PRs
   nobody armed. The 2026-09-09 changes (#6017 whitelist arms under the queue, #6020
   ledger-only tier, #6029 CodeQL never uploads in the queue, #6030 CodeQL scope, #6032 Next
   build cache, xdist for antidotes) all target those two; §1 below shows which are confirmed
   by a measured after-value and which (Next cache, xdist) are shipped but not yet confirmed
   effective.

## 1. Shipped 2026-09-09 (measured before → after)

| Lever | Before | After | Pays on |
|---|---|---|---|
| CodeQL scope diet (#6030) | python 15 min, js 4 min | 7 min, 2 min (single PR observation — n=1, not a run-count baseline) | every python/js PR and batch |
| CodeQL `upload: never` on merge_group (#6029) | 10 of 54 merge-group Security runs red ("ref … not found") | 0 of that class on one subsequent green run (7m50s) — one clean run does not establish a 0/54-comparable rate | every batch with python |
| Next `.next/cache` for E2E (#6032) | "Run E2E tests" 244 s (tests themselves 69 s) | not yet measured — no warm-cache PR run observed as of this writing; do not read this row as a confirmed before/after | every mouth PR and batch |
| antidotes unit tests under xdist (in flight) | 116 s sequential (CI) | not yet run on CI; local pilot only: 288 s sequential → 161 s under xdist (−44 %) on a dev machine; the "~65 s expected on CI" figure is an extrapolation (scaling the local ratio onto the 116 s CI baseline), not an observation, and local/CI CPU counts differ | every immune-zone PR and batch |
| ledger-only antidotes tier (#6020, 09-09) | 6 min | ~1 min (this one check, measured) | ≥9 ledger PRs/day |
| whitelist arms under the queue (#6017) | dependabot PRs waited days | armed at open (#6028 proved) | every dependabot PR |
| stall notifier on Mini | first run timed out (collided with unstick at :00) | staggered to :07/:37, timeout 300 s, alive | every 30 min |

Typical python/frontend PR: longest required check 15 → 7–8 min in both lanes (from the
single-PR CodeQL observation above, not a cohort measurement). Open→merge time was not
re-measured end-to-end after these changes; ~20–25 min is a projection from the check-time
reduction, not an observed floor — treat it as directional until the next 25-PR median is
pulled, the same way the 08-28 study's 61-min median was pulled. Ledger-only PR: the
antidotes-tier check itself moved 6 → ~1 min (measured, single check); the ~15 → ~5 min
end-to-end figure is the same kind of projection, not a re-measured median.

## 2. Vercel — the largest identified cost lane (not proven to be "the real money" overall — see item 6)

Team `nuzantara-2026`, plan **Pro**. Two projects: `mouth` (apps/mouth) and `knowledge`
(dormant 184 days). No Vercel check is required on `main`, so nothing below touches merge time.

Measured (git log on origin/main, 7 days to 2026-09-09; Vercel deployments API, 2 h window —
the per-merge build claim below extrapolates the 2 h sample's rate onto the full 7-day merge
count, it is not a direct 7-day observation of every build):

| Signal | Value |
|---|---|
| merges to main / 7 days | 300 |
| of which touching `apps/mouth`, `packages/`, lockfile | 78 (26 %) |
| production builds triggered | one per merge (rate extrapolated from the 2 h window, see above); ~6 min average → ≈220 builds/week (≈1,300 build-min) outside the three named paths — "outside the named paths" is a path-based proxy for "no frontend change", not a verified content diff, and ~6 min is an average being multiplied as if exact |
| preview deployments | one per push on every branch, **including `gh-readonly-queue/main/pr-*`**; 15 previews in 2 h, cancelled at ~30 s |
| `apps/mouth/vercel.json` | no `ignoreCommand`; `installCommand: cd ../.. && npm ci --include=dev` (whole monorepo, no turbo/nx) |
| `mini.vercel_autopromote` | promotes READY builds every 120 s, creates none |

Cuts, ranked:

1. **`ignoreCommand` path-scoped to mouth + packages + lockfile.** Projected to remove ~74 %
   of production builds (same 222/300 proxy above, not yet piloted) and the previews of
   unrelated branches. Risk is **not** simply low: without a dependency-graph check, a change
   that reaches `apps/mouth` indirectly (a root build script, a generated input, a transitive
   package outside the three named paths) would be silently skipped — mitigate with fail-open
   on any undecidable diff (as already planned) plus a canary period with alerting before
   trusting it unattended. Bites: a docs-only merge yields no deployment.
2. **No previews for `gh-readonly-queue/*`** (`git.deploymentEnabled`, or the same
   `ignoreCommand` on `VERCEL_GIT_COMMIT_REF`). Nobody views them. The two mechanisms are not
   interchangeable — `ignoreCommand` is a path-based skip and would not by itself suppress a
   queue preview that *does* touch mouth; `git.deploymentEnabled` is the correct lever for a
   pure per-ref suppression. Verify live before relying on either: issue vercel/vercel#11176
   reports the `git.deploymentEnabled` key being ignored in some cases.
3. **Workspace-scoped install** instead of `npm ci` of the whole monorepo: projected (not yet
   piloted) to cut the ~6 min average build to roughly 4 min — treat as an estimate until a
   real before/after run confirms it. Also shortens the promote lag of `vercel_autopromote`
   after every frontend merge.
4. Optional, Zero's call: previews off for `agent/*` except frontend/mouth/design lanes.
5. Chore: `apps/kbli-navigator/vercel.json` is dead config.
6. Unknown until read from the Usage dashboard: image-optimization transformations (9 remote
   hosts on news/blog pages), function invocations, bandwidth. Size the $ from there, not from
   guesses. Build minutes on Pro are metered on demand — take the price from the live pricing
   page when estimating.

## 3. Fly — small bill, one real decision

Org `personal`, region `sin`, everything 24/7, no dedicated IPv4. Prices fetched live.

| App / process | Shape | $/mo |
|---|---|---|
| nuzantara-rag / api | shared-cpu-2x 3 GB, `auto_stop=off`, `min=1` (cold start ~7 min per an in-repo `fly.toml` comment dated 2026-05-28 — that figure was measured on the machine's PRE-upgrade 1-vCPU shape, the comment's own stated reason for the 1→2 vCPU upgrade; it has not been re-measured on the current 2-vCPU/3GB shape) | ~17 |
| nuzantara-rag / rag | shared-cpu-2x 2 GB, worker without `[[services]]` → never auto-stops | ~12 |
| nuzantara-rag / drive | shared-cpu-1x 1 GB + one stopped standby | ~6 |
| nuzantara-postgres | 3 × shared-cpu-2x 2 GB + 3 × 25 GB volumes | ~35 + ~11 |
| **total** | 7 machines (verified 2026-09-10: `fly machines list` — 4 in nuzantara-rag + 3 in nuzantara-postgres), 77 GB volumes (verified: `fly volumes list` — 1 GB rag data + 1 GB api data + 3×25 GB postgres = 77 GB exactly) | **≈ 81** (17+12+6+35+11 sums to 81, corrected from an original ≈82) |

Cuts, ranked: (1) measure real Postgres disk use, shrink 25 → 10–15 GB per node if < 30 %
used (projected ~$5–7/mo, not yet measured); (2) 3 → 2 Postgres nodes (projected ~$15/mo) —
this is not merely "a failure domain" to weigh against a dollar figure: dropping the third
node removes the standby that currently absorbs a primary failure without manual promotion, so
the tradeoff is quorum/failover behavior, not cost alone — **Zero decides**, with that
tradeoff stated explicitly, not just the dollar side; (3) right-size `rag`/`drive` from
measured memory (projected ~$3–6/mo, not yet measured); (4) fix `cron-fly-cost-alert.yml`
thresholds (60 GB / 6 machines are already exceeded: the tripwire is silent); (5) deploy 13 min
avg, 23 min on the Depot fallback — confirm the Depot-hosted builder is live and shorten the
fallback path. Do **not** scale the api to zero: the only outside cold-start evidence cited
here is a third-party benchmark of Fly's Machines API itself (~1.5 s boot), not of this app's
own readiness (heavy Python imports on top of that boot); the in-repo ~7 min figure is stale
(pre-vCPU-upgrade, see above). Neither number should be read as "the current cold start" —
re-measure end-to-end before ever considering `min_machines_running=0`.

## 4. World practices vs where we stand (sourced in the 2026-08-28 study and the audit)

- **Merge queue.** No consistent industry split between "fast PR lane / full queue" and the
  reverse: Rust bors runs full at merge, Chromium CQ runs a curated set per commit, Shopify
  runs the full suite async after merge. Our shape (full on both lanes, cheap idempotent
  checks, path-aware classifier) is defensible. Required checks match by **name**, not event;
  the documented workaround (one workflow branching on `github.event_name`) is what
  `tests.yml` already does. `min_entries_to_merge` stays at 1: batch-3 was measured at 85 %
  re-entry (08-28 study). Queue timeout stays at 90 min (not observed to be hit in the runs
  sampled for this document — no fixed observation window is stated; a lower value evicting
  healthy PRs on a slow-runner day is a stated hypothesis, not a measured incident).
- **Test selection.** The two antidotes to under-selection Meta/Google use — fail-open on
  unknown paths and a periodic full run on main — both exist here. The gap is the
  allowlist's coverage on the merge-group lane (13 % skip vs ~60 % eligible; R1b).
- **Caching.** Playwright's own docs say do not cache browser binaries (restore ≈ download).
  `actions/cache` is scoped by ref: verify the `gh-readonly-queue/*` lane actually restores
  main's uv/npm caches — one 25-min uv install on 2026-09-09 (normally 25 s) is *consistent
  with* a cache-scope miss but does not by itself isolate the cause from a dependency bump, a
  network blip, or eviction; confirm with an actual restore-key log before citing this as the
  fix's justification.
- **CodeQL.** `security-and-quality` adds maintainability queries with no published timing
  data; dropping to `security-extended` is directionally faster, not quantifiable — no
  analysis of which maintainability findings would be lost has been done either. Default
  setup cannot run on `merge_group`; advanced setup (ours) can. Known upstream trap
  (codeql-action#1537): check name may differ between lanes — believed to match today, but
  that has not been verified by a command run for this document; confirm with `gh api` on a
  merge_group run's check-runs before trusting it.
- **Playwright.** `workers: 1` in CI is Playwright's own guidance; already set. Build-once /
  reuse-artifact between lanes is a general Actions pattern, not first-party guidance.
- **Runners.** Self-hosting on the Mini is unsafe for `pull_request` on a public repo (GitHub's
  own security doc); only `merge_group`/dispatch jobs could use it. Paid runners
  (Blacksmith, WarpBuild, Depot, Namespace, ~$0.004/min) buy speed at real cost; pilot only if
  the free levers run out.
- **Stalls.** Flake harvest from paired pull_request/merge_group runs stays measure-only until
  the quarantine safeguards are ruled (R4). DIRTY prediction at open (R2) targets the 39 %
  DIRTY rate.

## 5. Ranked next moves

| # | Move | Saves | $ | Risk |
|---|---|---|---|---|
| 1 | Vercel `ignoreCommand` + no previews for queue refs | 0 min (not on the path) | most of the *build* spend measured so far — not proven to be most of Vercel's total spend, which also has unread transformation/invocation/bandwidth components (§2 item 6) | low |
| 2 | Backend-tests skip on merge_group at the PR-lane rate (R1b) | 5–7 min per eligible batch | 0 | low–med (pending: no symmetric path-sentinel equivalence check has been run yet — matching the PR-lane skip rate is not proof the same paths are safe to skip on the merge_group lane too) |
| 3 | Verify cache restore on `gh-readonly-queue/*`; fix keys if missing | 2–5 min per batch when it misses | 0 | low |
| 4 | Workspace-scoped Vercel install | 2 min per frontend deploy (projected, not piloted) | some | low |
| 5 | Fly: Postgres volumes + node count + `rag`/`drive` right-size | 0 | $15–30/mo (projected, not yet measured) | low–med (Zero's call on nodes; the 3→2 tradeoff is failover/quorum, not only cost — see §3) |
| 6 | CodeQL `security-extended` only, `build-mode: none` explicit | unquantified (no primary-source timing exists for this comparison) | 0 | low–med (no analysis yet of which maintainability findings would be lost) |
| 7 | DIRTY prediction at open (R2) | fewer re-queues — qualitative, no baseline rate stated yet | 0 | med |
| 8 | Fix Fly cost-guard thresholds; measure Depot fallback rate | 0 (deploy lane) | 0 | low |
| 9 | Flake harvest, measure-only (R4) | future — qualitative, no number yet | 0 | low |
| 10 | Paid runner pilot on merge_group only | wall-clock on long poles | −$ | med |

This ranking is directional (impact × ease, a judgment call), not a score computed on one
scale: dollars, minutes, and qualitative future-value are not fungible, so treat the order as
a discussion starting point for Zero, not a computed priority queue.

Owner decisions that remain: Postgres node count, previews for `agent/*`, CodeQL query suite.

## Adversarial review

Blind cross-family review (generator ≠ grader), 2026-09-10. `kimi -m kimi-code/k3` was tried
first and produced no output after >10 minutes (the fallback condition in the R1 task), so the
review was run with `codex exec -m gpt-5.6-sol -c model_reasoning_effort=medium --sandbox
read-only`, given the full document text inline and instructed to use no tools, so the
reviewer's only input was this document plus two named background facts (the 08-28 study's
batch-3/85%-re-entry finding, and the openstatus.dev cold-start benchmark's methodology) — it
had no prior context of this document's authorship. Dispositions below are the orchestrator's
(Claude, this PR's author): **accepted** = the text above was edited to fix it; **rejected** =
the objection misreads the document or was checked against live evidence and found wrong; no
objection below was watered down from the refuter's original wording.
Tally: 32 raised · 31 accepted · 1 rejected · 0 survive.

**Reviewer: `codex` (gpt-5.6-sol)** — via `codex exec`, read-only sandbox, no repo tool access
for this review (self-contained prompt). 32 raised.

| # | sev | objection (refuter's words) | disposition |
|---|---|---|---|
| 1 | HIGH | "created→started measures job scheduling latency after GitHub has created the jobs. It does not measure how long a PR or merge group remains parked before the workflow is created. The metric cannot support the broader claim that runner or queue wait is approximately zero." | accepted — §0 reworded to describe this as job-scheduling latency, not "wait", with the gap it doesn't cover stated explicitly |
| 2 | HIGH | "The evidence appears to cover one merge-group run containing 14–16 sibling jobs. Those jobs are correlated observations from one event, not 14–16 independent queue samples. No time range, number of merge groups, percentile, or slow-period sample is supplied." | accepted — same §0 edit as #1 now flags this as "a single correlated sample from one event" |
| 3 | MED | "Public-repository hosted-runner minutes being free does not establish that all GitHub-related CI consumption is free. The document does not audit artifact storage, cache/storage overages, Git LFS, or other metered GitHub services. 'Only' is an unaudited absolute." | accepted — §0 now says these were "not audited here and are assumed negligible... not verified at zero" |
| 4 | HIGH | "Sampling only merged PRs excludes the exact cases most likely to expose queue failure: evicted, cancelled, indefinitely parked, or never-merged PRs. This survivor-biased sample cannot establish that parking does not happen in the queue." | accepted — §0 point 2 now names this survivor bias explicitly |
| 5 | MED | "'Cures' overstates the evidence. The document later says the Next cache has no observed warm hit, xdist is in flight, and the stall notifier merely remains alive. Several listed interventions have not demonstrated the claimed outcome." | accepted — reworded "cures" to "changes... target", with a forward pointer to which rows in §1 are confirmed vs not |
| 6 | HIGH | "An observation that has not happened is not an after-measurement. The table heading presents the row as measured before/after evidence while the row explicitly admits that the effect remains unmeasured." | accepted — the Next-cache row now reads "not yet measured... do not read this row as a confirmed before/after" |
| 7 | HIGH | "The row uses two incompatible sequential baselines: 116 seconds in the Before column and 288 seconds in the After explanation. Against the stated 116-second baseline, 161 seconds is 39% slower, not an improvement. The document never explains why 288 seconds is the valid comparator." | accepted — xdist row rewritten to separate the CI baseline (116 s) from the local-only pilot pair (288 s → 161 s), so the two are no longer implicitly compared |
| 8 | HIGH | "This is an extrapolation, not a measurement. Local parallel scaling cannot be transferred to a GitHub runner without stating CPU count, runner type, test scheduling behavior, startup overhead, contention, or the scaling formula. It does not belong in a measured After column." | accepted — same xdist row edit labels "~65 s expected on CI" as an extrapolation, not an observation |
| 9 | MED | "A result observed on one PR does not establish the recurring benefit claimed for every PR and merge-group batch. No matched workload, run count, variance, cache state, or merge-group confirmation is shown." | accepted — CodeQL scope-diet row now flagged "n=1, not a run-count baseline" |
| 10 | MED | "One green queue run only proves that the failure did not occur once. It does not establish a post-change failure rate of zero comparable to the 54-run baseline." | accepted — `upload: never` row now says "one clean run does not establish a 0/54-comparable rate" |
| 11 | HIGH | "The document supplies no cohort, timestamps, sample size, or decomposition connecting the check reduction to the claimed 15-minute open-to-merge improvement. Calling a 20–25-minute range a 'floor' is also incoherent: a floor is a lower bound, not a typical interval." | accepted — paragraph after the §1 table now calls the open→merge number "a projection... not an observed floor" and says it needs a fresh cohort median |
| 12 | MED | "The table only reports a check changing from 6 minutes to approximately 1 minute. It does not provide evidence that total PR time changed from 15 to 5 minutes. The end-to-end conclusion is inferred without timestamps." | accepted — same paragraph now separates "this one check, measured" from "the same kind of projection, not a re-measured median" |
| 13 | HIGH | "A two-hour deployment sample cannot establish one production build for each of 300 merges over seven days. The document combines observation windows and presents the resulting weekly build count as measured fact without describing an extrapolation." | accepted — §2 intro and the "production builds triggered" row now state the 2 h→7-day extrapolation explicitly |
| 14 | MED | "The label 'with no frontend change' is only a path-based proxy. Changes outside the named paths can affect root build configuration, scripts, deployment configuration, generated inputs, or indirect dependencies. The document has not proved that all 222 builds were waste." | accepted — row reworded to "a path-based proxy... not a verified content diff" |
| 15 | MED | "An approximate build duration is multiplied as though every irrelevant deployment consumes that duration. No mean, median, distribution, cancellation treatment, or billed-duration definition is supplied. The arithmetic is an estimate dressed in a measurement table." | accepted — row now flags "~6 min is an average being multiplied as if exact" |
| 16 | HIGH | "The 74% estimate assumes every merge outside the allowlist is irrelevant and every relevant dependency is inside it. No dependency graph or fail-open test matrix establishes that assumption. A false skip can suppress a required production deployment, making the low-risk rating unsupported." | accepted — cut #1 reworded: "Risk is not simply low... a false skip on an indirect dependency would be silently skipped", with mitigation (canary + alerting) added |
| 17 | MED | "The document itself cites an upstream report that the configuration key may be ignored. It then ranks the move without selecting a reliable mechanism or defining a live acceptance test. The two proposed mechanisms are not interchangeable." | accepted — cut #2 now states explicitly that `ignoreCommand` and `git.deploymentEnabled` solve different problems and are not interchangeable |
| 18 | HIGH | "No workspace-install experiment is reported. The two-minute saving is an unsupported forecast, and npm workspace installs may still resolve substantial root-lockfile dependencies. The recommendation is presented with numerical precision it has not earned." | accepted — cut #3 now says "projected... not yet piloted" |
| 19 | HIGH | "The document admits that transformations, invocations, bandwidth, and live build-minute pricing remain unread from the Usage dashboard. Without the cost composition, it cannot know that build spend is the largest component or that this move saves 'most' of it." | accepted — §2 heading changed from "the real money" to "the largest identified cost lane (not proven... see item 6)"; ranked-move-1 $ column now says "most of the *build* spend measured so far — not proven to be most of Vercel's total spend" |
| 20 | MED | "The displayed rows sum to 17 + 12 + 6 + 35 + 11 = 81, not 82. Unrounded internal figures might total 82, but none are provided. The published table is arithmetically inconsistent on its face." | accepted — recomputed (17+12+6+35+11=81); total corrected to "≈ 81" with the arithmetic shown |
| 21 | MED | "The only volumes itemized are three 25 GB Postgres volumes, totaling 75 GB. The additional 2 GB is unexplained. The summary cannot be audited from the table." | rejected — checked against live data (`fly volumes list -a nuzantara-rag`, 2026-09-10): `nuzantara_rag_data` and `nuzantara_api_data` are each 1 GB, so 75 GB (postgres) + 1 GB + 1 GB = 77 GB exactly, matching the document; `fly machines list` on both apps also confirms 4+3=7 machines. The objection is fair that the table didn't itemize these two volumes, so the total *looked* unaudited, but the underlying number was correct — fixed by adding the verification inline rather than by changing the figure |
| 22 | HIGH | "The document does not establish that the seven-minute observation belongs to the current two-vCPU machine shape. If it came from a one-vCPU-era incident, presenting it alongside the current shape implies current applicability without evidence." | accepted — verified against the in-repo `fly.toml` comment ("EMERGENCY upgrade 1→2 (cold-start import 7min on 1 vCPU)"): the 7-min figure IS from the pre-upgrade shape; the api row and the §3 cuts paragraph now say so explicitly and call the figure stale |
| 23 | HIGH | "The cited external benchmark measured Fly Machines API startup, not 'a plain container.' Recasting it that way misstates the comparator. The valid distinction is between machine-level startup and this application's full readiness." | accepted — §3 cuts paragraph now correctly attributes the ~1.5 s figure to "a third-party benchmark of Fly's Machines API itself... not of this app's own readiness" |
| 24 | HIGH | "Reducing a three-node database topology to two can alter quorum, failover, maintenance, and split-brain characteristics. Calling it merely 'a failure domain' understates a structural availability change. No database architecture or recovery objective is supplied to make the option decision-ready." | accepted — cut (2) now spells out that the third node is the standby absorbing a primary failure without manual promotion, not just a dollar/failure-domain tradeoff |
| 25 | MED | "Both are ranked before the required disk and memory measurements exist... These are speculative opportunities, not established savings." | accepted — cuts (1) and (3) now say "projected... not yet measured" |
| 26 | MED | "No command, run identifiers, check-name pair, or timestamped observation is shown in the document. 'Ours matches today' is asserted as verified fact without presenting its verification." | accepted — §4 CodeQL bullet now says "believed to match today, but that has not been verified by a command run for this document" with the verification command named |
| 27 | MED | "'Never hit' has no stated observation window, while the slow-runner eviction claim is hypothetical and unsupported by a latency distribution." | accepted — §4 merge-queue bullet reworded to "not observed to be hit in the runs sampled... a stated hypothesis, not a measured incident" |
| 28 | MED | "One extreme install is not enough to identify ref-scoped cache restoration as the cause; dependency changes, network failure, cache eviction, or service degradation remain alternatives." | accepted — §4 caching bullet now says "consistent with... does not by itself isolate the cause" |
| 29 | HIGH | "Matching a skip rate is not proof that the same paths are safe to skip in both lanes. No symmetric path-sentinel result, false-negative analysis, or re-entry impact is supplied. The document's own world-practice section calls merge-group allowlist coverage a gap, yet the ranking treats expansion as low risk before validating equivalence." | accepted — §5 row 2 risk changed to "low–med (pending: no symmetric path-sentinel equivalence check has been run yet...)" |
| 30 | MED | "The document admits the speed gain is unquantified and supplies no analysis of lost maintainability findings, language compatibility, or build-mode consequences. There is no evidence supporting either the ranking or the risk classification." | accepted — §4 CodeQL bullet and §5 row 6 both now flag the missing maintainability-loss analysis |
| 31 | MED | "These rows use qualitative aspirations in the same 'Saves' column as concrete minute estimates. Neither has a baseline, forecast, success criterion, or confidence marker. The table visually implies comparability that does not exist." | accepted — §5 rows 7 and 9 now marked "qualitative, no baseline" / "qualitative, no number yet" |
| 32 | MED | "The ranking mixes dollars, merge latency, deployment latency, reliability, and future learning without an exchange rate, objective function, confidence score, or implementation cost. The document cannot justify why a zero-minute cost cut outranks a claimed 5–7-minute queue reduction, or why unquantified security changes outrank measured operational guards." | accepted — added an explicit caveat after the §5 table: the order is "directional... not a score computed on one scale", not a computed priority |

Refuter's verdict: 32 objections raised, none of the numeric or logical inconsistencies were
defensible as originally written; the one rejected objection was checked against live Fly data
rather than dismissed on reading alone.
