---
date: 2026-07-19
domain: operations
client_case: none (GARUDA-FILIERA Batch B pre-registration DRAFT)
status: DRAFT REV-3 — post 4-LLM panel (Codex GPT-5.6-sol xhigh red-team REJECT with 10
  blockers + 14 majors; Gemini 3.1 Pro constructive with 10 recommendations) then a Codex
  re-check on REV-2 (B1/B4/B9 CURED; B2/B3/B5/B6/B10 PARTIAL; B7/B8 NOT-CURED; SIGN-READY: NO).
  REV-3 closes every residual. Still NOT armed. No lot may run under this document until a
  conductor re-reviews REV-3 and signs it.
sources:
  - "methodology: research/operations/2026-07-16-kbli-filiera-methodology.md (P1-P9, G13-G17, Phase 1-4)"
  - "Batch A plan + amendments A-1..A-10: research/operations/2026-07-18-kbli-batch-a-plan.md"
  - "Batch A lot gate reports: research/operations/2026-07-18-kbli-batch-a-lot{1,2}-conductor-gate.md, research/operations/2026-07-19-kbli-batch-a-lot{3,4}-conductor-gate.md"
  - "calibration lineage: data/kbli-filiera/batch-reports/batchA-calibration-v3.md (v3, signed 2026-07-19)"
  - "cure specs: scripts/kbli_filiera/cure_specs/{metadata_56101,metadata_fixes_2026_07_19,metadata_residuals_2026_07_19}.json"
  - "compilers: scripts/kbli_filiera/cure_canonical_collisions.py, scripts/kbli_filiera/cure_metadata_pp28_sources.py"
  - "membership pattern: data/kbli-filiera/membership/batch-a-members.json"
  - "lot runner to adapt: infra/workflows/kbli-batch-a-lot.js"
  - "data-plane guard registry: infra/claude-hooks/data-plane-registry.json"
  - "canonical dataset (population + consumer-map computed/grepped live this session): data/source_documents/KBLI_2025_FINAL_CLEAN.json"
  - "live consumers grepped this session: apps/mouth/src/lib/{kbli-data.ts,kbli-data.server.ts,kbli-types.ts,types/kbli.ts}, apps/kbli-navigator/lib/{kbli-data.ts,kbli-types.ts}, apps/backend-rag/backend/services/kbli_eye.py, apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py"
  - "BPS Tabel Konversi KBLI 2020-2025 Vol.2 (vault-pinned, sha256 29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949), data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json"
  - "twin-race lessons: lesson_lot1_closeout_twin_race_two_conductors_2026_07_18, lesson_garuda_c1_twin_race_clobbered_prod_sibling_2026_07_18, lesson_outbound_email_twin_race_mailbox_check_2026_07_18 (memory)"
adversarial_review: REV-3 — re-check verdicts incorporated; sign-off pending conductor. REV-1
  panel (Codex sol xhigh REJECT + Gemini 3.1 Pro constructive) is summarized in full in §Panel
  below; the REV-2 re-check (7 residual PARTIAL/NOT-CURED findings) is dispositioned in
  §Changelog alongside the original 24. No lease, lot, or compiler run may cite this document
  as authority until a fresh conductor pass signs REV-3.
---

# Batch B design — the crosswalk-metadata sweep (DRAFT REV-3, pre-registration)

> Conductor note: this document is authored by a dispatched lane (worktree
> `.worktrees/docs-batch-b-design`, branch `agent/air-m5/docs/batch-b-design`), NOT by the
> conductor session itself. It is a **proposal**, structured like the Batch A plan
> (`2026-07-18-kbli-batch-a-plan.md`) so the conductor can amend it in place and sign it the
> same way, but nothing here is armed. REV-1 went through the standing 4-LLM panel and was
> correctly rejected — see §Panel/§Changelog for the full disposition. No lease, no lot, no
> compiler run may cite this file as authority until a conductor signs REV-2 in an appended
> `## Sign-off` section, exactly as the Batch A plan required before Lot 1.

## Panel (REV-1 review — verdicts and where the outputs live)

Two seats reviewed REV-1 of this document, per CLAUDE.md §6's 4-LLM panel discipline
(generator≠grader: neither seat is the authoring lane):

- **Codex GPT-5.6-sol, xhigh effort, read-only red-team.** Verdict: **REJECT — DO NOT SIGN OR
  ARM.** 10 BLOCKERS (B1–B10) + 14 MAJOR findings (M1–M14) + 7 minor findings, closing with a
  10-item "minimum conditions before this can be signed" list. Core charge: the draft's
  cross-lampiran check claimed cross-family independence it didn't have (B1), the object being
  validated (`pp28_sources`) had no stable operational definition (B2 — "the detector therefore
  flags the cure convention itself"), the m2′ metric was left deliberately gameable (B3), the
  census/AQL framing was internally contradictory (B4), the parser evidence was nowhere near
  validation-grade (B5), the gold sets were circular (B6), and the coordination mechanism
  "reproduces the exact twin-race failure it claims to fix" (B7/B8).
- **Gemini 3.1 Pro, constructive seat.** Verdict: **"conceptually excellent... ready for
  conductor sign-off" once four categories of gaps close** — 10 numbered recommendations
  spanning parser rigor (the `sebagian` partial-mapping modifier, `uraian` title-diffing for
  `MATCH_LANGSUNG`, position-anchored `pdfplumber` extraction over whitespace-splitting), lot
  economics (an explicit "unparseable" Tier 2.5, sub-stratifying validated mismatches by
  cardinality, keeping AQL evidence independent of the parser under test), a parser
  ground-truth metric ($m_P$), tier-specific $m_2'$ directions, and two Indonesian-regulatory
  specifics (4-digit `golongan` inheritance, deprioritizing `BPS_ONLY`).

Both seats' full output was read in full by this lane before REV-2 was drafted (session
scratchpad, ephemeral — not a durable repo path, hence not cited as a frontmatter source; every
load-bearing quote from both reviews is reproduced verbatim in §Changelog below so the
disposition is self-contained and auditable without the transient files). REV-2 below
incorporates conductor rulings on all 10 blockers baked in over the panel output; every major
and minor finding is individually dispositioned in the changelog.

## Changelog — REV-1 → REV-2 → REV-3 (all 24 original findings + the 7 REV-2 residuals dispositioned)

**REV-3 note:** Codex's re-check of REV-2 read B1/B4/B9 as **CURED** (unchanged below, no
REV-3 addendum needed) and B2/B3/B5/B6/B10 as **PARTIAL**, B7/B8 as **NOT-CURED** — each of
those 7 rows below now carries a REV-3 addendum closing its specific residual.

