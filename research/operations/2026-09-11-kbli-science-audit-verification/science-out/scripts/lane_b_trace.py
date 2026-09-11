#!/usr/bin/env python3
"""Lane B — website (apps/mouth) vs corpus static audit.

Reads ONLY files inside the read-only snapshot and writes:
  science-out/kbli_site_vs_corpus.csv
  science-out/data/lane_b_render_map.json
  science-out/data/lane_b_numbers.json
  science-out/B_METHOD.md

Every count in the CSV / METHOD is computed here. Line numbers are resolved
by searching for anchor substrings in the source files, so they are
reproducible against the snapshot SHA and fail loudly if the code moves.

Usage:  python3 science-out/scripts/lane_b_trace.py  (run from snapshot root
        or anywhere; ROOT is resolved relative to this file)
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "science-out"
DATA_OUT = OUT / "data"
DATA_OUT.mkdir(parents=True, exist_ok=True)

LANE = "B"
FAMILY_ABBREV = OrderedDict(
    [
        ("FIELD_TRACE", "TRACE"),
        ("HEURISTIC", "HEUR"),
        ("HARDCODED", "HARD"),
        ("OTHER_FILE", "OTHER"),
        ("PHANTOM_CODE", "PHAN"),
        ("CLAIM_LEDGER", "LEDG"),
        ("VERSION_MISMATCH", "VERS"),
        ("SCHEMA_DIVERGENCE", "SCHEMA"),
        ("RUNTIME", "RT"),
    ]
)

# ----------------------------------------------------------------------------
# File paths (relative to snapshot root)
# ----------------------------------------------------------------------------
P_OSS = "data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
P_CORPUS = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
P_CORPUS_MOUTH = "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
P_CORPUS_NAV = "apps/kbli-navigator/data/kbli-2025.json"
P_VERSION = "apps/mouth/data/kbli-dataset-version.json"
P_SLICE = "apps/mouth/data/kbli-perpres-slice-disclosures.json"
P_LEDGER = "apps/mouth/src/content/_regulatory-claim-ledger.json"
P_GOLD = "apps/mouth/data/kbli-gold-all.json"
P_DISPUTES = "apps/mouth/data/kbli-risk-disputes.json"
P_LOCATORS = "apps/mouth/data/perpres-locators.json"
P_CERT = "data/kbli-filiera/pma-editorial-certifications.json"

L = "apps/mouth/src/lib/"
C = "apps/mouth/src/components/kbli/"
A = "apps/mouth/src/app/kbli/"
X = "apps/mouth/src/app/kbli-explorer/"
F_DATA = L + "kbli-data.ts"
F_DATA_SRV = L + "kbli-data.server.ts"
F_PAGE = A + "[code]/page.tsx"
F_INDEX = A + "page.tsx"
F_SECTOR = A + "sectors/[id]/page.tsx"
F_EN = L + "kbli-english.ts"
F_EN_GEN = L + "kbli-english-generated.ts"
F_DERIVE = L + "kbli-derive.ts"
F_META = L + "kbli-meta.ts"
F_SECTION = L + "kbli-section.ts"
F_LABELS = L + "kbli-status-labels.ts"
F_PMA = L + "kbli-pma-disclosure.ts"
F_PROV = L + "kbli-provenance.ts"
F_CERT = L + "kbli-editorial-certification.ts"
F_EDIT = L + "kbli-pma-editorial.ts"
F_BLOCK = L + "kbli-bali-block.ts"
F_SLICE = L + "kbli-perpres-slice.ts"
F_LOC = L + "kbli-perpres-locator.ts"
F_DISP = L + "kbli-risk-dispute.ts"
F_TRUNC = L + "kbli-obligation-truncation.ts"
F_FAQ = L + "kbli-faq.ts"
F_TYPES = L + "kbli-types.ts"
F_API = L + "api/kbli.api.ts"
F_LIC = C + "LicensingSection.tsx"
F_JSONLD = C + "KBLIStructuredData.tsx"
F_CARD = C + "KBLICard.tsx"
F_PROVPANEL = C + "KBLIProvenancePanel.tsx"
F_TRANS = C + "KBLITransitionSources.tsx"
F_EDITORIAL = C + "KBLIEditorial.tsx"
F_BALICTX = C + "KBLIBaliContext.tsx"
F_YOULL = C + "KBLIYoullAlsoNeed.tsx"
F_TBADGE = C + "TransitionBadge.tsx"
F_RBADGE = C + "RiskBadge.tsx"
F_PBADGE = C + "PMABadge.tsx"
F_BBADGE = C + "BaliStatusBadge.tsx"
F_PROVBADGE = C + "ProvenanceBadge.tsx"
F_SEARCH = C + "KBLISearch.tsx"
F_CHAT = C + "ZantaraChat.tsx"
F_XPAGE = X + "page.tsx"
F_XINSP = X + "components/KBLIInspector.tsx"
F_XLAYOUT = X + "layout.tsx"
F_CONC = X + "concordance.ts"

_file_cache: dict[str, list[str]] = {}


def lines_of(rel: str) -> list[str]:
    if rel not in _file_cache:
        _file_cache[rel] = (ROOT / rel).read_text(encoding="utf-8").splitlines()
    return _file_cache[rel]


def ln(rel: str, anchor: str, nth: int = 1) -> int:
    """1-based line number of the nth line containing `anchor`."""
    hits = [i + 1 for i, s in enumerate(lines_of(rel)) if anchor in s]
    if len(hits) < nth:
        raise SystemExit(f"anchor not found: {rel!r} :: {anchor!r} (nth={nth})")
    return hits[nth - 1]


def lnr(rel: str, a1: str, a2: str) -> str:
    """Range 'x-y' between two anchors (first occurrence each)."""
    return f"{ln(rel, a1)}-{ln(rel, a2)}"


def sha256(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()


def load(rel: str):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------
# Ports of the TypeScript helpers (kept literal; see B_METHOD.md)
# ----------------------------------------------------------------------------
ID_LOWERCASE_WORDS = {
    "dan", "di", "yang", "untuk", "dari", "ke", "atau", "dengan", "pada", "oleh",
    "dalam", "atas", "sebagai", "serta", "melalui",
}


def to_title_case(text: str) -> str:  # kbli-data.ts toTitleCase
    if not text:
        return text
    words = re.split(r"\s+", text.lower())
    out = []
    for i, w in enumerate(words):
        if i == 0 or w not in ID_LOWERCASE_WORDS:
            out.append(w[:1].upper() + w[1:])
        else:
            out.append(w)
    return " ".join(out)


SECTION_PREFIX_MAP = {
    "A": ["01", "02", "03"], "B": ["05", "06", "07", "08", "09"],
    "C": [f"{i:02d}" for i in range(10, 34)], "D": ["35"],
    "E": ["36", "37", "38", "39"], "F": ["41", "42", "43"], "G": ["45", "46", "47"],
    "H": ["49", "50", "51", "52", "53"], "I": ["55", "56"],
    "J": ["58", "59", "60", "61", "62", "63"], "K": ["64", "65", "66"], "L": ["68"],
    "M": ["69", "70", "71", "72", "73", "74", "75"],
    "N": ["77", "78", "79", "80", "81", "82"], "O": ["84"], "P": ["85"],
    "Q": ["86", "87", "88"], "R": ["90", "91", "92", "93"], "S": ["94", "95", "96"],
    "T": ["97", "98"], "U": ["99"],
}
PREFIX_TO_SECTION = {p: s for s, ps in SECTION_PREFIX_MAP.items() for p in ps}


def section_of(code: str):
    return PREFIX_TO_SECTION.get(code[:2])


def public_text(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


KNOWN_PMA = {"TERBUKA", "TERBATAS", "TERTUTUP"}


def pma_provenance(raw):  # kbli-provenance.ts pmaProvenance
    locator = public_text(raw.get("pma_official_basis"))
    vintage = public_text(raw.get("pma_source_vintage"))
    located = (
        raw.get("pma_verification_status") == "located"
        and raw.get("pma_status") in KNOWN_PMA
        and bool(locator)
        and bool(vintage)
    )
    return {
        "source": raw.get("pma_source") if located and isinstance(raw.get("pma_source"), str) else None,
        "vintage": vintage if located else None,
        "status": "located" if located else "declared_gap",
        "locator": locator if located else None,
    }


def licensing_provenance(raw):  # kbli-provenance.ts deriveProvenance (state + licensing.status)
    disputed = any(k.startswith("per_skala_disputed_") for k in raw.keys())
    no_oss_risk = raw.get("_l2_status") == "no_oss_risk"
    oss_native = raw.get("_l2_source") == "OSS_RBA_resiko_2025"
    unknown_l2 = raw.get("_l2_source") is not None and not oss_native
    state = "not_classifiable" if disputed else ("pending" if no_oss_risk else ("verified" if oss_native else "pending"))
    if state == "not_classifiable":
        status = "detached"
    elif state == "pending":
        status = "unverified_source" if (unknown_l2 or not no_oss_risk) else "pending_crosswalk"
    else:
        status = "oss_native"
    return state, status


def normalized_pma_status(v):
    return {"TERBUKA": "open", "TERBATAS": "restricted", "TERTUTUP": "closed"}.get(v, "unknown")


def public_pma_cap(raw):
    if raw.get("pma_cap_verified") is not True:
        return None
    cap = raw.get("pma_max_asing")
    if is_num(cap):
        return cap
    if cap == "special" and raw.get("pma_cap_special") is True:
        return "special"
    return None


def disclose_pma_info(raw, prov_pma):  # kbli-pma-disclosure.ts disclosePmaInfo (citation excluded from fingerprint)
    if prov_pma["status"] != "located":
        return {
            "status": "unknown", "maxForeign": None, "condition": None, "isPriority": False,
            "note": None, "source": None, "verificationStatus": "declared_gap",
            "officialBasis": None, "sourceVintage": None, "capSpecial": False,
            "capVerified": False, "routeTo": None,
        }
    mf = public_pma_cap(raw)
    return {
        "status": normalized_pma_status(raw.get("pma_status")),
        "maxForeign": mf,
        "condition": public_text(raw.get("pma_kondisi")),
        "isPriority": raw.get("pma_prioritas") is True,
        "note": public_text(raw.get("pma_nota")),
        "source": public_text(raw.get("pma_source")),
        "verificationStatus": "located",
        "officialBasis": prov_pma["locator"],
        "sourceVintage": prov_pma["vintage"],
        "capSpecial": mf == "special",
        "capVerified": mf is not None,
        "routeTo": public_text(raw.get("pma_route_to")),
    }


def has_publishable_cap(pma):
    if pma["verificationStatus"] != "located" or pma["capVerified"] is not True:
        return False
    if is_num(pma["maxForeign"]):
        return True
    return pma["maxForeign"] == "special" and pma["capSpecial"] is True


def stable_value(v):
    if isinstance(v, list):
        return [stable_value(x) for x in v]
    if isinstance(v, dict):
        return {k: stable_value(v[k]) for k in sorted(v.keys()) if v[k] is not None or True}
    return v


def stable_sha256(v) -> str:  # kbli-editorial-certification.ts stableEditorialSha256
    s = json.dumps(stable_value(v), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def pma_fingerprint(pma) -> str:
    keys = ["status", "maxForeign", "condition", "isPriority", "note", "source",
            "verificationStatus", "officialBasis", "sourceVintage", "capSpecial",
            "capVerified", "routeTo"]
    return stable_sha256({k: pma[k] for k in keys})


def matches_cert(section, code, pma, content) -> bool:
    if not has_publishable_cap(pma) or content is None:
        return False
    cert = section.get(code)
    return (
        cert is not None
        and cert.get("pmaFingerprint") == pma_fingerprint(pma)
        and cert.get("contentSha256") == stable_sha256(content)
    )


LIST_STYLE = re.compile(r";\s*(?:dan|atau)\s*$", re.I)
DANGLING = re.compile(r"\s(?:dan|atau|yang|di)\s*$", re.I)


def is_source_truncated(text) -> bool:  # kbli-obligation-truncation.ts
    t = (text or "").strip()
    if not t or LIST_STYLE.search(t):
        return False
    return bool(DANGLING.search(t))


def usable_licence_name(v) -> str:
    t = (v or "").strip()
    return t if t and not is_source_truncated(t) else ""


def licence_for_risk(risk) -> str:
    r = (risk or "").strip()
    if r == "Tinggi":
        return "NIB + Izin"
    if r in ("Menengah Tinggi", "Menengah Rendah"):
        return "NIB + Sertifikat Standar"
    return "NIB"


def resolve_license_type(perizinan, risk) -> tuple[str, bool]:
    """Returns (licence, derived_from_risk)."""
    if isinstance(perizinan, list):
        distinct = list(dict.fromkeys(x for x in (usable_licence_name(p) for p in perizinan) if x))
        if distinct:
            return " · ".join(distinct), False
        return licence_for_risk(risk), True
    p = usable_licence_name(perizinan)
    return (p, False) if p else (licence_for_risk(risk), True)


BARE_DAYS = re.compile(r"^(\d{1,3})$")
N_HARI = re.compile(r"^(\d{1,3})\s*[Hh]ari(?:\s*[Kk]erja)?$")


def format_timeframe(raw):
    s = (raw or "").strip()
    if not s or s in ("-", "—"):
        return None
    if s.lower() == "otomatis":
        return "Instant"
    m = BARE_DAYS.match(s) or N_HARI.match(s)
    if m:
        return f"{m.group(1)} working days"
    return s


def risk_label_en(cat):
    if not cat:
        return None
    lo = cat.lower()
    men = "menengah" in lo
    if men and "tinggi" in lo:
        return "Medium-High"
    if men and "rendah" in lo:
        return "Medium-Low"
    if "tinggi" in lo:
        return "High"
    if "rendah" in lo:
        return "Low"
    return None


def parse_ts_map(rel: str) -> dict[str, str]:
    """Extract "NNNNN": "..." entries from a TS Record literal."""
    rx = re.compile(r'^\s*"(\d{5})":\s*"((?:[^"\\]|\\.)*)"\s*,?\s*$')
    out = {}
    for s in lines_of(rel):
        m = rx.match(s)
        if m:
            out[m.group(1)] = m.group(2)
    return out


# ----------------------------------------------------------------------------
# Load data
# ----------------------------------------------------------------------------
oss = load(P_OSS)
oss5 = {r["kode"] for r in oss["data"] if r.get("digits") == 5}
corpus_file = load(P_CORPUS)
corpus = corpus_file["data"]
corpus_meta = corpus_file["metadata"]
codes = [r["kode_kbli_2025"] for r in corpus]
cset = set(codes)
by_code = {r["kode_kbli_2025"]: r for r in corpus}
assert len(codes) == len(cset) == 1559, len(codes)
assert len(oss5) == 1559, len(oss5)

sha_src = sha256(P_CORPUS)
sha_mouth = sha256(P_CORPUS_MOUTH)
sha_nav = sha256(P_CORPUS_NAV)
version = load(P_VERSION)
slice_file = load(P_SLICE)
ledger = load(P_LEDGER)
gold_file = load(P_GOLD)
gold = gold_file.get("data", gold_file)
disputes = load(P_DISPUTES)["disputes"]
locators_file = load(P_LOCATORS)
locators = locators_file["locators"]
cert = load(P_CERT)

N: dict = OrderedDict()  # every number reported anywhere
N["snapshot_sha"] = (ROOT / "SNAPSHOT_SHA.txt").read_text().strip()
N["corpus_records"] = len(codes)
N["oss_5digit_codes"] = len(oss5)
N["corpus_eq_oss_codeset"] = cset == oss5
N["sha256_source"] = sha_src
N["sha256_mouth_copy_identical"] = sha_mouth == sha_src
N["sha256_navigator_copy_identical"] = sha_nav == sha_src

# ---- judul / uraian transformations -----------------------------------------
title_changed = sorted(c for c in codes if to_title_case(by_code[c]["judul"]) != by_code[c]["judul"])
N["titleId_differs_from_judul"] = len(title_changed)
N["titleId_differs_examples"] = title_changed[:10]

en_cur = parse_ts_map(F_EN)
en_gen = parse_ts_map(F_EN_GEN)
N["english_curated_entries"] = len(en_cur)
N["english_generated_entries"] = len(en_gen)
N["english_curated_phantom"] = sorted(set(en_cur) - cset)
N["english_generated_phantom"] = sorted(set(en_gen) - cset)
titleEn_real = sorted(c for c in codes if c in en_cur or c in en_gen)
titleEn_fallback = sorted(c for c in codes if c not in en_cur and c not in en_gen)
N["titleEn_from_english_maps"] = len(titleEn_real)
N["titleEn_from_curated"] = sum(1 for c in codes if c in en_cur)
N["titleEn_from_generated_only"] = sum(1 for c in codes if c not in en_cur and c in en_gen)
N["titleEn_fallback_to_titleId"] = len(titleEn_fallback)
N["titleEn_fallback_codes"] = titleEn_fallback
N["h1_differs_from_judul"] = len(sorted(set(titleEn_real) | set(title_changed)))
N["titleEnMeta_curated_only_fallback"] = sum(1 for c in codes if c not in en_cur)
# judul_en in OSS equals judul_id (given), so any English h1 is a divergence from OSS wording
N["uraian_longer_than_160_codepoints"] = sum(1 for c in codes if len(by_code[c]["uraian"]) > 160)
N["uraian_longer_than_160_utf16"] = sum(
    1 for c in codes if len(by_code[c]["uraian"].encode("utf-16-le")) // 2 > 160
)

# ---- section derivation -----------------------------------------------------
sec_null = sorted(c for c in codes if section_of(c) is None)
N["section_null_from_prefix"] = len(sec_null)
N["section_null_codes"] = sec_null
N["sektor_id_distinct_values"] = len({r.get("sektor_id") for r in corpus})

# ---- PMA / provenance / certification gates ---------------------------------
pma_by, prov_by, cert_intel, cert_gold, publishable = {}, {}, [], [], []
render_branch = {}
lic_state = Counter()
lic_status = Counter()
for c in codes:
    raw = by_code[c]
    pp = pma_provenance(raw)
    pma = disclose_pma_info(raw, pp)
    pma_by[c], prov_by[c] = pma, pp
    st, ls = licensing_provenance(raw)
    lic_state[st] += 1
    lic_status[ls] += 1
    verified = pp["status"] == "located" and pma["status"] != "unknown"
    pub = has_publishable_cap(pma)
    if pub:
        publishable.append(c)
    ci = matches_cert(cert["canonicalIntel"], c, pma, raw.get("intel_2026"))
    cg = matches_cert(cert["mouthGold"], c, pma, gold.get(c))
    if ci:
        cert_intel.append(c)
    if cg:
        cert_gold.append(c)
    # discloseKbliEditorial + page branch
    if not (verified and pub):
        render_branch[c] = "uraian"  # editorial withheld -> kbli.description
    elif cg:
        render_branch[c] = "gold"
    elif ci and (raw.get("intel_2026") or {}).get("whatItMeans"):
        render_branch[c] = "intel"
    else:
        render_branch[c] = "uraian"

N["pma_verification_status_located"] = sum(1 for r in corpus if r.get("pma_verification_status") == "located")
N["pma_verdict_verified"] = sum(1 for c in codes if prov_by[c]["status"] == "located")
N["pma_verdict_declared_gap"] = 1559 - N["pma_verdict_verified"]
N["pma_cap_publishable"] = len(publishable)
N["cert_registry_canonicalIntel_entries"] = len(cert["canonicalIntel"])
N["cert_registry_mouthGold_entries"] = len(cert["mouthGold"])
N["cert_registry_source_sha_matches_corpus"] = cert.get("sourceDatasetSha256") == sha_src
N["certified_intel_codes"] = len(cert_intel)
N["certified_gold_codes"] = len(cert_gold)
N["render_branch_counts"] = dict(Counter(render_branch.values()))
N["uraian_not_rendered_in_body_codes"] = sorted(c for c, b in render_branch.items() if b != "uraian")
N["licensing_provenance_state"] = dict(lic_state)
N["licensing_provenance_status"] = dict(lic_status)
N["gold_file_entries"] = len(gold)
N["gold_phantom"] = sorted(set(gold) - cset)
N["gold_entries_shown_on_page"] = len(cert_gold)
gold_branch = sorted(c for c, b in render_branch.items() if b == "gold")
N["gold_branch_codes"] = gold_branch
N["intel_2026_present"] = sum(1 for r in corpus if r.get("intel_2026"))
N["intel_editorial_present"] = sum(1 for r in corpus if (r.get("intel_2026") or {}).get("editorial"))
N["intel_shown_on_page"] = sum(1 for c in codes if render_branch[c] in ("intel", "gold"))
N["cert_canonicalIntel_phantom"] = sorted(set(cert["canonicalIntel"]) - cset)
N["cert_mouthGold_phantom"] = sorted(set(cert["mouthGold"]) - cset)

# ---- per_skala / licensing ----------------------------------------------------
rows = [(c, s) for c in codes for s in by_code[c].get("per_skala") or []]
N["per_skala_rows"] = len(rows)
N["codes_without_per_skala"] = sum(1 for c in codes if not by_code[c].get("per_skala"))
N["codes_multi_distinct_risk"] = sum(
    1 for c in codes if len({s["kategori_risiko"] for s in by_code[c].get("per_skala") or []}) > 1
)
N["codes_first_row_risk_not_max"] = 0
order = {"Rendah": 0, "Menengah Rendah": 1, "Menengah Tinggi": 2, "Tinggi": 3}
for c in codes:
    ps = by_code[c].get("per_skala") or []
    if ps and order.get(ps[0]["kategori_risiko"], -1) < max(order.get(s["kategori_risiko"], -1) for s in ps):
        N["codes_first_row_risk_not_max"] += 1
derived = sum(1 for _, s in rows if resolve_license_type(s.get("perizinan"), s.get("kategori_risiko"))[1])
N["licence_rows_derived_from_risk"] = derived
N["licence_rows_from_perizinan"] = len(rows) - derived
N["codes_first_row_licence_derived"] = sum(
    1 for c in codes if (by_code[c].get("per_skala") or [])
    and resolve_license_type(by_code[c]["per_skala"][0].get("perizinan"), by_code[c]["per_skala"][0].get("kategori_risiko"))[1]
)
tf_changed = sum(1 for _, s in rows if format_timeframe(s.get("jangka_waktu")) not in (None, (s.get("jangka_waktu") or "").strip()))
N["timeframe_rows_rewritten"] = tf_changed
N["timeframe_values"] = dict(Counter(s.get("jangka_waktu") for _, s in rows).most_common(10))
N["risk_values_unmapped_by_riskLabelEn"] = sorted({s["kategori_risiko"] for _, s in rows if risk_label_en(s["kategori_risiko"]) is None})
obl = [t for _, s in rows for t in (s.get("kewajiban") or [])]
req = [t for _, s in rows for t in (s.get("persyaratan") or [])]
N["kewajiban_items"] = len(obl)
N["kewajiban_flagged_truncated"] = sum(1 for t in obl if is_source_truncated(t))
N["persyaratan_items"] = len(req)
N["persyaratan_flagged_truncated"] = sum(1 for t in req if is_source_truncated(t))
N["kewenangan_rows_nonempty"] = sum(1 for _, s in rows if s.get("kewenangan"))
N["scope_uraian_rows_nonempty"] = sum(1 for _, s in rows if s.get("scope_uraian"))

# ---- raw field presence (KBLIRawCode vs corpus) -----------------------------
key_counts = Counter(k for r in corpus for k in r.keys())
N["raw_field_presence"] = {
    k: key_counts.get(k, 0)
    for k in [
        "pma_official_basis", "pma_source_vintage", "pma_cap_verified", "pma_cap_special",
        "pma_route_to", "_l2_source", "_l2_status", "_data_note", "aggregation_note",
        "mapping_note", "kbli_2020_source", "per_skala_disputed_pp28_collision",
        "per_skala_disputed_pp28_mice", "status_mapping", "pp28_sources", "pma_max_asing",
    ]
}
declared = set(re.findall(r"^\s+([a-zA-Z_][a-zA-Z_0-9]*)\??:", "\n".join(
    lines_of(F_TYPES)[ln(F_TYPES, "export interface KBLIRawCode") - 1: ln(F_TYPES, "export interface KBLIRawCode") + 60]
), re.M))
N["corpus_fields_not_declared_in_KBLIRawCode"] = sorted(k for k in key_counts if k not in declared and not k.startswith("per_skala_disputed_"))
N["l4_status_values"] = dict(Counter(r["l4_bali"].get("status") for r in corpus))
N["status_mapping_values"] = dict(Counter(r.get("status_mapping") for r in corpus))
N["ruang_lingkup_records_nonempty"] = sum(1 for r in corpus if r.get("ruang_lingkup"))
N["ruang_lingkup_rendered_by_site"] = False  # grep in METHOD: no consumer in apps/mouth/src

# ---- perpres slice disclosures (b) ------------------------------------------
slice_codes = sorted(slice_file["disclosures"].keys())
slice_excl = sorted((slice_file.get("_meta") or {}).get("excluded_adjacent_not_contained", {}).keys())
N["slice_disclosure_codes"] = slice_codes
N["slice_disclosure_count"] = len(slice_codes)
N["slice_meta_count"] = (slice_file.get("_meta") or {}).get("count")
N["slice_phantom_vs_corpus"] = sorted(set(slice_codes) - cset)
N["slice_phantom_vs_oss"] = sorted(set(slice_codes) - oss5)
N["slice_excluded_codes"] = slice_excl
N["slice_excluded_phantom_vs_corpus"] = sorted(set(slice_excl) - cset)
N["slice_excluded_phantom_vs_oss"] = sorted(set(slice_excl) - oss5)
N["slice_codes_whole_code_TERBUKA"] = sum(1 for c in slice_codes if c in by_code and by_code[c].get("pma_status") == "TERBUKA")
N["slice_codes_pma_verified"] = sum(1 for c in slice_codes if c in prov_by and prov_by[c]["status"] == "located")
N["slice_codes_on_gold_pages"] = sorted(set(slice_codes) & set(gold_branch))
N["dispute_codes_on_gold_pages"] = sorted(set(disputes) & set(gold_branch))
N["codes_with_per_skala_not_rendered_in_licensing_section"] = sum(1 for c in codes if (by_code[c].get("per_skala") or []) and c not in gold_branch)
N["disputes_count"] = len(disputes)
N["disputes_phantom"] = sorted(set(disputes) - cset)
N["locators_count"] = len(locators)
N["locators_codeset_eq_corpus"] = set(locators) == cset
N["locators_phantom"] = sorted(set(locators) - cset)
N["locators_with_cite"] = sum(1 for v in locators.values() if public_text(v.get("cite")))
phantoms_dropped = (corpus_meta.get("l1_realign") or {}).get("phantoms_dropped", [])
N["metadata_phantoms_dropped"] = phantoms_dropped
N["phantoms_dropped_still_in_english_maps"] = sorted(c for c in phantoms_dropped if c in en_cur or c in en_gen)
N["phantoms_dropped_still_in_gold"] = sorted(c for c in phantoms_dropped if c in gold)

# ---- hardcoded code lists in TS -----------------------------------------------
nat_codes = re.findall(r'^\s+\[?\s*"(\d{5})",', "\n".join(lines_of(F_BLOCK)[ln(F_BLOCK, "const NATIONAL_CLOSURE_CODES") - 1: ln(F_BLOCK, "export function nationalClosureBasis")]), re.M)
nat_codes += re.findall(r'\["(\d{5})",', "\n".join(lines_of(F_BLOCK)[ln(F_BLOCK, "const NATIONAL_CLOSURE_CODES") - 1: ln(F_BLOCK, "export function nationalClosureBasis")]))
nat_codes = sorted(set(nat_codes))
N["national_closure_hardcoded_codes"] = nat_codes
N["national_closure_phantom"] = sorted(set(nat_codes) - cset)
N["national_closure_pma_status"] = {c: by_code[c].get("pma_status") for c in nat_codes if c in by_code}
N["national_closure_pma_verified"] = {c: prov_by[c]["status"] for c in nat_codes if c in by_code}
conc_keys = re.findall(r'^\s+"(\d{5})": \{', "\n".join(lines_of(F_CONC)), re.M)
conc_refs = sorted(set(re.findall(r"\b(\d{5})\b", "\n".join(lines_of(F_CONC)))) - set(conc_keys))
N["concordance_entry_codes"] = conc_keys
N["concordance_entry_phantom_vs_corpus"] = sorted(set(conc_keys) - cset)
N["concordance_referenced_target_codes"] = conc_refs
N["concordance_target_phantom_vs_corpus"] = sorted(set(conc_refs) - cset)

# ---- claim ledger (c) ---------------------------------------------------------
claims = ledger["claims"]
N["ledger_schema_version"] = ledger.get("$schema_version")
N["ledger_verified_on"] = ledger.get("verified_on")
N["ledger_claim_count"] = len(claims)
N["ledger_claim_fields"] = sorted({k for c in claims for k in c.keys()})
# Consumers: any file under apps/mouth (src, scripts, tests) that mentions the ledger file
mouth_files = [p for p in (ROOT / "apps/mouth").rglob("*") if p.is_file() and p.suffix in (".ts", ".tsx", ".js", ".mjs", ".json", ".md", ".py") and "node_modules" not in p.parts]
ledger_consumers = []
id_hits: dict[str, list[str]] = {c["id"]: [] for c in claims}
for p in mouth_files:
    if p.resolve() == (ROOT / P_LEDGER).resolve():
        continue
    try:
        txt = p.read_text(encoding="utf-8")
    except Exception:
        continue
    if "regulatory-claim-ledger" in txt or "claim-ledger" in txt or "claimLedger" in txt:
        ledger_consumers.append(str(p.relative_to(ROOT)))
    for cid in id_hits:
        if cid in txt:
            id_hits[cid].append(str(p.relative_to(ROOT)))
N["ledger_consumers_in_apps_mouth"] = sorted(ledger_consumers)
N["ledger_ids_referenced_anywhere_in_apps_mouth"] = {k: v for k, v in id_hits.items() if v}
N["ledger_claims_used_on_kbli_pages"] = 0
N["ledger_claims_unused_on_kbli_pages"] = len(claims)
ledger_codes = {c["id"]: sorted(set(re.findall(r"\b(\d{5})\b", json.dumps(c, ensure_ascii=False)))) for c in claims}
N["ledger_codes_mentioned_not_in_corpus"] = {k: [x for x in v if x not in cset] for k, v in ledger_codes.items() if any(x not in cset for x in v)}

# ---- dataset version (d) ------------------------------------------------------
N["version_sidecar_fields"] = sorted(version.keys())
N["version_sidecar_lastModified"] = version.get("lastModified")
N["version_sidecar_sha"] = version.get("datasetSha256")
N["version_sidecar_sha_matches_corpus"] = version.get("datasetSha256") == f"sha256:{sha_src}"
N["corpus_metadata_version"] = corpus_meta.get("version")
N["corpus_metadata_total_codes"] = corpus_meta.get("total_codes")
N["corpus_metadata_total_codes_eq_len"] = corpus_meta.get("total_codes") == len(codes)
N["corpus_metadata_date_fields"] = {k: v for k, v in corpus_meta.items() if isinstance(v, str) and re.search(r"20\d\d-\d\d-\d\d", v)}
N["corpus_metadata_has_lastModified"] = "lastModified" in corpus_meta
N["version_sidecar_has_version_or_total"] = any(k in version for k in ("version", "total_codes", "totalCodes"))
N["server_fallback_lastModified"] = "2026-06-19"
N["jsonld_datePublished_hardcoded"] = "2025-06-18"
N["metadata_from_both"] = corpus_meta.get("from_both")
N["metadata_from_bps_only"] = corpus_meta.get("from_bps_only")
N["metadata_from_kbli_only"] = corpus_meta.get("from_kbli_only")
N["metadata_sum_from_fields"] = (corpus_meta.get("from_both") or 0) + (corpus_meta.get("from_bps_only") or 0) + (corpus_meta.get("from_kbli_only") or 0)
N["source_field_counts"] = dict(Counter(r.get("_source") for r in corpus))

# ----------------------------------------------------------------------------
# Findings
# ----------------------------------------------------------------------------
findings: list[dict] = []
seq: Counter = Counter()


def add(family, code, file, line, claim, confidence, runtime, fix):
    assert family in FAMILY_ABBREV, family
    assert len(claim) < 200, (len(claim), claim)
    for q in re.findall(r'"([^"]*)"', claim + " " + fix):
        assert len(q) <= 80, q
    seq[family] += 1
    findings.append(
        OrderedDict(
            finding_id=f"{LANE}-{FAMILY_ABBREV[family]}-{seq[family]:03d}",
            family=family,
            code=code or "",
            file=file,
            line=str(line),
            claim=claim,
            confidence=f"{float(confidence):.2f}",
            runtime_dependent="true" if runtime else "false",
            suggested_fix=fix,
        )
    )


def ex(lst, n=6):
    return ",".join(lst[:n]) + (f",+{len(lst) - n}" if len(lst) > n else "")


# ===== (a) FIELD_TRACE: page /kbli/[code] and its components ==================
T = "FIELD_TRACE"
H = "HEURISTIC"
add(T, "", F_DATA, ln(F_DATA, '"KBLI_2025_FINAL_CLEAN.json",'),
    "Loader kbli-data.ts reads data/KBLI_2025_FINAL_CLEAN.json (cwd-relative); sha256 identical to corpus copy in data/source_documents",
    1.0, False, "Keep; add a build-time sha256 guard against the source_documents copy")
add(T, "", F_PAGE, ln(F_PAGE, "KBLI {kbli.code}"),
    "Code pill renders kbli.code = corpus kode_kbli_2025 verbatim", 1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "{kbli.description}"),
    f"Lead paragraph renders kbli.description = corpus uraian verbatim, but only on the non-gold, non-intel branch: {N['render_branch_counts'].get('uraian', 0)} of 1559 codes",
    1.0, False, "Render uraian on every layout (also gold/intel) so OSS wording is always on the page")
add(T, "", F_DATA, ln(F_DATA, "description: raw.uraian,"),
    "kbli.description is assigned raw.uraian with no transformation in the loader", 1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "category={kbli.licensing[0].riskCategory}"),
    "RiskBadge reads per_skala[0].kategori_risiko (first row only), label mapped to English in RiskBadge.parseRisk",
    1.0, False, "State which skala/scope row the badge summarises, or show the tier range")
add(T, "", F_PAGE, ln(F_PAGE, '{kbli.licensing[0].licenseType || "NIB"}'),
    "License Type cell reads per_skala[0].perizinan via resolveLicenseType; empty perizinan falls back to risk-derived label",
    1.0, False, "Label the risk-derived fallback as derived, not as OSS data")
add(T, "", F_PAGE, ln(F_PAGE, "{formatTimeframe(kbli.licensing[0].timeframe) ??"),
    "Processing cell reads per_skala[0].jangka_waktu through formatTimeframe (rewrites Otomatis and bare day counts)",
    1.0, False, "Show the raw jangka_waktu value next to the English rendering")
add(T, "", F_PAGE, ln(F_PAGE, "? formatPmaOwnership(kbli.pma)"),
    "Foreign Ownership cell derives from pma_status, pma_max_asing, pma_cap_verified, pma_cap_special via formatPmaOwnership",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "<TransitionBadge transition={kbli.transition} />"),
    "TransitionBadge reads status_mapping and bps_2020_ancestors.codes; hidden when ancestors list is empty",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "status={kbli.baliL4.status}"),
    "BaliStatusBadge reads l4_bali.status, reason, confidence, needs_review (gated on PMA verdict located)",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "<ProvenanceBadge state={kbli.provenance.state} />"),
    "ProvenanceBadge state derived from _l2_source, _l2_status and presence of per_skala_disputed_* keys",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "Instrument locator:"),
    "Instrument locator line reads perpres-locators.json cite for the code (OTHER_FILE), shown only when PMA verdict located",
    1.0, False, "None")
add(T, "", F_LIC, ln(F_LIC, '{tier.scales.join(" + ")}'),
    "LicensingSection tier tabs render per_skala[i].skala_usaha joined with plus signs", 1.0, False, "None")
add(T, "", F_LIC, ln(F_LIC, "const duty = describeObligation(req);"),
    "LicensingSection requirements render per_skala[i].persyaratan items trimmed, with a heuristic truncation marker",
    1.0, False, "None")
add(T, "", F_LIC, ln(F_LIC, "const duty = describeObligation(obl);"),
    "LicensingSection obligations render per_skala[i].kewajiban items trimmed, with a heuristic truncation marker",
    1.0, False, "None")
add(T, "", F_LIC, ln(F_LIC, "{currentTier.timeframe && ("),
    "LicensingSection tier panel renders per_skala[i].jangka_waktu raw and per_skala[i].fiktif_positif flag",
    1.0, False, "None")
add(T, "", F_LIC, ln(F_LIC, "{kbli.perpresSlice.map((row, i) => ("),
    f"Perpres slice notice (LicensingSection) renders kbli-perpres-slice-disclosures.json rows (OTHER_FILE); LicensingSection mounts only on gold pages: {len(N['slice_codes_on_gold_pages'])} of {N['slice_disclosure_count']} slice codes",
    1.0, False, "Render the slice notice outside the gold-only branch")
add(T, "", F_FAQ, ln(F_FAQ, "const perpresSliceQualifier = hasPerpresSlice"),
    f"FAQ answer 1 (Common Questions + FAQ JSON-LD) appends a slice qualifier from kbli-perpres-slice-disclosures.json for all {N['slice_disclosure_count']} slice codes",
    1.0, False, "None")
add(H, "", F_PAGE, ln(F_PAGE, "<LicensingSection kbli={kbli} gold={gold} />"),
    f"LicensingSection (skala tabs, persyaratan, kewajiban, slice and dispute notices) is inside the gold branch: mounted on {len(gold_branch)} pages; {N['codes_with_per_skala_not_rendered_in_licensing_section']} codes with per_skala never show persyaratan/kewajiban",
    1.0, False, "Mount LicensingSection on the non-gold layout too")
add(H, "", F_LIC, ln(F_LIC, "{kbli.riskDispute && ("),
    f"Risk dispute notice reaches the page for {len(N['dispute_codes_on_gold_pages'])} of {N['disputes_count']} disputed codes (gold-only mount); FAQ answer 2 carries a dispute qualifier for all",
    1.0, False, "Render the dispute notice on every layout")
add(T, "", F_LIC, ln(F_LIC, '{kbli.riskDispute.recordTiers.join(" / ")}'),
    "Risk dispute notice renders recordTiers/kind/baliDependsOnTier from kbli-risk-disputes.json (OTHER_FILE)",
    1.0, False, "None")
add(T, "", F_TRANS, ln(F_TRANS, "const bpsCodes = transition.bpsCrosswalk?.codes ?? [];"),
    "KBLITransitionSources renders bps_2020_ancestors.codes, pp28_sources and mapping_note", 1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "<KBLIDivergence code={kbli.code} provenance={kbli.provenance} />"),
    "KBLIDivergence renders per_skala_disputed_* rows and _l2_status no_oss_risk flag via provenance", 1.0, False, "None")
add(T, "", F_PROVPANEL, ln(F_PROVPANEL, "const dateStr = lastModified.toISOString().slice(0, 10);"),
    "Provenance panel date comes from kbli-dataset-version.json lastModified (OTHER_FILE), not from corpus metadata",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "<KBLIEditorial editorial={intel.editorial} />"),
    f"KBLIEditorial renders intel_2026.editorial headline/body through humanizeInternalEnums; shown only for certified intel ({N['certified_intel_codes']} codes)",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "{intel.whatItMeans}"),
    f"Non-gold intel layout renders intel_2026.whatItMeans/whatChanged/whatYouNeed/baliContext/whoThisIsFor/youllAlsoNeed for {N['render_branch_counts'].get('intel', 0)} codes",
    1.0, False, "None")
add(T, "", F_PAGE, ln(F_PAGE, "{gold.whatItMeans}"),
    f"Gold layout renders kbli-gold-all.json fields (OTHER_FILE) instead of corpus text for {N['render_branch_counts'].get('gold', 0)} certified codes",
    1.0, False, "None")
add(T, "", F_JSONLD, ln(F_JSONLD, "name: `KBLI ${code.code} — ${code.titleId}`,"),
    "Article JSON-LD name/headline use titleId (title-cased judul); keywords add titleEn when different", 1.0, False, "None")
add(T, "", F_FAQ, ln(F_FAQ, "const head = `KBLI ${code.code} (${code.titleId})`;"),
    "FAQ answers embed titleId (title-cased judul) and titleEn; question templates are hardcoded English", 1.0, False, "None")
add(T, "", F_CARD, ln(F_CARD, "{code.titleEn}"),
    "Related-code cards render titleEn (English map) and titleId (title-cased judul) with the same transforms as the hero",
    1.0, False, "None")
add(T, "", F_SECTOR, ln(F_SECTOR, "const codes = getCodesBySection(id);"),
    "Sector page lists codes by prefix-derived section using KBLICard (titleEn/titleId); sektor_id never read",
    1.0, False, "None")
add(T, "", F_TYPES, ln(F_TYPES, "export interface KBLIRawCode"),
    f"Corpus ruang_lingkup ({N['ruang_lingkup_records_nonempty']} records) and per_skala.scope_uraian are not declared or rendered anywhere in apps/mouth/src",
    1.0, False, "Decide whether OSS ruang lingkup should be shown; today the site omits it")
add(T, "", F_LIC, ln(F_LIC, 'value: "BKPM / OSS",'),
    f"per_skala.kewenangan ({N['kewenangan_rows_nonempty']} non-empty rows) is mapped to licensing.authority but never rendered; Authority cell is a literal",
    1.0, False, "Render kewenangan or drop the Authority cell")

# ===== judul / uraian verdict rows ============================================
add(H, "", F_DATA, ln(F_DATA, "const titleId = toTitleCase(raw.judul);"),
    f"Rendered judul (titleId) is toTitleCase(judul): lower-cased then re-capitalised; differs from corpus judul for {N['titleId_differs_from_judul']} of 1559 codes",
    1.0, False, "Render raw.judul verbatim; drop toTitleCase (corpus judul is already mixed case)")
add(H, "", F_DATA, ln(F_DATA, "function toTitleCase(text: string): string {"),
    f"toTitleCase breaks acronyms and parenthesised tokens (e.g. {ex(N['titleId_differs_examples'], 4)}); verdict: judul NOT verbatim for all codes",
    1.0, False, "Remove toTitleCase or restrict it to all-uppercase input")
add(H, "", F_PAGE, ln(F_PAGE, "{kbli.description}"),
    f"Verdict uraian: rendered verbatim on {N['render_branch_counts'].get('uraian', 0)} codes; absent from body on {len(N['uraian_not_rendered_in_body_codes'])} certified codes (gold/intel replace it)",
    1.0, False, "Always render uraian; place editorial below it")
add(H, "", F_JSONLD, ln(F_JSONLD, "description: `${code.description.slice(0, 160)}."),
    f"JSON-LD description truncates uraian to 160 chars for {N['uraian_longer_than_160_utf16']} of 1559 codes and appends PMA/risk prose",
    1.0, False, "Truncate at a sentence boundary and mark as excerpt, or use the full uraian")

# ===== OTHER_FILE: English titles ==============================================
O = "OTHER_FILE"
add(O, "", F_DATA, ln(F_DATA, "ENGLISH_TITLES[code] ?? ENGLISH_TITLES_GENERATED[code] ?? null"),
    f"h1 title = English string from kbli-english.ts ({N['titleEn_from_curated']} codes) or kbli-english-generated.ts ({N['titleEn_from_generated_only']}); not an OSS field (OSS judul_en == judul_id)",
    1.0, False, "Label the English h1 as a Bali Zero translation; show OSS judul as primary")
add(O, "", F_EN_GEN, ln(F_EN_GEN, "export const ENGLISH_TITLES_GENERATED"),
    f"Generated map header states LLM batch translation of judul; {N['english_generated_entries']} entries, {len(N['english_generated_phantom'])} not in corpus",
    1.0, False, "Add a visible translation disclaimer on pages using generated titles")
add(O, "", F_DATA, ln(F_DATA, "const titleEn = titleEnReal ?? titleId;"),
    f"Fallback: titleEn = titleId for {N['titleEn_fallback_to_titleId']} codes without any English entry ({ex(N['titleEn_fallback_codes'], 5)})",
    1.0, False, "None (fallback is the title-cased judul)")
add(O, "", F_DATA, ln(F_DATA, "ENGLISH_TITLES[code] ?? ENGLISH_TITLES_GENERATED[code] ?? null"),
    f"h1 differs from corpus judul for {N['h1_differs_from_judul']} of 1559 codes (English map or title-case change)",
    1.0, False, "Compute and publish the per-code judul alignment table")
add(O, "", F_DATA, ln(F_DATA, "const goldPath = path.join(process.cwd()"),
    f"kbli-gold-all.json has {N['gold_file_entries']} entries; only {N['gold_entries_shown_on_page']} pass certification (pmaFingerprint+contentSha256) and reach the page",
    1.0, False, "Document the certification gate in the page footer")
add(O, "", F_CERT, ln(F_CERT, "import certifications from"),
    f"Editorial gate reads data/kbli-filiera/pma-editorial-certifications.json: canonicalIntel {N['cert_registry_canonicalIntel_entries']}, mouthGold {N['cert_registry_mouthGold_entries']} entries; sha matches corpus: {N['cert_registry_source_sha_matches_corpus']}",
    1.0, False, "None")
add(O, "", F_LOC, ln(F_LOC, 'const LOCATORS_PATH'),
    f"perpres-locators.json covers {N['locators_count']} codes (set equals corpus: {N['locators_codeset_eq_corpus']}); cite non-empty for {N['locators_with_cite']}",
    1.0, False, "None")
add(O, "", F_DISP, ln(F_DISP, '"kbli-risk-disputes.json",'),
    f"kbli-risk-disputes.json carries {N['disputes_count']} codes (all in corpus: {not N['disputes_phantom']}); kbli-data.ts comment says 30",
    0.9, False, "Update the comment or the artifact so the counts agree")

# ===== HEURISTIC rows =========================================================
add(H, "", F_SECTION, ln(F_SECTION, "export function getSectionFromCode"),
    f"Section letter derived from 2-digit code prefix (SECTION_PREFIX_MAP); corpus sektor_id ignored; null section for {N['section_null_from_prefix']} codes",
    1.0, False, "None (sektor_id is a PP28 locator, not a BPS section)")
add(H, "", F_DERIVE, ln(F_DERIVE, "export function licenseForRisk"),
    f"licenseForRisk maps kategori_risiko to NIB/NIB + Sertifikat Standar/NIB + Izin; applied to {N['licence_rows_derived_from_risk']} of {N['per_skala_rows']} per_skala rows with empty perizinan",
    1.0, False, "Flag derived licence labels as derived from PP 28 risk tier, not read from OSS")
add(H, "", F_PAGE, ln(F_PAGE, '{kbli.licensing[0].licenseType || "NIB"}'),
    f"First-row License Type is risk-derived (not from perizinan) for {N['codes_first_row_licence_derived']} of {1559 - N['codes_without_per_skala']} codes with per_skala",
    1.0, False, "Show the derivation basis in the cell")
add(H, "", F_PAGE, ln(F_PAGE, "category={kbli.licensing[0].riskCategory}"),
    f"Hero RiskBadge uses per_skala[0] only; {N['codes_multi_distinct_risk']} codes have >1 distinct kategori_risiko across rows, {N['codes_first_row_risk_not_max']} where row 0 is below the max tier",
    1.0, False, "Show tier range or the highest tier with a per-scale caveat")
add(H, "", F_DERIVE, ln(F_DERIVE, "export function formatTimeframe"),
    f"formatTimeframe rewrites jangka_waktu (Otomatis to Instant, N to N working days) for {N['timeframe_rows_rewritten']} of {N['per_skala_rows']} rows; other strings pass through",
    1.0, False, "Keep raw value visible; the working-days reading of a bare number is an assumption")
add(H, "", F_DERIVE, ln(F_DERIVE, "export function riskLabelEn"),
    f"riskLabelEn maps kategori_risiko by substring (menengah/tinggi/rendah); unmapped values in corpus: {len(N['risk_values_unmapped_by_riskLabelEn'])}",
    1.0, False, "None")
add(H, "", F_TRUNC, ln(F_TRUNC, "export function isSourceTruncated"),
    f"Truncation marker is a regex on trailing dan/atau/yang/di; flags {N['kewajiban_flagged_truncated']} of {N['kewajiban_items']} kewajiban and {N['persyaratan_flagged_truncated']} of {N['persyaratan_items']} persyaratan items",
    1.0, False, "Verify flagged items against OSS ruang_lingkup text; regex is a proxy")
add(H, "", F_LABELS, ln(F_LABELS, "export function humanizeInternalEnums"),
    "All intel_2026, gold and l4_bali.reason text is regex-rewritten: internal enum tokens replaced by English labels before render",
    1.0, False, "Rewrite at data build time, not at render, so what is served equals what is stored")
add(H, "", F_PMA, ln(F_PMA, "export function discloseBaliL4("),
    f"l4_bali shown only if PMA verdict located and status in ALLOWED set; confidence coerced to MEDIUM if not HIGH/MEDIUM/LOW; {N['l4_status_values'].get('NON_CLASSIFICABILE', 0)} NON_CLASSIFICABILE",
    1.0, False, "None")
add(H, "", F_PROV, ln(F_PROV, "export function deriveProvenance"),
    f"Provenance state derived from _l2_source/_l2_status/disputed keys: {json.dumps(N['licensing_provenance_state'])} (licensing status has same split)",
    1.0, False, "None")
add(H, "", F_PAGE, ln(F_PAGE, "isNationalClosure(kbli.baliL4?.status, kbli.code) ||"),
    "PMA banner text chosen by rule over baliL4.blocked, hardcoded national-closure code list, pma.status, capVerified and maxForeign",
    1.0, False, "Move the decision inputs into the corpus record so the banner is data, not code")
add(H, "", F_PAGE, ln(F_PAGE, "/\\b(PT PMA|100% foreign|foreign-owned)\\b/i.test(op)"),
    "Chat opener replaced by a template when baliL4.blocked and a regex matches foreign-ownership phrases",
    1.0, False, "None")
add(H, "", F_DATA_SRV, ln(F_DATA_SRV, "const goldBaliMisleads ="),
    "server transform swaps gold baliContext for l4 text when a regex finds foreign-ownership phrases on a blocked code (server module, not the page path)",
    1.0, False, "None")
add(H, "", F_LIC, ln(F_LIC, "function parseWhatYouNeed(markdown: string) {"),
    "Gold whatYouNeed markdown is parsed by regex into alert/source/sections and section titles are renamed (humanizeTitle)",
    1.0, False, "None")
add(H, "", F_BALICTX, ln(F_BALICTX, "{baliContext.split(/\\n---\\n/).map((block, idx) => {"),
    "baliContext is split on --- separators and card titles inferred by keyword matching", 1.0, False, "None")
add(H, "", F_YOULL, ln(F_YOULL, "const exists = !!getCode(code);"),
    "youllAlsoNeed lines parsed for leading 5-digit codes; links only when getCode finds them in corpus", 1.0, False, "None")
add(H, "", F_DATA, ln(F_DATA, "keywords: extractKeywords(raw.judul, raw.uraian),"),
    "keywords derived from judul+uraian by stopword regex (max 20); used by kbli-search only", 1.0, False, "None")
add(H, "", F_DATA, ln(F_DATA, "function assignTier(code: string, goldCertified: boolean): KBLITier {"),
    "tier gold/silver/bronze derived from certification and English-map presence; rendered as Gold-Tier Intel label",
    1.0, False, "None")
add(H, "", F_META, ln(F_META, "return `KBLI ${kbli.code}: ${metaTitleEn} — ${kbliMetaTitleSuffix(kbli)}`;"),
    "HTML title/description composed from titleEnMeta plus rule-derived PMA/risk suffix (kbliMetaTitleSuffix)", 1.0, False, "None")
add(H, "", F_EDIT, ln(F_EDIT, "export function discloseKbliEditorial("),
    f"Editorial (gold+intel) withheld unless PMA verdict located and cap publishable: {N['pma_cap_publishable']} codes publishable of 1559",
    1.0, False, "None")

# ===== HARDCODED rows =========================================================
HC = "HARDCODED"
add(HC, "", F_DATA, ln(F_DATA, "const SECTION_META"),
    "Section names (nameEn, nameId, description, icon) are literals in kbli-data.ts SECTION_META; not from corpus or OSS",
    1.0, False, "Source section names from BPS/OSS data or mark as editorial")
add(HC, "", F_DATA_SRV, ln(F_DATA_SRV, "const SECTION_NAMES_EN"),
    "A second, differently worded section-name map exists in kbli-data.server.ts (D, K, L, V differ from kbli-data.ts)",
    1.0, False, "Keep one map")
add(HC, "", F_LIC, ln(F_LIC, 'value: "BKPM / OSS",'),
    "Authority fact cell is the literal BKPM / OSS on every gold page; corpus kewenangan lists other authorities", 1.0, False, "Render kewenangan")
add(HC, "", F_JSONLD, ln(F_JSONLD, 'datePublished: "2025-06-18",'),
    "JSON-LD datePublished is a literal date for all codes; not present in corpus metadata", 1.0, False, "Derive from dataset sidecar or omit")
add(HC, "", F_DATA_SRV, ln(F_DATA_SRV, '_datasetLastModified = new Date("2026-06-19");'),
    "Fallback lastModified literal 2026-06-19 differs from sidecar lastModified 2026-08-15", 1.0, False, "Fail the build instead of falling back")
add(HC, "", F_JSONLD, ln(F_JSONLD, 'name: "Badan Pusat Statistik (BPS)",'),
    "JSON-LD attributes the code to BPS as provider while the loader reads OSS-realigned judul/uraian (_l1_source OSS)", 0.9, False,
    "Attribute to OSS/BPS consistently with _l1_source")
add(HC, "", F_PAGE, ln(F_PAGE, "Kepmenaker 228/2019 — Category"),
    "TKA section cites Kepmenaker 228/2019 as literal text; tkaInfo values come from gold file, not corpus", 1.0, False,
    "TO VERIFY: regulation reference; move citation into the claim ledger")
add(HC, "", F_LIC, ln(F_LIC, "Perpres 10/2021 (as amended) — {row.condition}."),
    "Perpres slice notice cites Perpres 10/2021 as literal text; slice file _meta names Perpres 49/2021 Lampiran III", 0.9, False,
    "TO VERIFY: align instrument naming between component and artifact")
add(HC, "", F_BLOCK, ln(F_BLOCK, "export function baliBlockClause"),
    "baliBlockClause maps l4_bali.status to literal English clauses including a 13 May 2026 moratorium date", 1.0, False,
    "TO VERIFY: date; source clauses from the ledger")
for c in nat_codes:
    add(HC, c, F_BLOCK, ln(F_BLOCK, f'"{c}"'),
        f"National closure basis for {c} is a literal in NATIONAL_CLOSURE_CODES (corpus pma_status {N['national_closure_pma_status'].get(c)}, verdict {N['national_closure_pma_verified'].get(c)}); overrides record",
        1.0, False, "Move the closure basis into the corpus record with a locator")
add(HC, "", F_BLOCK, ln(F_BLOCK, "const NATIONAL_CLOSURE_CODES"),
    f"Summary: {len(nat_codes)} hardcoded national-closure codes; all in corpus: {not N['national_closure_phantom']}", 1.0, False, "None")
add(HC, "", F_FAQ, ln(F_FAQ, "The June 2026 KBLI 2025 transition window has closed"),
    "FAQ answer asserts a June 2026 transition-window closure as literal text; not in corpus or ledger", 0.9, False,
    "TO VERIFY: deadline; add to claim ledger and read from it")
add(HC, "", F_META, ln(F_META, 'return "Blocked for PT PMA in Bali (2026)";'),
    "Meta title suffix literal asserts a 2026 Bali block for PT PMA when l4 blocked with HIGH confidence", 1.0, False, "None")
for c in conc_keys:
    add(HC, c, F_CONC, ln(F_CONC, f'"{c}": {{'),
        f"Explorer concordance entry for {c} carries literal regulatory status/impact/action text (in corpus: {c in cset})",
        1.0, False, "Move to a reviewed data artifact with source locators")
add(HC, "", F_CONC, ln(F_CONC, "export const KBLI_CONCORDANCE_2025"),
    f"Concordance references target codes {','.join(conc_refs)} (all in corpus: {not N['concordance_target_phantom_vs_corpus']}); includes literal 2026 deadlines and IDR figures",
    1.0, False, "TO VERIFY: deadlines and figures; source from ledger")
add(HC, "", F_DATA, ln(F_DATA, "transforms or the two readers disagree on the 14 slice-disclosure codes."),
    f"Comment says 14 slice-disclosure codes; artifact carries {N['slice_disclosure_count']} (_meta.count {N['slice_meta_count']})", 0.9, False,
    "Update comment")
add(HC, "", F_CERT, ln(F_CERT, "export function neutralKbliChatOpenerText"),
    "Chat opener is always replaced by a neutral template; gold/intel zantaraOpener never reaches the page", 1.0, False, "None")

# ===== SCHEMA_DIVERGENCE ======================================================
S = "SCHEMA_DIVERGENCE"
add(S, "", F_DATA_SRV, ln(F_DATA_SRV, "titleEn: raw.judul,"),
    "Two loaders build KBLICode differently: kbli-data.server.ts sets titleEn = judul, kbli-data.ts sets titleEn = English map; page mixes both modules",
    1.0, False, "Collapse to one transform")
add(S, "", F_PAGE, ln(F_PAGE, "getKbliDatasetLastModified,"),
    "page imports getCode from kbli-data.ts but getGoldContent from kbli-data.server.ts (separate caches, separate transforms)",
    1.0, False, "Import gold and code from the same module")
add(S, "", F_TYPES, ln(F_TYPES, "export interface KBLIRawCode"),
    f"KBLIRawCode declares PMA locator fields present on few records: pma_official_basis {N['raw_field_presence']['pma_official_basis']}, pma_source_vintage {N['raw_field_presence']['pma_source_vintage']}, pma_cap_verified {N['raw_field_presence']['pma_cap_verified']} of 1559",
    1.0, False, "None (drives the declared_gap gate)")
add(S, "", F_PROV, ln(F_PROV, "function pmaProvenance"),
    f"PMA verdict located for {N['pma_verdict_verified']} codes; {N['pma_verdict_declared_gap']} pages show the not-verified banner and withhold editorial",
    1.0, False, "None")
add(S, "", F_TYPES, ln(F_TYPES, "export interface KBLIRawCode"),
    f"Corpus fields not declared in KBLIRawCode and unused: {ex(N['corpus_fields_not_declared_in_KBLIRawCode'], 8)}", 1.0, False, "None")
add(S, "", F_TBADGE, ln(F_TBADGE, "const LABELS: Record<KBLIMappingStatus, string> = {"),
    f"status_mapping missing on {1559 - N['raw_field_presence']['status_mapping']} record(s); LABELS lookup yields undefined label",
    1.0, False, "Guard the missing value")
add(S, "", F_PMA, ln(F_PMA, "if (raw.pma_cap_verified !== true) return null;"),
    f"pma_max_asing is ignored unless pma_cap_verified is true: cap shown for {N['pma_cap_publishable']} codes although pma_max_asing is set on {N['raw_field_presence']['pma_max_asing']}",
    1.0, False, "None")
add(S, "", P_CORPUS, 1,
    f"metadata.total_codes {N['corpus_metadata_total_codes']} equals record count: {N['corpus_metadata_total_codes_eq_len']}; from_both+bps_only+kbli_only = {N['metadata_sum_from_fields']}; _source counts {json.dumps(N['source_field_counts'])}",
    1.0, False, "None")

# ===== (b) PHANTOM_CODE =======================================================
PH = "PHANTOM_CODE"
for c in slice_codes:
    in_c, in_o = c in cset, c in oss5
    add(PH, c, P_SLICE, ln(P_SLICE, f'"{c}"'),
        f"Slice-disclosure code {c}: in corpus {in_c}, in OSS 5-digit set {in_o}; whole-code pma_status {by_code.get(c, {}).get('pma_status')}",
        1.0, False, "None" if in_c and in_o else "Remove or remap the code")
add(PH, "", P_SLICE, ln(P_SLICE, '"disclosures"'),
    f"Summary: {N['slice_disclosure_count']} disclosure codes; not in corpus: {len(N['slice_phantom_vs_corpus'])}; not in OSS: {len(N['slice_phantom_vs_oss'])}; _meta.count {N['slice_meta_count']}",
    1.0, False, "None")
for c in slice_excl:
    add(PH, c, P_SLICE, ln(P_SLICE, f'"{c}"'),
        f"_meta.excluded_adjacent_not_contained code {c} (not rendered): in corpus {c in cset}, in OSS {c in oss5}",
        1.0, False, "None")
add(PH, "", F_EN, ln(F_EN, "export const ENGLISH_TITLES"),
    f"English maps carry codes absent from corpus: curated {len(N['english_curated_phantom'])} ({ex(N['english_curated_phantom'])}), generated {len(N['english_generated_phantom'])} ({ex(N['english_generated_phantom'])})",
    1.0, False, "Prune entries not in KBLI 2025")
for c in N["concordance_entry_phantom_vs_corpus"]:
    add(PH, c, F_CONC, ln(F_CONC, f'"{c}": {{'),
        f"Explorer concordance entry code {c} is not in the 1559 corpus codes (in OSS 5-digit set: {c in oss5})", 1.0, False,
        "Mark as legacy KBLI 2020 code or remove")
for c in N["english_curated_phantom"]:
    add(PH, c, F_EN, ln(F_EN, f'"{c}":'),
        f"Curated English title for {c}: not in corpus (in OSS: {c in oss5}); listed in corpus metadata phantoms_dropped: {c in phantoms_dropped}", 1.0, False, "Remove entry")
for c in N["gold_phantom"]:
    add(PH, c, P_GOLD, ln(P_GOLD, f'"{c}":'),
        f"kbli-gold-all.json entry {c} is not in corpus (in OSS: {c in oss5}); never reaches a page", 1.0, False, "Remove entry")
add(PH, "", P_GOLD, 1,
    f"kbli-gold-all.json codes absent from corpus: {len(N['gold_phantom'])} ({ex(N['gold_phantom'])})", 1.0, False, "Prune")
add(PH, "", P_CORPUS, 1,
    f"metadata.l1_realign.phantoms_dropped {','.join(phantoms_dropped)} still present in English maps: {ex(N['phantoms_dropped_still_in_english_maps'])}; in gold: {ex(N['phantoms_dropped_still_in_gold'])}",
    1.0, False, "Prune dropped phantoms from derived TS/JSON")

# ===== (c) CLAIM_LEDGER =======================================================
CL = "CLAIM_LEDGER"
add(CL, "", P_LEDGER, ln(P_LEDGER, '"claims"'),
    f"Ledger schema v{N['ledger_schema_version']}: top keys $schema_version, description, verified_on, ground_truth_source, claims; claim fields {','.join(N['ledger_claim_fields'])}",
    1.0, False, "None")
add(CL, "", P_LEDGER, ln(P_LEDGER, '"claims"'),
    f"No file under apps/mouth imports or reads the ledger (consumers found: {len(N['ledger_consumers_in_apps_mouth'])}); 0 of {N['ledger_claim_count']} claims used on KBLI pages, {N['ledger_claims_unused_on_kbli_pages']} unused",
    1.0, False, "Wire regulatory literals in KBLI components to ledger ids")
for cl in claims:
    cid = cl["id"]
    bad = N["ledger_codes_mentioned_not_in_corpus"].get(cid, [])
    add(CL, "", P_LEDGER, ln(P_LEDGER, f'"{cid}"'),
        f"Claim {cid} ({cl.get('domain')}, {cl.get('severity')}): not referenced by any KBLI route/component/lib; codes it mentions not in corpus: {','.join(bad) or 'none'}",
        1.0, False, "None")
add(CL, "", F_CONC, ln(F_CONC, "export const KBLI_CONCORDANCE_2025"),
    "Regulatory claims on KBLI surfaces (concordance, bali-block, faq, LicensingSection, page TKA) are component literals, not ledger reads",
    1.0, False, "Reference ledger ids from components")

# ===== (d) VERSION_MISMATCH ===================================================
V = "VERSION_MISMATCH"
add(V, "", P_VERSION, ln(P_VERSION, '"datasetSha256"'),
    f"Sidecar datasetSha256 matches sha256 of loaded corpus: {N['version_sidecar_sha_matches_corpus']}", 1.0, False, "None")
add(V, "", P_VERSION, ln(P_VERSION, '"lastModified"'),
    f"Sidecar lastModified {N['version_sidecar_lastModified']} has no counterpart in corpus metadata (no lastModified field; dated fields: {','.join(N['corpus_metadata_date_fields'].keys())})",
    1.0, True, "TO VERIFY: git commit date of last corpus change; add lastModified to corpus metadata")
add(V, "", P_VERSION, 1,
    f"Sidecar carries no version/total_codes; corpus metadata.version {N['corpus_metadata_version']}, total_codes {N['corpus_metadata_total_codes']} (records {N['corpus_records']})",
    1.0, False, "Add version and total_codes to the sidecar and assert them at build")
add(V, "", P_CERT, 1,
    f"Certification registry sourceDatasetSha256 matches corpus: {N['cert_registry_source_sha_matches_corpus']}; reviewedAt {cert.get('reviewedAt')} vs sidecar {N['version_sidecar_lastModified']}",
    1.0, False, "None")
add(V, "", F_DATA_SRV, ln(F_DATA_SRV, "export function getKbliDatasetLastModified(): Date {"),
    "Page dateModified (JSON-LD, provenance panel) read from sidecar at build; falls back to a literal date on read error", 1.0, False, "Fail build on missing sidecar")

# ===== (e) RUNTIME ============================================================
R = "RUNTIME"
add(R, "", F_DATA, ln(F_DATA, "const META_USES_FULL_EN = process.env.NEXT_PUBLIC_KBLI_META_EN"),
    f"HTML title/meta title source depends on env NEXT_PUBLIC_KBLI_META_EN: full English map if 1, else curated-only with judul fallback for {N['titleEnMeta_curated_only_fallback']} codes",
    1.0, True, "Pin the flag in code; the metadata surface cannot be audited statically")
add(R, "", F_DATA, ln(F_DATA, 'const fallbackPath = path.join(process.cwd(), "data", "kbli-2025.json");'),
    "Corpus path is cwd-relative with a fallback file name; which file is loaded depends on build cwd", 1.0, True, "Resolve path from module location")
add(R, "", F_API, ln(F_API, 'const baseUrl = process.env.NEXT_PUBLIC_API_URL'),
    "kbli.api.ts base URL from env NEXT_PUBLIC_API_URL; explorer and search call a remote kbli-notebook API, not the local JSON",
    1.0, True, "Document which dataset version the API serves")
add(R, "", F_XPAGE, ln(F_XPAGE, "const detail = await kbliApi.inspect(code);"),
    "Explorer inspector title/description/licenses come from remote inspect endpoint; no static trace to corpus fields possible",
    1.0, True, "None (out of static scope)")
add(R, "", F_XINSP, ln(F_XINSP, "{data.title}"),
    "KBLIInspector renders API data.title and data.description; source dataset unknown statically", 1.0, True, "None")
add(R, "", F_SEARCH, ln(F_SEARCH, "const data = await kbliApi.search(query);"),
    "Landing-page KBLISearch results (title, description, risk) come from remote search endpoint", 1.0, True, "None")
add(R, "", F_CHAT, ln(F_CHAT, "process.env.NEXT_PUBLIC_BACKEND_URL ||"),
    "ZantaraChat posts to env NEXT_PUBLIC_BACKEND_URL kbli-notebook chat endpoint; answers are runtime output", 1.0, True, "None")
add(R, "", F_PAGE, ln(F_PAGE, "url: `https://balizero.com/api/og/kbli/${kbli.code}`,"),
    "OG image URL points to /api/og/kbli route; route source not present in snapshot (apps/mouth/src/app has only kbli and kbli-explorer)",
    1.0, True, "TO VERIFY: route exists in full repo")
add(R, "", F_XLAYOUT, ln(F_XLAYOUT, "process.env.NEXT_PUBLIC_PUBLIC_URL"),
    "Explorer canonical base URL from env NEXT_PUBLIC_PUBLIC_URL", 1.0, True, "None")
add(R, "", F_PAGE, ln(F_PAGE, "export const dynamicParams = false;"),
    "All 1559 code pages are pre-rendered at build (SSG); transforms above run at build time against the committed JSON",
    1.0, True, "None")

# ----------------------------------------------------------------------------
# Write outputs
# ----------------------------------------------------------------------------
COLUMNS = ["finding_id", "family", "code", "file", "line", "claim", "confidence", "runtime_dependent", "suggested_fix"]
csv_path = OUT / "kbli_site_vs_corpus.csv"
with csv_path.open("w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for row in findings:
        w.writerow(row)

N["findings_total"] = len(findings)
N["findings_by_family"] = dict(Counter(f["family"] for f in findings))
N["findings_runtime_dependent"] = sum(1 for f in findings if f["runtime_dependent"] == "true")

# render map
render_map = OrderedDict()


def rm(field, source, file, anchor, verbatim, affected, note=None, nth=1):
    entry = OrderedDict(source=source, file=file, line=ln(file, anchor, nth), verbatim=verbatim, affected_codes=affected)
    if note:
        entry["note"] = note
    render_map[field] = entry


rm("hero.h1_title", "OTHER_FILE:kbli-english.ts|kbli-english-generated.ts; fallback HEURISTIC toTitleCase(judul)", F_PAGE, "{kbli.titleEn}", False,
   sorted(set(titleEn_real) | set(title_changed)), "codes whose h1 != corpus judul (English map present or title-case changed)")
rm("hero.subtitle_judul", "HEURISTIC:toTitleCase(data[].judul)", F_PAGE, "{kbli.titleId}", False, title_changed, "codes whose toTitleCase(judul) != judul", nth=2)
rm("hero.code", "data[].kode_kbli_2025", F_PAGE, "KBLI {kbli.code}", True, [])
rm("lead.uraian", "data[].uraian (only when editorial withheld/uncertified)", F_PAGE, "{kbli.description}", True,
   N["uraian_not_rendered_in_body_codes"], "codes where uraian is NOT rendered in the body (gold/intel branch)")
rm("jsonld.description", "HEURISTIC:data[].uraian.slice(0,160) + PMA/risk prose", F_JSONLD, "description: `${code.description.slice(0, 160)}.", False,
   sorted(c for c in codes if len(by_code[c]["uraian"].encode("utf-16-le")) // 2 > 160), "codes whose uraian exceeds 160 UTF-16 units")
rm("jsonld.name_headline", "HEURISTIC:toTitleCase(data[].judul)", F_JSONLD, "name: `KBLI ${code.code} — ${code.titleId}`,", False, title_changed)
rm("meta.title", "RUNTIME:env NEXT_PUBLIC_KBLI_META_EN selects English map; HEURISTIC suffix", F_PAGE, "const metaTitleEn = kbli.titleEnMeta ?? kbli.titleEn;", False, None,
   "affected set depends on env flag: full map (same as hero.h1_title) or curated-only")
rm("hero.section_line", "HEURISTIC:code prefix -> SECTION_PREFIX_MAP; HARDCODED SECTION_META names", F_PAGE, "{sectionMeta.icon} Section {kbli.section}", False, sec_null, "codes with null section")
rm("hero.pma_banner", "HEURISTIC over l4_bali.blocked, l4_bali.status, pma_status, pma_max_asing, pma_cap_verified, HARDCODED NATIONAL_CLOSURE_CODES", F_PAGE, "PMA status not yet verified for this KBLI 2025 code", False, None,
   "text is a literal chosen by rule; not a corpus string")
rm("hero.instrument_locator", "OTHER_FILE:perpres-locators.json locators[code].cite", F_PAGE, "Instrument locator:", True, [])
rm("badge.pma", "data[].pma_status, pma_max_asing, pma_cap_verified, pma_cap_special (labels HARDCODED)", F_PAGE, "<PMABadge", False, None)
rm("badge.risk", "data[].per_skala[0].kategori_risiko (English label HEURISTIC)", F_PAGE, "category={kbli.licensing[0].riskCategory}", False,
   sorted(c for c in codes if len({s["kategori_risiko"] for s in by_code[c].get("per_skala") or []}) > 1), "codes with >1 distinct kategori_risiko (badge shows row 0 only)")
rm("badge.transition", "data[].status_mapping, bps_2020_ancestors.codes (labels HARDCODED)", F_PAGE, "<TransitionBadge transition={kbli.transition} />", False, None)
rm("badge.bali_status", "data[].l4_bali.status/reason/confidence/needs_review (labels HARDCODED, reason regex-humanized)", F_PAGE, "status={kbli.baliL4.status}", False, None)
rm("badge.provenance", "HEURISTIC over _l2_source, _l2_status, per_skala_disputed_*", F_PAGE, "<ProvenanceBadge state={kbli.provenance.state} />", False, None)
rm("editorial.article", "data[].intel_2026.editorial (certified only, regex-humanized)", F_PAGE, "<KBLIEditorial editorial={intel.editorial} />", False, cert_intel, "codes with certified intel")
rm("intel.whatItMeans_etc", "data[].intel_2026.* (certified only, regex-humanized)", F_PAGE, "{intel.whatItMeans}", False, sorted(c for c, b in render_branch.items() if b == "intel"))
rm("gold.*", "OTHER_FILE:kbli-gold-all.json (certified only, regex-humanized)", F_PAGE, "{gold.whatItMeans}", False, cert_gold)
rm("quickfacts.risk_level", "data[].per_skala[0].kategori_risiko via riskLabelEn", F_PAGE, "{riskLabelEn(kbli.licensing[0].riskCategory) ??", False, None)
rm("quickfacts.license_type", "data[].per_skala[0].perizinan; HEURISTIC licenseForRisk when empty", F_PAGE, '{kbli.licensing[0].licenseType || "NIB"}', False,
   sorted(c for c in codes if (by_code[c].get("per_skala") or []) and resolve_license_type(by_code[c]["per_skala"][0].get("perizinan"), by_code[c]["per_skala"][0].get("kategori_risiko"))[1]),
   "codes whose first-row licence label is risk-derived")
rm("quickfacts.processing", "data[].per_skala[0].jangka_waktu via formatTimeframe", F_PAGE, "{formatTimeframe(kbli.licensing[0].timeframe) ??", False, None)
rm("quickfacts.foreign_ownership", "data[].pma_* via formatPmaOwnership", F_PAGE, "? formatPmaOwnership(kbli.pma)", False, None)
rm("licensing.scales", "data[].per_skala[i].skala_usaha", F_LIC, '{tier.scales.join(" + ")}', True, [], "rendered only on gold pages (see gold.*)")
rm("licensing.requirements", "data[].per_skala[i].persyaratan (trimmed, truncation marker HEURISTIC)", F_LIC, "const duty = describeObligation(req);", True, [])
rm("licensing.obligations", "data[].per_skala[i].kewajiban (trimmed, truncation marker HEURISTIC)", F_LIC, "const duty = describeObligation(obl);", True, [])
rm("licensing.authority", "HARDCODED literal; data[].per_skala[i].kewenangan unused", F_LIC, 'value: "BKPM / OSS",', False, None)
rm("licensing.perpres_slice", "OTHER_FILE:kbli-perpres-slice-disclosures.json", F_LIC, "{kbli.perpresSlice.map((row, i) => (", True, [], f"LicensingSection is gold-only; slice codes on gold pages: {N['slice_codes_on_gold_pages']}; FAQ path renders for all slice codes")
rm("licensing.risk_dispute", "OTHER_FILE:kbli-risk-disputes.json", F_LIC, '{kbli.riskDispute.recordTiers.join(" / ")}', True, [])
rm("transition.sources", "data[].bps_2020_ancestors.codes, pp28_sources, mapping_note", F_TRANS, "const bpsCodes = transition.bpsCrosswalk?.codes ?? [];", True, [])
rm("provenance.panel", "data[]._l1_source, _source, _l2_source, pma_official_basis, pma_source_vintage, l4_bali.moratorium; OTHER_FILE kbli-dataset-version.json", F_PAGE, "<KBLIProvenancePanel", False, None)
rm("faq.common_questions", "HARDCODED templates over titleId/titleEn/pma/l4_bali", F_PAGE, "<KBLICommonQuestions code={kbli} />", False, None)
rm("related.cards", "same as hero.h1_title / hero.subtitle_judul", F_PAGE, "<KBLICard key={r.code} code={r} />", False, None)
rm("chat.opener", "HARDCODED neutral template (gold/intel zantaraOpener never shown)", F_PAGE, "const fallback = neutralKbliChatOpener(kbli);", False, None)
rm("ruang_lingkup", "NOT RENDERED (corpus field unused by apps/mouth)", F_TYPES, "export interface KBLIRawCode", False, None, "no consumer found by grep")
rm("explorer.inspector.title_description", "RUNTIME: remote kbli-notebook inspect API", F_XINSP, "{data.title}", False, None, "not statically traceable")

(DATA_OUT / "lane_b_render_map.json").write_text(json.dumps(render_map, indent=2, ensure_ascii=False), encoding="utf-8")
(DATA_OUT / "lane_b_numbers.json").write_text(json.dumps(N, indent=2, ensure_ascii=False, default=str), encoding="utf-8")

# ----------------------------------------------------------------------------
# METHOD.md
# ----------------------------------------------------------------------------
fam_lines = "\n".join(f"| {k} | {v} |" for k, v in sorted(N["findings_by_family"].items()))
method = f"""# Lane B — website (apps/mouth) vs corpus — METHOD

