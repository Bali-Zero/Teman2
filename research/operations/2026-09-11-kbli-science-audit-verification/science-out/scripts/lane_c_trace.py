#!/usr/bin/env python3
"""Lane C — kbli-navigator app vs corpus vs OSS ground truth (static audit).

Reads only files inside the snapshot; writes only into science-out/.
All counts reported in kbli_app_vs_corpus.csv and C_METHOD.md are produced here.

Usage:  python3 science-out/scripts/lane_c_trace.py   (run from snapshot root or anywhere)
"""
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, OrderedDict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
APP = "apps/kbli-navigator"
OUT = os.path.join(ROOT, "science-out")
OUT_CSV = os.path.join(OUT, "kbli_app_vs_corpus.csv")
OUT_MAP = os.path.join(OUT, "data", "lane_c_render_map.json")
OUT_NUM = os.path.join(OUT, "data", "lane_c_numbers.json")

OSS_PATH = "data/source_documents/KBLI_2025_OSS_GROUND_TRUTH.json"
CORPUS_PATH = "data/source_documents/KBLI_2025_FINAL_CLEAN.json"
APP_DATA = f"{APP}/data/kbli-2025.json"
MOUTH_DATA = "apps/mouth/data/KBLI_2025_FINAL_CLEAN.json"
CERT_PATH = "data/kbli-filiera/pma-editorial-certifications.json"
JABATAN_PATH = f"{APP}/data/kepmenaker-228-jabatan-mapping.json"

F_TYPES = f"{APP}/lib/kbli-types.ts"
F_DATA = f"{APP}/lib/kbli-data.ts"
F_ENGLISH = f"{APP}/lib/kbli-english.ts"
F_GOLD = f"{APP}/lib/kbli-gold-content.ts"
F_GOLDCODES = f"{APP}/lib/kbli-gold-codes.ts"
F_CERT = f"{APP}/lib/kbli-editorial-certification.ts"
F_PMA = f"{APP}/lib/kbli-pma-disclosure.ts"
F_L4 = f"{APP}/lib/kbli-bali-l4.ts"
F_SEARCH = f"{APP}/lib/kbli-search.ts"
F_ARTICLES = f"{APP}/lib/kbli-articles.ts"
F_PAGE = f"{APP}/app/kbli/[code]/page.tsx"
F_INDEX = f"{APP}/app/kbli/page.tsx"
F_HOME = f"{APP}/app/page.tsx"
F_SEARCHPAGE = f"{APP}/app/kbli/search/page.tsx"
F_API = f"{APP}/app/api/kbli/codes/route.ts"
F_SITEMAP = f"{APP}/app/sitemap.ts"
F_CARD = f"{APP}/components/kbli/KBLICard.tsx"
F_JSONLD = f"{APP}/components/kbli/KBLIStructuredData.tsx"
F_PMABADGE = f"{APP}/components/kbli/PMABadge.tsx"
F_RISKBADGE = f"{APP}/components/kbli/RiskBadge.tsx"
F_TRANSBADGE = f"{APP}/components/kbli/TransitionBadge.tsx"
F_BALIBADGE = f"{APP}/components/kbli/BaliStatusBadge.tsx"
F_LIC = f"{APP}/components/kbli/LicensingSection.tsx"
F_CHAT = f"{APP}/components/kbli/ZantaraChat.tsx"
F_TEST = f"{APP}/lib/__tests__/kbli-data.test.ts"


def P(rel):
    return os.path.join(ROOT, rel)


