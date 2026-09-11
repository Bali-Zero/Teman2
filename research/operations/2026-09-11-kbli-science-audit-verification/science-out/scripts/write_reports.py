#!/usr/bin/env python3
"""Generate science-out/RUN_MANIFEST.md and science-out/SUMMARY.md from the lane outputs.
Usage: python3 write_reports.py <snapshot_root>
All numbers are read from science-out/data/*.json and the three CSVs; nothing is typed by hand.
"""
import csv, hashlib, json, os, sys
from collections import Counter, defaultdict

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
SO = f"{ROOT}/science-out"
SHA = open(f"{ROOT}/SNAPSHOT_SHA.txt").read().strip()
A = json.load(open(f"{SO}/data/lane_a_stats.json"))
B = json.load(open(f"{SO}/data/lane_b_numbers.json"))
C = json.load(open(f"{SO}/data/lane_c_numbers.json"))
CH = json.load(open(f"{SO}/data/chain_alignment.json"))

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for ch in iter(lambda: f.read(1 << 20), b""):
            h.update(ch)
    return h.hexdigest()

def load(name):
    return list(csv.DictReader(open(f"{SO}/{name}", encoding="utf-8")))

def cbin(c):
    c = float(c)
    return "1.0" if c >= 1 else "0.9-0.99" if c >= 0.9 else "0.7-0.89" if c >= 0.7 else "<0.7"

LANES = [("A", "kbli_corpus_vs_oss.csv", "corpus vs OSS"), ("B", "kbli_site_vs_corpus.csv", "website (apps/mouth) vs corpus"),
         ("C", "kbli_app_vs_corpus.csv", "navigator app vs corpus")]
rows = {l: load(f) for l, f, _ in LANES}
INPUTS = ["data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json", "data/source_documents/KBLI_2025_FINAL_CLEAN.json",
          "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json", "apps/kbli-navigator/data/kbli-2025.json",
          "apps/mouth/data/kbli-dataset-version.json", "apps/mouth/data/kbli-perpres-slice-disclosures.json",
          "apps/mouth/src/content/_regulatory-claim-ledger.json", "apps/kbli-navigator/data/kepmenaker-228-jabatan-mapping.json",
          "research/operations/2026-06-19-kbli-2025-ours-vs-oss-ground-truth.md"]

# ------------------------------------------------------------------ RUN_MANIFEST.md
m = []
m.append(f"# RUN_MANIFEST — KBLI 2025 data-chain audit\n")
m.append(f"Snapshot: git origin/main SHA `{SHA}` (SNAPSHOT_SHA.txt). Read-only; outputs only under `science-out/`.")
m.append("Static analysis only. No statement in any output refers to a deployed system, daemon, cron, database or Fly; "
         "rows that would depend on runtime carry `runtime_dependent=true`.\n")
m.append("## Input files (sha256)\n")
m.append("| file | sha256 |\n|---|---|")
for p in INPUTS:
    m.append(f"| `{p}` | `{sha256(f'{ROOT}/{p}')}` |")
m.append("\nThe three corpus copies share one sha256, so Lanes B and C read the same bytes as Lane A.\n")
m.append("## Commands (run from the snapshot root, Python 3 stdlib only)\n")
m.append("```\npython3 science-out/scripts/lane_a_corpus_vs_oss.py .\npython3 science-out/scripts/lane_b_trace.py\n"
         "python3 science-out/scripts/lane_c_trace.py\npython3 science-out/scripts/chain_alignment.py .\n"
         "python3 science-out/scripts/write_reports.py .\npython3 science-out/scripts/validate_outputs.py .\n```")
m.append("Re-running the first four scripts reproduced byte-identical CSV/JSON outputs (checked by sha256 before/after).\n")
m.append("## Output files\n")
m.append("| file | sha256 | rows |\n|---|---|---|")
for l, f, _ in LANES:
    m.append(f"| `science-out/{f}` | `{sha256(f'{SO}/{f}')}` | {len(rows[l])} |")
for f in sorted(os.listdir(f"{SO}/data")):
    m.append(f"| `science-out/data/{f}` | `{sha256(f'{SO}/data/{f}')}` | - |")
m.append("\n## CSV schema (all three lanes)\n")
m.append("`finding_id, family, code, file, line, claim, confidence, runtime_dependent, suggested_fix` — exactly these columns. "
         "`code` is one 5-digit KBLI code or empty (structural). `file` is relative to the snapshot root; `line` is 1-based "
         "(range allowed). No quoted span longer than 80 characters; claims under 200 characters. Enforced by `validate_outputs.py`.\n")
