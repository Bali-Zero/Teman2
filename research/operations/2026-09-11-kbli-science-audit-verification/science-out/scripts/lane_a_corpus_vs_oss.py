#!/usr/bin/env python3
"""Lane A: KBLI_2025_FINAL_CLEAN.json (corpus) vs KBLI_2025_OSS_GROUND_TRUTH.json (OSS).

Usage: python3 lane_a_corpus_vs_oss.py <snapshot_root>
Writes:
  science-out/kbli_corpus_vs_oss.csv        (fixed 9-column schema)
  science-out/data/lane_a_per_code.json     (per-code classification matrix)
  science-out/data/lane_a_stats.json        (all aggregate numbers used in SUMMARY/MANIFEST)

Definitions (see RUN_MANIFEST.md):
  norm(s)  = NFKC -> casefold -> strip punctuation (unicode category P*) -> collapse whitespace -> strip
  EXACT      : corpus raw == OSS raw
  NORMALIZED : norm(corpus) == norm(OSS) and not EXACT
  TRUNCATED  : norm(OSS).startswith(norm(corpus)) and len(norm(corpus)) < len(norm(OSS))
  DIVERGENT  : everything else
  sim        = difflib.SequenceMatcher(None, norm(a), norm(b)).ratio()   (character-level, 0..1)
  jaccard    = |tokens(norm a) & tokens(norm b)| / |tokens(norm a) | tokens(norm b)|  (June-19 method)
  June-19 "fedele" uraian threshold: jaccard >= 0.80 (as stated in the June 19 note)
"""
import csv, difflib, hashlib, json, os, re, sys, unicodedata
from collections import Counter, OrderedDict

ROOT = sys.argv[1] if len(sys.argv) > 1 else "."
OSS_PATH = f"{ROOT}/data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
CORP_PATH = f"{ROOT}/data/source_documents/KBLI_2025_FINAL_CLEAN.json"
OUT_DIR = f"{ROOT}/science-out"
REL_OSS = "data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
REL_CORP = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"

def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def norm(s):
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", str(s)).casefold()
    s = "".join(ch for ch in s if not unicodedata.category(ch).startswith("P"))
    return re.sub(r"\s+", " ", s).strip()

def classify(ours, oss):
    if ours is None or ours == "":
        return "MISSING_FIELD"
    if ours == oss:
        return "EXACT"
    a, b = norm(ours), norm(oss)
    if a == b:
        return "NORMALIZED"
    if b.startswith(a) and len(a) < len(b):
        return "TRUNCATED"
    return "DIVERGENT"

def sim(a, b):
    return round(difflib.SequenceMatcher(None, norm(a), norm(b)).ratio(), 4)

def jaccard(a, b):
    ta, tb = set(norm(a).split()), set(norm(b).split())
    if not ta and not tb:
        return 1.0
    return round(len(ta & tb) / len(ta | tb), 4)

def line_index(path, pattern):
    """Return {captured_code: line_no} for the first regex match per line."""
    idx = {}
    rx = re.compile(pattern)
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            m = rx.search(line)
            if m and m.group(1) not in idx:
                idx[m.group(1)] = n
    return idx

oss = json.load(open(OSS_PATH, encoding="utf-8"))
corp = json.load(open(CORP_PATH, encoding="utf-8"))
oss5 = {r["kode"]: r for r in oss["data"] if r.get("digits") == 5}
corp_by = {r["kode_kbli_2025"]: r for r in corp["data"]}
assert len(oss5) == 1559, len(oss5)
assert len(corp_by) == len(corp["data"]) == 1559, (len(corp_by), len(corp["data"]))

oss_lines = line_index(OSS_PATH, r'^\s*"kode":\s*"(\d{5})"')
corp_lines = line_index(CORP_PATH, r'^\s*"kode_kbli_2025":\s*"(\d{5})"')