def sha256(rel):
    h = hashlib.sha256()
    with open(P(rel), "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def lines_of(rel):
    with open(P(rel), encoding="utf-8") as f:
        return f.read().split("\n")


def find_line(rel, needle, start=1):
    """1-based line number of first line containing needle (from start)."""
    for i, ln in enumerate(lines_of(rel), 1):
        if i >= start and needle in ln:
            return i
    raise KeyError(f"{needle!r} not found in {rel}")


def grep_lines(rel, pattern):
    rx = re.compile(pattern)
    return [i for i, ln in enumerate(lines_of(rel), 1) if rx.search(ln)]


# =============================================================================
# Load data
# =============================================================================
oss = json.load(open(P(OSS_PATH), encoding="utf-8"))
corpus = json.load(open(P(CORPUS_PATH), encoding="utf-8"))
certs = json.load(open(P(CERT_PATH), encoding="utf-8"))
jab = json.load(open(P(JABATAN_PATH), encoding="utf-8"))

OSS5 = OrderedDict((r["kode"], r) for r in oss["data"] if r["digits"] == 5)
CORP = OrderedDict((r["kode_kbli_2025"], r) for r in corpus["data"])
assert len(OSS5) == 1559 and len(CORP) == 1559
assert set(OSS5) == set(CORP)
CODES = list(CORP)

sha_corpus = sha256(CORPUS_PATH)
sha_app = sha256(APP_DATA)
sha_mouth = sha256(MOUTH_DATA)
assert sha_corpus == sha_app == sha_mouth, "corpus copies diverge"
assert sha_corpus.startswith("3dafab17")

N = {}  # every number used in CSV / METHOD
N["snapshot_sha"] = open(P("SNAPSHOT_SHA.txt")).read().strip()
N["corpus_sha256"] = sha_corpus
N["oss_5digit"] = len(OSS5)
N["corpus_records"] = len(CORP)
N["cert_sourceDatasetSha256_matches_corpus"] = certs.get("sourceDatasetSha256") == sha_corpus

# =============================================================================
# Text alignment corpus vs OSS (needed for DECISION_INPUT recompute)
# =============================================================================
N["judul_eq_oss"] = sum(1 for c in CODES if CORP[c]["judul"] == OSS5[c]["judul_id"])
N["uraian_eq_oss"] = sum(1 for c in CODES if CORP[c]["uraian"] == OSS5[c]["uraian_id"])
N["oss_judul_en_eq_id"] = sum(1 for c in CODES if OSS5[c]["judul_en"] == OSS5[c]["judul_id"])


def rl_key(lst):
    return [(d.get("id"), d.get("uraian_id")) for d in (lst or [])]


def rl_key_corpus(lst):
    return [(d.get("id"), d.get("uraian")) for d in (lst or [])]


N["ruang_lingkup_eq_oss"] = sum(
    1 for c in CODES if rl_key(OSS5[c].get("ruang_lingkup")) == rl_key_corpus(CORP[c].get("ruang_lingkup"))
)
N["corpus_with_ruang_lingkup"] = sum(1 for c in CODES if CORP[c].get("ruang_lingkup"))
N["oss_with_ruang_lingkup"] = sum(1 for c in CODES if OSS5[c].get("ruang_lingkup"))

# =============================================================================
# Ports of kbli-data.ts
# =============================================================================
ID_LOWERCASE_WORDS = {
    "dan", "di", "yang", "untuk", "dari", "ke", "atau", "dengan", "pada", "oleh",
    "dalam", "atas", "sebagai", "serta", "melalui",
}


def to_title_case(text):
    """Port of toTitleCase (kbli-data.ts)."""
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


STOPWORDS = {
    "yang", "dan", "di", "dari", "untuk", "dengan", "pada", "ke", "atau", "ini", "itu",
    "juga", "serta", "tidak", "dalam", "oleh", "atas", "sebagai", "melalui", "adalah",
    "akan", "telah", "bukan", "belum", "sudah", "bisa", "dapat", "harus", "perlu",
    "kelompok", "mencakup", "kegiatan", "termasuk", "lihat", "usaha", "jasa", "lainnya", "lain",
}


def extract_keywords(title, description):
    """Port of extractKeywords (kbli-data.ts)."""
    combined = f"{title} {description}".lower()
    words = re.findall(r"[a-zA-Z\u00C0-\u024F]+", combined)
    uniq = []
    seen = set()
    for w in words:
        if len(w) >= 3 and w not in STOPWORDS and w not in seen:
            seen.add(w)
            uniq.append(w)
    return uniq[:20]


SECTION_PREFIX_MAP = {
    "A": ["01", "02", "03"], "B": ["05", "06", "07", "08", "09"],
    "C": [f"{i:02d}" for i in range(10, 34)], "D": ["35"], "E": ["36", "37", "38", "39"],
    "F": ["41", "42", "43"], "G": ["45", "46", "47"], "H": ["49", "50", "51", "52", "53"],
    "I": ["55", "56"], "J": ["58", "59", "60", "61", "62", "63"], "K": ["64", "65", "66"],
    "L": ["68"], "M": ["69", "70", "71", "72", "73", "74", "75"],
    "N": ["77", "78", "79", "80", "81", "82"], "O": ["84"], "P": ["85"], "Q": ["86", "87", "88"],
    "R": ["90", "91", "92", "93"], "S": ["94", "95", "96"], "T": ["97", "98"], "U": ["99"],
}
PREFIX_TO_SECTION = {p: s for s, ps in SECTION_PREFIX_MAP.items() for p in ps}
SECTION_META_IDS = list("ABCDEFGHIJKLMNOPQRSTUV")  # 22 entries incl. V


def section_from_code(code):
    return PREFIX_TO_SECTION.get(code[:2])


# ---- ENGLISH_TITLES parse ----------------------------------------------------
ENGLISH_TITLES = OrderedDict()
ENGLISH_LINES = {}
_rx_en = re.compile(r'^\s*"(\d{5})":\s*"(.*)",\s*$')
for i, ln in enumerate(lines_of(F_ENGLISH), 1):
    m = _rx_en.match(ln)
    if m:
        if m.group(1) in ENGLISH_TITLES:
            N.setdefault("english_duplicate_keys", []).append(m.group(1))
        ENGLISH_TITLES[m.group(1)] = m.group(2)
        ENGLISH_LINES[m.group(1)] = i
N["english_titles_entries"] = len(ENGLISH_TITLES)
N["english_titles_in_oss"] = sum(1 for c in ENGLISH_TITLES if c in OSS5)
english_phantom = [c for c in ENGLISH_TITLES if c not in OSS5]
N["english_titles_phantom"] = len(english_phantom)

# ---- GOLD_CODES parse (kbli-gold-codes.ts) -------------------------------------
GOLD_CODES = OrderedDict()
_rx_gc = re.compile(r'^\s*"(\d{5})",')
for i, ln in enumerate(lines_of(F_GOLDCODES), 1):
    m = _rx_gc.match(ln)
    if m:
        GOLD_CODES.setdefault(m.group(1), i)
N["gold_codes_entries"] = len(GOLD_CODES)
gold_codes_phantom = [c for c in GOLD_CODES if c not in OSS5]
N["gold_codes_phantom"] = len(gold_codes_phantom)

# ---- KBLI_GOLD_CONTENT keys + certified-entry parse -----------------------------
GOLD_KEYS = OrderedDict()
_rx_key = re.compile(r'^  "(\d{5})": \{\s*$')
gold_lines = lines_of(F_GOLD)
for i, ln in enumerate(gold_lines, 1):
    m = _rx_key.match(ln)
    if m:
        GOLD_KEYS.setdefault(m.group(1), i)
N["gold_content_entries"] = len(GOLD_KEYS)
gold_content_phantom = [c for c in GOLD_KEYS if c not in OSS5]
N["gold_content_phantom"] = len(gold_content_phantom)

# ---- GOLD_HERO_IMAGES keys (page.tsx) -------------------------------------------
HERO_KEYS = OrderedDict()
page_lines = lines_of(F_PAGE)
hero_start = find_line(F_PAGE, "const GOLD_HERO_IMAGES")
hero_end = find_line(F_PAGE, "const SECTOR_HERO")
for i in range(hero_start, hero_end):
    m = _rx_key.match(page_lines[i - 1])
    if m:
        HERO_KEYS.setdefault(m.group(1), i)
N["hero_image_entries"] = len(HERO_KEYS)
hero_phantom = [c for c in HERO_KEYS if c not in OSS5]
N["hero_image_phantom"] = len(hero_phantom)

# ---- kbli-articles exact 5-digit keys ------------------------------------------
ARTICLE_KEYS = OrderedDict()
for i, ln in enumerate(lines_of(F_ARTICLES), 1):
    m = _rx_key.match(ln)
    if m:
        ARTICLE_KEYS.setdefault(m.group(1), i)
N["article_5digit_entries"] = len(ARTICLE_KEYS)
article_phantom = [c for c in ARTICLE_KEYS if c not in OSS5]
N["article_phantom"] = len(article_phantom)

# ---- certification keys ------------------------------------------------------------
cert_canon = certs["canonicalIntel"]
cert_gold = certs["standaloneGold"]
N["cert_canonicalIntel_entries"] = len(cert_canon)
N["cert_standaloneGold_entries"] = len(cert_gold)
cert_phantom = [c for c in list(cert_canon) + list(cert_gold) if c not in OSS5]
N["cert_phantom"] = len(cert_phantom)


# =============================================================================
# Minimal JS object-literal parser (for the two certified gold entries)
# =============================================================================
class JSParser:
    def __init__(self, s):
        self.s = s
        self.i = 0

    def ws(self):
        s = self.s
        while self.i < len(s):
            c = s[self.i]
            if c in " \t\r\n":
                self.i += 1
            elif s.startswith("//", self.i):
                j = s.find("\n", self.i)
                self.i = len(s) if j < 0 else j
            elif s.startswith("/*", self.i):
                j = s.find("*/", self.i)
                self.i = len(s) if j < 0 else j + 2
            else:
                break

    def value(self):
        self.ws()
        c = self.s[self.i]
        if c == "{":
            return self.obj()
        if c == "[":
            return self.arr()
        if c == '"' or c == "'":
            return self.string(c)
        if c == "`":
            return self.template()
        m = re.match(r"-?\d+(\.\d+)?", self.s[self.i:])
        if m:
            self.i += m.end()
            t = m.group(0)
            return float(t) if "." in t else int(t)
        for lit, val in (("true", True), ("false", False), ("null", None)):
            if self.s.startswith(lit, self.i):
                self.i += len(lit)
                return val
        raise ValueError(f"unexpected {self.s[self.i:self.i+40]!r}")

    def obj(self):
        assert self.s[self.i] == "{"
        self.i += 1
        out = OrderedDict()
        while True:
            self.ws()
            if self.s[self.i] == "}":
                self.i += 1
                return out
            if self.s[self.i] in "\"'":
                key = self.string(self.s[self.i])
            else:
                m = re.match(r"[A-Za-z_$][\w$]*", self.s[self.i:])
                key = m.group(0)
                self.i += m.end()
            self.ws()
            assert self.s[self.i] == ":", self.s[self.i:self.i+20]
            self.i += 1
            out[key] = self.value()
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def arr(self):
        self.i += 1
        out = []
        while True:
            self.ws()
            if self.s[self.i] == "]":
                self.i += 1
                return out
            out.append(self.value())
            self.ws()
            if self.s[self.i] == ",":
                self.i += 1

    def _escape(self):
        c = self.s[self.i]
        self.i += 1
        table = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "v": "\v", "0": "\0"}
        if c in table:
            return table[c]
        if c == "u":
            hexs = self.s[self.i:self.i + 4]
            self.i += 4
            return chr(int(hexs, 16))
        if c == "x":
            hexs = self.s[self.i:self.i + 2]
            self.i += 2
            return chr(int(hexs, 16))
        if c == "\n":  # line continuation
            return ""
        return c  # \" \\ \' \` \$ \/ etc.

    def string(self, q):
        self.i += 1
        buf = []
        while True:
            c = self.s[self.i]
            if c == "\\":
                self.i += 1
                buf.append(self._escape())
            elif c == q:
                self.i += 1
                return "".join(buf)
            else:
                buf.append(c)
                self.i += 1

    def template(self):
        self.i += 1
        buf = []
        while True:
            c = self.s[self.i]
            if c == "\\":
                self.i += 1
                buf.append(self._escape())
            elif c == "`":
                self.i += 1
                return "".join(buf)
            elif self.s.startswith("${", self.i):
                raise ValueError("template interpolation not supported")
            else:
                buf.append(c)
                self.i += 1


def parse_gold_entry(code):
    start = GOLD_KEYS[code]
    text = "\n".join(gold_lines[start - 1:])
    text = text[text.index("{"):]
    return JSParser(text).obj()


