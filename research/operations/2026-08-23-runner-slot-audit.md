---
date: 2026-08-23
domain: operations
client_case: none
sources:
  - gh api "repos/Bali-Zero/Teman2/actions/runs?created=2026-08-23&per_page=100" --paginate
  - gh api "repos/Bali-Zero/Teman2/actions/runs?created=2026-08-23T<H>:00:00..<H+1>:00:00&per_page=100" --paginate (hourly buckets, hours 00-11 UTC)
  - gh api "repos/Bali-Zero/Teman2/actions/runs?created=2026-08-23&event=<event>&per_page=1" (full-day event totals via total_count)
  - gh api "repos/Bali-Zero/Teman2/actions/workflows" --paginate
  - gh api "repos/Bali-Zero/Teman2/actions/workflows/<id>/runs?created=2026-08-23&per_page=1" (per-workflow full-day totals)
  - gh api "repos/Bali-Zero/Teman2/actions/runs/<id>/jobs" (job-level sampling, 8 workflows, ~90 runs, 373 job records)
  - gh api repos/Bali-Zero/Teman2/actions/permissions
  - gh api repos/Bali-Zero/Teman2/branches/main/protection/required_status_checks
  - gh api repos/Bali-Zero/Teman2/rules/branches/main
  - gh api repos/Bali-Zero/Teman2/rulesets
  - gh api orgs/Bali-Zero (plan)
  - Read .github/workflows/tests.yml, security.yml, main-red-breaker.yml (source inspection, not API)
  - WebSearch "GitHub Actions concurrent jobs limit Team plan 2026 public repository" (documentation, not measurement)
---

# Runner-slot audit — Bali-Zero/Teman2, 2026-08-23

**Lede — the one unobtainable number:** true peak-concurrent-jobs for the full day is
**unobtainable within this session's budget**. GitHub exposes no API field for it, and
computing it exactly requires job-level `started_at`/`completed_at` for every job of
~19,500+ runs, not just workflow-level run metadata. What follows is a verified **lower
bound of 15** from a ~1% stratified job sample (90 of the 8,511 runs in
its own window — see §5; an earlier draft said ~3% here, which no computation
in this document supports), plus the GitHub-documented plan cap
(**60**, cited as documentation, not measurement) — see §5.

## What was measured

1. **Full-day run totals** (2026-08-23, 00:00–23:59 UTC — the day had fully elapsed by
   query time): pulled via `event`-filtered `total_count` on `actions/runs`, one call per
   event value. The 8 event-type totals sum to **exactly 21,054**, matching the
   unfiltered `total_count` for the same `created=2026-08-23` window — a hard
   cross-check that the event breakdown is complete and internally consistent.
2. **Exhaustive workflow-run capture, 00:00–11:00 UTC only**: fetched every run created
   in that 11-hour window in 1-hour buckets (`per_page=100 --paginate`), because a single
   unbounded `created=2026-08-23` query silently truncates to its most recent 1,000
   results (verified: page 11 of that query returned 0 rows spanning only a 42-minute
   window, while `total_count` said 8,435 — a real pagination ceiling on this endpoint,
   not a data problem). Hourly per-bucket `total_count` never exceeded 1,383, so the
   1,000-row ceiling was never hit inside a single hour. Result: **8,511 unique run
   records**, IDs deduplicated, covering `created_at` 00:00:33–11:02:40 UTC only.
   **This is ~40% of the day's runs by count (8,511 of 21,054) and covers WITA
   08:00–19:00 — later hours (14:00–17:00 and 21:00–23:00 UTC) measured busier by
   `total_count` alone (1,148–1,445 runs/hour vs 348–1,383 in the captured window) and
   are NOT in this sample.** Workflow-name/event/conclusion tables below are built from
   this 8,511-row set unless marked "full-day."
3. **Full-day per-workflow totals**: for the top-8 candidates, fetched `total_count` via
   the workflow-scoped endpoint (`actions/workflows/<id>/runs?created=2026-08-23`) —
   cheap and exact, used to scale job-minute estimates to the full day.
