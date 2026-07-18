---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — LANE-E1 Lot 1 completion)
adversarial_review: codex
adversarial_review_detail: "superseded 2026-07-18: conductor D6 gate COMPLETE — codex 3 refuter passes + full-report red-team (gpt-5.6-sol xhigh) + glm-5.2 blind second extractor; see 2026-07-18-kbli-batch-a-lot1-conductor-gate.md (PR #2721). Original: none (D5 blind refutation in-pipeline; conductor D6 gate pending)"
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§8 A-2 lot-shape rule)"
  - "calibration: data/kbli-filiera/batch-reports/batchA-calibration.md (m1-m5, SIGNED f5892d39)"
  - "dossiers: data/kbli-filiera/dossiers/*.jsonl (13 codes)"
---

# GARUDA-FILIERA Batch A — LANE-E1 Lot 1 COMPLETE (div 01→39, 13 codes)

> Lot 1 as redefined by conductor §8 A-2 (a lot = contiguous taxonomy segment ≥10 codes). Lane E1
> owns D0-D4; this is the lane's complete measured output for Lot 1. Ready for the conductor's D6
> gate + gold-set/mutation injection. Quarantines PROPOSED, never adjudicated; canonical untouched.

## Result (13 codes)

| Code | D1 mapping | Outcome | Note |
| --- | --- | --- | --- |
| 01287 | ONE_TO_ONE | CLEAN | narcotic plants; licensing OSS-2025-native |
| 01700 | MERGE 6→1 | QUARANTINE | 01711..01719 hunting consolidation; aggregate ≠ single-inherit |
| 02201 | ONE_TO_ONE | CLEAN | logging (Pemanenan Kayu) |
| 02402 | ONE_TO_ONE (ex-02401) | CLEAN | disambiguated the cross-edition 02402 numeral collision |
| 02409 | SPLIT/MERGE | QUARANTINE | many-to-many crosswalk |
| 05102 | SPLIT | QUARANTINE | **D5-refuted**: mining-concession licensing wrongly on coal-beneficiation |
| 05200 | ONE_TO_ONE | CLEAN | lignite mining |
| 08920 | ONE_TO_ONE | CLEAN | peat; title "Gemuk"→"Gambut" = terminology fix, not scope change |
| 19206 | SPLIT (19291→3) | CLEAN | petroleum-biofuel blending; **D2 image-verified** |
| 36003 | ONE_TO_ONE | CLEAN | — |
| 38122 | SPLIT (38120→2) | QUARANTINE | D1-flagged split |
| 38222 | SPLIT (38220→1) | CLEAN | **D2 image-verified** |
| 39001 | SPLIT (39000→1) | QUARANTINE | D1-flagged |

**8 CLEAN · 5 quarantine proposed (01700, 02409, 05102, 38122, 39001).**

## Calibration metrics over the full 13-code lot (the correct sampling unit per A-2)

| # | Metric | Lot 1 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | extractor/refuter blind-concordance | **12/13 = 0.923** | floor 0.75 | ✅ |
| m2 | certification rate (clean/adjudicated) | **8/13 = 0.615** | [0.20, 0.85] | ✅ |
| m3 | refutation categories | illegitimate_inheritance, merge-aggregation, split-many-to-many (all in-registry) | closed list | ✅ |
| m4 | tokens/code | ~208k | ceiling 400k | ✅ |
| m5 | gold-set hit rate | n/a (conductor-injected) | 1.00 | — |

The single D5 refutation (05102) is the generator≠grader design working — a real catch, not seat
drift. Under A-2's ≥10-code lot it lands at 0.923, well above floor; the earlier per-division "breach"
was exactly the small-sample artifact A-2 corrected.

## Notable catches (conductor review)

- **05102** (coal beneficiation): D1 over-certified `licensing_inherits=true`; D5 blind-refuted — the
  declared PP28 row [05100] is a mining-concession regime (IUP eksplorasi / WIUP auction / Neraca
  Cadangan) that does not apply to non-mining beneficiation. Same disease family as the pilot's
  false-friends. Honest-gap cure likely.
- **01700 / 02409 / 38122 / 39001**: SPLIT/MERGE crosswalks where licensing cannot cleanly single-inherit.
- **02402 / 08920**: examples of the pipeline NOT over-firing — a cross-edition numeral collision (02402)
  and a title terminology fix (08920) both correctly resolved to CLEAN via uraian, not title.

## Deliverables

13 hash-chained dossiers (D0→D1→D5→[D2]→D4) in `data/kbli-filiera/dossiers/` on PR #2695; all chains
verified; compiler-mediated writes only; leases per code; grounded on pinned canonical `45bbc1f4`
(blob 3cfe8134d) + manifest `e7d25a37` + membership `aa0a0a69`.

## Open for the conductor

1. **D6 gate + gold-set/mutation** on Lot 1 (conductor's calibration injections).
2. **5 quarantines** — honest-gap cures (canonical writes are the conductor's at emit).
3. **Canonical pin W88** (`45bbc1f4` unreachable from main) — re-pin before emit.
4. **Next**: Lot 2 = next contiguous ≥10-code segment (div 42→64 region). Lane ready on gate/go.
