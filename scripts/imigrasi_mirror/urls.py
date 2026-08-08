r"""Canonical URL catalog for the imigrasi.go.id scoped mirror.

Scope (Zero mandate, 2026-08-08): NOT a full-site copy. Only the pages that
feed the Bali Zero visa engine — the VoA/BVK/Calling subject lists, the
per-visa-code catalog, and three regional-office mirrors as a counter-proof
that the schema is uniform. v2 (2026-08-09) adds two more daily pages: the
national `/berita` news index — where a subject removal (e.g. San Marino) is
announced first, before the subject lists are edited — and the kemenimipas
Peraturan Menteri legal-doc listing (the legal instrument that enacts a visa
rule change, feeding the Visa Oracle RulePack). ~125 pages total (11 "daily" +
114 "weekly").

Every URL below was verified live (200, real content — not a 404) before being
committed here (anti-hallucination discipline, CLAUDE.md §6): the v1 set on
2026-08-08, the `/berita` and kemenimipas Permen v2 pages on 2026-08-09. Do not
add a URL to this file without the same verification.

The ~114 per-visa-code identifiers are a COPY of the codes in the repo's own
seed file, not a live import — this keeps the mirror module dependency-free
from the backend-rag app (no sqlalchemy/pydantic import chain for a crawler
script that must also run standalone via cron). That makes this a
state-schema fork by construction (cicatrix family #9): if the seed file
gains/loses codes, this list goes stale silently unless re-checked.

Source of truth:
    apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py

Regenerate/verify with:
    grep -oP '"code":\s*"\K[^"]+' \
        apps/backend-rag/backend/migrations/scripts/seed_visa_types_complete_2026.py \
        | sort -u

`run.py --verify-codes` re-runs that grep (when the monorepo is reachable
from this checkout) and fails loudly on drift instead of silently mirroring
a stale catalog.

Extracted 2026-08-08: 114 codes, A1..SKTT.
"""

from __future__ import annotations

from dataclasses import dataclass

BASE = "https://www.imigrasi.go.id"

# --- 114 codes, verbatim from the seed file (see docstring for provenance) --
CODES: list[str] = [
    "A1", "A4", "A36", "A37",
    "B1", "B4",
    "C1", "C2", "C3", "C4", "C5", "C5A", "C6", "C7", "C7A", "C7B", "C7C",
    "C8", "C8A", "C8B", "C9", "C9A", "C9B", "C10", "C10A", "C11", "C11A",
    "C12", "C13", "C14", "C15", "C16", "C17", "C18", "C19", "C20", "C21",
    "C22", "C22A", "C22B",
    "D1", "D2", "D3", "D4", "D7", "D8", "D12", "D14", "D17",
    "E23", "E23-FREELANCE", "E23A", "E23U", "E23V", "E23X", "E23Y",
    "E25", "E25A", "E25B", "E25C", "E25D", "E25E", "E25F",
    "E26", "E27",
    "E28", "E28A", "E28B", "E28C", "E28D", "E28E", "E28F", "E28G",
    "E29",
    "E30", "E30A", "E30B", "E30E", "E30F",
    "E31", "E31A", "E31B", "E31C", "E31D", "E31E", "E31F", "E31G", "E31H", "E31J",
    "E32", "E32A", "E32B", "E32C", "E32D", "E32E", "E32F", "E32G", "E32H",
    "E33", "E33A", "E33B", "E33C", "E33D", "E33E", "E33F", "E33G",
    "E34",
    "E35", "E35A",
    "EPO", "ERP",
    "F1", "F4",
    "SKTT",
]

assert len(CODES) == 114, f"expected 114 codes, got {len(CODES)} — catalog drifted, re-derive from the seed file"
assert len(set(CODES)) == len(CODES), "duplicate code in CODES"


@dataclass(frozen=True)
class Page:
    id: str
    url: str
    slug: str
    label: str
    tier: str  # "daily" | "weekly"
    category: str  # "list" | "faq" | "index" | "berita" | "produk-hukum" | "regional" | "code"
    # Which extractor in extract.py handles this page's HTML. Default = the
    # generic content-block extractor; a page on a differently-structured CMS
    # (e.g. the kemenimipas Joomla legal-doc listing) names a specific one.
    extractor: str = "default"


