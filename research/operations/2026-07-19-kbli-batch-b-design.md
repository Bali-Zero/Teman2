---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch B pre-registration DRAFT)
status: DRAFT — for conductor review + 4-LLM panel. NOT armed. No lot may run under this
  document until a conductor signs it (mirroring the Batch A plan's own gate).
sources:
  - "methodology: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, G13-G17, Phase 1-4)"
  - "Batch A plan + amendments A-1..A-10: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "Batch A lot gate reports: research/operations/2026-07-18-kbli-batch-a-lot{1,2}-conductor-gate.md, research/operations/2026-07-19-kbli-batch-a-lot{3,4}-conductor-gate.md"
  - "calibration lineage: data/kbli-filiera/batch-reports/batchA-calibration-v3.md (v3, signed 2026-07-19)"
  - "cure specs: scripts/kbli_filiera/cure_specs/{metadata_56101,metadata_fixes_2026_07_19,metadata_residuals_2026_07_19}.json"
  - "compiler: scripts/kbli_filiera/cure_canonical_collisions.py"
  - "membership pattern: data/kbli-filiera/membership/batch-a-members.json"
  - "lot runner to adapt: infra/workflows/kbli-batch-a-lot.js"
  - "canonical dataset (population computed live this session): data/source_documents/KBLI_2025_FINAL_CLEAN.json"
  - "BPS Tabel Konversi KBLI 2020-2025 Vol.2 (vault-pinned, sha256 29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949), data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json"
  - "twin-race lessons: lesson_lot1_closeout_twin_race_two_conductors_2026_07_18, lesson_garuda_c1_twin_race_clobbered_prod_sibling_2026_07_18, lesson_outbound_email_twin_race_mailbox_check_2026_07_18 (memory)"
adversarial_review: pending (this draft has NOT yet been through Codex/4-LLM panel — the
  conductor runs that gate per CLAUDE.md §6, not this authoring session)
---

# Batch B design — the crosswalk-metadata sweep (DRAFT, pre-registration)

> Conductor note: this document is authored by a dispatched lane (worktree
> `.worktrees/docs-batch-b-design`, branch `agent/air-m5/docs/batch-b-design`), NOT by the
> conductor session itself. It is a **proposal**, structured like the Batch A plan
> (`2026-07-18-kbli-batch-a-plan.md`) so the conductor can amend it in place and sign it the
> same way, but nothing here is armed. No lease, no lot, no compiler run may cite this file as
> authority until a conductor signs it in an appended `## Adversarial review` / `## Sign-off`
> section, exactly as the Batch A plan required before Lot 1.

## 0. Why Batch B, and why now

Batch A targets the ~221 no-scope codes (OSS `ruang_lingkup` 404) whose `per_skala` was
silently filled from PP28/curatela — a **licensing-payload** disease on codes that were never
OSS-verified in the first place. Three lots in (39/39 quarantined, 0/39 certified — see §2),
that disease is confirmed severe on that population.

**Batch B is a different disease on a different population.** The 1,338 OSS-native codes
(`_l2_source == "OSS_RBA_resiko_2025"`, verified live this session — see §1) were always treated
as the *trustworthy core* (kbli-navigator corner §1: "structurally safe from cross-vintage
contamination"), because their `per_skala` licensing content comes straight from the 2025 OSS
snapshot, not from a 2020-vintage PP28 proxy. That is still true and **stays true under this
plan — per_skala on this population is OUT OF SCOPE for any Batch B cure.**

What is NOT OSS-native, even on these "healthy" codes, is the **crosswalk metadata**:
`pp28_sources`, `status_mapping`, `kbli_2020_source`, `aggregation_note`,
`intel_2026.whatChanged`. These fields assert a *historical* claim — which 2020 code(s) this
2025 code descends from — and that claim was authored during the original cross-vintage
ingest, the same weak-key joining process the methodology doc's §Meta-pattern already indicted
for the Batch A disease. **It was never re-verified for the "healthy" population because the
population looked healthy on the field that gates the served page (per_skala).**

The evidence this is real, not speculative: every one of the four proven crosswalk-metadata
disease cases to date was found **by accident**, as an innocence/gold *control* enrolled to
verify something else, never as a deliberately-audited Batch-B-shaped target:

| Code | Found as | Disease | Fix |
|---|---|---|---|
| 56101 | Lot 2 innocence control | false `pp28_sources` ancestry (56103/56104 claimed, true is 56102) | `scripts/kbli_filiera/cure_specs/metadata_56101.json` |
| 52101 | Lot 2 POS gold control | `status_mapping=MATCH_LANGSUNG` false — true 5-parent merge | `metadata_fixes_2026_07_19.json` |
| 46100 | Lot 2 innocence control | `status_mapping=MATCH_LANGSUNG` false — true 2-parent merge, missed on first receipt-level review, caught on the *reverse* table | `metadata_fixes_2026_07_19.json` |
| 10433 | Lot 2 POS gold control (Appendix A) | `pp28_sources` wrongly co-attributes 10490, which belongs to a different 2025 code (10419) | `metadata_fixes_2026_07_19.json`, residual closure in `metadata_residuals_2026_07_19.json` |

Four confirmed cases out of a handful of controls sampled — a striking hit rate, though the
sample was not random (§1 addresses this directly: it is exactly why Batch B cannot rely on
opportunistic discovery and needs a real sweep). The `m3` refutation-category registry already
names this disease class (`mapping_metadata_false`, closed-7 list,
`data/kbli-filiera/batch-reports/batchA-calibration-v3.md:26`) — Batch B is the deliberate,
population-wide hunt for it.

## 1. Population & stratification

### 1.1 Population — computed live against canonical

```
data/source_documents/KBLI_2025_FINAL_CLEAN.json → data.data (1,559 records)
Predicate: record["_l2_source"] == "OSS_RBA_resiko_2025"
→ 1,338 records (exactly; the complement, _l2_source is None, is exactly 221 — the Batch A
  no-scope population, confirming the two batches are disjoint and jointly exhaustive of the
  1,559-code corpus)
```

Verified this session (python, canonical loaded fresh, not from memory): `1338 + 221 = 1559`.
This matches the kbli-navigator corner's standing figure (§1 LIVE STATE: "1,338/1,559 carry
OSS-native `ruang_lingkup`") and the Batch A plan's own framing of the complement set — no
discrepancy to reconcile.

Batch A's own population is currently **down to 49 in-scope codes** (Lots 1-5 quarantined
13×5=65 of the original 114 `A-serving`; `data/kbli-filiera/membership/batch-a-members.json:12-18`,
census block: `A-serving/pp28: 48, A-serving/orphan: 1, _in_scope_total: 49`). Batch B does not
touch this remainder and can run in parallel (§5).

### 1.2 status_mapping distribution over the 1,338 (computed live)

| `status_mapping` | Count | % | Shape |
|---|---:|---:|---|
| `MATCH_LANGSUNG` | 854 | 63.8% | declared 1:1, same code number |
| `CODICE_RINUMERATO` | 224 | 16.7% | declared 1:1, renumbered — different 2020 code |
| `MATCH_CON_AGGREGAZIONE` | 185 | 13.8% | declared merge/split, multiple 2020 ancestors |
| `BPS_ONLY` | 74 | 5.5% | no PP28/2020 crosswalk basis at all |
| (null) | 1 | 0.1% | — |

### 1.3 Mechanically-detectable strata (computed live against canonical — zero LLM tokens spent)

These are pure-Python structural checks over fields already in the canonical record. They do
**not** establish truth (only the BPS crosswalk source can) but they give a falsifiable,
zero-cost triage signal, in the same spirit as the "declared count vs actual" check below that
independently re-discovered both already-known stale-note cases with no false positives.

**Stratum 1 — `MATCH_CON_AGGREGAZIONE` with `len(pp28_sources) == 1`: 46 codes.**
This is *exactly* the shape of all three proven merge-mislabel/undercount diseases (52101, 46100,
10433 before their fix) — a code claims a merge/split but its pointer list carries only one
entry. **Highest-priority stratum**, first candidates for D0-D6.

**Stratum 2 — `MATCH_LANGSUNG` with `pp28_sources[0] != own code`: 16 codes.**
A direct-match label with a pointer that names a *different* 2020 code number is an internal
contradiction (if the match were truly direct/unchanged, the pointer should be the same digits).
Full list, small enough for 100% review: `02103, 12003, 37002, 47401, 63900, 68210, 74199, 78200,
79903, 80110, 86991, 86992, 86993, 86994, 90130, 96210` (all point to a *different* code, e.g.
`63900 → ['63990']`). Second-priority stratum.

**Stratum 3 — `aggregation_note` internal-consistency check: 198 codes carry the field
(`Dati da <code> + N codici figli PP28` prose); parsing "N" and diffing against
`len(pp28_sources)` under BOTH observed array conventions (self-code included as element 0 vs.
children-only) finds exactly **2 mismatches: 10433 and 49213** — both already known
(10433: residual-fixed pp28_sources but the note text was left stale, flagged as a known
follow-up in `metadata_residuals_2026_07_19.json`; 49213: the A-6(b) 3-ancestor restore left the
note at its pre-restore "+1" wording). **Zero false positives across the other 196.** This is a
cheap regression gate (run it every cure) more than a discovery tool — its yield on fresh ground
will be near-zero going forward precisely because it only catches *count*-level contradictions
between two already-derived fields, not content correctness against the true source.

**Stratum 4 — `kbli_2020_source` vs `pp28_sources[0]`: 314 codes carry `kbli_2020_source`
(a scalar shadow field); 0/314 disagree with `pp28_sources[0]`.** This field carries zero
independent diagnostic value today (it is a perfect echo, never an independently-sourced
check) — noted here only because §4 must ensure any `pp28_sources` cure also updates this field,
or a fresh field-vs-field staleness is created by the cure itself (the exact failure mode
`aggregation_note` already suffered on 10433/49213).

### 1.4 The real leverage: a deterministic BPS crosswalk extraction pass (the brief's "KEY IDEA")

The vault-pinned BPS Tabel Konversi Vol.2 (`data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json`,
sha256 `29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949`, same pin every cure
spec to date cites) is a **444-page, born-digital text PDF** — confirmed via `pdfinfo`
(`Creator: Word`, `Producer: macOS ... Quartz PDFContext`; encrypted only against *editing*,
not against copy/print extraction) and via `pdftotext -layout` producing clean, columnar,
directly-legible Indonesian text. This is a materially different situation from the **PP28
lampiran corpus**, which is scanned and OCR-hostile (the "681t2" digit-corruption trap the
kbli-navigator corner's operating rules warn about) and therefore requires per-code 300-dpi
image renders read by a vision model or a human eye.

**Two tables at the code ("kelompok", 5-digit) level — the exact level every cure spec to date
has cited — sit inside this one PDF:**

| Lampiran | Direction | Pages | Span |
|---|---|---:|---|
| **Lampiran 5** | KBLI 2020 → KBLI 2025 (forward) | 131–246 | ~115 pp |
| **Lampiran 10** | KBLI 2025 → KBLI 2020 (reverse) | 325–444 | ~120 pp |

(Page numbers verified this session via `pdftotext -layout` + a grep for the `LAMPIRAN`/`Lampiran N`
header lines; e.g. `page 325: Lampiran 10 Tabel Konversi Kelompok KBLI 2025—2020`.)

**Empirical spot-validation against an already-signed ground truth:** the A-6(b) restore of
49213 (Batch A Lot 1, `plan §8`) rests on a conductor eye-read of PDF page 399: "49213 = MERGE of
{49214, 49219, 49413}". Extracting that same page's text layer this session reproduces the
*identical* three rows verbatim:

```
49213   Angkutan Perkotaan     49214   Angkutan Bus Kota
49213   Angkutan Perkotaan     49219   Angkutan Bus Dalam Trayek Lainnya
49213   Angkutan Perkotaan     49413   Angkutan Perkotaan Bukan Bus, ...
```

No digit corruption, exact match to the signed finding. This is one data point, not a proof of
100% reliability, but it is a real, falsifiable spot-check against the highest-stakes finding
this program has produced so far — and it passed.

**A v0 prototype parser (built this session, explicitly NOT production-grade — for feasibility
demonstration only)** does a whitespace-column split, anchoring each row on a leading 5-digit
code. Result on Lampiran 10: **2,102 of 2,560 candidate data-rows parsed (82%)**; the remaining
458 are rows whose second (2020-code) column lands on a *continuation line* because the first
column's title wrapped — a known, tractable table-layout problem (needs a position-anchored
column tracker keyed off the header row's character offsets, not a whitespace heuristic; NOT a
digit-corruption/OCR problem like PP28). Unique-code counts from this crude pass are already
sane (1,340 unique left/2025 codes on Lampiran 10 vs. the true 1,338 population — a 0.1%
overshoot, most plausibly parser noise, not evidence of a structural problem).

Running this v0 parser's per-code Lampiran-10 ancestor set as a diff against canonical
`pp28_sources` across the 1,338 population: 1,147 codes got at least one parsed row; of those,
603 set-matched and **544 set-mismatched**. **This number is explicitly NOT a defect count** —
two reasons, both borne out by evidence already in hand:

1. The parser's own 18% row-loss rate on Lampiran 10 alone means both false-omission
   ("no_l10_row": 191 codes) and false-mismatch (a genuinely-matching code where the parser
   simply missed one of several true ancestor rows) are expected at non-trivial rates until the
   continuation-line gap is closed.
2. **A crosswalk-ancestor divergence from `pp28_sources` is not automatically a bug.** The
   52101 cure spec is explicit that `pp28_sources` is a deliberately *narrower* concept
   ("the PP28-licensing-basis pointer... separate from the full BPS crosswalk-ancestor
   narrative") — 52101 and 46100 both shipped with their true multi-parent ancestry recorded
   only in prose (`data_note`/`whatChanged`), `pp28_sources` left untouched, precisely because
   injecting the extra ancestors would have required an independent PP28-corpus re-hunt beyond
   what was verified. A full crosswalk diff will therefore surface a mix of (a) genuine
   `pp28_sources`/`status_mapping` falsities (like 56101, 10433's wrong co-parent), (b) legitimate
   narrower-by-convention cases (like 52101/46100's *unchanged* `pp28_sources`), and (c) parser
   noise. **Adjudicating which is which is exactly the D1 crosswalk-adjudication work Batch B
   exists to do** — the 544 number's only honest use here is as an order-of-magnitude leverage
   estimate ("hundreds, not dozens, not thousands"), not a population size to plan lots against.

**Recommendation — Batch B Phase 0 (before any lot runs):** build the real parser as a
deterministic Python compiler (`scripts/kbli_filiera/`, following the P5 "deterministic
compilers" principle) with: (a) position-anchored column tracking off each page's header row
(not whitespace-split), (b) independent parsing of **both** Lampiran 5 (forward) and Lampiran 10
(reverse) with a **built-in cross-check** — for every 2025 code, the ancestor set derived from
filtering Lampiran 5's forward rows by 2025-column match must equal the ancestor set derived
directly from Lampiran 10's reverse rows for that code; a genuine same-source double-extraction
check requiring **zero extra LLM family**, satisfying the brief's "double-extraction cross-family"
mandate more cheaply than a second vision seat would, because the two lampiran are two
independently-typeset views of the same underlying relation. (c) digit-confidence flags on any
row the parser could not anchor with full column-position confidence — those rows, and only
those, get the image-verify treatment PP28 needs everywhere. This whole pass costs **zero LLM
tokens** for the ~99% of rows that parse cleanly; LLM/conductor time is reserved for adjudicating
genuine divergences, not for bulk extraction — a materially different (cheaper) leverage profile
than Batch A, where every code needed an image-render vision pass because the source itself was
OCR-hostile.

### 1.5 Stratification for lot ordering (not permanent sampling — full 1,338 stays in scope)

Per the north star ("re-validate the WHOLE navigator... code by code" — no code is
permanently exempted), all 1,338 stay in eventual scope. Processing *order* is prioritized by
mechanical risk signal:

1. **Tier 1** (46 codes, §1.3 stratum 1) — highest proven-disease-shape match. First lots.
2. **Tier 2** (16 codes, §1.3 stratum 2) — label/pointer contradiction. Small enough for one lot.
3. **Tier 3** — Phase-0 parser output: codes with a genuine cross-lampiran-validated ancestor-set
   mismatch (not the raw 544 — the *validated* subset once Phase 0's cross-check is built).
   Expected the bulk of real yield.
4. **Tier 4** (remainder, ~1,090+ codes: clean-shaped `MATCH_LANGSUNG` self-referencing,
   `CODICE_RINUMERATO`, `BPS_ONLY`) — AQL-adaptive sampling per the methodology's own Batch B/C
   row ("AQL tightened start", methodology doc Part 3 batch table), NOT the 100%-conductor-review
   Batch A ran, because the per-code stakes differ: a Batch B cure never touches served licensing
   content (per_skala is out of scope by construction, §0), only ancestry prose/pointers — the
   blast radius of a missed Tier-4 defect is a wrong "what changed" sentence, not a wrong permit
   requirement. Batch A's 100% rule was earned by its population being *already suspect*
   (no-scope, silently-filled); Batch B's Tier 4 is the closest thing this program has measured
   to a "presumed healthy" population, and AQL sampling is the calibrated instrument for that,
   not a corner cut — provided §2's m2′ control limit is pre-registered tight enough to catch a
   surprise (see §2).

## 2. Measurement design

### 2.1 What carries over unchanged

- **m1 (cross-family extractor-vs-extractor IAA, floor 0.75)** — same metric, same floor. Redefine
  the *task* being agreed on: crosswalk adjudication (does this code's declared ancestor set match
  the BPS table, and is the split/merge semantically inheritable), not licensing-payload
  adjudication. `batchA-calibration-v3.md:24` shows same-family agreement is worthless (Lot 1's
  same-family reading was a red-team-caught mislabel) — the cross-family requirement is not
  optional here either.
- **m3 (closed refutation-category registry)** — reuse the v3 closed-7 list verbatim:
  `code_collision, illegitimate_inheritance, wrong_authority_level, source_absent_in_vault,
  payload_cross_contamination, unresolvable_source_pointer, mapping_metadata_false`
  (`batchA-calibration-v3.md:26`). Batch B's target disease, `mapping_metadata_false`, is
  *already* in this registry with 4 confirmed instances (§0) — no registry amendment needed to
  start. A genuinely new category (e.g. a metadata field this design didn't anticipate) still
  triggers the standing automatic-pause rule.
- **m4 (tokens/dossier ceiling)** — carries over as a ceiling, but is expected to read *lower*
  per dossier than Batch A's ~197k/dossier average (`plan §8 A-7`), because Phase 0's
  deterministic parse replaces the D2 image-extraction step for the majority of codes; reserve
  the ceiling as a runaway guard, not a target.
- **m5 (gold-set hit rate, digest-pinned blind sha256, NEG+POS, reveal-after-close)** — carries
  over architecturally. Two changes inherited as *standing protocol*, not new proposals:
  the **POS pre-verification-both-directions rule** shipped at v3 after 46100/52101/10433 all
  turned out to be contaminated "clean" controls drawn from exactly this population
  (`batchA-calibration-v3.md:123`) — Batch B's own gold-set compiler MUST pre-verify every POS
  control on both Lampiran 5 and Lampiran 10 before enrollment, not just by lowest-digest
  selection. NEG controls for Batch B seed from the four already-cured metadata cases
  (56101/52101/46100/10433) the same way Batch A seeded its NEG set from the 8 phase-1 cured
  codes.

### 2.2 What must be replaced or newly pre-registered

- **m2 → m2′ (metadata certification rate), floor/ceiling TBD by conductor+Zero, not by this
  draft.** Batch A's own m2 has read **0.000 across three consecutive lots** (39/39 quarantined,
  `batchA-calibration-v3.md:25,131,138,148` — "read as the true state of the disease band, not
  instrument drift"). That reading is legitimate for Batch A's *already-suspect* population.
  Batch B's population is the opposite prior — "presumed healthy" — so an m2′ reading anywhere
  near 0.000 would be a substantially more alarming finding than Batch A's own 0.000, not a
  restatement of the same baseline. This draft explicitly does **not** propose a numeric
  floor/ceiling for m2′: the methodology's own falsifiability rule (plan §5, "no floor
  re-registration... a control-limit breach pauses the lane") requires the number be
  pre-registered by the conductor *before* Tier-1 evidence exists, not backed into once the
  first lot's number is known. What this draft does propose: whatever the floor is, it must be
  pre-registered wide enough that Tier 1/2's already-elevated risk (46+16 = 62 codes hand-picked
  precisely because they match a proven disease shape) doesn't itself trip a ceiling-breach false
  alarm in the very first lot — Tier 1/2 should probably be measured as their **own sub-lot**,
  separate from Tier 3/4's population-representative reading, exactly as Batch A's own §8 A-4
  amendment had to retroactively acknowledge Lot 1 was "a contiguous segment... not a random
  sample" and forbade extrapolating its rate to the whole population. Pre-declare that
  non-representativeness here, not after the fact.
- **m3 sub-classification (not a new top-level category, a refinement worth pre-registering):**
  distinguish, within `mapping_metadata_false` verdicts, **falsity-in-pointer** (the value is
  wrong — 56101, 10433's co-parent; cure = correct it) from **narrower-by-convention**
  (`pp28_sources` deliberately omits a true crosswalk ancestor already recorded in prose — 52101,
  46100's pattern; cure = confirm/leave, maybe extend prose) — these have different D6 verdicts
  and different cure actions (§4) and conflating them in one certification-rate bucket would
  make m2′ uninterpretable.

## 3. Lot shape

Adapt the Batch A lot-shape rule (plan §8 A-2: "a lot is a contiguous taxonomy-ordered segment
of ≥10 codes, divisions kept intact") to Batch B's ~10× population. Batch A's 114 in-scope codes
spanned 31 divisions (~3.7 codes/division); the OSS-native 1,338 span the same taxonomy with a
much denser per-division population, so contiguous-division lots will naturally land near
whatever size threshold is chosen without needing artificial division-splitting.

**Recommendation:** N ≥ 25 codes/lot for Tier 1–3 lots (small enough that a single conductor
gate stays reviewable, large enough that m1/m2′ read as more than single-code noise — Batch A's
own A-2 amendment reasoning applies unchanged: a floor/ceiling only means something over a
sample large enough to carry a fraction). Tier 4's AQL-sampled pass can run at a different,
larger nominal lot size (its per-lot review is a sample, not 100%, so lot size there tracks
sampling-plan design, not conductor-reviewable-count).

**Runner delta from `infra/workflows/kbli-batch-a-lot.js`:** the existing runner's D1/D5
architecture (independent-propose → blind-refute → deterministic `diffD1D5()` verdict, never
averaged/picked) is reusable almost as-is — the adjudication *shape* (structured proposal,
independent blind re-derivation, compiler-diffed verdict) does not depend on what's being
adjudicated. What changes:

- **Evidence input**: Batch A's D0/D2 pulls PP28 lampiran renders per-code (image-grounded,
  because the source is OCR-hostile). Batch B's primary evidence, once Phase 0 ships, is the
  **pre-computed crosswalk table** (deterministic, already parsed) — D1 proposes a verdict by
  looking up the code's row in that table and comparing to canonical, not by reading a fresh
  render. D5's "blind re-derivation" becomes an independent **re-lookup against the same parsed
  table plus an independent re-scan of the raw PDF pages** (catching parser bugs, not just
  seat disagreement) — genuinely cheaper than Batch A's per-code vision pass, but the blind
  discipline (D5 never sees D1's proposal) carries over unchanged.
- **Membership gate**: same mechanism (`args.membership` passed in verbatim, no filesystem
  primitive inside the Workflow script), pointed at a new
  `data/kbli-filiera/membership/batch-b-members.json` artifact (Phase-0 compiler output: code →
  tier → parsed-ancestor-set → canonical-value → mismatch-class).
- **Verdict taxonomy**: extend the frozen `certified | quarantined | abstained` set with the m3
  sub-classification from §2.2 as a *verdict annotation*, not a fourth top-level state (mirrors
  how the existing script already normalized the pilot's 4-vocabulary innocence branch down to
  the same three tokens — same discipline, one more annotated dimension).
- **Lease/abstain scope**: identical boilerplate (`agent_lock:kbli-dossier:<code>` WARN-only per
  workflow §1's no-subprocess-primitive constraint; P1-v2 abstain-class facets `pma_status`,
  `l4_bali`, `TKA` remain out of scope exactly as in Batch A — Batch B doesn't touch those facets
  either).

Concrete deliverable: `infra/workflows/kbli-batch-b-lot.js`, forked from
`kbli-batch-a-lot.js` with the evidence-input and membership-artifact deltas above — a BUILD-phase
task, not something this design document should write.

## 4. Cure conventions (restated as law — already ruled, not re-litigated here)

These conventions are **already established and proven** across the four shipped metadata
cures (§0) and the compiler that implements them
(`scripts/kbli_filiera/cure_canonical_collisions.py`, spec-entry keys documented at lines 36-61,
`"action": "metadata_only"` detection at lines 220-224/302-308, correction application at
242-277/341-356). Batch B does not invent new law — it reuses this law at scale:

1. **Correct FALSITY in the pointer/label; record incompleteness in `_data_note`.** A wrong
   `pp28_sources` entry (10433's `10490`) or a wrong `status_mapping` label
   (52101/46100's false `MATCH_LANGSUNG`) gets corrected outright. A `pp28_sources` that is
   merely *narrower* than the full true crosswalk ancestry (52101/46100's own, deliberately
   left `pp28_sources` unchanged) is NOT falsified — it is documented more fully in prose,
   because forcing a value in without independent verification of the PP28-licensing-basis
   pointer specifically would itself violate rule #9 (no new values without provenance).
2. **`per_skala` is never touched.** The `"action": "metadata_only"` spec-entry key exists
   precisely to make this structural: the compiler skips all per_skala/disputed-key handling
   unconditionally when this action is set, regardless of the record's current state
   (`cure_canonical_collisions.py:220-224`). Every Batch B cure spec uses this action; a spec
   that needs to touch `per_skala` is not a Batch B cure — it belongs to a different batch.
3. **Append-never-erase.** Every shipped cure's `_data_note` appends the new finding onto the
   *existing* note verbatim (the residuals spec explicitly names this convention: "each entry's
   data_note APPENDS a residual-fix sentence to the EXISTING #2777 note verbatim, never erases
   it" — `metadata_residuals_2026_07_19.json:2`). The evidence trail of who found what, and when,
   stays intact across successive fixes on the same code.
4. **Compilers only.** Lanes propose (structured JSON matching the spec schema); the compiler
   validates and writes; the conductor signs and approves the emit — same writer discipline as
   Batch A plan §4, unchanged for Batch B.
5. **Pins after data commit.** Every cure spec pins its BPS Vol.2 sha (`29f17b3b...`) and cites
   an exact page + render filename; the calibration/membership artifacts pin canonical
   git-revision AND blob-sha (scar #9/W88 — pin the content, never the commit alone).

**Two small, well-precedented compiler extensions Batch B needs (not built yet — flagged as
Phase-0-adjacent work, not a re-architecture):**

- **`aggregation_note_correction`** — a spec-entry key mirroring `pp28_sources_correction`
  exactly. Both known stale-note cases (10433, 49213 — §1.3 stratum 3) were explicitly flagged
  in their own cure specs as "known follow-up... the compiler does not write this field" — this
  is not a new problem, it is an already-documented gap with an obvious, precedented shape of
  fix.
- **`kbli_2020_source_correction`** — same reasoning: any `pp28_sources_correction` that changes
  `pp28_sources[0]` must also update this scalar shadow field in the same write, or the cure
  itself creates a fresh field-vs-field staleness identical in kind to the one it just closed
  (§1.3 stratum 4).

## 5. Coordination — two-conductor protocol

Batch A has suffered **three twin-races in roughly 48 hours** at 114-code scale: the Lot 1
closeout twin (two conductors, resolved by the cross-family gate winning per #2721), the Lot 2
twin (M5 vs Pro lane, independently convergent verdicts — the *good* outcome, §5.1 below), and
the A-10 twin (M5 conceded content-equivalence to Pro's #2761 and reworked its own PR down to an
orthogonal delta). Batch B's ~1,338-code population is ~12× larger; without a coordination
convention in place *before* Lot B-1 starts, the collision surface scales roughly with it.

**5.1 What already worked (formalize it, don't reinvent it):** the Lot 2 twin-race was not a
failure — two independent lanes (M5, Pro) ran the same lot with *different* innocence controls
and a *different* cross-family seat family (Codex vs GLM-vision) and landed on the **same
13/13-quarantine verdict**, which the calibration registry explicitly reads as *evidence the
disease call is real, not an artifact of either lane's extraction path*
(`batchA-calibration-v3.md`, Lot 2 outcome section references PR #2753/#2761). Independent
convergence is a feature when it happens on the SAME scope by accident. What made A-10 costly
was a race on the **same PR/scope without either lane knowing about the other's claim** — that
is the actual failure mode to close, not "two lanes ever touching related work."

**5.2 Proposed convention:** before starting any Batch B lot, **grep the ledger** (open PRs +
`agent/*`/`agent-b/*` branches whose title/diff touches the lot's code range or the
`data/kbli-filiera/` membership/manifest paths for Batch B) and post a **claim comment** on the
first PR opened for that lot (mirrors what A-10 already did de facto, formalized). A second lane
that finds an active claim on its intended range does NOT duplicate the full lot — it either (a)
picks a disjoint range, or (b) if it has already found something orthogonal (the 56101-style
"innocence-violation on someone else's control" case), ships *only* that orthogonal delta against
the first lane's PR, exactly as M5's A-10 rework did. This draft recommends this become a written
rule in `infra/workflows/kbli-batch-b-lot.js`'s header comment (mirroring
`kbli-batch-a-lot.js`'s own extensive inline-doctrine comments), not just a memory lesson.

**5.3 Lot-range reservation register:** given Batch B's scale plausibly justifies *multiple
lanes running concurrently by design* (unlike Batch A's single-conductor-at-a-time cadence to
date), propose a small committed JSON,
`data/kbli-filiera/membership/batch-b-lot-reservations.json`, recording `{lot_id, code_range,
claimed_by, claimed_at, status}` — a lightweight, git-diffable claim ledger that turns "grep the
PR list and hope" into a single-file check. This is new infrastructure, so it needs conductor
sign-off before being built (it is a coordination primitive, not a data-plane write, so it does
NOT need the data-plane-guard registry treatment — it is not part of the canonical/gold/KG
surfaces #2550 protects).

## 6. §Meta-pattern

**What single defective belief generated the metadata layer's disease?** The belief was:
*"OSS-native `ruang_lingkup` means the record is safe."* That is true for the field it actually
gates — served `per_skala` licensing content — and the kbli-navigator corner is correct to keep
calling that population "structurally safe from cross-vintage contamination." But the belief
silently generalized to *the whole record*, including fields (`pp28_sources`, `status_mapping`,
`kbli_2020_source`, `aggregation_note`, `intel_2026.whatChanged`) that were **never OSS-sourced
at all** — they were authored during the same cross-vintage ingest pass, via the same weak-key
joining process, that produced the Batch A disease. The methodology doc's own §Meta-pattern
already named the general defect ("facts joined across sources by weak keys... with silent
substitution on source-silence, inside pipelines that cannot be re-run") — Batch B is that exact
same disease, resurfacing on a field that happens not to gate the page a client sees, on records
this program had already marked "done."

This is a specific instance of a pattern this organism has now seen three times at increasing
generality (scar family #6, phantom-citation lineage): **W65 "even the refuter allucinates"** →
**W90 "even the ground-truth ages"** → and now, Batch B's founding observation, **"even the
codes marked healthy carry unverified metadata."** Each generation of the lesson moves the
unverified-until-proven-otherwise boundary one layer further from the obviously-suspect surface.
The structural fix this program keeps reaching for — per-fact provenance with a locator and
vintage tag on *every* field, not just the ones that gate a rendered page (methodology P1) — is
the only cure that generalizes past a fourth instance of this same lesson on a fifth field.

## 7. §Solo-operatore (Zero decides — Legge 5)

1. **GO to start Batch B** — same as every phase/batch gate in this program to date
   (methodology §Solo-operatore precedent; Batch A plan's own P2 precondition).
2. **m2′ control-limit numbers (§2.2)** — this draft deliberately does not propose a floor/ceiling;
   pre-registering a falsifiable number for a population this program has never measured before
   is a conductor+Zero call, not something a design-drafting lane should unilaterally fix.
3. **Business call on client-facing disclosure**: Batch A's TRACK-P work put a "Regulatory
   Divergence" section on `/kbli/<code>` pages for codes with an honest-gap `per_skala` — should
   a Batch B metadata-only cure (which never changes served licensing content) get any
   client-visible surface at all, or stay a silent backend correction? This draft's default
   recommendation is **silent-by-default** (nothing the client reads has changed), but it is
   flagged here as a business call, not decided.
4. **Sequencing vs. Batch A's tail**: recommend Batch B Phase 0 (parser build) can start
   immediately in parallel with Batch A's remaining Lots 6-9 (~49 codes) — the populations are
   provably disjoint (§1.1) and no shared canonical-record collision is possible even under
   concurrent compiler writes to *different* records. The one shared-resource risk is CI/fleet
   throughput (the corner's own memory log already shows the pre-push gate flaking under fleet
   contention this week) — a scheduling/pacing call, not a technical blocker.

## Top-3 open design risks

1. **The v0 parser's 544-candidate-mismatch figure is explicitly not a validated defect count**
   (§1.4). It demonstrates leverage and order of magnitude; it must not be quoted downstream as
   "Batch B has 544 known bugs" until Phase 0's real parser + the forward/reverse cross-check
   replaces it. Treating it as ground truth would repeat exactly the W65/W90 lesson this document
   itself names in §6.
2. **m2′'s control limits are genuinely undetermined**, and the stakes of getting them wrong run
   both ways: too loose, and a real population-wide disease (plausible given the 4/4 hit rate on
   accidentally-sampled controls) reads as a false pass; too tight, and Tier 1/2's
   deliberately-adversarial-selected sub-lot (hand-picked to match a known disease shape) trips a
   spurious ceiling breach on its very first run, exactly as Batch A's Lot 1 non-representative
   segment initially did before A-4 corrected the framing. §2.2's proposal to measure Tier 1/2 as
   a separate, explicitly non-representative sub-lot is this draft's mitigation; it needs
   conductor sign-off before Lot B-1.
3. **Coordination overhead scales faster than headcount at 12× the population.** Three
   twin-races already happened at Batch A's scale with (per the memory ledger) essentially one
   or two concurrent lanes; Batch B's design assumes *multiple concurrent lanes as a feature*
   (§5.3), which only stays a feature if the reservation register ships and is actually checked
   before Lot B-1, not retrofitted after the first race.

## Adversarial review

Not yet run. This draft is submitted for the conductor's own review plus the standing 4-LLM
panel (CLAUDE.md §6: Gemini agy + Codex GPT-5.6 + DeepSeek V4 Pro, ~$0.01/section) before any
amendment converts it from DRAFT to a signed pre-registration. No lease, lot, or compiler run may
cite this document as authority until that gate closes and a `## Sign-off` section is appended
here, mirroring the Batch A plan's own discipline.
