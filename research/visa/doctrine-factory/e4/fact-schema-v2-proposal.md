---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/2026-08-12-fact-vocabulary-extension-design.md
    note: "the fact-extension v2 input this proposal re-grounds; its own frontmatter says adversarial_review:codex — that review covered the ARCHITECTURE (additive-optional, capability negotiation), never the DOCTRINE (whether the discriminators name the right legal question for the right product)"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "MERGED (PR #4245) — D1/D2/D12/E31B/E31D claim ledger, the only claim_id-backed doctrine that exists today"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "branch agent/air-m5/ops/e2b-batch1, not yet merged (fetched for this task) — covers E33/E33A/E33E/E33F/E33G family+retirement doctrine, A1/B1/C-series, E28A, E30/E30A/E30B; scope stated at its own §Method"
  - path: research/visa/doctrine-factory/claims/e3a-cf1-resolution.md
    note: "D2/D12 extension-count fast-follow, out of scope for this proposal's 8 candidate facts"
  - path: apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py
    note: "canonical 114-code catalog — ground truth for what each of the 11 BLOCKED product codes actually IS, checked line-by-line for the 7 codes the design doc names"
  - path: research/visa/doctrine-factory/reachability/rulepack-prod-007-reachability.md
    note: "the 5 NOT_ASKED facts + 8 zero-rule FactPaths this proposal must dispose of, re-verified live this session (matches exactly)"
  - path: apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts
    note: "live wire mapper, 41 keys measured this session (not 40 — see §Wire-shape correction)"
adversarial_review: kimi-k3
---

# Fact-schema v2 proposal — E4 slice, CP2 input

Prepared for the E4 slice of the Visa Oracle doctrine-factory execution plan. This is a **design
document only** — no code in `apps/` or `backend/` changes in this PR. CP2 (fact-schema approval) is
Zero's gate; this proposal is the material for that decision, not a self-approval.

## 0. Headline finding — the 2026-08-12 design's product identities are wrong

Before evaluating any individual fact, the seed catalog (`seed_visa_types_complete_2026.py`) was checked
against every product code the 2026-08-12 design names. **All seven checked codes are misidentified**:

| Code | 2026-08-12 design assumed | Actual catalog entry (verified this session) |
| --- | --- | --- |
| `E23U` | "Technical service / installation / audit / consultancy" work | **Working Visa Foreign Diplomat House Assistant** |
| `E23V` | "Full-time expatriate employment (RPTKA)" | **Working Visa Kantor Dagang dan Ekonomi** (Trade & Economic Office) |
| `E30E` | University-level study | **Education Visa Special Economic Zone** |
| `E30F` | K-12 / vocational study | **Visa Student Exchange** |
| `E33A` | Top-100-global-university graduate talent | **Second Home Visa Tenaga Ahli Government Invitation** |
| `E33B` | G2G / 90-Day-Agreement academic talent | **Second Home Visa Kolaborasi Special Expertise Golden Visa** |
| `E33C` | Self-sponsored academic talent (GPA discriminator) | **Second Home Visa World Figure Government Invitation** |

None of the six candidate facts in the 2026-08-12 design (`study.institution_level`,
`work.employment_engagement_nature`, `education.university_global_rank`,
`education.institutional_cooperation_duration_status`, `education.academic_gpa_band`,
`sponsor.indonesian_tier`) discriminate a real legal boundary for these products — they discriminate a
boundary the design's regulatory lane invented for products it never actually looked up. This is worse
than the design's own "CRITICAL EPISTEMIC CAVEAT" (generic citations, no pinpoint): the caveat assumed the
right legal *question* was named and only the *authority* was thin. Verified this session: the question is
also wrong. `e2b-batch1-claim-ledger.md` independently confirms the real E33A/E33B/E33C family — its
`CL-E33-…` claims discuss E33A/E33E/E33F/E33G as part of the **Second Home family/retirement general
doctrine card**, not an academic-talent track; no claim in either merged ledger touches E23U/E23V/E30E/E30F
at all.

