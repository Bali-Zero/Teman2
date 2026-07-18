---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 3 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE 2026-07-19: full-report red-team (gpt-5.6-sol xhigh, read-only) on the FIRST signing returned FIX-FIRST — 1 BLOCKER (lease-gate SKIPPED undeclared → cured by full disclosure + infra item) + 4 MAJOR (census double-count → 4/5/2/1/1; §3 concordance misread → 4 codes are divergence-rule quarantines; m1 masking → runner breach 0.462 declared, tautological 13/13 withdrawn; m4 mixed numerator → 212,095 avg / 272,805 max) + 2 MINOR (double-blind wording; 64940 delivery receipt) — all cured in this second signing. The by-eye claims, verdicts, controls 2/2, m2, and 64220 retro-category all VERIFIED by the red-team against raw."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§3 divergence rule, §5, §8 A-2/A-4/A-5/A-6)"
  - "calibration v2: data/kbli-filiera/batch-reports/batchA-calibration-v2.json (re-emitted post-Lot-2, census 87/1/133)"
  - "runner: infra/workflows/kbli-batch-a-lot.js @ v2 categories, run wf_c00a9ec4-c61 (29 seats, 0 errors)"
  - "prior gate: research/operations/2026-07-18-kbli-batch-a-lot2-conductor-gate.md (#2753, second signing + Appendix A)"
---

# GARUDA-FILIERA Batch A — Lot 3 (A-L3) conductor gate

> Conductor D6 adjudication of the third Batch-A lot: 13 in-scope codes (divisions 60→64:
> 60101, 60103, 60201, 60203, 60311, 61905, 61909, 64110, 64220, 64320, 64330, 64920,
> 64940) + 2 innocence controls (59140, 59201). FIRST lot run with the amended
> control protocol: both controls were pre-verified by the conductor BY EYE on BOTH
> crosswalk directions before enrollment (Lampiran 5 p.198 + Lampiran 10 p.395: single
> rows, identical titles), after the first two candidates (61101, 61102) were REJECTED at
> pre-verification — the reverse table revealed both as 3-parent merges.

## 1. Outcome

**13/13 in-scope QUARANTINED, 0 certified. Both innocence controls CERTIFIED (2/2
true-clean)** — the Lot-2 lesson (3 contaminated controls) is answered: pre-verified
controls behave, and the lane manufactured no spurious work on them.

Final category census (CORRECTED at second signing — red-team MAJOR: the first census
double-counted 60201 and was non-exclusive; this is the runner's final assignment,
4/5/2/1/1 = 13 exactly):

| Category | Codes |
| --- | --- |
| mapping_metadata_false (4) | 60101, 61905, 64920, 64940 |
| source_absent_in_vault (5) | 60201, 60311, 64110, 64320, 64330 |
| illegitimate_inheritance (2) | 60103, 60203 |
| payload_cross_contamination (1) | 61909 |
| unresolvable_source_pointer (1) | 64220 |

(60201's D1 seat ALSO found mapping_metadata_false — recorded as a secondary dossier
note, not a census entry.) All five seen categories are in the v2 closed registry
(m3 ✅, zero out-of-registry).

**Lease disclosure (red-team BLOCKER, cured by declaration):** the runner logged
`LEASE-GUARD SKIPPED` on all 15 dossiers — per-code Redis leases were NOT acquired by
the caller. This is the standing state of ALL THREE lots (the Redis lease registry is
unreachable from sessions — `NOAUTH`, infrastructure finding recorded in memory
2026-07-18), not a Lot-3 regression. Isolation was ensured by other means: the lane
reads a conductor-private evidence root, the data-plane guard blocks any non-compiler
canonical write, the lane performs ZERO canonical writes by design, and exactly one
lane was live. Residual risk (a concurrent lane on the same codes) was nil this run;
fixing the lease registry (REDIS_PASSWORD in session env or a Postgres-backed
registry) stays an open infra item — first governance PR that touches the runner
should downgrade SKIP-with-WARN to fail-closed once the registry is reachable.

## 2. Conductor spot verification (by-eye, this session)

- **64940** (the flagship wrong-parent case): reverse table Lampiran 10 printed p.399
  (render `lampiran10_p413-413.png`) read BY EYE: **64940-2025 "Aktivitas Sekuritisasi" ←
  64992-2020 "Perusahaan Pembiayaan Sekunder Perumahan"**, single row. Canonical
  `kbli_2020_source/pp28_sources="53201"` (a courier code) is FALSE — same wrong-parent
  class as 10433. Implication verified by the seat and accepted: the PP28 ABSENT verdict
  hunted the WRONG code (53201); a D2 re-hunt under 64992 is scheduled with the cure.
