"""
Tests for LegalMetadataExtractor
"""

from backend.core.legal.metadata_extractor import LegalMetadataExtractor


class TestLegalMetadataExtractor:
    """Test suite for LegalMetadataExtractor"""

    def test_init(self):
        """Test extractor initialization"""
        extractor = LegalMetadataExtractor()
        assert extractor is not None

    def test_extract_empty_text(self):
        """Test extracting metadata from empty text"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract("")
        assert result == {}

    def test_extract_whitespace_only(self):
        """Test extracting metadata from whitespace-only text"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract("   \n\t  ")
        assert result == {}

    def test_extract_undang_undang(self):
        """Test extracting metadata from UNDANG-UNDANG"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST LEGAL DOCUMENT

DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "UNDANG-UNDANG"
        assert result["type_abbrev"] == "UU"
        assert result["number"] == "12"
        assert result["year"] == "2024"
        assert "TEST LEGAL DOCUMENT" in result["topic"]
        assert result["full_title"] is not None

    def test_extract_peraturan_pemerintah(self):
        """Test extracting metadata from PERATURAN PEMERINTAH"""
        text = """PERATURAN PEMERINTAH REPUBLIK INDONESIA
NOMOR 15 TAHUN 2023
TENTANG PERATURAN TEST

DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "PERATURAN PEMERINTAH"
        assert result["type_abbrev"] == "PP"
        assert result["number"] == "15"
        assert result["year"] == "2023"

    def test_extract_peraturan_presiden(self):
        """Perpres sources retain their own canonical legal type."""
        text = """PERATURAN PRESIDEN REPUBLIK INDONESIA
NOMOR 43 TAHUN 2011
TENTANG HAL UJI
"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "PERATURAN PRESIDEN"
        assert result["type_abbrev"] == "Perpres"
        assert result["number"] == "43"
        assert result["year"] == "2011"

    def test_extract_keputusan_presiden(self):
        """Test extracting metadata from KEPUTUSAN PRESIDEN"""
        text = """KEPUTUSAN PRESIDEN REPUBLIK INDONESIA
NOMOR 20 TAHUN 2024
TENTANG KEPUTUSAN TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "KEPUTUSAN PRESIDEN"
        assert result["type_abbrev"] == "Keppres"

    def test_extract_peraturan_menteri(self):
        """Test extracting metadata from PERATURAN MENTERI"""
        text = """PERATURAN MENTERI KESEHATAN REPUBLIK INDONESIA
NOMOR 5 TAHUN 2024
TENTANG PERATURAN MENTERI TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "PERATURAN MENTERI"
        assert result["type_abbrev"] == "Permen"

    def test_extract_number_with_letter(self):
        """Test extracting document number with letter suffix"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12A TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["number"] == "12A"

    def test_extract_number_with_slash(self):
        """Test extracting document number with slash format"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12/2024 TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        # Should extract "12" from "12/2024"
        assert result["number"] == "12"

    def test_extract_topic(self):
        """Test extracting topic from TENTANG clause"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG PENGELOLAAN SUMBER DAYA ALAM DAN LINGKUNGAN HIDUP

DENGAN RAHMAT TUHAN YANG MAHA ESA"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "PENGELOLAAN" in result["topic"]
        assert "SUMBER DAYA ALAM" in result["topic"]

    def test_extract_topic_long_text(self):
        """Test extracting topic with long text (should be truncated)"""
        long_topic = "A" * 300
        text = f"""UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG {long_topic}

DENGAN RAHMAT TUHAN YANG MAHA ESA"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert len(result["topic"]) <= 200  # Should be truncated

    # `status` extraction was RETIRED 2026-08-25 (Lane P, kb-p2-status-retire-0825):
    # a bare regex over chunk text cannot correctly answer "is this document
    # currently revoked" — that fact is always established by a LATER, different
    # instrument, never by the document's own body. See constants.py's tombstone
    # comment above `# Status indicators` and kb/inventory/immigration.yaml
    # LANE-A-1 for the measured damage this replaced.
    #
    # GUILT: each of these sentences used to set a status. None of them may set
    # one now — that is the whole retirement, and each represents a distinct real
    # false-positive shape found in production, not a hypothetical.
    def test_extract_does_not_set_status_on_class_exemption(self):
        """A provision not applying to a class of PERSON must not mark the
        document revoked. Measured live in UU_6_2011's own penjelasan."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Ketentuan ini tidak berlaku bagi warga negara asing."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "status" not in result

    def test_extract_does_not_set_status_on_substituted_guarantor(self):
        """DIGANTI matching inside "digantikan" must not mark the document
        revoked. Measured live in Permen_22_2023 (a guarantor being replaced)."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Penjamin dapat digantikan oleh penjamin lain."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "status" not in result

    def test_extract_does_not_set_status_on_predecessor_revocation(self):
        """A law's OWN closing clause revoking its PREDECESSOR must not mark
        the CURRENT, still-valid law as revoked. This is the live PP_31_2013
        defect (kb/inventory/immigration.yaml LANE-A-1) reproduced directly."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Pada saat Peraturan ini mulai berlaku, Keputusan Presiden Nomor 31
