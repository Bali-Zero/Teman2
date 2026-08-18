---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/shadow-parity.ts
    note: "QW-2's baseline-parity mechanism this rescope builds on (merged, per task briefing — PR #4234)"
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/preview-adapter.ts
    note: "buildPreviewOutcome, the independent-oracle mechanism QW-2 fixed"
  - path: research/visa/doctrine-factory/e4/question-registry-audit.md
    note: "the 12 HUMAN_CONTEXT lanes this rescope fences by reform-touch status"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "claim_id source for the reformed-lane expected mechanism"
adversarial_review: kimi-k3
---

# Parity harness re-scope — E4 slice

Per the execution plan §E4 item (c): "parity harness ri-scopato: fence di regressione SOLO sulle superfici
che la riforma NON tocca; per le superfici riformate... gli expected vengono dal claim ledger (oracolo
dottrinale), e ogni divergenza dal legacy è tracciata a un claim_id — mai eccezioni nominate generiche."

## 1. Measured test surface (correction to the task briefing's "~243")

Counted this session, not carried from memory: `apps/mouth/src/app/(visa-oracle)/**/*.test.ts` (the whole
region, not just `_lib/`) has **266 top-level `it()`/`test()` cases** across 23 files, plus 2 Playwright
e2e spec files (`visa-oracle-fullstack.spec.ts`, `visa-oracle-v2.spec.ts`) whose case count was not
separately tallied (Playwright specs commonly nest `test.describe` blocks the same grep undercounts). The
task briefing's figure of "~243" is close but does not match either number exactly measured here (218 in
`_lib/` alone, 266 across the wider region). **Recommendation: treat "~243" as approximate provenance from
an earlier count** (plausibly `_lib/` at a prior commit, or a different inclusion boundary) rather than
re-deriving a fresh canonical number in this design doc — the fence mechanism below (§2) does not depend on
the exact total, only on the reform-touch/no-touch partition, which is enumerable directly from
`question-registry-audit.md` §3's 12-row table regardless of how many test files reference each lane.

## 2. Two-tier fence

### Tier A — regression fence (unreformed surfaces)

Everything the RC-1 veto reform does **not** touch: the entry spine (10 questions, `branch-graph.md`), the
7 fixed-sequence categories' non-HUMAN_CONTEXT questions, the 3 dynamic categories' non-HUMAN_CONTEXT
branch logic, and 8 of the 12 HUMAN_CONTEXT lanes that are **not** reclassified to a real fact question in
this proposal (the two structural-forever lanes `other_purpose`/`other_paid_activity`, the two dead nodes
`tourism_duration`/`remote_income` — deleted, not fenced — and the 4 REVIEW_ONLY-pending-E3-claims lanes
`business_activity`/`work_role`/`diaspora_connection`/`diaspora_documents`, whose *classification* changes
in name only, not in interview behavior, per `question-registry-audit.md` §3).

**Rule for Tier A: existing test expecteds are the fence.** Any test whose assertion touches only these
surfaces must produce **byte-identical output before and after** the E4/E5/E6 changes land — this is a pure
regression suite, no claim ledger consultation needed, because nothing about these surfaces is asserted to
change. A failing Tier-A test after a reform PR is either (a) an accidental scope leak from the reform
(bug, must be fixed) or (b) an intentional dependency the reform PR failed to declare (must be re-classified
into Tier B with an explicit claim_id, never silently accepted).

### Tier B — reformed-lane expected-from-ledger (5 touched lanes)

The 5 HUMAN_CONTEXT lanes this proposal actually reclassifies to a different runtime behavior:
`trip_scope`, `investment_vehicle`, `retirement_basis` (→ real-fact-question candidates) and
`family_sponsor_status_code` (→ eliminate-as-direct-fact, REVIEW_ONLY input to the E31B-gated mapper). Any
test asserting behavior on these 5 lanes **cannot use the pre-reform legacy expected as ground truth** — the
whole point of the reform is that the legacy behavior (HUMAN_CONTEXT, non-decisional) is what is being
replaced.