# =============================================================================
# Ports of kbli-pma-disclosure.ts / kbli-editorial-certification.ts / kbli-bali-l4.ts
# =============================================================================
def is_js_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def public_text(v):
    return v.strip() if isinstance(v, str) and v.strip() else None


ALLOWED_PMA = {"TERBUKA", "TERBATAS", "TERTUTUP"}


def has_located_pma_tuple(rec):
    return (
        rec.get("pma_verification_status") == "located"
        and isinstance(rec.get("pma_status"), str)
        and rec.get("pma_status") in ALLOWED_PMA
        and public_text(rec.get("pma_official_basis")) is not None
        and public_text(rec.get("pma_source_vintage")) is not None
    )


def normalized_pma_status(v):
    return {"TERBUKA": "open", "TERBATAS": "restricted", "TERTUTUP": "closed"}.get(v, "unknown")


def public_pma_cap(raw):
    if raw.get("pma_cap_verified") is not True:
        return None
    cap = raw.get("pma_max_asing")
    if is_js_number(cap) and math.isfinite(cap):
        return cap
    if cap == "special" and raw.get("pma_cap_special") is True:
        return "special"
    return None


def disclose_pma_info(raw):
    if not has_located_pma_tuple(raw):
        return OrderedDict(
            status="unknown", maxForeign=None, condition=None, isPriority=False, note=None,
            source=None, verificationStatus="declared_gap", officialBasis=None, sourceVintage=None,
            capSpecial=False, capVerified=False, routeTo=None,
        )
    mf = public_pma_cap(raw)
    return OrderedDict(
        status=normalized_pma_status(raw.get("pma_status")),
        maxForeign=mf,
        condition=public_text(raw.get("pma_kondisi")),
        isPriority=raw.get("pma_prioritas") is True,
        note=public_text(raw.get("pma_nota")),
        source=public_text(raw.get("pma_source")),
        verificationStatus="located",
        officialBasis=public_text(raw.get("pma_official_basis")),
        sourceVintage=public_text(raw.get("pma_source_vintage")),
        capSpecial=mf == "special",
        capVerified=mf is not None and raw.get("pma_cap_verified") is True,
        routeTo=public_text(raw.get("pma_route_to")),
    )


def has_publishable_pma_cap(pma):
    if pma["verificationStatus"] != "located" or pma["capVerified"] is not True:
        return False
    if is_js_number(pma["maxForeign"]):
        return math.isfinite(pma["maxForeign"])
    return pma["maxForeign"] == "special" and pma["capSpecial"] is True


def stable_value(v):
    if isinstance(v, list):
        return [stable_value(x) for x in v]
    if isinstance(v, dict):
        return OrderedDict((k, stable_value(v[k])) for k in sorted(v) if v[k] is not None or True)
    return v


def js_stringify(v):
    # JSON.stringify: compact separators, non-ASCII unescaped
    return json.dumps(v, ensure_ascii=False, separators=(",", ":"))


def stable_sha256(v):
    return hashlib.sha256(js_stringify(stable_value(v)).encode("utf-8")).hexdigest()


def pma_fingerprint(pma):
    return stable_sha256({k: pma[k] for k in (
        "status", "maxForeign", "condition", "isPriority", "note", "source", "verificationStatus",
        "officialBasis", "sourceVintage", "capSpecial", "capVerified", "routeTo")})


def matches_cert(section, code, pma, content):
    if not has_publishable_pma_cap(pma) or content is None:
        return False
    c = section.get(code)
    return c is not None and c["pmaFingerprint"] == pma_fingerprint(pma) and c["contentSha256"] == stable_sha256(content)


ALLOWED_BALI = {
    "APERTO_BALI_RISCHIO_ALTO", "BLOCCATO_CLASSE_RISCHIO", "BLOCCATO_DIPENDE_SCOPE", "CHIUSO_BALI",
    "CHIUSO_BALI_PROPOSTO", "CHIUSO_MORATORIA_BALI", "CHIUSO_PMA_NO_BESAR", "CHIUSO_REGOLATORE_SETTORIALE",
    "NON_CLASSIFICABILE", "OK_or_HIGHER_RISK", "TERBATAS", "TERTUTUP",
}


def disclose_bali_l4(rec):
    if not has_located_pma_tuple(rec):
        return None
    l4 = rec.get("l4_bali")
    if not l4 or not isinstance(l4, dict):
        return None
    status, blocked, needs = l4.get("status"), l4.get("blocked"), l4.get("needs_review")
    if not isinstance(status, str) or status not in ALLOWED_BALI or not isinstance(blocked, bool) or not isinstance(needs, bool):
        return None
    conf = l4.get("confidence") if str(l4.get("confidence")) in ("HIGH", "MEDIUM", "LOW") else "MEDIUM"
    return {"status": status, "blocked": blocked, "needsReview": needs, "confidence": conf}


# =============================================================================
# Ports of PMABadge / RiskBadge / TransitionBadge / page verdict
# =============================================================================
def pma_badge(pma):
    verified = pma["verificationStatus"] == "located"
    mf = pma["maxForeign"]
    numeric = mf if is_js_number(mf) and math.isfinite(mf) else None
    marked_special = pma["capSpecial"] is True and mf == "special"
    cap_pub = verified and pma["capVerified"] is True and (numeric is not None or marked_special)
    status = pma["status"]
    if not verified:
        eff = "unknown"
    elif status == "open" and cap_pub and numeric == 0 and not marked_special:
        eff = "closed"
    else:
        eff = status
    if not verified or status == "unknown":
        suffix = None
    elif not cap_pub:
        suffix = "cap not verified"
    elif marked_special:
        suffix = "special conditions"
    elif status == "open":
        suffix = f"{numeric}% Foreign"
    elif status == "restricted" and numeric is not None:
        suffix = "closed (0%)" if numeric <= 0 else ("conditions apply" if numeric >= 100 else f"Max {numeric}%")
    else:
        suffix = None
    return eff, suffix


def parse_risk(category):
    if not category:
        return "Unknown"
    low = category.lower()
    if low == "tinggi":
        return "High"
    if "menengah" in low and "tinggi" in low:
        return "Medium-High"
    if "menengah" in low and "rendah" in low:
        return "Medium-Low"
    if low == "rendah":
        return "Low"
    return category


TRANSITION_LABELS = {"MATCH_LANGSUNG", "CODICE_RINUMERATO", "MATCH_CON_AGGREGAZIONE", "BPS_ONLY"}


def page_verdict(pma, bali):
    verified = pma["verificationStatus"] == "located"
    bali = bali if verified else None
    bali_blocked = bool(bali and bali["blocked"] is True)
    nationally_closed = verified and not (
        pma["capVerified"] is True and pma["capSpecial"] is True and pma["maxForeign"] == "special"
    ) and (pma["status"] == "closed" or (pma["capVerified"] and pma["maxForeign"] == 0))
    bali_missing = verified and not nationally_closed and bali is None
    if not verified:
        return "NOT_VERIFIED"
    if nationally_closed:
        return "CLOSED_NATIONAL"
    if bali_missing:
        return "BALI_MISSING"
    if bali_blocked:
        return "BALI_BLOCKED"
    return "BALI_NOT_BLOCKED"


# =============================================================================
# Per-code recompute (corpus input) and OSS-input recompute for text-keyed rules
# =============================================================================
title_case_changed = []
title_en_curated = []
h1_not_judul = []
uraian_not_lead = []  # detail page: uraian replaced by gold or intel_2026
gold_certified = []
intel_certified = []
tiers = Counter()
pma_status_out = Counter()
badge_out = Counter()
verdict_out = Counter()
risk_badge_out = Counter()
bali_badge_shown = []
no_transition_badge = []
multi_risk = []
no_per_skala = []
section_null = []
desc_gt150 = sum(1 for c in CODES if len(CORP[c]["uraian"]) > 150)
desc_gt200 = sum(1 for c in CODES if len(CORP[c]["uraian"]) > 200)
desc_gt500 = sum(1 for c in CODES if len(CORP[c]["uraian"]) > 500)
kw_changes_oss = 0
title_changes_oss = 0
meta_changes_oss = 0
jsonld_changes_oss = 0
penalty_changes_oss = 0
section_cnt = Counter()

