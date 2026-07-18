---
date: 2026-07-18
domain: operations
client_case: none (GARUDA-FILIERA Batch A pre-registration)
adversarial_review: codex
sources:
  - "workflow: research/operations/2026-07-16-kbli-garuda-filiera-workflow.md (§1-§8, red-teamed)"
  - "methodology: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, G13-G17)"
  - "GO: Zero 2026-07-17 ~23:00 WITA ('go', Batch A per workflow §8)"
  - "enumeration: live on KBLI_2025_FINAL_CLEAN.json 2026-07-17 post-cure-4"
---

# Batch A plan — pre-registration (authored BEFORE extraction, per D-protocol)

> Conductor: Fable session (M5). This plan is the pre-registered contract: acceptance criteria
> are fixed HERE, before any lane extracts anything. Changing a criterion mid-batch requires a
> logged amendment in this file (append-only §8), never a silent shift. This plan BINDS to the
> workflow doc — where this file is silent, the workflow doc (§1-§8) governs verbatim; nothing
> here relaxes it.

## 1. Scope — reason-coded membership, pinned as an artifact

The no-scope population, enumerated live on the canonical (2026-07-17, post-cure-4) with a
**reason code per member** (semantic membership, not census arithmetic):

| Reason code | Predicate | Count |
| --- | --- | --- |
| `A-serving/pp28` | `per_skala` non-empty AND `pp28_sources` non-empty AND no `_l2_source` | 113 |
| `A-serving/orphan` | `per_skala` non-empty AND `pp28_sources` empty AND no `_l2_source` (unsourced rows — same risk class) | 1 |
| `A-empty/gap` | `_l2_status: no_oss_risk` AND `per_skala == []` (incl. the 8 cured pilot codes) | 107 |

**Batch A scope = the 114 A-serving codes ONLY** (113 `A-serving/pp28` + 1
`A-serving/orphan`, 80190 — a source-discovery sub-class: its serving rows have no declared
source at all, so D0 starts from zero-inventory). These codes SERVE possibly-collision
licensing in production today; batch-done (§7) is defined over exactly this set. The 107
`A-empty/gap` codes are NOT in Batch A: they are registered as the standing **no-scope
watchlist** (methodology Phase-3 receptor: OSS publishes a scope → re-adjudication triggers),
and their gap-closing is a follow-up batch scoped from this batch's measured report.

Precondition P0 (below) pins the exact member lists (code → reason code) as a committed
artifact via the filiera compilers; the enumeration predicate above is re-runnable by any seat
against the pinned canonical revision. (Reconciliation with the workflow doc's "119": at that
doc's commit the serving predicate matched 119; cures since then moved codes from serving to
empty. Same semantic set, different snapshot date — membership is by predicate + pinned
revision, never by a hardcoded count.)

Ordering: taxonomy order (division/group) across the 114.

## 2. Preconditions (no extraction before ALL are true)

- **P0 Membership artifact**: the reason-coded member list (§1) emitted by a filiera compiler
  and committed (`data/kbli-filiera/`), pinned to a canonical git revision recorded in it.
- **P1 Vault manifest pinned**: LANE-B0 has committed `data/kbli-filiera/manifest/` with
  sha256 + URL + fetch date per item covering: BPS conversion table (Vol.1+2), PP28 lampiran
  300-dpi renders (BPK ids 394930–394950), full OSS re-snapshot (version uuid fff4053d…) **with
  an explicit endpoint inventory per code (detail / ruang-lingkup / relasi / umku: attempted +
  outcome)**, Perpres 10/49-2021 annexes, **Bali overlay (Gubernur letter) and Kepmenaker
  228/2019 rows** (evidence sources for l4/TKA facts, pinned like the rest), and a
  **status snapshot per instrument** (in-force / dicabut / superseded-by, with the
  peraturan.bpk.go.id status-page capture) so A1's abrogation gate is checkable offline.
  A batch pins ONE manifest revision; mid-batch refreshes never change evidence under a running
  lot (fencing per workflow §3).
- **P2 Plan on main**: this file merged.
- **P3 Leases**: every dossier claim goes through `agent_lock:kbli-dossier:<code>` (Redis).
  No lease, no touch. Run ownership: each lane run records `(lane id, op_id range)` in its
  dossier events; resume = re-run with same op_ids (idempotent no-ops per workflow §3).