Snapshot SHA: {N['snapshot_sha']} (SNAPSHOT_SHA.txt). All paths relative to the snapshot root.
Script: `science-out/scripts/lane_b_trace.py` (writes this file, the CSV, `science-out/data/lane_b_render_map.json`,
`science-out/data/lane_b_numbers.json`). Command: `python3 science-out/scripts/lane_b_trace.py`.
Line numbers in the CSV are resolved at run time by anchor-substring search; the script aborts if an anchor is missing.

## Files read
- Source of truth: `{P_OSS}` (5-digit codes: {N['oss_5digit_codes']}).
- Corpus: `{P_CORPUS}` ({N['corpus_records']} records, sha256 {N['sha256_source'][:16]}...). Byte-identical copies:
  `{P_CORPUS_MOUTH}` ({N['sha256_mouth_copy_identical']}), `{P_CORPUS_NAV}` ({N['sha256_navigator_copy_identical']}). Corpus code set == OSS 5-digit set: {N['corpus_eq_oss_codeset']}.
- Site data: `{P_VERSION}`, `{P_SLICE}`, `{P_GOLD}`, `{P_DISPUTES}`, `{P_LOCATORS}`, `{P_LEDGER}`, `{P_CERT}`.
- Site code: `apps/mouth/src/app/kbli/**`, `apps/mouth/src/app/kbli-explorer/**`, `apps/mouth/src/components/kbli/*.tsx`,
  `apps/mouth/src/lib/kbli-*.ts`, `apps/mouth/src/lib/api/kbli.api.ts`, `apps/mouth/src/lib/types/kbli.ts`.
  Test files were read as evidence of intent only and are not cited in the CSV.

