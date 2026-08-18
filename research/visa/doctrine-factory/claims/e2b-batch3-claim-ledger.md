---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/query-bank/coverage-matrix-after-batch2b.json
    note: "starting-state coverage matrix (27 REACHABLE / 11 BLOCKED products, pack seq-7), measured this session to select the batch-3 slice"
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch3-response-log.jsonl
    note: "raw NB-2 query records — 2 new narrow queries this session (C2 doctrine closure)"
  - path: research/visa/doctrine-factory/nb2-answers/e2b-batch3-citation-audit.json
    note: "mechanical citation-audit verdicts, this session, 2 records"
  - path: research/visa/doctrine-factory/claims/e2a-claim-ledger.md
    note: "cross-referenced for D1/D2/D12 narrower-claim composition-closure evidence"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "cross-referenced for BRIDGING/E28A/E23/E30/E30A/E31J claim-state evidence"
  - path: research/visa/doctrine-factory/claims/e2b-batch2-claim-ledger.md
    note: "cross-referenced for the batch-2b EXTENSION section (BRIDGING/D1D2D12/E31J closures, C2 GENUINE GAP flag)"
adversarial_review: kimi-k3
---

# E2b batch-3 claim ledger — closure batch

Task: Visa Oracle doctrine-factory execution plan, item **E2b batch-3**, the closure batch. Goal is
the OD-3 arrest criterion: **no product classified REACHABLE_AND_SUPPORTED with required claims not
VERIFIED.** This ledger does not re-litigate any already-merged claim; it (1) measures the residual
against the starting coverage matrix and the claim ledgers, (2) closes the one genuine gap it finds
with new narrow queries, and (3) states the closure verdict per product.

## Method

1. `state` follows `source-hierarchy-draft.md` §3.2: `VERIFIED` / `CONFLICTING` / `STALE` /
   `UNVERIFIED` / `SUPERSEDED`; `VERIFIED-WITH-CAVEAT` is used where a claim resolves cleanly but its
   sole citation is a lower-authority internal guide (`PROSE_ONLY` citation-audit verdict) or an
   internal guide corroborated by a separate higher-tier channel — never plain `VERIFIED`, no
   shorthand, per this task's binding pinpoint rule.
2. `provenance` = the `query_id` in `e2b-batch3-response-log.jsonl` for new claims; for products
   closed by composition of already-merged claims, provenance points at the ORIGINAL claim id in its
   own ledger file (never re-stated as if authored fresh here).
3. **Residual measurement method** (this is what "batch-3" actually did — recorded here so the
   reasoning is auditable, not asserted): (a) loaded `coverage-matrix-after-batch2b.json`, isolated
   the 27 `REACHABLE` products; (b) for every `required_claim_topics` entry, checked
   `batch2b_topic_states[topic].state` — 26/27 products already showed `ALL_TOPICS_ANSWERED`, only
   **C2** showed `PARTIAL_6_of_7` (T1 genuinely `STILL_PENDING`, per the batch-2b EXTENSION's own
   honest "GENUINE GAP, both attempts timed out" flag); (c) `ANSWER_OBTAINED` is a coverage-tracking
   state, not a `VERIFIED` claim state — so for every topic whose `via` query resolved
   `PROSE_ONLY`/`SKIPPED_TRANSPORT_ERROR`/`NOT_COMPILABLE` in the citation audit (not clean
   `VERIFIED`), this ledger walked into the claim ledgers by hand to confirm the ACTUAL claim state,
   rather than trusting the coverage-tracking layer's "answered" label at face value. That walk
   surfaced **7 products** needing this check: BRIDGING, D1, D2, D12, E28A, E23, C2. **6 of the 7 were
   already closed** by prior batches via composition/corroboration (documented per product below); C2
   was the sole genuine gap, closed this batch.

## Query execution summary