gold_entries = {}
for c in cert_gold:
    if c in GOLD_KEYS:
        gold_entries[c] = parse_gold_entry(c)

for c in CODES:
    raw = CORP[c]
    o = OSS5[c]
    # --- title pipeline
    title_id = to_title_case(raw["judul"])
    if title_id != raw["judul"]:
        title_case_changed.append(c)
    if c in ENGLISH_TITLES:
        title_en_curated.append(c)
        title_en = ENGLISH_TITLES[c]
    else:
        title_en = title_id
    if title_en != raw["judul"]:
        h1_not_judul.append(c)
    # OSS-input recompute of text-keyed rules
    if to_title_case(o["judul_id"]) != title_id:
        title_changes_oss += 1
    if extract_keywords(o["judul_id"], o["uraian_id"]) != extract_keywords(raw["judul"], raw["uraian"]):
        kw_changes_oss += 1
    if o["uraian_id"][:150] != raw["uraian"][:150]:
        meta_changes_oss += 1
    if o["uraian_id"][:200] != raw["uraian"][:200]:
        jsonld_changes_oss += 1
    if (len(o["uraian_id"]) > 500) != (len(raw["uraian"]) > 500) or (
        max(0, (len(o["uraian_id"]) - 500) // 100) != max(0, (len(raw["uraian"]) - 500) // 100)
    ):
        penalty_changes_oss += 1
    # --- section
    sec = section_from_code(c)
    if sec is None:
        section_null.append(c)
    else:
        section_cnt[sec] += 1
    # --- PMA / certification
    pma = disclose_pma_info(raw)
    pma_status_out[pma["status"]] += 1
    intel_ok = matches_cert(cert_canon, c, pma, raw.get("intel_2026"))
    gold_ok = matches_cert(cert_gold, c, pma, gold_entries.get(c))
    if intel_ok:
        intel_certified.append(c)
    if gold_ok:
        gold_certified.append(c)
    tier = "gold" if gold_ok else ("silver" if c in ENGLISH_TITLES else "bronze")
    tiers[tier] += 1
    if gold_ok or (intel_ok and raw["intel_2026"].get("whatItMeans")):
        uraian_not_lead.append(c)
    badge_out[pma_badge(pma)] += 1
    bali = disclose_bali_l4(raw)
    if bali is not None:
        bali_badge_shown.append(c)
    verdict_out[page_verdict(pma, bali)] += 1
    # --- risk
    ps = raw.get("per_skala") or []
    if not ps:
        no_per_skala.append(c)
        risk_badge_out["(no badge)"] += 1
    else:
        risk_badge_out[parse_risk(ps[0].get("kategori_risiko"))] += 1
        if len({e.get("kategori_risiko") for e in ps}) > 1:
            multi_risk.append(c)
    if raw.get("status_mapping") not in TRANSITION_LABELS:
        no_transition_badge.append(c)

N.update(
    title_case_changed=len(title_case_changed),
    title_en_curated=len(title_en_curated),
    h1_not_judul=len(h1_not_judul),
    h1_eq_judul=len(CODES) - len(h1_not_judul),
    uraian_not_lead_on_detail=len(uraian_not_lead),
    gold_certified=len(gold_certified),
    gold_certified_codes=gold_certified,
    intel_certified=len(intel_certified),
    tiers=dict(tiers),
    pma_status_after_disclosure=dict(pma_status_out),
    pma_located=sum(1 for c in CODES if CORP[c].get("pma_verification_status") == "located"),
    pma_declared_gap=sum(1 for c in CODES if CORP[c].get("pma_verification_status") == "declared_gap"),
    pma_badge_outcomes={f"{k[0]}|{k[1]}": v for k, v in badge_out.items()},
    page_verdict_outcomes=dict(verdict_out),
    bali_badge_shown=len(bali_badge_shown),
    corpus_with_l4_bali=sum(1 for c in CODES if isinstance(CORP[c].get("l4_bali"), dict)),
    risk_badge_outcomes=dict(risk_badge_out),
    multi_risk_codes=len(multi_risk),
    no_per_skala=len(no_per_skala),
    no_transition_badge=no_transition_badge,
    section_null=section_null,
    sections_with_codes=len(section_cnt),
    section_meta_entries=len(SECTION_META_IDS),
    sektor_id_null=sum(1 for c in CODES if CORP[c].get("sektor_id") is None),
    sektor_id_values=sorted({CORP[c].get("sektor_id") for c in CODES if CORP[c].get("sektor_id")}),
    desc_gt150=desc_gt150,
    desc_gt200=desc_gt200,
    desc_gt500=desc_gt500,
    oss_recompute_changes=dict(
        toTitleCase=title_changes_oss, extractKeywords=kw_changes_oss,
        metadata_slice150=meta_changes_oss, jsonld_slice200=jsonld_changes_oss,
        search_length_penalty=penalty_changes_oss,
    ),
    intel_keys_in_corpus=sorted({k for c in CODES for k in (CORP[c].get("intel_2026") or {})}),
    per_skala_keys=dict(Counter(k for c in CODES for e in (CORP[c].get("per_skala") or []) for k in e)),
    corpus_record_keys=dict(Counter(k for c in CODES for k in CORP[c])),
    pma_max_asing_types=dict(Counter(type(CORP[c].get("pma_max_asing")).__name__ for c in CODES)),
)
# fingerprint-only check for standalone gold (content hash needs parsed entry)
N["standaloneGold_pma_fingerprint_match"] = {
    c: cert_gold[c]["pmaFingerprint"] == pma_fingerprint(disclose_pma_info(CORP[c])) for c in cert_gold if c in CORP
}
N["standaloneGold_content_sha_match"] = {
    c: cert_gold[c]["contentSha256"] == stable_sha256(gold_entries[c]) for c in gold_entries
}

# "1,563" claim ledger
claim_1563 = []
for rel in (F_TYPES, F_DATA, F_GOLDCODES, F_PAGE, F_INDEX, F_HOME, F_SITEMAP):
    for ln in grep_lines(rel, r"1,563|\b1563\b"):
        claim_1563.append((rel, ln))
N["claim_1563_occurrences"] = len(claim_1563)
N["claim_22_sectors_lines"] = [(F_HOME, ln) for ln in grep_lines(F_HOME, r"22 sectors")]
N["test_expects_1505_gaps"] = bool(grep_lines(F_TEST, r"1505"))

# =============================================================================
# Jabatan mapping analysis (kepmenaker-228-jabatan-mapping.json)
# =============================================================================
jab_rows = []  # (jabatan_name_en, isco, category_id, code)
total_jabatan = 0
cat_code_refs = []
for cat in jab["categories"]:
    cat_codes = list(cat.get("gold_codes") or [])
    cat_code_refs.extend(cat_codes)
    jabs = []
    for ss in cat.get("sub_sectors") or []:
        for j in ss.get("jabatan") or []:
            jabs.append(j)
    total_jabatan += len(jabs)
    for code in cat_codes:
        if code not in OSS5:
            for j in jabs:
                jab_rows.append((j.get("name_en") or j.get("name_id"), j.get("isco"), cat["id"], code))
gcm_codes = [k for k in jab["gold_code_mapping"] if re.fullmatch(r"\d{5}", k)]
ki_codes = []
for k in ("most_restrictive_sectors", "most_permissive_sectors"):
    for e in jab["key_insights"].get(k, []):
        v = e.get("gold_codes_affected")
        if isinstance(v, list):  # some entries hold an int count instead of a list
            ki_codes.extend(v)
all_refs = cat_code_refs + gcm_codes + ki_codes
distinct_refs = sorted(set(all_refs))
absent_oss = sorted(c for c in distinct_refs if c not in OSS5)
absent_corpus = sorted(c for c in distinct_refs if c not in CORP)
N["jabatan_total"] = total_jabatan
N["jabatan_total_declared"] = sum(c.get("total_jabatan", 0) for c in jab["categories"])
N["jabatan_code_refs_total"] = len(all_refs)
N["jabatan_code_refs_categories"] = len(cat_code_refs)
N["jabatan_code_refs_gold_code_mapping"] = len(gcm_codes)
N["jabatan_code_refs_key_insights"] = len(ki_codes)
N["jabatan_distinct_codes"] = len(distinct_refs)
N["jabatan_absent_oss"] = absent_oss
N["jabatan_absent_corpus"] = absent_corpus
N["jabatan_phantom_pairs"] = len(jab_rows)
N["jabatan_categories_with_phantom"] = sorted({r[2] for r in jab_rows})
N["jabatan_gcm_phantom"] = sorted(c for c in gcm_codes if c not in OSS5)
N["jabatan_file_imported_by_ts"] = False  # grep in METHOD: no import outside data/*.md

# =============================================================================
# CSV rows
# =============================================================================
COLS = ["finding_id", "family", "code", "file", "line", "claim", "confidence", "runtime_dependent", "suggested_fix"]
rows = []
seq = Counter()
ABBR = {
    "FIELD_TRACE": "TRACE", "SCHEMA_DIVERGENCE": "SCHEMA", "HEURISTIC": "HEUR", "HARDCODED": "HARD",
    "PHANTOM_CODE": "PHANTOM", "CLAIM_LEDGER": "CLAIM", "VERSION_MISMATCH": "VER", "JABATAN_PHANTOM": "JAB",
    "DECISION_INPUT": "DEC", "RUNTIME": "RT",
}


def add(family, file, line, claim, conf, fix, code="", rt=False):
    assert family in ABBR
    assert len(claim) < 200, claim
    assert code == "" or re.fullmatch(r"\d{5}", code), code
    for q in re.findall(r'"([^"]*)"', claim + fix):
        assert len(q) <= 80
    seq[family] += 1
    rows.append(OrderedDict(
        finding_id=f"C-{ABBR[family]}-{seq[family]:03d}", family=family, code=code, file=file, line=str(line),
        claim=claim, confidence=f"{conf:.2f}", runtime_dependent="true" if rt else "false", suggested_fix=fix,
    ))


L = lambda rel, needle, start=1: find_line(rel, needle, start)

# ---- (a) FIELD_TRACE: rendered field -> corpus field ------------------------------
add("FIELD_TRACE", F_DATA, L(F_DATA, "const code = raw.kode_kbli_2025"),
    "KBLICode.code <- corpus kode_kbli_2025 verbatim; equals OSS kode for all 1559.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "const titleId = toTitleCase(raw.judul)"),
    f"KBLICode.titleId <- toTitleCase(corpus judul); NOT verbatim: {N['title_case_changed']}/1559 codes differ from judul.", 1.0,
    "Render corpus judul verbatim or store the title-cased form as a separate display field.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "const titleEn = ENGLISH_TITLES[code] ?? titleId"),
    f"KBLICode.titleEn <- ENGLISH_TITLES (OTHER_FILE kbli-english.ts) for {N['title_en_curated']} codes, else titleId; OSS judul_en==judul_id.", 1.0,
    "Label titleEn as an editorial translation; OSS provides no English judul.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "description: raw.uraian"),
    "KBLICode.description <- corpus uraian verbatim (equals OSS uraian_id for 1559/1559).", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "keywords: extractKeywords(raw.judul, raw.uraian)"),
    "KBLICode.keywords <- HEURISTIC extractKeywords(judul, uraian): lowercase, stopword-filtered, first 20; search-only.", 1.0,
    "None if search-only; document as derived.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "const section = getSectionFromCode(code)"),
    f"KBLICode.section <- HEURISTIC 2-digit prefix map, not corpus sektor_id; sektor_id is null for {N['sektor_id_null']} codes.", 1.0,
    "Document that section letter is derived from the code prefix; sektor_id is unused.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "sectionName: sectionMeta?.nameEn"),
    "KBLICode.sectionName <- HARDCODED SECTION_META in kbli-data.ts; no corpus or OSS source.", 1.0,
    "Cite the BPS section names source in SECTION_META.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "scales: entry.skala_usaha"),
    "KBLICode.licensing[] <- corpus per_skala[] (skala_usaha, kategori_risiko, perizinan, ...). ENRICHMENT; OSS has no per_skala.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "mappingStatus: raw.status_mapping"),
    "KBLICode.transition <- corpus status_mapping, pp28_sources, kbli_2020_source, mapping_note, aggregation_note. ENRICHMENT.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_PMA, L(F_PMA, "export function disclosePmaInfo"),
    f"KBLICode.pma <- corpus pma_* fields gated by pma_verification_status==located ({N['pma_located']} codes); else all-unknown.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "intel_2026: canonicalIntelCertified"),
    f"KBLICode.intel_2026 <- corpus intel_2026 only when hash-certified ({N['intel_certified']} codes); zantaraOpener replaced by neutral text.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_L4, L(F_L4, "const disclosed = discloseBaliL4Record(rec)"),
    f"BaliL4 <- corpus l4_bali re-read from the same JSON, gated by located PMA tuple; {N['bali_badge_shown']} of 1559 disclosed.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_PAGE, L(F_PAGE, "{kbli.titleEn}", 9400),
    "Detail page h1 renders titleEn (curated English or title-cased judul); corpus judul verbatim only as subtitle after title-case.", 1.0,
    "Render corpus judul verbatim in the subtitle; mark h1 as translation.")
