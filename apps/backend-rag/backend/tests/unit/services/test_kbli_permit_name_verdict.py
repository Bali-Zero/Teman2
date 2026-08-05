"""The graph wrote down that it did not know, and we published it as a permit.

One node's entity_id is literally `izin_usaha_tidak_diketahui` — "business
permit NOT KNOWN". `inspect_kbli` rendered it to clients as a permit called
"Izin Usaha" on **186 KBLI codes**. Alongside it: 7 more category labels and
extraction wrecks on 107 codes, and 71 whole obligation sentences on 39.

The innocence half is what decides whether this is usable at all, because the
junk sits next to names that look exactly as suspicious and are entirely real —
"NIB", "TDUP", "SBU", "KITAS" are just as short as "Izin"; "Menteri", "Merek"
and "Mesin" open just like an obligation verb. A first draft matched the meN-
prefix by regex and would have demoted all three.
"""

from __future__ import annotations

import pytest

from backend.services.kbli_requires_kind import (
    _OBLIGATION_VERBS,
    classify_requires_target,
    is_named_permit,
    permit_name_verdict,
)

# --------------------------------------------------------------------------
# GUILT — the three shapes, from the live census
# --------------------------------------------------------------------------


def test_the_graphs_own_admission_of_ignorance_is_not_a_permit():
    """186 codes. The id says `tidak_diketahui`; the display name does not."""
    assert permit_name_verdict("izin_usaha_tidak_diketahui", "Izin Usaha") == (
        "unspecified_permits"
    )


@pytest.mark.parametrize("marker", ["tidak_diketahui", "unknown", "placeholder"])
def test_an_unknown_marker_anywhere_in_the_id_demotes(marker):
    assert not is_named_permit(f"izin_{marker}_42", "Izin Industri Pertahanan")


@pytest.mark.parametrize(
    "label",
    [
        "Izin Usaha",  # the class, not an instance
        "Izin",  # literally "permit"
        "IZIN",  # same, shouted
        "UMKU",  # the OSS class of supporting permits
        "Badan Hukum",  # a company form
        "Jenis Izin",  # a table HEADER — "permit type"
        "Sertifikat",  # "certificate"
        "Kecil",  # "Small" — a business SCALE that leaked in
        "Unknown",
        "NIB dan",  # truncated at a conjunction
        "Izin Penga-",  # truncated mid-word at a PDF line break
    ],
)
def test_category_labels_and_extraction_wrecks_are_not_permits(label):
    assert permit_name_verdict("i.d.569", label) == "unspecified_permits"


@pytest.mark.parametrize(
    "label",
    [
        "Melaporkan kegiatan usahanya secara periodik kepada pimpinan instansi",
        "Memiliki SDM di bidang perbenihan",
        "Menjamin keamanan dan keselamatan",
        "Menyampaikan laporan kegiatan usaha secara periodik",
        "Merealisasikan pembangunan pabrik",
        "Mengajukan izin pembangunan prasarana perkeretaapian",
    ],
)
def test_obligation_sentences_go_to_the_obligations_bucket(label):
    """A duty you carry, not a document you obtain — and `Mengajukan izin …`
    ("to APPLY FOR a permit") is still a duty, not a permit's name."""
    assert permit_name_verdict("x", label) == "obligations"


def test_an_empty_name_cannot_be_presented_as_a_permit():
    assert permit_name_verdict("x", "") == "unspecified_permits"
    assert permit_name_verdict("x", "   ") == "unspecified_permits"
    assert permit_name_verdict("x", None) == "unspecified_permits"


# --------------------------------------------------------------------------
# INNOCENCE — the names that look guilty and are not
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label",
    ["NIB", "NPWP", "TDUP", "SBU", "KITAS", "NPPBKC", "SPP-IRT", "SKP", "PMR"],
)
def test_short_real_acronyms_survive(label):
    """Every one is shorter than "Izin Usaha". Length was never the signal."""
    assert is_named_permit("license_1", label)


@pytest.mark.parametrize(
    "label",
    [
        "Sertifikat Standar",
        "NIB dan Sertifikat Standar",
        "Izin Industri Pertahanan",
        "Izin Khusus Penjualan Minuman Beralkohol",
        "Sertifikat Persetujuan Kelaikan Fasilitas Produksi Pertahanan",
        "Izin Penerapan Program Manajemen Risiko (PMR) Bertahap Sarana Produksi",
    ],
)
def test_real_permit_names_survive_including_the_ones_that_extend_a_demoted_label(label):
    """"Sertifikat" alone is demoted; "Sertifikat Standar" must not be. Same for
    "NIB dan" versus "NIB dan Sertifikat Standar" — the demotion is on the
    ENUMERATED label, never on a prefix of it."""
    assert is_named_permit("license_1", label)


@pytest.mark.parametrize(
    "label",
    [
        "Menteri Kesehatan approval",  # minister
        "Merek Dagang Terdaftar",  # registered trademark
        "Mesin Produksi Certificate",  # machine
        "Media Penyimpanan Certificate",  # medium
        "Metode Uji Sertifikat",  # method
    ],
)
def test_nouns_that_merely_start_like_a_verb_survive(label):
    """The meN- prefix regex written first would have demoted all five."""
    assert is_named_permit("license_1", label)


def test_a_bare_verb_with_no_object_is_not_a_sentence():
    """"Memiliki" alone is a fragment, not an obligation — a second word is
    required, so a fragment keeps its label rather than being silently moved."""
    assert is_named_permit("x", "Memiliki")


def test_an_unrecognised_name_defaults_to_permit():
    """Fail-safe direction: a permit that keeps a bad label is visible and
    reportable; a real permit deleted from a client's list is not."""
    assert is_named_permit("x", "Something Nobody Has Censused Yet")


def test_a_24th_obligation_verb_keeps_its_label_and_that_is_declared():
    """Pins the DECLARED limit rather than pretending it does not exist."""
    assert "mendaftarkan" not in _OBLIGATION_VERBS
    assert is_named_permit("x", "Mendaftarkan kegiatan usahanya")


# --------------------------------------------------------------------------
# The two stages are independent and must stay so
# --------------------------------------------------------------------------


def test_the_type_stage_is_untouched():
    """`permit_name_verdict` is a SECOND filter. The first one still decides
    what is permit-shaped at all, and a cost is still a cost."""
    assert classify_requires_target("biaya") == "costs"
    assert classify_requires_target("perizinan") == "license"


def test_a_demoted_name_lands_in_a_bucket_the_response_already_publishes():
    """`obligations` is an existing `related_requirements` bucket, so a demoted
    duty joins the duties rather than inventing a parallel place to hide."""
    assert classify_requires_target("kewajiban") == "obligations"
    assert permit_name_verdict("x", "Melaporkan data kapal") == "obligations"


def test_every_enumerated_verb_actually_fires():
    """A list nobody exercises is a list that rots. All 23, one assertion."""
    assert len(_OBLIGATION_VERBS) == 23
    for verb in _OBLIGATION_VERBS:
        assert permit_name_verdict("x", f"{verb.capitalize()} sesuatu") == "obligations"