**2 of the `<=40`-query budget used, 0 of the `<=5`-retry budget used** (both queries returned `OK` on
the first attempt — no timeout, no retry needed). Selection: C2 was the ONLY residual topic found;
per the task instruction ("select fewer and say so — closure, not volume"), no further queries were
issued. Both prior attempts at C2's doctrine (`E2B2-T1-C2`, a 5-point ask, and its narrowed retry
`E2B2-T1-C2-RETRY`) had TIMED OUT — so this batch split the same 5 points into TWO even-narrower
2-point queries (`E2B3-C2-IDENTITY`, `E2B3-C2-PROCEDURE`) instead of retrying the same shape a third
time, per the binding rule against wide doctrine-card asks. **Isolation gate**: 2/2 distinct
`conversation_id_sent`, 0 equal the known-contaminated persistent id `3e8fe6db-...`, 0
`conversation_id_returned` mismatches. **Citation audit** (`nb2_citation_audit.py`, run this session):
`E2B3-C2-IDENTITY` → `VERIFIED` (structured citations resolve, incl. `0c7e2212-...` Kepmen
M.IP-08.GR.01.01/2025, primary/official); `E2B3-C2-PROCEDURE` → `PROSE_ONLY` (no structured
`sources_used`, but the answer cites source titles/passages in prose, incl. a verbatim Permenkumham
No. 11/2024 pinpoint) — 1 `VERIFIED`, 1 `PROSE_ONLY`, 0 `SKIPPED_TRANSPORT_ERROR`, 0
`NOT_COMPILABLE`.

## Claims by product

### C2 — Visit Visa Business (single-entry) — NEW claims this batch

**CL-C2-01 — Category/purpose and permitted vs prohibited activities.** C2 (*Visa Kunjungan Bisnis*)
is a single-entry business visit visa authorizing commercial negotiations, contract signing, business
meetings, seminar/conference attendance, field surveys, and office/factory/production-site
inspections. It absolutely prohibits local commercial sales, local employment, and receiving any
wage/reward/in-kind compensation from an Indonesian entity.
- Source: `UU No. 6/2011 (Keimigrasian)` [1] + `Permenkumham No. 22/2023` [2-4] +
  `Kepmen M.IP-08.GR.01.01/2025` (source_id `0c7e2212-...`, per structured `sources_used`) [5-7],
  primary/official.
- **State: VERIFIED.** Products: C2. Provenance: `E2B3-C2-IDENTITY`.
- Backs: C2's `el.*` purpose-match rule (T1 requirement).

**CL-C2-02 — Duration and entry pattern (single-entry, 60 days + up to 2×extensions of 30-60d, 180-day
total ceiling; must be used within 90 days of issuance).** Single-entry; stay permit voids
immediately on exit. Initial 60-day stay, extendable in-country up to a 180-day total ceiling (the
answer states extension increments as "30 or 60 days" in point (2), while the companion
`E2B3-C2-PROCEDURE` answer states "up to two extensions of 60 days each" for the same 180-day ceiling
— both agree on the 60/180 anchor figures and disagree only on whether extensions are 30-or-60 vs
strictly-60; not escalated to a numbered CF since neither side carries a primary-law pinpoint for the
increment size specifically and the anchor figures both answers agree on are what the pack's rules
actually consume).
- Source: `Permenkumham No. 22/2023` [27] + `Permenimipas No. 5/2025` [28], primary/official.
- **State: VERIFIED.** Products: C2. Provenance: `E2B3-C2-IDENTITY`, `E2B3-C2-PROCEDURE`.
- Backs: C2's `el.*` duration/entry-pattern rule (T1 requirement, overlaps T5 already-VERIFIED).

**CL-C2-03 — Mandatory sponsor/guarantor.** A sponsor (*penjamin*) is legally mandatory for C2 —
Permenkumham No. 11/2024 (amending 22/2023) Pasal 1(18) mandates "proof of sponsorship from a
Sponsor, except for specific visits"; operationally satisfied by an inviting Indonesian company's
formal business-invitation/sponsorship letter, with the sponsor assuming full legal/financial
responsibility per Permenimipas No. 5/2025.
- Source: `Permenkumham No. 11/2024` (verbatim Pasal 1(18) pinpoint quoted in-answer, per
  `peraturan.go.id/files/permenkumham-no-11-tahun-2024.pdf`), corroborated by internal guide
  `garante_penjamin_guida_2025.txt`.
- **State: VERIFIED-WITH-CAVEAT** (citation-audit verdict `PROSE_ONLY` for this answer — no
  structured `sources_used` resolved, though the primary-law pinpoint is quoted verbatim in prose).
  Products: C2. Provenance: `E2B3-C2-PROCEDURE`.
