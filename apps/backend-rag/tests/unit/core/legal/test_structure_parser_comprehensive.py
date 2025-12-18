"""
Comprehensive tests for Legal Structure Parser
Target: 95%+ coverage
"""


class TestLegalStructureParserInit:
    """Test LegalStructureParser initialization"""

    def test_init(self):
        """Test initialization logs message"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        assert parser is not None


class TestLegalStructureParserParse:
    """Test parse method"""

    def test_parse_empty_text(self):
        """Test parse with empty text"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()
        result = parser.parse("")

        assert result == {}

    def test_parse_none_text(self):
        """Test parse with None text"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()
        result = parser.parse(None)

        assert result == {}

    def test_parse_whitespace_only(self):
        """Test parse with whitespace only"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()
        result = parser.parse("   \n\t  ")

        assert result == {}

    def test_parse_simple_document(self):
        """Test parse with simple document"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: bahwa untuk melaksanakan ketentuan...

MEMUTUSKAN:
Menetapkan: UNDANG-UNDANG TENTANG KEIMIGRASIAN

BAB I
KETENTUAN UMUM

Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang.
(2) Orang Asing adalah orang yang bukan WNI.

BAB II
KEWENANGAN

Pasal 2
Pemerintah berwenang dalam keimigrasian.
"""

        result = parser.parse(text)

        assert "konsiderans" in result
        assert "batang_tubuh" in result
        assert "penjelasan" in result
        assert "pasal_list" in result

        # Should have BAB
        assert len(result["batang_tubuh"]) >= 1

        # Should have Pasal
        assert len(result["pasal_list"]) >= 1

    def test_parse_document_with_penjelasan(self):
        """Test parse with document containing Penjelasan"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: test

BAB I
KETENTUAN UMUM

Pasal 1
Test pasal content.

Penjelasan Umum
Penjelasan atas undang-undang ini...
"""

        result = parser.parse(text)

        assert result["penjelasan"] is not None
        assert "Penjelasan" in result["penjelasan"]

    def test_parse_document_without_konsiderans(self):
        """Test parse without Konsiderans"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Test content.
"""

        result = parser.parse(text)

        assert result["konsiderans"] is None


class TestLegalStructureParserExtractKonsiderans:
    """Test _extract_konsiderans_with_index method"""

    def test_extract_konsiderans_with_menimbang(self):
        """Test extraction with Menimbang marker"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: bahwa untuk melaksanakan ketentuan pasal 5
ayat 1 Undang-Undang Dasar...

MEMUTUSKAN:
Menetapkan: UNDANG-UNDANG
"""

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "Menimbang" in konsiderans
        assert end_index is not None

    def test_extract_konsiderans_with_mengingat(self):
        """Test extraction with Mengingat marker"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Mengingat: Pasal 5 ayat 1 UUD 1945...

BAB I
KETENTUAN UMUM
"""

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "Mengingat" in konsiderans

    def test_extract_konsiderans_no_marker(self):
        """Test extraction without any marker"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Content here.
"""

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is None
        assert end_index is None

    def test_extract_konsiderans_ends_at_bab(self):
        """Test Konsiderans ends at BAB"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: test consideration

BAB I
KETENTUAN UMUM
"""

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "BAB" not in konsiderans

    def test_extract_konsiderans_ends_at_pasal(self):
        """Test Konsiderans ends at Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: test consideration

Pasal 1
First article.
"""

        konsiderans, end_index = parser._extract_konsiderans_with_index(text)

        assert konsiderans is not None
        assert "Pasal" not in konsiderans

    def test_extract_konsiderans_backward_compat(self):
        """Test _extract_konsiderans wrapper"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Menimbang: test"

        result = parser._extract_konsiderans(text)

        assert result is not None


class TestLegalStructureParserParseBatangTubuh:
    """Test _parse_batang_tubuh method"""

    def test_parse_batang_tubuh_single_bab(self):
        """Test parsing single BAB"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Test content.
"""

        result = parser._parse_batang_tubuh(text)

        assert len(result) == 1
        assert result[0]["number"] == "I"
        assert result[0]["title"] == "KETENTUAN UMUM"

    def test_parse_batang_tubuh_multiple_bab(self):
        """Test parsing multiple BAB"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Content 1.

BAB II
KEWENANGAN

Pasal 2
Content 2.

BAB III
PENUTUP