4. **Job-level duration sampling**: for 8 workflows (Security Scanning n=15 runs/150
   jobs, Tests & Coverage n=11/118, merge-gate-integrity-watch n=41 of 46 — an 89% sample,
   NOT the full population as originally written, Contract Tests n=10/10, SonarQube Analysis n=10/20, Main-push Failure
   Watch n=9/18, Root Guard n=8/8, npm lock sync n=8/8), run IDs picked by fixed-stride
   sampling across the 00:00–11:00 UTC set to spread across the morning. Job fetches
   were parallelized (`xargs -P4`, 15–20s per-call timeout) after a serial loop hit
   repeated `TLS handshake timeout` (a real, not simulated, transient network condition —
   noted so the numbers below aren't read as more exhaustive than they are).
5. **Required-checks list**: `branches/main/protection/required_status_checks` returned
   27 contexts (`.checks | length` = 27, confirmed with `sort -u | wc -l` = 27, no
   duplicates). The newer rulesets API (`rules/branches/main`) does **not** carry this —
   it only has `deletion`/`non_fast_forward`/`copilot_code_review`/`merge_queue` rules;
   the required-checks list lives in the classic branch-protection API. This matters
   operationally: anyone querying only `rules/branches/main` for "the required list" gets
   zero results and may wrongly conclude nothing is required.
6. **Plan concurrency cap**: `actions/permissions` returns `enabled`/`allowed_actions`/
   `sha_pinning_required` only — no concurrency field. `orgs/Bali-Zero` reports plan
   `"team"`. No API on this token exposes the numeric concurrency cap (would need
   billing-admin scope this token doesn't have, or doesn't exist at all for this field).
   The GitHub-documented default for the Team plan is cited in §5 as documentation.

## 1. Runs by event — full day (exact, cross-checked)

| Event | Runs | Share |
|---|---:|---:|
| pull_request | 11,261 | 53.5% |
| merge_group | 5,553 | 26.4% |
| workflow_run | 2,407 | 11.4% |
| push | 1,011 | 4.8% |
| schedule | 435 | 2.1% |
| pull_request_target | 383 | 1.8% |
| workflow_dispatch | 2 | ~0.0% |
| dynamic | 2 | ~0.0% |
| **Total** | **21,054** | 100% |

`pull_request` + `merge_group` = 79.9% of all runs today — i.e. CI churn is overwhelmingly
driven by PR-transit traffic, not by cron/schedule (2.1%) or manual dispatch (~0%).

## 2. Required vs advisory — workflow-level proxy, 00:00–11:00 UTC sample (n=8,511)

The 27 required contexts are **job-level** check names; `actions/runs` only reports
**workflow-level** run names, and two of the biggest workflows (`Tests & Coverage`,
`Security Scanning`) mix required and advisory jobs in the same run. So this table
classifies a whole **run** as "required-producing" if the workflow contains ≥1 job that
maps to one of the 27 required contexts (verified by name-matching each context to its
producing workflow file, e.g. `Backend Tests (Python)`, `E2E Tests (Playwright)`,
`MCP Server Tests`, `Frontend Tests (Next.js) (mouth, true)` → all four live inside
`tests.yml` / "Tests & Coverage"; `Bandit Python Security`, `CodeQL Analysis (python/js)`,
`Detect Secrets` → all three live inside `security.yml` / "Security Scanning"). This
**over-counts** the required share slightly, since e.g. "Security Scanning" runs also
carry 6 non-required jobs (3× Snyk, Safety, Change map, Security Summary) and
"Tests & Coverage" also carries the advisory `npm audit (advisory)` job.

| Class | Runs | Share |
|---|---:|---:|
| Required-producing workflow (21 workflows → 27 required contexts) | 4,634 | 54.4% |
| Advisory-only workflow (46 remaining workflow names) | 3,877 | 45.6% |

## 3. Top-5 slot consumers by estimated job-minutes/day

Job-minutes = sum of every job's `completed_at − started_at` within a run (i.e.
runner-slot-minutes consumed, not wall-clock). Per-run averages come from the job-level
sample (§ "What was measured" step 4); full-day run counts come from the exact
workflow-scoped `total_count` (step 3). **Estimated full-day job-minutes = sampled
avg/run × full-day run count** — an extrapolation, stated as such, not a direct
measurement of every run.

| Rank | Workflow | Runs today (exact) | Sampled avg job-min/run | Est. job-min/day | Est. hours/day |
|---|---|---:|---:|---:|---:|
| 1 | Tests & Coverage | 532 | 14.84 (n=11) | ~7,895 | ~131.6h |
| 2 | Security Scanning | 520 | 11.99 (n=15) | ~6,235 | ~103.9h |
| 3 | Contract Tests (Schemathesis) | 116 | 4.10 (n=10) | ~476 | ~7.9h |
| 4 | Main-push Failure Watch | 1,914 | 0.16 (n=9) | ~306 | ~5.1h |
| 5 | npm lock sync | 628 | 0.48 (n=8) | ~301 | ~5.0h |
| (6th, close) | Root Guard | 628 | 0.42 (n=8) | ~264 | ~4.4h |
| (measured, not sampled small n) | SonarQube Analysis | ~unknown\* | 0.04 (n=10) | negligible | — |

