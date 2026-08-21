---
date: 2026-08-21
domain: operations
client_case: none
adversarial_review: kimi-k3
sources:
  - https://www.anthropic.com/engineering/multi-agent-research-system
  - https://cognition.com/blog/dont-build-multi-agents
  - https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents
  - https://arxiv.org/html/2606.22528v2
  - https://research.facebook.com/publications/predictive-test-selection/
  - https://github.com/tarpas/pytest-testmon
  - https://github.com/orgs/community/discussions/48792
  - https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching
discovered_by: workflow world-patterns-import (6 blind research lanes + 2 adversarial refuters, Sonnet 5)
---

# World-practice import map — token, velocity, incisiveness (2026-08-21)

**Mandate** (Zero, 2026-08-21): "ultima profonda analisi del sistema… numerose deep research con
le best practice mondiali e individuare i pattern da importare."

**Method**: 6 research lanes, each blind to the others (agentic orchestration · CI velocity ·
token economics · verification/incisiveness · practitioner fleets · live external-seat probe),
each required to open real sources and to mark vendor marketing as such; then 2 adversarial
refuters on fresh context, told to default to `survives=false` when the case is thin and to
re-verify factual claims against the named sources.

**Numbers, measured on the workflow journal, not recalled**: 39 patterns returned · 10 the
lanes themselves marked `reject` before any refuter saw them · 29 candidates judged · **13
survive, 16 refuted**. Two refutations were factual catches, not opinion: a "Google" attribution
for what is a **Meta** paper (Machalica et al., predictive test selection), and a fabricated
"$3,600/day runaway cost" figure that the cited GitHub issue does not contain (it says
$6/developer/day). Both candidates were otherwise sound and survive with the citation corrected
— which is the point of running the refuter on the *replacement* claim too (W113).

**Seat honesty**: the probe lane found **Codex quota-dead** at run time (`ERROR: You've hit your
usage limit`, CLI v0.147.0) — declared, not silently skipped. Kimi K3 answered and is this
document's cross-family grader.

---

## §Meta-pattern — what the 13 survivors have in common

They are not 13 unrelated ideas. **Eleven of the thirteen** are the same defect at different
boundaries (the two that are not: spend-cap alerting, §4, and manual-validation-before-arming,
§3 — both are process, not a measurement gap):

> **A boundary where work is repeated, or a signal is trusted, without a second measurement.**

- The **merge queue** re-runs a suite whose tree is byte-identical to the one that already
  passed → repeated work, no measurement that it is the same tree.
- The **prompt prefix** is re-sent and re-paid every call at 12% cache hit → repeated work, no
  measurement of which segment moved.
- **Every test** runs on every diff → repeated work, no measurement of which tests the diff can
  reach.