# ---------------------------------------------------------------- per-code matrix
FIELDS = [  # (label, corpus key, oss key)
    ("judul_id", "judul", "judul_id"),
    ("uraian_id", "uraian", "uraian_id"),
    ("judul_en", None, "judul_en"),     # corpus has no EN field
    ("uraian_en", None, "uraian_en"),
]
matrix = OrderedDict()
for kode in sorted(oss5):
    o = oss5[kode]
    c = corp_by.get(kode)
    row = {"in_corpus": c is not None, "oss_line": oss_lines.get(kode), "corp_line": corp_lines.get(kode)}
    for label, ck, ok in FIELDS:
        if c is None:
            row[label] = {"class": "CODE_MISSING_IN_CORPUS", "sim": None, "jaccard": None}
            continue
        if ck is None:
            row[label] = {"class": "NO_CORPUS_FIELD", "sim": None, "jaccard": None,
                          "oss_en_equals_id": o[ok] == o[ok.replace("_en", "_id")]}
            continue
        row[label] = {"class": classify(c.get(ck), o[ok]), "sim": sim(c.get(ck), o[ok]),
                      "jaccard": jaccard(c.get(ck), o[ok]),
                      "len_ours": len(c.get(ck) or ""), "len_oss": len(o[ok] or "")}
    # ruang_lingkup
    if c is not None:
        o_rl = o.get("ruang_lingkup") or []
        c_rl = c.get("ruang_lingkup") or []
        o_ids = [x.get("id") for x in o_rl]
        c_ids = [x.get("id") for x in c_rl]
        o_txt = [x.get("uraian_id") for x in o_rl]
        c_txt = [x.get("uraian") for x in c_rl]
        if not o_rl and not c_rl:
            rl_class = "BOTH_EMPTY"
        elif o_rl and not c_rl:
            rl_class = "MISSING_IN_CORPUS"
        elif c_rl and not o_rl:
            rl_class = "EXTRA_IN_CORPUS"
        elif o_ids == c_ids and o_txt == c_txt:
            rl_class = "EXACT"
        elif set(o_ids) == set(c_ids) and sorted(map(norm, o_txt)) == sorted(map(norm, c_txt)):
            rl_class = "NORMALIZED_OR_REORDERED"
        else:
            rl_class = "DIVERGENT"
        row["ruang_lingkup"] = {"class": rl_class, "n_oss": len(o_rl), "n_corpus": len(c_rl),
                                "oss_rl_status": o.get("_rl_status"), "corpus_l2_status": c.get("_l2_status")}
        # OSS deskripsi_* fields non-null anywhere?
        row["ruang_lingkup"]["oss_deskripsi_nonnull"] = sum(1 for x in o_rl if x.get("deskripsi_id") or x.get("deskripsi_en"))
    matrix[kode] = row

missing_in_corpus = sorted(k for k in oss5 if k not in corp_by)
phantom_in_corpus = sorted(k for k in corp_by if k not in oss5)

# ---------------------------------------------------------------- aggregates
def dist(label):
    return Counter(matrix[k][label]["class"] for k in matrix)
stats = {
    "sha256": {REL_OSS: sha256(OSS_PATH), REL_CORP: sha256(CORP_PATH)},
    "oss_records": len(oss["data"]), "oss_5digit": len(oss5),
    "corpus_records": len(corp["data"]), "corpus_version": corp["metadata"].get("version"),
    "missing_in_corpus": missing_in_corpus, "phantom_in_corpus": phantom_in_corpus,
    "class_dist": {lab: dict(dist(lab)) for lab, _, _ in FIELDS},
    "rl_dist": dict(Counter(matrix[k]["ruang_lingkup"]["class"] for k in matrix if matrix[k]["in_corpus"])),
    "oss_en_equals_id": {"judul": sum(1 for k in oss5 if oss5[k]["judul_en"] == oss5[k]["judul_id"]),
                         "uraian": sum(1 for k in oss5 if oss5[k]["uraian_en"] == oss5[k]["uraian_id"])},
    "oss_rl_deskripsi_nonnull_total": sum(matrix[k]["ruang_lingkup"]["oss_deskripsi_nonnull"] for k in matrix if matrix[k]["in_corpus"]),
}
shared = [k for k in matrix if matrix[k]["in_corpus"]]
for lab in ("judul_id", "uraian_id"):
    sims = [matrix[k][lab]["sim"] for k in shared]
    jac = [matrix[k][lab]["jaccard"] for k in shared]
    stats[f"{lab}_sim_mean"] = round(sum(sims) / len(sims), 4)
    stats[f"{lab}_jaccard_mean"] = round(sum(jac) / len(jac), 4)
    stats[f"{lab}_jaccard_ge_0.80"] = sum(1 for j in jac if j >= 0.80)
    stats[f"{lab}_jaccard_ge_0.95"] = sum(1 for j in jac if j >= 0.95)
    stats[f"{lab}_jaccard_lt_0.50"] = sum(1 for j in jac if j < 0.50)
    stats[f"{lab}_exact_or_normalized"] = sum(1 for k in shared if matrix[k][lab]["class"] in ("EXACT", "NORMALIZED"))
    stats[f"{lab}_sim_ge_0.80"] = sum(1 for s in sims if s >= 0.80)

