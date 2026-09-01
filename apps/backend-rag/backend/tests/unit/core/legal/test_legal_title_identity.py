"""Identity is taken from the document's own title, not from the laws it cites.

Every Indonesian regulation opens with a citation list. Until 2026-08-25 the
extractor searched for type, number and year INDEPENDENTLY over the whole
document and took each one's first hit, so a single identity could be assembled
out of three different instruments. Measured consequences, both real:

* PP 31/2013 (Immigration) was stored under number 5409 -- 441 points.
* A ministerial decree measured on 2026-08-25 came out as "UU 28/2025", with
  every field scavenged from its own citation list.

Since ``document_id`` is built from type_abbrev/number/year, a wrong identity is
not a cosmetic error: it is how two unrelated documents come to share a point id
and silently overwrite each other.
"""

import re
import time

import pytest

from backend.core.legal.constants import (
    LEGAL_TITLE_PATTERN,
    LEGAL_TYPE_ABBREV,
    LEGAL_TYPE_NAMES,
)
from backend.core.legal.metadata_extractor import (
    LegalMetadataExtractor,
    extract_title_identity,
    normalize_document_number,
)


@pytest.fixture
def extractor() -> LegalMetadataExtractor:
    return LegalMetadataExtractor()


# ---------------------------------------------------------------------------
# GUILT -- each of these fails against the pre-2026-08-25 extractor
# ---------------------------------------------------------------------------


