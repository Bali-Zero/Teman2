"""
Comprehensive tests for Legal Metadata Extractor
Target: 95%+ coverage
"""


class TestLegalMetadataExtractorInit:
    """Test LegalMetadataExtractor initialization"""

    def test_init(self):
        """Test initialization logs message"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        assert extractor is not None


class TestLegalMetadataExtractorExtract:
    """Test extract method"""

    def test_extract_empty_text(self):
        """Test extract with empty text"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()
        result = extractor.extract("")

        assert result == {}

    def test_extract_none_text(self):
        """Test extract with None text"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()
        result = extractor.extract(None)

        assert result == {}

    def test_extract_whitespace_only(self):
        """Test extract with whitespace only"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()
        result = extractor.extract("   \n\t  ")

        assert result == {}

    def test_extract_undang_undang(self):
        """Test extracting UNDANG-UNDANG metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN
"""

        result = extractor.extract(text)

        assert result["type"] == "UNDANG-UNDANG"
        assert result["type_abbrev"] == "UU"
        assert result["number"] == "6"
        assert result["year"] == "2011"
        assert result["topic"] == "KEIMIGRASIAN"
        assert "full_title" in result

    def test_extract_peraturan_pemerintah(self):
        """Test extracting PERATURAN PEMERINTAH metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
PERATURAN PEMERINTAH REPUBLIK INDONESIA
NOMOR 31 TAHUN 2013
TENTANG PERATURAN PELAKSANAAN UNDANG-UNDANG
"""

        result = extractor.extract(text)

        assert result["type"] == "PERATURAN PEMERINTAH"
        assert result["type_abbrev"] == "PP"
        assert result["number"] == "31"
        assert result["year"] == "2013"

    def test_extract_keputusan_presiden(self):
        """Test extracting KEPUTUSAN PRESIDEN metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
KEPUTUSAN PRESIDEN REPUBLIK INDONESIA
NOMOR 12 TAHUN 2020
TENTANG PENETAPAN BENCANA
"""

        result = extractor.extract(text)

        assert result["type"] == "KEPUTUSAN PRESIDEN"
        assert result["type_abbrev"] == "Keppres"

    def test_extract_peraturan_menteri(self):
        """Test extracting PERATURAN MENTERI metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
PERATURAN MENTERI HUKUM DAN HAK ASASI MANUSIA
NOMOR 27 TAHUN 2014
TENTANG PROSEDUR TEKNIS
"""

        result = extractor.extract(text)

        assert result["type"] == "PERATURAN MENTERI"
        assert result["type_abbrev"] == "Permen"

    def test_extract_qanun(self):
        """Test extracting QANUN metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
QANUN ACEH
NOMOR 6 TAHUN 2014
TENTANG HUKUM JINAYAT
"""

        result = extractor.extract(text)

        assert result["type"] == "QANUN"
        assert result["type_abbrev"] == "Qanun"

    def test_extract_peraturan_daerah(self):
        """Test extracting PERATURAN DAERAH metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
PERATURAN DAERAH PROVINSI BALI
NOMOR 5 TAHUN 2019
TENTANG PARIWISATA
"""

        result = extractor.extract(text)

        assert result["type"] == "PERATURAN DAERAH"
        assert result["type_abbrev"] == "Perda"

    def test_extract_unknown_type(self):
        """Test extracting with unknown document type"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
SOME UNKNOWN DOCUMENT
NOMOR 1 TAHUN 2024
TENTANG SOMETHING
"""

        result = extractor.extract(text)

        assert result["type"] == "UNKNOWN"
        assert result["type_abbrev"] == "UNKNOWN"

    def test_extract_number_with_letter(self):
        """Test extracting number with letter suffix"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6A TAHUN 2011
TENTANG KEIMIGRASIAN
"""

        result = extractor.extract(text)

        assert result["number"] == "6A"

    def test_extract_missing_number(self):
        """Test extracting with missing number"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
TAHUN 2011
TENTANG KEIMIGRASIAN
"""

        result = extractor.extract(text)

        assert result["number"] == "UNKNOWN"

    def test_extract_missing_year(self):
        """Test extracting with missing year"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6
TENTANG KEIMIGRASIAN
"""

        result = extractor.extract(text)

        assert result["year"] == "UNKNOWN"

    def test_extract_missing_topic(self):
        """Test extracting with missing topic"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
"""

        result = extractor.extract(text)

        assert result["topic"] == "UNKNOWN"

    def test_extract_long_topic_truncated(self):
        """Test that long topic is truncated"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        long_topic = "A" * 500
        text = f"""
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG {long_topic}
"""

        result = extractor.extract(text)

        assert len(result["topic"]) <= 200

    def test_extract_status_dicabut(self):
        """Test extracting dicabut status"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN

Status: DICABUT DAN DINYATAKAN TIDAK BERLAKU
"""

        result = extractor.extract(text)

        assert result["status"] == "dicabut"

    def test_extract_status_berlaku(self):
        """Test extracting berlaku status"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN

Status: MASIH BERLAKU
"""

        result = extractor.extract(text)

        assert result["status"] == "berlaku"

    def test_extract_status_none(self):
        """Test extracting with no status"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN
"""

        result = extractor.extract(text)

        assert result["status"] is None

    def test_extract_topic_with_dengan_rahmat(self):
        """Test topic extraction stops at DENGAN RAHMAT"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN

DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA
"""

        result = extractor.extract(text)

        assert "DENGAN RAHMAT" not in result["topic"]

    def test_extract_topic_whitespace_normalized(self):
        """Test topic whitespace is normalized"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN
   DAN   HAL   TERKAIT