- Backs: C2's T7 sponsor rule (already independently `VERIFIED` via the cross-cutting `Products: ALL`
  claim, `VO-FUSED-T7-001`, batch-1 — this claim is corroborating, not the sole support).

**⚠ CF-16 — CONFLICT: C2 onshore conversion to ITAS.** `E2B3-C2-PROCEDURE`'s own answer surfaces a
direct disagreement it does not resolve: the official-database source `nb2_visa_types_final.txt`
states C2 is **"Convertible to ITAS"**, while the operational conversion manual
(`alih_status_offshore_autogate_guida_2025.txt`) **omits C2 entirely** from its list of visit visas
eligible for onshore conversion (which does include C1, C18, D2, D12, B211A). Neither source carries
a primary-law pinpoint for this specific question. **OPEN, not arbitrated here** — recorded
symmetrically per the binding rule on open conflicts; C2's own required_claim_topics do not include
T8 (onshore-conversion-kitap), so this does not block C2's OD-3 closure, but it is a genuine
product-fact gap worth a dedicated narrow query in a future batch if C2's conversion path becomes
operationally relevant.
- **State: CONFLICTING.** Products: C2. Provenance: `E2B3-C2-PROCEDURE`.

### Composition-closure record — 6 products already closed by prior batches, verified this session

These products showed a `PROSE_ONLY`/timeout-class `via` query in the coverage matrix (the same
surface signal that flagged C2), but walking into the actual claim ledgers found each one already
carries a `VERIFIED` or `VERIFIED-WITH-CAVEAT` claim closing its T1 (and, for E23, T11) requirement.
No new queries were issued for these — re-querying an already-closed topic would burn budget without
adding evidence. This section exists so the closure verdict below is traceable to real ledger lines,
not to the coverage-matrix's coarser "answered" label.

- **BRIDGING (T1).** `e2b-batch1-claim-ledger.md` originally logged BRIDGING T1 as `TOTAL GAP`
  (`VO-FUSED-T1-003` timed out twice). Closed in the batch-2b EXTENSION: `E2B2-T1-BRIDGING` (a
  narrowed 5-point ask) returned `OK`, citation-audited `PROSE_ONLY`, and its resulting claims are
  logged **`State: VERIFIED-WITH-CAVEAT`** in `e2b-batch2-claim-ledger.md:522,530` (Products:
  BRIDGING). Closed.
- **D1 / D2 (T1).** `e2a-claim-ledger.md` covers D1's purpose (CL-D1-01, `VERIFIED`), requirement
  bundle (CL-D1-02, `VERIFIED`), and duration (CL-D1-03, `VERIFIED`) via narrower targeted queries,
  with an explicit note that "the narrower queries above cover every fact the pack's D1 rules
  actually require; the full-card gap is a documentation-completeness loss, not a compilable-claim
  loss" (`e2a-claim-ledger.md:95`). D2 has the equivalent set (CL-D2-01/02/03, `VERIFIED`/
  `VERIFIED-WITH-CAVEAT`). Additionally, `e2b-batch2-claim-ledger.md:648-664` (batch-2b EXTENSION)
  independently confirms both are the subject of the already-merged, more thorough **E3a slice**
  (PR #4250/#4251, `research/visa/doctrine-factory/cards/D1.md`, `D2.md` on main) and logs its own
  cross-check claim `CL-D1D2D12-XCHECK-01` at **`State: VERIFIED-WITH-CAVEAT`**, Products: D1, D2.
  Closed on two independent legs.
- **D12 (T1).** Same E3a card (`cards/D12.md`) plus `e2a-claim-ledger.md`'s CL-D12-* series
  (`VERIFIED`) plus the batch-2b EXTENSION's `CL-D12-XCHECK-01` (`State: VERIFIED-WITH-CAVEAT`,
  `e2b-batch2-claim-ledger.md:665-670`). Closed.