# June 19 headline numbers, then vs now
stats["june19"] = {
    "coverage": {"then": "1559/1563 corpus codes real; 0 OSS codes missing; 4 phantom (26120,60111,82920,85598)",
                 "now_corpus_codes": len(corp_by), "now_missing_in_corpus": len(missing_in_corpus),
                 "now_phantom": phantom_in_corpus},
    "judul_faithful": {"then": "1185/1559 (76%) EXACT+NORMALIZED; 337 TRUNCATED; 4 wrong",
                       "now_exact_or_normalized": stats["judul_id_exact_or_normalized"],
                       "now_truncated": stats["class_dist"]["judul_id"].get("TRUNCATED", 0),
                       "now_divergent": stats["class_dist"]["judul_id"].get("DIVERGENT", 0)},
    "uraian_faithful": {"then": "1408/1559 (90.3%) jaccard>=0.80; mean 0.937; 14 below 0.50",
                        "now_jaccard_ge_0.80": stats["uraian_id_jaccard_ge_0.80"],
                        "now_jaccard_mean": stats["uraian_id_jaccard_mean"],
                        "now_jaccard_lt_0.50": stats["uraian_id_jaccard_lt_0.50"]},
}
# The 4 forestry judul flagged on June 19
stats["june19_forestry_now"] = {k: matrix[k]["judul_id"]["class"] for k in ("02102", "02103", "02401", "02402") if k in matrix}

# Corpus fields with no OSS counterpart (ENRICHMENT)
OSS_TOP = {"uuid", "kode", "digits", "judul_id", "uraian_id", "judul_en", "uraian_en", "id_kategori", "id_version", "ruang_lingkup", "_rl_status"}
corp_field_count = Counter(k for r in corp["data"] for k in r)
counterpart = {"kode_kbli_2025": "kode", "judul": "judul_id", "uraian": "uraian_id", "ruang_lingkup": "ruang_lingkup", "_l2_status": "_rl_status (partial)"}
enrichment = {k: n for k, n in corp_field_count.items() if k not in counterpart}
stats["corpus_field_counts"] = dict(corp_field_count)
stats["enrichment_fields"] = enrichment
stats["oss_fields_without_corpus_counterpart"] = sorted(OSS_TOP - set(counterpart.values()) - {"_rl_status (partial)"} | {"_rl_status"})
# ruang_lingkup sub-fields: OSS has id, uraian_id, deskripsi_id, uraian_en, deskripsi_en ; corpus has id, uraian
rl_sub_corp = Counter(k for r in corp["data"] for x in (r.get("ruang_lingkup") or []) for k in x)
rl_sub_oss = Counter(k for r in oss5.values() for x in (r.get("ruang_lingkup") or []) for k in x)
stats["rl_subfields"] = {"corpus": dict(rl_sub_corp), "oss": dict(rl_sub_oss)}

# full alignment per code (Lane A only): judul_id and uraian_id EXACT, ruang_lingkup EXACT or BOTH_EMPTY
stats["laneA_fully_aligned_exact"] = sorted(k for k in shared if matrix[k]["judul_id"]["class"] == "EXACT"
                                            and matrix[k]["uraian_id"]["class"] == "EXACT"
                                            and matrix[k]["ruang_lingkup"]["class"] in ("EXACT", "BOTH_EMPTY"))