add("FIELD_TRACE", F_PAGE, L(F_PAGE, "{kbli.titleId}", 9400),
    f"Detail page subtitle renders titleId = toTitleCase(judul); differs from corpus judul for {N['title_case_changed']}/1559.", 1.0,
    "Use raw.judul for the Indonesian subtitle.")
add("FIELD_TRACE", F_PAGE, L(F_PAGE, "{kbli.description}", 9900),
    f"Detail page renders uraian verbatim only when no gold and no certified intel_2026; {N['uraian_not_lead_on_detail']}/1559 codes show editorial prose instead.", 1.0,
    "Always render corpus uraian (e.g. collapsible) alongside editorial prose.")
add("FIELD_TRACE", F_CARD, L(F_CARD, "{code.titleEn}"),
    "KBLICard renders titleEn (h3) and titleId (p); same non-verbatim pipeline as detail page.", 1.0,
    "See titleId/titleEn rows.")
add("FIELD_TRACE", F_PAGE, L(F_PAGE, "kbli.description.slice(0, 150)"),
    f"generateMetadata description <- uraian.slice(0,150)+'...' (HEURISTIC truncation); {N['desc_gt150']}/1559 uraian exceed 150 chars.", 1.0,
    "Truncate at word boundary and omit ellipsis when not truncated.")
add("FIELD_TRACE", F_JSONLD, L(F_JSONLD, "code.description.slice(0, 200)"),
    f"JSON-LD description <- uraian.slice(0,200) (HEURISTIC truncation); {N['desc_gt200']}/1559 uraian exceed 200 chars.", 1.0,
    "Document truncation or emit full uraian in structured data.")
add("FIELD_TRACE", F_SEARCH, L(F_SEARCH, "const desc = normalize(code.description)"),
    f"Search scores titleEn, titleId, keywords, description; length penalty applies to {N['desc_gt500']} codes with uraian > 500 chars.", 1.0,
    "None; search-only.")
add("FIELD_TRACE", F_PAGE, L(F_PAGE, "title: kbli.titleEn,"),
    "ZantaraChat context title <- titleEn, not corpus judul.", 1.0,
    "Pass judul verbatim in chat context alongside titleEn.")
add("FIELD_TRACE", F_DATA, L(F_DATA, "const raw: KBLIRawDataFile = JSON.parse"),
    "Loader parses raw.data[] without filtering on digits; corpus has 1559 5-digit records, all in OSS.", 1.0,
    "None; positive trace.")
add("FIELD_TRACE", F_DATA, 1,
    f"VERDICT: rendered judul is NOT verbatim ({N['h1_not_judul']} h1, {N['title_case_changed']} subtitle); uraian verbatim except {N['uraian_not_lead_on_detail']} detail pages.", 1.0,
    "See lane_c_render_map.json for affected code lists.")