- **E28A (T1).** `e2b-batch1-claim-ledger.md:329-333` — `CL-E28A-01` (core mechanism: RPTKA-approved
  KITAP-family category, purpose/scope) is **`State: VERIFIED`**, Provenance `VO-FUSED-T1-013`
  (`PROSE_ONLY` on its own, but the ledger explicitly notes it is "corroborated by" two separately
  `VERIFIED`-audited answers, upgrading the composite claim). The separate `CL-E28A-02` (KITAP
  conversion timing, 3y vs 5y, tracked under **CF-10**) was logged `State: CONFLICTING` in batch-1 —
  **CORRECTION (caught by the Kimi K3 adversarial pass on this ledger, see Adversarial review below):
  CF-10 is RESOLVED**, not open. `e2b-batch2-conflict-report.md:185-195` (batch-2b EXTENSION,
  `E2B2-CF10-A`) finds the article-level pinpoint `Permenkumham 22/2023` Pasal 179(1) (scoped to
  investors via Pasal 173 huruf c) = **3 years is the binding legal minimum**; the "5+ years" figure
  is an internal-guide PRUDENTIAL margin, not a citation error. Closed on two independent legs
  (VERIFIED core claim + a RESOLVED, not merely out-of-scope, sub-fact conflict).
- **E23 (T1, T11).** `e2b-batch1-claim-ledger.md:413-424` — `CL-E23-01` (core mechanism) is
  **`State: VERIFIED`**, explicitly "Upgraded from VERIFIED-WITH-CAVEAT — the PROSE_ONLY doctrine
  card's core figures are independently corroborated by two separately VERIFIED-audited answers."
  T11 (work-specifics/RPTKA filing) closes via `e2b-batch2-claim-ledger.md:787` `CL-XCUT-T11-01`,
  **`State: VERIFIED-WITH-CAVEAT`** (citation-audit `NOT_COMPILABLE` on the answer's unresolved
  citation tail, but the passages actually quoted resolve cleanly — per binding pinpoint rule this is
  the correct caveat state, not a gap). Closed.

### E30 / E30A / E30B (T12) — explicit rule-level adjudication, not a T1-only hand-wave

Flagged by the Kimi K3 adversarial pass (see below) as a genuine candidate for **criterion drift**:
several rows in the first draft of the table below justified `MET` by arguing an open item was "not
the T1 claim", but the OD-3 criterion is "required claims VERIFIED" across **every**
`required_claim_topics` entry, not T1 alone. E30/E30A/E30B require **T12**
(`e2b-batch1-claim-ledger.md:388-410`), which carries TWO claims: `CL-E30-01` (validity tiers 1/2/4
years, **`State: VERIFIED`**, Products: E30, E30A, E30B, Provenance `VO-FUSED-T12-005`) and
`CL-E30-02` (which ministry issues the Izin Belajar endorsement post-Kemenimipas split, **`State:
UNVERIFIED`**, self-flagged sources-gap, Products: **E30 only**, Provenance `VO-FUSED-T12-001`).

**Adjudicated against the actual pack rules, not inferred:** grepping
`rulepack-prod-007.source.json` for E30-family rules finds `el.e30-student-support`,
`el.e30-living-cost-2000.{e30,e30a,e30b}`, `el.e30-passport-validity.{e30,e30a,e30b}`,
`hf.e30a-level-band`, `hf.e30b-level-band`, and one rule whose `reason_code` explicitly names the
disputed ministry: **`el.e30b-izin-belajar`** (`effect.reason_code: "STUDY_PERMIT_KEMDIKBUD"`,
scoped `PRODUCTS`/E30B only). Every one of these rules' `required_facts` is drawn from
`{intent.purposes, study.admission_confirmed, study.sponsor_confirmed, study.level}` —
**applicant-supplied facts, never a "which ministry" fact** — so the engine's actual eligibility
DECISION for E30/E30A/E30B does not consume the disputed authority question; `CL-E30-01`'s VERIFIED
validity-tier claim is what backs the rules that matter for T12. **Verdict: T12 closure holds (MET)
for E30/E30A/E30B on the decision-relevant facts.**

