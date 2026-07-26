---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 4 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE 2026-07-19: TWO codex sol xhigh passes. Pass 1 (red-team on first signing): FIX-FIRST — m1 semantics inverted (tuple excludes category; problem-bit 12/13=0.923), controls DOWNGRADED to anchored non-blind fixtures (runner prompt announces the expected verdict — runner defect FILED for Lot 5), m4 computed (204,693 avg / 253,154 max), title-similarity re-worded as hypothesis; finding #1 of pass 1 was LOST to a tail-truncation (W97 recurrence, declared). Pass 2 (verify + finding-#1 re-derivation): FIX-FIRST — payload census undercount (ALL TEN 66xxx carry the identical cooperative-rating payload, not just the 8 final-category codes), image-grounding wording, signature consistency — all cured in this SECOND SIGNING."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "runner: infra/workflows/kbli-batch-a-lot.js @ v2 categories, run wf_66ea406e-b0d (28 seats, 0 errors)"
  - "prior gates: #2753 (Lot 2), #2768 (Lot 3), both second-signed with Appendix A"
---

# GARUDA-FILIERA Batch A — Lot 4 (A-L4) conductor gate

> D6 adjudication of the fourth lot: 13 in-scope codes (divisions 64→66: 64955, 64996,
> 64997, 66113, 66116, 66123, 66124, 66129, 66131, 66132, 66149, 66153, 66159 —
> pension funds, insurance support, securities clearing/guarantee) + 2 innocence
> controls (59140, 59201 — DELIBERATE REUSE from Lot 3, declared: both were
> conductor pre-verified on BOTH crosswalk directions at Lot 3 vetting; every lane
> seat spawn is context-fresh by construction, so reuse does not leak).

## 1. Outcome

**13/13 in-scope QUARANTINED, 0 certified. Controls 2/2 certified — but DOWNGRADED at
second signing from "true-clean validation" to ANCHORED REGRESSION FIXTURES** (red-team
finding, accepted): the runner's innocence-control prompt ANNOUNCES the expected verdict
("the dossier MUST come out boring", "verify that NOTHING needs changing") and even
asserts a falsehood about the evidence ("no pp28_sources" — both canonicals carry the
field). A control the seat is told must be boring is not a blind specificity measure; it
only proves the pipeline doesn't manufacture work when told not to. **RUNNER DEFECT
FILED (inherited from the pilot template): neutralize the innocence-control prompt to
symmetric blind treatment for Lot 5+** — until then, control outcomes are recorded as
non-blind fixtures. (Lot 3's 2/2 carries the same caveat retroactively; Lot 2's control
FINDINGS — 52101, 46100 — are unaffected: a finding against the announced expectation is
evidence a fortiori.)

Final category census (runner assignment, 3/8/2 = 13):

| Category | Codes |
| --- | --- |
| mapping_metadata_false (3) | 64955, 64996, 64997 |
| payload_cross_contamination (8) | 66116, 66123, 66124, 66129, 66131, 66132, 66149, 66159 |
| code_collision (2) | 66113, 66153 |

All in the v2 closed registry (m3 ✅). Note: this lot introduces **code_collision** —
first sighting in Batch-A of the pilot's original disease class (68112-style).

**Lease disclosure (standing, as Lot 3):** runner logged LEASE-GUARD SKIPPED on all 15
dossiers — same infra state (Redis lease registry unreachable from sessions), same
compensating isolation (conductor-private evidence root, data-plane guard, zero
canonical writes in-lane, single live lane). Infra item unchanged.

## 2. Conductor spot verification (by-eye)

- **64955 (flagship wrong-parent)**: CONDUCTOR-VERIFIED WITHOUT A NEW RENDER — the
  claims sit on `lampiran10_p413-413.png` (BPS Lampiran 10 printed p.399), the SAME
  render the conductor read by eye at the Lot 3 gate for 64940: that page shows BOTH
  `64955 "Pengelolaan Tabungan Perumahan Rakyat" ← 64999 "Aktivitas Jasa Keuangan
  Lainnya YTDL, Bukan Asuransi dan Dana Pensiun"` AND `64940 "Aktivitas Sekuritisasi"
  ← 64992 "Perusahaan Pembiayaan Sekunder Perumahan"`. Canonical's
  `kbli_2020_source="64992"` for 64955 is FALSE (64992 belongs to 64940). The
  title-similarity explanation ("Perumahan" in both titles, mapping_note confidence
  "[medium]") is recorded as a PLAUSIBLE HYPOTHESIS, not a demonstrated cause
  (red-team wording correction). Same wrong-parent CLASS as 64940 (Lot 3, §2 of that
  gate) and 10433 (Lot 2 Appendix A, image-verified Lampiran 10 p.326) — receipts in
  those signed gates.
