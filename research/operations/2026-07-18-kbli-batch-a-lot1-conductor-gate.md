---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 1 conductor gate + GO package)
adversarial_review: codex (3 passes, family-independent) + GLM-5.2 blind second extractor
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§8 A-1..A-3)"
  - "calibration: data/kbli-filiera/batch-reports/batchA-calibration.md (SIGNED f5892d39; pin interpretation per A-3)"
  - "lane report: research/operations/2026-07-18-kbli-batch-a-lot1-complete-e1.md (PR #2695)"
  - "dossiers: data/kbli-filiera/dossiers/*.jsonl (13 codes, hash-chained D0→D5, PR #2695)"
  - "evidence: mini:~/nuzantara-vault-evidence/batch-a/ + gold-conductor-0718/ (vault manifest e7d25a37)"
  - "cure spec: scripts/kbli_filiera/cure_specs/batch_a_lot1.json (this session)"
---

# GARUDA-FILIERA Batch A — Lot 1 CONDUCTOR GATE (D6 + cross-family tightening) + GO package

> Mandate S2 "GARUDA-FILIERA" (2026-07-18): the conductor session (Fable 5, mente immobile) runs the
> empirical final gate on LANE-E1's Lot 1 (13 codes, divisions 01→39, PR #2695), applies the
> anti-circular-IAA seat correction (blind cross-family second extractor + family-independent
> refuter), injects the calibration gold sets + mutations, adjudicates quarantines, and signs the
> lot. GO-recommendation ≠ GO-execution: no lot beyond this one runs without Zero's explicit GO.

## 1. Verdict

**Lot 1 PASSES the conductor gate, with the conductor FLIPPING SEVEN lane verdicts (all
clean→quarantine) on cross-family evidence — every flip verified by eye on the canonical payloads
and vault records before adjudication.**

| Outcome | Codes |
| --- | --- |
| **QUARANTINE → honest-gap cure (12)** | 01700, 02409, 05102, 38122, 39001 (lane-proposed, conductor-confirmed at D6) + **02402, 38222** (Codex-refuter flips) + **05200, 01287, 02201, 08920, 36003** (blind-GLM flips) |
| **CERTIFIED CLEAN (1)** | 19206 |

Final conductor-adjudicated certification rate: **1/13 = 0.077** — an m2 floor BREACH, acknowledged
and root-caused in plan §8 **A-4** (population disease ~92%, not seat drift; the A-serving class IS
the July silent-fill disease by construction). A new refutation category (payload cross-
contamination) triggered the m3 pause — triaged in-gate, registry extension proposed (plan §8
**A-5**). The cure spec for the 12 is `scripts/kbli_filiera/cure_specs/batch_a_lot1.json`
(compiler dry-run: 12 to cure, 0 problems); the data apply lands in its own PR with the A6
per-surface release checklist.

**Disease census of the 12 (each conductor-verified by eye):**

| Flavor | Codes | What was actually served |
| --- | --- | --- |
| payload cross-contamination | 02402, 02201 (seed-certification blob), 08920 (salt-extraction marine regime: 'fasilitas pengambilan air laut', ≤12/>12-mil jurisdiction), 01287 (generic agriculture on narcotic-crop code) | licensing rows whose CONTENT belongs to a different activity |
| regime mismatch across split | 05102 (mining-concession IUP on beneficiation), 38122/38222 (generic hazardous-B3 on the radioactive class), 39001 (storage-exploration + marine-pollution rows on capture) | a real PP28 row that does not substantively cover the 2025 activity |
| non-inheritable ancestry | 01700 (6-way merge, single-ancestor inherit), 02409 (many-to-many) | structure that cannot single-inherit |
| phantom source pointer | 05200, 36003 (+ the absence half of 01287/02201/08920) | pp28_sources cites a row ABSENT from the pinned corpus as hunted (11,208 pages) |

## 2. Seat map as actually run (degradations DECLARED)

