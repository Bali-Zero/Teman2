---
date: 2026-09-11
domain: compliance
client_case: none
adversarial_review: exempt-claude-science-deliverable-verified-row-by-row-in-parent-README
---

# SUMMARY — KBLI 2025 data-chain audit (snapshot `64df83d10b`)

Source of truth: `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` (2422 records, 1559 with digits == 5). Static analysis; nothing here describes a running system.

## Findings per lane, by family and confidence

### Lane A — corpus vs OSS — `kbli_corpus_vs_oss.csv` — 39 rows (runtime_dependent=true: 0, TO VERIFY: 0)

| family | rows | conf 1.0 | 0.9–0.99 | 0.7–0.89 | <0.7 |
|---|---|---|---|---|---|
| COVERAGE | 1 | 1 | 0 | 0 | 0 |
| DERIVATION | 1 | 1 | 0 | 0 | 0 |
| ENRICHMENT | 33 | 33 | 0 | 0 | 0 |
| PER_SKALA_SCOPE_DIVERGENT | 1 | 1 | 0 | 0 | 0 |
| SCHEMA | 3 | 3 | 0 | 0 | 0 |

### Lane B — website (apps/mouth) vs corpus — `kbli_site_vs_corpus.csv` — 170 rows (runtime_dependent=true: 11, TO VERIFY: 0)

| family | rows | conf 1.0 | 0.9–0.99 | 0.7–0.89 | <0.7 |
|---|---|---|---|---|---|
| CLAIM_LEDGER | 18 | 18 | 0 | 0 | 0 |
| FIELD_TRACE | 31 | 31 | 0 | 0 | 0 |
| HARDCODED | 30 | 26 | 4 | 0 | 0 |
| HEURISTIC | 26 | 26 | 0 | 0 | 0 |
| OTHER_FILE | 8 | 7 | 1 | 0 | 0 |
| PHANTOM_CODE | 34 | 34 | 0 | 0 | 0 |
| RUNTIME | 10 | 10 | 0 | 0 | 0 |
| SCHEMA_DIVERGENCE | 8 | 8 | 0 | 0 | 0 |
| VERSION_MISMATCH | 5 | 5 | 0 | 0 | 0 |

### Lane C — navigator app vs corpus — `kbli_app_vs_corpus.csv` — 133 rows (runtime_dependent=true: 7, TO VERIFY: 3)

| family | rows | conf 1.0 | 0.9–0.99 | 0.7–0.89 | <0.7 |
|---|---|---|---|---|---|
| CLAIM_LEDGER | 14 | 13 | 0 | 1 | 0 |
| DECISION_INPUT | 12 | 12 | 0 | 0 | 0 |
| FIELD_TRACE | 22 | 22 | 0 | 0 | 0 |
| HARDCODED | 7 | 5 | 1 | 0 | 1 |
| HEURISTIC | 5 | 5 | 0 | 0 | 0 |
| JABATAN_PHANTOM | 3 | 3 | 0 | 0 | 0 |
| PHANTOM_CODE | 48 | 48 | 0 | 0 | 0 |
| RUNTIME | 7 | 7 | 0 | 0 | 0 |
| SCHEMA_DIVERGENCE | 12 | 12 | 0 | 0 | 0 |
| VERSION_MISMATCH | 3 | 3 | 0 | 0 | 0 |

## Lane A headline

- Coverage: OSS 5-digit 1559, corpus 1559 (metadata.version v10.0-L2-oss-risk); missing in corpus 0, phantom in corpus 0.
- judul vs judul_id: EXACT 1559/1559. uraian vs uraian_id: EXACT 1559/1559 (sim mean 1.0, jaccard mean 1.0).
- ruang_lingkup: EXACT 1338, both empty 221 (OSS _rl_status=no_scope set == corpus _l2_status set: True).
- judul_en/uraian_en: corpus has no field; OSS EN equals ID for 1559/1559 (judul) and 1559/1559 (uraian).
- ENRICHMENT fields with no OSS counterpart: 33 (see CSV). per_skala scope_uraian: 9090 entries, 4 differ from OSS ruang_lingkup (codes: 49213).

## June 19 audit — three headline numbers, then and now

