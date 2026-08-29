---
date: 2026-08-30
domain: compliance
client_case: none
sources:
  - PR #5218 (SUSPENDED draft, head a1799989d) — the lint this spec replaces
  - scripts/mq_state_verdict.py (origin/main @ 5066d7a8d) — attestation order, no NOT_ARMED verdict
  - scripts/queue_shepherd.py (origin/main @ 5066d7a8d) — is_rearm_candidate, run_rearm_pass
  - scripts/ci/queue_rearm.sh + scripts/lane_ship.sh (origin/main) — the refusal-text convention
  - .claude/rules/cicatrix-scars.md — W111, W123 (GOTCHA a/b), W126
adversarial_review: codex
---

# L06-PR2b successor — the queue-field surface has an unresolved DOCTRINE, not a missing lint

> **Status: SPEC — no code changed by this document.** It discharges the Rule-8 suspension of
> PR #5218 (`ci(queue): a regression guard with zero catches today`), stopped because its rule's
> PREMISE was false rather than its implementation. Rule 8: *if the correction is itself wrong,
> the surface is under-specified — write the spec, do not open the third PR.*
>
> Date: 2026-08-30 · Author: Squad W (workflow track), Opus 5 · Base: `origin/main` @ `5066d7a8d`
> · Lineage: L06 lane, `docs/plans/2026-08-29-beyond-sota-craft-wave/`
>
> **This document was rewritten wholesale after its first draft was refuted.** Codex GPT-5.6 sol
> returned DO-NOT-SHIP with 3 BLOCKER + 3 HIGH; five of the six were reproduced on disk and are
> load-bearing here. What the first draft got wrong is recorded in §Adversarial review rather
> than quietly deleted, because the errors are the same class the spec is about.

---

## TL;DR

1. **The suspended lint is genuinely broken** — both blockers reproduced this turn (§1). It stays
   suspended; do not re-open it.
2. **The repo holds a three-way, unresolved split on what `auto=null AND queue=null` means** (§2).
   One of the three is the auto-loaded cicatrix file every session reads. **This spec cannot settle
   it** — settling it needs a primary artifact (the PR #5036 receipt) that no one has preserved.
   Everything downstream is blocked on that, and saying so is the deliverable.
3. **The one concrete, measured defect is a false human-escalation alert**, not a bad merge and not
   a spurious re-arm (§3). `queue_shepherd.py` in the disputed window sends a P0 saying a PR "looks
   disarmed" and stops. It never calls `gh pr merge`.
4. **The "cure" the first draft proposed already exists** in `queue_rearm.sh` and `lane_ship.sh`
   (§4). `queue_shepherd` is the outlier among its own siblings — which reframes the work from
   "invent a convention" to "one organ diverges from a convention the repo already keeps."

---

## 1. The suspended lint: both blockers reproduced on disk (2026-08-30)

PR #5218 shipped `scripts/ci/lint_queue_field_verdict.py`: for any tracked file containing a
null-comparison on `autoMergeRequest`, require the SAME file to also mention `mergeQueueEntry`,
`isInMergeQueue`, `"already queued"`, `"mq state"`, or an explicit waiver.

Head tree `a1799989d` extracted with `git archive | tar -x` and `git init`-ed, because the tool's
`git ls-files` gathering exits **3 (CANNOT VERIFY)** without a repo — correctly fail-closed.

**BLOCKER 1 — the rule absolves the disease.** Added:

```python
def verdict(pr):
    if pr.get("autoMergeRequest") is None:
        if pr.get("mergeQueueEntry") is None:
            return "AUTO-MERGE DISARMED — re-arm needed"
    return "armed"
```

→ **rc=0**, probe file appears **0 times** in the output. It reads both fields, so it clears the
rule, while being precisely the shape the rule exists to catch.

**BLOCKER 2 — the allowlist tripwire is form, not entity.** Appending an unconditional
`gh pr merge --auto "$PR" || true` to the orchestrator whose awareness the waiver rests on
(`scripts/ci/queue_rearm.sh`) leaves the scan **rc=0** and the tripwire still printing
`orchestrator … still carries: mergeQueue(, already in the queue`. It asserts the words are
PRESENT, never that the guard is EFFECTIVE.

Both reproductions restored the tree and re-ran clean.

**Also measured: the obvious replacement discriminator fails too.** Switching the rule to *"the file
emits a disarm verdict"* flags `scripts/mq_state_verdict.py` **9 times** — and those nine are its
docstring *explaining why the verdict must not exist*. A guard firing on the prose that warns against
the disease is this repo's W108/W112 shape, hit on the second attempt.

## 2. The unresolved doctrine — and this is the deliverable

Three artifacts on `origin/main` @ `5066d7a8d` answer *"what does `auto=null AND queue=null` prove?"*
and they do not agree:

| # | artifact | position |
|---|---|---|
| A | `.claude/rules/cicatrix-scars.md:1279` (W123 GOTCHA b) | `queue:false + auto:null` = **«disarmata davvero»** |
| B | `scripts/mq_state_verdict.py:11-24` | **no** instantaneous joint read can prove NOT ARMED; the module therefore has no `NOT_ARMED` verdict |
| C | `scripts/queue_shepherd.py:233-236` | *"Only BOTH null means truly disarmed, which is the only state this organ may act on"* — agrees with A |

**The first draft of this spec asserted B as settled fact and called C a contradiction of it.** That
was wrong in a way worth recording: A is in the file auto-loaded into **every** session, so the
majority doctrine — and the one with the widest reach — is the one B denies. Promoting B's docstring
to a measured fact was the exact move (§1) the suspended lint made with its own premise.

**What would settle it.** B cites PR #5036 — *"both fields read 'not armed' while 32 queue-branch
runs existed"*. Searched this turn: the repo preserves that claim in B's docstring and in a
**synthetic** fixture (`scripts/tests/test_mq_state_oracle.sh:79`, which fabricates
`autoMergeRequest:null, mergeQueueEntry:null, matched:32`). A fixture built from the claim cannot
corroborate the claim. **No primary receipt — no API/timeline capture from #5036 — exists in-tree.**

> **BLOCKING PREREQUISITE.** Until a primary #5036 receipt (or a fresh live reproduction of the
> transient) is produced and committed, B is a **hypothesis**, A and C are **unrefuted**, and no
> guard, lint, or organ change on this surface should be built — any of them would harden one side
> of an open question with CI's authority. This is the whole reason the surface is under-specified.

