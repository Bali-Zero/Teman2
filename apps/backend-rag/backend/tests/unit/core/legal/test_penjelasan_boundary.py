"""The elucidation is a distinct part of a law, not part of its body.

Every Indonesian law is published with its PENJELASAN, the official
article-by-article commentary, which repeats the same article numbers. Until
2026-08-25 the boundary between the two was never found, so the commentary was
parsed AS the law: its chunk ids collided with the real articles and destroyed
them.

Measured on UU 40/2007 (Perseroan Terbatas): the real heading sits at character
133,167; the old pattern instead matched at 201,998, 68,000 characters too late.
The consequence in production was Pasal 32 -- the minimum-capital rule a PT PMA
is founded on -- holding the words "Cukup jelas" ("self-explanatory") instead of
"Modal dasar Perseroan paling sedikit Rp 50.000.000,00".
"""

import pytest

from backend.core.legal.constants import PENJELASAN_PATTERN
from backend.core.legal.hierarchical_indexer import HierarchicalIndexer
from backend.core.legal.structure_parser import LegalStructureParser

# Verbatim shape of the real gazette heading, leading space included -- that
# single space is what the previous pattern could not cross.
REAL_HEADING = "\n PENJELASAN \nATAS \nUNDANG-UNDANG REPUBLIK INDONESIA \nNOMOR 40 TAHUN 2007 \n"

DOCUMENT = (
    "UNDANG-UNDANG REPUBLIK INDONESIA\nNOMOR 40 TAHUN 2007\nTENTANG PERSEROAN TERBATAS\n\n"
    "Menimbang : a. bahwa ...\n\n"
    "BAB I\nKETENTUAN UMUM\n\n"
    "Pasal 1\nDalam Undang-Undang ini yang dimaksud dengan Perseroan Terbatas adalah badan hukum.\n\n"
    "Pasal 32\n(1) Modal dasar Perseroan paling sedikit Rp 50.000.000,00 (lima puluh juta rupiah).\n\n"
    + REAL_HEADING
    + "I. UMUM\nUndang-Undang ini disusun untuk memberikan kepastian hukum.\n\n"
    "II. PASAL DEMI PASAL\n\n"
    "Pasal 1\nCukup jelas.\n\n"
    "Pasal 32\nAyat (1)\nCukup jelas.\n"
)


@pytest.fixture
def parser() -> LegalStructureParser:
    return LegalStructureParser()


# ---------------------------------------------------------------------------
# GUILT
# ---------------------------------------------------------------------------


def test_an_indented_heading_is_still_a_heading():
    """The real gazette heading carries a leading space. The old pattern
    required column 0 and therefore never found the true boundary."""
    match = PENJELASAN_PATTERN.search(DOCUMENT)
    assert match is not None
    assert DOCUMENT[match.start() : match.start() + 40].strip().upper().startswith("PENJELASAN")


def test_an_in_sentence_mention_is_not_a_section_boundary():
    """A line wrap can put an ordinary phrase at the start of a line. The old
    pattern accepted `Penjelasan Pasal ...` and so chose a boundary 68,000
    characters into the commentary."""
    prose = (
        "Ketentuan ini harus dibaca bersama dengan\n"
        "penjelasan Pasal 123 ayat (2) huruf c dan Pasal 125 ayat (6)\nhuruf d.\n"
    )
    assert PENJELASAN_PATTERN.search(prose) is None


def test_the_commentary_never_enters_the_body_article_list(parser):
    structure = parser.parse(DOCUMENT)
    body_numbers = [p["number"] for p in structure["pasal_list"]]
    commentary_numbers = [p["number"] for p in structure["penjelasan_pasal_list"]]
    assert body_numbers == ["1", "32"]
    assert commentary_numbers == ["1", "32"]


def test_the_operative_article_keeps_the_rule_not_the_note(parser):
    """The exact production failure: Pasal 32 held "Cukup jelas"."""
    structure = parser.parse(DOCUMENT)
    pasal_32 = next(p for p in structure["pasal_list"] if p["number"] == "32")
    assert "Rp 50.000.000,00" in pasal_32["text"]
    assert "Cukup jelas" not in pasal_32["text"]


@pytest.mark.asyncio
async def test_commentary_chunks_carry_their_own_id_and_label():
    indexer = HierarchicalIndexer.__new__(HierarchicalIndexer)
    indexer.chunker = None
    chunks: list = []
    await indexer._add_pasal_to_chunks(
        pasal={"number": "32", "text": "Cukup jelas.", "ayat": [], "bab_context": None},
        document_id="UU_40_2007",
        bab_id=None,
        bab_title=None,
        metadata={},
        chunks_to_index=chunks,
        section="penjelasan",
    )
    assert chunks[0].chunk_id == "UU_40_2007_Penjelasan_Pasal_32"
    assert chunks[0].metadata["section"] == "penjelasan"


# ---------------------------------------------------------------------------
# INNOCENCE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_an_operative_article_keeps_the_id_it_always_had():
    """Point ids are derived from chunk_id. If the body's ids changed, every
    unaffected document in the corpus would be re-keyed for nothing."""
    indexer = HierarchicalIndexer.__new__(HierarchicalIndexer)
    indexer.chunker = None
    chunks: list = []
    await indexer._add_pasal_to_chunks(
        pasal={"number": "32", "text": "Modal dasar ...", "ayat": [], "bab_context": None},
        document_id="UU_40_2007",
        bab_id=None,
        bab_title=None,
        metadata={},
        chunks_to_index=chunks,
    )
    assert chunks[0].chunk_id == "UU_40_2007_Pasal_32"
    assert chunks[0].metadata["section"] == "batang_tubuh"


def test_a_document_without_an_elucidation_is_untouched(parser):
    plain = (
        "PERATURAN MENTERI\nNOMOR 5 TAHUN 2024\nTENTANG SESUATU\n\n"
        "Menimbang : a. bahwa ...\n\nPasal 1\nKetentuan pertama.\n\nPasal 2\nKetentuan kedua.\n"
    )
    structure = parser.parse(plain)
    assert structure["penjelasan"] is None
    assert structure["penjelasan_pasal_list"] == []
    assert structure["penjelasan_umum"] is None
    assert [p["number"] for p in structure["pasal_list"]] == ["1", "2"]


def test_the_general_part_is_the_narrative_only_never_the_whole_commentary(parser):
    """Falling back to the full elucidation text would store every article's
    commentary twice -- once as entries, once inside the narrative blob."""
    structure = parser.parse(DOCUMENT)
    general = structure["penjelasan_umum"]
    assert general is not None
    assert "UMUM" in general.upper()
    assert "PASAL DEMI PASAL" not in general.upper() or len(general) < len(structure["penjelasan"])
    assert len(general) < len(structure["penjelasan"])


def test_both_letter_cases_of_the_heading_are_accepted():
    for heading in (" PENJELASAN \nATAS \nUNDANG-UNDANG\n", " Penjelasan Umum\n"):
        assert PENJELASAN_PATTERN.search("Pasal 1\nisi\n" + heading) is not None