Pasal 3
Content 3.
"""

        result = parser._parse_batang_tubuh(text)

        assert len(result) == 3
        assert result[0]["number"] == "I"
        assert result[1]["number"] == "II"
        assert result[2]["number"] == "III"

    def test_parse_batang_tubuh_no_bab(self):
        """Test parsing without BAB"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Pasal 1
Content.

Pasal 2
More content.
"""

        result = parser._parse_batang_tubuh(text)

        assert len(result) == 0


class TestLegalStructureParserParseBagian:
    """Test _parse_bagian method"""

    def test_parse_bagian_single(self):
        """Test parsing single Bagian"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Bagian Kesatu
Umum

Pasal 1
Content.
"""

        result = parser._parse_bagian(text)

        assert len(result) == 1
        assert result[0]["number"] == "Kesatu"
        assert result[0]["title"] == "Umum"

    def test_parse_bagian_multiple(self):
        """Test parsing multiple Bagian"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Bagian Kesatu
Umum

Pasal 1
Content 1.

Bagian Kedua
Khusus

Pasal 2
Content 2.
"""

        result = parser._parse_bagian(text)

        assert len(result) == 2
        assert result[0]["number"] == "Kesatu"
        assert result[1]["number"] == "Kedua"

    def test_parse_bagian_empty(self):
        """Test parsing without Bagian"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Pasal 1\nContent."

        result = parser._parse_bagian(text)

        assert len(result) == 0


class TestLegalStructureParserParseParagraf:
    """Test _parse_paragraf method"""

    def test_parse_paragraf_single(self):
        """Test parsing single Paragraf"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Paragraf 1
Definisi

Pasal 1
Content.
"""

        result = parser._parse_paragraf(text)

        assert len(result) == 1
        assert result[0]["number"] == "1"
        assert result[0]["title"] == "Definisi"

    def test_parse_paragraf_multiple(self):
        """Test parsing multiple Paragraf"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Paragraf 1
Definisi

Paragraf 2
Ruang Lingkup

Paragraf 3
Asas
"""

        result = parser._parse_paragraf(text)

        assert len(result) == 3

    def test_parse_paragraf_empty(self):
        """Test parsing without Paragraf"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Pasal 1\nContent."

        result = parser._parse_paragraf(text)

        assert len(result) == 0


class TestLegalStructureParserParsePasal:
    """Test _parse_pasal_in_section method"""

    def test_parse_pasal_single(self):
        """Test parsing single Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang.
(2) Orang Asing adalah orang yang bukan WNI.
"""

        result = parser._parse_pasal_in_section(text)

        assert len(result) == 1
        assert result[0]["number"] == "1"
        assert len(result[0]["ayat"]) >= 1

    def test_parse_pasal_multiple(self):
        """Test parsing multiple Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Pasal 1
Content 1.

Pasal 2
Content 2.

Pasal 3
Content 3.
"""

        result = parser._parse_pasal_in_section(text)

        assert len(result) == 3

    def test_parse_pasal_with_letter(self):
        """Test parsing Pasal with letter (e.g., 1A)"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Pasal 1
Content.

Pasal 1A
Additional content.
"""

        result = parser._parse_pasal_in_section(text)

        assert len(result) >= 1

    def test_parse_pasal_empty(self):
        """Test parsing without Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Some text without articles."

        result = parser._parse_pasal_in_section(text)

        assert len(result) == 0


class TestLegalStructureParserParseAyat:
    """Test _parse_ayat method"""

    def test_parse_ayat_single(self):
        """Test parsing single Ayat"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
(1) First clause content.
"""

        result = parser._parse_ayat(text)

        assert len(result) == 1
        assert result[0]["number"] == "1"

    def test_parse_ayat_multiple(self):
        """Test parsing multiple Ayat"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
(1) First clause.
(2) Second clause.
(3) Third clause.
"""

        result = parser._parse_ayat(text)

        assert len(result) == 3
        assert result[0]["number"] == "1"
        assert result[1]["number"] == "2"
        assert result[2]["number"] == "3"

    def test_parse_ayat_empty(self):
        """Test parsing without Ayat"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Simple text without numbered clauses."

        result = parser._parse_ayat(text)

        assert len(result) == 0


class TestLegalStructureParserExtractPasalList:
    """Test _extract_pasal_list method"""

    def test_extract_pasal_list(self):
        """Test extracting full pasal list with context"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Content for pasal 1.
(1) Ayat 1.

BAB II
KEWENANGAN

