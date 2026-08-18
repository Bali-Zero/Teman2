---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/e4/fact-schema-v2-proposal.md
  - path: research/visa/doctrine-factory/e4/question-registry-audit.md
  - path: research/visa/doctrine-factory/e4/branch-graph.md
  - path: research/visa/doctrine-factory/e4/parity-harness-rescope.md
adversarial_review: kimi-k3
---

# CP2 decision request — fact-schema approval (E4 slice)

Owner-facing summary. CP2 is a Zero-only gate (execution plan §0, "Gate owner registrati" table) — this
pack does not self-approve anything; it is the material for Zero's decision.

## What this pack found, in one paragraph

The 2026-08-12 fact-vocabulary-extension design (the document this E4 slice was told to build on) proposed
6 new legal discriminator facts for 7 "blocked" visa product codes. Checking those 7 codes against the real
114-code catalog this session found **every one is misidentified** — the design's regulatory lane invented
plausible-sounding legal questions (Top-100-university talent, RPTKA employment tiers, technical-service
vs full-employment) for products that are actually Second Home government-invitation/golden-visa variants
and diplomat/trade-office work visas. None of the 6 proposed facts survive contact with the actual product
identity. This pack recommends dropping all 6 and re-scoping that work to E3 (product-identity + doctrine
pinpoint hunt), which is not something E4 can do on its own.

What DOES survive and IS ready for approval: a small, non-breaking set of decisions on the 5 currently
NOT_ASKED facts, a reclassification proposal for the interview's 12 HUMAN_CONTEXT lanes, and a generated
branch graph + re-scoped parity harness mechanism — all traced to measured facts on disk, none of it
requiring a wire-contract breaking change.

## What Zero approves at CP2

1. **Fact schema for this slice: 0 new required wire keys, 2 semantic-value changes on existing keys.**
   Not a breaking change to the shadow POST contract (`fact-schema-v2-proposal.md` §3). Nothing to sign off
   on the versioning/deploy-order mechanics — there is no version bump in this proposal.
2. **Ask-or-drop disposition on the 5 NOT_ASKED facts** (`fact-schema-v2-proposal.md` §2):
   - Drop permanently: `intent.requested_product_code` (architectural — never let the tool ask what it
     exists to answer).
   - Drop for now, revisit under OD-5 (telemetry/DPIA gate): `commercial.service_fee_budget_idr`,
     `commercial.wants_quote`.
   - Recommend ask, gated on E5 shipping a consuming rule first: `immigration.last_entry_date`,
     `intent.desired_entry_date`.
   - **Net: 0 of 5 asked unconditionally by this proposal.** Zero rules need removal in E5 as a consequence
     (all three drops are already zero-rule in the active pack).
3. **12 HUMAN_CONTEXT lane reclassification split** (`question-registry-audit.md` §3):
   - 2 dead-node cleanup (`tourism_duration`, `remote_income` — delete, not a doctrine decision).
   - 2 structural-forever REVIEW_ONLY (`other_purpose`, `other_paid_activity` — the catch-all category has
     no closed doctrine by design, not a gap to close).
   - 4 REVIEW_ONLY pending E3 claims (`business_activity`, `work_role`, `diaspora_connection`,
     `diaspora_documents`).
   - 3 real-fact-question candidates (`trip_scope`, `investment_vehicle`, `retirement_basis`) — approval
     here is "candidate for promotion, subject to E3/E5 authoring the actual FactPath + rule", not an
     immediate schema change.
   - 1 hard sequencing constraint (`family_sponsor_status_code`) — cannot change until the E31B pack rule
     fix lands in E5; this is not optional, it is a fail-open containment currently doing its job.
4. **Branch graph + parity harness mechanism** — process approval only, no immediate test-suite change
   (`parity-harness-rescope.md` §3: the mechanism degenerates to pure regression-fence today because no
   Tier-B claims exist yet).

## Options where a real choice exists