## Families (controlled set)
FIELD_TRACE (positive trace rendered field -> corpus field, confidence 1.0), HEURISTIC (rule/regex/fallback/string transform),
HARDCODED (literal text or code lists in source), OTHER_FILE (rendered from a non-corpus JSON/TS artifact), PHANTOM_CODE,
CLAIM_LEDGER, VERSION_MISMATCH, SCHEMA_DIVERGENCE (type/loader vs data shape), RUNTIME (depends on env/fetch/build cwd; runtime_dependent=true).

## Ports and definitions
- `toTitleCase` ported literally from kbli-data.ts (lower-case, split on whitespace, capitalise first char except a fixed
  Indonesian stopword list). titleId differs from judul when the ported output != corpus judul: {N['titleId_differs_from_judul']} codes.
- English maps parsed by regex `"NNNNN": "..."` from kbli-english.ts ({N['english_curated_entries']} entries) and
  kbli-english-generated.ts ({N['english_generated_entries']} entries). Precedence curated > generated > titleId (kbli-data.ts).
- Section = SECTION_PREFIX_MAP[code[:2]] (kbli-section.ts); null for {N['section_null_from_prefix']} codes.
- PMA verdict "located" = pma_verification_status == located AND pma_status in TERBUKA/TERBATAS/TERTUTUP AND non-empty
  pma_official_basis AND pma_source_vintage (kbli-provenance.ts pmaProvenance). Located: {N['pma_verdict_verified']}; declared_gap: {N['pma_verdict_declared_gap']}.
