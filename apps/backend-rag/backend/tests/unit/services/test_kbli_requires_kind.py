"""A capital threshold is not a permit.

`inspect_kbli` appended every REQUIRES-edge target to `licenses[]` using the
target node's name, with no notion of what the target was. On `56101`
(restaurant — one of the highest-traffic questions this product receives) a
client was shown, as permits to obtain: six renderings of the same two capital
thresholds, the company form "PT PMA", and an entry whose obligations were
good crop-cultivation practice with reporting to the Minister of Agriculture.

These tests pin BOTH directions, because a classifier that only proves guilt is
how a cure becomes the next defect (cicatrix family #3): the permit types must
still pass, and the non-permit types must not.
"""

import pytest

from backend.services.kbli_requires_kind import (
    PERMIT_TYPES,
    classify_requires_target,
    is_permit_type,
)

# The full census of REQUIRES-edge target types measured on prod
# (source_entity_id LIKE 'kbli:%'), with the edge count, so a future reader can
# see this was derived from the graph rather than imagined.
PROD_TARGET_TYPES: dict[str, int] = {
    "dokumen": 7369,
    "perizinan": 3808,
    "izin_usaha": 1935,
    "license": 1167,
    "kewajiban": 174,
    "permen": 116,
    "nib": 100,
    "peraturan_pemerintah": 96,
    "oss": 52,
    "jangka_waktu": 47,
    "biaya": 44,
    "pt_pmdn": 26,
    "company_type": 25,
    "undang_undang": 20,
    "penetapan": 10,
    "permit_type": 9,
    "perusahaan": 9,
    "organisasi": 7,
    "immigration_doc": 7,
    "sistem": 7,
    "fasilitas": 4,
    "sistem_manajemen_usaha": 3,
    "pekerja": 3,
    "kbli": 3,
    "entity": 3,
    "parameter": 2,
    "vitas": 1,
    "jabatan": 1,
    "kewajiban_perpajakan": 1,
    "kitas": 1,
    "perda": 1,
    "sanksi": 1,
    "surat_edaran": 1,
    "tanggung_jawab_sosial_lingkungan": 1,
    "alih_teknologi": 1,
}


# --- GUILT: the types that produced the live defect must not be licences ----

@pytest.mark.parametrize(
    ("entity_type", "expected_bucket"),
    [
        ("biaya", "costs"),  # "10 Billion IDR", "Rp10.000.000.000,00"
        ("company_type", "entity_forms"),  # "PT PMA"
        ("permen", "regulations"),  # "Cara budi daya tanaman pangan yang baik"
        ("jangka_waktu", "durations"),  # "10 Hari", "1 Tahun"
        ("kewajiban", "obligations"),  # "Laporan Hasil Monitoring"
        ("undang_undang", "regulations"),
        ("peraturan_pemerintah", "regulations"),
        ("dokumen", "documents"),  # "Akta Pendirian"
        ("oss", "systems"),  # "Online Single Submission"
        ("sanksi", "obligations"),
    ],
)
def test_non_permit_types_are_never_licences(entity_type: str, expected_bucket: str) -> None:
    assert not is_permit_type(entity_type)
    assert classify_requires_target(entity_type) == expected_bucket


def test_the_capital_threshold_defect_specifically() -> None:
    """Pin the exact shape that reached a client on 56101."""
    assert classify_requires_target("biaya") == "costs"
    assert "biaya" not in PERMIT_TYPES


# --- INNOCENCE: real permits must still reach licenses[] -------------------

@pytest.mark.parametrize(
    "entity_type",
    ["perizinan", "izin_usaha", "license", "nib", "permit_type", "penetapan"],
)
def test_permit_types_still_pass(entity_type: str) -> None:
    """The three biggest permit buckets carry 6,910 of the edges between them.

    A cure that suppressed these would empty the licence list on most codes —
    a different failure, not a fix.
    """
    assert is_permit_type(entity_type)
    assert classify_requires_target(entity_type) == "license"


def test_case_and_whitespace_do_not_change_the_verdict() -> None:
    assert is_permit_type("  Perizinan ")
    assert not is_permit_type("BIAYA")


# --- FAIL-SAFE: an unknown type is visible, never promoted ------------------

@pytest.mark.parametrize("entity_type", [None, "", "   ", "a_type_invented_next_year"])
def test_unknown_types_fall_to_other_and_are_never_licences(entity_type: str | None) -> None:
    """The graph gains types over time; this classification is a snapshot.

    The failure mode must be a missing badge, never an invented licence.
    """
    assert classify_requires_target(entity_type) == "other"
    assert not is_permit_type(entity_type)


# --- COVERAGE: every type actually observed on prod has a verdict ----------

def test_every_prod_target_type_is_classified() -> None:
    """`other` is a legitimate destination, but it should be a decision.

    Any type here that lands in `other` is one nobody has adjudicated — this
    test does not fail on that (the fail-safe already covers the risk), it
    reports them, so the list stays honest as the graph grows.
    """
    unadjudicated = sorted(
        t for t in PROD_TARGET_TYPES if classify_requires_target(t) == "other"
    )
    # These are the tail types (≤7 edges each) deliberately left to `other`:
    # they are neither permits nor cleanly bucketable, and `other` states that.
    assert unadjudicated == [
        "entity",
        "fasilitas",
        "jabatan",
        "kbli",
        "parameter",
        "pekerja",
    ], f"the `other` set changed: {unadjudicated}"


def test_the_permit_set_is_a_minority_of_types_but_the_majority_of_edges() -> None:
    """Sanity on the shape of the fix: it must not gut the licence list.

    Of the 35 observed types only 6 are permits — but they carry **7,029 of the
    15,055** edges (46.7%), so nearly half of what the endpoint used to call a
    licence really was one. The other 8,026 were not, and `dokumen` alone
    (7,369) is the single largest non-permit bucket — which is why those go to
    `documents` rather than being dropped.

    (These totals are asserted rather than described because the first draft of
    this test carried a hand-summed 14,875 and the test caught it. A number in
    a docstring is a claim; a number in an assert is a measurement.)
    """
    permit_edges = sum(n for t, n in PROD_TARGET_TYPES.items() if is_permit_type(t))
    total_edges = sum(PROD_TARGET_TYPES.values())
    assert permit_edges == 7029
    assert total_edges == 15055
    assert total_edges - permit_edges == 8026
    assert permit_edges > total_edges / 3