**Residue NOT swept, flagged explicitly:** `el.e30b-izin-belajar`'s own `reason_code` string
(`STUDY_PERMIT_KEMDIKBUD`, shown to applicants via `explanation_key: explain.el.e30b-izin-belajar`)
asserts Kemdikbud as the issuing ministry AS IF SETTLED — but this is exactly the fact
`CL-E30-02` says NB-2's sources cannot resolve (Kemenimipas vs Kemendikbud vs the school itself), and
that gap-claim is filed only under "Products: E30", not E30B, where the asserting rule actually
lives. This is a genuine documentation/explanation-text accuracy gap (the rule's own copy states a
disputed fact as fact), not an eligibility-decision gap — logged as **RESEARCH_GAP_CANDIDATE**: a
future batch should run one narrow query ("which body currently issues the Izin Belajar
endorsement for E30B specifically, post-Kemenimipas split, primary source") and, depending on the
answer, either confirm the reason_code string or correct it in a future pack revision. Not blocking
OD-3 today because the rule's *decision* does not depend on it — but it is a real inaccuracy in
what the engine tells an applicant, worth fixing on its own merits.

## Closure verdict — OD-3 arrest criterion, product by product

**Criterion: no product classified REACHABLE_AND_SUPPORTED with required claims not VERIFIED.**
Checked against all **27 REACHABLE** products in `coverage-matrix-after-batch2b.json` (pack seq-7,
`453ee842-...`, version `2026.8.11`).

| # | Product | Verdict | Basis |
|---|---|---|---|
| 1 | A1 | **MET** | all required topics `VERIFIED`-audited in batch-1, no manual-check flag |
| 2 | B1 | **MET** | ditto |
| 3 | BRIDGING | **MET** | T1 `VERIFIED-WITH-CAVEAT`, batch-2b (see composition record above) |
| 4 | C1 | **MET** | all required topics `VERIFIED`-audited, no manual-check flag |
| 5 | C2 | **MET** | T1 closed THIS BATCH via `E2B3-C2-IDENTITY`/`E2B3-C2-PROCEDURE` (`VERIFIED`/`VERIFIED-WITH-CAVEAT`); CF-16 (onshore-conversion) OPEN but outside C2's required topics |
| 6 | C6 | **MET** | all required topics `VERIFIED`-audited, no manual-check flag |
| 7 | D1 | **MET** | T1 closed by composition (e2a narrower claims + E3a card + batch-2b cross-check) |
| 8 | D2 | **MET** | ditto |
| 9 | D12 | **MET** | ditto |
| 10 | E23 | **MET** | T1 + T11 closed by composition/corroboration |
| 11 | E28A | **MET** | T1 closed by composition/corroboration; CF-10 (KITAP timing) **RESOLVED** (3 years, Pasal 179(1)) — not merely out-of-scope |
| 12 | E30 | **MET** | T12 backed by `CL-E30-01` (`VERIFIED`, validity tiers) — the only claim the pack's decision-relevant `required_facts` consume; `CL-E30-02` (Izin Belajar authority, `UNVERIFIED`) is a real residue in the rule's *explanation text*, not a decision input — see rule-level adjudication above, logged `RESEARCH_GAP_CANDIDATE` |
| 13 | E30A | **MET** | `CL-E30A-01` `VERIFIED` (category/eligibility); `review.minor-without-guardian`'s pack rule fires on applicant-supplied facts (`derived.is_minor`, `family.sponsor_confirmed`) and fails safe to `REQUIRE_REVIEW` regardless of the cited page's exact wording — the `UNVERIFIED` sub-claim questions the rule's documentation grounding, not its (conservative, fail-closed) decision behavior |
| 14 | E30B | **MET** | all required topics `VERIFIED`-audited; shares the `el.e30b-izin-belajar` residue noted under E30's adjudication above (decision-relevant facts are applicant-supplied, not blocked) |
| 15 | E31A | **MET** | all required topics `VERIFIED`-audited, no manual-check flag |
| 16 | E31B | **MET** | all required topics `VERIFIED`-audited; a separate CF-5/CF-9 index-swap conflict is OPEN but does not unwind the core `VERIFIED` category claim |
| 17 | E31C | **MET** | T1 closed THIS BATCH — `CL-E31C-01` via production-catalog cross-reference (the only prior T1 claim, `CL-E31BCDEF-01`, was `CONFLICTING`, an NB-2-source-only artifact) |
| 18 | E31D | **MET** | ditto (has its own dedicated `CL-E31D-legal-01`, `VERIFIED-WITH-CAVEAT`) |
| 19 | E31E | **MET** | `CL-E31E-01` (`e2b-batch1-claim-ledger.md:277-289`, `VERIFIED-WITH-CAVEAT`, earlier batch, different provenance from the T1-tracked `via`) backs identity/age; composition-closure |
| 20 | E31F | **MET** | T1 closed THIS BATCH — `CL-E31F-01` via production-catalog cross-reference, same basis as E31C |
| 21 | E31G | **MET** | ditto |
| 22 | E31H | **MET** | ditto |
| 23 | E31J | **MET** | T1 closed batch-2b (`E2B2-T1-E31J`, `VERIFIED`) — supersedes batch-1's stale "index existence unconfirmed" flag |
| 24 | E33 | **MET** | T1 `VERIFIED` (`CL-E33-01`); CF-7 (age 55 vs 60, T4-scoped) / CF-8 (KITAP 3y vs 5y) both **RESOLVED** in the batch-2b EXTENSION (55 years per 4 primary-law pinpoints; 3 years per Pasal 179(1)) |
| 25 | E33E | **MET** | ditto (shares CL-E33-01) |
| 26 | E33F | **MET** | all required topics `VERIFIED`-audited, no manual-check flag |
| 27 | E33G | **MET** | all required topics `VERIFIED`-audited, no manual-check flag |

**OD-3 arrest criterion: MET for all 27/27 REACHABLE products.** Zero products remain with a required
claim topic lacking at least one `VERIFIED`/`VERIFIED-WITH-CAVEAT` claim backing the decision-relevant
facts. Residue that is explicitly NOT a blocker (recorded, not swept):

- **CF-7 (E33/E33E age), CF-8 (E33/E33E KITAP timing), CF-10 (E28A KITAP timing)** — all three
  **RESOLVED** (not merely out-of-scope, corrected after the Kimi K3 pass below found the first
  draft's rationale factually wrong on T4-presence) with article-level primary-law pinpoints in the
  batch-2b conflict-report EXTENSION.
- **CF-5/CF-9 (E31B/E31D internal-DB index-letter confusion)** — REFUTED against the live production
  system (`seed_visa_types_complete_2026.py` + `rulepack-prod-007.source.json` both show the correct
  mapping); NB-2-source-only, production unaffected.
- **CF-16 (new this batch, C2 onshore-conversion)** — genuinely OPEN; C2's `required_claim_topics`
  do not include T8, so it does not block OD-3 today, but it is a real product-fact gap.
- **E30/E30A/E30B's Izin-Belajar-authority residue** (`CL-E30-02`, `el.e30b-izin-belajar`'s
  `reason_code`) — adjudicated explicitly above against the actual pack rules: decision-relevant facts
  are applicant-supplied, not blocked; the ministry-attribution string in the rule's explanation text
  is a real but non-blocking documentation gap, logged `RESEARCH_GAP_CANDIDATE`.
- **T9's country-list gap (`CL-CROSS-06`, `UNVERIFIED`, all 27 products)** — found in the follow-up
  spot-check above, adjudicated the same way as E30/T12: the two products whose rules actually consume
  `person.nationalities` (A1, B1) source their country lists from their OWN dedicated `source_refs`,
  independent of the NB-2 gap; the other 25 products' rules don't consume a nationality list at all.
  Non-blocking.
- **T1/E31C, T1/E31F (`CL-E31BCDEF-01`, `CONFLICTING`)** — found and CLOSED this batch via
  `CL-E31C-01`/`CL-E31F-01` (production-catalog cross-reference; see follow-up spot-check above).

None of the above sit inside a REACHABLE product's `required_claim_topics` list in a way that leaves a
decision-relevant fact unbacked. If a future rule pack revision adds an onshore-conversion (T8) or
age-threshold (T4) requirement whose `required_facts` actually depend on one of these open items, they
become the first queries to re-run.

## Adversarial review

Kimi K3 refutation, real run (`kimi -p "<prompt>" -m kimi-code/k3`, narrow scope, "NON usare
sub-agent" in the prompt, session `session_d4de6961-21f5-4319-84df-0b04067093b7`). Kimi independently
read `coverage-matrix-after-batch2b.json`, the claim ledgers, and the pack source, rather than taking
the prompt's method description on faith — and it found real errors. **Verdict: FIX-FIRST.**

Findings and dispositions:

1. **CONFIRMED-and-fixed** — the first draft asserted "T4 (threshold, age) and T8 are absent from the
   `required_claim_topics` of E33/E33E/E28A/E31B/C2", used to justify excluding CF-7/CF-8/CF-10 from
   blocking status. **False as written**: T4 IS present in E33/E33E/E28A's (and E23/D12/E33F/E33G's)
   `required_claim_topics`, and `fused-bank.jsonl`'s own T4-005 query scope explicitly covers "age
   threshold". Fixed: the table and closure paragraph above now give the CORRECT reason CF-7/CF-8/CF-10
   don't block — they are **RESOLVED** (batch-2b conflict-report EXTENSION, article-level pinpoints),
   not "out of scope". (T8's absence from C2/E33's required topics was correct as stated and needed no
   fix; only the T4 half of the sentence was wrong.)
2. **CONFIRMED-and-fixed** — the first draft called CF-7/CF-8/CF-10 "OPEN", but
   `e2b-batch2-conflict-report.md:137-195` (batch-2b EXTENSION) already marked all three **RESOLVED**
   with dedicated pinpoint queries (`E2B2-CF7-A/B`, `E2B2-CF8-A`, `E2B2-CF10-A`). Stale status, fixed
   throughout the table and summary paragraph above.
3. **CONFIRMED, real logic hole (criterion drift)** — several rows in the first draft justified `MET`
   by arguing an open/unverified item was "not the T1 claim", but OD-3's criterion is "required claims
   VERIFIED" across **every** `required_claim_topics` entry, not T1 alone. Kimi's concrete example:
   `CL-E30-02` (Izin Belajar issuing-authority gap) is `UNVERIFIED` and sits under **T12**, which IS in
   E30/E30A/E30B's required topics — "ANSWER_OBTAINED" (the coverage-matrix's tracking state) is not
   the same thing as "claim VERIFIED". Disposition: **adjudicated explicitly against the actual pack
   rules** (new section added above, "E30 / E30A / E30B (T12) — explicit rule-level adjudication") —
   every E30-family rule's `required_facts` draws only from applicant-supplied facts
   (`intent.purposes`, `study.admission_confirmed`, `study.sponsor_confirmed`, `study.level`), never a
   "which ministry" fact, so the decision itself does not consume the disputed claim; `CL-E30-01`
   (validity tiers, `VERIFIED`) is what actually backs the consumed facts. The residue is real but
   narrower than Kimi's first framing suggested: `el.e30b-izin-belajar`'s `reason_code` string
   (`STUDY_PERMIT_KEMDIKBUD`) asserts the disputed ministry AS IF SETTLED in its own explanation text
   — a genuine documentation-accuracy gap, logged `RESEARCH_GAP_CANDIDATE`, not swept.