- **66xxx payload cluster (CORRECTED at second signing — verify-pass MAJOR):** the
  census's "8 payload codes" is the runner's single-final-category assignment, NOT an
  exhaustive defect census — **all TEN in-scope 66xxx records carry the identical
  cooperative-rating kewajiban payload** (incl. 66113 and 66153, whose final category
  is code_collision; their D5 rationales record the layered payload defect too). The
  defect is canonical-text-grounded (per_skala content read directly), cross-checked
  against the image-grounded crosswalk and vault-absence evidence — NOT a D2
  licensing-row extraction (d2:null on all in-scope; verify-pass MINOR wording cure).
  Consistent with the 52xxx ship-broker cluster (Lot 2): division-level contamination.
  All quarantines fail-safe; conductor reviewed all 13 rationales.

## 3. Adjudications

1. **Seat-agreement structure (CORRECTED at second signing — red-team: the runner's
   concordance tuple is {mapping_type, licensing_inherits, problem_found}, category
   EXCLUDED; "D5-weighted" was wrong — the runner applies deterministic D5 PRECEDENCE
   when D5 flags a problem, runner line ~641):**
   - **category_mismatch (concordant tuple, different category): 66116, 66124, 66129**
     — the runner's only 3 concordant codes; final category = D5's by precedence.
   - **divergent (tuple mismatch): the other 10** — of which NINE have BOTH problem
     bits true (they disagree on mapping_type/licensing shape, not on "is it sick");
     only **66149** is a true D1-clean-vs-D5-problem case, quarantined by the plan §3
     preregistered divergence rule.
   - Problem-bit agreement: **12/13 = 0.923**.
4. **64955/64996/64997**: mapping_metadata_false confirmed (all three declare wrong or
   flattened 2020 sources vs the bidirectional BPS tables; 64955 conductor-verified §2).

## 4. Calibration

