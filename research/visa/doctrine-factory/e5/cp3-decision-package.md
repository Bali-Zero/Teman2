---
date: 2026-08-19
domain: visa
client_case: none
adversarial_review: codex
sources:
  - path: research/visa/doctrine-factory/e5/2026-08-19-e5-increment3-fold.md
    note: "the rule-by-rule seq-7→seq-9 semantic delta, claim-cited — the artifact CP3 approves"
  - path: apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-009.source.json
    note: "the seq-9 candidate, sha256 e3c1457952722706ec59b0a23e66c7d7a6a7b88735cda982b54957f5e4648660"
---

# CP3 — seq-9 fold: decision package for Zero

CP3 (blueprint gate G4): **owner approves the seq-9 diff rule-by-rule, claim-cited**, gating
CP4 = the sign+activate ceremony (M5/Mini key custody, two-login ceremony, SHADOW unchanged).
The full delta lives in `2026-08-19-e5-increment3-fold.md`; this page is only what needs your
eye. ENFORCE is NOT touched by any of this — it stays NO-GO (DPIA / analytics-TTL unchanged).

## The candidate in one paragraph

seq-9 = seq-7 + the seq-8 pricing fold (11 products' `pricing_key`, OD-2 executed, broken chain
retired) + 2 defective rules RETIRED (`el.e33e.deposit-income-basis` UNSAT-redundant,
`el.e33g.income-60k-manual` vacuous-mislabeled) + 8 rules ADDED (E30E/E30F real SUPPORT;
E33A/B/C sponsor hard-filters; E23U/E23V requested-product review; E33G income-evidence review)
+ E31E hard-filters re-sourced to Permenkumham 22/2023 Pasal 33(2)(h)(5) + freshness cured
(`0497cb52` dropped, `ee8fe5b8` de-referenced from all 18 rules with ≥2 sources each kept,
`ecd22722` re-verified live). Chain: `previous_payload_sha256` = seq-7 signed payload hash,
recomputed in test, `sequence 9`, `rule_pack_id` per the uuid5 convention. Gates: compile_pack
RC 0, 129 targeted pytest + 25 vitest green, fold deterministic (2 runs byte-identical),
adversarial pass by 2 cross-family refuters (Codex, Kimi) + fix round, mutation-proven tests.
Reachability 27→29 / blocked 11→9.

## Decisions / acknowledgements for Zero (6)

1. **E33E rule retirement** — the defective rule turned out REDUNDANT: `CL-E33-04` (VERIFIED)
   says deposit **AND** income, which healthy `el.e33e.retirement` already encodes. Retired with
   no replacement; zero behavior change (an UNSAT rule can never fire). *Ack.*
2. **E33G narrows to review-gated** — the USD 60k/yr income requirement has NO fact in the
   closed vocabulary (and `secondhome.passive_monthly_income_usd` would be a semantic lie for a
   salary). Cure per your OD-1 pattern: honest eligibility stays (`el.e33g.remote-work`), new
   `review.e33g.income-evidence` blocks silent SUPPORT without income evidence. This is a
   deliberate delta vs OD-3's "27/27 reachable" count (E33G was reachable through the defect).
   The missing work-income FactPath is recorded in the fact-vocabulary-extension design (E6). *Ack.*
3. **E23U/E23V get review-only rules, production-inert for now** — the W3 factbase rules out any
   safe SUPPORT (sponsor facts can't discriminate the pair), so they got requested-product
   review rules mirroring the E33 mechanism — which is itself inert today:
   `intent.requested_product_code` is hard-coded NOT_ASKED in the live interview mapper. Wiring
   it is Track C / E6 scope (PENDING-ARMS row opened). No user-visible regression either way. *Ack.*
4. **Two inherited same-class defects deliberately NOT cured** — `el.c2.corporate-sponsor-type`
   and `el.e31c-mixed-marriage-parents` (both seq-7 bytes, both "name promises a check the
   condition never performs", the e33g disease). E31C is the sharper one: a live probe reached
   SUPPORTED with `marriage_registered=false` and a US sponsor. **No compilable claim grounds a
   tightening** (attempted, stopped — never invented), and C2 has CF-16 open. The refuters
   split: Codex "shipping it uncured is indefensible" vs Kimi "defensible scope discipline,
   same defect class". Both rules are byte-identical to what is LIVE in seq-7 today, so seq-9
   makes nothing worse; pinned as known residuals in tests + ledger. **Decision: ship seq-9 with
   them and cure in seq-10 after an E31C/C2 doctrine query batch (recommended), or hold seq-9
   until that batch lands.**
5. **E33C capital tiers NOT encoded** — the USD 25M/50M immigration-guarantee figures are
   flagged plausibly-conflated with the corporate Golden Visa; an unencoded flagged claim, not
   a rule. *Ack.*
6. **Freshness residual** — `ee8fe5b8` (imigrasi.go.id landing page) verified CHANGED and
   de-referenced from all 18 rules (each keeps ≥2 valid sources); 3 product-level refs remain
   untouched by design. *Ack.*

## What happens on your GO

PR merges (auto-armed at green) → signing ceremony on M5 (`sign_pack.py`, kid `prod-2026-07-1`,
`--i-know-this-is-production`) → activation via the proven two-login ceremony → live smoke
(IT/TOURISM full-facts, NG negative control, all-UNKNOWN fail-closed) → LIVE STATE + evidence.
SHADOW stays on; ENFORCE untouched. On "hold": everything stays merged-but-unsigned; seq-7
remains the active pack.

## Adversarial review

The package summarizes decisions already adversarially reviewed at the artifact level (Codex
DO-NOT-SHIP → fix round → re-verified; Kimi 3 P2/3 P3 → disposed). Dispositions:
`2026-08-19-e5-increment3-fold.md` §Adversarial review. No surviving undisposed objection.
