"""What a REQUIRES edge out of a KBLI node actually points at.

`inspect_kbli` built its `licenses[]` by walking every `REQUIRES` edge and
appending the target node's *name* as a licence type, with no notion of what
the target IS. The knowledge graph does not only hang permits off a KBLI code
— it hangs costs, durations, obligations, regulations, company forms and the
OSS system itself off the same relationship. Measured on prod, **35 distinct
target entity types** reach that list.

So the endpoint told a client opening a restaurant (`56101`) that the permits
to obtain included:

    "10 Billion IDR" · "2.5 Billion IDR" · "Rp 2.5 miliar" · "IDR 10 billion"
    · "IDR 10 miliar" · "Rp10.000.000.000,00" · "Modal Disetor" · "PT PMA"

— six renderings of the same two *capital thresholds*, plus the company form —
and one entry whose obligations were "cara budi daya tanaman pangan yang baik"
(good crop-cultivation practice) with reporting to the Minister of Agriculture,
because a `permen` node describing farming practice is `REQUIRES`-linked to a
restaurant code.

A capital threshold is not a permit. Presenting one as a permit is the
plausible-but-wrong assertion this navigator exists to eliminate.

DESIGN — two rules, both learned the hard way in this repo:

1. **Nothing is dropped silently.** Non-permit targets are not discarded; they
   are bucketed and returned alongside, so the endpoint loses no information
   and a reader can see what the graph actually attached. A cure that quietly
   deletes 7,369 `dokumen` edges would be a second defect wearing the shape of
   a fix.

2. **An unknown type is never promoted.** The graph gains entity types over
   time (this classification was derived from a census, and a census is a
   snapshot). An unrecognised type therefore falls to `other` — visible, but
   never asserted to be a permit. The failure mode is a missing badge, never an
   invented licence. This is the fail-safe direction, and it is pinned by test.

The classification is by ENTITY TYPE, never by matching substrings in the
node's name — cicatrix family #3 has bitten this repo repeatedly on exactly
that pattern, and the names here are precisely where the noise lives
("NIB dan Izin (Izin Operasi Penyimpanan Karbon)" vs "Biaya izin ...").
"""

from __future__ import annotations

import re

# Types that genuinely denote something a business must OBTAIN — a permit, a
# registration, a standards certificate, a formal determination. Verified
# against the live node names, not assumed from the type label:
#   perizinan   → "NIB dan Izin (IUJP)", "NIB dan Izin (Izin Eksplorasi ...)"
#   izin_usaha  → "Akreditasi Rumah Sakit", "addendum Perizinan Berusaha"
#   license     → "Izin", "NIB", "NPWP", "Sertifikat Standar"
#   nib         → "NIB", "Nomor Induk Berusaha", "SERTIFIKAT STANDAR"
#   permit_type → permit taxonomy nodes
#   penetapan   → "Penetapan Pusat Penyedia" (a formal designation)
PERMIT_TYPES: frozenset[str] = frozenset(
    {
        "perizinan",
        "izin_usaha",
        "license",
        "nib",
        "permit_type",
        "penetapan",
    },
)

# Everything else, bucketed so it stays visible. The bucket name is what a
# reader of the API sees, so it is written for that reader, not for the graph.
_BUCKETS: dict[str, str] = {
    # Money. NEVER a permit — this is the defect that started this module.
    "biaya": "costs",
    # Time windows ("10 Hari", "1 Tahun") — an SLA or a validity, not a thing
    # you apply for.
    "jangka_waktu": "durations",
    # Duties you carry once operating: reports, monitoring, guarantees.
    "kewajiban": "obligations",
    "kewajiban_perpajakan": "obligations",
    "tanggung_jawab_sosial_lingkungan": "obligations",
    "alih_teknologi": "obligations",
    "sanksi": "obligations",
    # The legal instruments themselves. A regulation is the SOURCE of a duty,
    # never a permit to obtain — and `permen` is where the farming-practice
    # text that surfaced on a restaurant lives.
    "undang_undang": "regulations",
    "peraturan_pemerintah": "regulations",
    "permen": "regulations",
    "perda": "regulations",
    "surat_edaran": "regulations",
    "pasal": "regulations",
    # Papers you supply as evidence — required, but not licences.
    "dokumen": "documents",
    # Corporate form / counterparties.
    "company_type": "entity_forms",
    "pt_pmdn": "entity_forms",
    "perusahaan": "entity_forms",
    "organisasi": "entity_forms",
    # Immigration artefacts travel their own path in this product.
    "immigration_doc": "immigration",
    "vitas": "immigration",
    "kitas": "immigration",
    # Systems and channels ("Online Single Submission", "NOT_APPLICABLE_OSS").
    "oss": "systems",
    "sistem": "systems",
    "sistem_manajemen_usaha": "systems",
}