def test_identity_is_not_assembled_from_three_different_cited_laws(extractor):
    """The PP 31/2013 shape, which production stored under number 5409.

    The foreign number deliberately PRECEDES the title. That placement is what
    makes this test discriminate: the old extractor scans linearly and takes the
    first ``NOMOR <digits>`` anywhere, so a noise number that comes after the
    title is harmless and a test built that way passes before and after the fix,
    proving nothing. Gazette headers really do carry such a number, and 441
    points of PP 31/2013 were stored under it.
    """
    text = (
        "SALINAN\n"
        "TAMBAHAN LEMBARAN NEGARA REPUBLIK INDONESIA NOMOR 5409\n\n"
        "PERATURAN PEMERINTAH REPUBLIK INDONESIA\n"
        "NOMOR 31 TAHUN 2013\n"
        "TENTANG PERATURAN PELAKSANAAN UNDANG-UNDANG KEIMIGRASIAN\n\n"
        "Menimbang : a. bahwa untuk melaksanakan ketentuan ...\n"
        "Mengingat : 1. Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian;\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "PP"
    assert metadata["number"] == "31"
    assert metadata["year"] == "2013"


def test_a_ministerial_decree_keeps_its_alphanumeric_number(extractor):
    """Real specimen, OCR'd from the scan on 2026-08-25.

    Ministries do not number decrees with integers. The old pattern required
    ``\\d+``, found nothing in the title, and took ``Nomor 6 Tahun 2011`` out of
    the citation list -- the Immigration Law's own identity.
    """
    text = (
        "MENTERI IMIGRASI DAN PEMASYARAKATAN\nREPUBLIK INDONESIA\n\n"
        "KEPUTUSAN MENTERI IMIGRASI DAN PEMASYARAKATAN\nREPUBLIK INDONESIA\n\n"
        "NOMOR M.IP-19.GR.01.01 TAHUN 2025\n\nTENTANG\n\n"
        "SISTEM KERJA PADA TEMPAT PEMERIKSAAN IMIGRASI\n\n"
        "Menimbang : a. bahwa peningkatan lalu lintas orang ...\n"
        "Mengingat : 4. Undang-Undang Nomor 6 Tahun 2011 tentang Keimigrasian;\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "Kepmen"
    assert metadata["number"] == "M.IP-19.GR.01.01"
    assert metadata["year"] == "2025"


def test_ocr_confusion_of_one_as_capital_i_is_corrected(extractor):
    """Perpres 157/2024 reaches the extractor as "NOMOR I57"."""
    text = (
        "PERATURAN PRESIDEN REPUBLIK INDONESIA\n"
        "NOMOR I57 TAHUN 2024\n"
        "TENTANG KEMENTERIAN IMIGRASI DAN PEMASYARAKATAN\n\n"
        "Mengingat : Undang-Undang Nomor 39 Tahun 2008 tentang Kementerian Negara;\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "Perpres"
    assert metadata["number"] == "157"
    assert metadata["year"] == "2024"


def test_citation_words_at_the_very_start_do_not_blind_the_title_search(extractor):
    """The cleaner sometimes hoists "Menimbang Mengingat" to character 0.

    A title-block guard of the form ``start > 200`` then declines to cut and
    hands the whole document -- citation list included -- to the search.
    """
    text = (
        "Menimbang Mengingat Menetapkan SALINAN\nPRESIDEN\nREPUBLIK INDONESIA\n"
        "TAMBAHAN LEMBARAN NEGARA REPUBLIK INDONESIA NOMOR 6634\n"
        "PERATURAN PRESIDEN REPUBLIK INDONESIA\n"
        "NOMOR 157 TAHUN 2024\n"
        "TENTANG KEMENTERIAN IMIGRASI DAN PEMASYARAKATAN\n\n"
        "Mengingat : Undang-Undang Nomor 39 Tahun 2008 tentang Kementerian Negara;\n"
    )
    metadata = extractor.extract(text)
    assert metadata["number"] == "157"
    assert metadata["year"] == "2024"


def test_an_emergency_regulation_is_not_filed_as_a_government_regulation(extractor):
    """Perppu vs PP: alternation order decides, and both mint a document_id."""
    text = (
        "PERATURAN PEMERINTAH PENGGANTI UNDANG-UNDANG REPUBLIK INDONESIA\n"
        "NOMOR 2 TAHUN 2022\nTENTANG CIPTA KERJA\n\nMenimbang : a. bahwa ...\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "Perppu"
    assert metadata["number"] == "2"


def test_the_constitution_is_not_filed_as_an_ordinary_law(extractor):
    text = (
        "UNDANG-UNDANG DASAR NEGARA REPUBLIK INDONESIA\n"
        "NOMOR 1 TAHUN 1945\nTENTANG PEMBUKAAN\n\nMenimbang : ...\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "UUD"


# ---------------------------------------------------------------------------
# INNOCENCE -- behaviour that must not change
# ---------------------------------------------------------------------------


def test_a_plain_law_is_extracted_exactly_as_before(extractor):
    """UU 40/2007 (Perseroan Terbatas), verbatim opening of the real PDF."""
    text = (
        "UNDANG-UNDANG REPUBLIK INDONESIA \nNOMOR 40 TAHUN 2007 \nTENTANG \n"
        "PERSEROAN TERBATAS \n\nDENGAN RAHMAT TUHAN YANG MAHA ESA \n\n"
        "PRESIDEN REPUBLIK INDONESIA, \n\nMenimbang : a. bahwa perekonomian nasional ...\n"
    )
    metadata = extractor.extract(text)
    assert metadata["type_abbrev"] == "UU"
    assert metadata["number"] == "40"
    assert metadata["year"] == "2007"


def test_a_letter_suffixed_number_keeps_its_letter(extractor):
    text = (
        "PERATURAN MENTERI KEUANGAN REPUBLIK INDONESIA\n"
        "NOMOR 12A TAHUN 2020\nTENTANG SESUATU\n\nMenimbang : ...\n"
    )
    metadata = extractor.extract(text)
    assert metadata["number"] == "12A"


def test_a_number_fused_with_its_year_yields_only_the_number():
    assert normalize_document_number("40/2007") == "40"
    assert normalize_document_number("12A-2007") == "12A"


def test_a_token_without_any_digit_is_refused():
    """Otherwise a stray word becomes a document number, and then an identity."""
    assert normalize_document_number("TENTANG") is None
    assert normalize_document_number("") is None
    assert normalize_document_number("...") is None


def test_the_ocr_correction_never_touches_a_ministerial_number():
    """Mapping I->1 on "M.IP-19.GR.01.01" would produce "M.1P-19.GR.01.01"."""
    assert normalize_document_number("M.IP-19.GR.01.01") == "M.IP-19.GR.01.01"


def test_no_title_match_still_falls_back_to_the_old_behaviour(extractor):
    """A document whose title block did not survive parsing must still yield."""
    text = "3. Undang-Undang tentang sesuatu\na. bahwa Presiden selaku Kepala Pemerintahan\n"
    metadata = extractor.extract(text)
    assert extract_title_identity(text) is None
    assert metadata["type_abbrev"] == "UU"
    assert metadata["number"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# STRUCTURAL TRIPWIRES
# ---------------------------------------------------------------------------


def test_every_declared_type_name_has_an_abbreviation():
    """A missing entry does not raise -- it silently changes document_id shape."""
    missing = [name for name in LEGAL_TYPE_NAMES if name not in LEGAL_TYPE_ABBREV]
    assert missing == [], f"types without an abbreviation: {missing}"


def test_type_names_are_ordered_longest_first_where_one_prefixes_another():
    """First-match-wins alternation: a prefix listed first shadows the longer name."""
    for shorter_index, shorter in enumerate(LEGAL_TYPE_NAMES):
        for longer_index, longer in enumerate(LEGAL_TYPE_NAMES):
            if longer != shorter and longer.startswith(shorter):
                assert longer_index < shorter_index, (
                    f"{longer!r} is shadowed by {shorter!r}: list it first"
                )


def test_the_title_pattern_does_not_backtrack_catastrophically():
    """This file carries a ReDoS scar; the gap bounds are load-bearing."""
    for payload in (
        "PERATURAN PEMERINTAH " + "A" * 200_000,
        "PERATURAN PEMERINTAH NOMOR " + "1" * 100_000,
    ):
        started = time.perf_counter()
        LEGAL_TITLE_PATTERN.search(payload)
        assert time.perf_counter() - started < 1.0


def test_the_number_token_cannot_swallow_the_year_keyword():
    """The token class excludes whitespace, so "NOMOR 40 TAHUN" cannot fuse."""
    match = LEGAL_TITLE_PATTERN.search("UNDANG-UNDANG NOMOR 40 TAHUN 2007")
    assert match is not None
    assert match.group("number") == "40"
    assert not re.search(r"\s", match.group("number"))
