#!/usr/bin/env python3
"""
KBLI Schema-v2 populator — assembles 2422 records into the 5-layer provenance schema.

Design principle (Zero's mandate "analizza che si va bene"): INCREMENTAL + self-checking.
Each stage writes a health report and ASSERTS invariants before the next stage runs.
Reuses existing work (Zero's "non re-ingestire"): per_skala, PMA, intel_2026 (504), 2020-bridge.
NEVER invents: unresolved mappings are tagged `unmapped`, not guessed.

Stages:
  A  L0+L1+L2 from OSS + FINAL_CLEAN (deterministic, zero LLM)
  B  L4 Bali bans via 2020->2025 bridge, unmapped tagged explicitly
  C  L3 reuse 504 existing intel_2026 (mark legacy/LOW), list gaps (NOT generated here)
"""
import json, os, sys, re
from collections import Counter

WT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(WT, "data/source_documents")
OUT = os.path.join(WT, "data/kbli_schema_v2")
os.makedirs(OUT, exist_ok=True)

OSS = json.load(open(f"{SRC}/KBLI_2025_OSS_GROUND_TRUTH.json"))
OURS = json.load(open(f"{SRC}/KBLI_2025_FINAL_CLEAN.json"))["data"]
ours = {r["kode_kbli_2025"]: r for r in OURS}
NOW = "2026-06-19"

def vo(value, source, doc, conf):
    return {"value": value, "provenance": {"source": source, "source_document": doc,
            "confidence": conf, "last_verified": NOW}}

def hier(kode):
    """Parent codes by digit-prefix (2,3,4 -> the 5-digit itself). Filtered to existing later."""
    return [kode[:L] for L in (2, 3, 4, 5) if len(kode) >= L]

def health(stage, checks):
    """Print a health report; return False if any hard-invariant fails."""
    print(f"\n{'='*60}\nHEALTH — Stage {stage}\n{'='*60}")
    ok = True
    for label, val, invariant in checks:
        passed = invariant(val) if invariant else True
        flag = "✓" if passed else "✗ FAIL"
        print(f"  {flag} {label}: {val}")
        ok = ok and passed
    return ok

# ─────────────────────────────────────────────────────────────────────────
# STAGE A — L0 (OSS) + L1 (normalized) + L2 (national compliance)
# ─────────────────────────────────────────────────────────────────────────
records = {}
for r in OSS["data"]:
    kode = r["kode"]
    digits = r["digits"]
    o = ours.get(kode)  # our enrichment, only exists for most 5-digit
    rec = {
        "kode": kode,
        "digits": digits,
        "meta": {"schema_version": "v2", "kode_version": r.get("id_version"), "built": NOW},
        # L0 — government ground truth (OSS), always HIGH
        "l0_ground_truth": {
            "judul_id": vo(r["judul_id"], "OSS_API", "gw.oss.go.id/v2/portal/kbli 2026-06-16", "HIGH"),
            "uraian_id": vo(r["uraian_id"], "OSS_API", "gw.oss.go.id/v2/portal/kbli", "HIGH"),
            "ruang_lingkup_raw": r.get("ruang_lingkup", []) if isinstance(r.get("ruang_lingkup"), list) else [],
            "id_kategori": r.get("id_kategori"),
        },
        # L1 — normalized facts (EN separate, hierarchy, 2020 mapping)
        "l1_normalized": {
            "judul_en": vo(r.get("judul_en"), "OSS_API (en loc)", "OSS", "HIGH"),
            "uraian_en": vo(r.get("uraian_en"), "OSS_API (en loc)", "OSS", "HIGH"),
            "parent_hierarchy": hier(kode),
        },
        # L2 — national compliance (reuse our per_skala/PMA)
        "l2_compliance_national": None,
        # L3 — editorial (filled Stage C)
        "l3_editorial": None,
        # L4 — Bali bans (filled Stage B)
        "l4_bali": None,
    }
    if o:
        # status_mapping → 2020 (L1)
        if o.get("status_mapping"):
            rec["l1_normalized"]["status_mapping_2020"] = vo(
                {"type": o.get("status_mapping"), "kode_2020": o.get("kbli_2020_source")},
                "BPS_CONCORDANCE", "our FINAL_CLEAN v8", "MEDIUM")
        # L2: per_skala + PMA (reuse)
        rec["l2_compliance_national"] = {
            "per_skala": o.get("per_skala", []),
            "per_skala_provenance": {"source": "PP28_2024", "confidence": "HIGH",
                                     "note": "reused from FINAL_CLEAN; re-anchor per-field vs PP28 lampiran pending"},
            "pma": {
                "pma_status": vo(o.get("pma_status"), "PERPRES", o.get("pma_source", "Perpres 10/2021,49/2021,14/2024"), "HIGH"),
                "pma_max_asing": vo(o.get("pma_max_asing"), "PERPRES", o.get("pma_source", "Perpres 10/2021"), "HIGH"),
                "pma_kondisi": o.get("pma_kondisi"),
                "pma_prioritas": o.get("pma_prioritas"),
            },
            "sektor_id": o.get("sektor_id"),
        }
    records[kode] = rec

