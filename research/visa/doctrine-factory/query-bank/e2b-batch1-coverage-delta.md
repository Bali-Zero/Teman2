---
date: 2026-08-17
domain: visa
client_case: none
sources:
  - path: research/visa/doctrine-factory/query-bank/coverage-matrix-after-batch1.json
    note: "machine-generated delta this report summarizes"
  - path: research/visa/doctrine-factory/claims/e2b-batch1-claim-ledger.md
  - path: research/visa/doctrine-factory/claims/e2b-batch1-conflict-report.md
adversarial_review: kimi-k3
---

# E2b batch-1 coverage-matrix delta

## Adversarial review

Covered by the joint Kimi K3 pass over the batch (see the claim ledger's `## Adversarial review` for
the full account — killed at the 8-minute timebox before a verdict, no findings against this file
specifically). This delta file is a mechanical derivation of `coverage-matrix-after-batch1.json` — its
correctness was self-verified by re-running the same script's tally logic in this turn against the
raw `e2b-batch1-run-summary.json`/response-log rather than relying on a separate adversarial pass.

## Method

`coverage-matrix-after-batch1.json` is a copy of the skeleton `coverage-matrix.json` (NOT an
overwrite) with two additions per product: `batch1_topic_states` (per-topic:
`ANSWER_OBTAINED` if >=1 candidate query for that topic returned an `OK` NB-2 answer in batch-1,
else `STILL_PENDING`) and `batch1_coverage_state` (`ALL_TOPICS_ANSWERED` /
`PARTIAL_N_of_M` / `NO_CHANGE`).

**This is a topic-REACHABILITY delta, not a claim-QUALITY delta.** `ANSWER_OBTAINED` means a
compilable NB-2 answer exists — it does not mean the resulting claim in
`e2b-batch1-claim-ledger.md` is a clean `VERIFIED`. Several products with `ALL_TOPICS_ANSWERED`
still carry `VERIFIED-WITH-CAVEAT` claims, self-flagged `UNVERIFIED` gaps, or open numeric
conflicts (see conflict report CF-7/CF-8/CF-9/CF-10/CF-12). Read the matrix delta and the claim
ledger together — neither alone tells the whole story.

## Products moved to ALL_TOPICS_ANSWERED this batch (11)

`E23U`, `E23V`, `E28A`, `E30A`, `E33`, `E33A`, `E33B`, `E33C`, `E33E`, `E33F`, `E33G`

Every coverage-matrix topic for these 11 products now has >=1 compilable batch-1 answer behind
it. Notable: `E33A`/`E33B`/`E33C` (BLOCKED reachability) and `E23U`/`E23V` (BLOCKED) reached full
topic-answer coverage purely as a side-effect of this batch's 6 cross-cutting "ALL"-scoped
queries (T3 activity-boundary, T7 sponsor, T9 nationality, T10 family-minors/age, T15 overstay
risk) — we never queried them directly, but a single "ALL products" query satisfies the same
topic requirement across every product it's scoped to. This is the batch-1 selection rationale's
predicted leverage effect, confirmed empirically.

**Caveat on "ALL_TOPICS_ANSWERED":** for `E33`/`E33E`/`E33F` specifically, "answered" includes
claims that ended up `CONFLICTING` (CF-7 age 55-vs-60, CF-8 KITAP-conversion 3y-vs-5y) — these
products have MORE material to work with than before, not fewer open questions. Do not read
`ALL_TOPICS_ANSWERED` as "ready to compile clean."

## Products with partial movement (27)

Every REACHABLE product this batch touched gained partial topic coverage via the same
cross-cutting leverage — typically T3/T7/T9/T10/T15 answered, T1 (product-specific doctrine
card) still pending where that card timed out (`BRIDGING`, `E30B`, `E31J`, and — despite a
successful E33E-adjacent doctrine card for the family — the standalone `E33E`/`E31E` full-card
asks that timed out are noted as gaps in the claim ledger even though this delta shows E33E as
fully answered via indirect backfill).

Full per-product breakdown (`N_of_M` topics answered): `A1` 5/7, `B1` 5/7, `BRIDGING` 5/7 (note:
the claim ledger flags BRIDGING as a "TOTAL GAP" for its OWN doctrine-card content — the matrix's
5/7 here reflects the cross-cutting facts (sponsor/nationality/risk/age/activity-boundary) that
apply to BRIDGING generically, not BRIDGING-specific doctrine; the two lenses measure different
things and both are correct), `C1` 5/7, `C2` 5/7, `C6` 5/7, `D1` 5/7, `D12` 6/9, `D2` 5/7, `E23`
8/9, `E28B` 5/6, `E28C` 5/6, `E28D` 5/6, `E28F` 5/6, `E30` 6/7, `E30B` 6/7, `E30E` 4/5, `E30F`
4/5, `E31A` 6/7, `E31B` 5/6, `E31C` 5/6, `E31D` 5/6, `E31E` 5/6, `E31F` 5/6, `E31G` 5/6, `E31H`
5/6, `E31J` 5/6.

(`D1`/`D2`/`D12`/`E31B`/`E31D` were already substantively covered by E2a's own dedicated
querying — this batch's partial touch on them is incidental cross-cutting spillover, not new
targeted work; do not double-count against the "batch-1 selected 40 non-E2a-slice queries" claim.)

## Products with NO_CHANGE (0)

None — every one of the matrix's 38 products received at least partial topic-answer coverage
this batch, entirely via the 6 cross-cutting queries' broad scope.

## What batch 2 should prioritize

1. Retry the 6 timed-out doctrine cards (`BRIDGING`, `E30B`, `E33E`, `E31E`, `E31J`, `E30`) —
   BRIDGING and E31J remain the two genuine content gaps (no narrower backfill found anywhere in
   this batch).
2. Resolve or escalate CF-7 (E33E age 55/60) and CF-8 (E33/E33E KITAP conversion 3y/5y) before
   any RulePack HARD_FILTER references those figures.
3. The BLOCKED-reachability products (`E28B`-`E28F`, `E23U`/`E23V`, `E30E`/`E30F`, `E33A`-`E33C`)
   now have decent cross-cutting topic coverage but zero product-specific doctrine-card content —
   worth a batch-2 pass if/when their BLOCKED status is revisited.