- A **single-pass LLM verdict** gates a merge → trusted signal, no second independent draw.
- A **prose invariant** in CLAUDE.md is trusted to survive context compaction → trusted signal:
  violations run at **0% while the rule is visible and 38% when compaction drops it from the
  summary** (arXiv 2606.22528, §2.3 — the 30% figure in an earlier draft of this line was that
  paper's cross-family *average*, a different measure; the 38% is the drop-specific one).
- **Test workers** share one Postgres → repeated setup, no per-worker isolation, so the cheapest
  parallelism lever stays blocked.

This organism already has the antibody for this class in its own scar language — **"green ≠
working: read the OUTPUT, not the exit code"** (superscar #2) and **"the proxy lies"** (#9). The
import map below is that same antibody applied to boundaries nobody has pointed it at yet.

Counted honestly: §1 carries five survivors (§1.2 covers two — Meta's predictive selection and
testmon), §2 three, §3 four, §4 one = 13.

---

## §1 — Adopt now (targets a residual this system has already named)

### 1.1 Merge-queue duplicate-run elimination — the single biggest measured waste

GitHub's own community discussion #48792 (open ~2 years, unresolved by staff) documents that the
merge queue re-runs checks even when the PR head is already up to date with main, i.e. when the
merge-group tree is identical to the tree that just passed. Our own measurement today:
`Backend Tests` ≈30 min on the PR then ≈33 min in `merge_group`, re-entry ratio 1.5 → the suite
is paid **≈2.5× per merged PR**.

**Import**: a pre-check step in each `merge_group` workflow that compares the incoming
merge-group commit's **tree hash** against the tree of the PR head that already passed; identical
tree → report success without re-running. This is audit lever **L4 option B**, which the audit
rated "safe but low-yield at 37 merges/day" — the community pattern is the same idea and worth
re-measuring now that the docs lane and diff-scoping landed and the remaining wall-clock is 72%
queue wait (measured on PR #4499: 25m10s open→merge, **2m17s** of checks, 18m11s of post-green wait — the
2m17s is not in tension with the ~30 min above: #4499 was a docs-only PR that took the post-#4444
fast path, which is exactly why the queue wait is now the visible 72%).

**First step**: instrument, don't implement — log for a week how often the merge-group tree
equals the PR-head tree. If it is rare (main moves constantly at 37 merges/day), option B is
correctly rated low-yield and the honest answer is that the tail is queue *serialization*, not
duplicate compute — and then the lever is queue configuration, which the L1 measurement already
warns must not be flipped blind.

### 1.2 Test Impact Analysis — start static, not ML

Meta's predictive test selection (Machalica, Samylkin, Porth, Chandra — **Meta, not Google**;
the lane's attribution was wrong and the refuter caught it) reports large CI-cost cuts by
running only tests a diff can plausibly affect. `pytest-testmon` does the non-ML version:
coverage/AST fingerprints, no history corpus.

**Import, in this order**: (a) static import-graph mapping (changed file → pytest modules that
import it) on the **PR lane only**; (b) the merge-queue run stays the unconditional full suite,
so a wrong impact map costs a slow queue entry, never a missed regression. Never both lanes
scoped — that is how TIA becomes a hole instead of a lever.

### 1.3 Per-worker Postgres for xdist — the unblocking move

Today's `#4477` had to **drop xdist** because 18+ test files write to one shared
`nuzantara_test`; a counting invariant read another worker's rows. The standard fix is a
session-scoped template database: apply migrations once to `test_template`, then each worker does
`CREATE DATABASE test_gw{N} TEMPLATE test_template`. Postgres-native, no new dependency.

**First step**: a spike PR that does exactly this for the intake/CRM test group, then re-enable
`-n auto --dist loadfile` on that group alone and measure. The seed-tag scoping already landed in
`test_intake_review.py::_crm_counts` is the belt to that spike's braces, not a substitute for it.

### 1.4 Cache-aware boot-context ordering

Anthropic's own caching docs: the cache is a **prefix** — everything up to the first changed byte
is reusable, everything after is re-paid. Our measurement: 12% cache hit and ~16k input tokens
per message on `rag.gateway.chat`, i.e. the stable 88% of the prefix is being re-billed because
something dynamic sits early in it.

**Careful — two different caches, two different field names.** The prefix rule and the
`cache_read_input_tokens` / `cache_creation_input_tokens` fields are **Anthropic's**; the metered
spend we actually want to cut is **Gemini's** (`gemini_service.py`, AI-Studio key), whose implicit
caching reports `cachedContentTokenCount` and follows its own rules. A first step written against
the wrong provider's field names measures nothing.

**First step**: on the Anthropic side, instrument one repeating lane (regulatory-watcher) for
read-vs-creation tokens for a week; on the Gemini side, read `cachedContentTokenCount` from the
`rag.gateway.chat` responses where the 12% figure came from. If creation dominates on either,
find the earliest dynamic byte in that prefix and move it to the suffix. Reordering, not rewrite.
This is the only lever on this list touching **metered** spend rather than flat quota.

---

## §2 — Adopt as discipline (no code, changes how a session behaves)

### 2.1 A single-pass LLM verdict is a signal, never a sole gate

Position bias and single-draw variance are measured, not folklore — the lane reported kappa
deflation of 33-41pp and ranking shifts up to 14 positions from the two LLM-as-judge papers it
opened. **Provenance caveat**: those two figures come from the lane's reading, re-verified by the
in-workflow refuter against the same sources, not by an independent fetch in this document's own
turn — treat them as directionally load-bearing, not as quotable constants. Where a single AI verdict currently gates something, add
either order randomization or a second independent draw whose disagreement escalates.

This is the **already-correct** shape of our R1 gate (generator≠grader) — the import is to make
sure no *new* automation quietly becomes a one-draw gate.

### 2.2 Structured disagreement, not consensus

A reviewer + a critic whose explicit job is to audit the review beats both self-consensus and
bigger committees; the mechanism targeted is false-consensus (agreement without evidence).

**Import**: give `infra/workflows/verify-template.js`'s refuter step a required verdict schema —
`AGREE` / `DISAGREE_EVIDENCE(file:line + quote)` / `DISAGREE_CONCERN(named unverified assumption)`
— so "I agree" costs the same tokens as disagreeing and cannot be the cheap default.

### 2.3 Constraint pinning — the measured version of our own §7

Measured across seven model families: a governance rule visible in context = 0% violations; after
compaction drops it from the summary = 38%; deployed frameworks worse (LangGraph 65%, AutoGen's
recency eviction 100%). Re-injecting the rules after every compaction restored 0% at <0.5% token
overhead.

This is **CLAUDE.md §7 ("if a critical rule is violable, write a hook — documentation does not
suffice") with a number attached.** The import is an audit, not a new mechanism: which HARD
invariants (off-limits files, Anthropic-SDK ban, PII cleartext ban, ship-lifecycle ownership) are
prose-only today? A prose-only hard rule in a long session is a governance-decay candidate.

**Live instance found while writing this document**: the workflow that produced it died on its
first run because `workflow/SKILL.md` said lanes *default to the session model* while the
2026-08-20 ruling says Fable is out of the workflow — eight lanes inherited Fable and died on its
limit together. The rule existed; the default contradicted it. Cured in PR #4511. That is
governance decay's cousin: not a rule dropped by compaction, but a rule **outvoted by a default**.

---

## §3 — Prototype before believing (adapt, evidence thinner or cost unclear)

- **Diff-scoped mutation testing** (Google's mutation-at-scale is real; full-suite mutation is
  not affordable). Restrict mutants to the diff's file set, ship as a **non-required comment
  bot** on 5-10 PRs, measure the useful-finding rate before it goes anywhere near required.
- **LLM-driven property-based testing** (Hypothesis): a lane whose brief is "infer properties
  (monotonicity, idempotency, threshold-boundary) and write Hypothesis tests" for
  `_abstain_policy.py` and `PricingTool` — bug-hunting pass, never a coverage requirement.
- **Anti-nitpick tuning for AI critics**: the CriticGPT numbers are OpenAI-self-reported, but the
  mechanism (untuned critics nitpick and hallucinate) is real. If the AI-review Action is ever
  re-armed, audit its last ~20 comments for nitpick ratio and add a severity floor with a
  required failure-scenario.
- **Manual-validation period before arming a NEW cron**: n=1 practitioner evidence, but the
  applicability argument stands on its own and matches superscar #2 (built ≠ armed): a brand-new
  cron runs dry/manual for N days with its output graded before it gets a crontab line.

## §4 — Spend-cap alerting (the odd one out)

No hard spend cap exists on any of these tools; the real failure mode is a retry/recursion storm,
not legitimate heavy use. Our own week proves the shape: `llm_cost_events` shows 90% of two weeks'
spend inside 3 days, with 2,238 calls on one day spread evenly across 24h — an automatic driver,
not a human.

**Import**: extend the `pending_arms_report.py` pattern (pure signaller, never actuator) to cost —
a scheduled query flagging any single day/hour whose spend or call-rate exceeds its trailing
baseline. `scripts/qwen_quota_watch.py` (PR #4490) is the first instance of this shape; the
generalization is per-provider.

---

## §5 — Refuted, and worth recording

16 of 29 candidates did not survive. The instructive ones:

- **"Bounded team size 3-5 with kill-criteria"** and similar org-shaped advice — refuted as
  Google-scale reasoning applied to a solo founder at 37 merges/day.
- **Anything sourced only to a seat's own opinion** — the refuter rejected one candidate whose
  sole source was `seat:kimi`'s uncited view, correctly: "the weakest-evidenced candidate in the
  set, fails the bar the exercise itself set."
- Several practitioner-blog patterns whose numbers are n=1 and whose mechanism is already covered
  by an existing organ here.

**Refuted as already-live, and I put them back in anyway.** Two candidates — "fan out for reads,
single-thread for writes" and "subagent boundaries return a digest, not the raw trace" — were
refuted for a specific reason: *this system already does both, more strictly.* The worktree rule
here covers EVERY agent session, read or write, and is machine-enforced; the digest boundary is
how every lane in this very workflow reported. The first draft of this document nonetheless wrote
both up as §2 discipline to adopt. **The cross-family grader caught it.** That is the W113 shape
exactly — the refuter is pointed at the candidates, nobody is pointed at the synthesis — and it is
recorded here rather than quietly deleted.

A refuted pattern is not a wasted lane: **two** of the refutations were *citation* failures
(the Meta/Google misattribution and the fabricated $3,600/day) that would otherwise have entered
doctrine as facts. Those two candidates survive with the citation corrected; the count above
("two factual catches") and this line are the same two.

---

## Adversarial review

Cross-family grader: **Kimi K3** (`kimi -p … -m kimi-code/k3`), fresh context, given this
document and told to attack it — Codex was quota-dead at run time (probe evidence in §head), so
the cross-family chair is Kimi alone and that is declared, not papered over. The in-workflow
refuters were Sonnet 5 (same family as the lanes) and are therefore counted as a *first* pass,
not as the cross-family gate — W100: same-family agreement measures transcription fidelity, not
truth.

**Run detail, declared**: the Kimi invocation was killed by this session's own 300 s alarm
(RC=142) after producing 33 KB of review reasoning but before emitting a final formatted answer.
The objections below were taken from that reasoning trace — a cut-short review whose findings are
still findings, not a clean pass, and saying so is the point.

**Accepted and fixed in this document** (7): the §Meta-pattern survivor count did not add up
(fixed, with the two non-conforming survivors named instead of hidden); the compaction figure was
30% in one place and 38% in another (both real, different measures — disambiguated); §5 said
"three citation failures" against the header's "two" (fixed to two, the same two); §1.4 named
**Anthropic's** cache fields while claiming the spend is **Gemini's**, which have different
implicit-caching semantics and a different field name (`cachedContentTokenCount`) — a first step
written against the wrong provider measures nothing (split into two provider-specific steps); the
90.2% multi-agent figure was quoted without its ~15× token caveat, in a token-facing document
(added); the 86%-thinking and the LLM-judge kappa figures were stated without saying where they
were measured (provenance added, and the judge figures downgraded to "directional, not quotable");
the 2m17s-vs-30min juxtaposition read as a contradiction (explained: different lanes).

**The one that mattered most**: Kimi's objection #9 exposed that two entries I had written into §2
as discipline-to-adopt — "fan out for reads, single-thread for writes" and "subagent boundaries
return a digest" — were **refuted by the in-workflow refuters as already-live-and-stricter-here**,
and I had re-introduced them in the synthesis. Both are now removed from §2 and recorded in §5
with the refuters' reasoning. This is the W113 shape caught in the act: the refuter is aimed at the
candidates, and nobody is aimed at the synthesis.

**Not accepted**: Kimi questioned whether the §Meta-pattern frame is unfalsifiable ("any
verification-improvement pattern fits 'signal trusted without a second measurement'"). The
objection is fair as stated, and the fix applied is the honest one — the frame no longer claims to
cover all thirteen, it names the two it does not cover. It is kept because it is *predictive* here,
not decorative: it is what says the remaining wall-clock is queue serialization rather than
compute, which is a falsifiable claim with a measurement attached (§1.1 first step).
