---
date: 2026-08-18
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "BRIDGING T1 originally logged TOTAL GAP; cross-cutting claims CL-CROSS-01/02/05/06/07/08 and CL-XCUT-T8-01"
  - path: research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md
    note: "CL-BRIDGING-01/02 (T1 closure, batch-2b EXTENSION) and CL-XCUT-T8-01 (T8 blackout windows) provenance"
  - path: research/visa/doctrine-factory/query-bank/coverage-matrix-after-batch3.json
    note: "BRIDGING's required_claim_topics (T1,T10,T15,T3,T7,T8,T9) — note T5 NOT required — ALL_TOPICS_ANSWERED"
  - path: research/visa/doctrine-factory/source-hierarchy-draft.md
    note: "authority-level vocabulary (L1-L7), state vocabulary"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "active pack seq-7 (SHADOW) — the 8 hf./el./review.bridging.* rules this card's coverage matrix targets"
adversarial_review: kimi-k3
---

# Product Doctrine Card — BRIDGING (Transitional Stay Permit)

Task: E3 bulk (Visa Oracle doctrine-factory execution plan), VISIT/ENTRY family. Input: the merged
e2b-batch1 (which logged BRIDGING's T1 as a TOTAL GAP) and e2b-batch2/2b (which closed it) claim
ledgers. Format follows `cards/D1.md`'s PDC-1 field set. No legal fact without a `claim_id` pointer; a
PDC-1 field with no claim behind it is marked **GAP**, not silently filled.

## 1. Identity

- **Code**: BRIDGING
- **Name**: Bridging Visa — Transitional Stay Permit (*Izin Tinggal Peralihan*, legally "Visitor Stay
  Permit in the framework of Transition of Immigration Stay Permit")
- **Category**: OTHER — not a visit or KITAS/KITAP category in its own right; a procedural bridge
  preventing overstay while an onshore stay-permit transition (VITAS/ITAS/ITAP) is processed. Not in
  the public catalog (`public_catalog: false` in the pack — an internal/procedural product, unlike the
  5 other cards in this slice, which are all `public_catalog: true`).

## 2. `claims_digest`

Recipe: identical to A1/B1/etc. — sort `(claim_id, state)` pairs ascending by `claim_id`, join
`claim_id=state` newline-separated, sha256 the UTF-8 bytes.

```
claims_digest: 4375d4fd632f3c46f643eec9b5c4c5d4fc400362f2d78768437c96448bc68e09
```

## 3. Doctrinal facts (PDC-1 fields, each claim-referenced)

1. **Category & legal purpose.** BRIDGING is legally the "Visitor Stay Permit in the framework of
   Transition of Immigration Stay Permit" — a procedural bridge preventing overstay while a new onshore
   stay-permit application (VITAS/ITAS/ITAP transition) is processed, not a stay-permit category in its
   own right. — `CL-BRIDGING-01`, **VERIFIED-WITH-CAVEAT** (citation-audit `PROSE_ONLY` — no structured
   citation pointers, though the answer names `Permenkumham No. 11/2024` and `Permenkumham_27_2021_
   Visa.pdf` by passage).
2. **Permitted activities.** Permitted activities are limited to "certain activities" (*kegiatan
   tertentu*) whose specific definition the primary regulation DELEGATES to the Director General of
   Immigration, not the statute itself — the activity boundary is not self-executing from
   `Permenkumham 11/2024` alone. — `CL-BRIDGING-02`, **VERIFIED-WITH-CAVEAT** (same `PROSE_ONLY`
   citation class).
3. **Prohibited activities.** Local labor, commercial sales, and compensation from an Indonesian party
   are prohibited by the GENERAL cross-cutting rule (matching batch-1's T3-series findings), not a
   BRIDGING-specific carve-out — `CL-BRIDGING-02` explicitly states this is the general rule applying,
   not a dedicated BRIDGING prohibition claim. Reinforced by `CL-CROSS-01`/`CL-CROSS-02` (Products:
   ALL), both **VERIFIED**. The pack's own structured `prohibited_activities` for BRIDGING —
   `employment_relationship`, `exit_terminates_permit` — is a pack-structural fact, consistent with
   these claims but not itself independently claim-verified.
4. **Borderline/unresolved activities.** **GAP** — no BRIDGING-specific borderline-activity claim
   exists.
5. **Single or multiple entry.** Not applicable — BRIDGING's own pack `entry_policy.entry_count` is
   `NOT_APPLICABLE` (an onshore procedural bridge, not an entry visa). BRIDGING's required_claim_topics
   (per the coverage matrix) explicitly EXCLUDE T5 (entry pattern) — the only one of this slice's 6
   products where T5 is not required — consistent with entry-pattern being inapplicable to a purely
   onshore transitional permit. No claim needed or sought.
6. **Duration per entry & total validity.** 60 days maximum (pack `stay_policy.maximum_days=60`,
   `minimum_days: null`), no extension (`extension_policy.allowed=false`). CL-BRIDGING-02's own note
   states the batch-2b answer "did not fully cover points 3-5 (entry/duration, extension/conversion,
   sponsor)" — so this specific 60-day figure is a **pack-structural fact, not doctrinally
   claim-verified in prose**. **GAP** flagged explicitly, not silently inferred from the pack alone.
7. **Extensions & conversions.** No extension (per §6). The onward stay-permit transition BRIDGING is a
   bridge TOWARD (VITAS/ITAS/ITAP) is exactly its own purpose (§3.1) — but the specific transition
   mechanics/timing are **GAP** per CL-BRIDGING-02's own acknowledged incompleteness.
8. **Filing location (onshore/offshore) & onshore-status prerequisites.** Onshore-only — the pack's own
   `hf.bridging.offshore` rule EXCLUDES any applicant with `immigration.currently_in_indonesia=false`
   (reason code `BRIDGING_ONSHORE_ONLY`). This is a pack-structural rule fact; no dedicated ledger claim
   states the onshore prerequisite in doctrinal prose, though it is directly consistent with §3.1's
   "onshore transitional" category claim. **GAP** for a dedicated prose-level claim.
9. **Nationality restrictions incl. calling-visa applicability.** **GAP** — out of this slice's claim
   scope entirely; BRIDGING has no nationality-gating rule in seq-7 and the GLOBAL calling-visa rule
   carries no BRIDGING-specific claim, same as every other card in this slice.
10. **Age limits.** Not applicable — no BRIDGING age-eligibility rule in seq-7.
11. **Sponsor/guarantor requirements.** No `sponsor_types` recorded for BRIDGING beyond `NONE` in the
    pack's own product record. — `CL-CROSS-05`, **VERIFIED** (Products: ALL), though CL-BRIDGING-02's
    own note flags sponsor-specificity as one of the points its source answer did NOT fully cover
    (§6/§7 note) — carried here as an honest partial-coverage caveat, not silently dropped.
12. **Financial requirements & proof.** **GAP** — no BRIDGING-specific financial-proof claim or pack
    rule; BRIDGING's own 4 ELIGIBILITY rules (below) gate on immigration-status facts, not funds.
13. **Permitted source of income/compensation.** Same cross-cutting compensation-source test as
    A1/B1/C1/C2/C6. — `CL-CROSS-01`, **VERIFIED** (Products: ALL) + `CL-CROSS-02`, **VERIFIED**
    (Products: ALL).
14. **Family/dependent provisions.** Not applicable to BRIDGING as a procedural-bridge product.
    `CL-CROSS-08` (**VERIFIED**, Products: "ALL family-line products") does not literally name
    BRIDGING — same documentation-completeness gap flagged across this slice's other cards.
15. **Investment requirements.** Not applicable.
16. **Mandatory documents.** **GAP** — no document-bundle claim; the pack's own 4 ELIGIBILITY rules
    require applicant-supplied facts (current status code, current status expiry, requested product
    code, purposes), not a document list per se.
17. **Declarative vs. documentary-proof requirements.** **GAP** — no claim classifies this.

## 4. Full-card query note

BRIDGING's widest "full doctrine card" query (`VO-FUSED-T1-003`) timed out TWICE in batch-1 — logged
honestly as `CL-BRIDGING-GAP-01` (`UNVERIFIED`, "no claims can be authored ... this is a genuine
coverage hole, not a downgraded claim") in `e2b-batch1-claim-ledger.md`. The batch-2b EXTENSION's own
narrower `E2B2-T1-BRIDGING` query then closed the T1 topic with `CL-BRIDGING-01`/`02` — but that
answer's own note explicitly states it did NOT fully cover entry/duration, extension/conversion, or
sponsor specifics (§3.6/§3.7/§3.11 above). **This card treats `CL-BRIDGING-GAP-01`'s original TOTAL-GAP
finding as superseded, not silently forgotten** — the gap was real, then partially (not fully) closed;
the residual thin spots are named explicitly in §3, matching this task's binding honesty rule.

## 5. Open conflicts

None specific to BRIDGING from the original E3 batch. **New, 2026-08-24 (owner ruling, D12/F4
investigation lane — see `research/visa/doctrine-factory/e5/inc8-pack-edits/`):** Zero drew BRIDGING's
scope precisely, verbatim, in response to a question about whether a renewal-in-process KITAS holder
could be a BRIDGING candidate —

> **"ASSOLUTAMENTE NO. BRIDGING VISA FA DA PONTE TRA UN KITAS E UN ALTRO, TRA VISA KUNJUNGAN E UN
> KITAS. MAI TRA UN KITAS E IL KITAS CON STESSO SPONSOR O TRA UN KITAS E UN VISA KUNJUNGAN"**

Four boundaries, precise:

| transition | BRIDGING? |
|---|---|
| KITAS → a DIFFERENT KITAS | valid |
| visa kunjungan → KITAS | valid |
| KITAS → the SAME KITAS, same sponsor (a renewal) | never |
| KITAS → visa kunjungan (a downgrade) | never |

**This directly contradicts §3.1/§6's own prior reasoning**, which is now the record's own citation
trail catching itself: `hf.bridging.from-visit-itk`'s row above was already marked SUPPORTED-but-
**thin** — "a visit-visa-origin applicant cannot bridge — consistent with §3.1's 'bridge between
VITAS/ITAS/ITAP transitions,' not visit-visa transitions; no dedicated claim states this exclusion
explicitly." Zero's ruling says the OPPOSITE: visa kunjungan → KITAS IS a valid bridge. The doctrine
author's own "thin" flag was the right instinct — the assumption it flagged as unconfirmed is the one
that turned out wrong.

Read-only rule-audit findings against this ruling (reported to team-lead 2026-08-24, not fixed here —
different product, different lane; routing to Zero is team-lead's call):
1. **`hf.bridging.from-visit-itk`'s live `when` clause** (`rulepack-prod-013.source.json`) EXCLUDES
   `immigration.current_status_code ∈ {A1, C1, C2, C6, ITK_FROM_BVK, ITK_FROM_VISIT_C,
   ITK_FROM_VISIT_D}` — A1/C1/C2/C6 are the raw visa-kunjungan/short-stay codes, so this filter, as
   coded, blocks the exact "visa kunjungan → KITAS" path Zero just confirmed is valid. Concrete
   applicant: a tourist currently on a C1 visit visa requesting BRIDGING to convert to a KITAS is
   HARD-EXCLUDED today, reason `BRIDGING_FROM_VISIT_ITK_PROHIBITED`.
2. **No fact anywhere expresses sponsor identity** (current permit's sponsor vs. the intended one) —
   checked the full 45-fact vocabulary; the 8 `sponsor`-named facts (`sponsor.type`,
   `family.sponsor_*`, `work.indonesian_work_sponsor_confirmed`, `study.sponsor_confirmed`) each
   describe A sponsor for THIS application, none compares two. Boundary "same-sponsor renewal never
   bridges" cannot be tested by any existing rule — not currently violated in a provable sense, but
   structurally unguarded.
3. **No fact records the bridge's intended destination status** either — `el.bridging.destination-
   stated`'s `when` clause (reason code `BRIDGING_DESTINATION_STATED`) tests only `purposes intersects
   OTHER` + `requested_product_code != BRIDGING`, the same shape as the other 3 advisory SUPPORT rules
   — it does not verify any destination was actually stated. So "KITAS → visa kunjungan (downgrade)"
   is equally unguarded: nothing distinguishes a legitimate KITAS→different-KITAS bridge from an
   illegitimate downgrade attempt once `hf.bridging.from-visit-itk`/`hf.bridging.to-bridging` are
   passed.

None of this is fixed by this card update — it is the domain fact plus the audit trail, so the next
reader does not re-derive the same doctrinally-flagged-but-unconfirmed assumption from the vague
"Visitor Stay Permit in the framework of Transition of Immigration Stay Permit" phrasing in §1.

## 6. Rule coverage matrix (seq-7, verified live against `rulepack-prod-007.source.json`)

BRIDGING has 8 rules: 3 HARD_FILTER, 4 ELIGIBILITY, 1 HUMAN_REVIEW.

| rule_id | stage | reason_code | required claim(s) | claim state | rule status |
|---|---|---|---|---|---|
| `hf.bridging.offshore` | HARD_FILTER | `BRIDGING_ONSHORE_ONLY` | `CL-BRIDGING-01` (category consistency) | VERIFIED-WITH-CAVEAT | SUPPORTED (§3.8, pack-structural, consistent with claim but not itself prose-verified) |
| `hf.bridging.from-visit-itk` | HARD_FILTER | `BRIDGING_FROM_VISIT_ITK_PROHIBITED` | `CL-BRIDGING-01` | VERIFIED-WITH-CAVEAT | SUPPORTED (a visit-visa-origin applicant cannot bridge — consistent with §3.1's "bridge between VITAS/ITAS/ITAP transitions," not visit-visa transitions; no dedicated claim states this exclusion explicitly — thin) |
| `hf.bridging.to-bridging` | HARD_FILTER | `BRIDGING_TO_BRIDGING_PROHIBITED` | none | — | **UNBACKED** — no claim in either ledger addresses BRIDGING-to-BRIDGING chaining; a genuine, undocumented rule-backing gap (see §8 item 1) |
| `el.bridging.t3-window-manual` | ELIGIBILITY | `BRIDGING_T3_WINDOW_ADVISOR_CHECK` | `CL-BRIDGING-02` (activities-delegated-to-DGI framing) | VERIFIED-WITH-CAVEAT | SUPPORTED (thin — CL-BRIDGING-02 does not itself name the specific T3-window filing mechanic) |
| `el.bridging.overstay-shield-payment` | ELIGIBILITY | `BRIDGING_OVERSTAY_SHIELD_PAYMENT_CHECK` | `CL-BRIDGING-01` (overstay-prevention purpose) | VERIFIED-WITH-CAVEAT | SUPPORTED (consistent with §3.1's core purpose claim, no dedicated payment-mechanics claim) |
| `el.bridging.source-status-verify` | ELIGIBILITY | `BRIDGING_SOURCE_STATUS_VERIFY` | `CL-BRIDGING-01` | VERIFIED-WITH-CAVEAT | SUPPORTED (same basis) |
| `el.bridging.destination-stated` | ELIGIBILITY | `BRIDGING_DESTINATION_STATED` | `CL-BRIDGING-01` | VERIFIED-WITH-CAVEAT | SUPPORTED (same basis) |
| `review.bridging.adverse-history` | HUMAN_REVIEW | `BRIDGING_ADVERSE_HISTORY` | none | — | **UNBACKED** — no ledger claim addresses adverse-history review for BRIDGING specifically; the GLOBAL enforcement-posture claim `CL-CROSS-07` (**VERIFIED**, substance-over-form standard) is topically adjacent but does not name this rule's specific overstay/deportation/blacklist trigger set |

T3/T7/T9/T10/T15 topic-level backing (required per coverage matrix, not tied to a single named rule
above): `CL-CROSS-01`/`CL-CROSS-02` (T3, **VERIFIED**), `CL-CROSS-05` (T7, **VERIFIED**), `CL-CROSS-06`
(T9, **UNVERIFIED**-with-caveat, same as A1/B1 — though BRIDGING has no nationality-gating rule itself,
so this topic's applicability is weaker than for A1/B1), `CL-CROSS-08` (T10, **VERIFIED**, same
Products-scoping gap flagged in §3.14 — this row was missing from an earlier draft even though
`CL-CROSS-08` is present in the digest and discussed in §3.14; added for traceability), `CL-CROSS-07`
(T15, **VERIFIED**). T8 (blackout windows) is backed by `CL-XCUT-T8-01`, **VERIFIED-WITH-CAVEAT** — the
claim's own text notes it is "grounded but does not deliver a crisp per-product blackout-window table,"
an honest thinness carried forward here, not smoothed over.

**Standard applied for SUPPORTED vs UNBACKED in the table above** (made explicit after the real Kimi K3
pass flagged the two categories as applied inconsistently — see Adversarial review below): a rule is
marked **SUPPORTED (thin)** when its fact domain is directly addressed by a claim's own core content
even though no claim names the rule's specific `reason_code` (e.g. `hf.bridging.offshore`/
`hf.bridging.from-visit-itk`/the 4 ELIGIBILITY rules all sit squarely within `CL-BRIDGING-01`'s own
"onshore transitional bridge between VITAS/ITAS/ITAP" category claim). A rule is marked **UNBACKED**
when its fact domain is not addressed by ANY claim at all, even loosely — `hf.bridging.to-bridging`
(anti-chaining) and `review.bridging.adverse-history` (violation-history triggers) are each about a
topic no claim in either ledger discusses, not merely under-detailed.

**Rules WITHOUT backing in this ledger**: `hf.bridging.to-bridging` and `review.bridging.adverse-history`
— 2 of 8 rules have **no** claim addressing their specific decision logic (both are pack-structural facts
only), per the standard above. Both are safety-conservative EXCLUDE/REQUIRE_REVIEW rules whose
`on_unknown` is `HUMAN_REVIEW` (fail-closed), so their absence of doctrinal backing does not create an
under-restrictive gap — but it is a genuine, named documentation gap the next batch should close (see
§8).

## 7. Disposition

**REACHABLE_AND_SUPPORTED-candidate, with 2 unbacked rules named explicitly.** BRIDGING's T1 topic is
closed (`CL-BRIDGING-01`/`02`, VERIFIED-WITH-CAVEAT) and matches the batch-3 closure verdict
(`coverage-matrix-after-batch3.json` row "BRIDGING — MET — T1 VERIFIED-WITH-CAVEAT, batch-2b"). Unlike
D1/A1/B1, this card surfaces 2 of BRIDGING's own 8 rules (`hf.bridging.to-bridging`,
`review.bridging.adverse-history`) that have **zero** claim backing at all — not merely a documentation-
completeness GAP on an unconsumed PDC-1 field, but an actual rule-level gap on rules the pack DOES
execute today. Per the OD-3 arrest criterion's own wording ("required claims VERIFIED"), these 2 rules'
`required_facts` are applicant-supplied booleans/enums with conservative fail-closed `on_unknown`
behavior, so the criterion is not violated in a safety sense — but this is flagged, not silently
absorbed into the MET verdict, matching the batch-3 ledger's own practice of naming residue explicitly
(e.g. its E30/E30B `RESEARCH_GAP_CANDIDATE` treatment) rather than sweeping it.

`claims_digest` pairs (sorted, `claim_id=state`):

```
CL-BRIDGING-01=VERIFIED-WITH-CAVEAT
CL-BRIDGING-02=VERIFIED-WITH-CAVEAT
CL-CROSS-01=VERIFIED
CL-CROSS-02=VERIFIED
CL-CROSS-05=VERIFIED
CL-CROSS-06=UNVERIFIED
CL-CROSS-07=VERIFIED
CL-CROSS-08=VERIFIED
CL-XCUT-T8-01=VERIFIED-WITH-CAVEAT
```

## 8. Claim gaps discovered (input for next E2 batch — not queried in this task per brief)

1. `hf.bridging.to-bridging` (BRIDGING-to-BRIDGING chaining prohibition) — zero claim backing, found by
   this card's own rule-by-rule walk (§6), not by any prior batch.
2. `review.bridging.adverse-history`'s specific overstay/deportation/blacklist/investigation trigger
   set — zero claim backing, same finding method.
3. A narrower follow-up query on BRIDGING's duration/extension/sponsor specifics, exactly as
   `CL-BRIDGING-02`'s own note already recommended — restated here as still open.
4. BRIDGING's onshore-prerequisite (`hf.bridging.offshore`) and visit-visa-origin exclusion
   (`hf.bridging.from-visit-itk`) in dedicated doctrinal prose, beyond the pack-structural fact.

## Adversarial review

**Real run** (not simulated): `kimi -p "<full 6-card combined text + refutation instructions>" -m
kimi-code/k3`, one invocation across all 6 cards in this slice. Ran past the 8-minute timebox producing
a substantial partial transcript, killed per this task's own documented precedent — see A1.md's
Adversarial Review section for the full method note. Raw transcript:
`/tmp/e3refs/kimi-review-output.txt` (session-local). Findings below are the ones concretely affecting
BRIDGING, re-verified independently against the source ledgers and `rulepack-prod-007.source.json`:

1. **[P2, CONFIRMED, cured]** §6's original topic-level backing paragraph enumerated "T3/T7/T9/T15"
   (omitting T10) even though `CL-CROSS-08` (T10) is present in the digest and discussed in §3.14 —
   the digest pair was not traceable to a §6 line. Added the missing T10 row.
2. **[P2, CONFIRMED, cured]** §6's original table applied "SUPPORTED (thin)" to
   `hf.bridging.from-visit-itk`/`el.bridging.t3-window-manual` (whose claims do not name the rule's
   specific decision logic either) while applying "UNBACKED" to `hf.bridging.to-bridging`/
   `review.bridging.adverse-history` (same absence-of-specific-naming pattern) — an inconsistently
   applied standard between two categories that looked, on the surface, like the same defect. Made the
   actual distinguishing standard explicit in a new paragraph above the table: SUPPORTED-thin rules sit
   within a claim's own core topical content even without naming the exact `reason_code`; UNBACKED
   rules sit in a fact domain (chaining, violation-history) no claim touches at all. This is a real
   difference in kind, not just degree — now stated, not merely applied silently.
3. **[P3, CONFIRMED, cured]** This card's own T1 "TOTAL GAP → closed" arc is genuinely comparable to
   C2's (both went from a batch-1 TOTAL GAP to a claim-backed T1) — C2.md's original §7 wording
   ("the only card in this slice...") is corrected there, not here, since it is C2's overreach, not
   BRIDGING's.
4. **[P2, NOT-AN-ISSUE]** `VERIFIED-WITH-CAVEAT` flagged as outside the base 5-state vocabulary — same
   disposition as A1.md's finding #6 (established, ledger-defined qualifier, not a defect).
5. **[P2, NOT-AN-ISSUE]** Reviewer asked whether BRIDGING's `public_catalog: false` status (unlike the
   other 5 cards in this slice) should change the doctrine card's disposition class — no; catalog
   visibility is a display/publication concern, not an eligibility-decision concern, and does not
   change the OD-3 arrest criterion's applicability.

Net: 3/5 raised findings were real and are cured above (1 of those cured in C2.md, not here); 2/5 were
reviewed and confirmed not applicable.
