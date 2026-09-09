# PR time, merge queue and Fly/Vercel cost — study 2026-09-10

> Mandate (Zero, 2026-09-09): "best practice mondiali per ridurre ancora tempo PR e coda, e
> risparmiare i costi Fly e Vercel senza perdere tempo". Three read-only audits (Fly, Vercel,
> world practices) plus the day's measurements. Companion to
> `2026-08-28-beyond-sota-ci-merge-queue-ship-pipeline.md` (R1–R6, kimi-k3 reviewed); this
> document does not re-derive that one — it adds what was measured on 2026-09-09 and the
> cost side, which the earlier study did not cover.

## 0. Two facts that reframe the question

1. **The repo is public** (`gh repo view --json isPrivate` → false) and the org is on the
   Enterprise plan. Standard GitHub-hosted runner minutes are free and runner wait is ~0 s
   (measured: 14–16 jobs per merge-group run, max 3 s created→started). CI buys **time**, not
   dollars. Dollars live only on Vercel and Fly.
2. **The queue itself is not where PRs park.** Last 25 merged PRs: 6–27 min in the queue,
   always one enqueue, never kicked. The parking happens before the queue: red checks a seat
   has to diagnose, and PRs nobody armed. The 2026-09-09 cures (#6017 whitelist arms under the
   queue, #6020 ledger-only tier, #6029 CodeQL never uploads in the queue, #6030 CodeQL scope,
   #6032 Next build cache, xdist for antidotes) all attack those two.

## 1. Shipped 2026-09-09 (measured before → after)

| Lever | Before | After | Pays on |
|---|---|---|---|
| CodeQL scope diet (#6030) | python 15 min, js 4 min | 7 min, 2 min (observed on the PR) | every python/js PR and batch |
| CodeQL `upload: never` on merge_group (#6029) | 10 of 54 merge-group Security runs red ("ref … not found") | 0 of that class; queue run 7m50s green | every batch with python |
| Next `.next/cache` for E2E (#6032) | "Run E2E tests" 244 s (tests themselves 69 s) | first warm hit still to be observed | every mouth PR and batch |
| antidotes unit tests under xdist (in flight) | 116 s sequential | 161 s vs 288 s locally (−44 %), ~65 s expected on CI | every immune-zone PR and batch |
| ledger-only antidotes tier (#6020, 09-09) | 6 min | ~1 min | ≥9 ledger PRs/day |
| whitelist arms under the queue (#6017) | dependabot PRs waited days | armed at open (#6028 proved) | every dependabot PR |
| stall notifier on Mini | first run timed out (collided with unstick at :00) | staggered to :07/:37, timeout 300 s, alive | every 30 min |

Typical python/frontend PR: longest required check 15 → 7–8 min in both lanes; open→merge
floor for a green PR ~35–40 → ~20–25 min. Ledger-only PR: ~15 → ~5 min.

## 2. Vercel — the real money

Team `nuzantara-2026`, plan **Pro**. Two projects: `mouth` (apps/mouth) and `knowledge`
(dormant 184 days). No Vercel check is required on `main`, so nothing below touches merge time.

Measured (git log on origin/main, 7 days to 2026-09-09; Vercel deployments API, 2 h window):

| Signal | Value |
|---|---|
| merges to main / 7 days | 300 |
| of which touching `apps/mouth`, `packages/`, lockfile | 78 (26 %) |
| production builds triggered | one per merge, ~6 min each → ~220 builds/week (~1,300 build-min) with no frontend change |
| preview deployments | one per push on every branch, **including `gh-readonly-queue/main/pr-*`**; 15 previews in 2 h, cancelled at ~30 s |
| `apps/mouth/vercel.json` | no `ignoreCommand`; `installCommand: cd ../.. && npm ci --include=dev` (whole monorepo, no turbo/nx) |
| `mini.vercel_autopromote` | promotes READY builds every 120 s, creates none |

Cuts, ranked:

1. **`ignoreCommand` path-scoped to mouth + packages + lockfile.** Removes ~74 % of production
   builds and the previews of unrelated branches. Risk low (fail-open when undecidable; shallow
   clone → use `VERCEL_GIT_PREVIOUS_SHA` with fallback). Bites: a docs-only merge yields no
   deployment.
2. **No previews for `gh-readonly-queue/*`** (`git.deploymentEnabled`, or the same
   `ignoreCommand` on `VERCEL_GIT_COMMIT_REF`). Nobody views them. Verify live: issue
   vercel/vercel#11176 reports the key being ignored in some cases.
3. **Workspace-scoped install** instead of `npm ci` of the whole monorepo: build 6 → ~4 min.
   Also shortens the promote lag of `vercel_autopromote` after every frontend merge.
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
| nuzantara-rag / api | shared-cpu-2x 3 GB, `auto_stop=off`, `min=1` (cold start ~7 min, documented) | ~17 |
| nuzantara-rag / rag | shared-cpu-2x 2 GB, worker without `[[services]]` → never auto-stops | ~12 |
| nuzantara-rag / drive | shared-cpu-1x 1 GB + one stopped standby | ~6 |
| nuzantara-postgres | 3 × shared-cpu-2x 2 GB + 3 × 25 GB volumes | ~35 + ~11 |
| **total** | 7 machines, 77 GB volumes | **≈ 82** |

Cuts, ranked: (1) measure real Postgres disk use, shrink 25 → 10–15 GB per node if < 30 %
used (~$5–7/mo); (2) 3 → 2 Postgres nodes (~$15/mo) — a failure domain, **Zero decides**;
(3) right-size `rag`/`drive` from measured memory (~$3–6/mo); (4) fix
`cron-fly-cost-alert.yml` thresholds (60 GB / 6 machines are already exceeded: the tripwire is
silent); (5) deploy 13 min avg, 23 min on the Depot fallback — confirm the Depot-hosted builder
is live and shorten the fallback path. Do **not** scale the api to zero (cold start measured
at minutes, not the 1.5 s of a plain container).

## 4. World practices vs where we stand (sourced in the 2026-08-28 study and the audit)

- **Merge queue.** No consistent industry split between "fast PR lane / full queue" and the
  reverse: Rust bors runs full at merge, Chromium CQ runs a curated set per commit, Shopify
  runs the full suite async after merge. Our shape (full on both lanes, cheap idempotent
  checks, path-aware classifier) is defensible. Required checks match by **name**, not event;
  the documented workaround (one workflow branching on `github.event_name`) is what
  `tests.yml` already does. `min_entries_to_merge` stays at 1: batch-3 was measured at 85 %
  re-entry (08-28 study). Queue timeout stays at 90 min (never hit; a lower value evicts
  healthy PRs on a slow-runner day).
- **Test selection.** The two antidotes to under-selection Meta/Google use — fail-open on
  unknown paths and a periodic full run on main — both exist here. The gap is the
  allowlist's coverage on the merge-group lane (13 % skip vs ~60 % eligible; R1b).
- **Caching.** Playwright's own docs say do not cache browser binaries (restore ≈ download).
  `actions/cache` is scoped by ref: verify the `gh-readonly-queue/*` lane actually restores
  main's uv/npm caches — a 25-min uv install on 2026-09-09 (normally 25 s) says it may not.
- **CodeQL.** `security-and-quality` adds maintainability queries with no published timing
  data; dropping to `security-extended` is directionally faster, not quantifiable. Default
  setup cannot run on `merge_group`; advanced setup (ours) can. Known upstream trap
  (codeql-action#1537): check name may differ between lanes — ours matches today.
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
| 1 | Vercel `ignoreCommand` + no previews for queue refs | 0 min (not on the path) | most of the build spend | low |
| 2 | Backend-tests skip on merge_group at the PR-lane rate (R1b) | 5–7 min per eligible batch | 0 | low |
| 3 | Verify cache restore on `gh-readonly-queue/*`; fix keys if missing | 2–5 min per batch when it misses | 0 | low |
| 4 | Workspace-scoped Vercel install | 2 min per frontend deploy | some | low |
| 5 | Fly: Postgres volumes + node count + `rag`/`drive` right-size | 0 | $15–30/mo | low–med (Zero's call on nodes) |
| 6 | CodeQL `security-extended` only, `build-mode: none` explicit | unquantified | 0 | low–med |
| 7 | DIRTY prediction at open (R2) | fewer re-queues | 0 | med |
| 8 | Fix Fly cost-guard thresholds; measure Depot fallback rate | 0 (deploy lane) | 0 | low |
| 9 | Flake harvest, measure-only (R4) | future | 0 | low |
| 10 | Paid runner pilot on merge_group only | wall-clock on long poles | −$ | med |

Owner decisions that remain: Postgres node count, previews for `agent/*`, CodeQL query suite.
