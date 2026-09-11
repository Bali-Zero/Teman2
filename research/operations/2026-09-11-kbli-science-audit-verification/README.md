---
title: "KBLI 2025 data-chain audit (Claude Science, snapshot 64df83d10b) — row-by-row verification"
date: 2026-09-11
domain: compliance
client_case: none
sources:
  - science-out/ (this folder): Claude Science deliverable, run 2026-09-11 on a read-only snapshot of origin/main 64df83d10b
  - data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json (sha256 5d207ede…, 2422 records / 1559 five-digit)
  - data/source_documents/KBLI_2025_FINAL_CLEAN.json (v10.0-L2-oss-risk, sha256 3dafab17…, 1559 codes)
  - live curls on https://balizero.com/kbli/* and https://knowledge.balizero.com/kbli/* on 2026-09-11 (M5)
  - research/operations/2026-06-19-kbli-2025-ours-vs-oss-ground-truth.md (the June 19 baseline)
adversarial_review: codex
---

# KBLI 2025 data-chain audit — verification of the Claude Science run

**Question the audit answered:** of 1,559 KBLI codes, how many have corpus, website and app aligned
word-for-word with the OSS ground truth?

**Verified answer:** corpus **1559/1559** aligned with OSS (judul and uraian byte-identical; ruang_lingkup
identical after key normalization, OSS `uraian_id` → corpus `uraian`);
**1310/1559** end-to-end on the Indonesian judul + uraian (website subtitle + lead, app subtitle + lead);
**0/1559** if the English h1 must also equal OSS, because OSS carries no translated judul
(`judul_en == judul_id` for all 1559) and the website renders an English h1 for every code
(curated map + generated map); the navigator renders English for its 373 curated codes and
`toTitleCase(judul)` for the other 1186.

This folder holds the Science deliverable (`science-out/`, 342 findings in three CSVs, scripts,
method notes) and the verification of every row (`verification_ledger.csv`).

## Verdicts

| lane | rows | CONFIRMED | REFUTED | NEEDS-RUNTIME | NEEDS-SOURCE |
|---|---|---|---|---|---|
| A — corpus vs OSS | 39 | 39 | 0 | 0 | 0 |
| B — website (apps/mouth) vs corpus | 170 | 160 | 2 | 8 | 0 |
| C — navigator (apps/kbli-navigator) vs corpus | 133 | 125 | 0 | 7 | 1 |
| **total** | **342** | **324** | **2** | **15** | **1** |

Both REFUTED rows are artifacts of the snapshot's scope, not analysis errors (see §3.1).

## 1. How each row was verified

1. **Script re-run on `origin/main` (0b56e22f56, 15 commits after the snapshot).** The six
   Science scripts were executed unchanged against a fresh worktree. All three CSVs, the chain
   alignment JSON and the Lane A stats came out byte-identical, except one Lane B row and its
   numbers file (`B-LEDG-002`, ledger consumers 0 → 1, explained in §3.1).
2. **Independent re-derivation with fresh code (generator ≠ grader).** Without Science's scripts:
   OSS five-digit 1559 = corpus 1559, 0 missing, 0 phantom; judul EXACT 1559; uraian EXACT 1559;
   ruang_lingkup EXACT 1338 + both-empty 221; per_skala scope divergence only on 49213 (4 entries);
   English-map phantoms 82920 and 85598 (both apps); `kbli-gold-all.json` phantoms 8; Kepmenaker
   mapping distinct codes 234 with 0 absent from OSS.
3. **Every cited `file:line` read on disk** on the current checkout: 342 cited rows, 0 missing
   files, all 342 inspected (277 by token match, 65 by eye); 341 resolve exactly and one is
   off by one (C-VER-003 cites 44943 in a 44942-line file — the claim itself is true).
4. **Live observations** on the production site, 2026-09-11: h1 is English (`Restaurant` for
   56101, `Corn Farming` for 01111); the toTitleCase alteration is live on 01192
   (`(bukan Bit Gula)` vs corpus `(Bukan Bit Gula)`); the uraian is rendered verbatim (1217 chars
   for 56101); JSON-LD `Article.description` is the 160-char uraian slice plus PMA/risk prose;
   pages carry `x-nextjs-prerender: 1`; `sitemap.xml` lists exactly 1559 `/kbli/<code>` URLs;
   a phantom code (82920) soft-404s with `noindex`.
5. **Scope re-check on the full repository** for every claim of the form "not imported / no
   consumer / route absent", because the snapshot was partial (§3.1).

`runtime_dependent=true` rows stay NEEDS-RUNTIME by construction; where a live observation was
possible it is recorded in the ledger's `evidence` column.

## 2. What moved since June 19

| metric | 2026-06-19 (v8.0-final, 1563 codes) | 2026-09-11 (v10.0-L2-oss-risk, 1559) |
|---|---|---|
| coverage | 1559/1563, 4 phantoms | 1559/1559, 0 phantoms |
| judul faithful | 1185 (76%), 337 truncated, 4 wrong | 1559 (100%) |
| uraian jaccard ≥ 0.80 | 1408 (90.3%), mean 0.937 | 1559 (100%), mean 1.0 |