stats["laneA_fully_aligned_exact_count"] = len(stats["laneA_fully_aligned_exact"])
stats["laneA_aligned_exact_or_normalized_count"] = sum(1 for k in shared if matrix[k]["judul_id"]["class"] in ("EXACT", "NORMALIZED")
                                                       and matrix[k]["uraian_id"]["class"] in ("EXACT", "NORMALIZED")
                                                       and matrix[k]["ruang_lingkup"]["class"] in ("EXACT", "NORMALIZED_OR_REORDERED", "BOTH_EMPTY"))

# ---------------------------------------------------------------- findings CSV
COLS = ["finding_id", "family", "code", "file", "line", "claim", "confidence", "runtime_dependent", "suggested_fix"]
rows = []
seq = Counter()
def add(family, code, file, line, claim, conf, fix, abbrev=None):
    ab = abbrev or family[:6]
    seq[ab] += 1
    assert len(claim) <= 200, claim
    rows.append({"finding_id": f"A-{ab}-{seq[ab]:04d}", "family": family, "code": code, "file": file,
                 "line": line if line is not None else "", "claim": claim, "confidence": conf,
                 "runtime_dependent": "false", "suggested_fix": fix})

# structural
add("COVERAGE", "", REL_CORP, 2, f"Corpus has {len(corp_by)} codes; OSS 5-digit has {len(oss5)}; missing_in_corpus={len(missing_in_corpus)}; phantom_in_corpus={len(phantom_in_corpus)}", 1.0,
    "None if both zero; otherwise add/remove listed codes", "COV")
for k in missing_in_corpus:
    add("CODE_MISSING_IN_CORPUS", k, REL_OSS, oss_lines.get(k), "OSS 5-digit code absent from corpus", 1.0, "Add record from OSS", "MISS")
for k in phantom_in_corpus:
    add("CODE_PHANTOM_IN_CORPUS", k, REL_CORP, corp_lines.get(k), "Corpus code absent from OSS 2025 5-digit set", 1.0, "Remove or mark deprecated-2020", "PHAN")
add("SCHEMA", "", REL_CORP, 2, "Corpus has no judul_en/uraian_en field; OSS judul_en/uraian_en exist but equal judul_id/uraian_id for all 1559 codes", 1.0,
    "Document that OSS EN fields are untranslated copies; do not treat corpus EN absence as data loss", "SCH")
add("SCHEMA", "", REL_CORP, 2, f"ruang_lingkup sub-fields: corpus keeps id+uraian only; OSS has id,uraian_id,deskripsi_id,uraian_en,deskripsi_en; deskripsi non-null in OSS: {stats['oss_rl_deskripsi_nonnull_total']}", 1.0,
    "None if deskripsi are all null in OSS; otherwise add deskripsi_id to corpus", "SCH")
l2_set = {k for k, r in corp_by.items() if "_l2_status" in r}
ns_set = {k for k, r in oss5.items() if r.get("_rl_status") == "no_scope"}
stats["l2_status_equals_no_scope_set"] = (l2_set == ns_set)
add("SCHEMA", "", REL_CORP, 2, f"Corpus _l2_status=no_oss_risk on {len(l2_set)} codes == OSS _rl_status=no_scope set: {l2_set == ns_set}; OSS uuid, id_kategori, id_version have no corpus counterpart", 1.0,
    "Consider carrying OSS uuid for stable joins", "SCH")
for k, n in sorted(enrichment.items(), key=lambda x: -x[1]):
    add("ENRICHMENT", "", REL_CORP, 2, f"Corpus field '{k}' present on {n}/1559 records has no OSS counterpart (enrichment, not error)", 1.0, "None", "ENR")