- **60103 / 60203 (prior independent conductor reading, now lane-confirmed)**: during
  control vetting the conductor had already read Lampiran 10 p.395 by eye: 60103 ←
  {60101, 60102} and 60203 ← {60201, 60202} — 2-parent merges under the
  government/private → analog/digital/on-demand axis re-organization. The lane's
  verdicts are consistent with that prior reading. (Wording note per red-team: this is
  a prior independent reading, not "double-blind"; and the p.395 merge evidence grounds
  the MERGE fact — the illegitimate_inheritance CATEGORY additionally rests on the
  seats' PP28/licensing evidence in the dossiers.)
- **60101 split**: D1+D5 agree (forward p.212 shows 60101-2020 fanning to {60101,
  60103}-2025); consistent with the same p.395 reading above.
- Remaining quarantines: rationales reviewed; all image-grounded bidirectional reads;
  risk-proportional depth applies (all verdicts are fail-safe quarantines; no CLEAN
  in-scope verdict exists to demand the heavier cross-family certification gate).

## 3. Adjudications

1. **60201 (D1 mapping_metadata_false vs D5 source_absent_in_vault)**: conductor rules
   **source_absent_in_vault primary** (the PP28 pointer failure is the harm blocking any
   licensing basis; the metadata finding is concomitant and recorded).
2. **64320 (same split)**: same ruling, source_absent_in_vault primary.
3. **Seat-disagreement structure (REWRITTEN at second signing — red-team MAJOR; the
   first signing's "divergent-category, concordant verdict" misread the runner data):**
   - **60103, 60311, 64110, 64330 — D1 CLEAN vs D5 PROBLEM**: the seats' verdicts
     genuinely disagree; all four are quarantined by the plan §3 preregistered
     divergence rule ("Divergence → QUARANTINE, never averaged or picked") with the
     blind image-grounded D5's category. Same rule that flipped 19206 (Lot 1) and
     52299 (Lot 2).
   - **60203 — both seats flag, categories differ** (D1 mapping_metadata_false vs D5
     illegitimate_inheritance): quarantined with D5's category, D1's recorded.
   - **61905, 61909 — both seats flag, same category**: plain concordant quarantines.
   Runner telemetry: full-tuple concordance 6/13 = 0.462; problem-bit agreement 9/13 =
   0.692.
4. **64220 (both seats no-category, runner retro-category)**: quarantined
   unresolvable_source_pointer per the #2731 retro-demote rule — the D2 self-confirmation
   path could not ground the pointer.
5. **64940 direct-delivery disclosure**: the D1 finding was ALSO delivered directly to
   the conductor mid-lane (same chain-of-custody class as Lot 2 §7; the in-workflow
   result matches the direct message on category and content — mapping_metadata_false,
   64992 true parent). Receipt: the direct message is preserved verbatim in the S2
   session transcript (session 680a67f6, 2026-07-19 ~00:30 WITA); the journal contains
   only in-workflow results by design, so the transcript is the sole delivery record —
   declared as such, per red-team MINOR.

## 4. Class findings (program-level)

- **The metadata disease dominates division 64 (finance)**: wrong-parent pointers
  (64940→53201-courier), stale MATCH_LANGSUNG on re-axed families (radio/TV
  government/private → analog/digital/on-demand). The 2025 restructure of the finance
  and broadcasting divisions is systematically undercounted in canonical metadata.
- **Control protocol validated**: pre-verify on BOTH directions → 2/2 clean controls
  (vs 0/2 in Lot 2). The v3 registry rule ("POS controls pre-verified on both crosswalk
  directions before salting") is hereby the standing protocol.

## 5. Calibration (v2 limits, run wf_c00a9ec4-c61)

| # | Metric | Lot 3 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-FAMILY blind concordance | NOT MEASURED in-lane (all seats Sonnet). The runner's SAME-FAMILY full-tuple reading is **0.462, a DECLARED runner-level breach** (recorded, not masked); problem-bit agreement 9/13 = 0.692. The first signing's "verdict-level 13/13 = 1.00" was tautological (it compared conductor verdicts to themselves) and is WITHDRAWN. | ≥0.75 | ❌ runner-proxy breach DECLARED · true cross-family reading ⏸ pending (§6) |
| m2 | certification rate | **0.000** (0/13) | [0.20, 0.85] | ❌ BREACH (declared; same object-level adjudication as Lots 1-2 — the disease band is real, pausing rewards it) |
| m3 | category registry | 5 seen, all in closed-7 | closed list | ✅ (mismatches adjudicated §3) |
| m4 | tokens/dossier | **avg 212,095** (2,757,234 / 13 in-scope, controls excluded from numerator AND denominator) · **max 272,805 (64220)** | ≤400k per dossier | ✅ (max under ceiling; first signing's 231k avg used a mixed numerator — corrected) |
| m5 | gold-set hit rate | NOT run in-lane (digest-blind by design) | ==1.00 | ⏸ cross-family pass pending (§6) |

## 6. Open before the Lot 3 cure ships

1. **Cross-family pass (m1 + m5)**: GLM-vision blind, sample of lot codes + gold
   controls, per the Lot 2 Appendix-A method. NOTE: the v2-lot2 POS plaintexts were
   REVEALED at Lot 2 (burn recorded); the v3 registry re-salt (POS "v2-lot3" or v3) must
   ship in the next governance PR before the m5 POS leg can run un-burned; NEG controls
   (21 cured, now 26+13 post-Lot-2... recompute at re-salt) unaffected for a spot NEG leg.
2. **Cure spec** `batch_a_lot3.json`: 13/13 detach (per_skala → [], preserve block,
   F12 notes); metadata corrections for the wrong-parent/mis-axed cases (64940 →
   kbli_2020_source 64992; 60101/60103/60201/60203 re-axed mappings) recorded as
   crosswalk ancestors, never as PP28 sources.
3. **Surfaces**: Lot 1/2 consumer-map (KG detach — licensing_status in-script — Qdrant
   clear, cache bust, prove-live).
4. **D2 re-hunt** under 64992 for 64940 (wrong code was hunted) — outcome feeds a
   possible future restore, never an in-gate fill.

## Appendix A — cross-family conductor pass (m1 + m5-NEG), adjudicated

Executed post-second-signing per §6.1: blind GLM-vision pass, 8 codes sha256-shuffled
(seat never told the class): 5 lot codes (m1) + 3 NEG spot controls from the Lot 1+2
cured set (49296, 47771, 05102). POS leg deliberately NOT run (v2-lot2 plaintexts were
revealed at Lot 2 — burn recorded; the v3 re-salt ships in the next governance PR).
Raw outputs + full report: `/tmp/kbli-conductor-a1-0718/lot3-conductor-crossfamily-report.md`.

**m1 (true cross-family): 5/5 = 1.00 ✅** (floor 0.75). All five (60101, 60203, 61909,
64330, 64940) blind-concur with the lane's quarantine verdicts, and the GLM's free-text
rationales name the SAME disease as the lane's structured category on all five —
including independently re-deriving 64940's true ancestor 64992 vs the declared courier
code 53201, and 60203's "a standalone VOD streamer would not hold a broadcast
concession" (verbatim illegitimate-inheritance shape). The runner's same-family 0.462
stays declared lane telemetry; the registry-valid m1 is 1.00, NO breach.

**m5-NEG: 3/3 HIT ✅** — each seat, fed the PRE-detach evidence snapshot, independently
re-derived the original defect that justified the detach (49296 railway payload; 47771
4-parent merge vs MATCH_LANGSUNG; 05102 mining-concession regime excluded by the code's
own scope). Explicitly checked for the 49213 completion-path pattern on all three: none
found — no partial-restore candidates, all three honest-gaps re-affirmed.

**Sign-off conditions update:** condition (1) of the second signing is MET (m1 1.00,
m5-NEG 3/3 adjudicated here). Lot 4 remains gated on (2) the Lot 3 cure shipping and
(3) the v3 registry re-salt. — Conductor, 2026-07-19.

## Adversarial review

Seat: **codex** — scheduled on this SIGNED report per the W100 protocol:
`codex exec -m gpt-5.6-sol -c model_reasoning_effort="xhigh" --sandbox read-only` over
this file + the raw lot output (`wfnxi51et.output`) + journal (`wf_c00a9ec4-c61`) +
canonical + renders. Findings appended and cured before the cure PR ships.

## Sign-off

**Lot 3 conductor gate: SIGNED — SECOND SIGNING, post-red-team** (the first signing was
FIX-FIRSTed: 1 BLOCKER + 4 MAJOR + 2 MINOR, all cured above; the red-team also VERIFIED
the load-bearing substance — 13/13 quarantine, 2/2 controls true-clean, all §2 by-eye
claims, m2, and the 64220 retro-category — so the outcome stands while the audit trail
is now honest). **Lot 4 is authorized ONLY after: (1) cross-family m1/m5 adjudicated in
an appendix to this report, (2) the Lot 3 cure shipped, (3) the v3 registry re-salt
shipped.** — Conductor (Fable, MANDATO S2), 2026-07-19.