The OSS file is unchanged since June 19 (same sha256). The whole movement is on the corpus side
(`metadata.l1_realign`: judul_fixed 1559, uraian_fixed 1550, ruang_lingkup_added 1338).

## 3. Discoveries that change how the findings should be read

### 3.1 The snapshot handed to Science was partial

`apps/mouth/src/app/` in the snapshot contained only `kbli/` and `kbli-explorer/`. Two findings
are therefore wrong on the full repository:

- **B-RT-008** — the OG image route is not absent: `apps/mouth/src/app/api/og/kbli/[code]/route.tsx`
  exists and `https://balizero.com/api/og/kbli/56101` returns 200 `image/png`. REFUTED.
- **B-LEDG-002** — `_regulatory-claim-ledger.json` has 1 consumer under `apps/mouth`, the
  content-freshness sentinel test (fixed-string grep of the file name; the Science re-run on the
  full checkout said 4 because its pattern also matched three Visa Oracle files that read separate
  Markdown claim ledgers). No KBLI page reads it, so the substantive half ("0 of 15 claims used on
  KBLI pages") stands. REFUTED on the count.

Every other "not imported / no consumer" claim (Kepmenaker mapping, `GOLD_CODES`) survived the
full-repo grep. Next run: snapshot the whole `apps/mouth/src` tree, or say in the brief which
directories were excluded.

### 3.2 Lane C audits a surface that is not production

`apps/kbli-navigator/README.md` states PRODUCTION = `apps/mouth` → `balizero.com/kbli`;
`/kbli-navigator/*` 308s to `/kbli/*`. The navigator is served at `knowledge.balizero.com`
behind the kita login (302 to login observed); its Vercel alias
`kbli-navigator-rebuild.vercel.app` returns DEPLOYMENT_NOT_FOUND. The 133 Lane C findings are
correct as static facts, and their client-facing weight is that of an internal, login-gated
surface. All 7 `C-RT-*` rows are NEEDS-RUNTIME for that reason.

### 3.3 Corpus-side defects confirmed (cures not in this PR)

| id | defect | cure |
|---|---|---|
| C-CLAIM-014 | corpus `metadata.source` says `PP28_2024`; 1558 of 1559 records' `_source` say `PP28_2025` (1552 + 6; 01122 is `BPS_7_2025_ONLY`); under `docs/` the string "PP 28/2025" occurs 67× and "PP 28/2024" 18× | fix the metadata string; regenerate `kbli-dataset-version.json` (sha guard) |
| A-DER-0001 / A-PSK-0001 | 49213: 4 `per_skala.scope_uraian` entries differ from OSS `ruang_lingkup[2]` (sim 0.58) | resync scope_uraian from OSS for 49213 |
| C-CLAIM-001…010, C-VER-001 | 13 occurrences of the literal "1,563" in apps/kbli-navigator, 11 outside two historical test comments (Science counted 10) | replace with 1,559 or compute from data — low value while the surface is not production |
| B-PHAN-019, C-PHANTOM-001/002 | English maps keep the 2 dropped phantoms 82920, 85598 | prune the keys (harmless: map lookups only) |
| B-PHAN-033, C-PHANTOM-003…018 | gold tables keep 8 codes absent from OSS (64921, 85300, 85491, 85499, 85600, 86903, 96120, 96130) | prune or declare as legacy; not rendered (no page is generated for them) |
| C-DEC-* | PMA badge unknown for 1505/1559; RiskBadge reads `per_skala[0]` while 525 codes carry mixed tiers | product decision, not a data fix |

### 3.4 The one row that needs a source outside the repo

**C-HARD-001** — `SECTION_META` nameId/nameEn strings in the navigator. OSS has no section
records and the corpus `sektor_id` is a roman-numeral code (`I.C`, `I.D`), so the 21 section
titles can only be checked against BPS Perka 7/2025 itself. NEEDS-SOURCE.

## 4. Verdict on the Claude Science run itself

- **Hit rate on the corpus families (Lane A): 39/39.** Every number reproduced with independent code.
- **Hit rate on the static code-trace rows (B/C, `runtime_dependent=false`): 283/285 CONFIRMED,**
  1 REFUTED (B-LEDG-002, snapshot scope), 1 NEEDS-SOURCE (C-HARD-001), and 1 more scope refutation
  among the runtime-marked rows (B-RT-008). 341 of 342 `file:line` citations resolved on a
  checkout 15 commits newer than the snapshot; one is off by one.
- **Runtime rows: 18 marked, 0 diagnosed.** 15 stay NEEDS-RUNTIME, 2 were confirmed live
  (B-RT-010, B-VERS-002), 1 refuted by the full repo (B-RT-008). The brief's "do not diagnose
  processes" held.
- **Cost of verification:** one session, no new script needed beyond a 60-line ledger builder and
  a 40-line line-checker; the deliverable's own scripts did the heavy lifting because they were
  reproducible (byte-identical on re-run).

Kill-criterion check (research/agent-craft/2026-09-11-claude-science-cosa-e-e-come-usarlo.md):
all three families are far above the 60% floor. The tool stays in the workflow for corpus
censuses and static code traces.

## 5. Files

- `verification_ledger.csv` — 342 rows: `finding_id, lane, family, code, file_line,
  science_confidence, runtime_dependent, verdict, method, evidence`.
- `science-out/` — the Science deliverable: three CSVs, `SUMMARY.md`, `RUN_MANIFEST.md`
  (input/output sha256), `B_METHOD.md`, `C_METHOD.md` and `data/chain_alignment.json` (the
  excluded-code list). The six scripts and the per-lane JSON summaries are NOT in the repo: the size floor
  of the harness (`SIZE_GEAR3_THRESHOLD` 1828 churn lines) would have demanded a Gear-3
  evidence pack for a research bundle. They remain in the Science artifact
  (`science-out-64df83d10b.zip`, and the Desktop copy on M5); their sha256, so a copy can be
  trusted before it is run:

  | script | sha256 |
  |---|---|
  | `chain_alignment.py` | `0d4e5d3a8b610a0ece0bb25d89710c24b7814c6bba6bf2008e1776e8411b742d` |
  | `validate_outputs.py` | `81fe1901c784939efb756c4a294ac4c8db68f8901f9a6235dfc37bcb98301b0d` |
  | `lane_a_corpus_vs_oss.py` | `59e9d7091d65143e7bc060269938f35734c457a8c51e6af99ed6fadbfae5f096` |
  | `lane_b_trace.py` | `57aa1f457fb311a702e70b875249b102518b4ce8f350ff1f4cbfc57e3d2b6a34` |
  | `lane_c_trace.py` | `441e735b67a007c46aa5209232746745c61fc733092d02ee938924a0839020cc` |
  | `write_reports.py` | `609b0f68ca14fcf5b68f043bf7084879bab00f13ded461ca04e53c359e42b1ea` |

Reproduce: from a checkout root containing the full `science-out/` (scripts restored),
`python3 science-out/scripts/lane_a_corpus_vs_oss.py .` then `lane_b_trace.py`, `lane_c_trace.py`,
`chain_alignment.py .`, `validate_outputs.py .` (`write_reports.py` needs a `SNAPSHOT_SHA.txt`).
Re-run on `origin/main` 0b56e22f56 reproduced every CSV byte-identical except the B-LEDG-002 row.

## Adversarial review

**Seat: codex (`codex exec`, read-only sandbox, no network), 2026-09-11, three rounds.**

Round 1 verdict **BLOCK** with 7 findings, all folded:

| id | severity | finding | disposition |
|---|---|---|---|
| F-01 | BLOCK | C-VER-003 cites line 44943 in a 44942-line file; my "0 out-of-range" claim was false (the line checker counted the trailing newline as a line) | ledger evidence rewritten; README §1.3 and §4 corrected |
| F-02 | MAJOR | ledger consumers are 1, not 4 — three Visa Oracle files read separate Markdown ledgers | README §1.1, §3.1 and ledger B-LEDG-002 corrected |
| F-03 | MAJOR | static B/C denominator is 285, not 286 (Lane B has 11 runtime rows, not 10) | §4 corrected |
| F-04 | MAJOR | 342 rows carry a citation, not 339 | §1.3 corrected |
| F-05 | MINOR | "every record" says PP28_2025 — 1558 do; 01122 is `BPS_7_2025_ONLY` | §3.3 corrected |
| F-06 | MINOR | 13 literal "1,563", not 11; the exclusion of two test comments was unstated | §3.3 and ledger corrected |
| F-07 | MINOR | ruang_lingkup is not byte-identical (OSS key `uraian_id` vs corpus `uraian`); identical after normalization | headline reworded |

Round 2 verdict **BLOCK**: the 7 corrections verified as applied (F-05 residual: the ledger
evidence of C-CLAIM-014 still said "every record" — fixed), plus 3 new findings, all folded:

| id | severity | finding | disposition |
|---|---|---|---|
| N-01 | MINOR | 277 + 65 = 342, contradicting "341 resolve" | §1.3 reworded: 342 inspected, 341 exact, 1 off by one |
| N-02 | MAJOR | "both surfaces render an English h1 for every code" is false for the navigator: 373 curated English titles, the other 1186 fall back to `toTitleCase(judul)` | headline reworded; the 0/1559 strict figure is unchanged because the website alone breaks it |
| N-03 | MINOR | "docs cite PP 28/2025 219×" had no stated scope | replaced with fixed-string occurrence counts under `docs/` |

Round 3 verdict **PASS**: N-01, N-02, N-03 and the F-05 residual re-checked by codex on this
checkout (342 = 277 + 65; 373 curated + 1186 fallback; 67 / 18 occurrences; ledger row clean).
