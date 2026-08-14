---
date: 2026-08-15
domain: visa
client_case: none — Visa Oracle v2 G-b divergence disposition matrix
sources:
  - research/visa/2026-08-12-gold-replay-live-report.json
  - research/visa/2026-08-12-gold-replay-live.md
  - research/visa/2026-08-15-gold-family-refuter.md
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
  - apps/backend-rag/backend/tests/services/visa_engine/_gold_fixtures.py
  - https://github.com/Bali-Zero/Teman2/pull/4195
  - https://github.com/Bali-Zero/Teman2/actions/runs/31828149383
adversarial_review: kimi-k3
status: DRAFT — proposed dispositions; no divergence accepted without owner or legal approval
---

# Visa Oracle G-b divergence disposition matrix

**Evidence scope:** the first live replay of the 20 canonical personas against
active RulePack sequence 7 (`2026.8.11`, payload SHA-256
`3d068aef2dca40f1efb74bdd3f8859e767c000282ab8299ac7f277b0b9719f82`).

**Measured result:** 6/20 matches and 14 unexplained divergences. **G-b remains
RED.** This document classifies the work needed to dispose of each divergence;
it does not retroactively edit the immutable live report, approve a legal
interpretation, change a RulePack, authorize activation, or make ENFORCE ready.
The six matching personas (3, 4, 11, 12, 13 and 14) are enumerated in the
2026-08-12 live report and are out of scope here except as stability witnesses
under the replay contract.

## Notice-dedupe deployment evidence

PR #4195 merged at `2026-08-14T18:20:09Z` as exact merge commit
`35494716abcfdb4bf7e104382cc2fef81ff3b2d7`. GitHub deploy workflow
`31828149383` completed successfully for that same head SHA, and Fly release
`4125` completed at `2026-08-14T18:27:38Z` with image
`registry.fly.io/nuzantara-rag:deployment-01M00RA6VF7H915NWC055DTHPJ`.
The read-only `fly image show --app nuzantara-rag --json` inspection on
2026-08-15 resolved that tag on every listed machine to immutable digest
`sha256:e075926299c082587fab4022f64127e5c3f3c8685e0389708931d3c81b1851fc`;
the same image metadata carries OCI label
`GH_SHA=35494716abcfdb4bf7e104382cc2fef81ff3b2d7`. This binds the deployed
artifact, rather than only its release time, to the merge commit.

This closes the merge/deployment prerequisite only. No fresh active-pack replay
after that deployment is recorded here, so the affected rows remain unexplained
and G-b remains RED.

## Correction to the first-read narrative

The companion Markdown report said most divergences were “expected by
construction” before the active rules had been inspected. That is too broad.
Catalogue differences can explain a changed candidate set only after the new
candidate's predicates, legal basis and product semantics are independently
accepted. The sequence-7 inspection has already refuted that presumption for
personas 7 and 8, and the D12 substitutions in personas 9, 10, 16 and 17 still
need an owner/legal decision. The machine-readable replay remains the canonical
observation; this document narrows the interpretation.

## Status vocabulary

- **BLOCK — defect:** evidence identifies a fail-open rule defect; the row
  cannot be accepted as a catalogue change.
- **CODE FIX DEPLOYED; REPLAY PENDING:** the bounded implementation fix is
  merged and deployed at a pinned revision, but the row stays unexplained until
  a fresh active-pack replay proves the effect.
- **OWNER/LEGAL DECISION:** the engine is behaving deterministically, but the
  repository does not contain authority to decide whether the live behavior or
  the fixture expectation is normative.
- **OWNER PRODUCT DECISION:** a subtype of OWNER/LEGAL DECISION used only where
  the open question is catalogue or product semantics and no legal
  discriminator, guardian handling, bridging behavior or route meaning
  changes. If route meaning is affected, legal approval is also required.
- **SAFE-DIRECTION REVIEW:** the live result abstains more than the fixture.
  This lowers immediate automation risk, but it is not an automatic G-b pass;
  owner/legal must still accept the semantics and user experience.
- **SPLIT:** a row with independently disposable components. Each component
  carries its own status and closes only under its own criteria; the row stays
  unexplained until every component is closed.
- **SUPPORT DIRECTION:** a qualifier marking that the live engine supports a
  candidate the fixture did not. It is never a standalone status or evidence
  of correctness.
- **NEGATIVE CONTROL:** a qualifier requiring a witness that proves the
  deciding fact's absence changes the result. It is never a standalone status.

## Complete 14-row matrix

