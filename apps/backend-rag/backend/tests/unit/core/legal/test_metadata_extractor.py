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

    def test_extract_status_berlaku(self):
        """Test extracting status 'berlaku'"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

BERLAKU sejak tanggal ditetapkan."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] == "berlaku"

    def test_extract_status_masih_berlaku(self):
        """Test extracting status 'berlaku' with MASIH BERLAKU"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

MASIH BERLAKU hingga saat ini."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] == "berlaku"

    def test_extract_status_dicabut(self):
        """Test extracting status 'dicabut'"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

DICABUT dengan undang-undang baru."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] == "dicabut"

    def test_extract_status_tidak_berlaku(self):
        """Test extracting status 'dicabut' with TIDAK BERLAKU"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

TIDAK BERLAKU lagi."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] == "dicabut"

    def test_extract_status_diganti(self):
        """Test extracting status 'dicabut' with DIGANTI"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST

DIGANTI dengan peraturan baru."""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] == "dicabut"

    def test_extract_no_status(self):
        """Test extracting metadata without status"""
        text = """UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 12 TAHUN 2024
TENTANG TEST"""
        extractor = LegalMetadataExtractor()
        result = extractor.extract(text)

        assert result["status"] is None

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