| # | Finding (one-line) | Action in REV-2 |
|---|---|---|
| B1 | "Independent" L5↔L10 check is counterfeit independence — same-source agreement can reproduce a shared upstream error | **Renamed** to "same-source consistency check" throughout (§1.4). Every adjudicated code, all tiers, now keeps a genuinely independent, image-grounded cross-family seat on the RAW page render (§4) — the parser output gates *which pages/rows* get pulled, it never substitutes for the independent read. |
| B2 | `pp28_sources` has no stable operational meaning — the detector flags the cure convention itself | **New §2, typed-field split.** Additive `bps_2020_ancestors` field becomes the sole source of truth for full BPS crosswalk ancestry; `pp28_sources` keeps its existing (now precisely documented) role. Grep-verified consumer-map, backfill policy, migration plan. §2.1 corrected mid-review (team-lead, 2026-07-19): 46100/52101 were NOT structurally identical findings treated inconsistently — 46100's pointer was true-but-incomplete, 52101's was outright false, and both were handled consistently under a real ruling ("correct FALSITY; record incompleteness in `_data_note`"). The still-damning fact, kept: that ruling lives only in PR prose, never in the schema — a reader can't tell verified-narrow from falsely-incomplete from the field alone, which is exactly what the typed split fixes. **REV-3 (closes PARTIAL):** §2.5's redefined Tier-1 detector had a scope bug — read literally pre-Phase-0 it would sweep all 409 AGGREGAZIONE/RINUMERATO codes into Tier 1, contradicting the frozen 46-code seed list. Fixed by sequencing: Tier 1/2 (§1.5) are FROZEN at pre-registration and never re-derived; the redefined detector only goes live *after* Phase 0 populates `bps_2020_ancestors`, and even then feeds Tier-3 formation only, never a retroactive Tier-1 relabel. Also: `previousCodes` (the live `pp28_sources`-sourced display prop in `apps/mouth`/`kbli-navigator`) is now named on the §5 field-dependency matrix as the explicit migration target for the follow-up UI PR. |
| B3 | `m2′` left deliberately gameable — undefined direction/denominator/floor-vs-ceiling | **§3.2**, full frozen formula: per-stratum defect-rate, denominator = adjudicated codes only (abstentions/parser-failures reported separately, never in denominator), floor ≥0.10 for Tier 1/2 (yield), ceiling for Tier 4 — numbers proposed and marked CONDUCTOR-PROPOSED/Zero-ratified, not silently assumed. **REV-3 (closes PARTIAL):** four residuals closed — (1) stratum membership FREEZES at lot-open, adjudication outcomes never move a code between strata mid-lot; (2) m2′ computed as a rate only when the adjudicated-denominator ≥10, else raw counts only; (3) per-lot abstention-rate ceiling of 0.30 added (breach = pause, same escalation shape as a defect-rate breach); (4) Tier-4 AQL parameters (n, acceptance number, switching rule) are now a **required output of the Phase-0 gate itself** (§1.4 item 10), named owner conductor+Zero, before any Tier-4 certification can run. |
| B4 | The promised census quietly becomes sampling | **§1.5 reframed**: the Phase-0 parser pass *is* the census (every one of 1,338 gets a mechanical entry). Adjudication is tiered; Tier-4 clean-parse codes get an honest, distinct verdict class (`machine-consistent, not eye-adjudicated`) instead of an implied full validation. Every "code-by-code eye validation" claim for Tier 4 removed. |
| B5 | Parser evidence nowhere near validation-grade; 82%→"~99%" jump was invented; missingness is differential, not random | **§1.4 Phase-0 gate**: adopts Codex's acceptance-criteria list verbatim (frozen row counts, edge-level precision/recall on a stratified manual truth sample incl. wrapped/N:M rows, digests+locators, fail-closed unanchored rows, zero unexplained L5↔L10 diffs) + Gemini's $m_P$ metric. The "~99%" claim is deleted; differential-missingness risk (multi-parent rows disproportionately wrapped) is named explicitly and routed to Tier 2.5, never silently absorbed into Tier 3/4. **REV-3 (closes PARTIAL — the gate still wasn't deterministic):** every number frozen — manual truth sample = 10 pages/lampiran (20 total), stratified to require ≥3 wrapped-row pages and ≥3 N:M-relation pages; page selection seeded deterministically from the parser-run digest (pre-registered, never hand-picked); the 10-page draw splits into disjoint 5-page tuning/holdout halves (tuning may be studied repeatedly, holdout scored blind exactly once); pass = edge-level precision ≥0.995 AND recall ≥0.995 on the holdout half only. $m_P$ is consolidated onto the same tuning half as an early diagnostic (closing the two-inconsistent-sample-specs problem — REV-2 had a separate "random 5-page sample" for $m_P$ alongside the vague stratified sample for the main gate). |
| B6 | Gold sets circular (verified by the same mechanism under test) and not genuinely blind (famous codes) | **Two separate gold registries** (parser-extraction gold vs. metadata-truth gold), per ruling 5. The B2 typed-field split independently dissolves the "expected verdict depends on the disputed convention" problem for 52101/46100 (§2.5). The non-blindness of already-published seed codes (56101/52101/46100/10433) is explicitly acknowledged as a **residual, not fully closed** risk (§3.1) — new NEG/POS material for Batch B onward must be freshly discovered and digest-blinded before any prose names it. **REV-3 (closes PARTIAL — the metadata-truth gold was still labeled via the parser under test and the same Lampiran corpus, with no independent minimum):** the metadata-truth gold set must now include **≥5 FRESH POS controls** — codes never named in any program document — **eye-adjudicated by the conductor directly on raw Lampiran page renders, at Phase-0 close, before Lot B-1 opens** (§3.1). The 4 known cases are formally demoted to regression fixtures only and are **never counted toward the m5 hit-rate denominator**. |
| B7 | No actual locking — PR comments + a shared JSON is a TOCTOU race | **§6 (REV-2)**: CAS-style lease via git's own merge serialization (a reservation PR must be green+merged before its lot dispatches — two competing reservation PRs touching the same tracked JSON conflict on merge by construction), explicit code lists (not vague ranges) for scattered tiers, conductor id + TTL + heartbeat/expiry fields specified. **REV-3 (closes NOT-CURED — Codex correctly called out that "conflict by construction" overstated what git's merge machinery guarantees):** §6 rewritten (§6.1). The reservation register is now a **single JSON object keyed by `lot_id`**. Claiming a lot = writing your own key (`conductor_id`, `code_range`, `opened_at`, `ttl_hours: 12`, `heartbeat`). Precisely stated: **different keys are additive edits and merge cleanly by design** (this is correct/expected — different lots genuinely don't collide, and REV-2's own §1.5 dispatch-order work wants concurrent different-lot lanes); **the SAME `lot_id` claimed twice is a genuine same-key textual conflict**, which is the actual CAS property. Expiry: `ttl_hours` elapsed with no heartbeat comment → any conductor may supersede by overwriting the key with an explicit `superseded_previous` note, auditable in the file's own git history. |
| B8 | "Different records" doesn't make concurrent canonical writes safe — same file, whole-file rewrite conflicts | **§6 (REV-2)**: canonical emits SERIALIZED — at most one open, unmerged canonical-emit PR per batch at any time; a second conductor must wait. Blob-pin re-fencing at emit time (reused verbatim from Batch A plan §4/A-3 precedent) stated explicitly. **REV-3 (closes NOT-CURED — Codex correctly called out that "grep open PRs, then open" is still TOCTOU, and per-batch scope let Batch A and B race on the same canonical file):** §6 rewritten (§6.2). Serialization is now **program-wide** — at most one open canonical-writing PR across Batch A and Batch B and every conductor, at any time. The pre-open grep-then-claim-comment protocol is now **explicitly acknowledged as TOCTOU-imperfect** rather than claimed to prevent the race — the honest backstop is procedure, not the register: a genuine race resolves first-to-merge-wins, and the loser's PR is **regenerated from the new base, never hand-merged or carried forward** (the Batch A plan §8 A-10 precedent, already used in practice), making a race non-destructive and slow rather than silent and corrupting. Blob-pin re-fencing at emit time remains in force unchanged. |
| B9 | Population denominators contradictory (221 vs 114; 1,338 vs 1,340 unexplained) | **New §1.1b, frozen population manifest** — every denominator (1,559 canonical; 221 no-scope; 114 Batch-A original operational scope, a reason-coded *subset* of the 221, not the full 221; 49 Batch-A remaining; 1,338 Batch-B population; the 1,340 BPS-table-observed figure) reconciled in one table, with the ~2-code delta named as an open Phase-0 reconciliation category, not asserted-away as noise. |
| B10 | BPS crosswalk evidence alone cannot certify regulatory inheritance/licensing-basis semantics | **§4**: the D1/D5 task is explicitly split into two layers — (a) mechanical crosswalk-**edge** verification (what Phase-0 + the consistency check establish) and (b) regulatory/**inheritance** adjudication (a separate judgment, reusing the existing 01700-vs-49213 "convergent vs. divergent ancestor regimes" precedent, requiring the independent image-grounded seat and, where needed, PP28 evidence — never claimed to follow from the BPS table alone). **REV-3 (closes PARTIAL — the operative contract registered only BPS locators, with no explicit per-ancestor evidence requirement or verifiable decision rule):** §4 now states a **numbered advancement gate** (item 3): `inheritance_verdict` may move off `not-adjudicated` only when *every* ancestor in `bps_2020_ancestors.codes` has at least one of two evidence classes attached — a PP28-lampiran row **image-verified** (same 300-dpi/locator standard as 68112/49213), or confirmed **OSS-native provenance**. A `bps_2020_ancestors` entry alone, however populated, **never** advances the verdict; a single ancestor missing both evidence classes keeps the code at `not-adjudicated`. |
| M1 | "4/4 hit rate" framing indefensible — denominator not 4, controls not random | Language corrected throughout (§0, §2.1, §3.2) to "4 confirmed cases, tiny and non-random sample" — never stated as a fraction implying a clean trial count. |
| M2 | Lot size 25 has no statistical power justification | **§4** now states plainly: N≥25 is a conductor-review ergonomics choice for Tier 1–3, not a power guarantee; real AQL sample-size/LTPD/producer-consumer-risk parameters are named as an explicit BUILD-phase deliverable, not resolved in this draft. |
| M3 | Contiguous taxonomy lots create cluster bias; tier ordering conflicts with intact-division rule | **§4**: "contiguous taxonomy segment" lot-shape is now scoped ONLY to Tier 4's AQL frame, and even there sampling must be stratified/randomized across divisions, not one contiguous block. Tier 1/2/2.5/3 lots are explicit **code lists**, never taxonomy-contiguous by construction. |
| M4 | m1≥0.75 floor is prevalence-sensitive and weak at n=25 | **§3.1**: floor kept at 0.75 (Batch A precedent) but now stated with its prevalence-sensitivity caveat, plus a per-lot Cohen's-kappa report required alongside raw agreement. |
| M5 | `BPS_ONLY`+null treated as healthy remainder, but absence-of-evidence isn't low-risk | **§1.5, Tier 5**: `BPS_ONLY` (74) + null (1) get their own deprioritized tier with an explicit "no licensing surface, not adjudicated, never called healthy" status — never folded into Tier 4's AQL-sampled "clean" frame. |
| M6 | Cure doesn't atomically cover every derived field | **§5**, field-dependency matrix: enumerates `pp28_sources`, `status_mapping`, `kbli_2020_source`, `aggregation_note`, `intel_2026.whatChanged`, gold `whatChanged`, plus two newly-grepped consumers (`kbli_eye.py`'s reverse-lookup, the Qdrant reindex payload) — one compiler pass, explicit field-vs-field staleness tests required per cure. |
| M7 | `kbli_2020_source = pp28_sources[0]` enshrines arbitrary list order | **§5**: NOT deprecated (a live grep finding — `kbli_eye.py:123` uses it as an active reverse-lookup matching key, not decoration) — instead its scalar "primary/most-specific ancestor for matching" meaning is pinned explicitly, and a genuine consumer-side symptom is flagged: `kbli_eye._resolve_kbli` currently can't resolve merged codes' non-primary 2020 ancestors, a concrete follow-up ticket for `bps_2020_ancestors` once populated. |
| M8 | Append-never-erase preserves false claims with no supersession semantics | **§5**: structured `_metadata_corrections` audit-log array added alongside (not replacing) the prose `_data_note`; prose is explicitly demoted to "historical narrative, never current-state authority" — current state is always read from the field itself. |
| M9 | Aggregation-note dual-convention check is post-hoc convention-shopping | **§1.3**: corrected — the convention is determined *before* the count check (by whether `pp28_sources[0]` equals the code, itself a deterministic fact known in advance), never selected after the fact to make a count fit. Framing tightened to make this explicit; the check is also explicitly demoted from "discovery tool" to "legacy regression gate" given B2's typed-field split. |
| M10 | "Zero false positives" overclaimed — only two derived fields agreeing, not ground truth | Reworded everywhere to "zero additional internal count contradictions" — never "zero false positives against ground truth." |
| M11 | `mapping_metadata_false` too coarse, collapses ≥9 distinct states | **§3.1**: replaced the REV-1 two-way split with four precedented sub-flavors (`edge_wrong`, `edge_missing`, `edge_extra`, `field_vs_note_contradiction` — the last already shipped in `metadata_residuals_2026_07_19.json`); "narrower-by-convention" is retired as a category entirely (it dissolves under §2); parser failure, L5/L10 conflict, and schema ambiguity are resolved *before* Batch B lots start (Phase-0 gate) or routed to Tier 2.5/instrumentation, never into this registry. |
| M12/M13 | "Silent backend correction" contradicts the stated client impact; scope firewall could suppress correlated licensing disease | **§8** business-call language corrected (no default asserted); **§4/§5** add a mandatory cross-batch escalation: any metadata finding implying `per_skala` may also be contaminated routes the code to a Batch-A-style detach lane — Batch B's own compiler still never touches `per_skala`, but it can no longer silently certify a code whose metadata problem smells like a licensing problem too. |
| M14 | Pinning/reproducibility underspecified; membership artifact can orphan on canonical drift | **§1.4/§6**: explicit pin list (BPS PDF digest, parser commit/blob, extraction-tool version+flags, page-numbering convention, canonical input blob, output relation digest, unresolved-row manifest, row locators, exception render digests) + the same blob-refencing-at-emit-time rule Batch A already uses (plan §4/A-3), stated explicitly rather than assumed. |
| minor×7 | encrypted-only-against-editing irrelevant; 1,340 vs 1,338 not "sane"; grammatical ambiguity; `code_range` unsuitable for scattered tiers; reservation file guard-exemption unjustified; Tier-3-yield claim unsupported; "closest to presumed healthy" not a statistical prior | All corrected in place (§1.1b, §1.4, §6). One is a genuine correction of REV-1's own error, confirmed by re-reading the actual registry file: the reservation path is **already** covered by the existing `kbli-filiera` entry's `data/kbli-filiera/**` glob (`infra/claude-hooks/data-plane-registry.json`) — REV-1 asserted the opposite without checking; no new registry entry is even needed. |

## 0. Why Batch B, and why now

Batch A targets the ~221 no-scope codes (OSS `ruang_lingkup` 404) whose `per_skala` was
silently filled from PP28/curatela — a **licensing-payload** disease on codes that were never
OSS-verified in the first place. Three-plus lots in (39/39 quarantined, 0/39 certified — see
`batchA-calibration-v3.md`), that disease is confirmed severe on that population.

**Batch B is a different disease on a different population.** The 1,338 OSS-native codes
(`_l2_source == "OSS_RBA_resiko_2025"`, verified live — see §1) were always treated as the
*trustworthy core* (kbli-navigator corner §1: "structurally safe from cross-vintage
contamination"), because their `per_skala` licensing content comes straight from the 2025 OSS
snapshot, not from a 2020-vintage PP28 proxy. That is still true and **stays true under this
plan — `per_skala` on this population is OUT OF SCOPE for any Batch B cure** (with the M12/M13
escalation-trigger exception in §4/§5: a metadata finding that *implies* licensing contamination
routes the code out of Batch B, it is never silently absorbed).

What is NOT OSS-native, even on these "healthy" codes, is the **crosswalk metadata**:
`pp28_sources`, `status_mapping`, `kbli_2020_source`, `aggregation_note`,
`intel_2026.whatChanged`. These fields assert a *historical* claim — which 2020 code(s) this
2025 code descends from — and that claim was authored during the original cross-vintage ingest,
the same weak-key joining process the methodology doc's §Meta-pattern already indicted for the
Batch A disease. **It was never re-verified for the "healthy" population because the population
looked healthy on the field that gates the served page (`per_skala`).**

The evidence this is real: four crosswalk-metadata disease cases confirmed to date, every one
found **by accident**, as an innocence/gold *control* enrolled to verify something else:

| Code | Found as | Disease | Fix |
|---|---|---|---|
| 56101 | Lot 2 innocence control | false `pp28_sources` ancestry (56103/56104 claimed, true is 56102) | `scripts/kbli_filiera/cure_specs/metadata_56101.json` |
| 52101 | Lot 2 POS gold control | `status_mapping=MATCH_LANGSUNG` false — true 5-parent merge | `metadata_fixes_2026_07_19.json`, then `metadata_residuals_2026_07_19.json` |
| 46100 | Lot 2 innocence control | `status_mapping=MATCH_LANGSUNG` false — true 2-parent merge, missed on first receipt-level review, caught on the *reverse* table | `metadata_fixes_2026_07_19.json` |
| 10433 | Lot 2 POS gold control (Appendix A) | `pp28_sources` wrongly co-attributes 10490, which belongs to a different 2025 code (10419) | `metadata_fixes_2026_07_19.json`, residual closure in `metadata_residuals_2026_07_19.json` |

**Corrected framing (M1):** this is four confirmed cases out of a small, non-random set of
controls — not a clean fraction, and not itself a population-prevalence estimate (§3.2 formalizes
why). What it *does* establish, checked empirically this session (§2.1, §3.2): **all four cases,
in their pre-cure state, would have fallen into what this design calls Tier 4 (the "presumed
clean" bucket), not Tier 1 or Tier 2 (the mechanically-flagged, adversarially-selected
buckets).** That is a materially important, slightly uncomfortable finding this draft did not
have in REV-1, and it directly shapes the tiering and measurement design below.

## 1. Population & stratification

### 1.1 Population — computed live against canonical

```
data/source_documents/KBLI_2025_FINAL_CLEAN.json → data.data (1,559 records)
Predicate: record["_l2_source"] == "OSS_RBA_resiko_2025"
→ 1,338 records; the complement (_l2_source is None) is exactly 221.
```

Verified this session, canonical loaded fresh: `1338 + 221 = 1559`. The `_l2_source` predicate
is a complete, exhaustive partition of the 1,559-code canonical — this arithmetic identity is
solid. What it does **not** by itself establish is that Batch A's and Batch B's *operational*
scopes are jointly exhaustive of anything — Batch A's own operational scope is a reason-coded
*subset* of the 221 (§1.1b resolves this precisely, per B9).

### 1.1b Frozen population manifest (closes B9)

| Denominator | Value | Definition | Source |
|---|---:|---|---|
| Canonical universe | 1,559 | all records in `KBLI_2025_FINAL_CLEAN.json` | canonical `metadata.total_codes` |
| No-scope superset | 221 | `_l2_source is None` (OSS `ruang_lingkup` 404) | computed live, §1.1 |
| Batch A original operational scope | 114 | reason-coded `A-serving/pp28` (113) + `A-serving/orphan` (1) — a *subset* of the 221, NOT the full 221; the remaining 107 were registered as a separate no-scope watchlist, out of Batch A | `2026-07-18-kbli-batch-a-plan.md` §1 |
| Batch A remaining (as of this session) | 49 | 114 minus 65 quarantined across Lots 1–5 (13×5) | `data/kbli-filiera/membership/batch-a-members.json:12-18` census block |
| Batch B population | 1,338 | `_l2_source == "OSS_RBA_resiko_2025"` | computed live, §1.1 |
| BPS-table-observed unique 2025 codes (Lampiran 10, v0 parser) | 1,340 | unique left-column codes across all parsed reverse-table rows | computed live, §1.4 |
| BPS/canonical delta | **2 (named, not dismissed)** | see below | — |

**On the 1,340 vs. 1,338 delta (minor finding, corrected):** REV-1 called this "sane" and
"most plausibly parser noise" — an unsupported claim (0.15% is not self-evidently noise, and the
BPS table's universe need not equal the OSS-native subset at all: a 2025 code can appear in
Lampiran 10 as a crosswalk *target* whether or not OSS ever published a `ruang_lingkup` for it).
This delta is now a **named, open Phase-0 reconciliation category** with candidate explanations
to test, not assert: (a) v0-parser row-duplication/miscount (most likely, given the parser is
explicitly not production-grade), (b) a genuine `BPS_ONLY` code (§1.5 Tier 5, canonical says "no
PP28/2020 crosswalk basis at all") that nonetheless has a row in the *official* crosswalk table —
which would itself be a new, previously-uncatalogued disease shape (canonical's `BPS_ONLY`
classification would be wrong, not just its metadata), (c) a retired/superseded code appearing
as a stray row target. Phase 0 must resolve this into one of these categories (or a named
fourth) before its output is trusted; it is explicitly **not** resolved by this document.

### 1.2 status_mapping distribution over the 1,338 (computed live)

| `status_mapping` | Count | % | Shape |
|---|---:|---:|---|
| `MATCH_LANGSUNG` | 854 | 63.8% | declared 1:1, same code number |
| `CODICE_RINUMERATO` | 224 | 16.7% | declared 1:1, renumbered — different 2020 code |
| `MATCH_CON_AGGREGAZIONE` | 185 | 13.8% | declared merge/split, multiple 2020 ancestors |
| `BPS_ONLY` | 74 | 5.5% | no PP28/2020 crosswalk basis at all (Tier 5, §1.5) |
| (null) | 1 | 0.1% | — (Tier 5, §1.5) |

### 1.3 Mechanically-detectable strata — candidate seed lists, NOT certified defects (B2/M9-corrected)

**Reframing, post-panel:** these structural checks over fields already in the canonical record
were presented in REV-1 as a triage *detector*. Codex's B2 finding is correct: because
`pp28_sources` has no single stable meaning across the corpus today, a structural shape check
over it cannot certify anything — it can only *seed a candidate list* for Phase-0/adjudication to
resolve. That is now their explicit, sole role.

**Empirically verified this session (grounds the "detector flags the cure" charge concretely):**
checking the two cured Tier-1-shaped codes against the *current* canonical —

- **46100** (post-cure): `status_mapping=MATCH_CON_AGGREGAZIONE`, `pp28_sources=['46100']`
  (unchanged, len 1) → this **is** the Tier-1 detector shape (`MATCH_CON_AGGREGAZIONE` +
  `len(pp28_sources)==1`), even though the record is now *correct*: 2020-code 46100 genuinely
  **is** one of its two true parents (`{46100, 63122}`) — the pointer is TRUE, merely incomplete,
  and stays untouched by design, its missing co-parent recorded only in prose. A structural
  detector keyed on this shape flags its own *correct* cure.
- **52101** (post-*residual*-cure): `pp28_sources` was changed from `['52101']` to the *full*
  5-parent list `['03143','03241','03243','03263','52108']` (len 5) — because, unlike 46100,
  2020-code 52101 was never actually one of the five true parents; the original self-referencing
  pointer was FALSE, not merely incomplete.
  **Self-correction (team-lead review, 2026-07-19):** REV-1 called these two "structurally
  identical findings" treated "two incompatible ways" — that mis-recorded history on two counts.
  First, the findings were not identical: 46100's pointer was true-but-incomplete, 52101's was
  outright false — a substantive difference, not an arbitrary split. Second, the two treatments
  are *consistent* under a single ruling — "correct FALSITY in `pp28_sources`; record
  incompleteness in `_data_note`" — stated in the #2777 conductor comment and the #2786 PR body,
  though formalized only *after* #2777 itself had already shipped (which is why 46100, shipped
  inside #2777, and 52101's residual fix, shipped afterward, look superficially inconsistent at
  a glance when they are not).
  **What remains true, and is the actual, still-damning point:** that ruling exists only in
  out-of-band PR prose. Looking at `pp28_sources=['46100']` and the pre-residual
  `pp28_sources=['52101']` side by side, both are self-referencing singleton pointers — a reader
  or a downstream compiler cannot tell, from the field alone, which is "verified-narrow, correctly
  left as-is" and which is "falsely incomplete, needs correcting" without reading the PR history.
  §2 fixes exactly this: making the distinction a structural, machine-readable property of the
  record, not an artifact of prose archaeology.

**Stratum 1 — `MATCH_CON_AGGREGAZIONE` with `len(pp28_sources) == 1`: 46 codes.** Candidate seed
list for Tier 1 (§1.5). First 15 for illustration (the full 46 lives only in the compiler-emitted
membership artifact once Phase 0 ships — never hand-transcribed as authority):
`01272, 05101, 10113, 10304, 10309, 10501, 10502, 12009, 19203, 19204, 22201, 22202, 22209,
23999, 26702, ...`

**Stratum 2 — `MATCH_LANGSUNG` with `pp28_sources[0] != own code`: 16 codes.** Candidate seed
list for Tier 2. Full list (small enough): `02103, 12003, 37002, 47401, 63900, 68210, 74199,
78200, 79903, 80110, 86991, 86992, 86993, 86994, 90130, 96210`.

**Empirically checked this session: none of the four known-diseased codes' pre-cure states match
either stratum** (56101, 52101, 46100, 10433 all pre-cure `MATCH_CON_AGGREGAZIONE` with
`len(pp28_sources)` of 4/1/1/2 respectively, or `MATCH_LANGSUNG` with a self-referencing
pointer — none trip Stratum 1 or 2's mechanical shape). **This is the single most important
finding of REV-2**: the only real evidence available says the confirmed disease so far lives in
what this draft calls Tier 4, not in the adversarially-selected Tier 1/2. §1.5 and §3.2 both
change REV-1's ordering/measurement assumptions in response to this, not just acknowledge it in
passing.

**Stratum 3 — `aggregation_note` internal-consistency check (corrected framing, M9): 198 codes
carry the field.** Convention (self-code included as `pp28_sources[0]` vs. children-only) is
**determined before** the count check — by the deterministic, pre-known fact of whether
`pp28_sources[0] == own code` — never selected post hoc to make a count fit; REV-1's "under BOTH
conventions" phrasing read as convention-shopping and is corrected here. Parsing the note's
declared count under its determined convention and diffing against `len(pp28_sources)` finds
exactly **2 mismatches: 10433 and 49213** — both already known (10433's residual fix left the
note text stale; 49213's A-6(b) restore left the note at its pre-restore wording), **zero
additional internal count contradictions** across the other 196 (M10-corrected wording — this is
agreement between two derived fields, never a ground-truth claim). Demoted, per B2/M9, from
"discovery tool" to **legacy regression gate only** — it will be superseded by `bps_2020_ancestors`
(§2) as the source of truth for ancestry counts going forward.

**Stratum 4 — `kbli_2020_source` vs `pp28_sources[0]`: 314 codes carry `kbli_2020_source`; 0/314
disagree.** Not a redundant decoration as REV-1 assumed to be safely ignorable — see §2.3/§5: it
is a live matching key in `apps/backend-rag/backend/services/kbli_eye.py`.

### 1.4 Phase 0 — the deterministic BPS crosswalk extraction pass, and its acceptance gate

**Terminology correction (closes B1):** the check described below is a **same-source
consistency check**, not an independent cross-family verification. If Lampiran 5 and Lampiran
10 were typeset from the same underlying BPS database export (unverified either way), agreement
between them proves internal consistency of the *published* tables, never truth against
reality. It gates the parser (did it read the same relation the same way from two angles); it
does **not** satisfy the program's cross-family adjudication requirement, which every tier keeps
via an independent, image-grounded seat on the raw page render (§4).

**What is still true and useful:** the vault-pinned BPS Tabel Konversi Vol.2
(`data/kbli-filiera/manifest/vault-manifest-batch0-2026-07-18.json`, sha256
`29f17b3b133497a88c5bfd0eaa3f73c90233b9b95dd76dd0ea2ccaed31724949`) is a 444-page, born-digital
text PDF, confirmed via `pdfinfo` and `pdftotext -layout` producing clean, legible Indonesian
text (the "encrypted" flag on this PDF blocks *editing*, not extraction — noted for completeness,
carries zero evidentiary weight on parsing correctness, per the minor-finding correction). This
remains a materially different situation from the scanned, OCR-hostile PP28 lampiran corpus.

| Lampiran | Direction | Pages | Span |
|---|---|---:|---|
| **Lampiran 5** | KBLI 2020 → KBLI 2025 (forward) | 131–246 | ~115 pp |
| **Lampiran 10** | KBLI 2025 → KBLI 2020 (reverse) | 325–444 | ~120 pp |

A single spot-check against an already-signed ground truth (the A-6(b) 49213 restore, PDF page
399 reproducing the identical three-ancestor rows verbatim) remains real but is **one data
point, not validation** (B5) — it says nothing defensible about the other 443 pages.

**Phase-0 acceptance gate (adopts Codex's list verbatim + Gemini's $m_P$ + Gemini's three parser
requirements — nothing in this gate is optional, and no Batch-B lot may dispatch before it PASSES):**

1. Frozen true-row counts per lampiran (a pinned, independently-verified ground truth, not the
   parser's own output count).
2. **Edge-level precision and recall, frozen numbers (closes B5 residual — REV-2 left this
   gate non-deterministic; Codex's re-check was correct that "stratified manual truth sample"
   had no size, threshold, or seeding, so two conductors could run "the same" gate and get two
   different answers):**
   - **Sample size**: 10 pages per lampiran (20 total across Lampiran 5 + Lampiran 10) — not a
     vague "spanning pages, divisions, wrapped/continuation rows, and N:M relations," a fixed
     count.
   - **Stratification**: each lampiran's 10-page draw is required to include **≥3 wrapped/
     continuation-row pages and ≥3 N:M (many-to-many) relation pages** — the two shapes B5
     named as differentially missed by whitespace-based extraction.
   - **Page selection is pre-registered, not hand-picked**: seeded deterministically from the
     SHA256 digest of the specific parser run being gated (the digest already required by item 9's
     pinning) — a fixed pseudorandom draw over the eligible pages within each stratum, computed
     the same way by any conductor re-running the gate against the same parser-run digest. A
     parser fix produces a new digest, which reseeds a fresh draw — there is no re-scoring the
     same pages after a tune.
   - **Tuning/holdout split**: the 10-page sample per lampiran splits into two **disjoint**
     5-page halves — a **tuning half** (may be read, studied, and used to debug the parser as
     many times as needed) and a **holdout half** (scored **exactly once**, blind).
   - **Pass criterion**: edge-level precision ≥ **0.995** AND recall ≥ **0.995**, measured on the
     **holdout half only**. A miss fails Phase 0 outright — no partial credit.
3. **$m_P$ (Gemini 3.1), consolidated onto the same frozen sample (closes the two-different-
   sample-specs inconsistency Codex flagged):** $m_P$ is the early, cheap tuning-time diagnostic
   — precision/recall computed against the **tuning half** (item 2) while the parser is still
   being debugged, not a separate independent "random 5-page sample" (REV-2's wording, deleted).
   $m_P$ has no pass/fail gate of its own; it exists so the conductor can see convergence before
   spending the one-shot holdout scoring in item 2. Phase 0 is not allowed to stratify the 1,338
   population until item 2's holdout pass is recorded.
4. **Independent coordinate extraction**: row anchoring via `^\d{5}` regex bounding-boxes on the
   Y-axis using a layout-aware library (`pdfplumber`, not `pdftotext -layout` whitespace-splitting
   — Gemini 1.3), so continuation/wrapped rows are captured by position, not lost to a whitespace
   heuristic. This directly targets the 458-row (18%) loss the REV-1 v0 prototype suffered.
5. **The `sebagian` (partial) modifier extracted as a first-class attribute** (Gemini 1.1): BPS
   tables mark non-total splits/merges with `sebagian` next to a code; dropping it collapses a
   partial relationship into a full one, corrupting `aggregation_note`/`whatChanged` generation
   and inflating false `m1` cross-family agreement downstream.
6. **`uraian` (title) diffing for `MATCH_LANGSUNG` codes** (Gemini 1.2): BPS sometimes keeps a
   5-digit code identical while quietly changing its scope text. The parser must extract and diff
   both title columns against canonical, and a same-code/changed-title pair is a distinct finding
   from a true unchanged match — it feeds `whatChanged`, never silently passes as "no change."
7. **Zero unexplained Lampiran 5↔10 edge differences** — any edge present in one direction and
   absent (or contradictory) in the other is either resolved (a parsing gap on one side) or
   explicitly logged as a same-source table inconsistency, never silently dropped.
8. **Fail-closed for every unanchored row** — a row the parser cannot confidently position-anchor
   does not get guessed at; the code it belongs to routes to Tier 2.5 (§1.5), never Tier 3 or 4.
9. **Full pinning (closes M14):** BPS PDF digest (already have, `29f17b3b...`), parser
   commit/blob sha, extraction-tool name+version+flags (`pdfplumber` version, or `pdftotext`
   version+flags if any whitespace fallback remains), page-numbering convention (PDF page vs.
   printed page — already a live distinction in this program, e.g. "printed p.385 / PDF p.399"
   for 49213), canonical input blob sha (re-checked/re-fenced at emit time, §6), output relation
   digest (the parsed crosswalk table itself is a build artifact, sha256-tracked), an
   unresolved-row manifest (every row that failed to anchor, with page + reason), row-level
   page/coordinate locators for every parsed edge, and render digests for any code that
   subsequently gets an image-verify exception.
10. **Tier-4 AQL parameters — REQUIRED OUTPUT of this gate, not left floating (closes the B3
    residual on the Tier-4 ceiling):** before Phase 0 is declared PASSED, it must emit the
    concrete acceptance-sampling parameters Tier 4 will run under — sample size **n**,
    acceptance number, and the switching rule (normal/tightened/reduced, ISO-2859 spirit, per
    §0's AQL framing) — computed from the actual Phase-0-measured edge error rate, not asserted
    in advance. **Named owner: conductor + Zero** (Legge 5 — Tier-4 volume and the residual
    false-negative risk it accepts is a business call, not a lane decision); no Tier-4
    certification may run before this parameter set is signed off.

**4-digit `golongan` inheritance check (Gemini 4.1, Phase-0 mechanical pass):** KBLI 5-digit
(`kelompok`) codes inherit structural scope from their 4-digit (`golongan`) parent; BPS sometimes
revised a 4-digit parent's scope without enumerating the impact on every 5-digit child in the
crosswalk table. Phase 0 adds a programmatic check: if a 4-digit parent's title/scope changed,
every 5-digit child (even ones marked `MATCH_LANGSUNG`) gets a `whatChanged` candidate
annotation for review — this is a mechanical *flag generator*, not an automatic write.

This whole pass costs materially fewer LLM tokens than Batch A's per-code image-render workflow
for the majority of edges that anchor cleanly — but "materially fewer," not the REV-1 "~99%
free" claim, which is deleted as unsupported (B5).

### 1.5 Tiering — the census/adjudication split (closes B4, incorporates Gemini 2.1/2.2/4.2, M3/M5)

**Reframing (B4):** the Phase-0 parser pass, once it clears its own acceptance gate, **is the
census** — every one of the 1,338 codes gets a mechanical per-code entry (an edge set + a
consistency verdict). What is tiered is *adjudication depth*, and Tier 4's honest verdict for a
clean-parse code is a **distinct, named class — `machine-consistent, not eye-adjudicated`** —
never conflated with "certified" or "code-by-code eye validated." Every prior REV-1 sentence
implying whole-population eye validation is removed.

1. **Tier 1** (46 codes, §1.3 Stratum 1) — candidate seed list matching the historical merge
   shape. Explicit code list, never taxonomy-contiguous (M3). **FROZEN at pre-registration**
   (§2.5) — this list does not grow or shrink once §2's typed-field split ships; it is not
   re-derived from the redefined detector.
2. **Tier 2** (16 codes, §1.3 Stratum 2) — candidate seed list, label/pointer contradiction.
   Explicit code list, small enough for 100% review. **FROZEN at pre-registration** (§2.5), same
   reasoning as Tier 1.
3. **Tier 2.5 — unparseable/unanchored (new, Gemini 2.1, closes part of B5/M11)**: any code with
   ≥1 row that failed the Phase-0 fail-closed anchor check, or whose L5↔L10 consistency check
   did not resolve. **Cannot use the parsed table as evidence** — reverts to Batch-A-style D2
   image-render review. This is an explicit third bucket precisely so differential missingness
   (multi-parent rows disproportionately wrapped, per B5) does not silently bias Tier 3's or
   Tier 4's composition.
4. **Tier 3 — parser-validated candidate mismatches**, sub-stratified by topology (Gemini 2.2,
   different cognitive load, different lot):
   - **3A** — 1:1 cardinality mismatches (e.g., a `CODICE_RINUMERATO` code whose pointer disputes
     the parsed edge).
   - **3B** — N:M cardinality mismatches (multi-parent/multi-child complex relations).
5. **Tier 4 — AQL-sampled, presumed-clean remainder.** `per_skala` is never at stake here by
   construction (§0); the AQL sample's evidence **must be the raw PDF image render, not the
   Phase-0 parsed table** (Gemini 2.3 — feeding the parser's own output back to the LLM to verify
   the parser measures reading comprehension, not correctness). Sampling is **stratified/random
   across divisions, not one contiguous taxonomy block** (M3 — contiguous sampling clusters
   ingest-defect correlation by division/page/authoring-batch, biasing any population estimate).
   Real AQL parameters (sample size, LTPD, producer/consumer risk, switching rule) are an
   explicit **BUILD-phase deliverable**, not resolved in this design draft (M2).
6. **Tier 5 — `BPS_ONLY` (74) + null (1) (new, Gemini 4.2, closes M5).** These codes have no
   PP28/2020 crosswalk basis in canonical at all — per OSS RBA's own scope, they track economic
   activities OSS explicitly does not license (internal-government/non-profit functions).
   Deprioritized to the back of the queue **for cost reasons** (zero licensing-navigator value in
   adjudicating their crosswalk metadata), but per M5's correction: **absence of evidence is not
   low risk** — Tier 5 gets an explicit `no-licensing-surface, not adjudicated` status, never
   silently described as "healthy" or folded into Tier 4's clean-sample frame. (Tier 5 is also
   where the §1.1b `BPS_ONLY`-with-a-crosswalk-row reconciliation category, if confirmed, would
   surface as a genuinely new finding.)

**Dispatch-order revision driven by §1.3's empirical finding:** REV-1 implied strict
Tier1→2→3→4 sequential priority. Given all four known-diseased codes were Tier-4-shape pre-cure,
REV-2 recommends **Tier 4's AQL sample start in parallel with Lot B-1 (Tier 1/2), not after
Tier 1-3 clear** — the only real evidence available points at exactly the population REV-1 would
have processed last.

## 2. Schema — the typed-field split (closes B2)

### 2.1 The problem, stated precisely

`pp28_sources` is asked to mean two different things depending on which population a code
belongs to. Even setting that aside, §1.3's 46100/52101 pair shows the deeper problem precisely:
a real, principled ruling governs when a pointer is corrected versus left narrow ("correct
FALSITY in `pp28_sources`; record incompleteness in `_data_note`") — but that ruling lives only
in PR prose, never in the schema itself. A reader (human or downstream compiler) looking at two
self-referencing singleton pointers cannot tell, from the field alone, which one the ruling says
to leave alone (verified-narrow, true-but-incomplete) and which one it says to correct
(falsely-incomplete). That is precisely why a typed split is required — not because the program
applied its own rule inconsistently (it didn't, per the correction above), but because the
rule's output is invisible in the data it governs.

### 2.2 `bps_2020_ancestors` — new additive field

```json
"bps_2020_ancestors": {
  "codes": ["49214", "49219", "49413"],
  "sebagian": [false, false, false],
  "source_locator": [
    {"lampiran": 10, "pdf_page": 399, "printed_page": 385}
  ],
  "parser_run_digest": "<Phase-0 output relation sha256>",
  "adjudication_status": "mechanical-only | tier1-2-adjudicated | tier3-adjudicated | tier4-aql-verified",
  "inheritance_verdict": "inheritable | non-inheritable | not-adjudicated",
  "adjudicated_by": "<seat/session ids, or 'mechanical-only'>",
  "adjudicated_at": "<date>"
}
```

- **Additive only.** `pp28_sources`, `status_mapping`, `kbli_2020_source`, `aggregation_note`
  are unchanged in meaning and unchanged in value by this migration alone — nothing currently
  reading them breaks.
- **Sole source of truth for full BPS crosswalk ancestry** going forward, on the 1,338 Batch-B
  population only (Batch A's 221 codes are out of scope for this field — a later, separate
  program decision, not scope-crept in here).
- **`inheritance_verdict` defaults to `not-adjudicated`, never silently inferred.** A
  mechanically-populated edge set (Tier 4, `adjudication_status: mechanical-only`) never implies
  the licensing regime transfers — that requires the separate semantic judgment §4/B10 describes,
  reusing the 01700 (divergent ancestor regimes, non-inheritable) vs. 49213 (convergent regimes,
  inheritable) precedent.
- **Writers: compilers only**, per data-plane-guard convention (#2550). Two distinct writer
  shapes: (a) a new **bulk** Phase-0 output compiler (`scripts/kbli_filiera/populate_bps_ancestors.py`,
  not yet built) writes `mechanical-only` entries for all 1,338 in one deterministic pass, fully
  logged/diffed; (b) existing **per-code** cure-spec compilers
  (`cure_canonical_collisions.py`) gain a new correction key to bump `adjudication_status` and
  `inheritance_verdict` per-code as Tier 1/2/3 lots close, following the exact
  `status_mapping_correction`/`pp28_sources_correction` pattern already shipped
  (`cure_canonical_collisions.py:36-61`).
- **Backfill policy:** never invented from nothing. Phase 0 populates `mechanical-only` entries
  for every code its acceptance gate clears (§1.4); a code Tier 2.5 catches gets no
  `bps_2020_ancestors` entry until its image-verify review completes; Tier 1/2/3 entries get
  `inheritance_verdict` set only by an actual D1/D5 adjudication.

### 2.3 Consumer-map (grepped live this session — every result below is a real hit, not asserted)

| Consumer | Kind | Reads | Notes |
|---|---|---|---|
| `apps/mouth/src/lib/{kbli-data.ts,kbli-data.server.ts,kbli-types.ts,types/kbli.ts}` | Live web app (`balizero.com/kbli/<code>`) | `pp28_sources` → `previousCodes`, `status_mapping` → `mappingStatus`, `kbli_2020_source` → `kbli2020Source`, `aggregation_note` → `aggregationNote` | Display-layer mapping only, additive change is fully safe |
| `apps/kbli-navigator/lib/{kbli-data.ts,kbli-types.ts}` | Separate Next.js app (`package.json` name `kbli-navigator-rebuild`; has `vercel.json`+`netlify.toml`, i.e. web-deployed, not the "native desktop app" the kbli-navigator corner's prose describes — a corner-vs-disk discrepancy worth a future ALIGN-FLEET check, out of scope here) | Same four fields, near-identical mapping to `apps/mouth`'s | A second, largely-duplicate consumer of the same shape — additive change safe for both |
| `apps/backend-rag/backend/services/kbli_eye.py` | **Live backend service** ("KBLI EYE — Punto fisso deterministico per l'intelligence normativa", Bali PMA compliance checks) | `kbli_2020_source` at lines 100 (output `kbli_2020_ref`) **and** 123 (`_resolve_kbli`'s reverse-lookup match condition: `item.get("kbli_2020_source") == clean_code`) | **Load-bearing, not decorative** (corrects REV-1's assumption). Lets a caller submit an *old* 2020 code and resolve the current 2025 record. Since it matches a scalar, a merged code's non-primary 2020 ancestors are silently unresolvable today — a genuine, previously-uncatalogued consumer-side symptom of the same disease, flagged in §5 as a concrete follow-up. |
| `apps/backend-rag/backend/scripts/reindex_kbli_2025_final.py` | Live-maintained Qdrant/RAG reindex pipeline (last touched 2026-07-09, PR #2189) | `status_mapping` written into the Qdrant payload consumed by `inspect_kbli`/`chat_kbli` | Confirmed live and maintained; additive schema change is safe, but any *value* correction to `status_mapping` needs a reindex to propagate to WA/webchat — a §5 field-dependency-matrix line item |
| `kbli_enrichment_pipeline.py`, `kbli_silver_parallel.py`, `kbli_enrich_deterministic.py`, `generate_gold_content.py`, `kbli_l3_merge_into_final_clean.py`, `kbli_schema_v2_populate.py` | Historical/one-off build-pipeline scripts | `pp28_sources`/`status_mapping`/`kbli_2020_source` for `whatChanged` synthesis, plus `kbli_schema_v2_populate.py`'s derived `l1_normalized.status_mapping_2020` object | Liveness unverified — not asserted dead, not asserted live; a BUILD-phase task should confirm whether any of these are still invoked before assuming they're safe to ignore |
| `scripts/kbli_filiera/cure_canonical_collisions.py`, `cure_metadata_pp28_sources.py` | Writers | write `pp28_sources`, `status_mapping`, `aggregation_note`, `whatChanged` | Gain the new `bps_2020_ancestors`-correction key (§2.2) |

### 2.4 Migration plan

1. Phase 0 ships the parser + acceptance gate (§1.4) — zero schema change yet.
2. `populate_bps_ancestors.py` (new bulk compiler) writes `mechanical-only` entries for every
   code the gate clears, in one deterministic, diffed, sha256-pinned pass. This alone satisfies
   B4's census requirement.
3. Existing per-code cure-spec compilers gain the `bps_2020_ancestors`-correction key; Tier
   1/2/3 lots bump `adjudication_status`/`inheritance_verdict` as they close.
4. **No frontend change required to ship safely** — `apps/mouth` and `apps/kbli-navigator` keep
   reading `pp28_sources` unchanged. Surfacing `bps_2020_ancestors` on the client-facing page (the
   TRACK-P-style "Sources & Verification" panel) is an explicit, separate follow-up PR, exactly
   as Batch A's own TRACK-P UI work shipped separately from its data cures — not built here.
5. **Concrete follow-up flagged, not built here:** extend `kbli_eye._resolve_kbli` to also match
   against `bps_2020_ancestors.codes` (once populated) so a merged code's full ancestor set
   resolves via old-code lookup, not just its scalar primary parent.

### 2.5 How "narrower-by-convention" dissolves; the Tier-1 detector, redefined

Under the split, 52101 and 46100's *correct* state is unambiguous: `bps_2020_ancestors.codes`
carries the full parent set (typed, structured, machine-readable — no longer buried in prose or
inconsistently injected into `pp28_sources`, closing the §2.1 inconsistency directly);
`pp28_sources` is simply whatever it already was, frozen, historical, no longer asked to also
mean "the complete crosswalk ancestry." There is no longer a judgment call — "is this pointer
deliberately narrow or falsely incomplete" stops being a question the moment
`bps_2020_ancestors` exists and is populated; it is either populated correctly (done) or not yet
populated (Tier 4/mechanical-only, honestly labeled as such).

**Sequencing fix (Codex re-check on REV-2, corrected in REV-3): the redefined detector does NOT
retroactively resweep Tier 1/2.** REV-2's wording — "Tier-1 candidacy is `status_mapping
declares AGGREGAZIONE/RINUMERATO AND bps_2020_ancestors is absent or mechanical-only`" — read
literally and applied *today* (before Phase 0 has run) would sweep in **all 409**
`MATCH_CON_AGGREGAZIONE`(185) + `CODICE_RINUMERATO`(224) codes, since `bps_2020_ancestors` is
absent for every one of the 1,338 until Phase 0 populates it — directly contradicting the frozen
46-code Tier-1 seed list §1.5 pre-registers. That is a real 9× scope explosion, not a rounding
error, and the fix is sequencing, not a different formula:

1. **Lot B-1 and B-2 run on the FROZEN §1.5 seed lists (46 + 16), pre-registered and unchanged**
   — these are the hand-picked, structurally-flagged candidates this document commits to
   processing first, regardless of what the typed-field split later reveals about the rest of the
   corpus. Nothing about §2's schema work moves or grows these two lists.
2. **The redefined detector (`status_mapping` declares a merge/renumber shape AND
   `bps_2020_ancestors.adjudication_status == "mechanical-only"`) becomes the ONGOING triage
   instrument only *after* Phase 0 has actually populated `bps_2020_ancestors` for the
   population** — at that point "absent" no longer applies to anyone (Phase 0's bulk pass gives
   every clearing code a `mechanical-only` entry, §2.2/§2.4), so the condition collapses to
   exactly "mechanically-populated but not yet adjudicated," a real, bounded, honest signal.
3. **Its output feeds Tier-3 lot formation, never a retroactive Tier-1 relabeling.** Codes
   already adjudicated in Tier 1/2 (their `adjudication_status` advanced past
   `mechanical-only`) drop out of the detector's candidate set automatically; codes newly
   surfaced by the detector after Phase 0 runs are new Tier-3 material (§1.5), not Tier-1
   material — Tier 1/2 membership is a closed, one-time, pre-registered set, not a live query
   re-evaluated as the schema fills in.

## 3. Measurement design

### 3.1 What carries over, with corrections

- **m1 (cross-family extractor-vs-extractor IAA), floor 0.75** — kept at the Batch A precedent
  value, but stated now with its **prevalence-sensitivity caveat** (M4): at n=25 with a dominant
  "no-defect" class, raw agreement can read high while hiding poor sensitivity on the minority
  (defect) class. Every lot report must include a **per-lot Cohen's kappa** alongside raw
  agreement, not raw agreement alone. Same-family agreement is never a valid m1 reading
  regardless of how high it reads (`batchA-calibration-v3.md:24`, scar W100).
- **m3 (refutation-category registry) — reworked sub-flavors under `mapping_metadata_false`
  (closes M11):** `edge_wrong` (a declared ancestor is factually incorrect), `edge_missing` (a
  true ancestor omitted from `bps_2020_ancestors`), `edge_extra` (a declared ancestor doesn't
  belong), `field_vs_note_contradiction` (already-shipped flavor,
  `metadata_residuals_2026_07_19.json`). **"Narrower-by-convention" is retired as a category —
  it dissolves under §2.** Parser failure routes to Tier 2.5 (instrumentation, not m3). L5/L10
  same-source conflicts are resolved *before* any lot starts (Phase-0 gate item 7, §1.4), never
  an m3 finding. Schema/convention ambiguity is resolved by §1.3's deterministic
  convention-detection fix, never an m3 finding either. The rest of the v3 closed-7 registry
  (`code_collision, illegitimate_inheritance, wrong_authority_level, source_absent_in_vault,
  payload_cross_contamination, unresolvable_source_pointer`) carries over unchanged.
- **m4 (tokens/dossier ceiling)** — carries over as a ceiling/runaway-guard, expected lower than
  Batch A's ~197k/dossier average given Phase 0 replaces per-code image extraction for the
  majority of edges — but "materially fewer," never the deleted "~99% free" claim (B5).
- **m5 (gold-set hit rate) — TWO SEPARATE REGISTRIES (closes part of B6):** a **parser-extraction
  gold set** (withheld rows with known-correct edges, used only to gate Phase 0 itself, §1.4 item
  3's $m_P$) and a **metadata-truth gold set** (NEG/POS controls for lot-level D1/D5
  adjudication, structured exactly like Batch A's — digest-pinned sha256, blind to lanes,
  reveal-after-close). POS controls are still pre-verified on both Lampiran directions before
  enrollment (standing protocol since `batchA-calibration-v3.md:123`), but pre-verification now
  runs against an **$m_P$-gated** parser (§1.4), materially reducing (not eliminating) the
  circularity B6 charged. **NEG-set residual risk, explicitly not fully closed:** 56101, 52101,
  46100, 10433 are already named in this very document and in merged cure specs — they cannot be
  made blind to any agent that recognizes the codes. They remain usable as **known-answer
  regression fixtures** (do they still read correctly), never as a claim of a fresh, unbiased
  NEG sample. Every new NEG/POS item Batch B discovers from here forward must be freshly found
  and digest-blinded before this document or any lot report names it in prose.
  **Residual, closed in REV-3 (Codex's B6 re-check: the metadata-truth gold was still labeled by
  the parser under test and the same Lampiran, with no independent minimum):** the
  metadata-truth gold set must include **≥5 FRESH POS controls** — codes never named in this
  document, any prior Batch A/B document, or any merged cure spec — **eye-adjudicated by the
  conductor directly on raw Lampiran page renders** (not via the parser's structured output, not
  via any prior lot's finding) **at Phase-0 close, before Lot B-1 opens**. These 5 are the actual
  independent truth this metric needed; the 4 known cases (56101/52101/46100/10433) are demoted
  to regression fixtures ONLY and are **never counted toward the m5 hit-rate denominator** —
  their continued correct behavior is checked, but contributes no evidence of generalization.

### 3.2 m2′ — full frozen definition (closes B3, REV-3 closes the 4 residuals from Codex's re-check)

**Formula:** per-stratum defect rate = (# codes in stratum adjudicated as a genuine
`mapping_metadata_false` sub-flavor, §3.1) ÷ (# codes in stratum **adjudicated** this lot).
**Denominator explicitly excludes** abstentions and Tier-2.5 parser-failure codes — both are
reported as a separate abstention-rate metric, never folded into the defect-rate denominator (a
direct answer to B3's "are abstentions in the denominator" question: no).
**"Narrower-by-convention, leave unchanged" no longer exists as a verdict** (§2.5) — it cannot
be used to inflate or deflate a rate.

**Residual 1 — stratum membership freezes at lot-open.** A code's tier assignment is fixed the
moment its lot opens (§6.1's reservation record pins the code list). Findings that emerge
*during* adjudication — e.g. a Tier-1 code whose true disease shape turns out to look more like
a Tier-3 pattern — never move that code to a different stratum mid-lot; they are recorded as-is
against the stratum it was opened under, and re-tiering (if warranted) happens only as a
decision at the *next* lot boundary. This prevents exactly the kind of after-the-fact
reclassification that would let a lot's own results reshape its own denominator.

**Residual 2 — minimum-N gate on the rate itself.** m2′ is only **computed as a rate** when the
adjudicated-denominator for that stratum in that lot is **≥ 10**; below that, the lot report
states raw counts (e.g. "2/6 defect") and explicitly declines to compute or publish a rate —
a rate on n<10 is not statistically meaningful and REV-2 left this open-ended.

**Residual 3 — abstention-rate ceiling.** Per-lot abstention rate (Tier-2.5 parser-failures +
any D1/D5 `abstain.needed` flags ÷ total codes attempted that lot) is capped at a **ceiling of
0.30**; breach pauses the lot, same escalation shape as a defect-rate breach. This is a new
number for Batch B — no exact numeric abstention-ceiling precedent exists in Batch A's own
plan/calibration docs (checked this session, none found) — but it follows the same qualitative
discipline the methodology doc's P9 already establishes (quarantine/abstention is a state
machine with resolution criteria, never silently tolerated without limit), made numeric and
falsifiable here for the first time.

**Direction, per stratum (Gemini 3.2 + conductor ruling):**

- **Tier 1 / Tier 2 (adversarially selected — matched to the historical merge/label-contradiction
  shape): FLOOR ≥ 0.10.** A lot reading *below* 0.10 is not a normal pass — it is a declared
  **"hypothesis falsified, stop-and-rethink"** pause, because these codes were specifically
  chosen to match a known disease shape. Given §1.3's empirical finding (all 4 known cases were
  Tier-4-shape, none Tier-1/2-shape), a first-lot reading near or at 0/62 is a **live,
  non-hypothetical risk this design must anticipate, not a remote edge case** — flagged again in
  the risk list below.
- **Tier 3A/3B (parser-validated candidate mismatches):** **no floor/ceiling proposed in this
  draft** — genuinely no prior exists yet. Explicitly deferred to a conductor+Zero call at Lot
  B-3 kickoff, once Tier 1/2 data exists to inform it. Stated as **unresolved-by-design**, not
  silently left blank the way REV-1 left the whole metric blank (the difference: REV-1 left
  *everything* undefined; REV-2 defines everything it can and names exactly the one number that
  must wait for more evidence, with the reason stated).
- **Tier 4 (AQL-sampled, presumed-clean): CEILING = 0.15, CONDUCTOR-PROPOSED / Zero-ratified,
  not silently assumed.** Derivation, stated honestly: the raw "accidental-find" rate this
  program has observed on codes drawn from this population is ~4 out of ~6 controls (≈0.67) —
  but that raw rate is *not* usable directly as Tier 4's ceiling, for three stated reasons: (a)
  tiny-n; (b) the controls were selected as sentinel gold/innocence checks specifically because
  the protocol already distrusted them, not a random draw of the population; (c) — the strongest
  reason — every one of the four confirmed cases would, pre-cure, have been *Tier-4-shape*
  itself, meaning there is **zero clean Tier-4 evidence** to anchor a ceiling on at all. Proposing
  0.15 — well below the raw 0.67 — is the conservative choice: it treats the "4/4 were Tier-4-shape"
  finding as a live warning, not something to average away, and it keeps the ceiling meaningfully
  falsifiable (a ceiling near 0.67 would functionally never breach, which is decoration, not a
  control limit, per B3's own critique).
- **Tier 5 (`BPS_ONLY`+null):** no defect-rate metric at all — explicitly out of m2′'s scope, per
  its `no-licensing-surface, not adjudicated` status (§1.5).

## 4. Lot shape

**D1/D5 task, redefined in two explicit layers (closes B10):**

1. **Mechanical edge verification** — does this code's `bps_2020_ancestors` (once populated)
   agree with the Phase-0 same-source-consistent parse? This layer is what the BPS crosswalk
   evidence can actually support (B10's core point) and is largely deterministic.
2. **Regulatory/inheritance adjudication** — a separate judgment, never claimed to follow from
   the BPS table alone: does the licensing/regulatory regime attached to the true 2020
   ancestor(s) actually transfer to the 2025 code, reusing the program's own existing precedent
   (01700: divergent ancestor regimes → non-inheritable; 49213: convergent regimes across all
   three ancestors → inheritable). This layer requires the independent, image-grounded
   cross-family seat on the raw page render — **for every adjudicated code, all tiers** (closes
   B1's "adjudication seats never see parser output" requirement and Gemini 2.3's AQL-independence
   point simultaneously: Tier 4's AQL sample is evaluated against the raw render, never the
   parser's own output, precisely so the check never measures the parser grading itself).
3. **Advancement gate for `inheritance_verdict`, stated as a numbered rule (closes the B10
   residual — Codex's re-check was correct that the operative contract as written registered
   only BPS locators, with no explicit evidence requirement or verifiable decision rule):**
   `inheritance_verdict` may move off `not-adjudicated` **only** when, for **every** ancestor
   listed in `bps_2020_ancestors.codes`, at least one of the following two evidence classes is
   attached and cited by locator — reusing Batch A's own D0 evidence taxonomy, not inventing a
   third:
   - **PP28-lampiran evidence**: the ancestor's licensing-authority row in the relevant PP28
     lampiran, **image-verified** (300-dpi render, page/coordinate locator recorded, same
     standard as the 68112/49213 precedents), or
   - **OSS-native provenance**: the ancestor's post-2025 successor already carries a live,
     OSS-native `ruang_lingkup` record (`_l2_source == "OSS_RBA_resiko_2025"`) that the adjudicator
     confirms genuinely describes the same licensing surface.
   A `bps_2020_ancestors` entry **alone — mechanically populated, unadjudicated — never advances
   `inheritance_verdict`**, regardless of `adjudication_status`; the crosswalk table proves an
   ancestry relationship exists, never that its regulatory regime transfers. If any single
   ancestor lacks both evidence classes, the code stays `not-adjudicated` and routes to Tier 2.5
   or the next tier's manual queue — it does not get a partial or majority-rule verdict.

**Lot composition, corrected (closes M2/M3):**

- Tier 1/2/2.5/3A/3B lots are **explicit code lists**, never taxonomy-contiguous — these
  populations are curated/scattered by construction (mechanical flag, not a division range), and
  forcing them into a contiguous-division shape (as REV-1's blanket rule implied) would either
  violate contiguity or scatter Tier-1 codes across artificial lot boundaries for no reason.
  N≥25 codes/lot is a **conductor-review ergonomics choice**, stated explicitly as such — not a
  statistical power guarantee (M2). Real power/AQL math (sample size vs. true defect rate,
  producer/consumer risk) is a named BUILD-phase deliverable for the Tier-4 sampling plan
  specifically, not resolved here.
- Tier 4's AQL frame is the **only** place a taxonomy-ordered span is used, and even there the
  actual sample drawn from within that span must be stratified/randomized across divisions
  (M3 — a literal contiguous block clusters exactly the ingest-defect correlation this metric
  exists to detect).

**Runner delta from `infra/workflows/kbli-batch-a-lot.js`:** the D1/D5 propose→blind-refute→
deterministic-diff architecture is reused; what changes is the evidence input (raw page render
for adjudication, §4 above — never the parser's own table, closing Gemini 2.3) and the
membership gate now points at `data/kbli-filiera/membership/batch-b-members.json` (Phase-0
compiler output, tier-tagged). Concrete deliverable `infra/workflows/kbli-batch-b-lot.js` remains
a BUILD-phase task, not written here.

## 5. Cure conventions

**Field-dependency matrix (closes M6) — every Batch B cure must atomically address:**

| Field | Role | Written by |
|---|---|---|
| `pp28_sources` | frozen/historical, no longer the ancestry source of truth (§2) | existing compiler, unchanged unless a genuine `pp28_sources` falsity (not an ancestry-completeness question) is found |
| `bps_2020_ancestors` | new, sole ancestry source of truth (§2.2) | new bulk + per-code compiler paths |
| `status_mapping` | mapping-shape label | existing compiler |
| `kbli_2020_source` | scalar "primary/most-specific ancestor for matching" — pinned meaning, not deprecated (M7) | existing compiler, kept in sync with `pp28_sources[0]` by the SAME write, or a fresh field-vs-field staleness is created (the exact `aggregation_note` failure mode repeating) |
| `aggregation_note` | legacy prose, demoted to non-authoritative narrative (§1.3 Stratum 3) | existing compiler |
| `intel_2026.whatChanged` (canonical) | client-facing prose | existing compiler |
| gold `whatChanged` (`apps/mouth/data/kbli-gold-all.json`) | masks canonical on live page for gold-listed codes (49213/50115 precedent) | separate gold-layer write, same PR, Codex-gated |
| Qdrant payload `status_mapping` (via `reindex_kbli_2025_final.py`) | WA/webchat-consumed | requires a reindex step after any `status_mapping` value correction — a release-checklist line item, mirroring Batch A's A6 per-surface checklist |
| `apps/mouth`/`apps/kbli-navigator` `previousCodes` display prop (§2.3, `raw.pp28_sources → previousCodes`) | client-facing "previously known as" UI element | **explicit migration target for the §2.4 follow-up UI PR** — once `bps_2020_ancestors` exists, `previousCodes` should re-point at it (the full, correct ancestor set) instead of the frozen/historical `pp28_sources`; not built in this document (§2.4), but named here so the field-dependency sweep doesn't lose track of it |

**Supersession semantics (closes M8):** the append-never-erase prose `_data_note` convention is
kept (it remains a valuable audit trail) but is explicitly demoted to **historical narrative,
never current-state authority** — a consumer needing current state reads the field, never parses
the note. A new, structured `_metadata_corrections` array is added alongside it:
`{field, old_value, new_value, date, pr, supersedes}` per correction — machine-readable,
queryable, and the actual mechanism for detecting field-vs-note staleness going forward (the
exact defect class 10433/49213's stale notes already demonstrated).

**Cross-batch escalation trigger (closes M12/M13):** if a Batch B metadata finding implies the
*licensing* payload may also be contaminated (not just its ancestry metadata) — e.g. an
`edge_wrong`/`edge_missing` finding on a code whose `per_skala` content looks suspiciously
generic or mismatched to its own title — the code is **quarantined and routed to a
Batch-A-style detach lane**, never silently certified as "metadata-only, per_skala untouched."
Batch B's own compiler still never writes `per_skala` (§0's firewall holds), but it can no
longer treat a metadata defect as evidence that everything else on the record is fine.

**`kbli_2020_source` follow-up (M7), stated as a ticket, not built here:** extend
`kbli_eye._resolve_kbli` (`apps/backend-rag/backend/services/kbli_eye.py:123`) to also check
`bps_2020_ancestors.codes` membership once populated, so old-code lookups resolve correctly for
every true ancestor of a merged code, not just the scalar primary.

**Unchanged from REV-1 (still correct, restated):** correct FALSITY, never touch `per_skala`,
compilers-only, pins after data commit.

## 6. Coordination

**REV-3 status: B7 and B8 were the two NOT-CURED findings on Codex's re-check of REV-2** — its
core objection was correct: "two PRs modifying the same JSON file don't conflict by
construction — git does textual merges, not semantic-overlap detection." REV-2's phrasing
overstated what git's merge machinery actually guarantees. This section restates the mechanism
precisely, names what it does and does not prevent, and states the honest backstop.

### 6.1 Lot-level reservation (closes B7)

The reservation register (`data/kbli-filiera/membership/batch-b-lot-reservations.json`) is a
**single JSON object keyed by `lot_id`**, not an array:

```json
{
  "B-L1": {
    "conductor_id": "<session/agent id>",
    "code_range": ["46 Tier-1 codes"] ,
    "opened_at": "2026-07-19T12:00:00Z",
    "ttl_hours": 12,
    "heartbeat": "<PR comment URL, refreshed on activity>",
    "status": "open | superseded | closed"
  }
}
```

**Precise conflict mechanics (this is what actually holds, stated exactly, not asserted
loosely):**

- **Different `lot_id` keys are additive JSON edits on non-overlapping lines.** Two lanes
  claiming *different* lots and opening PRs concurrently will, in the ordinary case, **merge
  cleanly** — this is correct and expected behavior, not a race: different lots genuinely do not
  collide, and the file's shape (one key per lot) is chosen specifically so that the common case
  (multiple lanes working different lots at once, which REV-2's own §1.5 dispatch-order revision
  now actively wants) doesn't manufacture artificial conflicts.
- **Two claims on the SAME `lot_id`** are edits to the *same JSON key* — a genuine textual
  overlap, so git's three-way merge produces a **real conflict** on the second PR to attempt to
  land, which is exactly the property a CAS lease needs: the second claimant cannot merge without
  manually resolving against the first claimant's already-merged key, at which point the
  file itself (now showing an existing, unexpired reservation) tells them to stop.
- **Expiry:** `ttl_hours` (12) elapsed with no `heartbeat` refresh (a PR comment on the open lot)
  means the reservation is stale. Any conductor may then **supersede** it — not append to it,
  **overwrite** that key's value with a new reservation carrying an explicit
  `"superseded_previous": {"conductor_id": "...", "reason": "ttl-expired, no heartbeat"}` note, so
  the overwrite itself is auditable in the file's own git history.

**Registry correction (minor finding, self-corrected in REV-2, unchanged in REV-3):** the
existing `kbli-filiera` entry's `protected` glob in `infra/claude-hooks/data-plane-registry.json`
already covers `data/kbli-filiera/**`, so the reservation path is guarded automatically — no new
registry entry needed. Only `scripts/kbli_filiera/` compilers may write it.

### 6.2 Canonical-emit serialization (closes B8)

**Rule, corrected per-batch scope (REV-2 said per-batch; REV-3 widens it as instructed):** at
most **one open, unmerged canonical-writing PR, program-wide, across Batch A and Batch B and
every conductor, at any time.** Pre-open protocol: grep open PRs for any diff touching
`data/source_documents/KBLI_2025_FINAL_CLEAN.json` (or its tracked mirror copies) **and** post a
claim comment on the PR **before** opening it, not after.

**Honest limit, stated plainly (Codex is right, and REV-2 should have said this instead of
implying the register prevents the race):** this pre-open grep-then-claim protocol is
**TOCTOU-imperfect** — two conductors can still grep at the same near-instant, both see no open
PR, and both open one. Nothing in this design makes that structurally impossible; git cannot
detect semantic overlap between two PRs that both patch different lines of the same JSON blob
but represent contradictory intent on the same record. **The backstop is procedure and
regeneration, not the register:**

1. If two canonical-emit PRs genuinely race, the **first to merge wins**; this is not prevented,
   only made visible (the second PR's diff, computed against a base that predates the first
   merge, will very likely conflict on file-level diff at merge time even where the *records*
   touched are logically disjoint, because both emits rewrite the same large JSON file).
2. The losing PR is **never hand-merged or carried forward against the new base** — it is
   **regenerated from the new post-merge canonical**, exactly the resolution Batch A's own A-10
   amendment already used in practice (`2026-07-18-kbli-batch-a-plan.md` §8, A-10: the M5 lane
   conceded content-equivalence to the Pro lane's already-merged PR and reworked its own PR down
   to its orthogonal, non-overlapping delta, rather than attempting to force a stale diff through).
   This makes a race **non-destructive and slow, not silent and corrupting** — the losing
   conductor loses time re-deriving its diff against the new base, never data.
3. Blob-pin re-fencing at emit time (`plan §4`/A-3 precedent: pin the content-authoritative blob
   sha, re-check and re-base if it moved before merging) is what actually catches a stale-base
   emission mechanically, independent of whether the pre-open grep worked — this remains in
   force from REV-2, unchanged.

**Twin-race pattern, restated (unchanged reasoning from REV-1/REV-2, still holds):** Batch A's
Lot 2 twin (M5 vs. Pro, independently convergent 13/13-quarantine verdicts) shows independent
convergence on the *same, openly-claimed* scope is a feature; the A-10 twin (a race on shared
scope neither lane knew the other held) is the failure mode this section's procedure narrows,
never fully eliminates.

## 7. §Meta-pattern

**What single defective belief generated the metadata layer's disease?** The belief was:
*"OSS-native `ruang_lingkup` means the record is safe."* True for the field it actually gates
— served `per_skala` licensing content. False as a generalization to the whole record: fields
authored during the same cross-vintage ingest pass (`pp28_sources`, `status_mapping`,
`kbli_2020_source`, `aggregation_note`, `intel_2026.whatChanged`) were never OSS-sourced at all.
REV-2 adds one layer to this diagnosis the panel surfaced that REV-1 didn't have: **the disease
also lives in the program's own operational vocabulary, not only the data** — `pp28_sources` was
treated inconsistently by the *cure process itself* (46100 vs. 52101, §2.1) precisely because no
schema distinguished "licensing pointer" from "full ancestry," the same weak-key-collapsing
failure mode this program keeps finding in the data, now found in its own tooling.

This is a fourth generation of the same lineage (scar family #6): **W65 "even the refuter
allucinates"** → **W90 "even the ground-truth ages"** → **Batch B's own founding observation,
"even the codes marked healthy carry unverified metadata"** → and now, **"even the cure
convention itself can silently mean two things."** The structural fix — per-fact provenance with
a locator and vintage tag on every field, typed and schema-distinguished, not just the fields
that gate a rendered page (methodology P1) — is the only cure that generalizes past a fifth
instance of this same lesson on a sixth field.

## 8. §Solo-operatore (Zero decides — Legge 5)

1. **GO to start Batch B** — pending REV-2's own re-review; same standing precedent as every
   phase/batch gate in this program.
2. **m2′ numbers (§3.2)** — Tier 1/2 floor 0.10 and Tier 4 ceiling 0.15 are proposed here with
   stated derivations, explicitly marked CONDUCTOR-PROPOSED/Zero-ratified, not silently assumed;
   Tier 3A/3B is explicitly left open, deferred to a Lot B-3 kickoff decision.
3. **Business call on client-facing disclosure (corrected, M12/M13):** no default is asserted in
   this revision — REV-1's "silent-by-default" recommendation directly contradicted its own
   stated client-impact claim ("a wrong what-changed sentence") and is deleted. Whether any
   Batch B metadata cure gets a client-visible surface (mirroring TRACK-P's Regulatory
   Divergence pattern) is a business call this draft does not pre-judge; §5's field-dependency
   matrix at least makes clear which fields are client-visible today (gold `whatChanged`,
   `aggregation_note` on `apps/mouth`) so the decision has a concrete surface list to act on.
4. **Sequencing vs. Batch A's tail:** Phase 0 can start in parallel with Batch A's remaining
   Lots 6-9 — populations provably disjoint (§1.1b). Canonical-emit serialization (§6) is a
   per-batch rule; Batch A and Batch B emits still need their own cross-batch ordering
   discipline if both are mid-emit at once — flagged, not resolved, since Batch A's own emit
   cadence is outside this document's authority.
5. **New from REV-2: is the reservation-register process (§6) worth building as real
   BUILD-phase tooling before Lot B-1, given Batch B's ~12× scale, or is the lighter Batch-A-style
   claim-comment convention sufficient until a race actually recurs?** This draft's own position
   (stated, not decided): build it — three twin-races already happened at 1× the scale.

## Top remaining risks (post-REV-3)

1. **The Tier 1/2 hypothesis has zero empirical support so far** (§1.3/§3.2) — all four confirmed
   disease cases were Tier-4-shape pre-cure. A first Tier 1/2 lot reading at or near its 0.10
   floor is a live, anticipated possibility, not a remote edge case; the "hypothesis falsified,
   stop-and-rethink" pause this draft pre-registers for that outcome must actually be honored,
   not quietly waived because the codes were "obviously" going to be diseased.
2. **Phase 0's acceptance gate (§1.4) is a hard, non-negotiable precondition, and it is real
   engineering work** — position-anchored `pdfplumber` extraction, `sebagian`/`uraian` handling,
   the now-frozen 10-page-per-lampiran truth sample, and the $m_P$ tuning diagnostic are all
   unbuilt. Nothing in REV-3 should be read as "the parser is basically done, tune the numbers"
   — it is closer to "the parser's *design* and its gate's *numbers* are now specified enough to
   build," which is a meaningfully earlier stage than REV-1 implied.
3. **The typed-field split (§2) touches a live backend matching service
   (`kbli_eye.py`) and two duplicate frontend consumers** discovered only by grepping this
   session — the migration is additive and should be safe, but "should be safe" is not the same
   as verified; the BUILD phase must run the actual consumer surfaces (not just read their
   source) before this is called done, per CLAUDE.md §2's PROVE-LIVE discipline.
4. **REV-3's coordination fixes (§6) are a precisely-stated procedure, not a guarantee** — B8's
   honest limit stands: two conductors can still race past the pre-open grep on a genuine
   coincidence. The design accepts this and makes the race non-destructive (regenerate, not
   carry forward) rather than claiming to prevent it; a BUILD-phase reviewer should not mistake
   "TOCTOU-imperfect, acknowledged" for "TOCTOU-imperfect, unaddressed."

## Sign-off

Not yet signed. REV-3 is submitted for a fresh conductor pass; per the panel's own generator≠grader
discipline, this authoring lane does not grade its own revision. A `## Sign-off` section is
appended here only after that re-review closes.
