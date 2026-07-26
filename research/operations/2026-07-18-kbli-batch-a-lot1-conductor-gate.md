---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A — Lot 1 conductor gate + GO package)
adversarial_review: codex
adversarial_review_detail: "codex: 3 refuter passes + full-report red-team + verify pass (gpt-5.6-sol xhigh, family-independent) · glm-5.2: blind second extractor with vision (29 codes)"
sources:
  - "plan: research/operations/2026-07-18-kbli-batch-a-plan.md (§8 A-1..A-6; the signed conclusion depends centrally on A-4/A-5/A-6)"
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

**Lot 1's conductor gate is COMPLETE and SIGNED — outcome: 13/13 quarantine, 0 certified, and the
program is HALTED (m5 NEG breach, plan A-6(b)).** The conductor FLIPPED EIGHT lane verdicts (all
clean→quarantine): seven on cross-family content evidence — each verified by eye on the canonical
payloads and vault records before adjudication — and one (19206) under the plan's preregistered
divergence rule after the post-signing red-team showed the conductor's own "clean" was a picked
verdict in a two-seat divergence (plan §8 A-6). The gate is deliberately NOT labeled "passed": a
lot whose NEG control missed is halted by the preregistered calibration-§5 rule, and a halted gate cannot
certify. What DOES proceed is the fail-safe cure of the 13 (detaching an uncertifiable payload is
protective and requires no certification — rule #4, detach > plausible remap); certification of
any code and any further lot sit behind the halt resolution, the A-6 preconditions, and Zero's GO.

| Outcome | Codes |
| --- | --- |
| **QUARANTINE → honest-gap cure (13)** | 01700, 02409, 05102, 38122, 39001 (lane-proposed, conductor-confirmed at D6) + **02402, 38222** (Codex-refuter flips) + **05200, 01287, 02201, 08920, 36003** (blind-GLM flips) + **19206** (divergence-rule flip, A-6(a)) |
| **CERTIFIED CLEAN (0)** | — |

Final conductor-adjudicated certification rate: **0/13 = 0.000** — an m2 floor BREACH, and the
preregistered cross-family m1 (GLM-blind vs lane D1: 0.385) is ALSO a floor breach; both are
acknowledged and root-caused in plan §8 **A-4** (population disease + lane content-blindness, not
seat drift; the A-serving class IS the July silent-fill disease by construction — and no
extrapolation beyond this taxonomy-ordered segment is claimed). New refutation categories
(payload cross-contamination, unresolvable source pointer) triggered the m3 pause — triaged
in-gate, registry extension proposed (plan §8 **A-5**). The m5 NEG control 49213 is a formal miss
→ BREACH + declared halt (plan §8 **A-6(b)**). The cure spec for the 13 is
`scripts/kbli_filiera/cure_specs/batch_a_lot1.json` (compiler dry-run: 13 to cure, 0 problems;
receipts in §12); the data apply lands in its own PR with the A6 per-surface release checklist.

**Disease census of the 13 (each conductor-verified by eye):**

| Flavor | Codes | What was actually served |
| --- | --- | --- |
| payload cross-contamination | 02402, 02201 (seed-certification blob), 08920 (salt-extraction marine regime: 'fasilitas pengambilan air laut', ≤12/>12-mil jurisdiction), 01287 (generic agriculture on narcotic-crop code) | licensing rows whose CONTENT belongs to a different activity |
| regime mismatch across split | 05102 (mining-concession IUP on beneficiation), 38122/38222 (generic hazardous-B3 on the radioactive class), 39001 (storage-exploration + marine-pollution rows on capture) | a real PP28 row that does not substantively cover the 2025 activity |
| non-inheritable ancestry | 01700 (6-way merge, single-ancestor inherit), 02409 (many-to-many) | structure that cannot single-inherit |
| unresolvable source pointer | 05200, 36003 (annotative overlap: 01287/02201/08920 above ALSO carry an unresolvable-source half; primary bucket = cross-contamination) | pp28_sources cites a row not retrievable from the pinned corpus as hunted (11,208-page text-hunt; nonexistence NOT asserted — an earned ABSENT needs the plan-A5 image-grade scan) |
| split-generic-payload + false mapping metadata | 19206 (generic pre-split 19291 basket payload; Besar row not on the pinned page; status_mapping 'CODICE_RINUMERATO' vs image-verified 3-way split) | a 'Seluruh'-scoped generic row inherited across a split, quarantined under the divergence rule (A-6(a)) |

## 2. Seat map as actually run (degradations DECLARED)

| Role | Planned (mandate) | Actual | Note |
| --- | --- | --- | --- |
| Extractor #1 (D1/D5 lane) | Sonnet 5 | Sonnet 5 (LANE-E1, PR #2695) | same-family D5 — the very gap this gate closes |
| Extractor #2, BLIND | GLM 5.2 | **GLM 5.2, WITH vision** (probe: read code 05100/row 24 off the 300-dpi render) | zero visibility of Sonnet output; 29 codes = 13 lot + 16 gold, deterministic shuffle |
| Refuter of verdicts | Gemini 3.1 Pro (agy) | **Codex GPT-5.6 (sol xhigh / terra high)** | **agy seat DEAD** (3 probes hung >20min, CONTEXT_AUTH per arsenal report) → declared cascade to the other non-extractor family. Family-independence preserved: OpenAI ≠ Anthropic(Sonnet) ≠ Zhipu(GLM). PENDING-ARMS line filed for the agy seat. |
| Vision locator | qwen2.5vl (Mini) | not needed | GLM read renders directly; conductor read by eye |
| Final gate | Fable 5 (this session) | Fable 5 (this session) | non-delegable; initial D6 sample = 10 dossiers by eye (§3), then EVERY cross-family flip re-verified by eye at flip time (canonical payload + cited renders) → final by-eye coverage 13/13 |

## 3. Conductor D6 — raw-evidence gate (100% quarantines + 5 deterministic random)

Random rule: 5 lowest sha256(code|"d6-random") among the 8 lane-clean codes → 08920, 02201, 19206, 05200, 36003.

| Dossier | What the conductor verified BY EYE | Verdict |
| --- | --- | --- |
| 01700 (Q) | Lampiran 5 p.134: SIX rows 01711/01712/01713/01714/01715/01719 → 01700. Merge 6→1 real; single-ancestor per_skala inherit unjustifiable | CONFIRMED |
| 02409 (Q) | Lampiran 5 p.136: 02404→02409, 02409→02401, 02409→02409 — many-to-many real | CONFIRMED |
| 05102 (Q) | PP28 I.D.202 row 24 filed under 05100 (pre-split): IUP Tahap Eksplorasi / RKAB / Studi Kelayakan — mining-concession regime; 05102 uraian excludes mining. Crosswalk split 05100→{05101,05102} seen on p.144 | CONFIRMED |
| 38122 (Q) | Lampiran 5 p.170: 38120 → {38121 non-radioactive, 38122 radioactive} split real | CONFIRMED |
| 39001 (Q) | p.170: 39000 → {39001 capture, 39002 storage, 39009 remediation}; PP28 I.D.1022 row 68 = carbon-INJECTION-zone exploration (storage-side, 'Wilayah Izin Penyimpanan Karbon'); PP28 I.I.406 row 88 = marine pollution response. Neither is capture | CONFIRMED |
| 08920 (R) | p.145: 08920 Ekstraksi Tanah Gemuk→Gambut (Peat), 1:1 terminology fix | initial CONFIRMED clean — **SUPERSEDED by the blind-GLM content flip** (§6/§8: the crosswalk 1:1 was true, but the payload CONTENT is a salt-extraction marine regime; the D6 random check verified structure only) |
| 02201 (R) | p.135: 02201 Pemanenan Kayu → 02201, clean 1:1 | initial CONFIRMED clean — **SUPERSEDED by the blind-GLM content flip** (payload is a seed-certification blob; structure-only check) |
| 19206 (R) | p.154: 19291 → {19205, 19206 biofuel-blending, 19209}; PP28 I.F.1925 row 187 = 19291 'Seluruh' generic industry regime (Sertifikat Standar, Menengah Rendah) — read at the time as substantively covering the blending leg | initial CONFIRMED clean — **SUPERSEDED by the A-6 divergence-rule flip** (two cross-family seats dissented; plan §3 forbids picking in divergence; the p.525 render also carries ONLY the Kecil/Menengah block, so the served Besar row was never certifiable). Kept in the table as the honest historical record of the conductor's own miss |
| 05200 (R) | p.144: 05200 Pertambangan Lignit → 05200, 1:1 | initial CONFIRMED clean — **SUPERSEDED by the blind-GLM source flip** (the cited pp28 source row is not retrievable from the pinned corpus as hunted; structure-only check) |
| 36003 (R) | p.170: 36003 → 36003, 1:1 | initial CONFIRMED clean — **SUPERSEDED by the blind-GLM source flip** (same class as 05200; structure-only check) |

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
  - **19206 DISSENT — initially rejected, then UPHELD via A-6.** The conductor first rejected the
    dissent on A2 semantic grounds (the 19291 row is 'Seluruh'-scoped; pilot precedent 43216/43223).
    The blind-GLM census (§6) then independently quarantined 19206 too — making it a TWO-seat
    cross-family divergence against the conductor's clean, and plan §3 is binding: "Divergence →
    QUARANTINE, never averaged or picked." The initial rejection was itself a picked verdict (the
    full-report red-team caught this); the p.525 render also carries only the Kecil/Menengah block,
    so the served Besar row was never certifiable, and status_mapping 'CODICE_RINUMERATO' is
    contradicted by the image-verified 3-way split. **19206 QUARANTINED (A-6(a)).**
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
- GLM-blind vs **final conductor adjudication**: **13/13 = 1.000 after the A-6 flip** (12/13 =
  0.923 pre-flip, the sole dissent being 19206 — resolved by quarantining it under the divergence
  rule, not by picking the conductor's reading). Caveat, per the red-team: this figure is
  INFORMATIONAL, not an independence measure — the GLM findings informed the final adjudication,
  so it cannot serve as the preregistered m1 (see §7).
- Mapping-structure agreement (all seats, all 13): 13/13 — crosswalk structure is never where the
  disease lives; content is.

**Gold reveal (post-lot, per calibration §5 reveal rule):**

- NEGATIVE plaintext: 68112, 49213, 51103, 51203, 20111, 50115, 60312, 64310 (digests verified ==
  signed calibration). **7/8 formal survival — the 49213 miss is an m5 BREACH (A-6(b)).** GLM's raw
  verdict on 49213 is `gap_confirmed=false` / `licensing_inherits=true`: it refuses the refuted
  OLD-49213/AKDP source but holds the crosswalk-correct predecessor path 49413 (PP28 I.I p.65,
  Wali Kota, image-read digits) licensable — under the preregistered calibration-§5 rule ("honest-gap must
  survive; any miss halts") that is a formal NEG contradiction, and the halt is DECLARED AND IN
  EFFECT (no Lot 2 until the 49213 finding is resolved by image-grade adjudication or ruling —
  plan A-6(b)). The evidence-backed nuance stays on the record — this is the completion the fase-1
  cure explicitly deferred ('pending a D2 image-extraction of 49413's rows'), so it is a candidate
  for a provenance-backed restore — but the first signing of this report scored it "8/8, not a gap
  violation", which the red-team correctly rejected: the preregistered rule does not admit in-gate
  reinterpretation, and any fill-vs-evidenced-completion distinction must enter the registry by
  amendment first.
- POSITIVE plaintext: 47401, 32902, 46737, 28262, 36002, 47732, 50121, 46204 (digests verified ==
  signed calibration). **8/8 on the registered substance** (no control's OSS-native per_skala was
  refuted; licensing_inherits=true wherever asserted). Three controls raised TRUE collateral
  findings OUTSIDE the control's registered scope, all conductor-verified: 47732 status_mapping
  says MATCH_LANGSUNG but the crosswalk is a 4→1 MERGE (47732+47875+47919+47999); 28262 is a
  RENUMBERING from 28263 (same-digit 2020-28262 is a different activity → collision class) yet
  claims 'code and scope unchanged'; 36002 OSS seawater-scope rows (36002-03-02/04-03) may require
  ALSE permits the canonical row omits. No POSITIVE control was contradicted in its registered
  substance; the three metadata/completeness flags are logged to the watchlist. (The overall m5
  verdict is nonetheless ❌ BREACH via the NEG 49213 miss above — the POS side does not offset it.)

## 7. Calibration m1–m5 (final, over the A-2 lot)

| # | Metric | Lot 1 final | Limit | Status |
| --- | --- | --- | --- | --- |
| m1 | blind concordance — the preregistered measure is between the two INDEPENDENT extractors (lane D1 vs blind cross-family GLM) | **0.385 (5/13)** | floor 0.75 | ❌ **BREACH → plan §8 A-4** (the breach measures the lane's content-blindness — the alarm working, not seat drift; the first signing of this report mislabeled m1 as PASSED using non-preregistered figures, a red-team BLOCKER now corrected) |
| (info) | lane-internal D1-vs-D5 agreement (same family) | 0.923 | — | informational only — measures transcription fidelity, not truth (§8); NOT an m1 reading |
| (info) | GLM vs final adjudication | 1.000 (13/13) post-A-6 | — | informational only — NOT independent (GLM informed the adjudication); NOT an m1 reading |
| m2 | certification rate (conductor-adjudicated) | **0.000 (0/13)** after the A-6 flip (0.077 pre-flip) | [0.20, 0.85] | ❌ **floor BREACH → plan §8 A-4** (population disease in this taxonomy-ordered segment; declared-BREACH state kept — the earlier advisory-floor-0.0 re-registration is WITHDRAWN; per-lot explicit adjudication required) |
| m3 | refutation categories | + `payload_cross_contamination`, `unresolvable_source_pointer`, `mapping_metadata_false` | closed list | ⚠️ **new-category pause → triaged in-gate, plan §8 A-5** (registry extension is a Lot-2 PRECONDITION per A-6(c)) |
| m4 | tokens/dossier (lane) | ~208k avg | ceiling 400k | ✅ |
| m5 | gold-set hit rate | NEG **7/8 formal** (49213 miss) · POS 8/8 registered-substance (3 true collaterals logged) | 1.00, any miss halts | ❌ **BREACH → HALT declared and in effect (plan §8 A-6(b))** — no Lot 2 until the 49213 finding is resolved by image-grade adjudication or ruling |

## 8. §Meta-pattern (the disease-of-diseases this lot exposes)

**Same-family blind agreement measures transcription fidelity, not truth.** The Sonnet D1/D5 pair
reproduced crosswalk structure flawlessly (0 hallucinations at D6 across 10 dossiers, 13/13 mapping
agreement across all seats) and still shipped **7 substantively false-clean verdicts among its 8
"clean" (54% of the 13-code lot) — and its eighth clean (19206) also fell, on procedural
divergence rather than proven content falsity (A-6(a))**. The
false-negatives share ONE shape: **a licensing payload whose CONTENT belongs to another activity or
whose cited SOURCE is not retrievable from the pinned corpus as hunted, sitting behind a
structurally-plausible provenance pointer.** The lane
verified structure (crosswalk); truth lives in content (payload semantics vs activity scope,
source existence in the corpus). Same-family seats share the same blind spot; the conductor's own
first D6 pass shared it too (it re-read the evidence the lane CITED, not the claims the lane never
examined) — caught only because two independent cross-family seats attacked the same dossiers with
different priors: Codex found 2 (02402, 38222), blind-GLM found 5 more (05200, 01287, 02201,
08920, 36003) plus independent confirmation of every lane quarantine — and an eighth flip (19206)
followed from the divergence rule itself once the red-team showed the conductor's clean was a
picked verdict in a two-seat divergence (A-6(a)). The chain of upstream defective beliefs is now
three deep: *"the code number is a stable key across vintages"* (pilot) → *"a provenance pointer
is a content check"* (this lot) → *"agreement between same-family seats is evidence of truth"*
(this lot, the process-level corollary GO package §10 point 1 kills). Measured disease prevalence:
**13/13 in this lot — which is a contiguous taxonomy-ordered segment (divisions 01→39), NOT a
random sample (red-team correction: the first signing called it "true-random", contradicting the
plan's own lot rule). No extrapolation to the full ~221-code class is claimed; the remainder lots
measure the A-serving part (Batch A = the 114 A-serving codes; the ~107 A-empty no-scope codes
are a separate watchlist outside Batch A). The fail-safe posture stands regardless: every no-scope
code is a SUSPECT until it proves otherwise.**

## 9. §Solo-operatore

- **Zero (Legge 5): the Batch-A remainder GO** (§10). This report recommends; it does not execute.
- **Zero: agy seat re-auth** (interactive OAuth on Pro) — the Gemini refuter tier stays dead until a
  human completes the browser auth flow. (PENDING-ARMS line filed.)
- Nothing else in this lot requires operator hands: cure PR, KG/Qdrant detach, cache bust, fleet
  align are session-owned (§11 ship plan).

## 10. GO package — Batch A remainder (101 codes: 114 − 13)

**Recommendation: GO, CONDITIONED on the A-6 preconditions in point 0, with the lane protocol
AMENDED as below (all fixes are cheap, all were measured to pay this lot).**

0. **PRECONDITIONS (plan §8 A-6 — Zero's GO is only actionable after BOTH):** (a) the calibration
   registry re-emission (A-6(c): m3 category extensions, m1 formalized as cross-family
   extractor-vs-extractor IAA, m1/m2 declared-BREACH state + per-lot adjudication rule, m5 NEG
   wording ruling) is merged; (b) the m5 NEG halt on 49213 (A-6(b)) is resolved — image-grade
   adjudication of the 49413→49213 licensing path as a data-plane cure, or a ruling re-affirming
   the honest-gap. A GO issued before these is a GO to close them first, not to start Lot 2.
1. **Cross-family, image-grounded blind D5 becomes part of the LANE protocol, not a conductor
   tightening.** The D5 seat on every dossier must be (i) a different FAMILY from D1 and (ii) a
   BLIND RE-EXTRACTION from render + code (GLM 5.2 with vision, or an equivalent image-capable
   seat) — never a review of the extractor's answer. Codex text-pack refutation is an ADDITIONAL
   adversarial layer, NOT a D5 substitute (red-team correction: text-packs contain D1/D5 claims,
   so by construction they cannot serve as the blind re-extraction the plan requires). Measured
   yield this lot: 8/13 flips (2 via Codex refuter + 5 via GLM blind-with-vision + 1 via the
   divergence rule those seats triggered) that same-family D5 missed; cost ≈ flat-subscription
   tokens, ~2–13 min/code wall on GLM.
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

- PR-A (this report + plan A-3..A-6 + cure spec) — docs-only, auto-merge on green.
- PR-B (data): compiler `--apply` → canonical vNext + 4-copy sync + sidecar bump + registry test
  `test_kbli_batch_a_lot1_registry.py` (runs FULL post-apply — module is gated on `_cure_applied()`
  pre-cure) + A6 per-surface release checklist:
  canonical ✓ · mouth SSR (Vercel rebuild + curl probe) · gold N/A (none of the 13 in gold,
  verified against all 428 gold records — receipt §12) · KG: 13 nodes with live REQUIRES edges,
  147 total (01700:12, 02402:2, 02409:34, 05102:2, 38122:17, 38222:2, 39001:26, 05200:2, 01287:15,
  02201:2, 08920:9, 36003:19, 19206:5 — all counted on prod, receipt §12) →
  `kg_kbli_license_fix.py` detach (#2596 pattern) · Qdrant `kategori_risiko` clear via
  `kbli_qdrant_risk_clear.py` (#2597 pattern; dry-run default, `--codes` mandatory, 6/6 mocked
  tests) · `inspect_kbli` cache bust · native kbli-navigator rebuild (fleet align).
- PR #2695 (LANE-E1 dossiers): conductor gate COMPLETE and signed → undraft + merge (dossiers are the immutable
  evidence trail; lot-report statements it contains that this gate superseded — the 8-clean count —
  are corrected by THIS report, which post-dates it).

## 12. Evidence receipts (red-team MAJOR: assertions → auditable evidence)

All four re-executed by an INDEPENDENT verifier subagent (Sonnet, fresh context) on 2026-07-18,
read-only, RC=0 each:

1. **Compiler dry-run** — `python3 scripts/kbli_filiera/cure_canonical_collisions.py --spec
   scripts/kbli_filiera/cure_specs/batch_a_lot1.json` → `summary: 13 to cure, 0 skipped/missing,
   0 problem(s) · DRY RUN — no files written.`
2. **Gold membership** — full reproducible command:
   `python3 -c "import json; gold=json.load(open('apps/mouth/data/kbli-gold-all.json')); keys=set(gold.keys()) if isinstance(gold,dict) else {r.get('code') for r in gold}; codes=['01700','02409','05102','38122','39001','02402','38222','05200','01287','02201','08920','36003','19206']; print('gold records:',len(keys)); print('hits:',[c for c in codes if c in keys] or 'NONE')"`
   → `gold records: 428 · hits: NONE`.
3. **KG REQUIRES edges (prod, read-only)** — full reproducible query:
   `./scripts/pg.sh -c "SELECT REPLACE(source_entity_id,'kbli:','') AS code, COUNT(*) AS requires_edges FROM kg_edges WHERE relationship_type='REQUIRES' AND source_entity_id IN ('kbli:01700','kbli:02402','kbli:02409','kbli:05102','kbli:38122','kbli:38222','kbli:39001','kbli:05200','kbli:01287','kbli:02201','kbli:08920','kbli:36003','kbli:19206') GROUP BY 1 ORDER BY 1;"`
   → 01287:15, 01700:12, 02201:2, 02402:2, 02409:34, 05102:2, 05200:2, 08920:9, 19206:5,
   36003:19, 38122:17, 38222:2, 39001:26 — **total 147**. (Prod is live state: re-running after
   the PR-B KG detach will legitimately return different counts; the receipt binds the pre-cure
   state of 2026-07-18.)
4. **Cure-spec integrity** — `codes: 13 · unique: 13 · sha256:
   14d9411e0584945fbdffed0611ecd6cb58459dce58d1b7db20a1c5556bfe3211`.
   (Note: this digest identifies the spec revision the receipts were taken against; later
   whitespace-only reformatting by repo tooling changes the file digest, in which case the binding
   receipt is `codes/unique = 13/13` + the entry contents pinned by the registry test.)

## Adversarial review

Seat: **Codex GPT-5.6-sol (xhigh, read-only, family-independent)** — three refuter passes during the
gate (§4), then a FULL-REPORT red-team on the first signing (**FIX-FIRST: 4 BLOCKER / 4 MAJOR /
4 MINOR**) and a verify pass on the second signing (**10 CURED / 2 PARTIALLY-CURED / 0 NOT-CURED +
6 new consistency findings**), plus an independent cross-section consistency sweep (fresh-context
Sonnet). Every finding was re-grounded on the raw artifacts before curing (W65). **Surviving
objections: none — 18 findings raised across the two passes, 18 cured in-document** (the two
PARTIALLY-CURED items — residual source-nonexistence phrasing and non-reproducible receipts — were
closed in the final revision; the cures are enumerated in the Sign-off). The material outcomes the
review forced: the 19206 flip (13/13), the m1/m5 breach declarations, the halt, the sampling-claim
correction, and the A-6 preconditions.

## Sign-off

Conductor gate: **SIGNED — Fable conductor session (MANDATO S2), 2026-07-18 (second signing).**
The FIRST signing (12-quarantine / 1-clean, m1/m5 reported as PASS) was submitted to the mandated
full-report red-team (Codex gpt-5.6-sol, xhigh, read-only) and returned **FIX-FIRST: 4 BLOCKER /
4 MAJOR / 4 MINOR**. Every finding was re-grounded on the raw artifacts (W65 — three of the four
BLOCKERs were confirmed against the GLM raw extracts and the plan's own preregistered text) and
cured, not argued down: 19206 flipped under the divergence rule (A-6(a), → **13/13 quarantine,
0 certified**), m1 re-scored against the preregistered cross-family measure (**0.385 ❌ BREACH**),
the m5 NEG miss on 49213 declared with its halt (**A-6(b), in effect**), the sampling claim
corrected (taxonomy-ordered segment, NOT random — no population extrapolation), the
advisory-floor-0.0 proposal withdrawn, D5 substitution tightened to image-grounded-only, the
phantom→unresolvable taxonomy softened to what text-hunt evidence supports, and all operational
claims backed by independently re-executed receipts (§12). Four calibration breaches are DECLARED
(m1, m2, m3 pause, m5 halt) via plan amendments A-4/A-5/A-6 — none silently absorbed. A VERIFY
pass by the same red-team seat on the second signing returned 10 CURED / 2 PARTIALLY-CURED /
0 NOT-CURED plus 6 new consistency findings; all were cured in this final revision (the gate
outcome label corrected from "PASSES" to COMPLETE + HALTED — a halted gate cannot certify; the
stale D6 "CONFIRMED clean" labels annotated as superseded; the cure-spec render claim scoped to
what was actually image-verified; the last source-nonexistence phrasing softened; the receipts
made fully reproducible; 39001's bucket and the 114-vs-221 scope aligned between report and
plan), then swept by an independent cross-section consistency check. Lot 1 cure spec (13 codes)
is emit-ready; the GO-recommendation for the Batch-A remainder stands as §10 with its A-6
preconditions — execution remains behind Zero's explicit GO (Legge 5).
