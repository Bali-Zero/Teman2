---
date: 2026-08-01
domain: operations
client_case: none (internal engineering)
sources:
  - arXiv:2601.13295v2 — CooperBench (Stanford University + SAP Labs US), verified at source
  - arXiv:2512.08296v3 — Towards a Science of Scaling Agent Systems (Google Research + Google DeepMind + MIT), verified at source
  - arXiv:2603.24755v1 — SlopCodeBench, verified at source
  - arXiv:2607.21656 — Cross-Model LLM Code Review, verified at source
  - METR RCT 2025-07-10 + uplift update 2026-02-24, verified at source
  - Mergify "State of Merge Queues 2026" · Aviator batching docs — SECONDARY, vendor-published
  - LinearB 2026 · CircleCI 2026 — SECONDARY, via reporting, NOT verified at primary source
  - Live measurements on Bali-Zero/Teman2, 2026-08-01 (§5; method limits stated inline)
adversarial_review: codex
adversarial_review_note: >-
  Two cross-family seats reviewed the FIRST draft of this document and both
  returned DO-NOT-SHIP: Codex GPT-5.6-Sol xhigh (25 findings) and Gemini 3.1
  Pro via agy (6 findings). They converged independently on the same core
  defect — the CooperBench-to-worktree inference. The thesis was withdrawn,
  not defended. See "Adversarial review" at the end.
---

# Multi-session / multi-LLM engineering strategies — delta at 2 months

> **Status: the central thesis of the first draft was REFUTED and withdrawn.**
> What survives is §1 (a correction already shipped), §5 (local measurements,
> with their limits stated), and a set of open questions with a measurement
> plan. Read §6 before quoting anything here.

## Why this file exists (and what it is NOT)

A **delta**, not a survey. The organism already holds
`2026-05-24-sota-multi-agent-repo-architecture-synthesis.md`, its `2026-05-28`
update, and `2026-06-06-sota-agentic-dev-workflow.md`. Anti-twin check run
before writing: none contains CooperBench, SlopCodeBench, the cross-review
asymmetry result, METR, or any measurement of our own merge queue.

Triggered by Zero's question — *can we implement on all three machines in
parallel, at quality?* — and his proposed model: one topic per machine, the
heavy suite as the centre, small lanes around it that produce, push, and stop.

Seats: Claude Opus 5 (author), Codex GPT-5.6-Sol xhigh and Gemini 3.1 Pro
(research + adversarial review). Kimi probed and **dead** (HTTP 403, quota) —
recorded so its absence is not read as a choice.

---

## 1. The correction that started it — SHIPPED (PR #3509)

`scripts/federation_parallelize.py` enforces one hard prohibition — *coders on
the same artifact are NEVER parallelized* — and **our docstring** documented it
as `Google arXiv 2512.08296, −70% on sequential coding`.

Read at source, that paper's **−70.0% is sequential PLANNING** (PlanCraft,
Independent topology). Not coding. **We** (this repo's documentation, not the
paper) had collapsed three distinct measurements into one number:

| Number | What it measures | Source |
|---|---|---|
| **−70.0%** | PlanCraft, sequential planning, Independent topology | 2512.08296v3 |
| **−2.1% … −14.9%** | SWE-bench Verified, N agents on the **same issue**; all topologies degrade mildly, individual cells sometimes beat solo | 2512.08296v3 |
| **−30%** | CooperBench: two agents, two different features, separate containers, patches merged afterwards | 2601.13295v2 |

PR #3509 corrects the citation **and** relabels the prohibition as an
**operational safety policy of this repo**, not a research-established
invariant — because no study read here measures concurrent edits to one
artifact, and the code enforces the rule unconditionally
(`_estimate_merge_cost` returns `HIGH` on overlap *before*
`has_explicit_contract` is read).

---

## 2. CooperBench — what it says, and the inference that did NOT survive