| Role | Planned (mandate) | Actual | Note |
| --- | --- | --- | --- |
| Extractor #1 (D1/D5 lane) | Sonnet 5 | Sonnet 5 (LANE-E1, PR #2695) | same-family D5 — the very gap this gate closes |
| Extractor #2, BLIND | GLM 5.2 | **GLM 5.2, WITH vision** (probe: read code 05100/row 24 off the 300-dpi render) | zero visibility of Sonnet output; 29 codes = 13 lot + 16 gold, deterministic shuffle |
| Refuter of verdicts | Gemini 3.1 Pro (agy) | **Codex GPT-5.6 (sol xhigh / terra high)** | **agy seat DEAD** (3 probes hung >20min, CONTEXT_AUTH per arsenal report) → declared cascade to the other non-extractor family. Family-independence preserved: OpenAI ≠ Anthropic(Sonnet) ≠ Zhipu(GLM). PENDING-ARMS line filed for the agy seat. |
| Vision locator | qwen2.5vl (Mini) | not needed | GLM read renders directly; conductor read by eye |
| Final gate | Fable 5 (this session) | Fable 5 (this session) | non-delegable, 10 dossiers by eye |

## 3. Conductor D6 — raw-evidence gate (100% quarantines + 5 deterministic random)

Random rule: 5 lowest sha256(code|"d6-random") among the 8 lane-clean codes → 08920, 02201, 19206, 05200, 36003.

| Dossier | What the conductor verified BY EYE | Verdict |
| --- | --- | --- |
| 01700 (Q) | Lampiran 5 p.134: SIX rows 01711/01712/01713/01714/01715/01719 → 01700. Merge 6→1 real; single-ancestor per_skala inherit unjustifiable | CONFIRMED |
| 02409 (Q) | Lampiran 5 p.136: 02404→02409, 02409→02401, 02409→02409 — many-to-many real | CONFIRMED |
| 05102 (Q) | PP28 I.D.202 row 24 filed under 05100 (pre-split): IUP Tahap Eksplorasi / RKAB / Studi Kelayakan — mining-concession regime; 05102 uraian excludes mining. Crosswalk split 05100→{05101,05102} seen on p.144 | CONFIRMED |
| 38122 (Q) | Lampiran 5 p.170: 38120 → {38121 non-radioactive, 38122 radioactive} split real | CONFIRMED |
| 39001 (Q) | p.170: 39000 → {39001 capture, 39002 storage, 39009 remediation}; PP28 I.D.1022 row 68 = carbon-INJECTION-zone exploration (storage-side, 'Wilayah Izin Penyimpanan Karbon'); PP28 I.I.406 row 88 = marine pollution response. Neither is capture | CONFIRMED |
| 08920 (R) | p.145: 08920 Ekstraksi Tanah Gemuk→Gambut (Peat), 1:1 terminology fix | CONFIRMED clean |
| 02201 (R) | p.135: 02201 Pemanenan Kayu → 02201, clean 1:1 | CONFIRMED clean |
| 19206 (R) | p.154: 19291 → {19205, 19206 biofuel-blending, 19209}; PP28 I.F.1925 row 187 = 19291 'Seluruh' generic industry regime (Sertifikat Standar, Menengah Rendah) — substantively covers the blending leg | CONFIRMED clean |
| 05200 (R) | p.144: 05200 Pertambangan Lignit → 05200, 1:1 | CONFIRMED clean |
| 36003 (R) | p.170: 36003 → 36003, 1:1 | CONFIRMED clean |

**Anti-poisoning probe:** page 202 of PP28 394933 regenerated on Mini from the sha256-pinned PDF
(`pdftoppm -r 300`; PDF sha256 == manifest `8ad5155a…`) is **byte-identical** to the evidence render
(sha256 `2d4fecf461b15882…` both). Render pipeline deterministic; evidence not poisoned.

No seat hallucination found in any of the 10 dossiers: every load-bearing digit/row cited by D1/D5
matched what the conductor saw on the renders.

## 4. Cross-family refuter (Codex) — the pass that PAID

Three parallel passes over per-code "verdict packs" (D1+D5+canonical claims, no images):
R1 = 5 quarantined (sol, xhigh) · R2 = 8 clean (terra, high) · R3 = 2 MUTATED packs (terra, high).

- **R1: all 5 quarantines confirmed in substance.** 05102 and 39001 explicitly sound; on
  01700/02409/38122 the refuter "flipped toward quarantine" — which IS the recorded outcome: it was
  misled by the lane's `D5.verdict='certified'` label on quarantine-agreeing dossiers. **Program
  finding: the pilot's criterion-#6 taxonomy deviation RECURRED and actively confuses third-party
  consumers — normalize D5 verdict labels (e.g. `concur-quarantine`) before the next lot.**