Tahun 1998 dicabut dan dinyatakan tidak berlaku."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "status" not in result

    def test_extract_does_not_set_status_on_commencement_clause(self):
        """The standard commencement clause is a TRUE statement about when the
        document took effect and a FALSE inference about whether it is still
        in force today — a law that commenced in 2011 may be dead by now. This
        is the shape that looks like a legitimate self-referential status
        statement and is exactly the trap: no fix aimed only at `dicabut`
        would have caught it, because it matches `berlaku`."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Peraturan Menteri ini mulai berlaku pada tanggal diundangkan."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "status" not in result

    # INNOCENCE: the retirement is surgical — every OTHER field the extractor
    # produced before is unchanged on the same input, and a document with none
    # of the guilt sentences above still gets no status key either (there is no
    # "correct" case left to preserve — see the constants.py tombstone comment).
    def test_extract_other_fields_unchanged_when_status_sentence_present(self):
        """Removing status extraction must not touch type/number/year/topic/
        full_title — the retirement's whole point is that it changes ONLY the
        one field that was wrong."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG PENGUJIAN METADATA

DENGAN RAHMAT TUHAN YANG MAHA ESA

Pada saat Peraturan ini mulai berlaku, Keputusan Presiden Nomor 31
Tahun 1998 dicabut dan dinyatakan tidak berlaku."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "UNDANG-UNDANG"
        assert result["type_abbrev"] == "UU"
        assert result["number"] == "12"
        assert result["year"] == "2024"
        assert result["topic"] == "PENGUJIAN METADATA"
        assert result["full_title"] == "UU No 12 Tahun 2024 Tentang PENGUJIAN METADATA"
        assert "status" not in result

    def test_extract_no_status(self):
        """A document with none of the guilt sentences still gets no status
        key — there was never a positive case worth preserving (see the
        constants.py tombstone comment: no fix aimed only at the revoked
        direction survives, since even the innocent-looking commencement
        clause is a trap)."""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert "status" not in result

    def test_extract_missing_type(self):
        """Test extracting metadata when type is missing"""
        text = """NOMOR 12 TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "UNKNOWN"
        assert result["type_abbrev"] == "UNKNOWN"

    def test_extract_missing_number(self):
        """Test extracting metadata when number is missing"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["number"] == "UNKNOWN"

    def test_extract_missing_year(self):
        """Test extracting metadata when year is missing"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["year"] == "UNKNOWN"

    def test_extract_missing_topic(self):
        """Test extracting metadata when topic is missing"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["topic"] == "UNKNOWN"

    def test_build_full_title(self):
        """Test _build_full_title method"""
        extractor = LegalMetadataExtractor()
        metadata = {
            "type_abbrev": "UU",
            "number": "12",
            "year": "2024",
            "topic": "TEST DOCUMENT",
        }
        title = extractor._build_full_title(metadata)

        assert "UU" in title
        assert "No 12" in title
        assert "Tahun 2024" in title
        assert "Tentang TEST DOCUMENT" in title

    def test_build_full_title_with_unknowns(self):
        """Test _build_full_title with UNKNOWN values"""
        extractor = LegalMetadataExtractor()
        metadata = {
            "type_abbrev": "UNKNOWN",
            "number": "UNKNOWN",
            "year": "UNKNOWN",
            "topic": "UNKNOWN",
        }
        title = extractor._build_full_title(metadata)

        assert title == "Unknown Legal Document"

    def test_build_full_title_partial(self):
        """Test _build_full_title with partial metadata"""
        extractor = LegalMetadataExtractor()
        metadata = {
            "type_abbrev": "UU",
            "number": "12",
            "year": "UNKNOWN",
            "topic": "TEST",
        }
        title = extractor._build_full_title(metadata)

        assert "UU" in title
        assert "No 12" in title
        assert "Tahun" not in title  # Should skip UNKNOWN year
        assert "Tentang TEST" in title

    def test_is_legal_document_true(self):
        """Test is_legal_document with valid legal document"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

Menimbang:
a. Pertimbangan

Pasal 1
Content"""
        extractor = LegalMetadataExtractor()
        result = extractor.is_legal_document(text)

        assert result is True

    def test_is_legal_document_with_markers(self):
        """Test is_legal_document with legal markers"""
        text = """Pasal 1
Content

Menimbang:
a. Pertimbangan

DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA"""
        extractor = LegalMetadataExtractor()
        result = extractor.is_legal_document(text)

        # Should have at least 2 markers
        assert result is True

    def test_is_legal_document_false(self):
        """Test is_legal_document with non-legal document"""
        text = """This is just a regular document
without any legal markers or structure."""
        extractor = LegalMetadataExtractor()
        result = extractor.is_legal_document(text)

        assert result is False

    def test_is_legal_document_empty(self):
        """Test is_legal_document with empty text"""
        extractor = LegalMetadataExtractor()
        result = extractor.is_legal_document("")

        assert result is False

    def test_is_legal_document_one_marker(self):
        """Test is_legal_document with only one marker (should be False)"""
        text = """Pasal 1
Content without other legal markers."""
        extractor = LegalMetadataExtractor()
        result = extractor.is_legal_document(text)

        # Should need at least 2 markers
        assert result is False

    def test_extract_qanun(self):
        """Test extracting metadata from QANUN"""
        text = """QANUN PROVINSI ACEH
NOMOR 3 TAHUN 2024
TENTANG QANUN TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "QANUN"
        assert result["type_abbrev"] == "Qanun"

    def test_extract_peraturan_daerah(self):
        """Test extracting metadata from PERATURAN DAERAH"""
        text = """PERATURAN DAERAH PROVINSI JAWA BARAT
NOMOR 5 TAHUN 2024
TENTANG PERDA TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "PERATURAN DAERAH"
        assert result["type_abbrev"] == "Perda"

    def test_extract_peraturan_kepala(self):
        """Test extracting metadata from PERATURAN KEPALA"""
        text = """PERATURAN KEPALA BADAN PUSAT STATISTIK
NOMOR 1 TAHUN 2024
TENTANG PERKEP TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["type"] == "PERATURAN KEPALA"
        assert result["type_abbrev"] == "Perkep"