*"CooperBench: Why Coding Agents Cannot be Your Teammates Yet"* — Khatua et al.,
**Stanford University + SAP Labs US**, arXiv:2601.13295, 2026-01-19. 600+ tasks,
12 libraries, 4 languages, expert-written tests.

Setup: two agents work in **their own docker containers**, no inter-agent
interruption; patches **merged afterwards**; **77.3% of tasks have conflicting
ground-truth solutions**.

Results: **30% lower average success** than one agent doing both; pooled
retention **0.59** (*"41% of Solo capability is lost when agents must
coordinate"*); leading models ~**25%** cooperatively; scaling subset (46 tasks,
authors flag it as small) **68.6% → 46.5% → 30.0%** for 2→3→4 agents. Failure
symptoms: work overlap 33.2%, divergent architecture 29.7%, repetitive
communication 14.7%, unresponsiveness 8.7%, unverifiable claims 4.3%, broken
commitments 3.7% (partly LLM-judge classified with human validation — not
production frequencies). Ablation: communication did not significantly improve
completion, but **first-turn planning cut the conflict rate 51.5% → 29.4%**.

### The inference I drew, and why it was withdrawn

The first draft concluded: *"workspace isolation does not buy safety when two
lanes touch overlapping code — therefore `place` must partition by
code-that-touches, not by path."* **Both refuters killed it, independently.**

1. **The conflict rate is constructed.** 77.3% of CooperBench tasks are
   *designed* to have conflicting ground truths. Our topics are chosen to be
   disjoint. −30% is not a rate to expect from our fleet.
2. **The mechanism is not the one I asserted.** The paper attributes degradation
   to specification conflict and architectural divergence — not to "disjoint
   files calling the same function". I supplied that mechanism; the paper does
   not.
3. **The benchmark does not compare isolation against non-isolation.** It never
   runs the non-isolated condition, so it cannot establish what isolation buys
   or fails to buy.
4. **The proposed cure would serialize the monorepo.** Static call-graph
   partitioning closes over shared imports; concurrency collapses toward 1. And
   the paper's own ablation points the other way: first-turn *planning*, not
   static lock-out, is what cut conflicts.

**Withdrawn.** Whether path-disjoint-but-semantically-coupled lanes hurt us is
an **open question**, and §5 does not answer it either (see §6.2).

What survives as a genuine, weaker point: **divergent architecture (29.7%) is a
failure mode worktrees cannot fix.** Same-corner topic affinity plausibly helps
there — same context, same architectural assumptions. That is an argument for
Zero's one-topic-per-machine model, and it is a plausibility argument, not a
measurement.

---

## 3. SlopCodeBench — long-horizon degradation

arXiv:2603.24755v1, 2026-03-25. 20 problems, 93 checkpoints, 11 models; agents
repeatedly extend **their own prior solutions** under evolving specs.

No agent solves any problem end-to-end; best checkpoint solve rate **17.2%**.
Structural erosion rises in **80%** of trajectories, verbosity in **89.8%**.
Against 48 open-source Python repos, agent code is **2.2× more verbose**, and
over time **human code stays flat while agent code deteriorates each
iteration**. Prompt intervention improves initial quality but does not halt
degradation.

**Scope limit (refuter finding, accepted):** this is 20 synthetic iterative
tasks measuring unmanaged self-extension. Treating it as settled proof that
flagship lanes must be force-restarted overstates it — and the first draft did
not price the **restart overhead** (re-grounding, re-planning, warm-state loss).
Bounded-horizon flagships remain a reasonable default, held as a *hypothesis to
test*, not a law.

---

## 4. Verification: cross-family is a directed pair, not a property

arXiv:2607.21656, 2026-07-22, 116 LiveCodeBench tasks: Claude reviewing Codex
**71.6% → 89.7%**; Codex reviewing Claude **91.4% → 82.8%** (worse). Authors:
*"the useful pairing is asymmetric: use Claude to review Codex, not the other
way around."*

We run the direction that paper calls harmful. Declared limits: reviewers there
**cannot execute tests**, tasks are algorithmic not repo diffs, one small
preprint, and it is **not** settled law — the first draft leaned on it too
hard.

