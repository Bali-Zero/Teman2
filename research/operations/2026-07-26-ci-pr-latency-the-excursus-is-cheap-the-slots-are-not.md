---
date: 2026-07-26
domain: compliance
client_case: none (internal CI infrastructure)
adversarial_review: kimi-k3
sources:
  - gh API measurements on Balizero1987/Teman2, 2026-07-25/26 (runs, jobs, steps, branch protection)
  - .github/workflows/*.yml (77 files), .husky/pre-push, scripts/prepush_classify.py
  - 3-seat panel 2026-07-26 — Codex gpt-5.6-sol (xhigh, architecture+red-team) · Kimi K3 (cross-family
    strategy) · Gemini 3.1 Pro via agy (file-grounded)
---

# PR latency: the excursus is cheap, the slots are not

## 0. The answer in one line

**No, not every PR must run the same long excursus — but the excursus was never the problem.**
Every required gate executes in **~57 seconds** (median, successful jobs) and then waits **~54
minutes** for a runner slot. The list of gates should not shrink; what must shrink is how many of
them do *work* on a diff they have nothing to say about.

## 1. Measured (every figure re-derived from the API this session)

| Fact | Value |
|---|---|
| Workflow files | 77 (**55** trigger on `pull_request`, only ~3 use `paths:`) |
| Required status contexts on `main` | **25** |
| Fan-out of ONE pull request | **27 workflow-runs = 40 jobs** |
| Runners | 100% GitHub-hosted (`ubuntu-latest`×98, `macos-latest`×1); **0 self-hosted** |
| **Real work per successful job** | **median 57 s** · max 129 s · provisioning overhead 2% |
| **Queue wait** (`token-lint`, real job) | **54.4 min queue vs 1.1 min execution → 98% waiting** |
| Achieved parallelism | peak 11, **mean 6.4** concurrent jobs |
| Machine-minutes consumed in a 0.9 h window | **355** ⇒ ~350 jobs |
| Open PRs feeding that window | **26** (9 branches + `main` actively emitting into the backlog) |
| Backlog at time of measurement | 90–112 runs queued, oldest 42 min, still growing |

**The arithmetic that reframes everything.** A PR's entire immune system costs ~40 machine-minutes.
That is nothing. But ~350 jobs arrived in 54 minutes against ~10 usable slots — so the latency is
not produced by any PR's own checks, it is produced by **everyone's jobs standing in one line**.
Shortening a 57-second check saves 57 seconds off a 55-minute wait.

## 2. Where the seats converged (and it is the non-obvious direction)

All three seats, from different lenses, landed on the same lever: **cut the number of jobs that
must occupy a slot, do not cut what the gates verify.** The mechanism they converge on:

> A required context must **always fire**, but when its subject matter is untouched it should
> answer **"not applicable — green" in ~2 seconds** instead of doing its full work.

Kimi named the property this preserves: the guard still runs, still proves innocence, still bites
on a guilty diff — *the required context is satisfied by an honest verdict, never by omission.*

## 3. The trap that makes the naive version fatal — and it has already bitten us

**A required check that produces ZERO jobs blocks the PR forever.** So the obvious implementation
— add `on.pull_request.paths:` to the workflow — is precisely wrong for any *required* context:
the workflow never fires, the context never reports, branch protection waits forever. This is not
theoretical here; it is a catalogued scar in this repo
(`discovery_required_check_zero_jobs_blocks_pr_forever_2026_07_25`).

The filter therefore belongs **inside the job**, never in the top-level trigger.

## 4. Where the seats were wrong — corrections that matter

Recording these because a panel's agreement is not evidence, and two of these would have shipped
a broken change.

- **Gemini contradicted itself inside one answer.** It stated the rule above correctly, then its
  concrete deliverable proposed top-level `on.pull_request.paths` for `actionlint`, `asyncpg-lint`
  and `npm-lock-sync` — **all three are in the measured 25 required contexts.** Applying its own
  recommendation would hang every PR permanently, in exactly the way its own warning describes.
- **Kimi ranked #2 a lever already pulled.** It called `concurrency: cancel-in-progress` "table
  stakes you're missing". Measured: **65 of 77 workflows already declare `concurrency`, and 41 of
  the 55 PR workflows already cancel superseded runs.** A fair inference from the backlog — that
  datum was not in the brief — but wrong for this repo. Residual value is the 14 uncovered PR
  workflows, not a headline fix.
- **Kimi and Codex disagreed on the merge queue, and Codex's reason is the stronger one.** Kimi
  called it a trap that *adds* demand (re-runs every required check on the queue branch, plus
  speculation, on a capped fleet). Codex says it is **not available at all for a public repository
  owned by a personal account** — only organization-owned ones. Our `owner.type` is `User`
  (verified). Same conclusion, but one is a judgement and the other is a fact.
- **Codex's security point beats the capacity argument on self-hosting.** The tempting fix is
  self-hosted runners on Pro/Mini. Kimi objected on production-contention grounds. Codex objects
  on a harder one: this repository is **public**, and a fork's PR can execute hostile code on a
  self-hosted runner. That closes the option for PR workloads regardless of capacity.
- **Codex's trust-root finding, which nobody else raised:** the path classifier must be executed
  **from `main`, not from the PR's head** — otherwise a PR can edit the classifier that decides
  which gates apply to it. Any change to `.github/**`, to the classifier, or to a dependency
  manifest must force **full fan-out**, and an unknown path must too.

## 5. Two measurement errors of my own, kept in the record

Both would have produced a confident wrong recommendation.

- **I ranked job cost by MEAN.** `root-guard` and `asyncpg-lint` showed ~10 min and I nearly
  published "every job carries ~9 minutes of fixed overhead". This is the *identical* statistical
  error whose fix I shipped this same day in the WR2 ledger (PR #3146, mean hijacked by one outlier).
  Diagnosing it in someone else's code does not immunise you against it in your own analysis.
- **The real cause was worse: cancelled jobs contaminated the sample.** `cancel-in-progress` (which
  we already have) produces `completed` jobs with `conclusion: cancelled`, **zero steps**, and a
  duration that measures *how long they waited before being killed* — not work. Filtering to
  `conclusion == success` collapsed "9.6 min of execution" to **57 seconds**, and the "9 minutes of
  overhead" to **1 second**. *A `completed` status is not a completed job.*

## 6. Recommendation, ranked by latency-saved per unit of risk

| # | Change | Expected effect | Risk |
|---|---|---|---|
| **1** | **Job-level applicability + green-NA verdicts** across the ~52 unfiltered PR workflows. Every required context keeps firing; inapplicable ones report success in ~2 s. | 40 jobs → ~10–15 doing work per PR. Attacks the 98% at its source. | Low **only if** §3 and Codex's trust-root rule are honoured. |
| **2** | **Classifier runs from `main`**, unknown path ⇒ full fan-out, `.github/**` ⇒ full fan-out. | none (it is the safety condition for #1) | This is what keeps #1 from being a hole. |
| **3** | Add `concurrency` + `cancel-in-progress` to the **14** PR workflows still lacking it. | small; kills provably dead queue entries | Zero. Not the headline — 41/55 already have it. |
| **4** | Move the slowest scanners (SonarQube, SBOM ~15 min) **off the PR critical path** to `main` + scheduled, with revert-on-red. | removes the longest poles | Bounded exposure window on `main`. Requires the revert loop to be real. |
| **5** | Aggregator job with `if: always()` that inspects every `needs.*.result`. | prevents a skipped upstream from reporting false-green | Mandatory companion to #1. |

**Explicitly NOT recommended:** deleting or weakening any immune gate (they cost ~1 minute each —
they are not the problem); GitHub merge queue (unavailable to us, and demand-additive anyway);
self-hosted runners for PR workloads on a public repo (hostile-fork execution); reusable workflows
as a throughput fix (they improve maintenance — their jobs still occupy slots).

## 7. The irony, stated because it is evidence

This document is a markdown file. Merging it will emit **~40 jobs** into a saturated queue, none of
which has anything to say about a markdown file. That is the finding, demonstrating itself.

## 8. Not done here

Nothing was changed. No workflow was edited, no required context altered, no branch protection
touched. Each step in §6 needs its own PR, its own guilt-and-innocence corpus, and — per this
repo's own rule — a grader that is not its author.

## Adversarial review (§9)

Seat: **Kimi K3** (cross-family, flat-sub), fresh context, handed only the finished report and
instructed to refute rather than assess — reviewer ≠ author. Distinct from §4, which is me grading
the *planning* seats; this is a seat grading *this artifact*.

**Accepted, and the text above is now qualified accordingly:**

1. **The 54.4-minute queue wait is n=1.** One run of one job (`token-lint`), sampled while the
   backlog was by my own admission still growing. It anchors the 98%-waiting headline, and one
   observation cannot carry a steady-state law. Read §0 as conditional: *under the congestion
   measured here*, runtime is negligible. In an unloaded queue, job duration **is** the latency.
2. **"~10 usable slots" is inferred, not measured.** Observed concurrency (peak 11, mean 6.4)
   during saturation is a lower bound on the cap, not the cap. Nothing in my method distinguishes
   a hard limit from an arrival pattern.
3. **The "of 40 jobs, ~10-15 do real work" denominator is invented.** I presented no per-workflow
   applicability data. It is a plausible guess and should not have been written as a figure.

**Refuted in its conclusion — but it found a real error on the way.** The reviewer's headline
counter-claim was that ≥70% of queue demand is *non-PR*: 3 open PRs × 40 jobs cannot produce ~350
jobs, therefore §6 attacks the wrong emitter. The arithmetic was right and the conclusion was
wrong, because the premise it inherited from §1 was **mine and false**. There are not 3 open PRs.
There are **26**, and at the moment of writing 9 distinct branches plus `main` are emitting into
the backlog simultaneously. That single wrong figure is what made the numbers look impossible.

Measured rather than argued: over a 57-minute window (100 consecutive runs) the trigger mix is
**78 `pull_request` + 3 `pull_request_target` + 16 `push` + 3 `schedule`**, with sampled
jobs-per-run of **1.7 (PR) vs 2.2 (push)** — so PR-triggered work is **~77% of job demand**, not
≤30%. §6's targeting stands, and the corrected denominator makes it *stronger*: fan-out reduction
is multiplied by every open PR, not by three. §1 is amended above.

This is the review earning its cost. Not by being right — its conclusion was wrong — but by
attacking a number hard enough that checking it exposed my own.

**Left standing as a real risk, not resolved here:** the reviewer's read of §6 #1 — a green-N/A
verdict is only as sound as its classifier, and one misclassified path silently skips a security
gate. That is the guilt-and-innocence corpus §8 already demands, and it is the reason #1 ships as
its own PR rather than as part of this capture.
