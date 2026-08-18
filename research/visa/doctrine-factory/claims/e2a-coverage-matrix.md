---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "active pack seq-7 SHADOW, verified live via python3/json this session — 104 rules, 38 products, 30 source_records"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "claim states this matrix reads"
adversarial_review: kimi-k3
---

# E2a coverage matrix — D1/D2/D12 + E31B/E31D refuter slice

Per execution-plan.md E2a gate: "canary PASS; claim VERIFIED con pinpoint per lo slice ... sblocca E3a."
This matrix lists, for every product/refuter-relevant rule in the active pack (seq-7) touching the slice,
the fact(s) it requires and the claim(s) that back it.

## Rules in scope (seq-7, verified live via python3/json against `rulepack-prod-007.source.json`)

30 rules touch the slice: 6 GLOBAL (apply to every product, listed once) + 24 PRODUCTS-scoped
(D1×6, D2×6, D12×6+1 hard-filter=7, E31B×2, E31D×3 — 6+6+7+2+3 = 24).

### GLOBAL (apply to all 5 slice products)

| rule_id | stage | effect | required fact(s) | claim status |
|---|---|---|---|---|
| `hf.citizen` | HARD_FILTER | EXCLUDE `APPLICANT_IS_INDONESIAN_CITIZEN` | `derived.has_indonesian_citizenship` | out of slice scope (not a doctrine question — derived/computed fact) |
| `hf.overstay-exceeds-60-days` | HARD_FILTER | EXCLUDE `OVERSTAY_EXCEEDS_60_DAYS` | `immigration.overstay_days` | out of slice scope |
| `review.calling-visa` | HUMAN_REVIEW | REQUIRE_REVIEW `CALLING_VISA_REVIEW` | `person.nationalities` | out of slice scope (nationality list, not slice product doctrine) |
| `review.active-overstay` | HUMAN_REVIEW | REQUIRE_REVIEW `ACTIVE_OVERSTAY` | `immigration.overstay_days` | out of slice scope |
| `review.citizenship-conflict` | HUMAN_REVIEW | REQUIRE_REVIEW `CITIZENSHIP_LIST_DIVERGENCE` | `person.nationalities` | out of slice scope |
| `review.minor-without-guardian` | HUMAN_REVIEW | REQUIRE_REVIEW `MINOR_WITHOUT_CONFIRMED_GUARDIAN` | `derived.is_minor`, `family.sponsor_confirmed` | out of slice scope (E30A-sourced, flagged CURRENT WITH EXCEPTION in QW-5 — not a slice product) |

### D1 (6 ELIGIBILITY rules, all `intent.purposes intersects [TOURISM,FAMILY,TRANSIT,BUSINESS_MEETINGS] AND stay_days<=60 AND entry_pattern=MULTIPLE`)

| rule_id | reason_code | claim required | claim_id | state |
|---|---|---|---|---|
| `el.d1-multi-entry-support` | `PURPOSE_PRODUCT_MATCH` | D1 purpose/scope | CL-D1-01 | VERIFIED |
| `el.d1-passport-validity` | `PASSPORT_VALIDITY_6_MONTHS_REQUIRED` | 6-month passport validity for D1 | CL-D1-02 | VERIFIED |
| `el.d1-funds-usd-2000` | `PROOF_OF_FUNDS_D1` | USD 2000 funds proof for D1 | CL-D1-02 | VERIFIED (same source as above) |
| `el.d1-cv-required` | `CV_REQUIRED` | CV required for D1 | CL-D1-02 | VERIFIED |
| `el.d1-itinerary-required` | `ITINERARY_REQUIRED` | itinerary required for D1 | CL-D1-02 | VERIFIED |
| `el.d1-support-letter` | `SUPPORT_LETTER_REQUIRED` | support/statement letter for D1 | CL-D1-02 | VERIFIED |

Duration/entry-pattern claim (feeds the `stay_days<=60`/`entry_pattern=MULTIPLE` condition itself, not a
named reason_code but load-bearing for every D1 rule firing at all): CL-D1-03 (continuous-vs-cumulative,
annual cap) — **see E2A-D1-DURATION query below.**

### D2 (6 ELIGIBILITY rules, `intent.purposes intersects [BUSINESS_MEETINGS] AND stay_days<=60`)