| metric | June 19 (corpus v8.0-final, 1563 codes) | now (corpus v10.0-L2-oss-risk, 1559 codes) | moved? |
|---|---|---|---|
| Code coverage | 1559/1563 real; 0 OSS codes missing; 4 phantom | 1559/1559 real; 0 missing; 0 phantom | yes — 4 phantoms removed (listed in corpus metadata.l1_realign.phantoms_dropped) |
| judul faithful (EXACT+NORMALIZED) | 1185/1559 (76%); 337 TRUNCATED; 4 wrong | 1559/1559 (100%); 0 TRUNCATED; 0 DIVERGENT | yes — +374; the 4 forestry judul (02102, 02103, 02401, 02402) are now EXACT |
| uraian faithful (jaccard ≥ 0.80) | 1408/1559 (90.3%); mean 0.937; 14 below 0.50 | 1559/1559 (100%); mean 1.0; 0 below 0.50 | yes — +151; all 1559 byte-EXACT |

The OSS ground-truth file is unchanged since June 19 (sha256 prefix 5d207ede cited in that note equals the snapshot file). The movement is entirely on the corpus side (metadata.l1_realign: judul_fixed 1559, uraian_fixed 1550, ruang_lingkup_added 1338).

## Lane B headline (website, apps/mouth)

- Page h1 is an English title from kbli-english.ts / kbli-english-generated.ts for 1559/1559 codes; the subtitle is toTitleCase(judul), altered for 209 codes; the uraian lead is verbatim except on 50 certified editorial pages. JSON-LD description truncates uraian on 1366 codes.
- kbli-perpres-slice-disclosures.json: 12 codes, 0 missing from corpus, 0 missing from OSS. Other app-side tables carry phantom keys (English map: 82920, 85598; gold file: 8 codes) — see PHANTOM_CODE rows.
- _regulatory-claim-ledger.json (15 claims): 0 consumers under apps/mouth — no KBLI page reads the ledger.
- kbli-dataset-version.json: datasetSha256 matches the loaded corpus; it carries no version/total_codes field to compare with metadata.version; lastModified 2026-08-15 has no counterpart in corpus metadata.
- ruang_lingkup, sektor_id and kewenangan are never rendered; authority cell is a literal.

## Lane C headline (navigator app)

- h1 = ENGLISH_TITLES[code] ?? toTitleCase(judul): differs from judul for 529/1559; subtitle altered for 209; uraian lead replaced by editorial on 49 certified pages; metadata truncation 1395, JSON-LD truncation 1241.
- ruang_lingkup is not typed, loaded or rendered (1338 codes carry it).
- Kepmenaker 228 mapping: 216 jabatan listed (1678 declared), 395 code references, 234 distinct codes, 0 absent from OSS, 0 absent from corpus; the file is not imported by any TS source in the snapshot.
- Decision logic: every text-keyed rule recomputed with OSS judul_id/uraian_id gives 0/1559 outcome changes (corpus text == OSS text). Verdict/badge logic keyed on pma_*, l4_bali, per_skala has no OSS counterpart (ENRICHMENT): PMA badge unknown for 1505/1559; RiskBadge reads per_skala[0] only while 525 codes carry mixed tiers.

## The one question

**Of 1559 codes, how many have corpus, website and app all aligned word-for-word with OSS?**

- Corpus alone: **1559/1559** (judul, uraian and ruang_lingkup byte-identical to OSS).
- Strict (every rendered title and description on the code page verbatim, English h1 included): **0/1559** — the website h1 is an English string for all 1559 codes, and OSS has no translated judul to align it to.
- Indonesian text only (subtitle judul + lead uraian verbatim on both surfaces; the English h1 counted as ENRICHMENT): **1310/1559** — the 249 excluded codes are the union of 209 toTitleCase alterations and 50 certified editorial pages whose lead replaces the uraian (website 50, app 49, overlap 49); 10 codes fall in both sets.

One-line answer: **1559/1559 in the corpus; 1310/1559 end-to-end on Indonesian judul + uraian; 0/1559 if the English h1 must also equal OSS.**

Excluded-code list: `science-out/data/chain_alignment.json` → `full_chain_idtext_codes_excluded`.

## Next step

Each CSV row is to be verified on disk and on the machines by a separate session and marked CONFIRMED / REFUTED / NEEDS-RUNTIME; rows with runtime_dependent=true are NEEDS-RUNTIME by construction.