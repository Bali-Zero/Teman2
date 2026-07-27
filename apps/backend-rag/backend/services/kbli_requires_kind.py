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
