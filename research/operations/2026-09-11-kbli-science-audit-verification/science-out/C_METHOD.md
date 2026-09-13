---
date: 2026-09-11
domain: compliance
client_case: none
adversarial_review: exempt-claude-science-deliverable-verified-row-by-row-in-parent-README
---

# Lane C — kbli-navigator app vs corpus vs OSS (static audit)

Snapshot SHA: 64df83d10b (SNAPSHOT_SHA.txt). Static analysis only; nothing about the deployed site, API, Vercel/Fly or build output is asserted.

## Command

```
python3 science-out/scripts/lane_c_trace.py
```

Writes `science-out/kbli_app_vs_corpus.csv`, `science-out/data/lane_c_render_map.json`, `science-out/data/lane_c_numbers.json` (every number below). Python 3.11 stdlib only; no node runtime was available, so all TypeScript rules were ported to Python inside the script.

## Files read

- Source of truth: `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` (1559 records with digits==5).
- Corpus: `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (sha256 3dafab17f6c48477c34ae562d74d5015faeba74a44fee125ee9267c6c45da2e8); byte-identity with `apps/kbli-navigator/data/kbli-2025.json` and `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` re-asserted by one sha256 line.
- `data/kbli-filiera/pma-editorial-certifications.json` (imported by `lib/kbli-editorial-certification.ts`).
- `apps/kbli-navigator/data/kepmenaker-228-jabatan-mapping.json`.
- All of `apps/kbli-navigator/{app,components,lib}/**` (read manually; line numbers in the CSV are resolved by the script via `find_line` on literal code fragments, so they follow the file).

Not imported by any `.ts/.tsx` in the snapshot (grep): `data/kepmenaker-228-jabatan-mapping.json`, `data/gemini-research-input.json`, `lib/kbli-gold-codes.ts` (GOLD_CODES referenced only in a test comment). The snapshot contains no `package.json`/`next.config` for the navigator, so build wiring is out of scope.

## Families (controlled set)

FIELD_TRACE (positive trace, rendered field -> corpus field), SCHEMA_DIVERGENCE (type/loader vs corpus schema), HEURISTIC (derived transforms), HARDCODED (constants with no data source), CLAIM_LEDGER (numeric/regulatory claims in code), VERSION_MISMATCH, PHANTOM_CODE (5-digit key absent from OSS), JABATAN_PHANTOM (Kepmenaker mapping analysis), DECISION_INPUT (verdict/badge logic and its input field), RUNTIME (data sourced outside the shipped JSON; runtime_dependent=true).

## Definitions

- **Verbatim**: rendered string is byte-equal to the corpus field (which itself equals OSS `judul_id`/`uraian_id` for 1559/1559 codes; `ruang_lingkup` (id, uraian) pairs equal for 1559/1559).
- **toTitleCase port**: `text.toLowerCase().split(/\s+/)`; word 0 always capitalised; 15 listed Indonesian stop-words kept lower; joined by single space. Counted as changed if `toTitleCase(judul) != judul`.
- **titleEn**: `ENGLISH_TITLES[code] ?? titleId`; ENGLISH_TITLES parsed from `lib/kbli-english.ts` with regex `^\s*"(\d{5})":\s*"(.*)",\s*$`.
- **Hash gate port**: `stableEditorialSha256 = sha256(JSON.stringify(sortKeysDeep(value)))`, emulated with `json.dumps(..., ensure_ascii=False, separators=(",",":"))`; `pmaEditorialFingerprint` over the 12 disclosed PMA fields; `hasPublishablePmaCap` and `disclosePmaInfo` ported line by line from `lib/kbli-pma-disclosure.ts`. The two standaloneGold entries (47111, 65121) were parsed out of `lib/kbli-gold-content.ts` with a minimal JS object-literal parser (double-quoted strings, template literals, nested objects/arrays). Both content SHA-256 and both PMA fingerprints match the certification file, and 49/49 canonicalIntel entries match, so the port is exact.
- **uraian not lead**: detail page shows gold prose (certified standalone gold) or `intel_2026.whatItMeans` (certified canonical intel) instead of `kbli.description` (`app/kbli/[code]/page.tsx`, gold branch vs `kbli.intel_2026?.whatItMeans ? ... : kbli.description`).
- **Phantom**: a 5-digit key in an app-side table that is not one of the 1559 OSS 5-digit `kode`. None of the phantoms exists in OSS as a 2/3/4-digit record either.
- **Jabatan schema**: `categories[i].gold_codes` (KBLI codes) <-> `categories[i].sub_sectors[j].jabatan[k]` (no, isco, name_id, name_en). Also `gold_code_mapping{code -> category}` and `key_insights.*[].gold_codes_affected` (list, or an int count in 3 entries — skipped). A (jabatan, code) pair is phantom when the code in the category's `gold_codes` is absent from OSS. Total jabatan = explicitly listed jabatan objects; declared total = sum of `categories[].total_jabatan`.
- **DECISION_INPUT recompute**: for every rule keyed on judul/uraian text (toTitleCase, extractKeywords, `slice(0,150)`, `slice(0,200)`, search penalty `len>500` in 100-char steps) the rule was evaluated with corpus `judul/uraian` and with OSS `judul_id/uraian_id`; a change is counted when the two outputs differ. Rules keyed on `per_skala`, `pma_*`, `l4_bali`, `status_mapping` are ENRICHMENT (OSS has no counterpart) — outcome distributions recorded, no change count.
- **Quotes**: no quoted text longer than 80 characters anywhere; claims < 200 chars (asserted in script).

## Numbers computed

Alignment: judul==judul_id 1559/1559; uraian==uraian_id 1559/1559; ruang_lingkup equal 1559/1559 (1338 codes non-empty in both); OSS judul_en==judul_id 1559/1559.

Rendering (detail page `h1` = titleEn, subtitle = titleId, lead = description):
- toTitleCase changes judul for **209/1559** codes (subtitle and card `<p>` not verbatim).
- ENGLISH_TITLES: 375 entries, 373 in OSS, 2 phantom (82920, 85598). h1/card h3 differ from judul for **529/1559** (373 curated + 156 title-cased only); h1 == judul for 1030.
- uraian rendered verbatim as lead on 1510/1559 detail pages; replaced on **49** (2 gold + 47 intel-only; all 49 certified intel codes, incl. the 2 gold). Metadata truncates uraian at 150 chars (1395 codes longer), JSON-LD at 200 (1241 longer). Search length penalty applies to 517 codes (>500 chars).
- `ruang_lingkup` (1338 codes) is not typed, loaded or rendered anywhere in the app.
- Section derived from code prefix; `sektor_id` (18 distinct OSS-style values, null for 217) never read; 0 codes outside the prefix map; 21 of 22 SECTION_META entries receive codes (V has none).

Tiers after certification: gold 2 (47111, 65121), silver 372, bronze 1185. PMA disclosure: located 54, declared_gap 1505 (test expects 1,505 — matches). Disclosed status: unknown 1505, open 3, restricted 51. PMABadge outcomes: unknown 1505; open·100% 3; restricted·closed(0%) 19; restricted·Max 49% 25; restricted·Max 80% 6; restricted·special 1. Page verdict banner: NOT_VERIFIED 1505, BALI_NOT_BLOCKED 34, CLOSED_NATIONAL 19, BALI_BLOCKED 1. BaliStatusBadge shown for 54/1559 although all 1559 carry `l4_bali`. RiskBadge (per_skala[0]): Low 522, Medium-Low 305, Medium-High 258, High 257, no badge 217 (empty per_skala); 525 codes have >1 distinct kategori_risiko across per_skala. TransitionBadge absent for 1 code (01122, no status_mapping).

OSS-input recompute of text-keyed rules: toTitleCase 0, extractKeywords 0, slice150 0, slice200 0, search penalty 0 changes out of 1559.

Phantoms: ENGLISH_TITLES 2, GOLD_CODES 8/304, KBLI_GOLD_CONTENT 8/322, GOLD_HERO_IMAGES 28/1523, KBLI_ARTICLE_MAP 0 (prefix-keyed only), certifications 0. 4 of the 4 codes recorded in corpus `metadata.l1_realign.phantoms_dropped` (26120, 60111, 82920, 85598) still appear in ENGLISH_TITLES / GOLD_HERO_IMAGES.

Claims: "1,563" occurs at 10 file:line positions across lib/app; "22 sectors" once (app/page.tsx:376); certification `sourceDatasetSha256` equals the shipped corpus sha256 (true).

Jabatan: 216 jabatan listed vs 1678 declared; 395 code references (234 in categories, 110 gold_code_mapping, 51 key_insights); 234 distinct codes; **0 absent from OSS, 0 absent from corpus; 0 phantom (jabatan, code) pairs**.

CSV: 133 rows — FIELD_TRACE 22, SCHEMA_DIVERGENCE 12, HEURISTIC 5, HARDCODED 7, CLAIM_LEDGER 14, VERSION_MISMATCH 3, PHANTOM_CODE 48, JABATAN_PHANTOM 3, DECISION_INPUT 12, RUNTIME 7.

## Exclusions / limits

- No node runtime: TS rules ported to Python; ports validated by exact hash reproduction (49/49, 2/2). Title-case port assumes `toLowerCase`/`toUpperCase` agree with Python `lower()`/`upper()` on the judul character set (Latin only).
- SECTION_META names and the Bali moratorium/Gubernur-letter citation in `lib/kbli-bali-l4.ts` cannot be checked against snapshot data (OSS ground truth has no 1-digit records) — marked TO VERIFY.
- `apps/kbli-navigator/app/api/vitals`, `components/WebVitals.tsx`, `LanguageToggle.tsx` carry no KBLI data and produced no rows.
- Gold editorial prose bodies (322 entries) were not fact-checked against corpus fields beyond the hash gate; only their keys were audited.
- No personal data encountered; jabatan entries are job titles only and are not listed individually in the CSV (0 phantom pairs).