- **R2: 3 flip candidates (02402, 19206, 38222). Conductor re-grounded each on the actual canonical
  payloads:**
  - **02402 FLIP UPHELD** — per_skala persyaratan are forest-SEED-certification content ('sertifikat
    sumber benih', 'sarana perbenihan') on a forest-area-USE services code; pp28_sources=['02402'] is
    a bare-digit join (true ancestor is 02401-2020, seen on p.135). Lane false negative: D1/D5
    certified the crosswalk but never compared payload CONTENT to activity scope; D4 scan silent.
  - **38222 FLIP UPHELD** — payload is a generic B3/PSLB3 regime ('Persetujuan Teknis Dirjen PSLB3',
    kewajiban on 'Limbah B3') on the RADIOACTIVE-waste class, inherited from generic 38220. Same
    disease as 38122. (The refuter's specific "render_ref contradiction" claim was NOT in the dossier
    — a W65 partial hallucination; the flip stands on the conductor-verified payload evidence, not on
    that claim. The dossier's D2 self-confirm was nonetheless protocol-weak: `neighboring_codes: []`.)
  - **19206 DISSENT REJECTED** — the refuter wants a categorical no-inheritance-across-splits rule;
    the pre-registered criterion (A2) requires ADJUDICATION, not prohibition. The 19291 PP28 row is
    'Seluruh'-scoped and generic-industrial; it substantively covers the blending leg (pilot precedent
    43216/43223). 19206 stays clean, dissent recorded.
- **R3 (mutations): 2/2 CAUGHT** — both injected packs (fields-vs-narrative contradiction on 08920;
  ONE_TO_ONE fields with split narrative on 02201) refuted with exact diagnoses.
- Additional accepted refuter finding: 01700's PP28 ABSENT hunt covers ancestor 01711 only (verified
  in pp28/ABSENT.json: sources_hunted=['01711']) — the cure-spec data_note was re-scoped to claim
  absence only as hunted. A per-ancestor hunt rule goes into the GO package.
- Deferred (P1-v2, facet abstain): refuter flags 38122 `pma_status=TERBUKA` as implausible for a
  BAPETEN-class activity — recorded for the Perpres-10/49 audit wave, NOT touched this pass.

## 5. Compiler mutation probes

- Unresolvable evidence_ref → dossier_assemble.py REFUSED (RC=1), no event written. ✓
- Divergent same-stage rewrite → REFUSED (DivergentRewriteError, RC=1), chain intact. ✓

## 6. Blind cross-family extraction (GLM 5.2, vision) — IAA + gold reveal

> 29 blind extractions: the 13 Lot-1 codes + all 16 calibration gold controls, deterministic
> shuffled order, evidence-only prompts (no Sonnet output, no knowledge of which codes are controls).
> 29/29 completed, 0 unparsed. Wall-clock: avg 290s/code (min 121s, max 808s), ~71 min total at
> parallelism 3, flat GLM Coding Plan (zero marginal cost).

**IAA (the anti-circular measurement the mandate ordered):**

- GLM-blind vs **lane D1** verdicts: **5/13 = 0.385** — LOW, and that is the finding, not a seat
  failure: the lane's 8 "clean" contained 7 false-negatives that the same-family D5 could not see.
  The lane-internal m1 (Sonnet-D1 vs Sonnet-D5) measured 0.923 on the same dossiers — same-family
  agreement OVERSTATES truth by construction (§8).
- GLM-blind vs **final conductor adjudication**: **12/13 = 0.923** — the blind cross-family
  extractor and the conductor's eye-verified adjudication converge; the single dissent is 19206
  (GLM quarantines on strictness the pre-registered A2 criterion does not require; the 19291 PP28
  row is 'Seluruh'-scoped and image-verified matching — 19206 stays clean, dissent recorded).
- Mapping-structure agreement (all seats, all 13): 13/13 — crosswalk structure is never where the
  disease lives; content is.

**Gold reveal (post-lot, per calibration §5 reveal rule):**

- NEGATIVE plaintext: 68112, 49213, 51103, 51203, 20111, 50115, 60312, 64310 (digests verified ==
  signed calibration). **8/8 SURVIVED**: no control re-certified its refuted licensing. 49213
  adjudication note: GLM refuses the refuted OLD-49213/AKDP source AND identifies the
  crosswalk-correct predecessor 49413 (PP28 I.I p.65, Wali Kota, image-read digits) as certifiable
  — this is the completion the fase-1 cure explicitly deferred ('pending a D2 image-extraction of
  49413's rows'), recorded as a candidate for a provenance-backed restore, not a gap violation.
- POSITIVE plaintext: 47401, 32902, 46737, 28262, 36002, 47732, 50121, 46204 (digests verified ==
  signed calibration). **8/8 on the registered substance** (no control's OSS-native per_skala was
  refuted; licensing_inherits=true wherever asserted). Three controls raised TRUE collateral
  findings OUTSIDE the control's registered scope, all conductor-verified: 47732 status_mapping
  says MATCH_LANGSUNG but the crosswalk is a 4→1 MERGE (47732+47875+47919+47999); 28262 is a
  RENUMBERING from 28263 (same-digit 2020-28262 is a different activity → collision class) yet
  claims 'code and scope unchanged'; 36002 OSS seawater-scope rows (36002-03-02/04-03) may require
  ALSE permits the canonical row omits. **m5 halt clause evaluated and NOT triggered** — no control
  was contradicted in its registered substance; the three metadata/completeness flags are logged to
  the watchlist and the POS-hit definition is re-registered more precisely for the remainder (§10).

## 7. Calibration m1–m5 (final, over the A-2 lot)

| # | Metric | Lot 1 final | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | blind concordance — lane-internal (D1 vs D5, same family) | 0.923 | floor 0.75 | ✅ formally; see §8 — it measured fidelity, not truth |
| m1-x | blind concordance — cross-family (GLM vs final adjudication) | 0.923 (12/13) | (not yet registered) | proposed as the REAL m1 for the remainder |
| m2 | certification rate (conductor-adjudicated) | **0.077 (1/13)** | [0.20, 0.85] | ❌ **floor BREACH → plan §8 A-4 resume note** (population disease ~92%, not drift; advisory-floor 0.0 proposed for A-serving lots) |
| m3 | refutation categories | + `payload_cross_contamination`, `mapping_metadata_false` | closed list | ⚠️ **new-category pause → triaged in-gate, plan §8 A-5** (registry extension proposed) |
| m4 | tokens/dossier (lane) | ~208k avg | ceiling 400k | ✅ |
| m5 | gold-set hit rate | NEG 8/8 · POS 8/8 registered-substance (3 true collaterals logged) | 1.00, any miss halts | ✅ halt clause evaluated, not triggered — adjudication in §6, wording tightened for the remainder |

## 8. §Meta-pattern (the disease-of-diseases this lot exposes)

**Same-family blind agreement measures transcription fidelity, not truth.** The Sonnet D1/D5 pair
reproduced crosswalk structure flawlessly (0 hallucinations at D6 across 10 dossiers, 13/13 mapping
agreement across all seats) and still shipped **7 false-clean verdicts out of 13 (54%)**. The
false-negatives share ONE shape: **a licensing payload whose CONTENT belongs to another activity or
whose SOURCE does not exist, sitting behind a structurally-plausible provenance pointer.** The lane
verified structure (crosswalk); truth lives in content (payload semantics vs activity scope,
source existence in the corpus). Same-family seats share the same blind spot; the conductor's own
first D6 pass shared it too (it re-read the evidence the lane CITED, not the claims the lane never
examined) — caught only because two independent cross-family seats attacked the same dossiers with
different priors: Codex found 2 (02402, 38222), blind-GLM found 4 more (05200, 01287, 02201,
08920/36003) plus independent confirmation of every lane quarantine. The chain of upstream
defective beliefs is now three deep: *"the code number is a stable key across vintages"* (pilot) →
*"a provenance pointer is a content check"* (this lot) → *"agreement between same-family seats is
evidence of truth"* (this lot, the process-level corollary the GO package §10.1 kills). Measured
disease prevalence in the first true-random A-serving slice: **12/13 ≈ 92%** — the ~221-code
no-scope class must be presumed near-totally contaminated until each code proves otherwise.

## 9. §Solo-operatore

- **Zero (Legge 5): the Batch-A remainder GO** (§10). This report recommends; it does not execute.
- **Zero: agy seat re-auth** (interactive OAuth on Pro) — the Gemini refuter tier stays dead until a
  human completes the browser auth flow. (PENDING-ARMS line filed.)
- Nothing else in this lot requires operator hands: cure PR, KG/Qdrant detach, cache bust, fleet
  align are session-owned (§11 ship plan).

## 10. GO package — Batch A remainder (101 codes: 114 − 13)

**Recommendation: GO, with the lane protocol AMENDED as below (all fixes are cheap, all were
measured to pay this lot).**

1. **Cross-family refutation becomes part of the LANE protocol, not a conductor tightening.** The
   D5 seat on every dossier must be a different FAMILY from D1 (GLM 5.2 blind with vision, or Codex
   on text-packs), not a second Sonnet. Measured yield this lot: 7/13 false-clean caught by
   cross-family passes (2 Codex refuter + 5 GLM blind-with-vision) that same-family D5 missed;
   cost ≈ flat-subscription tokens, ~2–13 min/code wall on GLM.
2. **D4 gains a content-vs-scope check**: compare per_skala persyaratan/kewajiban SEMANTICS against
   the code's uraian scope; any cross-activity vocabulary (e.g. seed-certification terms on an
   area-use code) → automatic quarantine proposal. This closes the exact false-negative shape.