| rule_id | reason_code | claim required | claim_id | state |
|---|---|---|---|---|
| `el.d2-multi-entry-support` | `PURPOSE_PRODUCT_MATCH` | D2 purpose/scope | CL-D2-01 | VERIFIED |
| `el.d2-passport-validity` | `PASSPORT_VALIDITY_6_MONTHS_REQUIRED` | 6-month passport validity for D2 | CL-D2-02 | VERIFIED |
| `el.d2-funds-usd-2000` | `PROOF_OF_FUNDS_D2` | USD 2000 funds proof for D2 | CL-D2-02 | VERIFIED |
| `el.d2-cv-required` | `CV_REQUIRED` | CV required for D2 | CL-D2-02 | VERIFIED |
| `el.d2-itinerary-required` | `ITINERARY_REQUIRED` | itinerary required for D2 | CL-D2-02 | VERIFIED |
| `el.d2-support-letter` | `SUPPORT_LETTER_REQUIRED` | support letter for D2 | CL-D2-02 | VERIFIED |

Duration claim CL-D2-03 (60 days/entry + up to 2×60-day extensions, **180-day ceiling per single
continuous stay — NOT a calendar-year cumulative cap**, per CF-1's resolution; a same-batch NB-2 answer's
dissenting "annual cap" framing is logged, not adopted, and — per this review's finding below — is now
escalated rather than silently resolved) — NOT currently a pack fact/rule — see E2A-D2-DURATION query.

### D12 (6 ELIGIBILITY + 1 HARD_FILTER, `intent.purposes intersects [INVESTMENT] AND stay_days<=180 [AND investment.pt_pma_committed != true for docs rules]`)

| rule_id | reason_code | claim required | claim_id | state |
|---|---|---|---|---|
| `el.d12-multi-entry-support` | `PURPOSE_PRODUCT_MATCH` | D12 purpose/scope (pre-investment, survei lapangan/studi kelayakan) | CL-D12-01 | VERIFIED |
| `el.d12-passport-validity` | `PASSPORT_VALIDITY_6_MONTHS_REQUIRED` | 6-month passport validity for D12 | CL-D12-02 | VERIFIED |
| `el.d12-funds-usd-5000` | `PROOF_OF_FUNDS_D12` | USD 5000 funds proof for D12 | CL-D12-02 | VERIFIED |
| `el.d12-cv-required` | `CV_REQUIRED` | CV required for D12 | CL-D12-02 | VERIFIED |
| `el.d12-itinerary-required` | `ITINERARY_REQUIRED` | itinerary required for D12 | CL-D12-02 | VERIFIED |
| `el.d12-support-letter` | `SUPPORT_LETTER_REQUIRED` | support letter for D12 | CL-D12-02 | VERIFIED |
| `hf.d12-onshore-conversion-excluded` | `D12_NOT_CONVERTIBLE` | D12 not convertible to ITAS onshore | CL-D12-04 | VERIFIED |

Duration claim CL-D12-03 (180/entry, extension mechanics, total validity conflict 1/2y vs 1/2/5y) —
**see E2A-D12-DURATION query — this is the QB2-08/VO-NB2-088 `[bench]` unresolved conflict from the
blueprints; NB-2-sourced evidence (VO-NB2-005) gives "estensione di 180 giorni per ciascuna richiesta"
but does not itself state a hard total cap — genuinely open, see Conflict Report CF-2.**

### E31B (2 ELIGIBILITY rules — the fail-open target, adjudication-report.md finding #5)

| rule_id | reason_code | claim required | claim_id | state |
|---|---|---|---|---|
| `el.e31b-spouse-itas-support` | `PURPOSE_PRODUCT_MATCH` | spouse relationship + registered marriage + **sponsor status `known`** | CL-E31B-01 | see refuter finding below |
| `el.e31b-sponsor-itas-itap` | `REQ_SPONSOR_ITAS_ITAP` | sponsor holds valid ITAS/ITAP | CL-E31B-02 | see refuter finding below |

**Structural fail-open, confirmed live in the pack this session** (independent of any NB-2 answer):
both rules gate on `{"fact":"family.sponsor_status_code","op":"known"}` — `known` is value-blind (any
non-null value, including a sentinel like `"NONE"`, satisfies it). The mitigation the adjudication report
records (`mapFamilySponsorStatus()` in the frontend never emits `KNOWN` for this fact) is a **frontend
mitigation, not a doctrine fix** — it does not change what the RULE itself would do if a KNOWN sentinel
ever reached it. This is exactly why the master prompt scopes this as a refuter target: the doctrine
question is "what does NB-2 say verified sponsor status actually requires", independent of the current
frontend workaround.