| Persona | Observed divergence | Proposed status | Evidence and decision required |
|---|---|---|---|
| 1 — Indonesian citizen | Fixture `NO_SUPPORTED_PATH / APPLICANT_IS_INDONESIAN_CITIZEN`; seq-7 `HUMAN_REVIEW_REQUIRED / CITIZENSHIP_LIST_DIVERGENCE`. | **SAFE-DIRECTION REVIEW + OWNER/LEGAL DECISION** | Confirm whether conflicting citizenship-list evidence must outrank the citizen hard filter. If accepted, update the expected state and reason vocabulary explicitly; otherwise add precedence proof that the hard filter wins. |
| 2 — conflicting nationality | Both sides require review, but fixture says `CITIZENSHIP_EVIDENCE_CONFLICT`; seq-7 says `CALLING_VISA_REVIEW` plus `CITIZENSHIP_LIST_DIVERGENCE`. | **OWNER/LEGAL DECISION** | Approve the canonical review reasons and their precedence. A same-state result is not a match when the legal escalation reason changes. |
| 5 — minor, guardian unconfirmed | Both sides require review; seq-7 adds `MINOR_GUARDIAN_PRIVACY_REVIEW`. | **SAFE-DIRECTION REVIEW + OWNER/LEGAL DECISION** | Decide whether the privacy hold is always additive or only applies under a narrower guardian/data condition. Preserve the existing missing-guardian protection. |
| 6 — minor, guardian confirmed | Fixture supports `E31`; seq-7 requires `MINOR_GUARDIAN_PRIVACY_REVIEW`. | **SAFE-DIRECTION REVIEW + OWNER/LEGAL DECISION** | Decide whether a confirmed guardian can ever clear the privacy hold and which affirmative consent/evidence facts are required. Do not remove the hold from a rule-pack edit without an approved privacy interpretation and positive/negative controls. |
| 7 — adult spouse, marriage registered | Fixture supports `E31`; seq-7 supports `C1,E31A,E31B,E31D`. | **BLOCK — DEFECT** | The E31B predicate accepts sponsor status `NONE`, and the E31D family supports on FAMILY intent without the named relationship evidence. The authoritative diagnosis and repair criteria are in `2026-08-15-gold-family-refuter.md`. |
| 8 — adult spouse, marriage unverified | Fixture needs input; seq-7 supports `C1,E31D`. | **BLOCK — DEFECT** | Same E31D fail-open family as persona 7. No explanation may accept this row until approved family facts, a signed successor pack and an independent active-pack replay prove the repair. |
| 9 — investor, direct onshore | Fixture rejects direct onshore conversion; seq-7 supports `D12`. | **OWNER/LEGAL DECISION — SUPPORT DIRECTION** | Decide whether D12 is a legitimate alternative visit route or must be excluded when the requested process is direct onshore conversion. Reconcile `process.application_channel` with `process.wants_onshore_conversion`; prove the chosen signal changes the outcome. |
| 10 — investor, status bridging | Fixture requires `STATUS_BRIDGING_REVIEW`; seq-7 supports `D12`. | **OWNER/LEGAL DECISION — SUPPORT DIRECTION** | Decide whether a visit route may be proposed when the requested workflow is status bridging. Define the authoritative process fact and unknown/null behavior; add a sibling-negative witness. |
| 15 — tourism plus employment | Fixture supports only `E23`; seq-7 needs input because E23 does not cover the entire purpose set. | **SAFE-DIRECTION REVIEW + OWNER PRODUCT DECISION** | Choose whole-intent coverage or partial-candidate semantics for multi-purpose requests. If partial candidates are allowed, specify how unsupported purposes remain visible and non-authoritative. |
| 16 — below investment threshold | Fixture rejects at one rupiah below its E28A minimum; seq-7 supports `D12`. | **OWNER/LEGAL DECISION — NEGATIVE CONTROL, SUPPORT DIRECTION** | Legal approval is required because accepting D12 here changes route meaning. Do not describe this as a threshold bypass until route semantics are settled: D12 may be a different pre-investment visit route. Decide whether that substitution is allowed for an investment-intent request and prove it cannot be presented as investor-status eligibility. |
| 17 — investor at fixture minimum | Fixture supports `E28A`; seq-7 supports `D12`. | **OWNER/LEGAL DECISION — SUPPORT DIRECTION** | Reconcile the fixture's investment-capital model with the active pack's E28A facts and decide whether missing paid-up/role facts should yield input instead of a D12 substitution. Require positive E28A and D12 sibling-negative controls. |
| 18 — obsolete code, incomplete purpose | Both sides need input; seq-7 emits three duplicate `OBSOLETE_PRODUCT_CODE` notices instead of one. | **CODE FIX DEPLOYED; REPLAY PENDING** | PR #4195 is merged and deployed at the pinned revision above and aggregates successor source references into one notice. Keep the row unexplained until a fresh replay proves one notice with the complete reference union. |
| 19 — obsolete code, complete tourism facts | Fixture supports `C1`; seq-7 supports `B1,C1`, and emits three duplicate notices. | **SPLIT: CODE FIX DEPLOYED; REPLAY PENDING + OWNER PRODUCT DECISION** | PR #4195 addresses only notice multiplicity and is deployed at the pinned revision above. A fresh replay must prove that component; separately accept or reject B1 as a legitimate catalogue expansion for this persona and prove eligibility plus a B1 sibling-negative control. |
| 20 — onshore conversion, status unknown | Fixture needs status/overstay input; seq-7 requires review for visit-to-ITK and bridging-to-bridging prohibitions. | **SAFE-DIRECTION REVIEW + OWNER/LEGAL DECISION** | Choose whether unknown current status must first request input or conservatively escalate. Bind the choice to a closed null/unknown policy and prove known-safe, known-prohibited and unknown witnesses. |