**Mechanism**: for each Tier-B assertion, the expected outcome is derived from the claim ledger
(`e2a-claim-ledger.md` / `e2b-batch1-claim-ledger.md` / `e3a-cf1-resolution.md`), keyed by `claim_id`
(format `CL-<code>-<NN>`, e.g. `CL-D2-03`). A divergence between the legacy test's expected and the
claim-derived expected is not silently accepted or silently overwritten — it is **traced**:

```
divergence_trace:
  test: "<test file>::<test name>"
  lane: "<question id>"
  legacy_expected: "<value the pre-reform test asserted>"
  ledger_expected: "<value derived from the cited claim>"
  claim_id: "CL-XXXX-NN"
  disposition: "ADOPT_LEDGER | KEEP_LEGACY_PENDING_CLAIM | ESCALATE"
```

**No generic "known exception" list.** Per the task briefing's explicit instruction, a divergence is never
absorbed into an unlabeled exceptions file — every single one carries its own `claim_id` or is blocked
(`KEEP_LEGACY_PENDING_CLAIM`) until one exists. `family_sponsor_status_code` is the one lane where
`KEEP_LEGACY_PENDING_CLAIM` is mandatory regardless of claim availability, because of the E31B sequencing
constraint (`question-registry-audit.md` §3.1) — its expected cannot flip to a KNOWN-emitting behavior until
the E5 rule fix lands, independent of whether a claim exists for the sponsor-status doctrine itself.

**Currently zero claim_ids exist for any of the 5 Tier-B lanes.** Checked directly against the two merged
ledgers and the fetched `e2b-batch1` branch: `e2a-claim-ledger.md` covers D1/D2/D12/E31B/E31D-refuter only;
`e2b-batch1-claim-ledger.md` covers the E33/retirement family, A1/B1/C-series, E28A, E30/E30A/E30B; neither
contains a claim about trip-scope classification, investment-vehicle taxonomy, or retirement-basis
taxonomy as interview-facing discriminators (they cover the *products'* eligibility rules, not the
*interview's* branch-selection semantics — a different claim shape). **This means Tier B currently has no
tests to write against real claims** — the mechanism is specified here, but its first real use is gated on
E2b/E3 producing claims that discuss interview-branch semantics specifically, not just product eligibility.
Flag for E5: do not treat "0 claims cited yet" as "0 divergences exist" — it means the fence cannot yet
distinguish ADOPT_LEDGER from ESCALATE for these 5 lanes, so **until claims exist, all 5 default to
`KEEP_LEGACY_PENDING_CLAIM`**, which is the safe, conservative default (equivalent to leaving them in Tier A
until proven otherwise).

## 3. What this means for CP2 in practice

Because none of the 5 Tier-B lanes has a claim yet, **the parity harness re-scope currently degenerates to
Tier A only** — every existing test remains a hard regression fence until E3/E5 produce claims specific to
interview-branch semantics for `trip_scope`/`investment_vehicle`/`retirement_basis`, and until E31B's rule
fix lands for `family_sponsor_status_code`. This is not a gap in this design — it is the honest state of the
doctrine today, and it means **no test suite behavior needs to change as a direct consequence of approving
this proposal at CP2**. The mechanism (§2) is what E5/E6 implementers use once claims exist; approving it
now unblocks that future work without forcing any test rewrite today.

## Adversarial review

Kimi K3 refutation, narrow scope (facts without claim backing, wire-contract impacts, HUMAN_CONTEXT
reclassification/fail-open), 2026-08-17, run against the full 5-doc pack at once. This document's central
claim — "zero claim_ids exist for any of the 5 Tier-B lanes" — was independently used by the reviewer to
REFUTE a claim in `question-registry-audit.md` (the `trip_scope` row's overstated `CL-D1-03`/`CL-D2-03`
citation, cured there), which corroborates rather than contradicts this document's own §2 finding. No
defect was found in this document itself.