Counter-evidence from this session, stated as data not as vindication: Codex
reviewing Claude produced DO-NOT-SHIP on §1 and on this document, and the
findings held up when re-verified at source. n=2, opposite direction. Both
readings are weak evidence; neither settles it.

On judges generally: self-preference bias is documented (families assigning
themselves 75–84% win rates in some setups; a 2026 rubric study found judges
>50% more likely to incorrectly pass their own output on criteria the generator
failed). But where a verifiable oracle exists, same-family and cross-family
judges agree almost perfectly (κ 0.74–0.97). **Where there is a deterministic
arbiter, the arbiter wins and the panel is redundant.** Spend the panel on what
the suite cannot judge.

This ratifies Zero's framing that *the centre is the heavy suite*: an **oracle**,
not a judge.

---

## 5. Measured on OUR repo, 2026-08-01 — with method limits

| Measurement | Value | Method + limit |
|---|---|---|
| Merges | 19 in 1d · 67 in 3d · **365 in 7d** · 761 in 14d | `gh pr list --state merged --search merged:>=…` with `--limit 1000`. Includes bot PRs. |
| Shared-file touch rate, last 200 commits on `origin/main` | `PENDING-ARMS.md` **42/200 (21%)** · `DOCS_INVENTORY.md` 12 · `AI_ONBOARDING.md` 10 · `runbooks/README.md` 1 · `CLAUDE.md` 1 | single-pass `git log --format=@@@%H --name-only`. **LIMIT: this is path frequency. It does not map commits to lanes/topics, and says NOTHING about semantic coupling.** |
| Merge-queue config | `max_entries_to_merge=4`, `max_entries_to_build=5`, `min_entries_to_merge_wait_minutes=2`, `grouping_strategy=ALLGREEN`, `merge_method=SQUASH` | `gh api repos/…/rulesets/19779175` |
| Apparent batch size | **1.06** (67 PRs in 63 clusters; 59 of size 1, 4 of size 2) over 3d | clustering `mergedAt` within 60s. **LIMIT: timestamp proximity is a PROXY for merge-group membership, not the group ID.** Arrival rate in *this* window is ~1 PR/64.5 min (not the 7-day ~1/27.6 min). |
| Pre-push suite | 17,384 tests, 11–32 min; single-flight lock **per machine** (`.husky/pre-push:323`), taken only at push time | read at source |
| Path-aware skip | allowlist **v6** — `.md` under `docs/`, `research/`, `.claude/{skills,rules,commands,agents}`, `.agents/skills`; **plus** `.github/workflows/*.yml`, `apps/mouth/src/*.{ts,tsx,css}`, `scripts/tests/*.py`, `scripts/ci/*.sh`, `infra/launchagents/*.{plist,sh}`, `infra/home-fork/*.json`, root `.gitignore` | `scripts/prepush_classify.py`. The first draft said ".md only" — **wrong**; the allowlist is materially broader, so more lanes skip the toll than stated. |
| Post-merge failures on `main` | 2 failures / 36 success — but 118 skipped + 44 cancelled, **one-day window** | `gh run list --branch main`. **Not decisive**: dominated by path-filtered and superseded runs, and failures cannot be attributed to inter-lane semantic conflict. |

**Method error worth recording** (not a triumph — it briefly supported the
opposite conclusion): the first coupling measurement used `git log -200 -- <path>`
per path and compared against a 199 total from a different command. `-n` bounds
commits *that match the pathspec* — empirically, that path has **352** matching
commits on `origin/main` and `-200` returns exactly 200 — so the two numbers were
incommensurable and produced the impossible `200/199`. Corrected figures above.
(One refuter disputed this explanation; the empirical check confirmed the
original reading.)

### What these numbers do and do not support

- **The merge queue is not obviously the bottleneck** — ~52 merges/day
  sustained. **But throughput is not latency**: queue wait, backlog and blocked
  time were not measured, and this session hit a real blocked push (§below).
