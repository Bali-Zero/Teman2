---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 6 conductor D6 gate)
adversarial_review: codex
adversarial_review_detail: "DONE (sol xhigh read-only, full-output capture per W97 — /tmp/kbli-conductor-a1-0718/lot6-redteam.txt lines 8333-8362). Verdict: FIX-FIRST — 2 BLOCKER (80190 certification materially false; runner certification contract does not verify client-facing facts) + 3 MAJOR + 1 MINOR. ALL findings accepted and cured in this SECOND SIGNING; the 80190 certification is REVOKED."
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "runner: infra/workflows/kbli-batch-a-lot.js @ blob a3e8ed9dff (main 548d85b28c, post-#2778 SYMMETRIC BLIND controls), run wf_dfae986f-5d3 (30 seats, 0 errors, 0 empty)"
  - "prior gates: #2753 (L2), #2768 (L3), #2774 (L4), #2788 (L5), all second-signed with Appendix A"
  - "fill provenance: scripts/fill_kbli_80190.py (#1813, operator decision, NB-3 source) — surfaced by the red-team"
  - "cross-family: GLM 5.2 vision pass, full transcript /tmp/kbli-conductor-a1-0718/lot6-conductor-crossfamily-report.md (Appendix A)"
---

# GARUDA-FILIERA Batch A — Lot 6 (A-L6) conductor gate