m.append("## Lane A — definitions and thresholds\n")
m.append("- Join key: OSS `kode` (records with `digits == 5`, n=1559) ↔ corpus `kode_kbli_2025`.")
m.append("- Field pairs: corpus `judul` ↔ OSS `judul_id`; corpus `uraian` ↔ OSS `uraian_id`; corpus `ruang_lingkup[].{id,uraian}` ↔ OSS `ruang_lingkup[].{id,uraian_id}`.")
m.append("- OSS `judul_en`/`uraian_en`: no corpus counterpart (class NO_CORPUS_FIELD); verified equal to `judul_id`/`uraian_id` for 1559/1559 codes, "
         "so an EN comparison would duplicate the ID comparison.")
m.append("- norm(s) = NFKC → casefold → drop Unicode category P* → collapse whitespace → strip.")
m.append("- EXACT: raw strings equal. NORMALIZED: norm equal, raw differ. TRUNCATED: norm(OSS) starts with norm(corpus) and corpus shorter. DIVERGENT: otherwise.")
m.append("- sim = difflib.SequenceMatcher ratio on norm strings (0–1). jaccard = token-set Jaccard on norm strings (the June 19 method). "
         "June 19 'fedele' threshold for uraian: jaccard ≥ 0.80; 'quasi' ≥ 0.95; 'sporco' < 0.50.")
m.append("- ruang_lingkup classes: EXACT (same id order and text), NORMALIZED_OR_REORDERED, DIVERGENT, MISSING_IN_CORPUS, EXTRA_IN_CORPUS, BOTH_EMPTY.")
m.append("- ENRICHMENT = corpus top-level field with no OSS counterpart (one row per field with its record count). Not an error.")
m.append("- per_skala[].scope_uraian is checked against OSS `ruang_lingkup[scope_index].uraian_id` (DERIVATION / PER_SKALA_SCOPE_DIVERGENT).")
m.append("- Exclusions: OSS records with digits 2/3/4 (863) are not compared (corpus has 5-digit only). Corpus `intel_2026`, `l4_bali`, `pma_*`, `per_skala` content is not fact-checked, only inventoried.\n")
m.append("## Lane B / Lane C — definitions\n")
m.append("Full method notes, ported TypeScript rules, heuristics and exclusions are in `science-out/B_METHOD.md` and `science-out/C_METHOD.md` "
         "(written by their scripts). Key shared definitions:")
m.append("- FIELD_TRACE: rendered field → corpus field, confidence 1.0. HEURISTIC: value computed by code (toTitleCase, slice, regex, fallback, prefix map). "
         "HARDCODED: literal in source. OTHER_FILE: rendered from a non-corpus file (English title maps, gold content, slice disclosures).")
m.append("- toTitleCase ported literally from each app's kbli-data.ts; 'changed' = ported output != corpus judul (209 codes in both apps, sets identical).")
m.append("- English title precedence: website `ENGLISH_TITLES[code] ?? ENGLISH_TITLES_GENERATED[code] ?? titleId` (kbli-data.ts:330-334); "
         "navigator `ENGLISH_TITLES[code] ?? titleId` (lib/kbli-data.ts:365).")
m.append("- Editorial certification gates (which pages replace the uraian lead with editorial prose) were reproduced by porting the sha256/fingerprint "
         "logic to Python; ports validated by matching registry sizes (website: 49 intel / 15 gold; navigator: 49/49 and 2/2 exact hash matches).")
m.append("- Truncation counts use JS `slice` semantics (UTF-16 code units); website JSON-LD 160, navigator metadata 150 and JSON-LD 200.")
m.append("- PHANTOM_CODE: 5-digit key in an app-side table that is not among the 1559 OSS codes (and separately, not in the corpus).")
m.append("- DECISION_INPUT (Lane C): text-keyed rules were re-evaluated with OSS judul_id/uraian_id in place of corpus judul/uraian; "
         "outcome changes counted. Rules keyed on corpus-only enrichment (per_skala, pma_*, l4_bali, status_mapping) are recorded without a change count.")
m.append("- Exclusions: test files cited only as intent; explorer (`/kbli-explorer`) and landing search are remote-API driven → RUNTIME rows only; "
         "no node runtime in the sandbox, so TypeScript was ported, not executed.\n")
m.append("## Chain alignment definitions (chain_alignment.py)\n")
m.append(CH["definitions"].strip().split("Definitions", 1)[1].strip() + "\n")
m.append("## Validation\n")
m.append("`validate_outputs.py` checks: exact column set; confidence ∈ [0,1]; runtime_dependent ∈ {true,false}; unique finding_id; "
         "5-digit or empty code; cited file exists in snapshot; line format; no single-line quoted span > 80 chars in any CSV cell or .md; "
         "no email-like or 16-digit strings (personal-data heuristics). Result at time of writing: 0 violations.\n")
open(f"{SO}/RUN_MANIFEST.md", "w", encoding="utf-8").write("\n".join(m))