## 3. Per-fact acceptance criteria (what "certified" means in Batch A)

A fact (risk tier, license row, authority, scale, obligation) is **CERTIFIED** only if ALL:

- **A1 Provenance + temporal validity**: carries (source id from the pinned manifest,
  page/row locator, vintage tag, **validity interval**: in-force-from and, where applicable,
  revoked/superseded-by). A fact sourced from an instrument that was **dicabut/abrogated at
  fetch date** (checked against the manifest's status snapshot — e.g. the BKPM 4/2021 →
  5/2025 revocation class) cannot certify; it quarantines as `stale-source`. Where the
  methodology's L2b/sectoral sources apply to a code's obligations, absence of the L2b source
  from the manifest makes the fact `abstained(pending-evidence)`, never certified from the
  general source alone (P1/G17). A fact without a locator is not a fact.
- **A2 Vintage legality**: any KBLI-2020-vintage source (PP28, Perpres 10/49, Kepmenaker)
  reaches a KBLI-2025 code ONLY through a BPS-crosswalk row adjudicated at D1
  (uraian-equivalence for 1-to-1; full semantic adjudication for splits/merges). Bare-digit
  joins are auto-QUARANTINE.
- **A3 Image verification**: any digit/row read from a scanned lampiran is extracted from the
  300-dpi RENDER with the D2 self-confirming protocol (extractor re-states the code string +
  neighboring rows' codes from the image). pdftotext is never evidence of digits.
- **A4 Blind agreement**: the D5 refuter (family ≠ extractor) re-extracts blind (render + code,
  never the extractor's answer); the COMPILER diffs the two extractions and only a match
  certifies. Divergence → QUARANTINE, never averaged or picked.
- **A5 Absence is earned** (full workflow D0 + methodology G14 contract): an ABSENT/gap verdict
  requires ALL of — (i) the declared endpoint inventory for that source attempted = enumerated;
  (ii) ≥3 attempts over ≥72h; (iii) a negative control (known-present code) returning data in
  the same crawl window; (iv) a **portal-UI check** and **stable aggregate counts** for the OSS
  source (an API 404 with a working UI page is a discrepancy, not an absence); (v) a
  crosswalk-aware sweep: the code's 2020 ancestor(s) and every relevant annex/lampiran in the
  pinned vault searched (image-grade for scans) — absence of the code alone is not absence of
  the obligation if an ancestor row exists. Anything less → `abstained(pending-evidence)`.
- **A6 Honest fallback + enforced downstream exclusion**: where the true row cannot be
  certified, the code gets the pilot's honest-gap pattern (detach + disputed-key + _data_note +
  editorial/l4 NON_CLASSIFICABILE). Quarantined/abstained facts MUST NOT appear on any surface:
  the emit PR carries a **binary per-surface checklist** (canonical → mouth SSR / gold /
  KG / Qdrant / inspect-cache / native app) with a release block — the PR does not merge until
  EVERY surface is verified in one of exactly two states, each with evidence attached to the
  checklist: (i) UPDATED (probe shows the new fact), or (ii) VERIFIED-NOT-EXPOSING (probe
  shows the surface does not and cannot serve the quarantined/abstained fact — e.g. field
  absent, cache busted, query returns gap). "Parked with an owner" is NOT a release state:
  fail-closed means no merge while any surface could still expose the fact (P9).

## 4. Writers and the no-hands rule (workflow §1 binding)

- **Deterministic compilers are the ONLY writers** of dossier JSONL, membership artifact,
  manifest, and canonical deltas. Lanes (Sonnet/refuter) produce PROPOSALS (structured output);
  the compiler validates schema + evidence pointers and appends the event. Fable writes NO
  data: the conductor adjudicates quarantines, signs batch reports, and approves the emit PR
  that a compiler generated.
- Canonical emit re-checks the canonical git revision at emit time (fencing): revision moved →
  emit aborts and re-bases.

## 5. Quarantine, sampling, calibration (falsifiable)

- **Lot** = one taxonomy division within a wave. 100% conductor review of every certified
  licensing fact in Batch A (gold-set nursery).
- **Calibration artifact (pre-registered here)**: BEFORE the first lot, the conductor signs
  `data/kbli-filiera/batch-reports/batchA-calibration.md` (versioned, compiler-emitted from
  pilot measurements). It MUST contain, per metric, an explicit numeric control limit — the
  metrics are fixed NOW: (m1) extractor/refuter IAA per lot (floor), (m2) certification rate
  per lot (floor and ceiling — a too-high rate is drift, not excellence), (m3) refutation-
  category distribution (new category = automatic pause), (m4) tokens/dossier (ceiling),
  (m5) gold-set hit rate (must be 100%; any miss halts). No lot starts before this artifact
  exists; a control-limit breach pauses the lane and requires a conductor-signed resume note
  in §8 citing the breached metric.
- **Gold set (deterministic, digest-pinned)**: NEGATIVE controls = the 8 cured codes
  (honest-gap must survive). POSITIVE controls = 8 OSS-native codes with certified per_skala
  (Batch C class) selected by deterministic rule — the 8 lowest `sha256(code || manifest
  revision)` among eligible codes — NOT conductor-picked. Both lists are committed in the
  calibration artifact as sha256 digests only (blind to lanes); the plaintext lists are
  revealed in the lot report AFTER the lot closes. A lane/compiler result contradicting either
  control class halts the lot.
- **Mutation testing**: per workflow §5, the conductor periodically injects corrupted
  intermediates (wrong code string in a render locator, altered row value); the refuter/compiler
  MUST catch them. An uncaught mutation is a program-level defect: lot halts, root-cause pass.
- Quarantine auto-triage: `schema_error` → compiler lane; `logic_conflict`/`semantic` →
  conductor queue. Quarantine entries carry (reason, owner, resolution criteria) — a state
  machine, not a parking lot.

## 6. Failure & degradation (workflow §6 binding, made explicit for this batch)

- Seat probe-dead → declared degraded + family-pairing swap (extractor ≠ refuter ≠ red-team
  families) + a PENDING-ARMS line for the seat. Fewer than 3 families available → declared
  degraded council + tightened sampling, never silent correlation.
- Fable window dead → batch SUSPENDS at lot boundary; durable state carries; no substitute judge.
- Compiler exception / schema violation → code to quarantine, lot continues (fail-visible).
- OSS snapshot anomaly (count drift, schema drift, WAF signature) → vault refresh halts + alert;
  a lone 404 never flips a fact (A5).

## 7. Deliverables + definition of batch-done

1. Dossier JSONL per code (hash-chained events D0→D5) for all Wave A-serving codes.
2. Conductor-signed lot reports + final batch report: censuses, per-fact verdicts
   (certified/quarantined/abstained), IAA, gold-set hits (both control classes), mutation-test
   results, measured service times + token burn (the cadence basis for Batch B).
3. Canonical vNext delta PR(s), compiler-emitted: certified rows land with provenance;
   uncertifiable codes get the honest-gap pattern. Every negative finding becomes a permanent
   sentinel/registry test.
4. The §3/A6 per-surface release checklist executed on every emit (merged ≠ live).
5. The A-empty watchlist follow-up batch scoped from the measured report (§1).

## 8. Amendments (append-only)

- **A-1 (2026-07-18, Zero) — A1-first sequencing; addendum vault wave deferred.** The P1
  evidence classes NOT in the Batch-0 core vault (Perpres 10/49-2021 annexes, Bali Gubernur
  overlay + Kepmenaker 228/2019 rows, per-instrument in-force/dicabut status snapshots) become a
  **second vault wave (P1-v2) that is HELD until AFTER Pilota A1 runs** — the pilot measures on
  the clean OSS + PP28 + BPS core first (Zero: *"aspetti dopo il Pilota A1 così misuriamo prima
  su vault-core pulito"*). This does NOT weaken any acceptance criterion: facts depending on the
  deferred classes (`pma_status`, `l4_bali`, TKA) come out `abstained(pending-evidence)` per
  A1/A5, honest-gap per A6 — never certified from the core alone, never published wrong. The
  PP28 300-dpi renders required by A3 are produced **on-demand per-code at D2** from the
  sha256-pinned PP28 lampiran PDFs (`pdftoppm -r 300`, deterministic), so they are not a
  bulk-prebuild precondition. Net effect: the extraction gate collapses to P0 (membership) only;
  the addendum wave and the abstention-lifting re-run are scoped from the Pilota A1 measured
  report alongside Batch B cadence.

- **A-2 (2026-07-18, conductor) — lot-shape rule.** §5 defines a lot as "one taxonomy division
  within a wave", but Batch A's 114 in-scope codes span **31 taxonomy divisions**, many with only
  1-3 codes each — a literal one-division lot makes m1/m2 statistically meaningless (one
  quarantine in a 2-code lot reads as a spurious control-limit breach; a floor/ceiling only means
  something over a sample large enough to carry a fraction). **Rule: a lot is a contiguous
  taxonomy-ordered segment of >=10 codes, divisions kept intact and consecutive divisions bundled
  until the >=10 threshold is met** (a division never splits across two lots). This does not
  relax any acceptance criterion or calibration limit (§3, §5) — it only fixes the sampling unit
  m1/m2 are measured over. **Lot 1 = divisions 01->39** (13 codes, taxonomy order): `01287`,
  `01700`, `02201`, `02402`, `02409`, `05102`, `05200`, `08920`, `19206`, `36003`, `38122`,
  `38222`, `39001`. Control limits (m1-m5, `data/kbli-filiera/batch-reports/batchA-calibration.json`)
  are unchanged by this amendment.

- **A-3 (2026-07-18, conductor) — canonical pin is the BLOB, not the commit (W88).** The signed
  calibration artifact pins the canonical to git revision `45bbc1f42a…` — a lane PR-head that is
  unreachable from main after the squash-merge, so any §4 emit fencing keyed on that commit-SHA
  would fail spuriously (scar #9/W88: an SHA-ancestor proxy lies where the content arrived by
  another path). Rule, effective immediately: **the content-authoritative canonical pin for Batch A
  is the blob sha `3cfe8134d` (`data/source_documents/KBLI_2025_FINAL_CLEAN.json`); any commit-SHA
  recorded alongside it is informative only.** Verified this session: `git rev-parse
  origin/main:data/source_documents/KBLI_2025_FINAL_CLEAN.json` = `3cfe8134d` — byte-identical to
  the calibration's intent (the artifact itself already records "(blob 3cfe8134d)" in PR #2695's
  grounding). The filiera compilers already validate content-aware (`_validate_membership_pin`,
  W88-aware) — no compiler change needed; the calibration artifact is NOT edited (it stays
  historically accurate; this amendment governs its interpretation). Emit fencing (§4) shall
  compare the canonical BLOB at emit time against `3cfe8134d`, re-basing if it moved.

- **A-4 (2026-07-18, conductor; REVISED same day after the Codex sol red-team of the conductor-gate
  report — the first version of this amendment mislabeled m1 as PASSED, called the lot "true-random",
  and proposed a post-hoc floor re-registration; all three were red-team findings and are corrected
  here, not papered over) — m1 AND m2 control-limit BREACHES on Lot 1: acknowledged, adjudicated,
  root-caused (conductor-signed note per calibration §5).**
  **m1 BREACH:** the preregistered m1 measure is the IAA between the two INDEPENDENT extractors
  (lane D1 vs blind cross-family GLM). Measured: **5/13 = 0.385 < floor 0.75**. The first draft of
  this amendment reported 0.923 as m1 "PASSED" — that figure is GLM vs the FINAL adjudication, which
  is neither the preregistered comparison nor independent (the GLM findings informed that
  adjudication). Declared verdict: **m1 ❌ BREACH**. Root cause is the same driver as m2: the lane's
  same-family D1/D5 pair was systematically blind to content-level disease (it verified crosswalk
  STRUCTURE, never payload CONTENT or source existence), so the blind cross-family extractor
  legitimately disagreed on 8/13 codes — the breach measures the lane's blindness, not seat drift,
  and is exactly the alarm m1 exists to raise. It fires the same protocol consequence: no silent
  resume, lane protocol upgraded (GO package: cross-family image-grounded D5 becomes part of the
  lane itself).
  **m2 BREACH:** final conductor-adjudicated certification rate for Lot 1 is **0/13 = 0.000** (after
  the A-6 divergence-rule flip of 19206; 1/13 = 0.077 pre-flip), below the m2 floor 0.20. Root
  cause is **population disease, not seat drift**: the cross-family tightening exposed that all 13
  codes carry uncertifiable per_skala — 8 with payload content that does not substantively cover
  the 2025 activity (seed-certification blobs on 02402/02201, a salt-extraction marine regime on
  peat 08920, a mining-concession regime on beneficiation 05102, generic-B3 on radioactive
  38122/38222, generic agriculture on narcotic-crop 01287, storage-exploration + marine-pollution
  rows on capture code 39001), 4 with unresolvable PP28 source pointers or non-inheritable
  ancestry (05200, 36003 not-retrievable-as-hunted; 01700 6-way merge; 02409 many-to-many), and 1
  with a generic pre-split basket payload plus false mapping metadata (19206, A-6). Every flip was conductor-verified BY EYE on the canonical payloads
  and vault records — the seats' claims were re-grounded, never trusted (W65).
  **Sampling scope (corrected):** Lot 1 is a **contiguous taxonomy-ordered segment (divisions
  01→39)** per this plan's own lot rule — NOT a random sample. 13/13 measures prevalence in THIS
  segment only; divisions 01→39 may over-represent agriculture/forestry/extraction contamination,
  and no extrapolation beyond it is claimed — the Batch-A remainder lots (101 codes) measure the
  rest of the 114 A-serving codes; the ~107 A-empty no-scope codes are a separate watchlist
  OUTSIDE Batch A (§1) and are not measured by this batch at all.
  **Disposition (no floor re-registration):** the earlier proposal to re-register m2 as
  advisory-floor 0.0 is WITHDRAWN — it would disarm the very drift alarm m2 provides, on the
  strength of a non-random sample. m1 and m2 remain in **declared-BREACH state**: every subsequent
  lot's conductor gate must explicitly adjudicate its own m1/m2 readings against the original
  limits and sign the resume note; the limits themselves change only via a registry amendment
  (A-6) that Zero's GO explicitly covers. No silent resume in any form.

- **A-5 (2026-07-18, conductor) — m3 new-category pause: acknowledged, triaged, registry extension
  proposed.** Lot 1's conductor adjudication surfaced refutation shapes not in the m3 closed list:
  **`payload_cross_contamination`** — a per_skala whose CONTENT belongs to a different activity
  (seed-certification on 02402/02201, salt-extraction marine regime on 08920, generic agriculture on
  01287), behind a structurally-plausible pointer — and **`unresolvable_source_pointer`** — a
  pp28_sources locator whose cited row is not retrievable from the pinned corpus as hunted (05200,
  36003). Terminology note (red-team finding): the earlier label "phantom_source_pointer" implied
  source NONEXISTENCE, which text-hunt evidence (11,208-page scan) cannot establish under this
  plan's own A5 image-grade rule — "unresolvable ... as hunted" is what the evidence supports;
  upgrading an instance to an earned ABSENT verdict requires the A5 image-grade scan of the relevant
  annexes. Per calibration m3 this is an automatic pause + conductor triage: the triage happened
  in-gate (every instance conductor-verified by eye on the canonical payloads; see the conductor-gate
  report). Proposal for the remainder: add `payload_cross_contamination`,
  `unresolvable_source_pointer` and the metadata flavor `mapping_metadata_false` (status_mapping /
  intel.whatChanged contradicting the adjudicated crosswalk, seen on 47732/28262 gold collaterals
  and Lot-1 05102/02409/19206) to the m3 registry. No silent resume: Lot 2 is firebreak-gated on
  Zero's GO **and on A-6's registry precondition**.

- **A-6 (2026-07-18, conductor; post-red-team) — divergence-rule flip of 19206 + calibration
  registry closure as a Lot-2 PRECONDITION + m5 NEG halt.**
  **(a) 19206 flip:** this plan's §3 rule is binding — "Divergence → QUARANTINE, never averaged or
  picked." Two independent cross-family seats flagged 19206 against the conductor's initial clean
  (Codex refuter dissent; blind GLM `needs_quarantine=true`, licensing payload = generic pre-split
  19291 basket, Besar row not on the pinned page, status_mapping 'CODICE_RINUMERATO' contradicted
  by the image-verified 3-way split). The conductor's initial clean was itself a "picked" verdict
  in divergence — exactly what §3 forbids. 19206 is QUARANTINED (cure spec entry 13); Lot 1 final:
  **13/13 quarantine, 0 certified**.
  **(b) m5 NEG breach + HALT:** blind-GLM on NEG control 49213 returned `gap_confirmed=false` /
  `licensing_inherits=true` (it holds the predecessor path 49413 licensable) — a formal NEG miss
  under §5's any-miss-halts rule, so **m5 is ❌ BREACH (7/8 formal NEG survival), and the halt is
  DECLARED AND IN EFFECT**: no Lot 2 until the 49213 finding is resolved (either an image-grade
  adjudication that certifies the 49413→49213 licensing path as a data-plane cure, or a ruling that
  re-affirms the honest-gap; conductor + Zero). The earlier report framing ("a candidate, not a gap
  violation") understated this: the preregistered rule does not distinguish evidenced completion
  paths from fills, and the distinction — if wanted — must enter the registry by amendment, not by
  in-gate interpretation.
  **(b)-RESOLVED (2026-07-18, same session, post-GO — conductor per-ancestor image-grade
  adjudication): HALT LIFTED.** Zero issued the GO; the conductor then ran the full per-ancestor
  check the 01700 lesson mandates (a MERGE never inherits from a single ancestor). KBLI-2025 49213
  "Angkutan Perkotaan" = MERGE of THREE 2020 ancestors (BPS Lampiran 10 printed p.385 / PDF p.399,
  read by eye): 49214 "Angkutan Bus Kota", 49219 "Angkutan Bus Dalam Trayek Lainnya", 49413
  "Angkutan Perkotaan Bukan Bus, Dalam Trayek". ALL THREE PP28 I.I rows were rendered at 300 dpi
  and read by eye (49214: p.40 row 9 · 49219: p.51 row 11 · 49413: p.65 row 14; digits verified
  against the OCR trap — text layer shows `492L4`/`492t9`): the three regimes are SUBSTANTIVELY
  IDENTICAL — Menengah Tinggi · 'NIB dan Sertifikat Standar' · 5 Hari · municipal authority for
  the urban scope (Wali Kota / Bupati-Wali Kota; 49219 grades by territory, its kabupaten/kota
  tier converges). Unlike 01700 (divergent ancestor regimes → non-inheritable), this merge is
  regulatorily homogeneous → the completion path is **CERTIFIED**. Disposition: the GLM NEG "miss"
  is adjudicated a TRUE FINDING; the 49213 honest-gap stays LIVE until a provenance-backed RESTORE
  ships as its own data-plane cure (spec-driven compiler extension, per-ancestor pp28_sources
  ['49214','49219','49413'], row content transcribed from the three renders — scheduled, NOT
  applied in-gate). m5 stays recorded as ❌ BREACH for Lot 1 honesty, but the HALT is lifted; the
  registry ruling for the remainder (A-6(c)): a NEG miss raising an evidenced completion path is
  adjudicated per-ancestor image-grade by the conductor — certified → scheduled restore (never an
  in-gate fill), refuted → halt stands.
  **(c) Registry closure precondition:** before ANY Lot 2 work, the calibration registry
  (`data/kbli-filiera/batch-reports/batchA-calibration.json` successor artifact) must be re-emitted
  to carry: the m3 category extensions (A-5), the m1 measure formalized as cross-family
  extractor-vs-extractor IAA, the m1/m2 declared-BREACH state + per-lot explicit adjudication rule
  (A-4), and the m5 NEG wording ruling from (b). Zero's GO for the remainder is only actionable
  AFTER this registry re-emission is merged — a GO issued before it is a GO to close the registry
  first, not to start Lot 2.

- **A-7 (2026-07-18, conductor) — Lot 2 (42999→59131) conductor-signed D6 verdict + control
  limits + m5 deviation declared. TWO INDEPENDENT LANES, CONVERGENT VERDICT.**

  Two independent conductor lanes ran Lot 2 in parallel: M5 session f5892d39 (workflow
  `wf_1ce36fab-e85`, innocence controls 47111/56101, cross-family seat Codex gpt-5.6
  image-grounded) and a Pro lane per the second-signed gate doc
  `research/operations/2026-07-18-kbli-batch-a-lot2-conductor-gate.md` / PR #2753 (innocence
  controls 46100/52101, cross-family seat GLM-vision). **Both converged on the SAME verdict:
  13/13 quarantined, 0 certified** — independent-lane convergence is itself evidence the
  disease call is real, not an artifact of either lane's specific extraction path.

  **Innocence-layer finding CONFIRMED ACROSS BOTH LANES independently:** M5's 56101 AND Pro's
  46100/52101 innocence controls ALL carry crosswalk-metadata disease (56101's provenance
  pointer falsely credited 56103/56104; 46100 and 52101 are merge-undercounts caught only on
  the REVERSE BPS table). The "presumed healthy" stratum is diseased at the metadata layer too
  — supports PR #2753's FATAL-4 candidate (a crosswalk-metadata contamination axis separate
  from the per_skala/licensing-payload axis this program has measured so far).

  **This lane's (M5) verdict table — 13 quarantined, 0 certified:**

  | Category | Codes | Count |
  |---|---|---|
  | `source_absent_in_vault` | 42999, 47771, 49233, 50113, 52105, 52219, 52299, 59131 | 8 |
  | `payload_cross_contamination` | 49296, 52103, 52211, 52232 | 4 |
  | `mapping_metadata_false` | 52239 | 1 |

  Plus a **56101 metadata-only cure** (innocence-violation finding, NOT a detach — per_skala
  substance independently verified correct and left untouched): `pp28_sources` corrected
  `['56101','56104','56103','56109']` → `['56101','56102','56109']`, `aggregation_note` and
  `intel_2026.whatChanged` corrected to credit KBLI-2020 56102 ("Rumah/Warung Makan") as the true
  omitted ancestor instead of the false 56103/56104 claim (BPS Tabel Konversi Vol.2, Lampiran 5
  p.211/printed-197 + Lampiran 10 p.407, conductor eye-verified). Also cured in the same PR
  (value-in-place, `apps/mouth/data/kbli-gold-all.json`, NOT data-plane-guarded, Codex-gated
  generator≠grader, 2 review rounds both PASS): 49296.whatYouNeed + 50113.whatYouNeed honest-gap
  (gold masks canonical intel_2026 on the live page, 49213/50115 precedent) and 56101.whatChanged
  mirror of the metadata correction.

  **Control limits (per-lot adjudication against the A-4 declared-BREACH state, no silent
  resume):**
  - **m1** cross-family IAA **10/13 = 0.769 PASS** (≥0.75 floor) — the FIRST m1 PASS of the
    program (Lot 1 was 0.385/0.538 BREACH). Cross-family seat = Codex gpt-5.6 blind
    image-grounded extractor per plan A-4. The 3 structural disagreements are content-level
    contamination confirmed by conductor eye-verify, not extractor noise. **Gotcha-in-the-gotcha**:
    the cross-family seat itself misread a digit on 49296 (49224 vs the true 49424) — caught only
    by the conductor's own image-verify against the pinned PP28 renders. Scar discipline "digits
    from scans: image-verify" (kbli-navigator §4 rule 5) applies to the CHECKER too, not just the
    original extraction.
  - **m2** = **0.000, declared BREACH** — population disease, not lot noise (per A-4's per-lot
    adjudication rule; the floor is not re-registered, the breach is recorded and the lot proceeds
    under the existing signed exception).
  - **m3** no new categories beyond the A-5 registry extension (`payload_cross_contamination`,
    `unresolvable_source_pointer`/`source_absent_in_vault` naming, `mapping_metadata_false`) — all
    13 Lot 2 findings classify cleanly into the existing closed-7 registry.
  - **m4** ≈197k tokens/dossier average, **PASS** (≤400k ceiling).
  - **m5 NOT MEASURED IN THIS LANE — declared deviation, not a silent skip.** The digest-salted
    gold sets (negative/positive controls per emit_batch_calibration_v2) were not embedded into
    this lane's conductor-eye adjudication process; instead the conductor served a hand-picked
    innocence pair (47111 — clean, untouched by any finding; 56101 — a TRUE POSITIVE at the
    *metadata* layer, not the per_skala layer) as the innocence check. This means the innocence
    set ITSELF carries the July-disease pattern (a record can be simultaneously "per_skala clean"
    and "metadata contaminated") — a finding worth recording in its own right, not just a
    control-limit shortfall. **The Pro lane's Appendix A (PR #2753) independently measured its
    own m5 = 1.00 on valid controls** (4/4 after disqualifying one contaminated control, same
    disease pattern as this lane's 56101 finding) — so the program-level m5 gap this lane
    declares is closed by the sibling lane, not by this one. **Disposition:** this M5 lane's own
    deviation is recorded here for audit honesty; no future reader should mistake THIS lane's m5
    silence for a clean PASS, even though the sibling lane's measurement covers the gap.

  **SCOPE BOUNDARY (read before treating Lot 2 as closed):** this PR ships ONLY the original
  13-code detach + the 56101 metadata cure described above. It does **NOT** satisfy PR #2753's
  fuller "Lot 2 cure shipped" bar — that report additionally requires (1) an upgraded disposition
  for 47771 (`mapping_metadata_false` primary: detach, already done here, PLUS a metadata
  correction — status_mapping → MERGE-aware, the 4 BPS parents 47892/47919/47996/47771 recorded
  as crosswalk ancestors, explicitly NOT as pp28_sources — NOT done here) and (2) three standalone
  metadata-fix cures outside this lot's 13-code scope: 46100 (2-parent merge, Lampiran 10 p.356),
  52101 (5-parent merge, Lampiran 10 p.389), and 10433 (Appendix A finding — pp28_sources
  wrongly associates 10490 with the wrong child, Lampiran 10 p.326). These four items are a
  **follow-up PR, gated before Lot 3**, owned by the conductor lane (re-pull evidence via
  dossier_pull + image-verify citations directly — not delegated to an apply-only session, per
  the same-digit/image-verify discipline this program runs on).
  - **Disposition:** SIGNED — Fable conductor session f5892d39, 2026-07-18 (M5 lane); convergent
    with the Pro lane's second signing, PR #2753.

- **A-10 (2026-07-19, M5 conductor):** Third twin-race of the lot — while #2754 fought a
  dropped-at-open CI event plus two pre-push gate cycles, the Pro lane landed #2761 (same 13-code
  detach + 47771 metadata fix, codex+GLM gated). M5 concedes the apply on content-equivalence (all
  13 verified detached on main; 47771 verified cured) and reworks #2754 down to its orthogonal
  delta: the 56101 metadata cure (the innocence-violation finding of the M5 lane, absent from
  #2761), its compiler, and the registry reconcile. Category-split divergence between the two
  signed verdicts (M5: 8 source_absent/4 payload/1 metadata; Pro: 4 source_absent/8 payload/1
  metadata-on-47771) is recorded as a report-level divergence with identical data-plane action —
  detach; it does not affect the shipped state.

## Adversarial review

Codex GPT-5.6-sol (high effort, read-only, 2026-07-18) attacked v1 of this plan against the
workflow + methodology docs. Captured findings (stream truncated to #8-#12 + notes; the revision
below was then re-gated in full by a fresh round-2 pass):
- semantic scope of the "119 vs 221" enumeration → §1 rewritten as reason-coded membership
  pinned by predicate + canonical revision (count is derived, never load-bearing);
- A5 false-absence loophole (no portal-UI/aggregate-count/ancestor sweep) → §3/A5 now carries
  the full D0+G14 contract;
- A6 downstream exclusion unenforced → §3/A6 release-blocking per-surface checklist;
- writer-ownership contradiction (lanes/Fable writing data) → §4 compilers-only writers,
  lanes propose, Fable never writes;
- calibration non-falsifiable → §5 pilot-report-pinned control limits, dual control classes
  (negative + positive), mutation testing, lot definition, signed resume;
- missing failure/precondition coverage (endpoint inventories, Bali/Kepmenaker in manifest,
  fencing, Fable-dead suspension, degraded pairing, run ownership) → §2/P1, §4, §6.
Round 2 (gpt-5.6-terra high, full capture): 4 MUST-FIX — scope still mixing waves (fixed:
Batch A = 114 A-serving only, A-empty → watchlist), A6 not fail-closed ("parked" could still
expose; fixed: two release states only, both evidence-backed), calibration not falsifiable
(fixed: pre-registered metrics m1-m5 + numeric limits in a named artifact + digest-pinned
deterministic gold sets with post-lot reveal), missing temporal-validity/L2b/abrogation gate
(fixed: A1 + P1 status snapshots). Round 3 (gpt-5.6-terra, targeted): all 4 cured, minor §1 opener incoherence fixed in the same commit. VERDICT: PASS.
