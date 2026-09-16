---
date: 2026-09-16
domain: operations
client_case: none
sources:
  - "apps/backend-rag/backend/services/visa_engine/evaluator.py (_rank_supported)"
  - "apps/backend-rag/backend/services/visa_engine/evaluate_path.py (_build_display)"
  - "apps/backend-rag/backend/services/visa_engine/api_models.py (VisaOracleEvaluateResponse._check_projection_integrity)"
  - "apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts and outcome-view-model.ts"
adversarial_review: exempt-builder-codex-luna-conclusion-rederived-on-disk-by-the-sonnet-dux-and-an-opus-shipping-session
---

# Visa Oracle candidate order requires seq22

Date: 2026-09-16
Mandate: `zero-decisioni-visa-oracle`

## Verdict

The requested business-meetings order `D2 -> D1 -> D12` is engine-owned, not a
presentation-only order. No frontend reorder was made and no signed or unsigned
RulePack was changed. A correction therefore requires a new signed engine pack
(seq22), subject to the normal pack-fold/sign/activation gates.

## On-disk proof

- `apps/backend-rag/backend/services/visa_engine/evaluator.py:911-945` states
  that `_rank_supported` ranks already-supported products from `RANKING` rules
  in the compiled pack and applies the stable `(-score, product_code,
  product_version_id)` sort. Lines `947-966` assign the resulting ranks and
  return the ordered `Candidate` tuple.
- `apps/backend-rag/backend/services/visa_engine/evaluate_path.py:898-918`
  starts the pack-backed display projection and iterates `decision.candidates`
  directly; lines `928-978` append and return entries in that same order without
  a presentation sort.
- `apps/backend-rag/backend/services/visa_engine/api_models.py:461-476`
  validates the response boundary and raises if display candidate IDs do not
  exactly match decision candidate order.
- The frontend contract is consistent with that ownership:
  `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/outcome-view-model.ts:1-8`
  explicitly says the deterministic engine owns candidate ordering, while
  `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/engine-adapter.ts:1464-1513`
  maps display candidates by index and does not reorder them.

## Pack state checked

- `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-020.signed.json:8228`
  is the highest signed production pack present and carries sequence 20.
- `apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-021.source.json:8355`
  carries sequence 21, but no `rulepack-prod-021.signed.json` is present in the
  tracked pack set.

## Action boundary

Do not change the frontend display order for this request. Do not edit or sign
the existing packs in this lane. The candidate-order correction belongs in the
next signed engine sequence, so this memo is the requested seq22 handoff.
