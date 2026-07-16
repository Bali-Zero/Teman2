---
date: 2026-07-16
domain: compliance
client_case: none (dataset integrity sweep, not a single client case)
sources:
  - PP 28/2025 Lampiran (OCR-extracted, 4 lampiran txt files under data/source_documents/t0_regulations/)
  - BPS Peraturan 7/2025 (KBLI 2025 codebook, canonical source_documents/KBLI_2025_FINAL_CLEAN.json)
  - OSS RBA ruang-lingkup live lookups (verified 2026-07-16)
---

# KBLI 2025 false-friend sweep — PP28-vs-2025 code-number collisions

## What this is

A repo-wide sweep for the class of bug first caught in 68112 (fixed 2026-07-16,
PR #2508): PP 28/2025's licensing Lampiran tables are numbered on the OLD
KBLI 2020 codebook, while BPS Peraturan 7/2025 defines KBLI 2025 (what OSS
actually uses today). A prior enrichment pipeline joined licensing text to
our dataset by **code NUMBER**, not by **activity**. Where a 5-digit number
was reassigned to a genuinely different activity between the two codebooks,
this grafts the OLD activity's licensing requirements onto the NEW code's
served record — while the judul/uraian (sourced from the 2025 codebook
directly) stay correct. The result: a client reading a KBLI page sees the
right business description but the wrong legal requirements underneath it.

## Method

1. OCR-extracted all PP 28/2025 Lampiran tables (4 files, `t0_regulations/`)
   into structured rows: `{code, judul_pp28, raw_snippet, lampiran_file}`.
   1,167 rows covering 1,137 distinct PP28 code numbers.
2. Joined against our 1,559 KBLI 2025 records by code number where
   `pp28_sources` includes that number (699 codes joined — the rest of our
   1,559 have no PP28 Lampiran counterpart at all, e.g. brand-new 2025-only
   codes with no aggregation history).
3. For each joined pair, scored `judul_overlap` (content-word overlap between
   `judul_pp28` and our 2025 `judul`) and cross-checked which codebook's
   vocabulary the LIVE `per_skala` licensing text actually uses
   (`evidence_overlap_2025` vs `evidence_overlap_pp28`).
4. Auto-verdict: near-zero judul overlap + per_skala evidence pulling toward
   PP28's vocabulary, not 2025's → `CONFIRMED-contaminated`. Ambiguous scores →
   `SUSPECT-mismatch` or `parse-uncertain`. Everything else → `MATCHING`.
5. Manual review pass on every auto-flagged candidate (12 auto-CONFIRMED, 40
   auto-SUSPECT) — cross-checked against the actual PP28 raw OCR snippet and
   the 2025 uraian by hand, reclassifying OCR/spelling-variant and
   generic-boilerplate-word false positives back to `MATCHING` or
   `SUSPECT-mismatch` (lower confidence, not dismissed).

## Calibration

| Metric | Value |
|---|---|
| Our KBLI 2025 codes (total) | 1,559 |
| Distinct PP28 code numbers extracted | 1,137 |
| PP28 Lampiran rows extracted (raw) | 1,167 |
| Codes joined (have a PP28 counterpart) | 699 |

Post-manual-review verdict distribution (of the 699 joined):

| Verdict | Count |
|---|---|
| MATCHING | 645 |
| SUSPECT-mismatch | 47 |
| CONFIRMED-contaminated | 2 |
| ALREADY-REMEDIATED | 1 |
| parse-uncertain | 3 |
| not-applicable | 1 |

Full per-code result set (all 699 joined rows, with both the automated score
and the manual-review note where one exists): `2026-07-16-kbli-false-friend-sweep.json`
(same directory).

## 3 confirmed contaminated (the actionable finding)

- **68112** — residential leasing (2025) vs MICE-venue rental (PP28/2020
  numbering, Lampiran I.L, Sektor Pariwisata p.I.L.44). Fixed 2026-07-16,
  PR #2508 — `per_skala` detached, preserved under
  `per_skala_disputed_pp28_mice`, `_data_note` added, plus a third
  contaminated surface fixed same day (`apps/mouth/data/kbli-gold-all.json`
  gold record, which the sync script doesn't propagate to).
- **51103** — space transport for passengers (2025, brand-new code) vs
  scheduled international commercial aviation for passengers (PP28/2020
  numbering). Fixed 2026-07-16, this PR — `per_skala` detached, preserved
  under `per_skala_disputed_pp28_aviation`, `_data_note` added. Not a gold
  record.
- **51203** — space transport for cargo/goods (2025, brand-new code) vs
  scheduled international commercial aviation for cargo (PP28/2020
  numbering). Same fix, same PR. Not a gold record.

All three: OSS RBA ruang-lingkup returns 404 live (verified 2026-07-16) — no
published risk-based NSPK exists yet for any of them, so `per_skala -> []` is
the honest state, not a guess.

## SUSPECT-mismatch (47 total) — NOT fixed this sweep

None of these 47 met the bar for an automated/confident fix — they need
human regulatory review before touching. Three named clusters are the
highest-concern subset (17 of the 47):

- **25200** — weapons/ammunition manufacturing. Flagged because of the
  regulatory sensitivity of the sector, not because contamination was
  confirmed — needs dedicated review by someone who can read the actual
  defense-sector Lampiran chapter, not a heuristic score.
- **47xxx family, 11 codes** (`47523, 47524, 47594, 47630, 47781, 47782,
  47794, 47795, 47811, 47812, 47832` — all retail-trade codes): a
  judul-pairing/aggregation issue in how PP28's retail chapter maps onto
  2025's retail chapter, not a licensing-content collision like 68112.
  Practically low-harm even if real (retail licensing tends to be uniform
  across sub-codes), but not verified clean either.
- **5 inconclusive**: `20111, 32114, 43216, 43223, 32906` — score signals
  didn't resolve cleanly in either direction; need a human to read the
  actual PP28 snippet vs 2025 uraian side by side.

The remaining **30 codes** in the SUSPECT-mismatch bucket (`10120, 10215,
10217, 10296, 10772, 13923, 13924, 13993, 14302, 15121, 15122, 16212, 20121,
20125, 23955, 26110, 43301, 43901, 49213, 49214, 49221, 50142, 50143, 58120,
66292, 77291, 77292, 77294, 77299, 81300`) were **not** individually named
in this sweep's triage — reading their manual-review notes in the sweep JSON,
most (22 `MATCH_LANGSUNG` + 8 `MATCH_CON_AGGREGAZIONE`) look like heuristic
false-positives from OCR noise in the PP28 extraction (e.g. `10215` PP28
judul OCR'd as "Industn Peragian / Fermentasr Ikan") or generic
manufacturing-boilerplate word overlap tripping the token-overlap score, not
genuine reassignment collisions — but none have had the same manual
cross-check depth as the 17 named above, so they are lower-confidence-clean,
not verified-clean. Do not treat "not named here" as "cleared."

## 3 parse-uncertain — not fixed, not triaged as suspect either

`08914, 10722, 52102` — the OCR extraction of the PP28 Lampiran table
couldn't confidently parse a row for these (garbled table geometry / column
misalignment in the source PDF-to-text conversion), so no judul/evidence
comparison was possible at all. These need either a better OCR pass on the
specific Lampiran page or manual lookup, before any verdict can be assigned.

## What this sweep does NOT claim

- It does not claim the 645 `MATCHING` codes are collision-free by exhaustive
  review — only that the automated score + manual spot-checks found no
  contamination signal.
- It does not claim the 860 un-joined codes (1,559 total − 699 joined) are
  clean by this method — they simply have no PP28 Lampiran counterpart to
  compare against (mostly 2025-only new codes, same situation as 51103/51203
  before this sweep found them via a different route — the join itself, via
  `pp28_sources`, not the judul-overlap score).
- It is a data-integrity sweep, not a legal/regulatory review. The SUSPECT
  and parse-uncertain buckets need a human (ideally NB-3/NB-4 grounded) pass
  before anyone acts on them.