**Disposition: all six of these candidate facts are recommended DROP for this proposal**, not because the
concept of a discriminator is wrong, but because the discriminator is aimed at a product that does not
exist. Re-authoring correct discriminators for E23U/E23V/E30E/E30F/E33A/E33B/E33C is E3 doctrine-card work
(product identity + primary-source pinpoint), not E4 fact-ontology work, and is out of this proposal's
scope — see §5 open owner decisions.

## 1. What survives: `person.birth_date` / `derived.is_minor` / `family.legal_guardian_accompaniment_status`

The 2026-08-12 design's remaining two proposed facts are **not** tied to a misidentified product — they
target a cross-cutting minor/guardian safety boundary, and the design explicitly declines to name the
affected products ("supplied lane does not name the affected product codes... do not infer them").

- **`person.birth_date`** — the design proposes this as new. It is **not new**: `person.birth_date` already
  exists in the live 44-FactPath vocabulary (reachability report, §Fact-path coverage) and is already
  collected by the interview (`birth_date` question, `tree.ts:262`) and already wired
  (`"person.birth_date": dateFact(facts.birth_date)`, `fact-mapper.ts:456`). It is one of the reachability
  report's **8 zero-rule FactPaths** — collected, wired, referenced by zero rules in the active pack. No
  schema change is needed to collect it; the gap is entirely on the RulePack side (E5), not this proposal.
  `derived.is_minor` is one of the pack's 3 `derived.*` FactPaths (Preambolo: "44 FactPath (41+3)") — also
  pre-existing infrastructure, not a new wire key.
- **`family.legal_guardian_accompaniment_status`** — genuinely new. No claim in either merged/fetched ledger
  backs this fact or the "under-18 cannot independently hold a stay permit without guardian arrangement"
  rule the design cites to UU 6/2011 Art. 31 generically. **Recommendation: DROP from this proposal, but
  flag as a standing E3 doctrine-card item** — its own open question ("which four products does this
  affect?") cannot be answered by E4; it needs an E3 pinpoint hunt across the full 38-product catalog for
  any minor-specific eligibility clause, exactly as `e2b-batch1-claim-ledger.md`'s `CL-E30A-02-GAP` already
  flags one candidate (`review.minor-without-guardian`, itself **not resolved** by that batch — its own
  entry says "the live page text does not actually carry that specific requirement" and defers with a note
  that the requirement "may well be real and sourced").

## 2. Ask-or-drop disposition — the 5 NOT_ASKED facts

Distinct from the 2026-08-12 design's proposed *new* facts, the reachability report names 5 facts the
interview hard-codes to `UNKNOWN(NOT_ASKED)` **today**, unconditionally, regardless of applicant answers
(re-verified live this session against `fact-mapper.ts`, byte-identical to the report):

| FactPath | Ask or drop | Rationale |
| --- | --- | --- |
| `intent.requested_product_code` | **DROP** (permanently, not deferred) | This is a "what product do you want" field on a decision-tree tool whose entire purpose is to tell the applicant which product they should want. Asking it would let a naive applicant's guess anchor the interview, contaminating an eligibility funnel with a self-report the engine must not defer to. No claim needed — this is a UX/architecture call, not a doctrine gap. Zero-rule reference in the active pack (reachability report) is consistent with "correctly never meant to be asked." |
| `commercial.service_fee_budget_idr` | **DROP for E4; revisit under OD-5** | Pricing/quote facts are explicitly out of the fact-ontology's scope per the execution plan's OD-2 (seq-8 pricing fold) and OD-5 (telemetry/DPIA gate) — asking a budget question before a legal eligibility verdict risks anchoring bias and is commercial, not doctrinal. Recommend: stays NOT_ASKED through E4/E5; any future ask is a UX decision for E6, gated the same way QW-4b's copy is gated. |
| `commercial.wants_quote` | **DROP for E4; revisit under OD-5** | Same rationale as above — a UI CTA state, not a legal discriminator. Belongs to E6 experience design if ever built, never to the fact ontology. |
| `immigration.last_entry_date` | **ASK — recommend adding to interview, backend-first per the design's deploy order** | Unlike the three above, this is a genuine legal-adjacency fact: several immigration timing rules (overstay computation, re-entry windows referenced in the E3a CF-1 fast-follow's still-open "re-entry/exit reset of the 180-day ceiling" candidate query) plausibly depend on it. It is currently a zero-rule FactPath in the active pack (no rule references it yet). **Correction after Kimi K3 review**: the safety argument here is NOT the design's `UΔ`/`NΔ` identity proof — that proof covers adding a brand-new fact left `NOT_ASKED` (`NΔ`), not flipping an *existing required* key from `unknownFact(NOT_ASKED)` to a real value, which is a value-shape change on a key already in the wire contract. The correct (and sufficient) safety argument is simpler and already stated: **zero rules in the active pack reference this FactPath today**, so no rule can react to the new value regardless of which lemma applies — the reachability report confirms this directly. This is also, structurally, the same shape of exposure E31B already caught once (a value-blind `op:known` rule would fire silently on any non-null value): before this fact is ever asked live, E5 must confirm no such value-blind rule is authored against it, not merely that none exists today. **Recommend ask, but gate the actual interview-copy addition on E3/E5 producing at least one claim-backed rule that consumes it, and on that rule doing real value-checking rather than a value-blind `known` predicate** — otherwise this is UI surface with no doctrine behind it, which is exactly the failure mode §0 just found for the other six facts. |
| `intent.desired_entry_date` | **ASK, same conditional gating as above** | Same class as `immigration.last_entry_date` — genuinely useful for future-dated rules (e.g. bridging/entry-pattern timing), currently zero-rule. Same corrected safety argument applies: the zero-rule status is what makes this safe today, not the `UΔ`/`NΔ` identity proof, which covers a different case (see left cell). |

