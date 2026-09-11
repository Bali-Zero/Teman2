---
date: 2026-09-11
domain: compliance
client_case: none
adversarial_review: exempt-claude-science-deliverable-verified-row-by-row-in-parent-README
---

# RUN_MANIFEST — KBLI 2025 data-chain audit

Snapshot: git origin/main SHA `64df83d10b` (SNAPSHOT_SHA.txt). Read-only; outputs only under `science-out/`.
Static analysis only. No statement in any output refers to a deployed system, daemon, cron, database or Fly; rows that would depend on runtime carry `runtime_dependent=true`.

## Input files (sha256)

| file | sha256 |
|---|---|
| `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` | `5d207ede14f9b63f18fae5c0538e38bf743d018c437e34a02fc90b24d98b56b2` |
| `data/source_documents/KBLI_2025_FINAL_CLEAN.json` | `3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8` |
| `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` | `3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8` |
| `apps/kbli-navigator/data/kbli-2025.json` | `3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8` |
| `apps/mouth/data/kbli-dataset-version.json` | `efdba41a3592f457cb4a3f880157519b6c8de358e14f6e9f298343762da49598` |
| `apps/mouth/data/kbli-perpres-slice-disclosures.json` | `0bae979518cf6780a88d06826f0f830ca53dac6d4e52cb583855ea64f6c9c316` |
| `apps/mouth/src/content/_regulatory-claim-ledger.json` | `bb520d6d2ce69e5186c40138d33bea41b9cd361bec2f65d0396b3f231ad9eda8` |
| `apps/kbli-navigator/data/kepmenaker-228-jabatan-mapping.json` | `63834bb6dfc42ee6d194d84c70a832e446e9b3eed52fc51c2e73ff0fde53384a` |
| `research/operations/2026-06-19-kbli-2025-ours-vs-oss-ground-truth.md` | `ba90190634ec07a3a56f9f6cc37678a9d0f2d1ceb0009b28a5e000001f1721ac` |

The three corpus copies share one sha256, so Lanes B and C read the same bytes as Lane A.

## Commands (run from the snapshot root, Python 3 stdlib only)

```
python3 science-out/scripts/lane_a_corpus_vs_oss.py .
python3 science-out/scripts/lane_b_trace.py
python3 science-out/scripts/lane_c_trace.py
python3 science-out/scripts/chain_alignment.py .
python3 science-out/scripts/write_reports.py .
python3 science-out/scripts/validate_outputs.py .
```
Re-running the first four scripts reproduced byte-identical CSV/JSON outputs (checked by sha256 before/after).

## Output files

| file | sha256 | rows |
|---|---|---|
| `science-out/kbli_corpus_vs_oss.csv` | `fe43b83dd9d517e19146282db901e69d8a7ad7867e9918bd6f93240491e91955` | 39 |
| `science-out/kbli_site_vs_corpus.csv` | `f00c7d82198dca85561e1ba0fede2cf85c57333e4154903184d9dc7a40b87fe5` | 170 |
| `science-out/kbli_app_vs_corpus.csv` | `88dacf737cccece2e8026daf5c6f8d4df2915ffa618b9ee3b9a931e3e711999f` | 133 |
| `science-out/data/chain_alignment.json` | `70ae6738dba143ca6d97d6f517f7d8abf69b628bce7a1854c744b31316af7dd0` | - |
| `science-out/data/lane_a_per_code.json` | `7e75e0f25d7aa3d8c026ba2bb5b63adf619daa986ca698ebbdb5483b1914b0c6` | - |
| `science-out/data/lane_a_stats.json` | `bcaf124565c32fb4a7aadc7dc3daa77ff38d41302c44417b5e0d5c1dc89d9856` | - |
| `science-out/data/lane_b_numbers.json` | `ed7b24638ef155d5aeffea248ad10a3161c7d001007ef559061d1ff73958a9c3` | - |
| `science-out/data/lane_b_render_map.json` | `a8a49be0fad88fae5b5834d2244b90b5255cb9ee785e72c203f04af4ce7e078c` | - |
| `science-out/data/lane_c_numbers.json` | `4087967febd1324ae6e3a725905ebca332af67c1679ee7e61ab099875cb8e977` | - |
| `science-out/data/lane_c_render_map.json` | `4e89c9d3a2179aa2d8fcfb16f90e1b5855fe94b86060094ad10cf193a972dc1b` | - |

## CSV schema (all three lanes)

`finding_id, family, code, file, line, claim, confidence, runtime_dependent, suggested_fix` — exactly these columns. `code` is one 5-digit KBLI code or empty (structural). `file` is relative to the snapshot root; `line` is 1-based (range allowed). No quoted span longer than 80 characters; claims under 200 characters. Enforced by `validate_outputs.py`.

## Lane A — definitions and thresholds