\*SonarQube's full-day count wasn't separately pulled; its per-run cost is negligible
(~2.4s avg in sample) so it doesn't change the ranking regardless.

**Read on this table**: the four highest-*run-count* workflows in the whole dataset
(Main-push Failure Watch 1,914 runs/day, Root Guard 628, npm lock sync 628, Docs Sync
Check/runbook-numbers/asyncpg-lint ~500-600 each in the AM sample) are cheap **per run**
(sub-second to ~30s) — high volume does not translate to high job-minutes. The real
job-minute cost concentrates almost entirely in two workflows: **Tests & Coverage** and
**Security Scanning**, together ≈235 hours/day of runner-slot time, ~94% of the top-5's
combined total. A naive "sort by run count" audit would misidentify the trim targets.

**Structural note, mid-window transition observed live**: the Tests & Coverage sample
straddles the landing of PR #4647 (backend-test sharding, merged ~10:20 UTC per fleet
broadcast). 9 of 11 sampled runs show a single `Backend Tests (Python)` job (avg 243s);
2 show the post-split `Backend Shard 1/2/3` + `Backend Static (Python)` jobs (avg
183–200s **each**, run concurrently). Net effect: sharding **cuts wall-clock** critical
path (as the fleet independently measured: ~1068s→338s on `pull_request`) but
**increases total runner-slot-minutes consumed** per run, because 3–4 parallel jobs now
run where 1 ran before. This is expected and probably a good trade (wall-clock is what
blocks a human; slot-minutes are what this audit prices) — flagging only because it means
the Tests & Coverage row in the table above will trend upward, not downward, as the
sharded shape becomes the full-day norm (it landed only 40 minutes before the end of the
captured window).

## 4. merge-gate-integrity-watch — dedicated row

| Window | Runs | Failure | Success | Job-minutes | Avg/run |
|---|---:|---:|---:|---:|---:|
| 00:00–11:00 UTC (**41 of 46** runs fetched — an 89% sample, NOT the full population; see the correction note below) | 46 | 46 (100%) | 0 | 26.5 min measured across the 41 fetched | 38.8s (sample mean) |
| Full day (00:00–23:59 UTC, exact `total_count` + conclusion pull) | 110 | 48 (43.6%) | 62 (56.4%) | ~71 min (extrapolated at 38.8s/run) | — |

The mandate's framing ("12+ runs today, all failing") matches the *directional* shape of
the early-morning window (AM population: 46/46 failing) but **not the full day** —
something shifted between the AM window and end of day, flipping the majority of runs to
success (62/110 succeeded). This is cheap in runner-slot terms (~71 min/day, negligible
next to the top-5 above) — the actual cost here is **signal, not slots**: a watcher that
was 100% red all morning and then mostly green is either a real incident that got fixed,
or a broken detector that got fixed — either way it burned attention, not compute. Not a
slot-trim candidate; a signal-quality one, already flagged by the fleet's own C1 concern
(squash-SHA cause).

## 5. Peak concurrency vs plan cap

| | Value | Basis |
|---|---|---|
| Plan cap | **60 concurrent jobs** (GitHub Team plan, standard hosted runners) | **Documentation**, not measurement — no API field on this token exposes the org's actual configured/support-adjusted cap. `actions/permissions` returns only `enabled: true, allowed_actions: "all", sha_pinning_required: false`. Cited from GitHub's own docs via web search; org `Bali-Zero` plan confirmed as `"team"` via `gh api orgs/Bali-Zero`. |
| Peak concurrent jobs, TRUE value for the day | **unobtainable within this session's budget** — would require job-level timestamps for all ~19,500 runs after 11:00 UTC plus the ~8,500 before it. Not attempted at that scale (network calls were already hitting TLS timeouts at ~90 runs' worth of job fetches). |
| Peak concurrent jobs, SAMPLED lower bound | **15**, at 2026-08-23 00:31:15 UTC | Interval-sweep over 267 job (start,end) pairs from the 373-record combined sample (8 workflows, ~90 runs) spanning 00:30–11:02 UTC. This is a **hard lower bound only** — the sample is ~1% of the 8,511 runs in its own window, and 0% of the runs after 11:00 UTC (which `total_count` shows were busier: 1,148–1,445 runs/hour in the 14:00–17:00 and 21:00–23:00 UTC bands, vs the 348–1,383/hour range inside the sampled window). |

