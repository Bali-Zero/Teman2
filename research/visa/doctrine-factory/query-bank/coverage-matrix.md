---
date: 2026-08-17
domain: visa
client_case: none
sources: [rulepack-prod-007.source.json, research/visa/doctrine-factory/reachability/rulepack-prod-007-reachability.md, research/visa/doctrine-factory/query-bank/fused-bank.jsonl]
---

# E2b PREP — coverage matrix skeleton

Pack `453ee842-7f35-5d77-b460-31d67e2784c2` sequence **7** (version `2026.8.11`) — 38 products, 104 rules.

Per OD-3: the real E2b gate is this matrix, not corpus size. **Arrest criterion**: no product classified
`REACHABLE_AND_SUPPORTED` may have a required claim topic with zero covering query, and once E2b execution
starts, no required claim may remain non-VERIFIED. All `coverage_state` below is `PENDING` — this is a
SKELETON: the fused bank exists and every product→topic cell has ≥1 candidate query_id, or the gap is
explicitly listed. Nothing has been asked of NB-2 yet.

## Result summary

- Reachable products: **27**, Blocked products: **11** (per QW-3 reachability report, static 27/11 split).
- Products with ≥1 required claim-topic uncovered by the fused bank: **0** (of which **0** are REACHABLE — this is the number that matters for the arrest criterion).