# per-code text findings (non-EXACT only)
for k in shared:
    r = matrix[k]
    for lab, ck, ok in FIELDS:
        if ck is None:
            continue
        cl = r[lab]["class"]
        if cl == "EXACT":
            continue
        fam = f"{lab.upper()}_{cl}"
        claim = f"corpus {ck} vs OSS {ok}: {cl}; sim={r[lab]['sim']}; jaccard={r[lab]['jaccard']}; len ours/oss={r[lab]['len_ours']}/{r[lab]['len_oss']}; OSS at {REL_OSS}:{r['oss_line']}"
        conf = 1.0 if cl in ("NORMALIZED", "TRUNCATED", "MISSING_FIELD") else (0.95 if r[lab]["sim"] < 0.9 else 0.85)
        fix = {"NORMALIZED": "Copy OSS text verbatim (cosmetic)", "TRUNCATED": "Replace with full OSS text",
               "DIVERGENT": "Review against OSS text and replace", "MISSING_FIELD": "Populate from OSS"}[cl]
        add(fam, k, REL_CORP, r["corp_line"], claim, conf, fix, {"judul_id": "JUD", "uraian_id": "URA"}[lab])
    rl = r["ruang_lingkup"]
    if rl["class"] not in ("EXACT", "BOTH_EMPTY"):
        add(f"RUANG_LINGKUP_{rl['class']}", k, REL_CORP, r["corp_line"],
            f"ruang_lingkup {rl['class']}: n_corpus={rl['n_corpus']} n_oss={rl['n_oss']}; OSS _rl_status={rl['oss_rl_status']}; OSS at {REL_OSS}:{r['oss_line']}",
            1.0, "Regenerate ruang_lingkup list from OSS (id + uraian_id)", "RL")

# per_skala[].scope_uraian is text copied from OSS ruang_lingkup[scope_index].uraian_id: check it
ps_total = ps_mismatch = 0
ps_bad = Counter()
for r in corp["data"]:
    k = r["kode_kbli_2025"]
    rl = oss5[k].get("ruang_lingkup") or []
    for p in r.get("per_skala") or []:
        if p.get("scope_uraian") is not None and p.get("scope_index") is not None:
            ps_total += 1
            i = p["scope_index"]
            if i >= len(rl) or rl[i]["uraian_id"] != p["scope_uraian"]:
                ps_mismatch += 1
                ps_bad[(k, i)] += 1
stats["per_skala_scope_entries"] = ps_total
stats["per_skala_scope_mismatch_entries"] = ps_mismatch
stats["per_skala_scope_mismatch_codes"] = sorted({k for k, _ in ps_bad})
for (k, i), n in sorted(ps_bad.items()):
    o_t = (oss5[k].get("ruang_lingkup") or [None] * (i + 1))[i]
    s = sim(next(p["scope_uraian"] for p in corp_by[k]["per_skala"] if p.get("scope_index") == i), o_t["uraian_id"]) if o_t else 0.0
    add("PER_SKALA_SCOPE_DIVERGENT", k, REL_CORP, corp_lines.get(k),
        f"{n} per_skala entries with scope_index={i}: scope_uraian != OSS ruang_lingkup[{i}].uraian_id; sim={s}; OSS at {REL_OSS}:{oss_lines.get(k)}",
        1.0, "Re-copy scope_uraian from OSS ruang_lingkup[scope_index].uraian_id", "PSK")
add("DERIVATION", "", REL_CORP, 2,
    f"per_skala[].scope_uraian: {ps_total} entries carry scope_index+scope_uraian; {ps_total - ps_mismatch} equal OSS ruang_lingkup[scope_index].uraian_id", 1.0,
    "None", "DER")

os.makedirs(f"{OUT_DIR}/data", exist_ok=True)
with open(f"{OUT_DIR}/kbli_corpus_vs_oss.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS)
    w.writeheader()
    w.writerows(rows)
json.dump(matrix, open(f"{OUT_DIR}/data/lane_a_per_code.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
stats["findings_rows"] = len(rows)
stats["findings_by_family"] = dict(Counter(r["family"] for r in rows))
json.dump(stats, open(f"{OUT_DIR}/data/lane_a_stats.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in stats.items() if k not in ("laneA_fully_aligned_exact", "corpus_field_counts", "enrichment_fields")}, ensure_ascii=False, indent=1))