Given merge_group entries alone run ≥5 parallel jobs (Backend Shard 1/2/3 + Static +
fan-in, per the S11 fleet measurement) and Security Scanning runs ~9 jobs per invocation,
with `pull_request`+`merge_group` volume at ~560+~370 *trigger events*/day respectively
(back-calculated from 11,261 pull_request-event runs and 5,553 merge_group-event runs
divided by ~20 and ~15 workflows-per-event respectively), it is plausible the true peak
sits close to or at the 60-job cap during the busiest hours — but this is a **hypothesis
from the shape of the data, not a measured number**, and is flagged as such rather than
reported as fact.

## 6. CodeQL — the measurement trap, checked and partially corrected

A fleet broadcast (`Nuzantara:fleet-watch`, addressed to this lane) warned that CodeQL
"doesn't appear in `actions/runs`" because it runs via GitHub default code-scanning
setup, and would be silently miscounted as zero. **Checked directly, and this is only
half right for this repo**: `security.yml` uses **advanced setup**
(`github/codeql-action/init|autobuild|analyze`, not GitHub's managed default setup) —
confirmed by reading the workflow source (lines 554–639). So:

- CodeQL **is** measurable via `actions/runs/<id>/jobs` — it shows up as two job names,
  `CodeQL Analysis (python)` and `CodeQL Analysis (javascript)`, nested inside the
  "Security Scanning" **workflow run** (verified live on run 32634967911).
- It is **not** a separate top-level workflow-run name, so a name-count audit like
  §1/§3 that only reads `actions/runs[].name` genuinely does undercount it (it's baked
  into the Security Scanning row) — the fleet tip's underlying concern was directionally
  correct even though the specific claim ("doesn't appear at all") wasn't.
- `check-runs` on a recent merge commit (f26bd5a5f) returned **zero** CodeQL entries —
  plausibly because that PR's `changes` classification step decided
  `run_codeql_python`/`run_codeql_js` = false for that diff; not investigated further.
- **Duration is bimodal** (n=15 sampled `CodeQL Analysis (python)` jobs): most runs
  20–60s, but 5 of 15 (~33%) ran 500–845s (8.3–14.1 min). This is directionally
  consistent with the fleet's separately-reported "18+ min pending" observation on a
  live queue entry (their number likely includes queue wait, not just execution — not
  reconciled here, would need a dedicated check-runs pull on that specific PR to
  separate queue-wait from execution-time).

## 7. npm audit (advisory) — path-filter check

Read directly from `.github/workflows/tests.yml` lines 1790–1797 (verbatim):

```yaml
needs: [changes]
if: >-
  !cancelled() &&
  (
    (github.event_name != 'pull_request' && github.event_name != 'merge_group') ||
    needs.changes.result != 'success' ||
    needs.changes.outputs.run_frontend_tests != 'false'
  )
```

**Finding: it already path-filters, on `pull_request` and `merge_group` events, via the
`changes` job's `run_frontend_tests` output.** It skips only when the event is PR/merge_group
AND the changes-detector succeeded AND `run_frontend_tests == 'false'` (no
frontend-relevant paths touched). On `push`, `schedule`, or `workflow_dispatch` it always
runs regardless of paths — but `tests.yml`'s own top-level `on:` block (lines 3–8) doesn't
trigger on `push` at all (only `pull_request: [opened, synchronize, reopened]`,
`merge_group`, `workflow_dispatch`, plus a `schedule` trigger further down the file not
fully read here), so the un-filtered branch of this condition applies to a small slice of
Tests & Coverage's 532 runs/day (5 `schedule` + 2 `workflow_dispatch` in the AM sample of
221 — i.e. ~3%, not the dominant volume).

**Sample too small to state a skip rate**: in the 11-run Tests & Coverage job sample, the
`npm audit (advisory)` job executed 11/11 times (100%), avg 28s/run. Either all 11
sampled runs touched frontend-relevant paths, or the skip condition rarely fires in
practice — cannot distinguish with n=11. Do not treat "11/11 ran" as proof the filter is
ineffective; it isn't enough data either way.

## Candidate trims, with their before-number

