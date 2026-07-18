---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 2 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE 2026-07-18: full-report red-team (gpt-5.6-sol xhigh, read-only) on the FIRST-SIGNED report returned FIX-FIRST — 4 BLOCKER + 2 MAJOR + 1 MINOR, ALL verified against raw evidence and cured in this second signing (46100 retro-quarantined after conductor image-verify of Lampiran 10 p.356; m1 re-labeled NOT-MEASURED same-family proxy; 52101 disposition corrected to 5-parent MERGE after conductor image-verify of Lampiran 10 p.389; 47771 cure upgraded to detach+metadata). W100 protocol held: the signature lied until red-teamed, again."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§3 divergence rule, §5 calibration, §8 A-2/A-4/A-5/A-6)"
  - "calibration v2: data/kbli-filiera/batch-reports/batchA-calibration-v2.json (PR #2740)"
  - "runner: infra/workflows/kbli-batch-a-lot.js @ v2 categories (PR #2741), run wf_ec5c5f93-64b"
  - "lot output: 28 seats, 0 errors, journal wf_ec5c5f93-64b/journal.jsonl"
---

# GARUDA-FILIERA Batch A — Lot 2 (A-L2) conductor gate

> Conductor D6 adjudication of the second Batch-A lot: 13 in-scope codes (divisions 42→59:
> 42999, 47771, 49233, 49296, 50113, 52103, 52105, 52211, 52219, 52232, 52239, 52299, 59131)
> + 2 innocence controls (46100, 52101), run under the v2 calibration registry and the v2
> runner category set. Lane = `kbli-batch-a-lot.js` (Sonnet seats, extractor≠refuter per code,
> image-grounded D5 blind). Verdicts below are the CONDUCTOR's; the lane proposes only.

## 1. Outcome

**13/13 in-scope codes QUARANTINED, 0 certified.** The innocence-control pair outcome
(REVISED at second signing): **BOTH controls turned out contaminated on the
crosswalk-metadata layer** — neither provides the clean-pipeline innocence signal the
design intended. 52101 was lane-quarantined with a TRUE finding (see §4). 46100 was
lane-certified AND initially conductor-countersigned as "true-clean", but the red-team
refuted it and the conductor then image-verified Lampiran 10 p.356 (render
`lampiran10_p370-370.png`) BY EYE: **46100-2025 ← {46100, 63122} (2020)** — "Portal Web
Dan/Atau Platform Digital Dengan Tujuan Komersial" merges in, so canonical
`status_mapping="MATCH_LANGSUNG"` is a merge-undercount. The conductor RETRO-QUARANTINES
46100 (`mapping_metadata_false`, metadata-fix class, standalone cure like 52101 — its
OSS-native per_skala stays untouched). The lane's forward-table-only certified verdict AND
the conductor's first receipt-level countersign both missed the reverse table: recorded as
a protocol lesson (§4). The innocence-control design needs crosswalk-verified controls for
future lots.

Category census (lane-proposed, conductor-adjudicated):

| Category | Codes |
| --- | --- |
| payload_cross_contamination (8) | 49296, 52103, 52105, 52211, 52219, 52232, 52239, 52299 |
| source_absent_in_vault (4) | 42999, 49233, 50113, 59131 |
| mapping_metadata_false (1) | 47771 (conductor adjudication — see §3) |

All categories are in the v2 closed registry; the v2 runner alignment (#2741) held — zero
out-of-registry labels, zero retired-label (`phantom_source_pointer`) emissions.

## 2. Conductor spot verification (by-eye, this session)

The gate did NOT rely on lane agreement alone (scar W100: same-family D1/D5 agreement measures
transcription fidelity, not truth — both seats are Sonnet-family). Conductor checks executed
against raw evidence in this session:

- **49296** (payload_cross_contamination, the flagship case): canonical `per_skala` of
  "Angkutan Ojek Motor" grep-verified by the conductor — **5 occurrences of
  "perkeretaapian" (railways), 0 of "ojek"**. The licensing payload is verbatim
  special-railway-infrastructure text on a motorcycle-taxi code. Flagrant, no render needed.
- **52101 control finding**: BPS Lampiran 5 p.194 (render `lampiran5_p208-208.png`)
  **read by eye by the conductor**: row `52108 (2020) Pengelola Gudang Sistem Resi Gudang →
  52101 (2025)` — the code number CHANGED; canonical `status_mapping="MATCH_LANGSUNG"` and the
  customer-facing `intel_2026.whatChanged` ("code and scope unchanged") are false, and
  `pp28_sources:["52101"]` is a bare-number cross-vintage collision (the PP28 I.G row for
  "52101" describes the 2020 meaning — general warehousing, Rendah/NIB — not the SRG manager,
  Tinggi). The OSS-native `per_skala` itself is CORRECT (seat verified byte-for-byte against
  live OSS; conductor accepts with the triangulated receipts).
- **46100 control**: FIRST check reviewed the seat's receipts only (forward identity +
  I.G.45 row 19 pp28) and countersigned "certified" — WRONG. Post-red-team the conductor
  read the REVERSE table (Lampiran 10 p.356) by eye: second parent 63122 exists →
  retro-quarantined as mapping_metadata_false. Receipt-level review without the reverse
  render is NOT a conductor verify — pinned as a gate-protocol rule.