- Publishable cap = located AND pma_cap_verified true AND (numeric pma_max_asing OR special+pma_cap_special): {N['pma_cap_publishable']} codes.
- Certification (kbli-editorial-certification.ts): sha256 of key-sorted compact JSON (ensure_ascii=False) of the content, plus a
  fingerprint over 12 PMA fields; matched against `{P_CERT}`. Certified intel: {N['certified_intel_codes']} (registry {N['cert_registry_canonicalIntel_entries']}),
  certified gold: {N['certified_gold_codes']} (registry {N['cert_registry_mouthGold_entries']}). Registry sourceDatasetSha256 == corpus sha: {N['cert_registry_source_sha_matches_corpus']}.
  Caveat: Python json.dumps vs JS JSON.stringify can differ on float formatting; no floats occur in the hashed content, and the
  match counts equal the registry sizes, which supports the port.
- Page body branch per code (app/kbli/[code]/page.tsx): gold layout if certified gold; else intel layout if certified intel with
  whatItMeans; else the uraian paragraph. Counts: {json.dumps(N['render_branch_counts'])}.
- JSON-LD truncation: uraian longer than 160 UTF-16 code units (JS slice semantics): {N['uraian_longer_than_160_utf16']} (codepoints: {N['uraian_longer_than_160_codepoints']}).
- Licence derivation: `resolveLicenseType` ported; rows with empty/unusable perizinan fall to `licenseForRisk`: {N['licence_rows_derived_from_risk']} of {N['per_skala_rows']} rows;
  first-row derived for {N['codes_first_row_licence_derived']} codes. Codes without per_skala: {N['codes_without_per_skala']}.
