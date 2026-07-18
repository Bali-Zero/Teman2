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