Pasal 2
Content for pasal 2.
"""

        result = parser._extract_pasal_list(text)

        assert len(result) >= 1

        # Check structure
        for pasal in result:
            assert "number" in pasal
            assert "text" in pasal
            assert "ayat" in pasal
            assert "bab_context" in pasal

    def test_extract_pasal_list_empty(self):
        """Test extracting from text without Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Text without any articles."

        result = parser._extract_pasal_list(text)

        assert len(result) == 0


class TestLegalStructureParserFindBabContext:
    """Test _find_bab_context method"""

    def test_find_bab_context_found(self):
        """Test finding BAB context for position"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Pasal 1
Content.
"""

        # Position after BAB I
        result = parser._find_bab_context(text, 50)

        assert result is not None
        assert "BAB I" in result
        assert "KETENTUAN UMUM" in result

    def test_find_bab_context_multiple_bab(self):
        """Test finding correct BAB among multiple"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
FIRST

Some text.

BAB II
SECOND

Pasal here.
"""

        # Position in BAB II area
        result = parser._find_bab_context(text, len(text) - 10)

        assert result is not None
        assert "BAB II" in result

    def test_find_bab_context_not_found(self):
        """Test when position is before any BAB"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Some text before.

BAB I
KETENTUAN UMUM
"""

        # Position before BAB I
        result = parser._find_bab_context(text, 5)

        assert result is None

    def test_find_bab_context_no_bab(self):
        """Test when no BAB exists"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = "Text without any BAB markers."

        result = parser._find_bab_context(text, 10)

        assert result is None


class TestLegalStructureParserIntegration:
    """Integration tests for complete parsing"""

    def test_parse_complete_document(self):
        """Test parsing a complete legal document structure"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Menimbang: bahwa untuk melaksanakan ketentuan Pasal 5 ayat 1 UUD...

Mengingat: Undang-Undang Dasar 1945...

MEMUTUSKAN:
Menetapkan: UNDANG-UNDANG TENTANG KEIMIGRASIAN

BAB I
KETENTUAN UMUM

Bagian Kesatu
Umum

Paragraf 1
Definisi

Pasal 1
Dalam Undang-Undang ini yang dimaksud dengan:
(1) Keimigrasian adalah hal ihwal lalu lintas orang yang masuk atau keluar Wilayah Indonesia.
(2) Wilayah Indonesia adalah seluruh wilayah Negara Kesatuan Republik Indonesia.

Pasal 2
Keimigrasian merupakan bagian dari perwujudan kedaulatan negara.

BAB II
KEWENANGAN

Pasal 3
(1) Pemerintah mempunyai kewenangan dalam keimigrasian.
(2) Kewenangan sebagaimana dimaksud pada ayat (1) dilaksanakan oleh Menteri.

BAB III
PENUTUP

Pasal 4
Undang-Undang ini mulai berlaku pada tanggal diundangkan.

Penjelasan Umum
Penjelasan atas Undang-Undang ini memberikan penjelasan lebih lanjut...
"""

        result = parser.parse(text)

        # Validate structure
        assert result["konsiderans"] is not None
        assert "Menimbang" in result["konsiderans"]

        assert len(result["batang_tubuh"]) == 3  # BAB I, II, III
        assert result["batang_tubuh"][0]["number"] == "I"
        assert result["batang_tubuh"][1]["number"] == "II"
        assert result["batang_tubuh"][2]["number"] == "III"

        assert len(result["pasal_list"]) >= 3

        assert result["penjelasan"] is not None
        assert "Penjelasan" in result["penjelasan"]

    def test_parse_document_hierarchy(self):
        """Test that BAB contains Bagian, Bagian contains Paragraf"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
BAB I
KETENTUAN UMUM

Bagian Kesatu
Definisi

Paragraf 1
Istilah

Pasal 1
Content.
"""

        result = parser.parse(text)

        assert len(result["batang_tubuh"]) >= 1

        bab = result["batang_tubuh"][0]
        assert "bagian" in bab
        assert len(bab["bagian"]) >= 1

        bagian = bab["bagian"][0]
        assert "paragraf" in bagian

    def test_parse_minimal_document(self):
        """Test parsing minimal document with just one Pasal"""
        from backend.core.legal.structure_parser import LegalStructureParser

        parser = LegalStructureParser()

        text = """
Pasal 1
Simple regulation content.
"""

        result = parser.parse(text)

        assert result["konsiderans"] is None
        assert len(result["batang_tubuh"]) == 0
        assert len(result["pasal_list"]) >= 1
        assert result["penjelasan"] is None
