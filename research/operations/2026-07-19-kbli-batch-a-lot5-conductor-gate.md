---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 5 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE 2026-07-19: codex sol xhigh read-only on the FIRST-SIGNED report returned FIX-FIRST — 1 BLOCKER + 4 MAJOR + 2 MINOR, all verified and cured in this SECOND SIGNING. BLOCKER: the controls were STILL not blind — the prompt was neutral (#2776) but INNOCENCE_SCHEMA leaks both the control nature and the expected outcome (seats self-identify as 'innocence control' in their notes) — the Lot-4 fix begat its twin bug (scar-#3 shape); controls re-recorded as ANCHORED NON-BLIND FIXTURES, second-generation runner defect FILED. MAJORs: §3 concordance arithmetic rewritten (4 concordant / 9 divergent); 70100 _source_relabeled dispute ADJUDICATED by the conductor (structured markers refute the prose claim → detach stands); 59140 SHA claim retracted (only 59201 recorded sha256 verification); immutable artifact manifest added. MINORs: §2 render citations completed (p221 read by eye this session); m4 average stated exactly."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "runner: infra/workflows/kbli-batch-a-lot.js @ blob 78f3608008 (main 02d8c673b2, post-#2776 neutral prompt), run wf_0f7438f4-a41 (28 seats, 0 errors, 0 empty)"
  - "prior gates: #2753 (Lot 2), #2768 (Lot 3), #2774 (Lot 4), all second-signed with Appendix A"
---

# GARUDA-FILIERA Batch A — Lot 5 (A-L5) conductor gate

> D6 adjudication of the fifth lot: 13 in-scope codes (divisions 66→70: 66192, 66197,
> 66211, 66224, 66292, 66299, 66309, 68123, 68125, 68126, 68127, 68129, 70100 — trust
> administration, financial-market support, insurance intermediaries, real-estate
> management, head offices) + 2 innocence controls (59140, 59201 — THIRD deliberate
> reuse, declared; every lane seat spawn is context-fresh by construction).

## 1. Outcome

**13/13 in-scope QUARANTINED, 0 certified. Controls 2/2 certified — recorded as
ANCHORED NON-BLIND REGRESSION FIXTURES** (red-team BLOCKER, accepted): the Lot-4
innocence-PROMPT neutralization (#2776) landed and held (`innocencePrompt()` verified
in-file by the conductor: no expectation markers), but the red-team proved the leak
MOVED, not died — **`INNOCENCE_SCHEMA` (runner lines ~439-449) still reveals both the
control nature and the expected outcome** ("changes_proposed MUST be empty when
verdict=certified", "a true innocence control", quarantined = "over-extraction
finding"), and both control seats' notes self-identify as "innocence control". The
Lot-4 fix begat its twin bug — the scar-#3 family shape ("il fix partorisce il bug
gemello"). **SECOND-GENERATION RUNNER DEFECT FILED: neutralize the seat-visible surface
entirely** — controls must flow through the SAME schema and prompts as member codes,
with the innocence normalization computed runner-side (deterministic JS) after the
seat returns, the seat never knowing. Until that lands and 59140/59201 are re-run on
fresh contexts, no control outcome in this program is a blind specificity measure.
(Lot 2's control FINDINGS — 52101, 46100 — remain unaffected a fortiori.)

Final category census (runner assignment, 10/2/1 = 13):

| Category | Codes |
| --- | --- |
| payload_cross_contamination (10) | 66192, 66197, 66211, 66224, 66292, 66299, 66309, 68125, 68127, 68129 |
| mapping_metadata_false (2) | 68123, 68126 |
| source_absent_in_vault (1) | 70100 |

All in the v2 closed registry (m3 ✅, `breach=false`). Census is the runner's
single-final-category assignment, NOT an exhaustive defect census (Lot 4 lesson —
66192 is at minimum collision+payload multi-defect).

**Lease disclosure (standing, as Lots 3/4):** runner logged LEASE-GUARD SKIPPED on all
15 dossiers — same infra state, same compensating isolation (conductor-private
evidence root, data-plane guard, zero canonical writes in-lane, single live lane).

## 2. Conductor spot verification (by-eye, THIS session — three renders)

- **`lampiran5_p222-222.png` (printed p.208):** row 1 confirms `66193 "Wali Amanat
  (Trustee)" → 66192 "Penitipan dan Pengelolaan Berdasarkan Perjanjian Trust"` — the
  TRUE ancestor of 2025-66192 is 66193, so canonical's same-digit `MATCH_LANGSUNG` is
  a code-collision false-positive. Same page: `66292 "Aktivitas Pemeringkat Usaha
  Mikro, Kecil, Menengah dan Koperasi" → 66198` (the cooperative-rating activity's
  2025 home is 66198, NOT 66292), identity rows `66211→66211` / `66224→66224`, and
  independent re-confirmation of two Lot 4 adjudications (`66153 ← 66195 ASPM`; the
  `66199 → {66131, 66149, 66159, 66197, 66199}` five-way fan).
- **`lampiran5_p221-221.png` (printed p.207):** last row confirms `2020-66192
  "Kustodian (Custodian)" → 2025-66132` — the same-digit 2020 code is NOT this code's
  ancestor; its true destination is 66132. Same page independently re-confirms Lot 4:
  `2020-66159 fans to {64993, 66113, 66123, 66129, 66132}` and `2020-66153 "Pedagang
  Fisik Komoditi" → 64994`.
- **`lampiran5_p223-223.png` (printed p.209):** the seven-child fan `2020-68111 "Real
  Estat Yang Dimiliki Sendiri Atau Disewa" → {68111, 68112, 68123, 68125, 68126,
  68127, 68129}` confirmed row-by-row. This verifies BOTH metadata-false verdicts by
  direct contradiction: canonical claims `68123 ← 68130 "Kawasan Industri"`, but
  68130's actual child on this page is 68122; canonical claims `68126 ← 52101
  "Pergudangan"`, but 68126's actual parent is 68111. The same page closes the pilot's
  collision story with government ink: `2020-68112 "Penyewaan Venue MICE" → 2025-68124`
  while 2025-68112 (residential) descends from 68111.
- The `66292 ← 64400 (OJK)` forward mapping and the reverse-direction confirmations
  are cited from the LANE's evidence locators (`lampiran5_p218`, `lampiran10_p416/417`),
  NOT conductor-eye claims (red-team MINOR, wording corrected).

All 13 quarantine rationales were reviewed by the conductor; every one cites specific
crosswalk page/row locators and/or ABSENT scan counts. All quarantines are fail-safe.

## 3. Adjudications

1. **Seat-agreement structure (runner tuple {mapping_type, licensing_inherits,
   problem_found}, category EXCLUDED; corrected per red-team against
   `lotReport.m3_refutation_categories`):**
   - **4 concordant**: 2 full-match (66292, 66299) + 2 category_mismatch (66197,
     68125 — final category = D5's by precedence).
   - **9 divergent**: 6 with BOTH problem bits true (66192, 66309, 68123, 68126,
     68127, 68129 — disagreement is on mapping-shape/licensing labels, not on "is it
     sick") + **3 true D1-clean-vs-D5-problem (66211, 66224, 70100)** — quarantined by
     the plan §3 preregistered divergence rule (D5 precedence). Consistent with the
     by-eye p.208 reading: 66211/66224 are same-number identity rows (crosswalk clean —
     the disease D5 found is payload-level, invisible to a crosswalk-only read).
   - Problem-bit agreement: **10/13 = 0.769**.
2. **66192**: multi-defect (collision + cooperative payload); final category = D5's
   payload_cross_contamination; BOTH collision halves conductor-verified by eye (§2:
   66193→66192 on p.208; 66192→66132 on p.207).
3. **68123/68126**: mapping_metadata_false confirmed by direct visual contradiction
   (§2) — wrong-parent class, same disease as 64940/64955/10490.
4. **70100 — `_source_relabeled` dispute ADJUDICATED (red-team MAJOR, resolved THIS
   session):** the canonical record's `_source_relabeled` note (2026-06-27) claims
   "content is OSS-RBA-2025 per _l1/_l2" — but the STRUCTURED markers refute that for
   the per_skala layer: the record has **no `_l2_source` key at all** and
   `_l2_status="no_oss_risk"` (the OSS risk endpoint had nothing for this code), while
   the vault-exhaustive PP28 hunt is ABSENT (21 files / 11,208 pages). `_l1_source`
   covers judul/uraian, not per_skala. The note was a label-fix pass
   (PP28_2024→PP28_2025) whose content-provenance aside is unverified prose; per the
   TRACK-P doctrine, structured markers win over prose. **Detach STANDS** (per_skala
   provenance unverifiable on every axis — the July-disease signature), category
   source_absent_in_vault, honest gap, no remap asserted. The cure's `_data_note` MUST
   record this dispute and its resolution explicitly (F12 wording: "not
   retrievable/verifiable", never "not published").

## 4. Calibration

| # | Metric | Lot 5 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-family | Runner same-family tuple-concordance **4/13 = 0.308** = declared runner-proxy breach (same artifact as Lots 3/4); problem-bit agreement **10/13 = 0.769**. TRUE cross-family GLM pass ⏸ (§5). | ≥0.75 | ❌ runner-proxy breach DECLARED · true cross-family ⏸ |
| m2 | certification rate | **0.000** (0/13) | [0.20, 0.85] | ❌ BREACH (declared; same object-level adjudication as Lots 1-4) |
| m3 | categories | 3 seen, all closed-7 | closed list | ✅ |
| m4 | tokens/dossier | **avg 200,574.54 (≈200,575)** (2,607,469 / 13 in-scope; controls' 99,797 + 115,058 excluded from numerator AND denominator) · **max 228,839 (66192)** — computed from workflowProgress | ≤400k | ✅ |
| m5 | gold-set | not run in-lane | ==1.00 | ⏸ cross-family pass (§5) — POS leg UNBLOCKED (#2777 merged post-run) with the conductor exposed-codes screen |

## 5. Open before the Lot 5 cure ships

1. Cross-family GLM pass: m1 sample (5 codes incl. 66192) + m5-NEG spot (3 from cured
   set) + m5-POS (v3 registry now on main via #2777) — POS candidates screened by the
   conductor against the exposed-codes list (any code named in a signed gate report is
   no longer blind → skip to next eligible, declared).
2. Cure spec `batch_a_lot5.json`: 13/13 detach + `_data_note` provenance corrections
   (68123→68111, 68126→68111, 66192→66193; NO status_mapping_correction — Lot 4
   precedent) + the 70100 dispute record (§3.4) + cooperative-payload naming on the
   payload codes (root: PP28 row 66292 vintage-2020; true 2025 home 66198).
3. **Runner INNOCENCE_SCHEMA neutralization** (§1 BLOCKER): controls must present the
   SAME seat-visible surface as member codes (same schema, same prompts); innocence
   normalization computed runner-side post-hoc. Guilt test: schema/prompt text visible
   to control seats contains no control-identifying or expectation-revealing marker.
   Then re-run 59140/59201 on fresh contexts. **Condition for Lot 6.**
4. Surfaces: the proven consumer-map.

## 6. Meta-pattern (the malattia-delle-malattie, program record)

- **The cooperative-rating payload cluster has a traced ROOT**: PP28's own lampiran
  row for 66292 (render 394947_p143, "No.9, Kode KBLI 66292, 'Aktivitas Pemeringkat
  Usaha Mikro, Kecil, Menengah dan Koperasi'") is a KBLI-2020-vintage row; the
  silent-fill pipeline matched it by digit-string and spread its kewajiban across the
  66xxx division (Lots 4+5: 17+ codes carrying the identical cooperative payload).
  The activity's true 2025 home is 66198 (by-eye §2). One vintage-blind digit-string
  join at extraction time = an entire division's licensing facts poisoned.
- **The 68 division renumber-fan is the collision factory**: 2020-68111 fans into 7
  children while 2020-68112/68120/68130 shift to 68124/68121/68122 — same-digit
  continuity is FALSE for most of the division, and canonical's title-similarity
  remaps (68130→68123, 52101→68126) are exactly the "crosswalk narrows, context
  adjudicates" failure the methodology predicted.
- **The guard-fix-begets-twin-bug shape now has a THIRD instance in this program**:
  Lot 4 neutralized the innocence PROMPT; the SCHEMA still leaked (§1). Same family as
  W83→W84 (the noise-strip fix that spawned the cross-line over-match). Antidote
  restated: a blindness fix is only done when the ENTIRE seat-visible surface is
  symmetric, and the guilt test must scan every channel (prompt AND schema AND labels),
  not the one that bit last time.

## 7. Artifact manifest (immutable pins, red-team MAJOR fix)

| Artifact | Pin |
| --- | --- |
| Lane run | `wf_0f7438f4-a41` (28 seats, 0 errors) |
| Runner | blob `78f3608008a68d9030909ebb897edf7a9f70e147` = `infra/workflows/kbli-batch-a-lot.js` @ main `02d8c673b2c03e21048de088d0978174149b07ec` |
| Raw output | sha256 `8de714f054c32ab502ab9f57d81a3776d60f44383994c490a74659ed3009216c` (task wj4otn7pb output) |
| Journal | sha256 `06f306b99a348856ffec373535981ea5358f1cc65fdc309526987582624951ba` (wf_0f7438f4-a41/journal.jsonl, 28 start + 28 result) |
| Canonical @ lane run | sha256 `1ce3060de421030e00447e29ed135aeda72ea600e8d235f4bbdd4c01e815d757` (main `02d8c673b2`, pre-#2777) |
| Render p.207 (by-eye) | sha256 `46e37c5541c1467a7a51dd45b3ba0ddcd663a911189693d917f41296db29ece2` |
| Render p.208 (by-eye) | sha256 `b59863d35c5c3f66a595c0a06cd699b2c952b83e56cf64dea4fa2261dc56e493` |
| Render p.209 (by-eye) | sha256 `db9fe59065cecca8f464e96d764cbea7a4bb2aeb12d277864d4b1b01d963b2aa` |
| Red-team transcript | `/tmp/kbli-conductor-a1-0718/lot5-redteam.txt` (full-output capture, no tail — W97) |

## Adversarial review

Seat: **codex** — DONE on the first-signed report (sol xhigh read-only, full-output
capture): **FIX-FIRST, 1 BLOCKER + 4 MAJOR + 2 MINOR**, all cured in this second
signing (see frontmatter). The red-team ALSO independently confirmed: census 10/2/1=13
exhaustive and exclusive; m1 0.308 and problem-bit 10/13 correct; the 3 divergence-rule
cases real; controls' verdicts/changes_proposed as reported (their BLINDNESS is what
failed); §2 substantive claims confirmed by the renders; journal integrity (28+28).
W100 protocol held for the FIFTH consecutive lot: the signature lied until red-teamed.

## Sign-off

**Lot 5 conductor gate: SIGNED — SECOND SIGNING, post adversarial pass** (all findings
cured above; substance — 13/13 quarantine, census, 66192/68123/68126 by-eye, 70100
adjudication — VERIFIED). Controls 2/2 recorded as ANCHORED NON-BLIND REGRESSION
FIXTURES (schema leak); second-generation runner defect FILED. **Lot 6 authorized ONLY
after: (1) cross-family appendix adjudicated, (2) Lot 5 cure shipped, (3) the
INNOCENCE_SCHEMA neutralization lands with symmetric seat-visible surface + control
re-run.** — Conductor (Fable, MANDATO S2), 2026-07-19.