# --- daily tier: the pages that "morde" (bite) — subject lists, FAQ, visa    --
# --- index, the /berita news index + kemenimipas Permen listing (v2), and    --
# --- 3 regional mirrors as a schema counter-proof.                           --
DAILY_PAGES: list[Page] = [
    Page(
        id="parent",
        url=f"{BASE}/wna/daftar-negara-voa-bvk-calling-visa",
        slug="voa-bvk-calling-parent",
        label="Elenco padre VoA/BVK/Calling",
        tier="daily",
        category="list",
    ),
    Page(
        id="voa",
        url=f"{BASE}/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-subjek-visa-on-arrival",
        slug="voa-subjects",
        label="Lista VOA (Visa on Arrival)",
        tier="daily",
        category="list",
    ),
    Page(
        id="bvk",
        url=f"{BASE}/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-bebas-visa-kunjungan",
        slug="bvk-subjects",
        label="Lista BVK (Bebas Visa Kunjungan)",
        tier="daily",
        category="list",
    ),
    Page(
        id="calling",
        url=f"{BASE}/wna/daftar-negara-voa-bvk-calling-visa/daftar-negara-calling-visa",
        slug="calling-visa-subjects",
        label="Lista Calling Visa",
        tier="daily",
        category="list",
    ),
    Page(
        id="faq-evoa",
        url=f"{BASE}/faq/visa/negara-mana-saja-yang-terdaftar-dalam-daftar-electronic-visa-on-arrival-e-voa",
        slug="faq-evoa-countries",
        label="FAQ — Paesi e-VOA (documentata per la sua staleness, W90)",
        tier="daily",
        category="faq",
    ),
    Page(
        id="visa-index",
        url=f"{BASE}/wna/daftar-visa-indonesia",
        slug="visa-index",
        label="Indice Daftar Visa Indonesia",
        tier="daily",
        category="index",
    ),
    Page(
        id="berita",
        url=f"{BASE}/berita",
        slug="berita-index",
        label="Indice Berita (news/annunci — dove le rimozioni si annunciano per prime)",
        tier="daily",
        category="berita",
    ),
    Page(
        # kemenimipas.go.id, NOT imigrasi.go.id — the legal-documents portal
        # moved to the new ministry domain (imigrasi.go.id/produk-hukum is 404).
        # The Permen Imipas listing is where a visa rule change (e.g. Permen
        # 9 & 10/2025 added visa-free countries — the San Marino class — and
        # 14/2025 the zero-tariff services) is enacted, feeding the Visa Oracle
        # RulePack thresholds. Custom extractor: the listing lives inside a
        # Joomla <form> the generic extractor strips, with volatile view
        # counters the generic extractor would false-diff on — see extract.py.
        id="produk-hukum-permen",
        url="https://kemenimipas.go.id/produk-hukum/peraturan-menteri-imipas",
        slug="produk-hukum-permen",
        label="Kemenimipas — Peraturan Menteri (produk hukum, alimenta soglie RulePack)",
        tier="daily",
        category="produk-hukum",
        extractor="produk_hukum",
    ),
    Page(
        id="regional-depok",
        url="https://depok.imigrasi.go.id/47666-2/",
        slug="regional-depok-list",
        label="Kanim Depok — lista VoA/BVK/Calling",
        tier="daily",
        category="regional",
    ),
    Page(
        id="regional-bontang",
        url="https://bontang.imigrasi.go.id/layanan-publik/kategori/wna/sub/daftar-subjek-voa-bvk-calling-visa",
        slug="regional-bontang-list",
        label="Kanim Bontang — lista VoA/BVK/Calling",
        tier="daily",
        category="regional",
    ),
    Page(
        id="regional-ngurahrai",
        url="https://ngurahrai.imigrasi.go.id/layanan-wna/",
        slug="regional-ngurahrai-list",
        label="Kanim Ngurah Rai — lista VoA/BVK/Calling",
        tier="daily",
        category="regional",
    ),
]

# --- weekly tier: the ~114 per-visa-code detail pages -----------------------
WEEKLY_PAGES: list[Page] = [
    Page(
        id=f"code-{code}",
        url=f"{BASE}/wna/daftar-visa-indonesia/{code}",
        slug=f"code-{code}",
        label=f"Visa {code}",
        tier="weekly",
        category="code",
    )
    for code in CODES
]

ALL_PAGES: list[Page] = DAILY_PAGES + WEEKLY_PAGES

_BY_ID = {p.id: p for p in ALL_PAGES}
assert len(_BY_ID) == len(ALL_PAGES), "duplicate page id in catalog"


def pages_for_tier(tier: str) -> list[Page]:
    if tier == "daily":
        return list(DAILY_PAGES)
    if tier == "weekly":
        return list(WEEKLY_PAGES)
    if tier == "all":
        return list(ALL_PAGES)
    raise ValueError(f"unknown tier {tier!r} — expected daily|weekly|all")


def pages_for_select(ids: list[str]) -> list[Page]:
    missing = [i for i in ids if i not in _BY_ID]
    if missing:
        raise ValueError(f"unknown page id(s): {missing} — known ids: {sorted(_BY_ID)}")
    return [_BY_ID[i] for i in ids]