def classify_requires_target(entity_type: str | None) -> str:
    """Return `"license"` for permit-bearing targets, else the bucket name.

    Unknown / missing types fall to `"other"`: visible, never a licence.
    """
    if not entity_type:
        return "other"
    key = entity_type.strip().lower()
    if key in PERMIT_TYPES:
        return "license"
    return _BUCKETS.get(key, "other")


def is_permit_type(entity_type: str | None) -> bool:
    """True only for target types that denote something to OBTAIN."""
    return classify_requires_target(entity_type) == "license"


# =============================================================================
# SECOND STAGE — the TYPE says permit, the NAME says otherwise
# =============================================================================
#
# `classify_requires_target` answers "is this kind of thing a permit". It cannot
# answer "is this particular node a NAMED permit", and on the live graph those
# come apart. Census of the 2,585 permit-typed nodes reachable from a KBLI code
# (2026-08-06, measured — not estimated):
#
#   2,075 carry structured properties and share just 31 distinct names. Clean.
#     510 carry EMPTY properties and have 509 distinct names — one node per
#         free-text string lifted out of the PP 28 tables. Every defect below
#         lives in this second population, and none in the first.
#
# Three things in there are not permits, and each reaches real clients:
#
#   1. PLACEHOLDERS. One node's entity_id is literally
#      `izin_usaha_tidak_diketahui` — "business permit NOT KNOWN". The graph
#      recorded its own ignorance and the endpoint published it to clients as a
#      permit called "Izin Usaha", on **186 KBLI codes**.
#   2. CATEGORY LABELS. "Izin Usaha", "UMKU", "Izin", "Badan Hukum" — the class
#      of permit, never an instance. Plus two extraction wrecks, "NIB dan"
#      (cut at a conjunction) and "Izin Penga-" (cut mid-word at a PDF line
#      break), and the table header "Jenis Izin" ("permit type"). 107 codes.
#   3. OBLIGATIONS. 71 whole sentences from the kewajiban column, every one
#      starting with an Indonesian active verb: "Melaporkan kegiatan usahanya
#      secara periodik…" ("to report its activities periodically…"). A duty you
#      carry, not a document you obtain. 39 codes.
#
# DESIGN — the same two rules the first stage was built on:
#
# 1. **Nothing is dropped.** A demoted target moves into `related_requirements`,
#    so the endpoint loses no information and a reader still sees what the graph
#    attached. Deleting them would be a second defect wearing the shape of a fix.
# 2. **The default is to stay a permit.** Every rule below is a POSITIVE
#    recognition of a non-permit; anything unrecognised keeps its licence
#    status. The failure mode is a permit that keeps a bad label, never a real
#    permit that silently vanishes from a client's list.
#
# On matching by ENTITY and not by FORM (cicatrix family #3): the placeholder
# rule reads the graph's own id, not the display string. The category rule is an
# ENUMERATED list from the census above — not a length or substring heuristic,
# because "NIB", "NPWP", "TDUP", "SBU" and "KITAS" are equally short and
# entirely real. The obligation rule is the one linguistic rule, and it is a
# grammatical fact rather than a keyword: in Indonesian the meN- prefix marks
# the active verb, so a name that OPENS with one is a verb phrase — a duty —
# while every real permit name here is a noun phrase ("Sertifikat …", "Izin …").
# All 71 matches were read one by one before this shipped; none is a permit.

#: Substrings that make an entity_id an admission of ignorance, not an entity.
_UNKNOWN_ID_MARKERS: tuple[str, ...] = ("tidak_diketahui", "unknown", "placeholder")