- Join key: OSS `kode` (records with `digits == 5`, n=1559) ↔ corpus `kode_kbli_2025`.
- Field pairs: corpus `judul` ↔ OSS `judul_id`; corpus `uraian` ↔ OSS `uraian_id`; corpus `ruang_lingkup[].{id,uraian}` ↔ OSS `ruang_lingkup[].{id,uraian_id}`.
- OSS `judul_en`/`uraian_en`: no corpus counterpart (class NO_CORPUS_FIELD); verified equal to `judul_id`/`uraian_id` for 1559/1559 codes, so an EN comparison would duplicate the ID comparison.
- norm(s) = NFKC → casefold → drop Unicode category P* → collapse whitespace → strip.
- EXACT: raw strings equal. NORMALIZED: norm equal, raw differ. TRUNCATED: norm(OSS) starts with norm(corpus) and corpus shorter. DIVERGENT: otherwise.
- sim = difflib.SequenceMatcher ratio on norm strings (0–1). jaccard = token-set Jaccard on norm strings (the June 19 method). June 19 'fedele' threshold for uraian: jaccard ≥ 0.80; 'quasi' ≥ 0.95; 'sporco' < 0.50.
- ruang_lingkup classes: EXACT (same id order and text), NORMALIZED_OR_REORDERED, DIVERGENT, MISSING_IN_CORPUS, EXTRA_IN_CORPUS, BOTH_EMPTY.
- ENRICHMENT = corpus top-level field with no OSS counterpart (one row per field with its record count). Not an error.
- per_skala[].scope_uraian is checked against OSS `ruang_lingkup[scope_index].uraian_id` (DERIVATION / PER_SKALA_SCOPE_DIVERGENT).
- Exclusions: OSS records with digits 2/3/4 (863) are not compared (corpus has 5-digit only). Corpus `intel_2026`, `l4_bali`, `pma_*`, `per_skala` content is not fact-checked, only inventoried.

## Lane B / Lane C — definitions

Full method notes, ported TypeScript rules, heuristics and exclusions are in `science-out/B_METHOD.md` and `science-out/C_METHOD.md` (written by their scripts). Key shared definitions:
- FIELD_TRACE: rendered field → corpus field, confidence 1.0. HEURISTIC: value computed by code (toTitleCase, slice, regex, fallback, prefix map). HARDCODED: literal in source. OTHER_FILE: rendered from a non-corpus file (English title maps, gold content, slice disclosures).
- toTitleCase ported literally from each app's kbli-data.ts; 'changed' = ported output != corpus judul (209 codes in both apps, sets identical).
- English title precedence: website `ENGLISH_TITLES[code] ?? ENGLISH_TITLES_GENERATED[code] ?? titleId` (kbli-data.ts:330-334); navigator `ENGLISH_TITLES[code] ?? titleId` (lib/kbli-data.ts:365).
- Editorial certification gates (which pages replace the uraian lead with editorial prose) were reproduced by porting the sha256/fingerprint logic to Python; ports validated by matching registry sizes (website: 49 intel / 15 gold; navigator: 49/49 and 2/2 exact hash matches).
- Truncation counts use JS `slice` semantics (UTF-16 code units); website JSON-LD 160, navigator metadata 150 and JSON-LD 200.
- PHANTOM_CODE: 5-digit key in an app-side table that is not among the 1559 OSS codes (and separately, not in the corpus).
- DECISION_INPUT (Lane C): text-keyed rules were re-evaluated with OSS judul_id/uraian_id in place of corpus judul/uraian; outcome changes counted. Rules keyed on corpus-only enrichment (per_skala, pma_*, l4_bali, status_mapping) are recorded without a change count.
- Exclusions: test files cited only as intent; explorer (`/kbli-explorer`) and landing search are remote-API driven → RUNTIME rows only; no node runtime in the sandbox, so TypeScript was ported, not executed.

## Chain alignment definitions (chain_alignment.py)

corpus_aligned(code)  : Lane A judul_id EXACT and uraian_id EXACT and ruang_lingkup EXACT/BOTH_EMPTY
  STRICT surface align  : every rendered title/description text on the code page equals the corpus field
                          byte-for-byte: website = hero.h1_title, hero.subtitle_judul, lead.uraian;
                          app = titleEn (h1), titleId (subtitle), description (lead).
                          Metadata/JSON-LD truncations are excluded (not page body) and reported separately.
  ID-TEXT surface align : only the Indonesian text surfaces (subtitle judul + lead uraian) must be verbatim;
                          the English h1 is treated as ENRICHMENT with no OSS counterpart (OSS has no
                          translated judul: judul_en == judul_id for all 1559).
  Full chain            : corpus_aligned AND website aligned AND app aligned, under each definition.

## Validation

`validate_outputs.py` checks: exact column set; confidence ∈ [0,1]; runtime_dependent ∈ {true,false}; unique finding_id; 5-digit or empty code; cited file exists in snapshot; line format; no single-line quoted span > 80 chars in any CSV cell or .md; no email-like or 16-digit strings (personal-data heuristics). Result at time of writing: 0 violations.
