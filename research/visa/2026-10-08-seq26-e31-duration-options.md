---
date: 2026-10-08
domain: visa
client_case: none — rule pack change, no client data
sources:
  - research/visa/2026-10-07-freshness-restamp-seq25/text/ (saved visible text of the nine E31 portal pages)
  - apps/backend-rag/backend/data/bali_zero_official_prices_2026.json (kitas_permits rows, Spouse and Dependent, 1 and 2 years)
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-025.{source,signed}.json (the anchor)
  - apps/backend-rag/backend/services/visa_engine/contracts/packs/rulepack-prod-026.source.json
  - apps/backend-rag/backend/scripts/visa_engine/derive_seq26_e31_options.py
adversarial_review: codex
---

# seq-26 — the E31 family ITAS is a 1- or 2-year duration option

## Ruling

Zero, 2026-10-08: the family ITAS products E31A to E31J offer a stay of one or two years
on the same product. The two-year length is a duration option of that product, priced
all-inclusive from the official 2026 catalogue. No government fee figure appears in client
text and no price is "on request".

## What changes

seq-26 is the signed seq-25 (payload digest `603f777e…9d11`, `# pragma: allowlist secret`)
plus `duration_options` on nine products. Nothing else moves: the rules, the source records
and the eighteen portal stamps are byte-identical, so the freshness boundary stays
2026-11-08T13:32:18Z. The identity fields move as in every fold: sequence 26, a uuid5
`rule_pack_id`, version `2026.10.8`, `previous_payload_sha256` set to the seq-25 digest.

Each option list is `[365 days on the product's existing 1-year key, 730 days on the same
variant's "2 Years" key]`. The product's own `pricing_key` stays the first option, and its
stay policy is FIXED_DAYS from 365 to 730. E31A already said 365 to 730 with a 1-year key,
so its 730 days showed the 1-year price. The options cure that.

## Per product: the page and the catalogue

Every page sentence is `Anda dapat memilih untuk tinggal di Indonesia selama 1 tahun atau 2
tahun dihitung sejak tanggal kedatangan`, found verbatim in the saved text. The derivation
refuses a product whose saved page does not carry it, and refuses a missing catalogue sibling.

| Product | Saved page text | 1-year key | 2-year key |
|---|---|---|---|
| E31A | `…/text/950a9f63.txt` | Spouse 1 Year (Offshore) | Spouse 2 Years (Offshore) |
| E31B | `…/text/570f2bc4.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31C | `…/text/40523028.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31D | `…/text/50457cd0.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31E | `…/text/ecd22722.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31F | `…/text/f9306203.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31G | `…/text/86880290.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31H | `…/text/153beca1.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |
| E31J | `…/text/2d090f3a.txt` | Dependent 1 Year (Offshore) | Dependent 2 Years (Offshore) |

The text paths are under `research/visa/2026-10-07-freshness-restamp-seq25/`. No E31 product
is left without an option.

Catalogue rows (IDR, all-inclusive): Spouse and Dependent, 1 year, Offshore 11.000.000;
2 years, Offshore 15.000.000. The pack models only the Offshore variant, as before. The
Onshore (Altus) 13.500.000 and 18.000.000 rows and the Extend 9.000.000 and 15.000.000
rows exist in the catalogue and are not modelled in the pack.

## How the engine uses it

The evaluator reads `intent.stay_days` (in days) and takes the smallest option that covers
it. 365 gives 11.000.000, 366 to 730 give 15.000.000, and a longer wish still gets the 730
option with `extension_required` true, because the permit is extendable. An unknown stay
gets the first option.

## Findings worth keeping

- The 2026-08-30 pack already omitted the two-year option; the 2026-10-07 reader verdicts
  named it "changed" and the orchestrator dispositioned it as a modelling gap, not stale
  stamps. seq-26 closes that gap.
- A re-stamped candidate pack is graded after its newest portal read, not only after its
  newest rule. Without that the walk census holds every walk, because the sources look
  not yet verified. The census helper now does both.
- The twenty canonical gold personas are pinned by spec and replay the highest signed pack.
  Personas 6 and 7 (the E31 child and spouse walks) are run on the unsigned seq-26 in
  `test_seq26_pack.py` with 12, 24 and 36 months. The pinned corpus is unchanged.

## What this does not do

It does not sign or activate seq-26. The public screens must still learn to show both
durations: `schema.d.ts` carries the fields, `visa-oracle-contract.ts` and the pages do not.

## Adversarial review

(To be filled after the review of the candidate.)
