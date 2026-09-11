---
date: 2026-09-11
domain: compliance
client_case: none
adversarial_review: exempt-claude-science-deliverable-verified-row-by-row-in-parent-README
---

# Lane B — website (apps/mouth) vs corpus — METHOD

Snapshot SHA: 64df83d10b (SNAPSHOT_SHA.txt). All paths relative to the snapshot root.
Script: `science-out/scripts/lane_b_trace.py` (writes this file, the CSV, `science-out/data/lane_b_render_map.json`,
`science-out/data/lane_b_numbers.json`). Command: `python3 science-out/scripts/lane_b_trace.py`.
Line numbers in the CSV are resolved at run time by anchor-substring search; the script aborts if an anchor is missing.

## Files read
- Source of truth: `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` (5-digit codes: 1559).
- Corpus: `data/source_documents/KBLI_2025_FINAL_CLEAN.json` (1559 records, sha256 3dafab17f6c48477...). Byte-identical copies:
  `apps/mouth/data/KBLI_2025_FINAL_CLEAN.json` (True), `apps/kbli-navigator/data/kbli-2025.json` (True). Corpus code set == OSS 5-digit set: True.
- Site data: `apps/mouth/data/kbli-dataset-version.json`, `apps/mouth/data/kbli-perpres-slice-disclosures.json`, `apps/mouth/data/kbli-gold-all.json`, `apps/mouth/data/kbli-risk-disputes.json`, `apps/mouth/data/perpres-locators.json`, `apps/mouth/src/content/_regulatory-claim-ledger.json`, `data/kbli-filiera/pma-editorial-certifications.json`.
- Site code: `apps/mouth/src/app/kbli/**`, `apps/mouth/src/app/kbli-explorer/**`, `apps/mouth/src/components/kbli/*.tsx`,
  `apps/mouth/src/lib/kbli-*.ts`, `apps/mouth/src/lib/api/kbli.api.ts`, `apps/mouth/src/lib/types/kbli.ts`.
  Test files were read as evidence of intent only and are not cited in the CSV.

## Families (controlled set)
FIELD_TRACE (positive trace rendered field -> corpus field, confidence 1.0), HEURISTIC (rule/regex/fallback/string transform),
HARDCODED (literal text or code lists in source), OTHER_FILE (rendered from a non-corpus JSON/TS artifact), PHANTOM_CODE,
CLAIM_LEDGER, VERSION_MISMATCH, SCHEMA_DIVERGENCE (type/loader vs data shape), RUNTIME (depends on env/fetch/build cwd; runtime_dependent=true).

## Ports and definitions
- `toTitleCase` ported literally from kbli-data.ts (lower-case, split on whitespace, capitalise first char except a fixed
  Indonesian stopword list). titleId differs from judul when the ported output != corpus judul: 209 codes.
- English maps parsed by regex `"NNNNN": "..."` from kbli-english.ts (376 entries) and
  kbli-english-generated.ts (1186 entries). Precedence curated > generated > titleId (kbli-data.ts).
- Section = SECTION_PREFIX_MAP[code[:2]] (kbli-section.ts); null for 0 codes.
- PMA verdict "located" = pma_verification_status == located AND pma_status in TERBUKA/TERBATAS/TERTUTUP AND non-empty
  pma_official_basis AND pma_source_vintage (kbli-provenance.ts pmaProvenance). Located: 54; declared_gap: 1505.
- Publishable cap = located AND pma_cap_verified true AND (numeric pma_max_asing OR special+pma_cap_special): 54 codes.
- Certification (kbli-editorial-certification.ts): sha256 of key-sorted compact JSON (ensure_ascii=False) of the content, plus a
  fingerprint over 12 PMA fields; matched against `data/kbli-filiera/pma-editorial-certifications.json`. Certified intel: 49 (registry 49),
  certified gold: 15 (registry 15). Registry sourceDatasetSha256 == corpus sha: True.
  Caveat: Python json.dumps vs JS JSON.stringify can differ on float formatting; no floats occur in the hashed content, and the
  match counts equal the registry sizes, which supports the port.