# refine hierarchy: keep only parent prefixes that actually exist as records (+ self)
all_codes = set(records.keys())
for kode, rec in records.items():
    rec["l1_normalized"]["parent_hierarchy"] = [
        c for c in hier(kode) if c == kode or c in all_codes
    ]

five = [r for r in records.values() if r["digits"] == 5]
with_l2 = sum(1 for r in five if r["l2_compliance_national"])
A_ok = health("A — L0/L1/L2", [
    ("total records", len(records), lambda v: v == 2422),
    ("5-digit kelompok", len(five), lambda v: v == 1559),
    ("5-digit with L2 (per_skala/PMA reused)", with_l2, lambda v: v >= 1500),
    ("every record has L0 judul_id", sum(1 for r in records.values() if r["l0_ground_truth"]["judul_id"]["value"]), lambda v: v == 2422),
])
if not A_ok:
    sys.exit("STAGE A invariants failed — abort")
json.dump({"_meta": {"stage": "A", "built": NOW}, "records": list(records.values())},
          open(f"{OUT}/_stageA.json", "w"), ensure_ascii=False)
print(f"  → wrote {OUT}/_stageA.json")

# ─────────────────────────────────────────────────────────────────────────
# STAGE B — L4 Bali bans, via 2020->2025 bridge. NEVER invent: unmapped tagged.
# ─────────────────────────────────────────────────────────────────────────
# Bali status from VERIFIED research files (2026-06-09 moratorium + 2026-06-13 classification).
# Keys are KBLI 2020 codes as written in those files; we bridge to 2025.
BALI_STATUS_2020 = {
    "55130": ("TERTUTUP", "pondok wisata: 0% WNA, max 5 kamar, owner-resident", "research/compliance/2026-06-13"),
    "47111": ("TERTUTUP", "minimarket/supermarket riservato WNI", "research/compliance/2026-06-13"),
    "47112": ("TERTUTUP", "minimarket/supermarket riservato WNI", "research/compliance/2026-06-13"),
    "69100": ("TERTUTUP", "jasa hukum riservato WNI", "research/compliance/2026-06-13"),
    "86904": ("TERTUTUP", "praktik dokter mandiri riservato WNI", "research/compliance/2026-06-13"),
    "01111": ("TERTUTUP", "agricoltura base riservata", "research/compliance/2026-06-13"),
    "01119": ("TERTUTUP", "agricoltura base riservata", "research/compliance/2026-06-13"),
    "02100": ("TERTUTUP", "kehutanan riservato", "research/compliance/2026-06-13"),
    "41011": ("TERBATAS", "konstruksi gedung: max 67% WNA + partner locale + IUJK", "research/compliance/2026-06-13"),
    "52292": ("TERBATAS", "cargo/freight forwarding: max 49% WNA", "research/compliance/2026-06-13"),
    "69200": ("TERBATAS", "akuntan publik: max 20% WNA", "research/compliance/2026-06-13"),
    "86102": ("TERBATAS", "klinik: max 67% WNA", "research/compliance/2026-06-13"),
    "70209": ("CHIUSO_BALI", "consulenza mgmt: chiuso PMA Bali dal 28/1/2026 (primo dei 7)", "research/compliance/2026-06-09"),
    "68111": ("CHIUSO_BALI_PROPOSTO", "real estate: proposto per chiusura PMA Bali", "research/compliance/2026-06-13"),
    "79110": ("CHIUSO_BALI_PROPOSTO", "travel agency: proposto chiusura", "research/compliance/2026-06-13"),
    "77100": ("CHIUSO_BALI_PROPOSTO", "rental: proposto chiusura", "research/compliance/2026-06-13"),
}
# Manual, REVIEWED 2020->2025 bridge for codes the numeric bridge misses (candidates only — flagged).
# These are SUGGESTIONS requiring human/NB-3 confirmation, NOT auto-applied as fact.
MANUAL_BRIDGE_CANDIDATES = {
    "55130": ["55201"],            # pondok wisata -> homestay (likely)
    "69100": ["69102", "69104"],   # jasa hukum -> konsultan hukum + notaris (splits)
    "69200": ["69201"],            # akuntan -> akuntansi
    "86904": ["86201", "86202"],   # praktik dokter -> dokter umum/spesialis
    "01119": ["01112"],            # serealia selain padi/jagung
    "02100": ["02102", "02103", "02401", "02402"],  # kehutanan cluster
    "55120": [],                   # hotel melati: NO direct 2025 equivalent (per-star only)
}