- Risk badge uses per_skala[0]; codes with >1 distinct kategori_risiko: {N['codes_multi_distinct_risk']}; row 0 below the max tier: {N['codes_first_row_risk_not_max']}.
- `formatTimeframe` rewrites: {N['timeframe_rows_rewritten']} rows. `isSourceTruncated` regex flags kewajiban {N['kewajiban_flagged_truncated']}/{N['kewajiban_items']}, persyaratan {N['persyaratan_flagged_truncated']}/{N['persyaratan_items']}.
- Ledger usage = any file under apps/mouth (ts/tsx/js/mjs/json/md/py, excluding node_modules and the ledger itself) containing the
  ledger file name or a claim id. Consumers found: {len(N['ledger_consumers_in_apps_mouth'])}; ids referenced: {len(N['ledger_ids_referenced_anywhere_in_apps_mouth'])}.
- Phantom = code string not in the corpus set (and separately not in the OSS 5-digit set).

## Key numbers
- Slice disclosures: {N['slice_disclosure_count']} codes ({','.join(N['slice_disclosure_codes'])}); not in corpus {N['slice_phantom_vs_corpus']}; not in OSS {N['slice_phantom_vs_oss']};
  _meta.count {N['slice_meta_count']}; excluded_adjacent codes {N['slice_excluded_codes']} (not in corpus {N['slice_excluded_phantom_vs_corpus']}).