# ---- (a) SCHEMA_DIVERGENCE -----------------------------------------------------------
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "export interface KBLIRawCode"),
    f"KBLIRawCode omits corpus fields ruang_lingkup ({N['corpus_with_ruang_lingkup']} codes), bps_2020_ancestors, _l1_source, _l2_source, per_skala_legacy; never rendered.", 1.0,
    "Type and render ruang_lingkup; it is one of only four OSS fields.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "sektor_id: string | null"),
    f"sektor_id typed but never read; values are OSS sector ids like I.G ({len(N['sektor_id_values'])} distinct), not letters A-U.", 1.0,
    "Either use sektor_id or drop it from the type.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "pb_umku: string[];"),
    f"KBLIScaleEntry requires pb_umku, parameter, sanksi_*; present in only {N['per_skala_keys'].get('pb_umku', 0)} of {sum(1 for c in CODES for _ in CORP[c].get('per_skala') or [])} per_skala entries.", 1.0,
    "Mark these fields optional in KBLIScaleEntry.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "scope_index") if grep_lines(F_TYPES, "scope_index") else L(F_TYPES, "export interface KBLIScaleEntry"),
    f"per_skala entries carry scope_index/scope_uraian ({N['per_skala_keys'].get('scope_uraian', 0)} entries) linking to ruang lingkup; type and UI ignore them.", 1.0,
    "Expose scope_uraian so per-scale risk is shown per ruang lingkup.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "status_mapping: KBLIMappingStatus"),
    "status_mapping, pp28_sources, pma_max_asing, pma_kondisi, pma_prioritas, pma_nota typed required; absent on 1 record.", 1.0,
    "Mark optional; loader already defaults pp28_sources ?? [].", code="01122")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "pma_max_asing: number | \"special\""),
    f"pma_max_asing typed number|special; corpus types: {N['pma_max_asing_types']}.", 1.0,
    "Add null/undefined to the type.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "intel_2026?: {"),
    "intel_2026 type lists 6 keys; corpus also has editorial, whoThisIsFor, tkaInfo, coverImage, _l3_regen, _l3_gap_disclosure (ignored).", 1.0,
    "Extend the type or document ignored keys.")
add("SCHEMA_DIVERGENCE", F_TYPES, L(F_TYPES, "total_codes: number;"),
    "KBLIRawDataFile.metadata type omits corpus metadata keys l4_bali_injected, l1_realign, pma_gov_fix_2026_06_27 etc.; version never checked.", 1.0,
    "Assert metadata.version at load time.")
add("SCHEMA_DIVERGENCE", F_DATA, L(F_DATA, "const licensing: KBLILicenseByScale[]"),
    "Loader renames per_skala keys to camelCase and drops pb_umku, parameter, sanksi_*, jangka_waktu_source, scope_uraian.", 1.0,
    "Document dropped keys.")
add("SCHEMA_DIVERGENCE", F_CERT, L(F_CERT, "zantaraOpener: neutralKbliChatOpenerText(code)"),
    "Corpus intel_2026.zantaraOpener is always overwritten with a HARDCODED neutral opener; corpus value never shown.", 1.0,
    "None if intentional; document.")
add("SCHEMA_DIVERGENCE", F_L4, L(F_L4, "? (l4.confidence as BaliL4"),
    "l4_bali.confidence outside HIGH/MEDIUM/LOW defaults to MEDIUM; l4_bali.verdict, rule, verdict_state ignored.", 1.0,
    "Reject instead of defaulting confidence.")
add("SCHEMA_DIVERGENCE", F_DATA, L(F_DATA, "V: {"),
    f"SECTION_META has 22 entries (A-V) but V has no prefixes; only {N['sections_with_codes']} sections receive codes.", 1.0,
    "Drop V or document.")

# ---- HEURISTIC -----------------------------------------------------------------------
add("HEURISTIC", F_DATA, L(F_DATA, "function toTitleCase(text: string)"),
    f"toTitleCase lowercases then capitalises words except 15 stop-words; changes {N['title_case_changed']}/1559 judul (acronyms, hyphens, parentheses).", 1.0,
    "Do not transform judul; OSS judul_id is already mixed case.")
add("HEURISTIC", F_DATA, L(F_DATA, "function assignTier(code: string"),
    f"Tier: gold={N['tiers'].get('gold', 0)}, silver={N['tiers'].get('silver', 0)} (has ENGLISH_TITLES), bronze={N['tiers'].get('bronze', 0)}; silver reflects translation presence, not data quality.", 1.0,
    "Rename tier or base it on verified content.")
add("HEURISTIC", F_DATA, L(F_DATA, "export function getRelatedCodes"),
    "Related codes = same 3-digit prefix then same section; ignores OSS hierarchy records (2/3/4-digit) present in ground truth.", 1.0,
    "Use OSS 4-digit parent from ground truth.")
add("HEURISTIC", F_RISKBADGE, L(F_RISKBADGE, "function parseRisk"),
    "RiskBadge maps kategori_risiko by substring (menengah+tinggi etc.); all 4 corpus values map cleanly.", 1.0,
    "None.")
add("HEURISTIC", F_LIC, L(F_LIC, "obl.toLowerCase().includes(\"sertifikat laik sehat\")"),
    "LicensingSection adds English glosses by substring match on kewajiban text (enrichment field, not OSS).", 1.0,
    "None; document.")

# ---- HARDCODED -----------------------------------------------------------------------
add("HARDCODED", F_DATA, L(F_DATA, "const SECTION_META"),
    "TO VERIFY: SECTION_META nameId/nameEn strings are hardcoded; OSS ground truth has no 1-digit section records to check them against.", 0.9,
    "Cite BPS section names source or load from ground truth.")
add("HARDCODED", F_DATA, L(F_DATA, "const SECTION_PREFIX_MAP"),
    f"Section letter derived from a hardcoded 2-digit prefix map; {len(N['section_null'])} corpus codes fall outside the map.", 1.0,
    "None; verify map against BPS structure.")
add("HARDCODED", F_LIC, L(F_LIC, "value: \"BKPM / OSS\""),
    "KeyFacts Authority is hardcoded to BKPM / OSS; corpus per_skala.kewenangan (mapped to licensing.authority) is ignored here.", 1.0,
    "Render licensing[0].authority.")
add("HARDCODED", F_ENGLISH, 7,
    f"ENGLISH_TITLES: {N['english_titles_entries']} curated English titles with no source citation; OSS judul_en equals judul_id for all 1559.", 1.0,
    "Add provenance note; label as Bali Zero translation in UI.")
add("HARDCODED", F_L4, 3,
    "TO VERIFY: header comment cites a Bali moratorium date and Gubernur letter number; not checkable from snapshot data.", 0.5,
    "Move regulatory citations into the data file with a source field.")
add("HARDCODED", F_JSONLD, L(F_JSONLD, "url: \"https://bps.go.id\""),
    "JSON-LD cites bps.go.id as source; the app data actually comes from the corpus (OSS-realigned), not directly from BPS.", 1.0,
    "Cite corpus provenance (OSS gw.oss.go.id) in structured data.")
add("HARDCODED", F_BALIBADGE, L(F_BALIBADGE, "const config: Record<"),
    "BaliStatusBadge maps 12 l4_bali status enums to hardcoded English labels; enum values are Italian and not OSS.", 1.0,
    "None; document enum provenance.")

# ---- CLAIM_LEDGER / VERSION_MISMATCH -------------------------------------------------
for rel, ln in claim_1563:
    add("CLAIM_LEDGER", rel, ln,
        "States 1,563 KBLI codes; corpus and OSS 5-digit count is 1559 (metadata.total_codes 1559).", 1.0,
        "Replace with 1,559 or compute from data.")
for rel, ln in N["claim_22_sectors_lines"]:
    add("CLAIM_LEDGER", rel, ln,
        f"States 22 sectors; SECTION_META has 22 entries but only {N['sections_with_codes']} sections have codes and are listed.", 1.0,
        "Say 21 sectors or compute from data.")
add("CLAIM_LEDGER", F_TEST, L(F_TEST, "1505"),
    f"Test expects 1,505 PMA gaps; corpus has declared_gap={N['pma_declared_gap']}, located={N['pma_located']} (matches).", 1.0,
    "None; positive check.")
add("CLAIM_LEDGER", F_TEST, L(F_TEST, "assert.deepEqual(goldCodes"),
    f"Test expects gold codes 47111, 65121; recompute of hash gate yields {N['gold_certified_codes']}.", 1.0,
    "None; positive check.")