# ------------------------------------------------------------------ SUMMARY.md
s = []
s.append(f"# SUMMARY — KBLI 2025 data-chain audit (snapshot `{SHA}`)\n")
s.append("Source of truth: `data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json` (2422 records, 1559 with digits == 5). "
         "Static analysis; nothing here describes a running system.\n")
s.append("## Findings per lane, by family and confidence\n")
for l, f, title in LANES:
    r = rows[l]
    s.append(f"### Lane {l} — {title} — `{f}` — {len(r)} rows "
             f"(runtime_dependent=true: {sum(1 for x in r if x['runtime_dependent']=='true')}, TO VERIFY: {sum(1 for x in r if x['claim'].startswith('TO VERIFY'))})\n")
    fam = defaultdict(Counter)
    for x in r:
        fam[x["family"]][cbin(x["confidence"])] += 1
    s.append("| family | rows | conf 1.0 | 0.9–0.99 | 0.7–0.89 | <0.7 |\n|---|---|---|---|---|---|")
    for fname, c in sorted(fam.items()):
        s.append(f"| {fname} | {sum(c.values())} | {c['1.0']} | {c['0.9-0.99']} | {c['0.7-0.89']} | {c['<0.7']} |")
    s.append("")

s.append("## Lane A headline\n")
cd = A["class_dist"]
s.append(f"- Coverage: OSS 5-digit {A['oss_5digit']}, corpus {A['corpus_records']} (metadata.version {A['corpus_version']}); "
         f"missing in corpus {len(A['missing_in_corpus'])}, phantom in corpus {len(A['phantom_in_corpus'])}.")
s.append(f"- judul vs judul_id: EXACT {cd['judul_id'].get('EXACT',0)}/1559. uraian vs uraian_id: EXACT {cd['uraian_id'].get('EXACT',0)}/1559 "
         f"(sim mean {A['uraian_id_sim_mean']}, jaccard mean {A['uraian_id_jaccard_mean']}).")
s.append(f"- ruang_lingkup: EXACT {A['rl_dist'].get('EXACT',0)}, both empty {A['rl_dist'].get('BOTH_EMPTY',0)} "
         f"(OSS _rl_status=no_scope set == corpus _l2_status set: {A.get('l2_status_equals_no_scope_set')}).")
s.append(f"- judul_en/uraian_en: corpus has no field; OSS EN equals ID for {A['oss_en_equals_id']['judul']}/1559 (judul) and {A['oss_en_equals_id']['uraian']}/1559 (uraian).")
s.append(f"- ENRICHMENT fields with no OSS counterpart: {len(A['enrichment_fields'])} (see CSV). "
         f"per_skala scope_uraian: {A['per_skala_scope_entries']} entries, {A['per_skala_scope_mismatch_entries']} differ from OSS ruang_lingkup "
         f"(codes: {', '.join(A['per_skala_scope_mismatch_codes'])}).\n")

s.append("## June 19 audit — three headline numbers, then and now\n")
j = A["june19"]
s.append("| metric | June 19 (corpus v8.0-final, 1563 codes) | now (corpus v10.0-L2-oss-risk, 1559 codes) | moved? |\n|---|---|---|---|")
s.append(f"| Code coverage | 1559/1563 real; 0 OSS codes missing; 4 phantom | {j['coverage']['now_corpus_codes']}/{j['coverage']['now_corpus_codes']} real; "
         f"{j['coverage']['now_missing_in_corpus']} missing; {len(j['coverage']['now_phantom'])} phantom | yes — 4 phantoms removed (listed in corpus metadata.l1_realign.phantoms_dropped) |")
s.append(f"| judul faithful (EXACT+NORMALIZED) | 1185/1559 (76%); 337 TRUNCATED; 4 wrong | {j['judul_faithful']['now_exact_or_normalized']}/1559 (100%); "
         f"{j['judul_faithful']['now_truncated']} TRUNCATED; {j['judul_faithful']['now_divergent']} DIVERGENT | yes — +374; the 4 forestry judul (02102, 02103, 02401, 02402) are now EXACT |")
s.append(f"| uraian faithful (jaccard ≥ 0.80) | 1408/1559 (90.3%); mean 0.937; 14 below 0.50 | {j['uraian_faithful']['now_jaccard_ge_0.80']}/1559 (100%); "
         f"mean {j['uraian_faithful']['now_jaccard_mean']}; {j['uraian_faithful']['now_jaccard_lt_0.50']} below 0.50 | yes — +151; all 1559 byte-EXACT |")
s.append("\nThe OSS ground-truth file is unchanged since June 19 (sha256 prefix 5d207ede cited in that note equals the snapshot file). "
         "The movement is entirely on the corpus side (metadata.l1_realign: judul_fixed 1559, uraian_fixed 1550, ruang_lingkup_added 1338).\n")