## 3. The one concrete defect, traced rather than inferred

Assume B for a moment (the transient exists). Then `queue_shepherd.py` — LaunchAgent
`com.nuzantara.queue-shepherd.10min.plist`, every 10 minutes — does this:

| step | site | result in the disputed window |
|---|---|---|
| candidate gate | `queue_shepherd.py:238-250` | BOTH-null **passes** — it is the only state the organ acts on |
| last ejection event | `:515-536` | last item is `Added` (or none) → **`None`** |
| classify | `:176-196` | `None` → **`UNKNOWN`** |
| decide | `:913-923` | not allowed → **`send_telegram("PR #N looks disarmed … Needs a human look")`** → `continue` |

**`rearm_pr` is never reached.** The first draft of this spec claimed the organ "attempts a re-arm
and GitHub refuses"; that path requires a prior `Removed` event still last AND classified `INFRA`.
The draft modelled the candidate gate and stopped, then built a cure on the inferred remainder — the
same defect it was documenting.

So the harm is **a false P0 to a human**, saying a PR is disarmed when it is (per B) armed and
entering the queue. Severity is **not** the first draft's "P3, spurious mutation, mostly harmless":

- the alert consumes the shared Telegram budget, which `scripts/tg_notify.py:519-540` documents as
  **exhausted 8 days of 21**, with a critical backup alert already having gone slot-less;
- `alerted_state` dedups only a **delivered** alert (`:920-921`), so a send that fails is retried
  every tick;
- re-arm and janitor passes are serial (`:1048-1049`), so false candidates delay `cancel_run`.

**Correct severity: undetermined, plausibly P2, and it must be measured before it is asserted** —
frequency of the transient, `UNKNOWN`-vs-`INFRA` distribution, and actual P0 consumption. Naming a
severity without those numbers is what the first draft did.

## 4. The refusal-text convention already exists — `queue_shepherd` is the outlier

The first draft "proposed" classifying the refusal text of `gh pr merge --auto`. Measured this turn,
that is **already this repo's convention**:

- `scripts/ci/queue_rearm.sh:229-231` — *"Judge the REPLY, not only the exit code (W104): 'already
  queued' is success, and a zero rc on an unexpected message is not."*
- `scripts/lane_ship.sh:235` — same shape, matching `already queued|auto-merge enabled|already
  enabled|clean`.

And the first draft's cross-tab was wrong about its own population: `scripts/queue_unstick.py:29-37`
states explicitly that it *never* reads `autoMergeRequest` and never asserts an armed/disarmed
verdict; `queue_doctor.py:71-107` reports populations rather than deciding a re-arm. The honest
population is **`queue_shepherd.py`**, not five files, and the finding is that one organ diverges
from a convention its siblings keep.

**This does not make refusal-parsing the answer.** It is itself a form-not-entity gesture — a string
match on an error message, brittle to `gh` version, locale, stdout-vs-stderr, and rephrasing, and
liable to read `ALREADY_ARMED` out of an unrelated error containing the fragment. If it is ever
adopted in `queue_shepherd` it needs a fresh positive read of the queued entry after the refusal,
unknown wording **fail-closed**, and a `gh`-version-bound adapter.

## 5. Acceptance criteria — ordered, and the first one gates the rest

- **A0 (BLOCKING, prerequisite).** Produce and commit a primary receipt for the #5036 transient, or a
  fresh live reproduction. Until then A1-A4 must not be attempted. If the transient cannot be
  reproduced, the correct outcome is the **opposite** change: reconcile B toward A/C and delete the
  oracle's claim — the doctrine, either way, must end up single-valued.
- **A1.** Measure the defect before fixing it: transient frequency, `UNKNOWN`-vs-`INFRA` split, P0s
  emitted per week attributable to this branch, and janitor delay. Severity is then stated from
  numbers.