3. **Normalize the D5 verdict taxonomy** (`concur-quarantine` / `concur-clean` / `refute`) — the
   pilot's criterion-#6 deviation confused a third-party seat this lot; frozen tokens only.
4. **Per-ancestor ABSENT hunts**: a MERGE code's PP28 absence claim requires a hunt per ancestor
   (01700 lesson), else the note is scoped "as hunted".
5. **D2 self-confirm hard rule**: `neighboring_codes` must be non-empty (38222's was []), else the
   extraction does not count as image-verified.
6. Cadence/cost basis (Legge 7): lane ≈ 208k Sonnet tok/code (E1 measured); conductor plane ≈
   10 render reads + orchestration per ~13-code lot; GLM blind pass ≈ 290 s avg per code (min 121 s,
   max 808 s; 29 codes ≈ 71 min wall at par=3, flat plan); Codex 3 calls/lot (flat plan). At this
   cadence the 101-code remainder ≈ 8 lots of ~13, each gate-able in a single conductor session.
7. **FIREBREAK unchanged**: this is a GO-recommendation. No lot beyond Lot 1 starts without Zero's
   explicit GO (Legge 5). Findings vs BKPM/OSS stay INTERNAL (ruling 2026-07-16).

## 11. Ship plan for this lot (session-owned)

- PR-A (this report + plan A-3 + cure spec) — docs-only, auto-merge on green.
- PR-B (data): compiler `--apply` → canonical vNext + 4-copy sync + sidecar bump + registry test
  `test_kbli_batch_a_lot1_registry.py` + A6 per-surface release checklist:
  canonical ✓ · mouth SSR (Vercel rebuild + curl probe) · gold N/A (none of the 12 in gold,
  verified this session against all 428 gold records) · KG: 12 nodes with live REQUIRES edges,
  142 total (01700:12, 02402:2, 02409:34, 05102:2, 38122:17, 38222:2, 39001:26, 05200:2, 01287:15,
  02201:2, 08920:9, 36003:19 — all counted on prod this session) → `kg_kbli_license_fix.py` detach
  (#2596 pattern) · Qdrant `kategori_risiko` clear (#2597 pattern) · `inspect_kbli` cache bust ·
  native kbli-navigator rebuild (fleet align).
- PR #2695 (LANE-E1 dossiers): conductor gate PASSED → undraft + merge (dossiers are the immutable
  evidence trail; lot-report statements it contains that this gate superseded — the 8-clean count —
  are corrected by THIS report, which post-dates it).

## Sign-off

Conductor gate: **SIGNED — Fable conductor session (MANDATO S2), 2026-07-18.**
Re-affirmed after the §6 blind census and §7 calibration table landed: the 12-quarantine / 1-clean
verdict incorporates every seat's evidence (lane D1/D5, Codex refuter, GLM blind census, conductor
D6 on raw canonical + vault renders); the two calibration breaches (m2, m3) are DECLARED with
amendments A-4/A-5 filed in the plan, not silently absorbed. Lot 1 cure spec is emit-ready;
GO-recommendation for the Batch-A remainder stands as §10 — execution remains behind Zero's
explicit GO (Legge 5).