> D6 adjudication of the sixth lot: 13 in-scope codes (divisions 72→85: 72101, 72103,
> 72105, 75001, 75002, 75009, 77397, 78109, 80190, 82911, 85321, 85323, 85324 — R&D,
> veterinary, rental, labour supply, security, vocational education) + 2 innocence
> controls (59140, 59201 — FOURTH deliberate reuse, declared). **FIRST LOT RUN WITH
> SEAT-SURFACE-SYMMETRIC CONTROLS** (#2778 symmetric pipeline): controls flow through
> the SAME adjudicateCode() D1/D5 path as members — 30 seats this lot (vs 28), the
> price of symmetry. Conductor verified post-run: no control marker is exposed by the
> runner and no self-identification was observed in any seat output. (Full "true
> blindness" against 4th-reuse recognition would require FRESH controls — wording
> restricted per the adversarial MINOR.) **Condition 3 of the Lot 5 sign-off is
> SATISFIED at the seat-surface level.**

## 1. Outcome (post-adversarial)

**The runner emitted 12 QUARANTINED + 1 CERTIFIED (80190); the adversarial review
REJECTED the certification. Operational state: 13/13 in-scope QUARANTINED — zero valid
certifications in the program to date.** The would-be first certification failed the
red-team because the conductor's §3.4 rationale ("empty licensing arrays = the record
asserts nothing") was **materially false**: the record's four per_skala tiers each
assert `Tinggi` risk, a 7-day SLA, a scope string, and `fiktif_positif=true` (canonical
`KBLI_2025_FINAL_CLEAN.json:452247-452307`, re-verified by the conductor's eye at this
signing), and the web frontend derives **"NIB + Izin"** from `Tinggi` even with
`perizinan=[]` (`apps/mouth/src/lib/kbli-derive.ts:25`, the `[]` case pinned by
`kbli-derive.test.ts:48`). Certifying it would have published risk/SLA/license facts
with no government locator.

Controls under the symmetric regime: **59201 clean (true negative); 59140 flagged with
an evidence-grounded finding** (adjudicated §3.5 — a real metadata nit, not a
fabrication; under the old announced-expectation regime this code was "certified"
three times). Specificity datum: 1 clean + 1 real finding + 0 fabrications.

Final category census — **runner assignment, verbatim** (2/3/1/1/5 = 12 + 1 emitted;
the CERTIFIED row is preserved as audit trail of what the runner produced, NOT as a
valid verdict):

| Category (runner) | Codes |
| --- | --- |
| source_absent_in_vault (2) | 72101, 72103 |
| mapping_metadata_false (3) | 72105, 75002, 77397 |
| code_collision (1) | 75001 |
| wrong_authority_level (1) | 75009 — **first Batch-A sighting** (the 49213-class disease) |
| payload_cross_contamination (5) | 78109, 82911, 85321, 85323, 85324 |
| CERTIFIED — **REVOKED by adversarial review** (1) | 80190 → quarantined / pending source resolution (§3.4) |

All in the v2 closed registry (m3 ✅, `breach=false`; 5 of 7 categories seen — the
widest category spread of any lot). Census is the runner's single-final-category
assignment, NOT an exhaustive defect census.

**Lease disclosure (standing):** LEASE-GUARD SKIPPED on all 15 dossiers — same infra
state, same compensating isolation.

## 2. Conductor spot verification (by-eye, THIS session — two fresh renders + one prior)

- **`lampiran10_p422-422.png` (printed p.408, veterinary block):** rows 1-6 confirm the
  many-to-many tangle for ALL THREE vet codes: `75001 ← {01621 "Jasa Pelayanan
  Kesehatan Ternak", 75000 "Aktivitas Kesehatan Hewan"}`, `75002 ← {01621, 75000}`,
  `75009 ← {01621, 75000}` — each 2025 code has TWO 2020 parents (one from the
  AGRICULTURE chapter, one from professional services). The canonical single-parent
  metadata is incomplete for all three: `CODICE_RINUMERATO` for 75001/75002 and
  `MATCH_CON_AGGREGAZIONE` for 75009 (canonical:442231) each record only parent 75000,
  omitting 01621 — government ink refutes the single-parent claim in every case.
  *(Adversarial MAJOR cured: the first signing wrongly wrote `CODICE_RINUMERATO` for
  all three.)*
- **`lampiran10_p426-426.png` (printed p.412, security block):** exactly ONE row for
  80190: `80190 "Aktivitas Keamanan YTDL" ← 80200 "Aktivitas Jasa Sistem Keamanan"` —
  clean bidirectional 1:1, no other row touches either code. The CROSSWALK layer of
  80190 is conductor-eye-verified (and is not what failed — §3.4). Bonus:
  `82911 ← 82911` identity row visible on the same page (consistent with its
  payload-only quarantine).
- **`lampiran5_p207-207.png` (printed p.193, read by the conductor at the Lot 5 POS
  check THIS session):** contains the row `51108 "Angkutan Udara Bukan Niaga" → 85321
  "Pendidikan Menengah Kejuruan Umum Pemerintah"` — one of ~15 division-crossing
  targets of the 51108 residual bucket. The lane's D5 found the same 51108 parent on
  the reverse table (p.430) plus 85230; the conductor's independent prior read
  corroborates the forward direction.

All 12 quarantine rationales were reviewed by the conductor; every verdict cites
specific crosswalk page/row locators and/or ABSENT/NOT_APPLICABLE verdicts with probe
counts. The 13th rationale (the certification) was reviewed and initially accepted —
wrongly; see §3.4.

## 3. Adjudications

1. **Seat-agreement structure (runner tuple, category EXCLUDED):** 4 concordant
   (3 full-match: 72105, 85323, 80190 · 1 category_mismatch: 85324 — final = D5 by
   precedence) + 9 divergent, of which 5 have BOTH problem bits true and **4 are true
   D1-clean-vs-D5-problem (72101, 72103, 75002, 75009)** — quarantined by the
   preregistered divergence rule. Problem-bit agreement: **9/13 = 0.692** (8 both-sick
   + 1 both-clean). Note post-adversarial: the one both-clean (80190) is precisely the
   case the certification-contract hole let through — seat concordance measured the
   contract's blind spot, not the record's health.
2. **`_source_relabeled` class (72101, 72103):** D1 ACCEPTED the canonical's
   relabel-note prose ("content is OSS-RBA-2025"); D5 flagged source-absent. Adjudicated
   per the 70100 precedent (L5 gate §3.4): the structured markers
   (`_l2_status=no_oss_risk`, no `_l2_source`) refute the note's provenance aside for
   the per_skala layer — **markers beat prose, D5 precedence correct, detach stands.**
3. **Veterinary trio (75001 collision / 75002 metadata / 75009 wrong_authority):**
   multi-parent eye-verified (§2). 75009's authority facts trace to the PP28 row for
   2020-75000 (p.693) — inherited across an unacknowledged 2-parent split, the
   49213-class shape.
4. **80190 — CERTIFICATION REVOKED (adversarial BLOCKER, accepted in full):**
   - **What the first signing got wrong.** The conductor eye-verified the CROSSWALK
     (§2) but accepted the seats' claim about the CANONICAL CONTENT ("empty arrays =
     asserts nothing") without reading the full record. The record in fact asserts,
     in each of 4 tiers: `kategori_risiko="Tinggi"`, `jangka_waktu="7"`,
     `scope_uraian="Jasa Penerapan Peralatan Keamanan (security devices)"`,
     `fiktif_positif=true`, marker `jangka_waktu_source="nb3_lampiran_keamanan_verified"`
     (canonical:452247-452307, conductor-eye re-read at this signing). Downstream,
     `kbli-derive.ts:25` turns `Tinggi` + `perizinan=[]` into a published
     **"NIB + Izin"** license claim, and `l4_bali.reason` + `intel_2026.whatYouNeed`
     both derive from the same unverified `Tinggi` ("medium-high/high risk → not
     blocked by moratorium").
   - **Provenance (surfaced by the red-team).** The per_skala was filled by
     `scripts/fill_kbli_80190.py` (#1813) — an OPERATOR-decided, documented fill
     sourced from NB-3's verbatim reading of PP 28/2025 Lampiran I (sub-sektor
     Keamanan), cross-checked against sibling 80110. This is honest archaeology, but
     it does NOT meet the Filiera certification bar: NB-3 is a W90-class proxy (no
     page/row locator, no vintage pin, snapshot can be stale), the fill never updated
     the structured markers (hence the internal incoherence: `status_mapping=BPS_ONLY`
     + `pp28_sources=[]` + `_l2_status=no_oss_risk` vs `_source="BPS_7_2025 +
     PP28_2025"` and a full 4-tier regime — canonical:452309-452335, eye-verified),
     and the PP28 row NB-3 read was almost certainly keyed by a VINTAGE-2020 code —
     the crosswalk (§2) shows `80190 ← 80200`, so the inheritance 80200→80190 needed
     D2 adjudication that never happened.
   - **Disposition (fail-safe, per the red-team's prescription):** 80190 is
     **quarantined / pending source resolution** and **JOINS THE CURE — 13/13
     detach**, with the fill preserved under `per_skala_disputed_*` and a `_data_note`
     recording: the #1813 fill provenance, the marker incoherence, the 80200→80190
     crosswalk fact, and the concrete re-certification path (eye-verify the PP28
     Lampiran I Keamanan row on a 300-dpi render with page/row locator + adjudicate
     the 80200 inheritance + re-run both 80190 seats under the patched certification
     contract). Detaching supersedes but does not destroy the operator fill — the
     disputed block keeps it fully reconstructable. Invalidation list for the detach:
     `intel_2026.whatYouNeed` (honest-gap via compiler, standard) + `l4_bali.reason`
     (derived from the detached Tinggi — recorded as derived-surface note, F15
     conservative posture unchanged, consistent with the 8-code pilot treatment).
   - **The structural hole (adversarial BLOCKER 2, accepted).** The runner can
     certify without verifying client-facing facts: D5's schema requires only 4
     fields (runner:341), the certification diff compares only
     `{mapping_type, licensing_inherits, problem_found}` (runner:603), D2 fires only
     under the compound guard `preD2Verdict==="certified" && licensing_inherits===true`
     (runner:678 — independently re-verified on disk at this signing, all four
     red-team citations CONFIRMED; for 80190, `licensing_inherits=false` meant the
     "certified" pre-verdict passed through with NO PP28 check at all), and the PP28
     `NOT_APPLICABLE` verdict is circular ("N/A because `pp28_sources` is empty" —
     while the record carries regulatory facts). **Until this contract is patched, certification is
     structurally unsafe: every "certify" is an unverified pass-through.** The patch
     (per-field inventory of ALL exposed client-facing facts — risk, SLA, scope,
     derived license, fiktif_positif — each with `source_locator`/`vintage`/
     `verified|absent`; regression test "perizinan=[] + Tinggi with no resolvable
     source does NOT certify"; re-run of both 80190 seats) is a **mandatory
     deliverable of the Lot 6 cure and a precondition for Lot 7 and for any future
     certification** (§5).
5. **59140 control finding — ADJUDICATED (not a pipeline failure):** D5 found the
   crosswalk pristine (identity 1:1, eye-verified by the conductor at Lot 3) but
   flagged `pp28_sources=['59140']` as unverifiable (ABSENT from its narrow
   sektor-scoped scan). The code is OSS-NATIVE (`_l2_source=OSS_RBA_resiko_2025`,
   canonical:376461, red-team re-verified) — its per_skala provenance is sound BY
   MARKER; the unverifiable pp28 label is a metadata nit of the same class as the
   01629/71204 standalone cures, NOT the July disease. **No detach** (not a member;
   detaching an OSS-native record would be wrong); the pp28-label joins the standalone
   metadata cure-list. Specificity datum: 1 clean + 1 evidence-grounded finding + 0
   fabrications — the symmetric pipeline neither rubber-stamps nor invents.

## 4. Calibration (post-adversarial)

| # | Metric | Lot 6 | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | cross-family | Runner same-family tuple-concordance **4/13 = 0.308** = declared runner-proxy breach (standing artifact); problem-bit agreement **9/13 = 0.692**. TRUE cross-family GLM pass ⏸ (§5). | ≥0.75 | ❌ runner-proxy breach DECLARED · true cross-family ⏸ |
| m2 | certification rate | runner emitted **0.077 (1/13)**; **post-adversarial VALID rate 0.000 (0/13)** — the emitted certification was rejected (§3.4). Both numbers declared; the floor breach is object-level adjudication, not pausable. | [0.20, 0.85] | ❌ breach declared (0 valid; contract hole makes the metric non-computable-as-designed until the runner patch lands) |
| m3 | categories | 5 seen, all closed-7 | closed list | ✅ |
| m4 | tokens/dossier | **avg 200,507.31 (≈200,507)** (2,606,595 / 13 in-scope; controls' 187,313 + 209,149 excluded from numerator AND denominator — symmetric controls now cost ~2× the old leaky ones, the price of symmetry) · **max 229,314 (75002)** | ≤400k | ✅ |
| m5 | gold-set | not run in-lane | ==1.00 | ⏸ cross-family pass (§5) |

Red-team mechanical re-checks (census, m1/problem-bit, m4, divergence rule, 59140
marker, renders, blindness mechanics): **ALL PASS** — the transcription layer held;
the failure was the §3.4 adjudication and the certification contract.

## 5. Open before the Lot 6 cure ships

1. Cross-family GLM pass: m1 sample (5 codes **incl. 75001 AND 80190 — the revoked
   certification MUST be in the blind sample**) + m5-NEG spot (3 from cured set,
   fresh picks) + m5-POS from the v3 pool with the conductor exposed-codes screen
   (burn-list now +2: 01629, 71204).
2. Cure spec `batch_a_lot6.json`: **13/13 detach** (80190 INCLUDED — §3.4 disposition)
   + `_data_note` provenance (75001/75002/75009 → true parents {01621, 75000};
   85321 → {85230, 51108}; 80190 → fill-#1813 record + marker incoherence + 80200
   crosswalk + re-certification path) + the 72101/72103 `_source_relabeled` dispute
   record (70100-precedent wording) + F12 everywhere.
3. **Runner certification-contract patch (BLOCKER 2 — mandatory, ships WITH the cure
   PR):** per-field exposed-facts inventory with `source_locator`/`vintage`/
   `verified|absent` in schema + compiler; kill the circular PP28 NOT_APPLICABLE
   (presence of regulatory facts in the record forces the check); regression test
   "perizinan=[] + Tinggi, no resolvable source → does NOT certify"; both 80190 seats
   re-run under the patched contract before any future certification claim.
   **Precondition for Lot 7.**
4. Standalone metadata cure-list grows: 59140 pp28-label (with 01629, 71204).
5. Surfaces: the proven consumer-map — **13 codes, 80190 INCLUDED**.

## 6. Meta-pattern (the malattia-delle-malattie, program record)

- **The 51108 residual bucket is a SECOND division-crossing fan** (after 68111):
  non-commercial air transport fanning to ~15 unrelated 2025 targets (aviation schools,
  police, meteorology, vocational education, technical testing — incl. 71204, the
  disqualified POS control, and 85321 this lot). Residual/"YTDL" buckets in the 2020
  vintage are collision factories by construction: their children inherit NOTHING
  semantically, and any title-similarity remap across them is near-guaranteed wrong.
- **The symmetric-control upgrade paid off on its first run**: the leaky regime
  certified 59140 three times; the symmetric regime found its real metadata nit AND
  passed the genuinely clean 59201. Specificity is now measurable (wording per the
  adversarial MINOR: seat-surface symmetry proven; full anti-recognition blindness
  would need fresh controls).
- **W100 third generation, now at the VERDICT level: "anche la firma mente."** L1-L5's
  red-teams corrected audit trails; L6's red-team overturned a VERDICT the conductor
  had signed. The failure signature: the conductor eye-verified the layer he was
  primed on (crosswalk) and delegated the OTHER layer (canonical content) to the
  seats' prose. **New conductor rule, effective immediately: a CERTIFICATION requires
  the conductor's own eyes on the FULL canonical record — every asserted field —
  not only on the crosswalk render.** Corollary: "the certifiable class" is not
  "codes that assert nothing" (that class, on this evidence, may be EMPTY — even
  empty-array records assert facts via derivation); it is "codes whose every exposed
  fact carries a verified locator+vintage" — which no record can prove until the
  certification contract implements per-field provenance (§5.3).

## 7. Artifact manifest (immutable pins)

| Artifact | Pin |
| --- | --- |
| Lane run | `wf_dfae986f-5d3` (30 seats, 0 errors) |
| Runner | blob `a3e8ed9dffd343df4b4a3b4333dcedb98e6123b3` = `infra/workflows/kbli-batch-a-lot.js` @ main `548d85b28c62c18b111ea4759c0daa85159d470c` (post-#2778 symmetric blind) |
| Raw output | sha256 `946d5ffb9c0f43e1da977f8da3fb4d540bc9057042242157217450973d013659` (task ws4khx67a output) |
| Journal | sha256 `f84dd916f5bc4d81544e3b6bb3a4bec3f58443e874078db2d492db73b42274a4` (wf_dfae986f-5d3/journal.jsonl, 30 start + 30 result) |
| Canonical @ lane run | sha256 `cf27ab0397d1a22f…` (membership fence, main `548d85b28c`; launcher pin verified identical pre-launch) |
| Render p.408 (by-eye) | sha256 `4c7093c59bdbe3ebb7a403bb842547218bd9913b90bff947097d7a22fb476cfd` |
| Render p.412 (by-eye) | sha256 `89d395c66480bf096fca8e508090408a01a0b87dd40a54cfcfc8451c7dee7728` |
| Red-team transcript | `/tmp/kbli-conductor-a1-0718/lot6-redteam.txt` (full-output capture, no tail — W97; final report lines 8333-8362, 381,811 tokens) |

## Adversarial review — VERDICT AND CURES

Seat: **codex sol xhigh** (read-only) over the FIRST-signed report + raw output (task
ws4khx67a) + journal (wf_dfae986f-5d3) + canonical + renders. **Verdict: FIX-FIRST.**

| Severity | Finding | Cure in this signing |
| --- | --- | --- |
| BLOCKER | 80190 certification materially false ("asserts nothing" refuted by the record's own tiers + frontend derivation) | Certification REVOKED; 80190 → quarantined/pending source resolution, joins cure 13/13 (§3.4) |
| BLOCKER | Runner certification contract never verifies client-facing facts (3-field diff, D2 gated on licensing_inherits, circular PP28 N/A) | Contract patch = mandatory cure deliverable + Lot-7 precondition (§5.3); until then certification is structurally unsafe (§3.4) |
| MAJOR | 80190 record internally incoherent, un-adjudicated | Adjudicated §3.4 (marker incoherence recorded in the detach `_data_note`; alignment of `_source`/`_l2_*`/`pp28_sources` folded into the cure) |
| MAJOR | Outcome/meta-claims/cure depended on the invalid certification | §1 rewritten ("runner emitted 12Q+1C; adversarial review rejects C; zero valid certifications"); m2 dual-declared (§4); cure 12/13 → 13/13 (§5.2) |
| MAJOR | §2 vet wording (`CODICE_RINUMERATO` claimed for all three; parent 01621 omitted everywhere) | §2 corrected: RINUMERATO 75001/75002, MATCH_CON_AGGREGAZIONE 75009, single-parent metadata incomplete for all three |
| MINOR | "TRUE/genuinely blind" over-claimed | Wording restricted throughout: seat-surface symmetric; no marker exposed; no self-identification observed; true blindness needs fresh controls |

All mechanical re-checks (census, m1, m4, divergence, 59140, renders, blindness
mechanics) were independently recomputed by the red-team and PASS.

## Sign-off

**Lot 6 conductor gate: SIGNED — SECOND SIGNING, adversarial pass DONE, all findings
cured in this document.** The 80190 certification is REVOKED (the program still has
zero valid certifications); operational disposition 13/13 quarantined. Cure authorized
to SHIP as 13/13 detach + runner certification-contract patch (per-field provenance +
regression test + 80190 seat re-run), auto-merge armed only after the conductor's gate
on the diff. Cross-family GLM pass (m1 sample MUST include 80190) precedes surfaces.
The certification-contract patch is a PRECONDITION for Lot 7. — Conductor (Fable,
MANDATO S2), 2026-07-19.

## Appendix A — TRUE cross-family pass (GLM 5.2 vision), conductor-adjudicated

**Seat:** GLM 5.2 (`glm-5.2[1m]`, api.z.ai) via `claude --print` with
`CLAUDE_CONFIG_DIR=~/.claude-glm` + keychain token — a DIFFERENT model family from the
lane's seats (W100 discipline). Invocation gotcha recorded: inline `ANTHROPIC_API_KEY=`
env prefixes are hard-denied by global settings deny-rules regardless of value — the
runner logic must live in a script FILE invoked via `bash`. 15/15 calls (5 m1 × 2 +
3 NEG + 2 POS), 0 auth errors, 0 missing renders; one recoverable hiccup (3 in-flight
GLM subprocesses killed by an external session cleanup, relaunched detached via
`nohup`/`disown`, zero data loss).

**Design (upgraded from the Lots 2-5 single-call pattern):** per m1 code, TWO fully
independent GLM processes — Call A = image-only blind crosswalk extraction (zero
canonical, zero lane verdicts); Call B = fresh process, same images + canonical
excerpt, contradiction verdict, still blind to lane verdicts. Rationale: never re-feed
Call A's own prose into Call B — the seat-level analogue of the prose-contamination
failure this report's §6 diagnosed at the conductor level.

### A.1 — m1 blind re-extraction (5 codes, 80190 mandatory): 5/5 non-contradictory

| Code | Lane category | Call A (image-only) | Call B (contradiction) | Conductor adjudication |
| --- | --- | --- | --- | --- |
| 75001 | code_collision | MANY_TO_ONE {01621, 75000} ✓ | PARTIAL (canonical omits 01621) | Independent re-derivation of the vet-trio defect |
| 80190 | certified→REVOKED | **ABSENT — seat MISS** | **EXACT_MATCH** ("80200→80190" on both pages) | Split verdict: crosswalk fact CONFIRMED (Call B + seat's own eye-read ×2 + conductor §2); Call A miss is a seat defect, not a data defect |
| 72103 | source_absent_in_vault | 1:1 clean ✓ | EXACT_MATCH | Consistent (defect lives in the PP28/provenance layer, outside m1's crosswalk scope) |
| 75009 | wrong_authority_level | MANY_TO_ONE {01621, 75000} ✓ | PARTIAL (canonical omits 01621) | Independent re-derivation |
| 85321 | payload_cross_contamination | **wrong row-set — seat misread** | CONTRADICTION (= lane category, exact) | Split verdict: Call B + seat eye-read confirm; Call A misread |

**m1 = 5/5 non-contradictory with the lane's dispositions (3/5 independently
re-derive the specific defect) → the ⏸ in §4 resolves to PASS at the true
cross-family level.** Named finding — **intra-seat vision non-determinism**: Call A
scored 3/5 against ground truth (missed the 80190 row entirely on the very render
where it is unambiguous; misattributed 85321's rows) while Call B scored 5/5.
**Conductor rule for future lots: Call A is a SUPPLEMENTARY signal only, never
standalone** — a blind-image ABSENT from a single vision pass is a lead, not a fact
(W100 line extended to the cross-family seat itself).

### A.2 — m5-NEG (3 fresh picks, blind, tells redacted): 2/3 HONEST + 1 REAL DEVIATION

- **64920** (Lot 3): HONEST — clean detached state.
- **66153** (Lot 4): HONEST — minor same-shape wrinkle noted, not escalated.
- **52105** (Lot 2): **DEVIATION — a real, already-shipped bug found by the control**:
  `l4_bali` asserts `confidence:"HIGH"`, `needs_review:false`, `blocked:true` for the
  Bali PMA moratorium keyed on `kategori_risiko:"Menengah Rendah"` — a value that now
  exists ONLY inside `per_skala_disputed_pp28_collision`, the block the record's own
  `_data_note` disowns. The seat's finding was **independently re-verified by a direct
  read of origin/main** (byte-for-byte, not a GLM artifact). Same disease shape as the
  80190 certification blocker (§3.4) — a DERIVED surface still certifying a disowned
  value — on a code shipped two lots ago. **Disposition: 52105 l4_bali joins the
  standalone cure-list; a program-wide census of every `*_disputed_*`-carrying code
  for stale `l4_bali`/editorial derived fields is COMMISSIONED (read-only sweep in
  flight at this signing).** This validates rule #7 (derived layers need invalidation)
  as an enforcement gap in the Lots 1-5 cure pattern, not just a doctrine line.

### A.3 — m5-POS (v3 believed-good pool, conductor draw): 1/2 CLEAN + 1/2 SUSPECT

Screen: pool {01629, 71204, 58219, 81300, 50122, 93210, 74112, 46620} minus burn-list
{01629, 71204}; exposure screened three ways (seat grep + independent second agent +
conductor's own grep over all gate reports/corner/batch-reports) — zero hits.
**Conductor draw: 58219 + 93210; 74112 alternate (unused); 50122 EXCLUDED** — its
same-digit self-cite pattern is the exact FATAL-4 signature that burned both prior
draws; a candidate with high a-priori contamination risk measures nothing as a
positive control.

- **93210** (theme parks, aggregation): **CLEAN — the program's FIRST genuinely clean
  positive control.** Sector-coherent licensing, transparent inferred-tier disclosure,
  `MATCH_CON_AGGREGAZIONE` consistent with `pp28_sources` [93219, 93211].
- **58219** (video-game software publishing): **SUSPECT — a NEW contamination
  signature.** 8 of 14 per_skala entries carry full PPMSE/PSP e-commerce-intermediary
  licensing text, and `per_skala_legacy.pb_umku` carries DEFENSE-INDUSTRY permits
  (Izin Penetapan Industri Pertahanan et al.) — neither belongs to game publishing.
  Two independent reads agree (GLM cross-family + a blind direct-JSON verification
  that never saw GLM's output). Mapping metadata itself is coherent (58200→58219) —
  the disease is payload FUSION, not remap: a different signature from FATAL-4's
  same-digit self-cite. **Root cause NOT yet adjudicated** (upstream-OSS artifact
  faithfully mirrored vs pipeline-side fusion): a vault-probe comparison against the
  pinned OSS blobs for 58219 is the commissioned next step — no detach authorized on
  this evidence alone (the record class is OSS-native, out of Batch-A membership).

**m5 program ledger after this pass: POS draws to date = 1 clean / 3 contaminated
(01629, 71204, 58219 — three DIFFERENT signatures). The "believed-good" v3 pool is
measurably diseased; this is the strongest FATAL-4 evidence yet and goes to Zero
(operator[business], Legge 5) with the standing GO/NO-GO question on the verified-set
sweep (~1,336 codes).** m5 ==1.00 limit: **breach DECLARED** (NEG 2/3, POS 1/2) —
adjudicated as OBJECT-LEVEL world findings (both deviations independently
text-verified), not pipeline false-positives; the metric is doing exactly its job.

### A.4 — Conductor dispositions from this pass

1. Call A demoted to supplementary-only (A.1) — protocol note for Lot 7.
2. 52105 `l4_bali` cure + program-wide disputed-derived-fields census (A.2) — census
   in flight; cure PR follows it.
3. 58219 vault-probe root-cause investigation (A.3) — commissioned.
4. FATAL-4 dossier updated with the 1/3-clean POS ledger (A.3) — to Zero.
5. Gate ships: cure PR #2800 (13/13 + certification-contract patch) conductor-gated
   and auto-merge armed BEFORE this appendix; surfaces follow its merge.

— Conductor (Fable, MANDATO S2), Appendix A adjudicated 2026-07-19.