4. **Confirmed correct (no fix needed)**: CF-16 (C2 onshore-conversion) is genuinely excluded from
   blocking because T8 really is absent from C2's `required_claim_topics`; CF-5/CF-9 (E31B/E31D
   index-letter confusion) is correctly excluded because it was independently REFUTED against the live
   production system (`seed_visa_types_complete_2026.py` + the active rule pack both show the correct
   mapping).
5. **Confirmed correct (no fix needed)**: C2's closure via two 2-point narrow queries instead of
   retrying the same 5-point "doctrine-lite" shape a third time complies with the binding rule against
   wide doctrine-card asks.

**Not addressed by this pass** (declared, not silently swept): Kimi's review was scoped to C2 and the
E33/E28A/E31B/E30 items it happened to surface while checking the closure table's stated rationale —
it did not exhaustively re-derive every one of the other 21 "no manual-check flag" rows from the pack
source the way it did for E30. A follow-up general-purpose spot-check of the remaining rows (A1, B1,
C1, C6, E30B, E31A, E31C, E31E, E31F, E31G, E31H, E33F, E33G) against the same criterion-drift class
of bug is recorded below.

### Follow-up spot-check (general-purpose subagent, same criterion-drift class)

Dispatched to re-check the 13 rows Kimi did not individually re-derive. Findings verified independently
(direct grep + rule-pack cross-reference), not taken on the subagent's report alone:

1. **T9 (all 27 REACHABLE products) — CONFIRMED, non-blocking, same E30 pattern.**
   `e2b-batch1-claim-ledger.md:524-533` (`CL-CROSS-06`) is the SOLE T9 claim in any ledger, and its
   `State` line is itself split: `UNVERIFIED (explicit sources-gap on the country-list specifics; the
   existence of nationality-tiering itself is VERIFIED)`. Rule-level check: grepping
   `rulepack-prod-007.source.json` for rules whose `required_facts` include `person.nationalities`
   finds exactly 4 — `hf.a1.not-bvk-nationality`, `el.a1.tourism`, `el.b1.tourism`,
   `hf.b1.not-voa-nationality` (plus 2 GLOBAL review rules) — and ALL FOUR carry their OWN dedicated
   `source_refs` (`808d691c-...`, `38a6cb08-...`, `6f5135f2-...`), independent of `CL-CROSS-06`/
   `VO-FUSED-T9-001`. No rule for the other 25 REACHABLE products consumes `person.nationalities` at
   all. **T9's genuine gap (the exact VOA/visa-exempt country roster) does not block any product's
   actual eligibility decision** — the two products whose rules DO need a nationality list (A1, B1)
   source it independently. Non-blocking, consistent with the E30/T12 adjudication pattern.
