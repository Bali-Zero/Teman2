---
adversarial_review: codex
date: 2026-08-19
domain: visa
client_case: none
sources:
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-007.source.json
    note: "el.e33g.income-60k-manual (defective, VACUOUS-duplicate) and el.e33g.remote-work (sibling, same when-shape as the deduped cure)"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
    note: "CL-E33G-02 (USD 60,000/year income threshold, VERIFIED-WITH-CAVEAT) — the doctrinal grounding for why a review gate is needed, not for a runtime-testable income fact"
  - path: research/visa/doctrine-factory/cards/E33G.md
    note: "§3.2/§4/§6 — names the same defect (duplicate subtree, zero income facts tested) independently, adversarially reviewed there via kimi-k3"
  - path: apps/backend-rag/backend/services/visa_engine/evaluator.py
    note: "lines 610-663 evaluate_product() — HUMAN_REVIEW-stage TRUE outranks ELIGIBILITY SUPPORT for the same product, verified live this session (not assumed)"
  - path: research/visa/2026-08-12-fact-vocabulary-extension-design.md
    note: "the missing work-income FactPath is already recorded here as a lead per spec Step 3b"
discovered_by: agent.air-m5.backend-rag.visa-e5-seq9-implementer-b
adversarial_review: none (single-implementer artifact, prepared for CP3 review — not yet adversarially reviewed by a second seat)
---

# E33G cure — `el.e33g.income-60k-manual` -> `el.e33g.remote-work-configuration` + new `review.e33g.income-evidence`

## The defect (reconfirmed, not just cited)

`el.e33g.income-60k-manual`'s `when` is `all(subtree_A, subtree_A)` — the SAME 4-fact remote-work
condition duplicated as both children of the outer `all`. It is byte-for-byte identical (canonical
JSON) to `el.e33g.remote-work`'s own `when`. The literal string `60000` does not appear anywhere
in `rulepack-prod-007.source.json` (grepped this turn: zero matches). The rule's
`reason_code` (`E33G_INCOME_60K_ADVISOR_CHECK`) names a check the condition tree never performs.

## Claim citation backing the cure