| Decision | Option A | Option B | Recommendation |
| --- | --- | --- | --- |
| `immigration.last_entry_date` / `intent.desired_entry_date` — when to add the interview question | **Gate on E5 shipping a consuming rule first** (this pack's default) | Add the question now, ahead of any rule, to start collecting data early | **A** — adding UI with no doctrine behind it is the exact failure mode §0 found in the source design; B trades a small time saving for repeating that mistake at smaller scale |
| `trip_scope`/`investment_vehicle`/`retirement_basis` — promote to real FactPath now or wait for E3 claims | **Wait for E3** (this pack's default) | Pre-approve the FactPath name/shape now so E3 only needs to supply the claim, not design the fact | **B is worth considering** if Zero wants to unblock E3 doctrine work from waiting on a second fact-ontology round-trip — this pack did not pre-design the FactPath shapes for these 3, since doing so without knowing what the claim actually says risks repeating §0's mistake at a smaller scale. If Zero wants this, say so explicitly; it is not this pack's default. |
| The 6 dropped E23U/E23V/E30E/E30F/E33A/E33B/E33C facts — re-authorize the *concept* of these discriminators, or treat the whole line of inquiry as closed pending fresh E3 work | **Re-scope to E3, no schema decision now** (this pack's default) | Zero could instead direct a fast E3 fact-hunt specifically for these 7 codes before E5, given they're 7 of the 11 BLOCKED products (informing the OD-4 disposition decision) | **A** — CP2 is a fact-*schema* gate; committing to 6 concrete fact shapes before the underlying legal question is even correctly identified would just relocate §0's failure mode into an approved schema. Recommend Zero direct E3 to prioritize these 7 codes' doctrine (separately from this CP2 decision), then bring a fresh fact-schema addendum once real claims exist. |

## What is blocked until CP2

- E5 rule authoring for the 5 NOT_ASKED facts' disposition (cannot compile rules against facts whose
  ask-or-drop status is undecided).
- Any interview UI change to the 12 HUMAN_CONTEXT lanes (E6) — the reclassification split above is the
  precondition E6's copy-deck work needs.
- Nothing else in the broader execution plan is gated on CP2 specifically — E2b (bulk claim ledger), E3
  (doctrine cards for the 11 BLOCKED products, including the 7 misidentified ones), and QW-series items all
  proceed independently per the plan's dependency graph.

## Adversarial review

(Review dispositions — this document's R1 gate section.)

Kimi K3 refutation run against the finished pack (narrow scope: facts without claim backing, wire-contract
impacts missed, reclassifications that reintroduce the veto), 2026-08-17, wall time ~90s (`kimi -m
kimi-code/k3`, within the 8-minute timebox, no GLM fallback needed). 4 findings raised, 2 REFUTED (real
defects, both cured), 2 SOSTENUTO (claims held). Each of the 4 design docs' "## Adversarial review" section
carries the per-finding detail and the exact cure applied; summary:

| # | Finding | Verdict | Cured in |
| --- | --- | --- | --- |
| 1 | `question-registry-audit.md` overstated claim backing for the `trip_scope` real-fact candidate (cited `CL-D1-03`/`CL-D2-03`, which are product-duration claims, not interview-branch-semantics claims) | REFUTED | `question-registry-audit.md` §3 row 1 |
| 2 | `fact-schema-v2-proposal.md` §3 invoked the wrong lemma (`UΔ`/`NΔ` identity proof) to justify the `NOT_ASKED→KNOWN` value flip on 2 existing wire keys; correct safety argument is the zero-rule status of both FactPaths | REFUTED | `fact-schema-v2-proposal.md` §2/§3 |
| 3 | `question-registry-audit.md` §4 numeric slip ("4 have a fixed sequence" before listing 7) | REFUTED (textual) | `question-registry-audit.md` §4 |
| 4 | `family_sponsor_status_code`/E31B sequencing constraint correctly avoids reintroducing the fail-open across all 3 documents that touch it | SOSTENUTO | No change |

No finding required re-opening §0's headline conclusion (the 6 dropped E23U/E23V/E30E/E30F/E33A/E33B/E33C
facts) or the 5-fact ask-or-drop disposition (§2) — both held under adversarial pressure.