- English-map phantoms: curated {N['english_curated_phantom']}, generated {N['english_generated_phantom']}. Gold phantoms: {N['gold_phantom']}.
  metadata.phantoms_dropped {N['metadata_phantoms_dropped']} still in English maps: {N['phantoms_dropped_still_in_english_maps']}; in gold: {N['phantoms_dropped_still_in_gold']}.
- Hardcoded national-closure codes: {N['national_closure_hardcoded_codes']}; concordance codes: {N['concordance_entry_codes']}, targets {N['concordance_referenced_target_codes']}.
- Dataset sidecar: fields {N['version_sidecar_fields']}; sha matches corpus: {N['version_sidecar_sha_matches_corpus']}; lastModified {N['version_sidecar_lastModified']};
  corpus metadata.version {N['corpus_metadata_version']}, total_codes {N['corpus_metadata_total_codes']} (== records: {N['corpus_metadata_total_codes_eq_len']}); corpus has lastModified: {N['corpus_metadata_has_lastModified']}.
- Raw field presence (of 1559): {json.dumps(N['raw_field_presence'])}.
- Findings: {N['findings_total']} rows; runtime_dependent=true: {N['findings_runtime_dependent']}.

| family | rows |
|---|---|
{fam_lines}

- `affected_codes` in lane_b_render_map.json: for judul/uraian entries, the codes whose rendered text differs from the corpus field;
  for other entries, codes where the rendered value is not a verbatim corpus value, or null when not statically computable.