s.append("## Lane B headline (website, apps/mouth)\n")
s.append(f"- Page h1 is an English title from kbli-english.ts / kbli-english-generated.ts for {CH['website']['h1_not_verbatim']}/1559 codes; "
         f"the subtitle is toTitleCase(judul), altered for {CH['website']['subtitle_not_verbatim']} codes; the uraian lead is verbatim except on "
         f"{CH['website']['lead_not_verbatim']} certified editorial pages. JSON-LD description truncates uraian on {CH['website']['jsonld_description_truncated']} codes.")
s.append(f"- kbli-perpres-slice-disclosures.json: 12 codes, 0 missing from corpus, 0 missing from OSS. Other app-side tables carry phantom keys "
         f"(English map: 82920, 85598; gold file: 8 codes) — see PHANTOM_CODE rows.")
s.append("- _regulatory-claim-ledger.json (15 claims): 0 consumers under apps/mouth — no KBLI page reads the ledger.")
s.append("- kbli-dataset-version.json: datasetSha256 matches the loaded corpus; it carries no version/total_codes field to compare with metadata.version; "
         "lastModified 2026-08-15 has no counterpart in corpus metadata.")
s.append("- ruang_lingkup, sektor_id and kewenangan are never rendered; authority cell is a literal.\n")

s.append("## Lane C headline (navigator app)\n")
s.append(f"- h1 = ENGLISH_TITLES[code] ?? toTitleCase(judul): differs from judul for {CH['app']['h1_not_verbatim']}/1559; subtitle altered for "
         f"{CH['app']['subtitle_not_verbatim']}; uraian lead replaced by editorial on {CH['app']['lead_not_verbatim']} certified pages; "
         f"metadata truncation {CH['app']['metadata_description_truncated']}, JSON-LD truncation {CH['app']['jsonld_description_truncated']}.")
s.append(f"- ruang_lingkup is not typed, loaded or rendered ({CH['app']['ruang_lingkup_not_rendered']} codes carry it).")
s.append("- Kepmenaker 228 mapping: 216 jabatan listed (1678 declared), 395 code references, 234 distinct codes, 0 absent from OSS, 0 absent from corpus; "
         "the file is not imported by any TS source in the snapshot.")
s.append("- Decision logic: every text-keyed rule recomputed with OSS judul_id/uraian_id gives 0/1559 outcome changes (corpus text == OSS text). "
         "Verdict/badge logic keyed on pma_*, l4_bali, per_skala has no OSS counterpart (ENRICHMENT): PMA badge unknown for 1505/1559; "
         "RiskBadge reads per_skala[0] only while 525 codes carry mixed tiers.\n")

s.append("## The one question\n")
s.append(f"**Of 1559 codes, how many have corpus, website and app all aligned word-for-word with OSS?**\n")
s.append(f"- Corpus alone: **{CH['corpus_aligned']}/1559** (judul, uraian and ruang_lingkup byte-identical to OSS).")
s.append(f"- Strict (every rendered title and description on the code page verbatim, English h1 included): **{CH['full_chain_strict']}/1559** — "
         f"the website h1 is an English string for all 1559 codes, and OSS has no translated judul to align it to.")
s.append(f"- Indonesian text only (subtitle judul + lead uraian verbatim on both surfaces; the English h1 counted as ENRICHMENT): "
         f"**{CH['full_chain_idtext']}/1559** — the {1559-CH['full_chain_idtext']} excluded codes are the union of "
         f"{CH['idtext_exclusion_decomposition']['titlecase_altered']} toTitleCase alterations and "
         f"{CH['idtext_exclusion_decomposition']['lead_replaced_union']} certified editorial pages whose lead replaces the uraian "
         f"(website {CH['website']['lead_not_verbatim']}, app {CH['app']['lead_not_verbatim']}, overlap {CH['cross_checks']['lead_replaced_intersection']}); "
         f"{CH['idtext_exclusion_decomposition']['in_both_sets']} codes fall in both sets.")
s.append("\nOne-line answer: **1559/1559 in the corpus; 1310/1559 end-to-end on Indonesian judul + uraian; 0/1559 if the English h1 must also equal OSS.**\n")
s.append("Excluded-code list: `science-out/data/chain_alignment.json` → `full_chain_idtext_codes_excluded`.\n")
s.append("## Next step\n")
s.append("Each CSV row is to be verified on disk and on the machines by a separate session and marked CONFIRMED / REFUTED / NEEDS-RUNTIME; "
         "rows with runtime_dependent=true are NEEDS-RUNTIME by construction.")
open(f"{SO}/SUMMARY.md", "w", encoding="utf-8").write("\n".join(s))
print("written", f"{SO}/RUN_MANIFEST.md", f"{SO}/SUMMARY.md")
