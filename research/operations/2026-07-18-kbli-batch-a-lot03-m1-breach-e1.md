---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — LANE-E1 control-limit breach)
adversarial_review: codex
adversarial_review_detail: "superseded 2026-07-18: conductor D6 gate COMPLETE — codex 3 refuter passes + full-report red-team (gpt-5.6-sol xhigh) + glm-5.2 blind second extractor; see 2026-07-18-kbli-batch-a-lot1-conductor-gate.md (PR #2721). Original: none (D5 blind refutation is the trigger; conductor resume pending)"
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§5 pause/resume)"
  - "calibration: data/kbli-filiera/batch-reports/batchA-calibration.md (m1 floor 0.75, SIGNED f5892d39)"
  - "dossiers: data/kbli-filiera/dossiers/{05102,05200}.jsonl"
---

# GARUDA-FILIERA Batch A — LANE-E1 m1 CONTROL-LIMIT BREACH (lot 03, div 05)

> **The lane is PAUSED at the lot-03 boundary** per calibration §5. Resume requires a
> conductor-signed note in the plan §8 citing the breached metric + root cause. This lane does
> NOT self-resume (no silent resume). This report is the durable trigger for that conductor review.

## The breach

| Lot | Codes | m1 blind-concordance | Floor | Status |
| --- | --- | --- | --- | --- |
| 03 (div 05) | 05102, 05200 | **1/2 = 0.50** | 0.75 | **BREACH** |

- **05200** (Pertambangan Lignit): ONE_TO_ONE, D5 concordant (refuted=false) — CERTIFIED CLEAN.
- **05102** (Benefisiasi atau Peningkatan Kualitas Batu Bara / coal beneficiation): **D5 REFUTED (divergence)**.

## Root cause — a genuine D5 catch, not seat drift (conductor adjudicates)

D1 proposed the SPLIT mapping `05100 → {05101, 05102}` (correct, image-verified bidirectionally) BUT
also set `licensing_inherits=true`, `needs_quarantine=false`, `confidence=high` — while its own free-text
notes voiced doubt that the mining row genuinely applies to beneficiation.

The **D5 blind refuter independently re-derived** and REFUTED the licensing half: the sole PP28 evidence
(Lampiran I.D p.202 row 24, Kode 05100) is a mining-**CONCESSION** regime — IUP Tahap Eksplorasi, WIUP
coal-auction compensation, Neraca Sumber Daya dan Cadangan, post-mining reclamation — which is a
**substantive mismatch** to 05102's explicitly non-mining scope (its uraian excludes mining and requires
beneficiation be done *"secara terpisah dari proses pertambangan batu bara"*). The canonical copied the
05100 mining-concession row wholesale onto 05102. Same disease family as the pilot's false-friends: a
KBLI-2020 licensing regime inheriting onto a 2025 code whose activity does not match.

This is **the generator≠grader design working** — D1 over-certified, D5 caught it. The m1 metric fell
because the seats genuinely disagreed on one of two codes; on a 2-code lot a single (correct) refutation
mechanically trips the 0.75 floor. Whether to treat this as "correct-catch, resume" vs "systematic drift,
root-cause pass" is the **conductor's call** (calibration §5) — the lane surfaces, does not decide.

## Cumulative lane state (lots 01-03, 7 codes)

| Lot | Div | Codes | Clean | Quarantine (proposed) | m1 |
| --- | --- | --- | --- | --- | --- |
| 01 | 01 | 01287, 01700 | 01287 | 01700 (6-way MERGE) | 1.00 |
| 02 | 02 | 02201, 02402, 02409 | 02201, 02402 | 02409 (SPLIT/MERGE) | 1.00 |
| 03 | 05 | 05102, 05200 | 05200 | **05102 (D5-refuted mining-licensing mismatch)** | **0.50 ✗** |

- m2 certification rate cumulative: 4 clean / 7 = 0.57 (in [0.20, 0.85]).
- m3: refutation categories seen — merge-aggregation, split-many-to-many, and now
  **illegitimate_inheritance** (05102, in the closed registry). No out-of-registry category → no m3 trip.
- m4 tokens/code: ~197k (within 400k ceiling).
- Quarantines (3): 01700, 02409, 05102 — all PROPOSED to the conductor, none adjudicated; canonical untouched.

## What the conductor owns now (lane blocked on these)

1. **m1-breach adjudication + signed resume** in plan §8 (root cause: correct-catch vs drift). No lot 04
   until signed.
2. **05102 quarantine** — likely honest-gap cure (05102 needs its own beneficiation-scoped licensing or an
   honest "no PP28 row covers this activity"), not the inherited 05100 mining regime.
3. Standing: 01700 + 02409 quarantines; the canonical pin W88 (`45bbc1f4` unreachable from main).

## Deliverables this checkpoint

7 hash-chained dossiers (D0→D1→D5→D4) in `data/kbli-filiera/dossiers/` on PR #2695; all chains verified;
compiler-mediated writes only; leases acquired/released per code.