- **A2.** `queue_shepherd.py:233-236`'s docstring stops asserting a side of an open question and
  cites whichever artifact A0 leaves standing.
- **A3.** If (and only if) A0 confirms B: the `UNKNOWN`-branch P0 gains a disambiguating step before
  alerting. Guilt fixture — the transient shape produces **no** alert; innocence — a genuinely
  disarmed PR with no ejection event **still** alerts. Neither may be satisfied by prose.
- **A4.** Mutation-verified: inverting the disambiguator turns A3's guilt case red. Run with
  `PYTHONDONTWRITEBYTECODE=1` (W121 — a same-length mutation written in the same second is judged
  against a cached `.pyc`, and the verdict is manufactured by the filesystem).

## 6. What this spec explicitly does NOT recommend

**Do not re-open the lint.** Two textual discriminators were measured and both fail: "reads both
fields" absolves the disease (§1); "emits a disarm verdict" convicts the oracle's own warning prose
(§1). This refutes **those two lexical heuristics** — it does not prove no guard is possible. An
AST/dataflow check, a structural delegation rule, or a behavioural gate remain open designs. But
none of them may be built before A0, because all of them would encode one side of §2.

**Do not widen any existing gate's scope to cover this.** The population is one organ.

## 7. Evidence provenance

| claim | how |
|---|---|
| #5218 BLOCKER 1 + 2 | reproduced on `a1799989d`, this turn, rc=0 both |
| "emits a disarm verdict" flags the oracle's prose 9× | `grep -icE "DISARMED|re-?arm needed|not[ _]armed" scripts/mq_state_verdict.py` → **9** on `origin/main`, this turn. The regex is declared here because the first draft left it implicit and the count was correctly called irreproducible. |
| the three-way doctrine split (A/B/C) | all three read on `origin/main` @ `5066d7a8d`, this turn |
| **no primary #5036 receipt in-tree** | searched this turn; only B's docstring + a synthetic fixture |
| `queue_shepherd` control flow to the P0 | four sites read in sequence on `origin/main`, this turn |
| Telegram budget exhausted 8/21 days | `scripts/tg_notify.py:519-540` — read by the refuter, **not independently re-measured by me** |
| refusal-text convention already in 2 files | `queue_rearm.sh:229-231`, `lane_ship.sh:235`, this turn |
| `gh pr merge --auto` refusal wording | **RECORDED, NOT re-measured** — `cicatrix-scars.md:1248` (**W123**, not W126); that record carries no rc |

## Adversarial review

**Seat: Codex GPT-5.6 sol (`gpt-5.6-sol`, effort xhigh), blind, non-Anthropic — generator ≠ grader.**
Round 1 on the first draft: **DO-NOT-SHIP, 3 BLOCKER + 3 HIGH.** Five findings reproduced on disk by
the author before disposition; the sixth accepted on argument.

| # | finding | disposition |
|---|---|---|
| B1 | The BOTH-null premise is laundered from a docstring; `cicatrix-scars.md:1279` asserts the opposite | **CONFIRMED on disk. Rewrote §2** from "the oracle is right, the organ is wrong" to a three-way unresolved split, and added A0 as a blocking prerequisite. The draft's central claim is now a hypothesis. |
| B2 | The `queue_shepherd` harm model is invented; `rearm_pr` is unreachable in the disputed window | **CONFIRMED on disk** (four sites traced). §3 rewritten: the defect is a false P0, not a spurious re-arm. The draft's §4 cure targeted a path the defect never reaches — deleted. |
| B3 | A1 mis-cites the refusal string to W126; it is W123 and carries no rc. The classifier is under-specified and is itself form-not-entity | **CONFIRMED on disk** (line 1248 = W123). Citation fixed in §7; §4 now argues *against* refusal-parsing as the answer and lists the conditions it would need. |
| H4 | P3 ignores implemented harm: P0 budget, retry-on-failed-send, janitor serialization | **ACCEPTED.** Severity downgraded to *undetermined* with A1 requiring numbers first. The `tg_notify.py` budget figure is the refuter's measurement, flagged as such in §7 rather than restated as mine. |
| H5 | The cross-tab's semantic classification is false; `queue_rearm.sh`/`lane_ship.sh` already parse the refusal; `queue_unstick.py` does not read the field | **CONFIRMED on disk.** §4 rewritten — the population is one organ, not five, and the proposed "cure" was already the repo's convention. This inverted the draft's headline. |
| H6 | "Not lintable in any form" overreaches: two lexical heuristics refuted ≠ no guard possible | **ACCEPTED on argument** (no disk check needed — it is a logic error). §6 narrowed to the two measured heuristics; AST/dataflow/behavioural guards recorded as open, gated behind A0. |

**Not deferred, declined, or argued away: all six changed the document.** The regex behind the
draft's "disarm hits" column was challenged as undeclared and irreproducible (the refuter's own
case-sensitive variant produced different counts) — that column was **deleted** rather than
re-derived, because §4 removed the claim it supported.

**What round 1 could not test:** the spec's core prerequisite A0 is precisely the artifact neither
seat can produce from the repo. That is not a gap in the review — it is the finding.