"""

        result = extractor.extract(text)

        # Multiple spaces should be normalized
        assert "   " not in result["topic"]


class TestLegalMetadataExtractorBuildFullTitle:
    """Test _build_full_title method"""

    def test_build_full_title_complete(self):
        """Test building full title with all fields"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        metadata = {
            "type_abbrev": "UU",
            "number": "6",
            "year": "2011",
            "topic": "KEIMIGRASIAN",
        }

        result = extractor._build_full_title(metadata)

        assert "UU" in result
        assert "No 6" in result
        assert "Tahun 2011" in result
        assert "Tentang KEIMIGRASIAN" in result

    def test_build_full_title_unknown_type(self):
        """Test building full title with unknown type"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        metadata = {
            "type_abbrev": "UNKNOWN",
            "number": "6",
            "year": "2011",
            "topic": "KEIMIGRASIAN",
        }

        result = extractor._build_full_title(metadata)

        assert "UNKNOWN" not in result

    def test_build_full_title_unknown_number(self):
        """Test building full title with unknown number"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        metadata = {
            "type_abbrev": "UU",
            "number": "UNKNOWN",
            "year": "2011",
            "topic": "KEIMIGRASIAN",
        }

        result = extractor._build_full_title(metadata)

        assert "No UNKNOWN" not in result

    def test_build_full_title_all_unknown(self):
        """Test building full title with all unknown"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        metadata = {
            "type_abbrev": "UNKNOWN",
            "number": "UNKNOWN",
            "year": "UNKNOWN",
            "topic": "UNKNOWN",
        }

        result = extractor._build_full_title(metadata)

        assert result == "Unknown Legal Document"

    def test_build_full_title_empty_metadata(self):
        """Test building full title with empty metadata"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        metadata = {}

        result = extractor._build_full_title(metadata)

        assert result == "Unknown Legal Document"


class TestLegalMetadataExtractorIsLegalDocument:
    """Test is_legal_document method"""

    def test_is_legal_document_empty(self):
        """Test with empty text"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        assert extractor.is_legal_document("") is False
        assert extractor.is_legal_document(None) is False

    def test_is_legal_document_with_type_pattern(self):
        """Test detection with legal type pattern"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = "UNDANG-UNDANG REPUBLIK INDONESIA tentang sesuatu"

        assert extractor.is_legal_document(text) is True

    def test_is_legal_document_with_pasal_and_menimbang(self):
        """Test detection with Pasal and Menimbang markers"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
Menimbang: bahwa untuk melaksanakan...

Pasal 1
Ketentuan umum...
"""

        assert extractor.is_legal_document(text) is True

    def test_is_legal_document_with_mengingat_and_pasal(self):
        """Test detection with Mengingat and Pasal"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
Mengingat: Undang-Undang Dasar 1945...

Pasal 1
Content...
"""

        assert extractor.is_legal_document(text) is True

    def test_is_legal_document_with_presiden(self):
        """Test detection with PRESIDEN marker"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
DENGAN RAHMAT TUHAN YANG MAHA ESA
PRESIDEN REPUBLIK INDONESIA

Menimbang: bahwa...
"""

        assert extractor.is_legal_document(text) is True

    def test_is_legal_document_non_legal(self):
        """Test with non-legal document"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
This is just a regular document about programming.
It has nothing to do with Indonesian law.
"""

        assert extractor.is_legal_document(text) is False

    def test_is_legal_document_single_marker(self):
        """Test with only one marker (not enough)"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
Pasal 1
This document only has one legal marker.
"""

        # Only 1 marker, needs at least 2
        assert extractor.is_legal_document(text) is False


class TestLegalMetadataExtractorIntegration:
    """Integration tests"""

    def test_extract_complete_document(self):
        """Test extracting from complete legal document"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
UNDANG-UNDANG REPUBLIK INDONESIA
NOMOR 6 TAHUN 2011
TENTANG KEIMIGRASIAN

DENGAN RAHMAT TUHAN YANG MAHA ESA

PRESIDEN REPUBLIK INDONESIA,

Menimbang: bahwa untuk melaksanakan ketentuan Pasal 26 ayat (2)
Undang-Undang Dasar Negara Republik Indonesia Tahun 1945, negara
menjamin hak warga negara untuk berpindah, pergi meninggalkan,
dan kembali ke Negara Kesatuan Republik Indonesia;

Mengingat: Pasal 5 ayat (1) Undang-Undang Dasar 1945;

MEMUTUSKAN:

Menetapkan: UNDANG-UNDANG TENTANG KEIMIGRASIAN

BAB I
KETENTUAN UMUM

Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang yang masuk atau keluar
Wilayah Indonesia serta pengawasannya dalam rangka menjaga tegaknya
kedaulatan negara.
"""

        result = extractor.extract(text)

        assert result["type"] == "UNDANG-UNDANG"
        assert result["type_abbrev"] == "UU"
        assert result["number"] == "6"
        assert result["year"] == "2011"
        assert "KEIMIGRASIAN" in result["topic"]
        assert "UU No 6 Tahun 2011" in result["full_title"]

    def test_extract_and_validate(self):
        """Test extract and validate with is_legal_document"""
        from backend.core.legal.metadata_extractor import LegalMetadataExtractor

        extractor = LegalMetadataExtractor()

        text = """
PERATURAN PEMERINTAH REPUBLIK INDONESIA
NOMOR 31 TAHUN 2013
TENTANG PERATURAN PELAKSANAAN UNDANG-UNDANG NOMOR 6 TAHUN 2011

Menimbang: test
Pasal 1
Content
"""

        # Should be recognized as legal document
        assert extractor.is_legal_document(text) is True

        # Should extract metadata
        result = extractor.extract(text)
        assert result["type"] == "PERATURAN PEMERINTAH"
        assert result["number"] == "31"
        assert result["year"] == "2013"