**No coverage holes on REACHABLE products** at the topic-skeleton granularity — every REACHABLE product's
required claim topics (derived from its rules' `required_facts`) have ≥1 candidate covering `query_id` in the
fused bank. One hole was found and closed during this PREP pass: E33G/T11 (`work.employer_is_indonesian_entity`)
had zero covering query until a dedicated T13 row was added (the fact's topic mapping was also corrected —
it is a compensation/employer-locus test, not a T11 RPTKA-administrative one — see `dedup-log.md`). This does
NOT mean the claims are VERIFIED — `coverage_state` is PENDING for all cells; candidate coverage ≠ answered ≠
audited.

## Full per-product matrix

`required_claim_topics` are derived from the union of (a) every rule (GLOBAL + PRODUCTS-scoped for this
product)'s `required_facts`, mapped to the T-code taxonomy used in `fused-bank.md`, plus (b) T1 (doctrine card)
as a baseline for every product regardless of rule facts.

| Product | Reachability | #rules | Required topics | Coverage (topic: n candidate queries) | Gaps |
|---|---|---:|---|---|---|
| A1 | REACHABLE | 8 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:6; T3:12; T5:2; T7:5; T9:6 | — |
| B1 | REACHABLE | 8 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:6; T3:12; T5:2; T7:4; T9:6 | — |
| BRIDGING | REACHABLE | 14 | T1,T10,T15,T3,T7,T8,T9 | T1:1; T10:2; T15:6; T3:12; T7:4; T8:3; T9:5 | — |
| C1 | REACHABLE | 7 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:7; T3:13; T5:4; T7:4; T9:5 | — |
| C2 | REACHABLE | 8 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:7; T3:16; T5:4; T7:5; T9:5 | — |
| C6 | REACHABLE | 7 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:7; T3:12; T5:4; T7:3; T9:5 | — |
| D1 | REACHABLE | 12 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:7; T3:14; T5:5; T7:4; T9:5 | — |
| D12 | REACHABLE | 13 | T1,T10,T15,T3,T4,T5,T7,T8,T9 | T1:2; T10:2; T15:7; T3:16; T4:2; T5:6; T7:5; T8:4; T9:5 | — |
| D2 | REACHABLE | 12 | T1,T10,T15,T3,T5,T7,T9 | T1:1; T10:2; T15:7; T3:16; T5:5; T7:6; T9:5 | — |
| E23 | REACHABLE | 8 | T1,T10,T11,T15,T3,T4,T6,T7,T9 | T1:1; T10:3; T11:7; T15:6; T3:13; T4:1; T6:1; T7:5; T9:5 | — |
| E23U | BLOCKED | 6 | T1,T10,T15,T7,T9 | T1:2; T10:3; T15:6; T7:5; T9:5 | — |
| E23V | BLOCKED | 6 | T1,T10,T15,T7,T9 | T1:2; T10:3; T15:6; T7:5; T9:5 | — |
| E28A | REACHABLE | 9 | T1,T10,T15,T3,T4,T7,T9 | T1:1; T10:2; T15:7; T3:12; T4:2; T7:4; T9:5 | — |
| E28B | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:1; T10:2; T15:7; T3:12; T7:4; T9:5 | — |
| E28C | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:1; T10:2; T15:7; T3:12; T7:5; T9:5 | — |
| E28D | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:1; T10:2; T15:7; T3:12; T7:4; T9:5 | — |
| E28F | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:1; T10:2; T15:7; T3:12; T7:4; T9:5 | — |
| E30 | REACHABLE | 9 | T1,T10,T12,T15,T3,T7,T9 | T1:1; T10:2; T12:2; T15:6; T3:13; T7:4; T9:5 | — |
| E30A | REACHABLE | 10 | T1,T10,T12,T15,T3,T7,T9 | T1:2; T10:2; T12:2; T15:6; T3:13; T7:4; T9:5 | — |
| E30B | REACHABLE | 11 | T1,T10,T12,T15,T3,T7,T9 | T1:2; T10:2; T12:2; T15:6; T3:13; T7:4; T9:5 | — |
| E30E | BLOCKED | 6 | T1,T10,T15,T7,T9 | T1:2; T10:2; T15:6; T7:4; T9:5 | — |
| E30F | BLOCKED | 6 | T1,T10,T15,T7,T9 | T1:2; T10:2; T15:6; T7:4; T9:5 | — |
| E31A | REACHABLE | 10 | T1,T10,T15,T3,T7,T8,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T8:9; T9:5 | — |
| E31B | REACHABLE | 8 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31C | REACHABLE | 8 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31D | REACHABLE | 9 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31E | REACHABLE | 10 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31F | REACHABLE | 8 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31G | REACHABLE | 7 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31H | REACHABLE | 8 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E31J | REACHABLE | 9 | T1,T10,T15,T3,T7,T9 | T1:1; T10:10; T15:6; T3:12; T7:4; T9:5 | — |
| E33 | REACHABLE | 11 | T1,T10,T14,T15,T3,T4,T7,T9 | T1:1; T10:2; T14:5; T15:7; T3:13; T4:3; T7:5; T9:5 | — |
| E33A | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:2; T10:2; T15:7; T3:13; T7:5; T9:5 | — |
| E33B | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:2; T10:2; T15:7; T3:13; T7:6; T9:5 | — |
| E33C | BLOCKED | 7 | T1,T10,T15,T3,T7,T9 | T1:2; T10:2; T15:7; T3:13; T7:5; T9:5 | — |
| E33E | REACHABLE | 10 | T1,T10,T14,T15,T3,T4,T7,T9 | T1:2; T10:2; T14:6; T15:7; T3:13; T4:4; T7:5; T9:5 | — |
| E33F | REACHABLE | 9 | T1,T10,T14,T15,T3,T4,T7,T9 | T1:2; T10:2; T14:5; T15:7; T3:13; T4:3; T7:5; T9:5 | — |
| E33G | REACHABLE | 12 | T1,T10,T13,T15,T3,T4,T6,T7,T9 | T1:2; T10:2; T13:6; T15:7; T3:13; T4:4; T6:2; T7:5; T9:5 | — |

Full per-topic query_id lists: see `coverage-matrix.json` (machine-readable, same data, includes
`required_facts` verbatim and the covering `query_id` lists per topic per product).

## Adversarial review

Cross-family review dispatched to Kimi K3 (`kimi-code/k3`), 2026-08-17 — see `dedup-log.md` §Kimi refuter
disposition. Kimi's review did not have this matrix's full topic set in its context (only T2/T7/T8 extracts);
its 3 flagged "coverage gaps" were checked against the full matrix here and found already covered — logged
as false alarms, not blind trust in either direction.
