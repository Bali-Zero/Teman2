---
adversarial_review: exempt-generated-artifact # regenerable snapshot, not a research deliverable — see the sibling dated report
---

# Reachability report — rulepack-prod-009.source.json

Pack `66eb0b4c-58ee-56c3-812c-2acc26fff8ce` sequence **9** (version `2026.8.19`, environment `PRODUCTION`) — 38 products, 110 rules.

## Reachability

- **Reachable (has ≥1 SUPPORT rule): 29** — A1, B1, BRIDGING, C1, C2, C6, D1, D12, D2, E23, E28A, E30, E30A, E30B, E30E, E30F, E31A, E31B, E31C, E31D, E31E, E31F, E31G, E31H, E31J, E33, E33E, E33F, E33G
- **Blocked (zero SUPPORT rules): 9** — E23U, E23V, E28B, E28C, E28D, E28F, E33A, E33B, E33C

## Fact-path coverage

- 37/44 FactPaths referenced by at least one rule.
- **7 FactPaths referenced by zero rules**: commercial.service_fee_budget_idr, commercial.wants_quote, immigration.last_entry_date, intent.desired_entry_date, person.birth_date, process.application_channel, work.employer_country_code

## NOT_ASKED facts (live production interview)

Source: `apps/mouth/src/app/(visa-oracle)/visa-oracle/_lib/fact-mapper.ts` — facts the interview hard-codes to `UNKNOWN(NOT_ASKED)` unconditionally, regardless of applicant answers.

- **5 facts**: commercial.service_fee_budget_idr, commercial.wants_quote, immigration.last_entry_date, intent.desired_entry_date, intent.requested_product_code
- 4 of these are ALSO referenced by zero rules in this pack (expected — an unasked fact cannot be usefully gated on): commercial.service_fee_budget_idr, commercial.wants_quote, immigration.last_entry_date, intent.desired_entry_date
- 3 facts the interview DOES collect but this pack references in zero rules (collected data the pack does not yet use): person.birth_date, process.application_channel, work.employer_country_code

## Orphan rules

None — every rule's `product_version_ids` resolves to a real product.

## Products without a positive persona

Source: `apps/backend-rag/backend/tests/services/visa_engine/test_evaluator_gold.py` (the 20-gold-persona corpus).

**CAVEAT (do not read the number below as the whole story):** that corpus replays against a hand-written FIXTURE pack, never this signed pack — a known LIVE STATE gap (visaoracle skill, 2026-08-12). Its product-code vocabulary can diverge from this pack's; see the absent-codes list below.

- Persona corpus positively supports (`expected_candidates`) 5 distinct code(s): C1, E23, E28A, E31, E33G
- **1 of those codes do not exist in this pack at all** (vocabulary drift between the fixture and this pack): E31
- **34/38 products in this pack are never a persona's `expected_candidates`**: A1, B1, BRIDGING, C2, C6, D1, D12, D2, E23U, E23V, E28B, E28C, E28D, E28F, E30, E30A, E30B, E30E, E30F, E31A, E31B, E31C, E31D, E31E, E31F, E31G, E31H, E31J, E33, E33A, E33B, E33C, E33E, E33F