- Gold-only mount: LicensingSection renders inside the gold branch of the page, so per_skala persyaratan/kewajiban, slice and
  dispute notices reach only {len(N['gold_branch_codes'])} pages ({','.join(N['gold_branch_codes'])}); slice codes on gold pages: {N['slice_codes_on_gold_pages']};
  dispute codes on gold pages: {N['dispute_codes_on_gold_pages']}.

## Exclusions
- Explorer (`/kbli-explorer`) and landing search render remote API data; only RUNTIME rows, no field traces.
- Test files, `apps/mouth/scripts`, Swift/Navigator apps: out of Lane B scope.
- No claim is made about deployed pages, env values, the OG route, or the API; those rows carry runtime_dependent=true.
- Regulatory correctness of any literal is not assessed; such rows are labelled TO VERIFY.
"""
(OUT / "B_METHOD.md").write_text(method, encoding="utf-8")

print(json.dumps({"findings_total": N["findings_total"], "by_family": N["findings_by_family"],
                  "runtime_dependent": N["findings_runtime_dependent"],
                  "titleId_differs": N["titleId_differs_from_judul"], "h1_differs": N["h1_differs_from_judul"],
                  "render_branch": N["render_branch_counts"], "pma_located": N["pma_verdict_verified"],
                  "cert_intel": N["certified_intel_codes"], "cert_gold": N["certified_gold_codes"],
                  "slice_phantom_corpus": N["slice_phantom_vs_corpus"], "slice_phantom_oss": N["slice_phantom_vs_oss"],
                  "en_phantom": [len(N["english_curated_phantom"]), len(N["english_generated_phantom"])],
                  "gold_phantom": len(N["gold_phantom"]), "section_null": N["section_null_from_prefix"],
                  "sidecar_sha_ok": N["version_sidecar_sha_matches_corpus"]}, indent=1))