add("CLAIM_LEDGER", F_TYPES, 3,
    "TO VERIFY: header says source BPS 7/2025 + PP28/2025; corpus metadata.source string says PP28_2024. Labels disagree.", 0.7,
    "Align the regulation label with the dataset metadata after checking the source.")
add("VERSION_MISMATCH", F_DATA, L(F_DATA, "Get all 1,563 KBLI codes"),
    "Loader docstring and type header describe a 1,563-code dataset; shipped data/kbli-2025.json has 1559 (sha256 3dafab17...).", 1.0,
    "Update comments; add a load-time count assertion.")
add("VERSION_MISMATCH", "data/kbli-filiera/pma-editorial-certifications.json", 1,
    f"Certification sourceDatasetSha256 matches shipped corpus sha256: {N['cert_sourceDatasetSha256_matches_corpus']}.", 1.0,
    "None; positive check.")
add("VERSION_MISMATCH", F_GOLD, 44946 if len(gold_lines) >= 44946 else len(gold_lines),
    "Gold content ends with an opaque version stamp comment; no link to corpus metadata.version v10.0-L2-oss-risk.", 1.0,
    "Record the corpus version the gold content was verified against.")

# ---- PHANTOM_CODE ------------------------------------------------------------------------
for c in english_phantom:
    add("PHANTOM_CODE", F_ENGLISH, ENGLISH_LINES[c], "ENGLISH_TITLES key not among 1559 OSS 5-digit codes.", 1.0, "Remove or remap.", code=c)
for c in gold_codes_phantom:
    add("PHANTOM_CODE", F_GOLDCODES, GOLD_CODES[c], "GOLD_CODES entry not among 1559 OSS codes (set is not imported by app code).", 1.0, "Remove.", code=c)
for c in gold_content_phantom:
    add("PHANTOM_CODE", F_GOLD, GOLD_KEYS[c], "KBLI_GOLD_CONTENT key not among 1559 OSS codes.", 1.0, "Remove or remap.", code=c)
for c in hero_phantom:
    add("PHANTOM_CODE", F_PAGE, HERO_KEYS[c], "GOLD_HERO_IMAGES key not among 1559 OSS codes.", 1.0, "Remove.", code=c)
for c in article_phantom:
    add("PHANTOM_CODE", F_ARTICLES, ARTICLE_KEYS[c], "KBLI_ARTICLE_MAP 5-digit key not among 1559 OSS codes.", 1.0, "Remove.", code=c)
for c in cert_phantom:
    add("PHANTOM_CODE", "data/kbli-filiera/pma-editorial-certifications.json", 1, "Certification key not among 1559 OSS codes.", 1.0, "Remove.", code=c)
dropped = corpus["metadata"].get("l1_realign", {}).get("phantoms_dropped", [])
still_used = sorted(set(dropped) & (set(english_phantom) | set(hero_phantom) | set(gold_content_phantom) | set(gold_codes_phantom)))
N["l1_dropped_phantoms_still_in_app"] = still_used
add("PHANTOM_CODE", F_ENGLISH, 7,
    f"{len(still_used)} of {len(dropped)} codes in corpus metadata.l1_realign.phantoms_dropped ({', '.join(still_used)}) still appear in ENGLISH_TITLES / GOLD_HERO_IMAGES.", 1.0,
    "Purge codes dropped by the L1 realign from all app-side lookup tables.")
add("PHANTOM_CODE", F_ENGLISH, 7,
    f"Summary: ENGLISH_TITLES {N['english_titles_phantom']}, GOLD_CODES {N['gold_codes_phantom']}, GOLD_CONTENT {N['gold_content_phantom']}, HERO {N['hero_image_phantom']}, ARTICLES {N['article_phantom']}, CERTS {N['cert_phantom']} phantom keys.", 1.0,
    "See individual rows.")

# ---- (b) JABATAN_PHANTOM -----------------------------------------------------------------
for name, isco, cat_id, code in jab_rows:
    add("JABATAN_PHANTOM", JABATAN_PATH, 1,
        f"jabatan (ISCO {isco}) in category {cat_id} maps via gold_codes to a code absent from OSS 2025.", 1.0,
        "Remove or remap the category gold_codes entry.", code=code)
for c in N["jabatan_gcm_phantom"]:
    add("JABATAN_PHANTOM", JABATAN_PATH, 1, "gold_code_mapping key absent from OSS 2025.", 1.0, "Remove or remap.", code=c)
add("JABATAN_PHANTOM", JABATAN_PATH, 1,
    f"Summary: jabatan listed={N['jabatan_total']} (declared total_jabatan={N['jabatan_total_declared']}), code refs={N['jabatan_code_refs_total']}, distinct={N['jabatan_distinct_codes']}, absent OSS={len(absent_oss)}, absent corpus={len(absent_corpus)}.", 1.0,
    "Schema: categories[].gold_codes <-> categories[].sub_sectors[].jabatan; gold_code_mapping{code}; key_insights.")
add("JABATAN_PHANTOM", JABATAN_PATH, 1,
    f"File enumerates only {N['jabatan_total']} jabatan explicitly while category total_jabatan sums to {N['jabatan_total_declared']}; the mapping is a sample, not the full Kepmenaker list.", 1.0,
    "Label the file as partial or complete the jabatan lists.")
add("JABATAN_PHANTOM", JABATAN_PATH, 1,
    "kepmenaker-228-jabatan-mapping.json is not imported by any .ts/.tsx in the snapshot; tkaInfo is embedded in kbli-gold-content.ts.", 1.0,
    "Document the file as an offline research input or wire it in.")

# ---- (c) DECISION_INPUT --------------------------------------------------------------
add("DECISION_INPUT", F_DATA, L(F_DATA, "const titleId = toTitleCase(raw.judul)"),
    f"Text rule toTitleCase(judul): recomputed with OSS judul_id -> {N['oss_recompute_changes']['toTitleCase']}/1559 outcomes change (judul==judul_id).", 1.0,
    "None.")
add("DECISION_INPUT", F_DATA, L(F_DATA, "keywords: extractKeywords(raw.judul, raw.uraian)"),
    f"Text rule extractKeywords: recomputed with OSS judul_id/uraian_id -> {N['oss_recompute_changes']['extractKeywords']}/1559 change.", 1.0,
    "None.")
add("DECISION_INPUT", F_PAGE, L(F_PAGE, "kbli.description.slice(0, 150)"),
    f"Text rule metadata slice(0,150) and JSON-LD slice(0,200): OSS uraian_id recompute -> {N['oss_recompute_changes']['metadata_slice150']} and {N['oss_recompute_changes']['jsonld_slice200']} change.", 1.0,
    "None.")
add("DECISION_INPUT", F_SEARCH, L(F_SEARCH, "if (code.description.length > 500)"),
    f"Text rule search length penalty (uraian > 500): OSS recompute -> {N['oss_recompute_changes']['search_length_penalty']}/1559 change.", 1.0,
    "None.")
add("DECISION_INPUT", F_PMABADGE, L(F_PMABADGE, "const effectiveStatus ="),
    f"PMABadge keyed on pma_status/pma_max_asing/pma_cap_* (ENRICHMENT, no OSS counterpart); outcomes: unknown {N['pma_badge_outcomes'].get('unknown|None', 0)}/1559.", 1.0,
    "None; OSS has no PMA field.")
add("DECISION_INPUT", F_PMA, L(F_PMA, "export function hasLocatedPmaTuple"),
    f"PMA disclosure gate keyed on pma_verification_status, pma_official_basis, pma_source_vintage (ENRICHMENT); located={N['pma_located']}.", 1.0,
    "None; OSS has no PMA field.")
add("DECISION_INPUT", F_PAGE, L(F_PAGE, "const nationallyClosed ="),
    f"Page verdict banner keyed on pma.* and l4_bali.blocked (ENRICHMENT); outcomes {N['page_verdict_outcomes']}.", 1.0,
    "None; OSS has no PMA or Bali field.")