- Remaining quarantines: D1 and D5 converge independently on 12/13 (52299: D1 clean vs D5
  problem → quarantined by the plan §3 preregistered divergence rule, same rule that flipped
  19206 in Lot 1). Rationales are image-grounded with bidirectional crosswalk reads and
  explicit OCR-trap countermeasures (e.g. 52299's 2× zoom on the 90023→52299 cell). The
  conductor reviewed all 13 rationale texts; render-level re-verification was performed on the
  spot-check sample above, per the risk-proportional depth rule (all 13 are QUARANTINE
  verdicts — fail-safe direction; the cross-family seat requirement binds hardest on CLEAN
  verdicts, of which this lot has none in-scope).

## 3. Adjudications

1. **47771 category mismatch (D1 source_absent_in_vault vs D5 mapping_metadata_false):**
   conductor rules **mapping_metadata_false primary**. The canonical declares
   `MATCH_LANGSUNG` + `pp28_sources:["47771"]` while BPS documents a FOUR-source merge
   (47771+47892+47919+47996, both directions, pp.186/190/196/200 + p.395) — the false 1:1
   narrative is the client-facing harm; the vault absence is concomitant and recorded in the
   dossier. **Cure disposition (UPGRADED at second signing — red-team BLOCKER accepted):**
   metadata correction alone would leave uncertified vintage-2020 licensing facts exposed
   (`per_skala` material, `_l2_status=no_oss_risk`, PP28 hunt ABSENT over 11,208 pages; the
   4 BPS parents are crosswalk ancestors, NOT automatically PP28 sources — plan A-6 forbids
   exposing uncertified facts). 47771 gets **detach + metadata fix**, i.e. the Lot 2 cure
   spec is 13/13 detach.
2. **52299 divergence:** quarantined under the §3 rule ("Divergence → QUARANTINE, never
   averaged or picked"). D5's finding (90023 "Aktivitas Pelaku Kreatif Seni Rupa" merging into
   a transport-support code + payload concerns) is exactly the class the rule exists for.
3. **52101 (control):** the quarantine is a TRUE positive on a code OUTSIDE the lot's scope.
   Disposition (CORRECTED at second signing — red-team BLOCKER, then conductor
   image-verified Lampiran 10 p.389, render `lampiran10_p403-403.png`, by eye): 52101-2025
   is a **FIVE-parent MERGE** — {03143, 03241, 03243, 03263 (fishery post-harvest/production
   services), 52108 (same-title SRG warehouse manager)} → 52101. The first-signing
   disposition "CODICE_RINUMERATO from 52108" was itself a merge-undercount (the exact
   disease). Standalone cure (metadata-fix class): status_mapping → MERGE-aware with all 5
   parents, fix intel_2026.whatChanged, remove the bare-number pp28_sources ["52101"]
   (re-hunt under the 2020 parents if a PP28 basis is wanted). Its per_skala is healthy
   OSS-native and must NOT be detached. Bonus census fact from the same render: the 03xxx
   fishery fan-out hits the ENTIRE 52xxx warehousing family (52102, 52103, 52109 all show
   the same 4 fishery parents) — consistent with this lot's 52xxx
   payload_cross_contamination cluster.

## 4. The new class finding (for Zero — product-level)

The control results prove the **mapping-metadata disease (numeral collisions,
merge-undercounts) lives OUTSIDE the ~221 no-scope set too**: BOTH controls (52101 5-parent
merge, 46100 2-parent merge — each image-verified by the conductor on the REVERSE table)
are OSS-native and render as "verified" in the TRACK-P provenance badge — because the
badge's predicate covers the RISK layer (`_l2_source`), not the crosswalk narrative. 3 more
lot codes (42999 two-parent merge, 47771 four-source merge, 52299 many-to-many with 90023)
show canonical status_mapping/kbli_2020_source undercounting BPS's own bidirectional
tables — 5 metadata-undercount cases surfaced by ONE lot. Protocol note for all future
gates: **a crosswalk claim is verified only when BOTH directions are read — the reverse
table (Lampiran 10) catches merge-parents the forward table hides.** Extending
verification to the crosswalk-metadata layer across the catalog is a NEW program axis
(FATAL-4 candidate), and its product surface (badge semantics) is a Zero decision (Legge 5) —
NOT actioned in this lot.

## 5. Calibration (v2 limits, run wf_ec5c5f93-64b)

| # | Metric | Lot 2 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-FAMILY blind concordance | **NOT MEASURED in-lane** (all 28 seats are claude-sonnet-5; the in-lane 0.538 full-tuple D1-vs-D5 figure is a SAME-FAMILY proxy, which the v2 registry explicitly rules "is NOT an m1 reading") | ≥0.75 | ⏸ pending the conductor's cross-family pass (§6) |
| m2 | certification rate | **0.000** (0/13) | [0.20, 0.85] | ❌ BREACH (declared) |
| m3 | category registry | 3 seen, all in closed-7 | closed list | ✅ (1 category mismatch adjudicated §3) |
| m4 | tokens/dossier | **avg 215,251** (2,798,257 / 13 in-scope) · **max 247,199 (52299)** — run-log basis (in-lane lotReport declares it not-computable) | ≤400k per dossier | ✅ (max under ceiling) |
| m5 | gold-set hit rate | NOT run in-lane | ==1.00 | ⏸ conductor pass pending (§6) |

**Conductor-signed per-lot breach adjudication (plan A-4 rule):** m2 0.000 is a DECLARED
breach explained by the object, not the instrument: the lot sits in the same class-disease
band Lot 1 measured (silent vintage-2020 fill + metadata undercount), so a 0.00
certification rate is the true state of the data — pausing the program on it would reward
the disease. m1 is NOT adjudicated as breach-or-pass at this signing because it was not
measured (the first signing's "0.538, improved from 0.385" claim was a same-family proxy
mislabeled as m1 — red-team BLOCKER, accepted); the true cross-family m1 comes from the
conductor's GLM pass in §6 and is adjudicated there. Verdict-level same-family concordance
was 12/13 = 0.923 (category-level 7/13), recorded as lane-internal telemetry only.

## 6. Open items before Lot 2 cure ships

1. **Cross-family conductor pass (serves BOTH m1 and m5)**: a GLM-vision blind pass over
   (a) a sample of this lot's codes for the true cross-family m1 reading, and (b) the
   v2-lot2 gold controls (digest-blind in `batchA-calibration-v2.json`), per the Lot 1
   method. Scheduled as the conductor's next act, BEFORE the cure PR ships.
2. **Cure spec** `batch_a_lot2.json`: **13/13 detach** (per_skala → [], preserve prior
   block, honest-gap notes F12-conformant), incl. 47771 (§3.1 upgraded disposition) which
   ALSO gets the metadata correction (status_mapping MERGE + the 4 BPS parents recorded as
   crosswalk ancestors, explicitly NOT as PP28 sources). NO substitute values; PMA/l4/TKA
   stay abstained.
3. **Standalone metadata-fix cures for BOTH controls** (out-of-lot): 52101 (5-parent MERGE,
   §3.3) and 46100 (2-parent MERGE, §1) — per_skala untouched on both (healthy OSS-native).
4. **Surfaces**: same consumer-map as Lot 1 (canonical 4-copy sync + sidecar → KG detach →
   Qdrant clear → licensing_status (now in-script post #2742) → cache bust → prove-live).

## 7. Chain-of-custody note

One D5 seat (49233) was blocked mid-lane by a session-level tool gate and was unblocked by
the conductor with a file listing (no content, no opinion); its verdict was ALSO delivered
to the conductor directly. The runner's own journal shows all 28 seats returned results
in-workflow (0 empty). The in-workflow 49233 D5 and the directly-delivered verdict are
**semantically equivalent but categorically different** (in-workflow:
`source_absent_in_vault`; direct message: `unresolvable_source_pointer`) — both name the
same defect (a PP28 pointer an exhaustive 11,208-page hunt could not resolve), built on the
same crosswalk reads; the category difference is the same category-granularity divergence
counted in the lane's divergent-code telemetry, and the quarantine verdict is unaffected.
No claim of exact match is made. Declared here for audit completeness.

## Appendix A — cross-family conductor pass (m1 + m5), adjudicated

Executed post-second-signing per §6.1: blind GLM-vision pass (family ≠ lane, ≠ conductor),
10 codes in sha256-shuffled order (seat never told the class): 5 lot codes (m1) + 3 NEG +
2 POS (m5). POS plaintexts derived deterministically from the committed v2-lot2 digests
(derivation replicated independently; digests match byte-for-byte; full 8:
10433, 46329, 46631, 42204, 06202, 23129, 01285, 47711 — now REVEALED for lots 2+, burn
recorded for the v3 registry). Raw seat outputs:
`/tmp/kbli-conductor-a1-0718/out/lot2c-<code>.json`; full pass report:
`lot2-conductor-crossfamily-report.md` (same staging dir).

**m1 (cross-family, the registry's true measure): 5/5 = 1.00 ✅** (floor 0.75). All five
lot codes (42999, 47771, 49296, 52299, 59131) blind-concur with the lane's quarantine
verdicts, and the GLM independently re-derived the load-bearing findings (42999
two-parent merge; 47771 MATCH_LANGSUNG-vs-4-parent contradiction; 49296 railway/ojek
payload; 52299 many-to-many; 59131 pp28-absent). Method note, declared: category
concordance is read from the GLM rationale text (the cross-family template has no
structured problem_category field) — verdict-level concordance is the scored measure.
Adjudication: the same-family proxy figure (0.538) stays lane-internal telemetry; the
REAL m1 for Lot 2 is 1.00, NO breach. The §5 m1 row is superseded by this appendix.

**m5: adjudicated 4/4 valid controls = 1.00 ✅** with one control disqualified:
- NEG 3/3 HIT: 01700 (six-way merge undercount + veterinary payload re-found), 68112
  (honest gap confirmed; BONUS: independently re-found the 2020-MICE/2025-residential
  numeral collision — consistent with §4), 19206 (quarantine confirmed; the seat certifies
  a Kecil-Menengah completion path from parent 19291 and quarantines on the
  render-uncorroborated Besar tier — this is the A-6(b) pattern: recorded as a
  **scheduled per-ancestor image-grade adjudication candidate** for a possible partial
  restore, NOT a miss, NOT an in-gate fill; the honest-gap stays live).
- POS 46329 HIT (clean, no manufactured problem — the seat's specificity holds).
- POS 10433 **DISQUALIFIED AS CONTROL — TRUE FINDING** (conductor image-verified BPS
  Lampiran 10 printed p.326, render `lampiran10_p340-340.png`, BY EYE this session:
  `10419 (2025) ← 10490 (2020)` and `10433 (2025) ← 10433 (2020)` are SEPARATE rows —
  canonical `pp28_sources:["10433","10490"]` associates 10490 with the wrong child, its
  aggregation note is false). The seat did not hallucinate a problem; the "clean" control
  was metadata-contaminated. **Third contaminated control of the day (52101, 46100,
  10433), all on the crosswalk-metadata layer** — §4's disease, measured now at 3/4
  sampled OSS-native "verified" codes. 10433 joins the standalone metadata-fix cure list
  (§6.3); the v3 registry must pre-verify POS controls on BOTH crosswalk directions
  before salting.

**Sign-off condition (1) of the second signing is MET** (m1 1.00, m5 1.00 on valid
controls, both adjudicated here). Lot 3 remains gated only on condition (2): the Lot 2
cure shipping. — Conductor, 2026-07-18.

## Adversarial review

Seat: **codex** — scheduled on this SIGNED report per the W100 protocol ("even the signature
lies until red-teamed"): `codex exec -m gpt-5.6-sol -c model_reasoning_effort="xhigh"
--sandbox read-only` over this file + the raw lot output. Findings and their disposition will
be appended here and the frontmatter updated before the cure PR ships.

## Sign-off

**Lot 2 conductor gate: SIGNED — SECOND SIGNING, post-red-team** (first signing 2026-07-18
same session was FIX-FIRSTed by the codex sol red-team: 4 BLOCKER + 2 MAJOR + 1 MINOR, all
verified against raw evidence and cured above — 46100 retro-quarantined after conductor
image-verify; m1 re-labeled NOT-MEASURED; 52101 corrected to 5-parent MERGE; 47771 upgraded
to detach; m4 recomputed avg 215,251 / max 247,199; §7 reworded; this clause added).
Outcome: **13/13 in-scope quarantine, 0 certified; both innocence controls contaminated
(true findings, standalone cures §6.3)**; m2 declared breach adjudicated per-lot.
**Lot 3 is authorized ONLY after: (1) the cross-family conductor pass returns m1 and
m5==1.00 verdicts and they are adjudicated in an appendix to this report, AND (2) the Lot 2
cure has shipped.** — Conductor (Fable, MANDATO S2), 2026-07-18.