**`CL-E33G-02`** (`e2b-batch1-claim-ledger.md:115-124`), state **VERIFIED-WITH-CAVEAT**: *"E33G
requires documented proof of a minimum annual income of USD 60,000 (foreign employment contract,
payslips, or PayPal/bank statements)."* Caveat: sourced from Bali Zero's own internal operational
guide (`kitas_e33g_remote_work_guida_2025.txt`) and a dedicated threshold query, not an
independently-confirmed Kepmen/Permenkumham article pinpoint for the USD 60,000 figure
specifically — well-corroborated operationally, not primary-law-verified. This is the doctrinal
reason a review gate is needed at all: the requirement is real and claim-backed, but there is no
`work.*` (or any other) FactPath carrying an income amount to test mechanically (Anchors section
of the E5 inc-3 spec: *"There is NO work-income fact... `secondhome.passive_monthly_income_usd`
is passive income, semantically wrong for a remote worker's salary — do NOT reuse it for E33G"*).
The gap is already tracked as a lead in `research/visa/2026-08-12-fact-vocabulary-extension-design.md`.

## The cure (`cure-e33g.json`, this directory)

1. **`el.e33g.remote-work-configuration`** (renamed from `el.e33g.income-60k-manual`) — dedupe
   `all(subtree, subtree)` to a single `subtree` (the 4 employer/clients/compensation facts
   unchanged), rename the reason_code from the dishonest `E33G_INCOME_60K_ADVISOR_CHECK` to
   `E33G_REMOTE_WORK_CONFIGURATION_ELIGIBLE` (names what the condition actually tests: the
   remote-work configuration, not income). `covered_purposes`, `source_refs`,
   `product_version_ids`, `priority`, `valid_period`, `on_unknown`, `safety_critical` all
   preserved verbatim from seq-7.
   - **Note for CP3, not silently smoothed over:** this rule's `when` is now structurally
     IDENTICAL to the pre-existing sibling `el.e33g.remote-work` (`REMOTE_WORK_ELIGIBLE`) — same
     4 facts, same AND structure, same `effect.type` SUPPORT. Both rules independently grant
     SUPPORT on the exact same condition. This is a pre-existing redundancy in seq-7 (not
     introduced by this cure — `el.e33g.income-60k-manual`'s inner subtree already matched
     `el.e33g.remote-work` byte-for-byte before this cure), and is out of this session's Step-3b
     scope to resolve (the spec names the rename+dedupe+add-review-gate shape explicitly and does
     not ask to retire either SUPPORT rule). Flagged here so CP3 can decide whether the two SUPPORT
     rules should eventually be merged into one.
2. **`review.e33g.income-evidence`** (NEW) — HUMAN_REVIEW stage, PRODUCTS-scoped to E33G, same 4
   facts as (1), effect `REQUIRE_REVIEW` with a NEW reason_code `E33G_INCOME_EVIDENCE_REVIEW`.
   OD-1 pattern: an un-modelable statutory-adjacent requirement (income floor, no FactPath exists)
   routed to human judgment rather than silently granted.

## Why the review gate actually narrows E33G (verified against the evaluator, not assumed)

The spec's CP3 note claims this "narrows E33G from (defectively) SUPPORTED-able to review-gated."
That is only true if a product-scoped `HUMAN_REVIEW` TRUE actually overrides an `ELIGIBILITY`
SUPPORT for the SAME product — otherwise `el.e33g.remote-work` (pre-existing, unconditional
SUPPORT on these same 4 facts, no review gate) would still let E33G reach SUPPORTED regardless of
this cure. Read `apps/backend-rag/backend/services/visa_engine/evaluator.py::evaluate_product`
this session (lines 610-663):

```
610  if any(result.truth is TruthValue.TRUE for _, result in hard_results):
611      return finish(... status=ProductProofStatus.EXCLUDED ...)
...
624  if any(result.truth is TruthValue.TRUE for _, result in review_results):
625      return finish(... status=ProductProofStatus.REVIEW ...)
...
650  true_support = tuple(... for rule, result in support_results if result.truth is TruthValue.TRUE)
```

`review_results` (HUMAN_REVIEW stage) is checked and can return `REVIEW` at line 624-634 —
**before** `support_results` (ELIGIBILITY stage, line 650+) is ever consulted for the final
status. So a TRUE `review.e33g.income-evidence` forces `ProductProofStatus.REVIEW` for the whole
E33G product proof regardless of how many ELIGIBILITY rules (including `el.e33g.remote-work` and
the newly-renamed `el.e33g.remote-work-configuration`) would otherwise SUPPORT it. This confirms
the spec's narrowing claim is correct — verified against the real evaluator code this turn, not
carried forward from the spec's own assertion.

## QW-4a reason-code contract — concrete edit needed, NOT applied yet

`E33G_INCOME_EVIDENCE_REVIEW` is a brand-new `HUMAN_REVIEW` reason_code. It does not fit any
existing `REVIEW_REASON_COPY` key in
`apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts` (checked all 7 existing
keys: `CALLING_VISA_REVIEW`, `ACTIVE_OVERSTAY`, `CITIZENSHIP_LIST_DIVERGENCE`,
`MINOR_WITHOUT_CONFIRMED_GUARDIAN`, `BRIDGING_ADVERSE_HISTORY`, `LOCAL_MARKET_ACTIVITY_REVIEW`,
`DISCLOSED_ACTIVITY_BOUNDARY_REVIEW` — none is E33G-income-shaped) and is not currently in
`KNOWN_UNMAPPED_REVIEW_REASON_CODES` (`engine-adapter.test.ts:511-539`).

**Deliberately NOT added to either list in this session.** `reviewReasonCodesInPack()`
(`engine-adapter.test.ts:449-465`) derives "real" HUMAN_REVIEW codes by globbing the actual
`rulepack-prod-*.source.json` files on disk — since `rulepack-prod-009.source.json` does not exist
yet (assembly is a later step, owned by a different lane per this task's scope fence), adding
`E33G_INCOME_EVIDENCE_REVIEW` to `KNOWN_UNMAPPED_REVIEW_REASON_CODES` NOW would create a phantom
entry and fail the test `"keeps the known-gap list honest: no entry there names a code that
stopped being real"` (`engine-adapter.test.ts:579-594`). Verified this by reading that test's own
assertion, not assumed.

**Concrete edit for whoever assembles seq-9 (Step 5) to apply in the SAME change that lands
`rulepack-prod-009.source.json`:**

```diff
--- a/apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts
+++ b/apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.test.ts
@@ const KNOWN_UNMAPPED_REVIEW_REASON_CODES = [
     "E33B_EXPERTISE_QUALIFICATION_CHECK",
     "E33G_EXCLUDES_LOCAL_COMPANY_OWNERSHIP",
+    "E33G_INCOME_EVIDENCE_REVIEW",
     "E33_WORK_RANGKAP_KEGIATAN_GATED",
```

(Alphabetically slotted next to the existing `E33G_EXCLUDES_LOCAL_COMPANY_OWNERSHIP` entry, same
list style.) QW-4b (separately gated on copy-deck approval per the test file's own comment) later
writes the actual bilingual sentence into `REVIEW_REASON_COPY` and removes the code from this list.

## Proof: guilt on the original, innocence on the cure (this turn, `prove_cures.py`)

```
[PASS] GUILT: original el.e33e.deposit-income-basis is UNSATISFIABLE — expect_clean=False, findings=1
    - el.e33e.deposit-income-basis: condition is UNSATISFIABLE — brute-force over 6 distinct leaf condition(s) (each treated as an independent boolean atom) finds zero of 64 assignments that satisfy `when`; this rule can never fire. NOTE: this check is sound for UNSAT-by-structure but blind to arithmetic contradictions between different leaves (e.g. x>5 AND x<3) — if this fired, the tree really is structurally self-contradictory, not merely arithmetic-narrow.
[PASS] GUILT: original el.e33g.income-60k-manual has a duplicate subtree — expect_clean=False, findings=1
    - el.e33g.income-60k-manual: 'all' node has two structurally identical children (args[0] == args[1]) — a duplicated child adds no logical content beyond a single copy (VACUOUS-RULE): if the intent was two DIFFERENT conditions, one of them was never actually written
[PASS] INFO (not a defect): original el.e33g.income-60k-manual is satisfiable (fires for every clean remote worker — that's the VACUOUS problem, not an UNSAT one) — expect_clean=True, findings=0
[PASS] INNOCENCE: cured el.e33g.remote-work-configuration has NO duplicate subtree — expect_clean=True, findings=0
[PASS] INNOCENCE: cured el.e33g.remote-work-configuration is satisfiable — expect_clean=True, findings=0
[PASS] INNOCENCE: new review.e33g.income-evidence has NO duplicate subtree — expect_clean=True, findings=0
[PASS] INNOCENCE: new review.e33g.income-evidence is satisfiable — expect_clean=True, findings=0
[PASS] el.e33g.remote-work-configuration validates as a real Rule (required_facts derived: ['intent.purposes', 'work.employer_is_indonesian_entity', 'work.indonesia_source_compensation', 'work.serves_indonesian_clients'])
[PASS] review.e33g.income-evidence validates as a real Rule (required_facts derived: ['intent.purposes', 'work.employer_is_indonesian_entity', 'work.indonesia_source_compensation', 'work.serves_indonesian_clients'])

=== SUMMARY ===
ALL CHECKS PASSED
```

Invocation (from `apps/backend-rag`, venv active):
`PYTHONPATH=. python ../../research/visa/doctrine-factory/e5/inc3-pack-edits/prove_cures.py`

## Adversarial review

Reviewed 2026-08-19 by two cross-family refuter seats (Codex GPT-5.6 high; Kimi K3) as part
of the whole seq-9 fold working tree — both DROVE the real evaluator rather than reading the
diff. Findings touching this artifact and their dispositions are consolidated in
`../2026-08-19-e5-increment3-fold.md` §Adversarial review (fold doc); no finding against this
artifact survived undisposed.