Net disposition: **0 of 5 NOT_ASKED facts are asked unconditionally in this proposal.** 3 are permanent or
governance-gated drops (`intent.requested_product_code`, `commercial.service_fee_budget_idr`,
`commercial.wants_quote`); 2 are recommended-ask but explicitly deferred until E5 has a rule that consumes
them, so the interview never grows a question with no doctrinal payload behind it — the same failure mode
found in §0.

**Rule-removal consequence for drops (per task briefing):** none of the three drops here removes an
existing rule — the reachability report confirms all three `commercial.*`/`intent.requested_product_code`
facts are already zero-rule in the active pack (seq-7, 104 rules), so there is nothing for E5 to remove.
This is a genuinely free drop, not a doctrine regression.

## 3. Wire-shape / breaking-change analysis

**Correction to the task briefing's premise**: the wire contract is **41 required dotted-alias keys**, not
40 — recounted directly from `fact-mapper.ts:455-542` this session (41 `"namespace.field":` entries in the
`ApplicantFactsDataWire` object literal), consistent with the Preambolo's "44 FactPath (41+3 derived)" and
the reachability report's "36/44 referenced... 8 referenced by zero rules" (41 applicant-facing + 3
`derived.*` = 44). The visaoracle skill's LIVE STATE line citing "40" (2026-07-27 entry) was itself already
flagged there as measured against an earlier interview revision — this session's count supersedes it.

`ApplicantFactsData` is `extra="forbid"` (Pydantic, backend contract) — **any new required key is a
BREAKING change to the shadow POST**: every existing caller (the live SHADOW-wired interview) would 422 on
the next deploy unless the new field is optional-in-presence. This proposal adds **zero new required
keys**: §1's two survivors are pre-existing FactPaths, §2's two "ask" recommendations stay
`immigration.last_entry_date` / `intent.desired_entry_date` — both **already present as required keys**,
currently always emitted as `unknownFact(NOT_ASKED)`; changing what value they carry when known is not a
schema shape change, it is a semantic-value change on an existing key. **`family.legal_guardian_accompaniment_status`
is dropped in §1**, so it does not enter this analysis; if the standing E3 item eventually resurrects it,
the 2026-08-12 design's versioning strategy (additive-optional-first, fleet-minimum capability fence,
controlled v7 down-conversion, sequence-N-last activation, backend-reader-first / frontend-writer-second /
signed-pack-last deploy order) is the correct mechanism and this proposal adopts it verbatim for that
future case — it does not re-derive a new one.