## Decision package and replay contract

For any row to move from “unexplained” to “accepted explanation,” its linked
decision must record:

1. the exact persona, active pack identity and observed delta;
2. the accountable owner, plus legal/privacy approval where the row changes a
   legal discriminator, guardian handling, bridging behavior or route meaning;
3. whether the fixture expectation changes or code/RulePack behavior changes,
   with the approved reason and product semantics;
4. at least one positive witness and one sibling-negative or metamorphic
   witness showing that the deciding fact actually controls the result; and
5. the exact code/pack SHA, CI evidence and independent grader identity.

Owner seats remain pending assignment for personas 1, 2, 5, 6, 9, 10, 15,
16, 17, the B1 component of 19, and 20. No decision is valid until the
repository records a named accountable owner, plus legal or privacy approval
where applicable.

The fresh active-pack replay must then:

- regenerate all 20 rows without mutating the 2026-08-12 observation;
- contain zero unexplained divergences and no duplicated obsolete-code notice;
- prove personas 7 and 8 no longer manufacture E31B/E31D from unrelated or
  missing family facts;
- prove the approved D12/onshore and multi-purpose semantics explicitly;
- keep every previously matching outcome stable unless it has its own written
  disposition. Any E31-specific stability exemption must itself name its
  scope, accountable owner and expiry before the replay is graded; and
- be graded by an agent that is neither the author of the code, RulePack or
  fixture changes nor the generator of the replay artifact, and belongs to a
  different model family from both where cross-family grading is required. The
  grading must pin the exact signed payload hash and deployed revision.

## What can close without owner judgment

Only the notice aggregation for persona 18 and the notice portion of persona
19 currently have a bounded code fix. Its exact merge and deployment are now
proven above, but those components close only after a fresh active-pack replay
proves the corrected notice union. Personas 7 and 8 are blocked defects. The
remaining ten rows, plus the B1 component of persona 19, require explicit owner,
legal, privacy or product semantics before an agent may edit expected outcomes
or author the corresponding RulePack behavior.

Until those conditions are met, the operationally correct state is **SHADOW / G-b
RED / ENFORCE NO-GO**.

## Adversarial review

Kimi K3 reviewed the original non-PII draft, before the deployment-evidence
section existed, through the repository's pinned no-tools wrapper and returned
**SHIP-WITH-FIXES**. Both major findings were adopted: the status vocabulary now
defines product, split and directional qualifiers without lowering legal
approval for route meaning, and the replay stability floor no longer silently
exempts E31 outcomes. That bounded second pass returned **SHIP** for the
pre-deployment-evidence revision.

A fresh Kimi K3 delta review on 2026-08-15 covered the deployment-evidence
section, the persona 18/19 status changes and the updated closure statement. It
returned **SHIP-WITH-FIXES**. This revision adopts all four findings by scoping
the older review, binding the Fly artifact with its immutable digest and
`GH_SHA` label, reconciling the persona-19 B1 owner seat and downgrading the
unattributed hash-check claim below. The bounded second pass returned **SHIP**
with no surviving findings.

The canonical pack hash in this file is copied from the cited machine-readable
report. That provenance assertion is not a substitute for the named independent
grader and deployed-revision checks required by the replay contract.
