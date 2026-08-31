r"""Canonical URL catalog for the imigrasi.go.id scoped mirror.

Scope (Zero mandate, 2026-08-08): NOT a full-site copy. Only the pages that
feed the Bali Zero visa engine — the VoA/BVK/Calling subject lists, the
per-visa-code catalog, and three regional-office mirrors as a counter-proof
that the schema is uniform. v2 (2026-08-09) adds four more daily pages: the
national `/berita` news index — where a subject removal (e.g. San Marino) is
announced first, before the subject lists are edited — the kemenimipas
Peraturan Menteri legal-doc listing (the legal instrument that enacts a visa
rule change, feeding the Visa Oracle RulePack), the applicant-facing
e-Visa eVOA info page (fee, requirements, eligible-country list — the
downstream-of-policy surface the client actually reads, a second independent
witness to a rule change), and the TPI entry-point list — the 122 immigration
checkpoints (airports / seaports / land-border posts) where VoA is actually
granted, the operational counterpart to the subject lists (WHO may get VoA vs
WHERE it is issued). v3 (2026-08-31) adds the last two RulePack
OFFICIAL_PORTAL urls that were cited but never mirrored: the 2024 bridging-visa
press release and the ITK-to-ITAS status-conversion page.
129 pages total (15 "daily" + 114 "weekly"), asserted below so the number
cannot go stale in prose the way it already had.

Every URL below was verified live (200, real content — not a 404) before being
committed here (anti-hallucination discipline, CLAUDE.md §6): the v1 set on
2026-08-08, the `/berita`, kemenimipas Permen, e-Visa eVOA and TPI entry-point
v2 pages on 2026-08-09. Do not add a URL to this file without the same verification.

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
    category: str  # "list" | "faq" | "index" | "berita" | "produk-hukum" | "evisa" | "tpi" | "regional" | "code"
    # Which extractor in extract.py handles this page's HTML. Default = the
    # generic content-block extractor; a page on a differently-structured CMS
    # (e.g. the kemenimipas Joomla legal-doc listing) names a specific one.
    extractor: str = "default"


# --- daily tier: the pages that "morde" (bite) — subject lists, the TPI       --
# --- entry-point list, FAQ, visa index, the /berita news index + kemenimipas  --
# --- Permen listing + e-Visa eVOA info (v2), and 3 regional mirrors as a      --
# --- schema counter-proof.                                                    --
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
        # The operational counterpart to the subject lists above: WHO may get
        # VoA (the subject lists) vs WHERE it is actually issued (this list of
        # 122 immigration checkpoints — 16 airports, 11 land-border posts, 95
        # seaports — "titik masuk bagi pemegang e-VOA" = entry points for e-VOA
        # holders). A checkpoint added/removed here changes where a Bali Zero
        # client can physically land on VoA. Sibling of the VoA/BVK/Calling
        # section. Generic extractor: a plain "name, province" text list, no
        # form-wrapper and no volatile counters (extraction-stability probed
        # 2026-08-09 — identical extract sha d42f566c across two fetches).
        id="tpi-evoa-entry-points",
        url=f"{BASE}/wna/daftar-negara-voa-bvk-calling-visa/titik-masuk-bagi-pemegang-e-voa",
        slug="tpi-evoa-entry-points",
        label="TPI — 122 checkpoint d'ingresso e-VOA (aeroporti/porti/PLBN, dove il VoA è emesso)",
        tier="daily",
        category="tpi",
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
        # evisa.imigrasi.go.id, NOT www.imigrasi.go.id — the applicant-facing
        # e-Visa portal is a separate subdomain. This is the eVOA/Visitor-Visa
        # info page a foreign traveller actually reads: the fee ("IDR 500.000"),
        # the document requirements, and the full eligible-country list. It is
        # DOWNSTREAM of the policy pages above — when a Permen changes a fee or
        # adds a country, this is where the change surfaces to the public, so a
        # diff here is a second, independent witness to the same rule change.
        # Generic extractor: the page is a plain content block (extraction-
        # stability probed 2026-08-09 — identical extract across two fetches,
        # no volatile view counters), so no page-specific extractor is needed.
        id="evisa-evoa-info",
        url="https://evisa.imigrasi.go.id/front/info/evoa",
        slug="evisa-evoa-info",
        label="e-Visa — eVOA/Visitor Visa info (fee, requisiti, paesi eleggibili)",
        tier="daily",
        category="evisa",
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
    # v3 (2026-08-31): the two OFFICIAL_PORTAL urls the signed RulePack cites
    # that this catalog did not cover. Found by auditing the pack's 18
    # OFFICIAL_PORTAL source records against the 127 slugs actually on disk:
    # 16 were mirrored, these 2 never were, so the engine had a freshness
    # policy on a page nobody was watching.
    #
    # Both are DAILY on purpose. 14 of the 16 already-covered portal urls sit
    # on the weekly `code-*` tier, which means a change to them is invisible
    # for up to six days. A bridging-visa announcement and a status-conversion
    # service page are exactly the surfaces that must not be seen once a week.
    #
    # Extraction-stability probed live from Mini on 2026-08-31, two fetches
    # each, per this file's own house rule:
    #   bridging-visa-press-2024  200, 2436 chars, sha1 d58841c0fc69b58c x2
    #   itk-to-itas               200, 3728 chars, sha1 604ea66a793f4610 x2
    # Both land on the real content block, not the boilerplate banner that
    # trapped extract_text() on 2026-08-08, so `default` is correct for both.
    Page(
        id="bridging-visa-press-2024",
        url=f"{BASE}/siaran_pers/2024/04/23/izin-tinggal-peralihan-jembatani-proses-transisi-izin-tinggal-wna-di-ri",
        slug="bridging-visa-press-2024",
        label="Siaran pers 2024 — Izin Tinggal Peralihan (bridging visa)",
        tier="daily",
        category="berita",
    ),
    Page(
        id="itk-to-itas",
        url=f"{BASE}/wna/izin-tinggal-keimigrasian/izin-tinggal-kunjungan-menjadi-izin-tinggal-terbatas",
        slug="itk-to-itas",
        label="Alih status ITK -> ITAS — pagina di servizio izin tinggal",
        tier="daily",
        category="list",
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

# Asserted, not narrated. The module docstring carried "~127 (13 daily + 114
# weekly)" as prose and `run.py --help` still says "9 pages" from an earlier
# era; prose drifts silently, an assert does not.
assert len(DAILY_PAGES) == 15, f"expected 15 daily pages, got {len(DAILY_PAGES)}"
assert len(ALL_PAGES) == 129, f"expected 129 pages, got {len(ALL_PAGES)}"

_BY_ID = {p.id: p for p in ALL_PAGES}
assert len(_BY_ID) == len(ALL_PAGES), "duplicate page id in catalog"

# The slug is the snapshot FILENAME STEM (`snapshots/<date>/<slug>.txt`), and
# until 2026-08-31 nothing checked it. Only `id` was guarded, and the two are
# deliberately allowed to differ (`id="parent"` / `slug="voa-bvk-calling-parent"`
# ships that way today) — so a hand-authored daily page could reuse another
# page's slug and the two would overwrite each other's snapshot on EVERY run,
# silently, with no error and no missing file to notice. The mirror would keep
# reporting "no diffs" for whichever page lost the race.
_BY_SLUG = {p.slug: p for p in ALL_PAGES}
assert len(_BY_SLUG) == len(ALL_PAGES), (
    "duplicate page slug in catalog — two pages would overwrite each other's "
    "snapshot file every run: "
    + repr(sorted({p.slug for p in ALL_PAGES if sum(q.slug == p.slug for q in ALL_PAGES) > 1}))
)


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