#: The id token by which the graph calls a node a DUTY. When it disagrees with
#: `entity_type`, this wins — a node's own identity outranks the column that
#: happens to file it.
#:
#: Found by an independent reviewer's push on the name rule, then measured
#: rather than argued: **97** permit-typed targets of a KBLI `REQUIRES` edge
#: carry `kewajiban` as an id token, reaching **62** codes — far more than the
#: name rule could ever see, because these are noun-phrase duties
#: ("Laporan Penomoran Telekomunikasi", "Wajib Lapor Ketenagakerjaan
#: Perusahaan", "Laporan 6 Bulan") that no verb list catches.
#:
#: INNOCENCE MEASURED BEFORE SHIPPING, which is what makes it safe: of those 97,
#: **zero** carry a permit-shaped name (`Izin…`/`Sertifikat…`/`NIB…`/`Surat
#: Izin…`/`Persetujuan…`/`Penetapan…`). So the rule demotes no real permit today.
#:
#: Matched as a TOKEN, never as a bare substring (cicatrix #3): the id is split
#: on its own separators, so a hypothetical `izin_kewajibanX` is NOT caught. The
#: entity, not the shape.
_OBLIGATION_ID_TOKEN = "kewajiban"

#: Enumerated from the census. A category, a header, or a truncation wreck —
#: never an instance. Compared case-insensitively after stripping.
_CATEGORY_LABELS: frozenset[str] = frozenset(
    {
        "izin usaha",  # "business permit" — the class
        "izin",  # literally "permit"
        "umku",  # the OSS class of supporting permits
        "badan hukum",  # "legal entity" — a company form
        "jenis izin",  # "permit type" — a table HEADER
        "sertifikat",  # "certificate" — the class
        "kecil",  # "Small" — a business SCALE that leaked in
        "unknown",
        "nib dan",  # truncated at a conjunction ("NIB and …")
        "izin penga-",  # truncated mid-word at a PDF line break
    }
)

#: The 23 Indonesian active verbs that actually open an obligation sentence on
#: this graph, ENUMERATED from the census — not matched by the meN- prefix.
#:
#: The prefix rule was written first and is exactly the mistake this repo keeps
#: paying for: `^me[a-z]+ ` also matches "Menteri" (minister), "Merek" (brand),
#: "Mesin" (machine), "Media", "Metode" — nouns that could open a perfectly real
#: permit name. Measured: today NO permit-typed node starts with "Me" other than
#: these 71 obligations, so the enumeration loses nothing now and protects the
#: noun case later.
#:
#: DECLARED LIMIT: an obligation opening with a 24th verb keeps its licence
#: label until this list grows. That is the fail-safe direction — a mislabelled
#: duty is visible and reportable; a real permit deleted from a client's list
#: is not.
_OBLIGATION_VERBS: frozenset[str] = frozenset(
    {
        "melaksanakan", "melakukan", "melaporkan", "melengkapi", "memanfaatkan",
        "mematuhi", "membantu", "memenuhi", "memiliki", "mempunyai",
        "menerapkan", "mengajukan", "mengelola", "menggunakan", "mengikuti",
        "mengutamakan", "menjaga", "menjalankan", "menjamin", "menutup",
        "menyampaikan", "menyerahkan", "merealisasikan",
    }
)


def permit_name_verdict(entity_id: str | None, name: str | None) -> str:
    """`"permit"`, or the `related_requirements` bucket this target belongs in.

    Ordered most-decisive first: the graph's own admission of ignorance beats a
    plausible-looking name, and an enumerated label beats the grammatical rule.
    """
    label = (name or "").strip()
    ident = (entity_id or "").strip().lower()

    if not label:
        # A permit with no name cannot be presented as one to a client.
        return "unspecified_permits"

    if any(marker in ident for marker in _UNKNOWN_ID_MARKERS):
        return "unspecified_permits"

    # The graph calling itself a duty outranks the column that filed it as a
    # permit. Token match, not substring: `izin_kewajibanX` is a different word.
    if _OBLIGATION_ID_TOKEN in re.split(r"[^a-z0-9]+", ident):
        return "obligations"

    if label.casefold() in _CATEGORY_LABELS:
        return "unspecified_permits"

    # A verb phrase is a duty. Requires a SECOND word: a bare "Memiliki" would
    # be a fragment, not a sentence, and is left alone.
    head, _, rest = label.partition(" ")
    if rest.strip() and head.casefold() in _OBLIGATION_VERBS:
        return "obligations"

    return "permit"


def is_named_permit(entity_id: str | None, name: str | None) -> bool:
    """True when this target may be presented to a client as a permit to obtain."""
    return permit_name_verdict(entity_id, name) == "permit"