| # | Metric | Lot 4 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-family | Runner same-family tuple-concordance ({mapping_type, licensing_inherits, problem_found} — category EXCLUDED) **0.231** = declared runner-level breach. The low figure is driven by mapping_type/licensing-shape disagreement on codes BOTH seats flag sick (9/10 divergent have both problem bits true); problem-bit agreement **12/13 = 0.923** (sole disagreement: 66149). The first signing's causal claim ("category-level disagreement drives it") was inverted and is corrected. **TRUE cross-family (GLM 5.2 vision, blind): 5/5 = 1.00 — Appendix A.** | ≥0.75 | ✅ cross-family 1.00 (Appendix A) · runner-proxy breach stays DECLARED |
| m2 | certification rate | **0.000** (0/13) | [0.20, 0.85] | ❌ BREACH (declared; same object-level adjudication as Lots 1-3) |
| m3 | categories | 3 seen, all closed-7 | closed list | ✅ |
| m4 | tokens/dossier | **avg 204,693** (2,661,013 / 13 in-scope, controls' 210,906 excluded) · **max 253,154 (66159)** — red-team computed from workflowProgress | ≤400k | ✅ |
| m5 | gold-set | NEG spot **3/3 HIT** (cross-family blind, Appendix A) · POS leg SKIPPED (#2772 OPEN at run time — carried to Lot 5) | ==1.00 | ✅ NEG 3/3 · POS ⏸ declared |

## 5. Open before the Lot 4 cure ships

1. ~~Cross-family GLM pass~~ **DONE — adjudicated in Appendix A** (m1 5/5, m5-NEG 3/3,
   POS SKIPPED/declared, carried to Lot 5).
2. Cure spec `batch_a_lot4.json`: 13/13 detach + metadata corrections
   (64955→64999 et al.) per the Lot 3 precedent.
3. Surfaces: the proven consumer-map.

## Appendix A — cross-family adjudication (conductor, post-GLM pass)

Source: `/tmp/kbli-conductor-a1-0718/lot4-conductor-crossfamily-report.md` (GLM 5.2 vision
via `run-lot4-conductor.sh`, 8/8 rc=0 first attempt, zero retry, zero fallback, blind
sha256-shuffled order salt `shuffle-lot4-conductor`, ~13 min wall PAR=3). Both load-bearing
structured fields below were re-verified by the conductor DIRECTLY on the raw GLM outputs
(`out/lot4c-66159.json` → `mapping_type="COLLISION"`, `out/lot4c-60101.json` →
`mapping_type="SPLIT"`) this turn — not taken from the subagent's prose.

**m1 (5 in-scope codes: 64955, 66113, 66129, 66153, 66159) = 5/5 = 1.00 verdict-level —
ADJUDICATED PASS** (clears the ≥0.75 floor; the lane's same-family 0.231 tuple figure stays
declared as a runner-proxy breach, now superseded as the m1 reading by the true cross-family
measure, per the Lot 2/3 precedent). Category-level: 4/5 exact. The 1/5 nuance —
**66159**, GLM structured `mapping_type="COLLISION"` (66159←66199; same-digit 2020-66159 is
unrelated commodity-futures brokerage) vs lane final category payload_cross_contamination —
is ADJUDICATED AS THE MULTI-DEFECT STRUCTURE OF THE 66xxx CLUSTER, not a miss: this gate's
own second signing (§2) records that ALL TEN 66xxx carry the cooperative-rating payload and
that the runner census is a single-final-category assignment, NOT an exhaustive defect
census. GLM's rationale independently cites the payload defect too; both labels are
evidence-grounded, and the cure (detach) is identical under either. No census change.
Bonus corroborations logged for the cure: GLM independently refutes canonical ancestors
66152 (→66122, code 66129) and confirms 64955←64999 digit-by-digit on both renders.

**m5-NEG (60101, 64940, 52219 — pre-detach snapshots, DETACHED state re-confirmed on
origin/main at run time) = 3/3 HIT — ADJUDICATED PASS.** 64940 and 52219 re-derive their
documented defects almost verbatim (53201-courier false ancestor; maritime ship-broker
regime on a land-transport code). The flagged cross-pass divergence on **60101** (this pass
reads SPLIT 60101→{60101,60103}; the Lot-3 pass on the same renders read ONE_TO_ONE) is
**RESOLVED IN FAVOR OF SPLIT**: the conductor read that render by eye at the Lot 3 gate
(`lampiran10_p409-409.png`, printed p.395 — split 60101→{60101,60103} and merge
60103←{60101,60102} both visible), and the Lot 3 red-team independently confirmed the same
by-eye reading. The Lot-3 GLM ONE_TO_ONE was the less complete read; the HIT verdict is
unaffected either way.

**m5-POS: SKIPPED, declared** — #2772 (calibration v3 re-salt) verified OPEN at run time.
The POS leg runs at the Lot 5 cross-family pass once the v3 registry is on main.

**Seat-stability meta-note (for the program record):** in BOTH flags of this pass the
unstable element is the structured `mapping_type` LABEL from vision reads — never the
verdict bit, never the evidence citations. This mirrors the lane's own m1-tuple finding
(mapping_type/licensing-shape disagreement drives tuple divergence while problem bits agree
12/13). Verdict bits and citations are the load-bearing signal; structured labels from
vision extraction are soft and MUST NOT be used as concordance keys in future calibration
without this caveat.

## Adversarial review

Seat: **codex** — scheduled on this SIGNED report: sol xhigh read-only over this file +
raw output (`wd3w9n3b3.output`) + journal (`wf_66ea406e-b0d`) + canonical + renders.
Findings appended and cured before the cure ships.

## Sign-off

**Lot 4 conductor gate: SIGNED — SECOND SIGNING, post two adversarial passes** (pass-1
red-team FIX-FIRST + pass-2 verify FIX-FIRST, all findings cured above; substance —
13/13 quarantine, census-as-final-assignment, 64955 by-eye — VERIFIED). Controls 2/2
recorded as ANCHORED NON-BLIND REGRESSION FIXTURES (never "true-clean"); runner
prompt-neutralization defect FILED for Lot 5. **Lot 5 authorized ONLY after: (1)
cross-family appendix adjudicated, (2) Lot 4 cure shipped, (3) the runner
innocence-prompt fix lands.** — Conductor (Fable, MANDATO S2), 2026-07-19.