- **Batching is configured and rarely realized** (~1.06 apparent). Bursty pushes
  would fill it. **Correction to the first draft**: batching economizes
  *merge-queue* CI runs, **not** the pre-push suites already paid on our three
  machines — "one suite for four PRs" applies to the merge-group check only.
- **Batch size must be adaptive**: clean probability is `(1−p)^b` — at `b=10`,
  81.7% when `p=2%` but 34.9% when `p=10%`. Bisection is `O(log b)` only with a
  single culprit. Migrations, shared interfaces, dependency bumps, global config
  stay at batch 1.
- **The ~6% batching figure is not "6% of repos"** — the Mergify 2026 report
  measures ~6% of merges *transiting Mergify's own queue*, in a customer cohort
  (477 teams, ~160 filtered). Vendor dataset, not the repo universe. The
  "50–75% off the CI bill" figure is vendor arithmetic assuming full batches.
- **The heavy suite is a per-machine toll, not a centre.** Three machines =
  three concurrent suites. Demonstrated live: a push from this work was queued
  behind sibling lane `infra-codeql-262-triage` holding the same machine lock
  and died at a 10-minute foreground cap.

---

## 6. Where the evidence does NOT support what we claimed

Kept as a section because deleting inconvenient findings is how the next
generation of the same error is made.

1. **The same-artifact prohibition is policy, not a measured invariant** (§1).
   The inference from the easier measured setting to the harder assumed one is
   **ours**. Unchanged in code, deliberately: making it rebuttable under a
   formal upstream contract is a behaviour change.
2. **§5's path-frequency measure cannot speak to semantic coupling.** Both
   refuters flagged that the first draft used it to conclude "topic partition is
   clean" while simultaneously alarming about invisible semantic collisions.
   Those cannot both be argued from the same data. Neither is now claimed.
3. **The `17.2×` error-amplification figure IS in the paper** — 17.2×
   Independent, 4.4× Centralized, verbatim in 2512.08296v3. A June capture of
   ours called it "not in the paper, a TDS commentary"; **that note was wrong**.
   The real defect is worse: the paper's own regression finds error
   amplification **not statistically significant** after controls (β=0.014,
   p=0.658; interaction with tool count p=0.332) and says architecture
   differences are better explained by efficiency and overhead. `agent-library/
   02-patterns.md` and `03-lessons.md` cite 17.2× to justify centralized
   topology — asserting what the source explicitly declines to support. Same
   disease as §1, third surface. **Not fixed here; ledgered.**