**Net verdict: this proposal is NOT a breaking change to the wire contract.** No key is added, removed, or
renamed. The only behavioral delta is that 2 of the 5 currently-always-`NOT_ASKED` keys may eventually carry
a real value once the interview asks the question. **Correction after Kimi K3 review**: this is *not* the
`UΔ`/`NΔ` no-op case the 2026-08-12 design's identity proof covers — that proof is about adding NEW
FactPaths under `ΔF` and proving `D(P8, x⊕UΔ) = D(P8, x⊕NΔ) = D(P7, x)`; it says nothing about an EXISTING
required key changing from `NOT_ASKED` to a known value. The correct safety argument for this proposal's
two flips is narrower and already stated in §2's table: **both FactPaths are zero-rule in the active pack
today**, so no rule can consume the new value yet, full stop — no lemma from the versioning design is
needed or correctly applicable here. E5's gate before either flip goes live in the interview must confirm
(a) a rule now exists that consumes the fact, and (b) that rule does real value comparison, not a
value-blind `known` predicate (the exact E31B pattern) — this is a new, narrower check this proposal
introduces, not a citation of the 2026-08-12 design's CI proof.

## 4. `sponsor.type` note (scope boundary, not a proposal)

The 2026-08-12 design explicitly warns: "Do not treat `sponsor.indonesian_tier` as a rename of the existing
`sponsor.type`." Since `sponsor.indonesian_tier` is dropped in §0 (misidentified-product fact), this warning
is now moot for this proposal — `sponsor.type` is untouched, unchanged, and out of scope here. It remains
one of the reachability report's 8 zero-rule FactPaths; whether it should gain a consuming rule is E5/E3
doctrine work, not a fact-ontology decision.

## 5. Open owner decisions (not choices this proposal makes)

1. **Re-authoring E23U/E23V/E30E/E30F/E33A/E33B/E33C discriminators against their REAL product identity** —
   requires a fresh E3 doctrine-card pass (NB-2 query against the actual product names above), not covered
   by any existing claim ledger. Recommendation: route through E3's standard pinpoint-hunt process (OD-4),
   default `BLOCKED_BY_MISSING_DOCTRINE` until claim-backed.
2. **The 4 unidentified minor-affected products** — `family.legal_guardian_accompaniment_status` stays
   dropped from the fact ontology until E3 names them with a pinpoint (§1). `CL-E30A-02-GAP` in
   `e2b-batch1-claim-ledger.md` is the one existing lead and is itself unresolved.
3. **Whether to ask `immigration.last_entry_date` / `intent.desired_entry_date` in the interview UI** before
   or after E5 ships a consuming rule — this proposal recommends after (§2), to avoid UI-with-no-doctrine,
   but the ordering is a judgment call Zero may want to override for UX reasons (e.g. collecting the data
   early for future use without gating on a specific PR).

## Adversarial review

Kimi K3 refutation, narrow scope (facts without claim backing, wire-contract impacts missed, HUMAN_CONTEXT
reclassifications reintroducing the E31B fail-open), 2026-08-17, run against the full 5-doc pack at once.

| Finding | Verdict | Disposition |
| --- | --- | --- |
| §3's wire-safety argument invoked the 2026-08-12 design's `UΔ`/`NΔ` identity proof for the `NOT_ASKED→KNOWN` value flip on `immigration.last_entry_date`/`intent.desired_entry_date` — wrong lemma: that proof covers adding a brand-new FactPath, not an existing key's value changing. | REFUTED (real defect, non-fatal) | **Cured** — §2 table and §3 rewritten to ground safety in the zero-rule status directly (no rule references either FactPath today, so no rule can react regardless of lemma), and to add an explicit E5 gate requiring the future consuming rule to do real value comparison, not a value-blind `known` predicate (the E31B pattern). |
| `family.legal_guardian_accompaniment_status` honestly dropped with no claim_id fabricated to support it; `person.birth_date`/`derived.is_minor` correctly identified as pre-existing, not new. | SOSTENUTO | No change. |
| The 3 permanent/gated NOT_ASKED drops are all zero-rule in the active pack — no rule removal consequence. | SOSTENUTO | No change. |