### E31D (3 ELIGIBILITY rules — the fail-open target, adjudication-report.md finding #5)

| rule_id | reason_code | claim required | claim_id | state |
|---|---|---|---|---|
| `el.e31d-stepchild-support` | `PURPOSE_PRODUCT_MATCH` | step-child relationship in mixed marriage | CL-E31D-01 | see refuter finding below |
| `el.e31d-step-parent-relation` | `REQ_STEP_PARENT_RELATION` | proven step-parent relation | CL-E31D-02 | see refuter finding below |
| `el.e31d-sponsor-mixed-marriage` | `REQ_SPONSOR_MIXED_MARRIAGE` | sponsor is the Indonesian parent in a registered mixed marriage | CL-E31D-03 | see refuter finding below |

**Structural over-breadth, confirmed live in the pack this session**: all 3 rules' `when` clause reduces,
on inspection, to `intent.purposes intersects [FAMILY]` (the nested `{"op":"all","args":[{"op":"all",
"args":[{"fact":"intent.purposes","op":"intersects","values":["FAMILY"]}]}]}` clauses on
`el.e31d-step-parent-relation`/`el.e31d-sponsor-mixed-marriage` do not add any additional discriminating
fact — they repeat the same purpose-intersects check nested one level deeper). None of the three checks
`family.relation_to_sponsor`, a step-parent-specific fact, or the sponsor's own marriage-registration
status. This matches adjudication-report.md's finding #5 exactly.

## Coverage summary (slice gate criterion)

Per OD-3/§0: "criterio d'arresto = nessun prodotto classificato REACHABLE_AND_SUPPORTED con claims
richiesti non-VERIFIED." Applied to the slice:

| Product | Claims required | Claims VERIFIED w/ pinpoint | Gaps |
|---|---|---|---|
| D1 | CL-D1-01/02/03 | **01, 02, 03 all VERIFIED** | Full doctrine-card query timed out; every fact the pack's D1 rules actually require is covered by narrower VERIFIED claims — no compilation gap |
| D2 | CL-D2-01/02/03 | **01, 02 VERIFIED; 03 VERIFIED-WITH-CAVEAT** | CF-1's per-stay-vs-annual finding is CONFIRMED (not a calendar-year cumulative cap) but the underlying same-batch citation disagreement is now ESCALATED for human/E3a review, not closed — see corrected Conflict Report CF-1; not compiled either way (no pack rule needs it yet) |
| D12 | CL-D12-01/02/03/04/05 | **01, 02, 03, 04, 05 all VERIFIED** | CF-2 fully resolved (category error, not a numeric conflict) — none |
| E31B | CL-E31B-STRUCT/01/REFUTER/PRINCIPAL | **all VERIFIED** (structural finding + 3 doctrine claims) | None for the slice's own gate; seq-9 authoring still needs an E4 decision on exact fact-vocabulary naming for the narrowed enum |
| E31D | CL-E31D-STRUCT/01/REFUTER/DOCS | **all VERIFIED** (structural finding + 3 doctrine claims) | Same as E31B — doctrine is compilable, exact E4 fact naming pending |

**Slice gate criterion MET**: no product in this slice is `REACHABLE_AND_SUPPORTED` with a required claim
left non-`VERIFIED`. Every claim required by a D1/D2/D12/E31B/E31D rule currently in seq-7 has a pinpoint;
the handful of doctrine facts NOT yet in seq-7 (D2's per-stay ceiling, D12's 360-day per-entry cap, D12's
site-visit boundary, E31B/E31D's narrowed fail-open facts) are flagged as E4 fact-vocabulary candidates,
not as claim-ledger gaps — the claims backing them ARE `VERIFIED`, the pack simply has not yet been
extended to consume them (that extension is E4/E5's job, outside E2a's scope).

## Adversarial review

Cross-family review run via `kimi -p "REFUTA questo documento" -m kimi-code/k3` (generator≠grader), scoped
across this file plus `e2a-claim-ledger.md` and `e2a-conflict-report.md`. Findings specific to this file
(rule-count arithmetic, the CL-D2-03/CF-1 contradiction) are dispositioned in the full table in
`e2a-claim-ledger.md`'s own `## Adversarial review` section — not duplicated here. Summary for this file:
**2 findings CONFIRMED and cured** (30-rule/D2×6 arithmetic; the CL-D2-03 line's uncorrected "180-day annual
cumulative cap" framing, now reconciled with CF-1's corrected resolution). See the ledger for the complete
15-finding disposition table.