4. **The 3–4 ceiling is not a coder ceiling.** Verbatim in the paper, but derived
   from cross-domain turn growth under a **fixed 4,800-token reasoning budget**;
   the paper calls larger collectives an open question. Applying it to coders
   while exempting I/O-bound infra agents is our extrapolation (labelled in
   PR #3509).

---

## 7. The humility control

METR RCT 2025-07-10: 16 experienced developers, 246 tasks in their own repos —
AI-assisted work took **19% longer**, while they predicted 24% faster and
afterwards believed they had been 20% faster. The 2026-02-24 update (57
developers, 143 repos, 800+ tasks) estimates ~18% speedup for returning
participants, CI from −38% to +9%, and **METR itself calls the signal
unreliable**.

Humans-with-AI, not autonomous fleets — it does not transfer directly. The
transferable part is the epistemics: **perceived speedup is not evidence.**

---

## 8. Decisions and open work

**Applied**

- PR #3509 — citation corrected; absolute rule relabelled as policy; ceiling
  extrapolation labelled; metrics pinned; do-not-restore note made falsifiable.

**Adopted as working practice (no code, low regret)**

- Small lanes **produce → push → PR open → stop**. Stopping *dirty* holds files
  hostage fleet-wide; stopping *after push* frees them.
- Shared-ledger edits (`PENDING-ARMS.md`, 21%) batched at end-of-lane.
- A flagship declares **files, not directories** — a directory declaration makes
  `place` refuse its own flotilla by containment.

**Held as hypothesis, NOT adopted**

- Bounded-horizon flagship lanes (§3) — restart overhead unmeasured.

**WITHDRAWN**

- Re-partitioning `place` by code-coupling instead of path. Justification
  refuted (§2). Not built.

**Open — and what would settle each**

1. Do path-disjoint, semantically-coupled lanes actually hurt us? *Measure:*
   attribute merged PRs to lanes, then look for post-merge failures/reverts on
   `main` correlated with concurrent lanes. Today's attempt (§5) is not
   decisive.
2. Adaptive batch sizing on the merge queue — repo ruleset, `operator[consent]`.
3. Make the same-artifact prohibition rebuttable under a formal upstream
   contract — behaviour change.
4. Correct the `17.2×` attribution in `agent-library/*` (§6.3).
5. Queue *latency* (not throughput) — unmeasured.
6. 4 tests in `scripts/test_federation_parallelize_gate.py` fail on
   `import federation_orchestrator`; pre-existing, proven identical on a pristine
   `origin/main` checkout.

---

## Adversarial review

**Seats**: Codex GPT-5.6-Sol (`xhigh`, `--sandbox read-only`) — 25 findings; and
Gemini 3.1 Pro via `agy` — 6 findings. Both cross-family (author is Claude
Opus 5; generator ≠ grader), both mandated to refute with default-to-defect.
**Both returned DO-NOT-SHIP on the first draft**, converging independently on
the same core defect.

**Surviving objections, and what each changed:**

| Objection | Outcome |
|---|---|
| The CooperBench → worktree inference is unsound: conflict rate is constructed, mechanism mis-attributed, benchmark never compares isolation vs non-isolation, and call-graph partitioning would serialize the monorepo | **ACCEPTED — thesis withdrawn**, §2 rewritten, the `place` redesign cancelled |
| §2 alarms about semantic collision while §5 concludes partition is clean — cannot both be argued from path frequency | **ACCEPTED** — both claims dropped; the limit is now stated in the §5 table |
| Preliminary single studies (SlopCodeBench, cross-review preprint) presented as settled | **ACCEPTED** — both downgraded to hypotheses with scope limits |
| Missing disconfirming evidence: no audit of realized post-merge regressions | **ACCEPTED and ATTEMPTED** — measured, **not decisive**, recorded as such in §5 and left open in §8.1 |
| Factual: CooperBench is Stanford **+ SAP Labs US**; the scaling paper includes **DeepMind** | **ACCEPTED**, corrected |
| Factual: the pre-push allowlist is **v6 and far broader than `.md`** | **ACCEPTED**, corrected — the first draft's version was materially wrong |
| Factual: `17.2×` **is** in the paper; the real defect is its statistical insignificance after controls | **ACCEPTED** — §6.3 rewritten; our own June note was the phantom |
| The Mergify ~6% denominator is merges-through-its-queue, not repos; "50–75%" is vendor arithmetic | **ACCEPTED**, corrected |
| Arrival-rate arithmetic mixed a 7-day rate with a 3-day sample; 60s clustering ≠ merge-group membership | **ACCEPTED**, both stated as limits |
| Batching saves merge-queue CI, not pre-push suites already run locally | **ACCEPTED**, corrected |
| Self-serving framing of the author's own errors | **ACCEPTED** — triumphal wording removed from §5 |
| `git log -n` semantics: a refuter claimed the explanation was factually wrong | **REFUTED BY MEASUREMENT** — that path has 352 matching commits and `-200` returns exactly 200; `-n` does bound post-filter. The refuter hallucinates too (W65) |

**Known remaining weakness**: §5 is measured with stated limits; §§2–4 and 7 are
single-study readings, several small or preliminary; LinearB and CircleCI
figures come from secondary reporting **not** verified at primary source and
must not be quoted as measured. No claim here about our own fleet's semantic
collision rate is supported by data.