| Candidate | Runs/day removed | Job-min/day removed | Touches a REQUIRED context? |
|---|---|---|---|
| **None of the sampled workflows are strong runner-slot trim candidates at current volume.** The two workflows that actually cost slot-time (Tests & Coverage ~7,895 min/day, Security Scanning ~6,235 min/day) are both **majority required** (Backend/Frontend/E2E/MCP tests; CodeQL×2/Bandit/Detect-Secrets) — trimming them means trimming required gates, out of scope for a measure-only Gear-1 pass. | — | — | **DO-NOT-TOUCH** (both workflows carry required contexts; see §2) |
| Reduce/mute `merge-gate-integrity-watch` on-push firing (currently fires on every `push`, 110 runs today, was 100% red for the whole 00:00–11:00 UTC window before recovering) | ~110 runs/day (if collapsed to e.g. once per hour) | ~71 min/day → trivial (~60 min/day saved at most) | **Not required** (absent from the 27-context list) — but this is a *signal-quality* fix, not a slot-savings one; the fleet's own C1 concern already targets the root cause (squash-SHA), not the trigger frequency. Listed here only because it's explicitly cheap and safe to touch. |
| Tighten `npm audit (advisory)`'s non-PR/merge_group branch (currently unconditional on `schedule`/`workflow_dispatch`) | ~7 runs/day in the AM sample (≈3% of Tests & Coverage's 221 AM runs) × 28s ≈ **~3 min/day** | negligible | **Not required** (explicitly excluded from `infra/required.d/contexts.json` per the workflow's own comment, verified absent from the 27-list) — but the removed volume is too small to justify the churn of a PR. **Not worth doing** on the numbers measured here. |
| CodeQL Analysis (python) bimodal long tail (33% of sampled runs at 8–14 min vs 20–60s for the rest) | Not a run-count trim — a per-run duration issue on a **required** context | Potentially several hundred min/day if the ~33%-slow pattern holds repo-wide (520 runs/day × ~33% × ~(700s − 40s) ≈ **~64 hours/day** if extrapolated naively — **not verified**, sample is n=15, and the slow/fast split by event/path was not fully characterized) | **DO-NOT-TOUCH the check itself** — it's required (both `CodeQL Analysis (python)` and `(javascript)` are in the 27-context list). Candidate is *investigating why some runs are slow* (paths-ignore, language-split, bigger runner — options already surfaced independently by the fleet's own S12/C5 tip), not removing the check. Flagging as the single largest **unquantified** opportunity in this audit — needs a dedicated follow-up with a much bigger CodeQL-specific sample before any number here should be trusted past "probably real, size unknown." |

## Gate corrections (applied 2026-08-25 by the verifying session, NOT by the author)

This document was independently re-measured before being committed — generator≠grader.
Every full-day figure in §1 reproduced with **zero drift** (total 21,054; the eight event
totals still sum to it exactly), §2's 27 required contexts reproduced exactly, and the
rulesets-API-returns-zero trap reproduced exactly. Two claims did **not** survive, and were
corrected in place rather than quietly overwritten:

1. **Phantom line citation (scar family #6).** §7 cited
   `.github/workflows/tests.yml` **1712–1719**. The quoted YAML is byte-for-byte correct,
   but it lives at **1790–1797**; line 1712 is a comment about wa-mirror's vitest suite.
   Content real, location imagined — the exact shape family #6 exists to catch. Corrected.
   (`npm audit (advisory)` is declared at line 1775, consistent with the corrected range.)

2. **False completeness claim in §4.** The AM row read "captured, exhaustive — 41/41 jobs
   fetched … full population, not a sample". The window actually holds **46** runs, all 46
   `completed/failure` — re-measured twice, on both the loose `00:00–11:00Z` bounds and the
   document's own stated exact bounds, landing on 46 both times. So 41 fetched of 46 is an
   **89% sample**, and 38.8s/run is a sample mean, not a population mean. The direction is
   unchanged (100% failure either way) and the ~71 min/day extrapolation still holds,
   because it was always avg × full-day count — but "exhaustive" was not true, and a
   completeness claim is exactly the kind that must not be waived.

A third, minor one: the lede said the concurrency sample was "~3%" while §5 says "~1%".
No computation in the document supports 3% (90 of 8,511 runs = ~1.06%), so the lede now
matches §5.

**What this does NOT change**: the audit's conclusions. Both defects are in citation and
completeness, not in the headline findings — the two cost centres, their majority-required
status, and the "no trim justified at current volume" verdict all rest on §1/§2/§3 figures
that reproduced exactly.

## Honest gaps (stated per the mandate's hard rule — not filled in)

- **True peak concurrency for the full day**: unobtainable at this session's budget (§5).
- **Full-day job-minutes for all workflows** (only 8 of 67 distinct workflow names were
  job-sampled): the other 59 are unmeasured; given their run-counts (most in the 5–260/day
  range per the AM sample) and the strong pattern that lint/gate-style workflows run in
  single-digit seconds to under a minute, they are assumed low-cost but this is **not
  verified** for any of them individually.
- **CodeQL slow/fast split root cause**: not diagnosed (event type? diff size? cache
  state?) — flagged, not solved.
- **npm-audit true skip rate**: n=11 is not enough to state a percentage.