add("DECISION_INPUT", F_L4, L(F_L4, "export function discloseBaliL4Record"),
    f"BaliStatusBadge keyed on l4_bali.status/blocked/needs_review (ENRICHMENT); shown for {N['bali_badge_shown']} of {N['corpus_with_l4_bali']} codes carrying l4_bali.", 1.0,
    "None; OSS has no Bali field.")
add("DECISION_INPUT", F_PAGE, L(F_PAGE, "<RiskBadge category={kbli.licensing[0].riskCategory}"),
    f"RiskBadge keyed on per_skala[0].kategori_risiko (ENRICHMENT); {N['multi_risk_codes']} codes have >1 distinct risk across per_skala, {N['no_per_skala']} have none.", 1.0,
    "Show risk range or per-scope risk instead of first entry only.")
add("DECISION_INPUT", F_TRANSBADGE, L(F_TRANSBADGE, "const config = labels[status]"),
    f"TransitionBadge keyed on status_mapping (ENRICHMENT, corpus-only crosswalk); {len(N['no_transition_badge'])} code(s) render no badge.", 1.0,
    "None; OSS has no 2020 crosswalk.", code=N["no_transition_badge"][0] if len(N["no_transition_badge"]) == 1 else "")
add("DECISION_INPUT", F_CERT, L(F_CERT, "function matchesCertification"),
    f"Editorial gate keyed on sha256 of pma tuple + content (ENRICHMENT); certified intel {N['intel_certified']}/{N['cert_canonicalIntel_entries']}, gold {N['gold_certified']}/{N['cert_standaloneGold_entries']}.", 1.0,
    "None; positive recompute.")
add("DECISION_INPUT", F_SEARCHPAGE, L(F_SEARCHPAGE, "codes.filter((c) => c.pma.status === pmaFilter)"),
    "Search PMA/transition filters keyed on pma.status and transition.mappingStatus (ENRICHMENT).", 1.0,
    "None; OSS has no counterpart.")

# ---- (d) RUNTIME -------------------------------------------------------------------
add("RUNTIME", F_DATA, L(F_DATA, "const fallbackPath = path.resolve("),
    "Loader falls back to ../nuzantara/source_documents/KBLI_2025_FINAL_CLEAN.json if data/kbli-2025.json is absent at build; cannot observe which was used.", 1.0,
    "Remove fallback or log the resolved path into the build.", rt=True)
add("RUNTIME", F_L4, L(F_L4, "const candidates = ["),
    "Bali L4 loader probes 3 filesystem paths and accepts data.records / kode_kbli / kode / code keys; build-time environment dependent.", 1.0,
    "Load from the single shipped JSON only.", rt=True)
add("RUNTIME", F_SEARCHPAGE, L(F_SEARCHPAGE, "fetch(\"/api/kbli/codes\")"),
    "Search page fetches /api/kbli/codes at runtime (own API route serving getAllCodes()); response cached 86400s.", 1.0,
    "None; note it is the same loader.", rt=True)
add("RUNTIME", F_API, L(F_API, "s-maxage=86400"),
    "API route serves the transformed KBLICode[] with 24h cache; deployed content not observable here.", 1.0,
    "None.", rt=True)
add("RUNTIME", F_CHAT, L(F_CHAT, "NEXT_PUBLIC_BACKEND_URL"),
    "ZantaraChat posts to NEXT_PUBLIC_BACKEND_URL (default nuzantara-rag.fly.dev) kbli-notebook/chat; answers are LLM output, not corpus.", 1.0,
    "Label chat answers as unverified.", rt=True)
add("RUNTIME", F_CERT, L(F_CERT, "import certifications from"),
    "Editorial certification JSON imported from repo root data/kbli-filiera; build must have it; hash recompute here is static only.", 1.0,
    "None.", rt=True)
add("RUNTIME", F_SITEMAP, L(F_SITEMAP, "const BASE_URL"),
    "Sitemap hardcodes BASE_URL balizero.com/kbli-navigator and lists 1559 code pages from getAllCodes(); deployed sitemap unobserved.", 1.0,
    "None.", rt=True)

# =============================================================================
# Write outputs
# =============================================================================
os.makedirs(os.path.dirname(OUT_MAP), exist_ok=True)
with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=COLS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)

render_map = OrderedDict()
render_map["code"] = dict(source="data.kode_kbli_2025", file=F_DATA, line=L(F_DATA, "const code = raw.kode_kbli_2025"), verbatim=True, affected_codes=[])
render_map["titleId (subtitle, card p)"] = dict(source="HEURISTIC toTitleCase(data.judul)", file=F_DATA, line=L(F_DATA, "const titleId = toTitleCase(raw.judul)"), verbatim=False, affected_codes=title_case_changed)
render_map["titleEn (h1, card h3, metadata title, JSON-LD name, chat title)"] = dict(source="OTHER_FILE lib/kbli-english.ts ENGLISH_TITLES ?? titleId", file=F_DATA, line=L(F_DATA, "const titleEn = ENGLISH_TITLES[code] ?? titleId"), verbatim=False, affected_codes=h1_not_judul)
render_map["description (detail page lead)"] = dict(source="data.uraian (verbatim) unless gold or certified intel_2026 replaces it", file=F_PAGE, line=L(F_PAGE, "{kbli.description}", 9900), verbatim=False, affected_codes=uraian_not_lead)
render_map["description (metadata)"] = dict(source="HEURISTIC data.uraian.slice(0,150)+'...'", file=F_PAGE, line=L(F_PAGE, "kbli.description.slice(0, 150)"), verbatim=False, affected_codes=[c for c in CODES if len(CORP[c]["uraian"]) > 150])
render_map["description (JSON-LD)"] = dict(source="HEURISTIC data.uraian.slice(0,200)", file=F_JSONLD, line=L(F_JSONLD, "code.description.slice(0, 200)"), verbatim=False, affected_codes=[c for c in CODES if len(CORP[c]["uraian"]) > 200])
render_map["ruang_lingkup"] = dict(source="NOT RENDERED (corpus ruang_lingkup ignored)", file=F_TYPES, line=L(F_TYPES, "export interface KBLIRawCode"), verbatim=False, affected_codes=[c for c in CODES if CORP[c].get("ruang_lingkup")])
render_map["section"] = dict(source="HEURISTIC prefix map (not data.sektor_id)", file=F_DATA, line=L(F_DATA, "const section = getSectionFromCode(code)"), verbatim=False, affected_codes=None)
render_map["sectionName"] = dict(source="HARDCODED SECTION_META", file=F_DATA, line=L(F_DATA, "const SECTION_META"), verbatim=False, affected_codes=None)
render_map["pma"] = dict(source="data.pma_* (ENRICHMENT, gated)", file=F_PMA, line=L(F_PMA, "export function disclosePmaInfo"), verbatim=False, affected_codes=None)
render_map["licensing"] = dict(source="data.per_skala[] (ENRICHMENT)", file=F_DATA, line=L(F_DATA, "scales: entry.skala_usaha"), verbatim=True, affected_codes=None)
render_map["transition"] = dict(source="data.status_mapping etc. (ENRICHMENT)", file=F_DATA, line=L(F_DATA, "mappingStatus: raw.status_mapping"), verbatim=True, affected_codes=None)
render_map["baliL4"] = dict(source="data.l4_bali (ENRICHMENT, gated)", file=F_L4, line=L(F_L4, "export function discloseBaliL4Record"), verbatim=False, affected_codes=None)
render_map["intel_2026"] = dict(source="data.intel_2026 (ENRICHMENT, hash-gated, zantaraOpener replaced)", file=F_DATA, line=L(F_DATA, "intel_2026: canonicalIntelCertified"), verbatim=False, affected_codes=intel_certified)
render_map["gold editorial"] = dict(source="OTHER_FILE lib/kbli-gold-content.ts (hash-gated)", file=F_GOLD, line=L(F_GOLD, "export function getGoldContent"), verbatim=False, affected_codes=gold_certified)
json.dump(render_map, open(OUT_MAP, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

N["rows_total"] = len(rows)
N["rows_by_family"] = dict(Counter(r["family"] for r in rows))
json.dump(N, open(OUT_NUM, "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=str)
print(json.dumps({k: N[k] for k in ("rows_total", "rows_by_family")}, indent=1))