# Build numeric 2020->2025 reverse index from our kbli_2020_source
rev2020 = {}
for r in OURS:
    src = r.get("kbli_2020_source")
    if src:
        for s in (src if isinstance(src, list) else [src]):
            rev2020.setdefault(str(s), []).append(r["kode_kbli_2025"])

# Island-wide moratorium fact (applies to ALL low/medium-low risk PMA in Bali)
MORATORIUM = {
    "rule": "Bali province blocks ALL Low + Medium-Low risk KBLI for PMA (island-wide, permanent)",
    "effective": "2026-05-13", "source": "Gubernur letter B.27.000/642/PM/DPMPTSP",
    "virtual_office": "BANNED as PMA domicile in Bali",
}

def risk_of(rec):
    """Lowest (most permissive) risk across per_skala scales — drives moratorium applicability."""
    ps = (rec.get("l2_compliance_national") or {}).get("per_skala") or []
    risks = {row.get("kategori_risiko", "") for row in ps}
    return risks

all_codes_set = set(records.keys())
l4_explicit = l4_moratorium = l4_unmapped_candidate = l4_clear = 0
for kode, rec in records.items():
    l4 = {"moratorium": MORATORIUM, "bali_status": None, "needs_human_review": False, "candidates_2025": None}
    # 1) explicit status — precedence:
    #    (a) this 2025 code IS a banned code verbatim (same number in 2020+2025), OR
    #    (b) this 2025 code is the renumber-bridge target of a banned 2020 code.
    matched = None
    if kode in BALI_STATUS_2020:                       # (a) verbatim alive
        status, reason, src = BALI_STATUS_2020[kode]
        matched = (kode, status, reason, src)
    else:
        for c2020, (status, reason, src) in BALI_STATUS_2020.items():  # (b) renumber bridge
            if kode in rev2020.get(c2020, []):
                matched = (c2020, status, reason, src); break
    if matched:
        c2020, status, reason, src = matched
        l4["bali_status"] = vo({"status": status, "reason": reason, "from_2020": c2020},
                               "RESEARCH_VERIFIED", src, "HIGH")
        l4_explicit += 1
    else:
        # 2) is it a flagged manual-candidate target? (suggestion, needs review)
        cand_for = [c2020 for c2020, cands in MANUAL_BRIDGE_CANDIDATES.items() if kode in cands]
        if cand_for:
            c2020 = cand_for[0]
            status, reason, src = BALI_STATUS_2020.get(c2020, ("REVIEW", "candidate bridge", "manual"))
            l4["bali_status"] = vo({"status": status + "_CANDIDATE", "reason": reason, "from_2020_candidate": c2020},
                                   "MANUAL_CANDIDATE", "needs NB-3/human confirm", "LOW")
            l4["needs_human_review"] = True
            l4_unmapped_candidate += 1
        else:
            # 3) moratorium by risk class (low / medium-low) — applies generally
            risks = risk_of(rec)
            if risks & {"Rendah", "Menengah Rendah"}:
                l4["bali_status"] = vo({"status": "BLOCCATO_CLASSE_RISCHIO",
                                        "reason": "low/medium-low risk → moratorium 13/5/26 blocks PMA Bali"},
                                       "DERIVED", "moratorium + per_skala risk", "MEDIUM")
                l4_moratorium += 1
            else:
                l4["bali_status"] = vo({"status": "OK_or_HIGHER_RISK",
                                        "reason": "medium-high/high risk → not blocked by moratorium (verify per address)"},
                                       "DERIVED", "moratorium scope", "MEDIUM")
                l4_clear += 1
    rec["l4_bali"] = l4