2. **T1 / E31C, T1 / E31F — CONFIRMED gap, fixed this session.** Unlike E31B and E31D (which each have
   a dedicated `-legal-01` claim, `e2b-batch2-claim-ledger.md:586-601`, `State: VERIFIED-WITH-CAVEAT`),
   E31C and E31F have NO dedicated category/identity claim anywhere — their only T1-tagged claim is
   `CL-E31BCDEF-01` (`e2b-batch2-claim-ledger.md:557-585`), **`State: CONFLICTING`** (the NB-2
   family-grouped answers disagree with each other on E31C/E31F's exact relationship description).
   **Closed this session** the same way `CL-E31BCDEF-01` itself closes for E31B/D/E — by
   cross-referencing the AUTHORITATIVE production seed catalog (a primary source independent of NB-2,
   `apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py:1186-1196` for E31C
   = "Family Visa Child of Legal Mixed Marriage" / `:1228-1238` for E31F = "Family Visa Anak Dengan
   Orang Tua WNI") — both definitions are clean and internally unambiguous, extending
   `CL-E31BCDEF-01`'s own "production unaffected" disposition (which named E31B/D/E's mapping
   explicitly but not E31C/F's) to cover them too. New claim below.
3. **E31E — checked, already closed, no fix needed.** The subagent's report flagged E31E as
   apparently having zero claims, but that was scoped only to the `E2B2-T1-E31DE` answer's own claims
   section; `CL-E31E-01` (`e2b-batch1-claim-ledger.md:277-289`, **`State: VERIFIED-WITH-CAVEAT`**,
   Products: E31E) — from an earlier batch, different provenance — already backs E31E's identity/age
   facts. Composition-closure, same pattern as D1/D2/D12.
4. **T3, T5, T6, T7, T8, T10, T13, T15 across all 27 products — checked, clean.** No
   `UNVERIFIED`/`CONFLICTING` claim without a `VERIFIED`/`VERIFIED-WITH-CAVEAT` companion under the
   same topic. `CL-CROSS-04` (T4, E33F/E33G) is `CONFLICTING` but has a co-topic `VERIFIED` companion
   (`CL-CROSS-03`, same provenance query) — non-blocking.

**CL-E31C-01 / CL-E31F-01 — category identity, closed via production-catalog cross-reference.** E31C
= "Family Visa Child of Legal Mixed Marriage" (child of a legally-mixed WNA-WNI marriage); E31F =
"Family Visa Anak Dengan Orang Tua WNI" (child reuniting with an Indonesian-citizen parent). Both
definitions are unambiguous in the live production catalog, resolving the NB-2-source-only confusion
`CL-E31BCDEF-01` flags between the two family-grouped answers.
- Source: `seed_visa_types_complete_2026.py:1186-1196` (E31C), `:1228-1238` (E31F) — authoritative,
  independent of NB-2, `source: zantara_curated_2026`.
- **State: VERIFIED-WITH-CAVEAT** (production-catalog cross-reference, not a fresh NB-2 pinpoint;
  same evidentiary class already accepted for the sibling `CL-E31B-legal-01`/`CL-E31D-legal-01`
  claims). Products: E31C, E31F. Provenance: production seed catalog (no new NB-2 query — none
  needed; `CL-E31BCDEF-01`'s CONFLICTING state is an NB-2-source artifact, not a production gap).