- Page body branch per code (app/kbli/[code]/page.tsx): gold layout if certified gold; else intel layout if certified intel with
  whatItMeans; else the uraian paragraph. Counts: {"uraian": 1509, "intel": 35, "gold": 15}.
- JSON-LD truncation: uraian longer than 160 UTF-16 code units (JS slice semantics): 1366 (codepoints: 1366).
- Licence derivation: `resolveLicenseType` ported; rows with empty/unusable perizinan fall to `licenseForRisk`: 9078 of 9095 rows;
  first-row derived for 1336 codes. Codes without per_skala: 217.
- Risk badge uses per_skala[0]; codes with >1 distinct kategori_risiko: 525; row 0 below the max tier: 499.
- `formatTimeframe` rewrites: 8622 rows. `isSourceTruncated` regex flags kewajiban 877/48804, persyaratan 360/37437.
- Ledger usage = any file under apps/mouth (ts/tsx/js/mjs/json/md/py, excluding node_modules and the ledger itself) containing the
  ledger file name or a claim id. Consumers found: 0; ids referenced: 0.
- Phantom = code string not in the corpus set (and separately not in the OSS 5-digit set).

## Key numbers
- Slice disclosures: 12 codes (10761,13133,20232,26513,30111,30113,30301,30302,58130,60102,60202,90200); not in corpus []; not in OSS [];
  _meta.count 12; excluded_adjacent codes ['20235', '30303', '51103', '60103', '60203'] (not in corpus []).
- English-map phantoms: curated ['82920', '85598'], generated []. Gold phantoms: ['64921', '85300', '85491', '85499', '85600', '86903', '96120', '96130'].
  metadata.phantoms_dropped ['26120', '60111', '82920', '85598'] still in English maps: ['82920', '85598']; in gold: [].
- Hardcoded national-closure codes: ['01287', '47111', '47112', '59131', '69102', '69104', '86201', '86202']; concordance codes: ['63122', '56101', '55113', '70209', '62019', '68111', '55209'], targets ['55106', '55203'].
- Dataset sidecar: fields ['datasetSha256', 'lastModified', 'note']; sha matches corpus: True; lastModified 2026-08-15;
  corpus metadata.version v10.0-L2-oss-risk, total_codes 1559 (== records: True); corpus has lastModified: False.
- Raw field presence (of 1559): {"pma_official_basis": 56, "pma_source_vintage": 54, "pma_cap_verified": 57, "pma_cap_special": 15, "pma_route_to": 21, "_l2_source": 1338, "_l2_status": 221, "_data_note": 123, "aggregation_note": 198, "mapping_note": 352, "kbli_2020_source": 314, "per_skala_disputed_pp28_collision": 118, "per_skala_disputed_pp28_mice": 1, "status_mapping": 1558, "pp28_sources": 1558, "pma_max_asing": 1558}.
- Findings: 170 rows; runtime_dependent=true: 11.

| family | rows |
|---|---|
| CLAIM_LEDGER | 18 |
| FIELD_TRACE | 31 |
| HARDCODED | 30 |
| HEURISTIC | 26 |
| OTHER_FILE | 8 |
| PHANTOM_CODE | 34 |
| RUNTIME | 10 |
| SCHEMA_DIVERGENCE | 8 |
| VERSION_MISMATCH | 5 |

- `affected_codes` in lane_b_render_map.json: for judul/uraian entries, the codes whose rendered text differs from the corpus field;
  for other entries, codes where the rendered value is not a verbatim corpus value, or null when not statically computable.
- Gold-only mount: LicensingSection renders inside the gold branch of the page, so per_skala persyaratan/kewajiban, slice and
  dispute notices reach only 15 pages (41020,47111,47221,50113,50131,50132,50133,50213,51101,51102,53200,65121,79122,96210,96220); slice codes on gold pages: [];
  dispute codes on gold pages: ['50133', '53200'].

## Exclusions
- Explorer (`/kbli-explorer`) and landing search render remote API data; only RUNTIME rows, no field traces.
- Test files, `apps/mouth/scripts`, Swift/Navigator apps: out of Lane B scope.
- No claim is made about deployed pages, env values, the OG route, or the API; those rows carry runtime_dependent=true.
- Regulatory correctness of any literal is not assessed; such rows are labelled TO VERIFY.