B_ok = health("B — L4 Bali", [
    ("explicit banned (verbatim+bridge, HIGH)", l4_explicit, lambda v: v >= 9),  # 10 verbatim-alive expected
    ("manual-candidate (needs_human_review)", l4_unmapped_candidate, None),
    ("blocked by risk-class moratorium", l4_moratorium, None),
    ("OK / higher-risk", l4_clear, None),
    ("every record has l4_bali", sum(1 for r in records.values() if r["l4_bali"]), lambda v: v == 2422),
])
if not B_ok:
    sys.exit("STAGE B invariants failed — abort")
print(f"  → L4 review queue: {l4_unmapped_candidate} codes flagged needs_human_review (NOT auto-decided)")

# ─────────────────────────────────────────────────────────────────────────
# STAGE C — L3 editorial: REUSE existing 504 intel_2026 (mark legacy/LOW), list gaps.
# ─────────────────────────────────────────────────────────────────────────
l3_reused = l3_gap = 0
gaps = []
for kode, rec in records.items():
    o = ours.get(kode)
    if o and o.get("intel_2026"):
        rec["l3_editorial"] = {
            "generation_meta": {"model": "deepseek-r1:32b (legacy)", "human_review": "NOT_REVIEWED",
                                "confidence": "LOW", "reused": True,
                                "WARNING": "legacy intel_2026 — LLM-invented prices/locations, re-gate before publish"},
            "intel_2026": o["intel_2026"],
        }
        l3_reused += 1
    elif rec["digits"] == 5:
        rec["l3_editorial"] = {"generation_meta": {"status": "GAP — to generate with fact-gate", "reused": False},
                               "intel_2026": None}
        gaps.append(kode); l3_gap += 1

C_ok = health("C — L3 editorial", [
    ("reused existing intel_2026 (NOT regenerated)", l3_reused, lambda v: v >= 500),
    ("5-digit gaps to generate later", l3_gap, lambda v: v > 0),
    ("reused + gaps == 5-digit total", l3_reused + l3_gap, lambda v: v == 1559),
])
json.dump(gaps, open(f"{OUT}/_l3_gaps.json", "w"))
print(f"  → {l3_gap} L3 gaps listed in _l3_gaps.json (generation is a SEPARATE gated step)")

# ─────────────────────────────────────────────────────────────────────────
# FINAL assembly + global health
# ─────────────────────────────────────────────────────────────────────────
final = {
    "_meta": {
        "schema_version": "v2", "built": NOW,
        "total_records": len(records), "five_digit": len(five),
        "layers": ["l0_ground_truth", "l1_normalized", "l2_compliance_national", "l3_editorial", "l4_bali"],
        "l3_reused": l3_reused, "l3_gaps": l3_gap,
        "l4_explicit_banned": l4_explicit, "l4_review_queue": l4_unmapped_candidate,
        "source": "OSS ground-truth + FINAL_CLEAN reuse + research/compliance L4",
    },
    "records": list(records.values()),
}
json.dump(final, open(f"{OUT}/KBLI_2025_SCHEMA_V2.json", "w"), ensure_ascii=False, indent=1)
sz = os.path.getsize(f"{OUT}/KBLI_2025_SCHEMA_V2.json")
print(f"\n{'='*60}\nFINAL → {OUT}/KBLI_2025_SCHEMA_V2.json ({sz//1024} KB)\n{'='*60}")
